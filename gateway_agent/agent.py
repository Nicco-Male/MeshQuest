#!/usr/bin/env python3
"""MeshQuest gateway: Python 3.9+, stdlib core, suitable for Raspberry Pi Zero W ARMv6.

No gameplay decisions, traceroute, commands or radio transmissions. A separate
server-authorized radio command module will be needed in a future release.
"""
import argparse
import json
import os
import re
import sqlite3
import stat
import sys
import threading
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from gateway_agent.monitor import metadata
except ModuleNotFoundError:
    from monitor import metadata  # direct script execution

AGENT_VERSION = "0.4.0a0"
_NODE_ID = re.compile(r"^![0-9a-fA-F]{8}$")


def read_token(path):
    token_file = Path(path)
    if token_file.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise ValueError("Token file must be private: chmod 600 " + str(token_file))
    token = token_file.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise ValueError("Invalid gateway token length")
    return token


def server_url(url):
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password:
        return url.rstrip("/")
    if (parts.scheme == "http" and parts.hostname in ("localhost", "127.0.0.1", "::1")
            and not parts.username and not parts.password):
        return url.rstrip("/")
    raise ValueError("Use HTTPS for non-local MeshQuest servers")


class ServerClient:
    def __init__(self, url, token, staging_password="", opener=urlopen):
        self.url = server_url(url)
        self.token = token
        self.staging_password = staging_password
        self.opener = opener

    def post(self, endpoint, payload):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = {"Authorization": "Bearer " + self.token,
                   "Content-Type": "application/json", "User-Agent": "MeshQuest-Gateway/" + AGENT_VERSION}
        if self.staging_password:
            headers["X-MeshQuest-Staging-Password"] = self.staging_password
        req = Request(self.url + endpoint, data=body, headers=headers, method="POST")
        with self.opener(req, timeout=8) as response:
            return json.loads(response.read(4096).decode("utf-8"))


class DiskQueue:
    """Bounded SQLite queue: no RAM-only backlog, predictable on a 512 MB device."""
    def __init__(self, location, limit=256):
        if limit < 1:
            raise ValueError("Invalid queue limit")
        path = Path(location).expanduser()
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, timeout=5)
        self.conn.execute("CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY, event_id TEXT UNIQUE, payload TEXT NOT NULL)")
        self.conn.commit()
        self.limit = limit

    def add(self, payload):
        with self.lock:
            self.conn.execute("INSERT OR IGNORE INTO queue(event_id, payload) VALUES (?,?)",
                              (payload["event_id"], json.dumps(payload, separators=(",", ":"))))
            total = self.conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]
            if total > self.limit:
                self.conn.execute("DELETE FROM queue WHERE id IN (SELECT id FROM queue ORDER BY id LIMIT ?)",
                                  (total - self.limit,))
                print("Gateway queue reached its size limit; oldest metadata discarded", file=sys.stderr)
            self.conn.commit()

    def first(self):
        with self.lock:
            row = self.conn.execute("SELECT id,payload FROM queue ORDER BY id LIMIT 1").fetchone()
            return (row[0], json.loads(row[1])) if row else None

    def delete(self, seq):
        with self.lock:
            self.conn.execute("DELETE FROM queue WHERE id=?", (seq,))
            self.conn.commit()

    def count(self):
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM queue").fetchone()[0]

    def close(self):
        with self.lock:
            self.conn.close()


def normalize_packet(packet, channel):
    """Capture metadata only for the chosen MeshQuest channel, excluding MQTT.

    No decoded chat text or device location is ever sent or stored in the queue.
    """
    if not isinstance(packet, dict) or packet.get("channel") != channel or packet.get("viaMqtt", False):
        return None
    info = metadata(packet)
    sender = info.get("sender")
    sender_node_id = sender.lower() if isinstance(sender, str) and _NODE_ID.fullmatch(sender) else None
    raw_id = info.get("packet_id")
    if isinstance(raw_id, int) and 0 <= raw_id <= 0xffffffff and sender_node_id:
        event_id = "radio-" + sender_node_id[1:] + "-" + format(raw_id, "08x")
    else:
        event_id = "radio-" + uuid.uuid4().hex
    port = info.get("portnum")
    if port is not None:
        port = str(port)[:64]
    return {
        "event_id": event_id, "observation_type": "packet_metadata_only",
        "channel_index": channel, "sender_node_id": sender_node_id, "portnum": port,
        "hop_start": info.get("hop_start"), "hop_limit": info.get("hop_limit"),
        "rx_rssi": info.get("rx_rssi"), "rx_snr": info.get("rx_snr"),
        "via_mqtt": False,
    }


def connect_radio(serial_device, tcp_host, tcp_port):
    try:
        from meshtastic.serial_interface import SerialInterface
        from meshtastic.tcp_interface import TCPInterface
    except ImportError as exc:
        raise RuntimeError("Install Meshtastic Python library on the gateway: pip install meshtastic") from exc
    return SerialInterface(devPath=serial_device) if serial_device else TCPInterface(hostname=tcp_host, portNumber=tcp_port)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MeshQuest read-only token-authenticated radio gateway")
    parser.add_argument("--server", default=os.getenv("MESHQUEST_SERVER", ""), help="HTTPS central server address")
    parser.add_argument("--token-file", default=os.getenv("MESHQUEST_TOKEN_FILE", ""), help="Private gateway token file (mode 0600)")
    parser.add_argument("--queue", default=os.getenv("MESHQUEST_QUEUE", "~/.local/state/meshquest-gateway/queue.db"))
    parser.add_argument("--serial", help="Meshtastic USB serial device")
    parser.add_argument("--tcp", help="Meshtastic TCP host")
    parser.add_argument("--tcp-port", type=int, default=4403)
    parser.add_argument("--channel-index", type=int, help="Local Meshtastic index of the MeshQuest secondary channel (0..7)")
    parser.add_argument("--check", action="store_true", help="Authenticate with Pisa, no radio needed")
    parser.add_argument("--self-test", action="store_true", help="Test metadata filter only; no token or network")
    args = parser.parse_args(argv)
    if args.self_test:
        assert normalize_packet({"channel": 1, "id": 1, "fromId": "!12345678",
                                 "decoded": {"portnum": "TEXT_MESSAGE_APP", "text": "SECRET"}}, 1)["event_id"]
        print("Gateway self-test OK: channel filter and metadata-only capture")
        return 0
    if not args.server or not args.token_file:
        parser.error("--server and --token-file are required (or set environment variables)")
    if args.serial and args.tcp:
        parser.error("Choose --serial or --tcp")
    if not args.check and (not (args.serial or args.tcp) or args.channel_index is None or not 0 <= args.channel_index <= 7):
        parser.error("Radio mode requires --serial/--tcp and --channel-index 0..7")
    try:
        token = read_token(args.token_file)
        client = ServerClient(args.server, token, os.getenv("MESHQUEST_STAGING_PASSWORD", ""))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    transport = "test" if args.check else ("serial" if args.serial else "tcp")
    heartbeat = {"agent_version": AGENT_VERSION, "transport": transport}
    try:
        reply = client.post("/api/v1/gateway/heartbeat", heartbeat)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        print("Gateway authentication failed: " + type(exc).__name__, file=sys.stderr)
        return 1
    if not reply.get("accepted"):
        print("Central server rejected gateway registration", file=sys.stderr)
        return 1
    print("Pisa gateway authentication OK: " + reply["gateway_id"])
    if args.check:
        return 0

    queue = DiskQueue(args.queue)
    from pubsub import pub  # installed with Meshtastic on gateway only

    def on_receive(packet, interface=None):
        data = normalize_packet(packet, args.channel_index)
        if data is not None:
            queue.add(data)

    pub.subscribe(on_receive, "meshtastic.receive")
    radio = None
    try:
        radio = connect_radio(args.serial, args.tcp, args.tcp_port)
        last_heartbeat = time.monotonic()
        next_retry = time.monotonic()
        print("Gateway running in read-only mode; no radio transmissions or game logic", file=sys.stderr)
        while True:
            now = time.monotonic()
            if now - last_heartbeat >= 60:
                try:
                    client.post("/api/v1/gateway/heartbeat", heartbeat)
                except (HTTPError, URLError, OSError, ValueError):
                    pass
                last_heartbeat = now
            if now >= next_retry:
                first = queue.first()
                if first is not None:
                    seq, payload = first
                    try:
                        response = client.post("/api/v1/gateway/packets", payload)
                        if response.get("accepted"):
                            queue.delete(seq)
                        else:
                            next_retry = now + 30
                    except (HTTPError, URLError, OSError, ValueError):
                        next_retry = now + 30
            time.sleep(1)
    except KeyboardInterrupt:
        return 0
    finally:
        if radio is not None:
            radio.close()
        queue.close()


if __name__ == "__main__":
    sys.exit(main())
