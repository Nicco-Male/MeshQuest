#!/usr/bin/env python3
"""Experimental MeshQuest MQTT channel discovery -> single-gateway DM pilot.

Python 3.9+, suitable for small ARM devices but intended for the central pilot.
By default RX-only; use --enable-tx explicitly after configuring the Meshtastic
MQTT JSON downlink. No game state, account identity or XP is changed here.
"""
import argparse
import json
import os
import re
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from urllib.parse import urlsplit

CHANNEL = "MeshQuest"
NODE_RE = re.compile(r"^![0-9a-f]{8}$")
BROADCAST = "!ffffffff"
MAX_REPLY = 150


def node_id(value):
    """Convert numeric or hex Meshtastic addresses, including signed broadcast."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return "!%08x" % (value & 0xffffffff) if -(1 << 31) <= value <= 0xffffffff else None
    if isinstance(value, str):
        value = value.strip().lower()
        if NODE_RE.fullmatch(value):
            return value
        if value.isdecimal() and int(value) <= 0xffffffff:
            return "!%08x" % int(value)
    return None


@dataclass(frozen=True)
class Packet:
    sender: str
    recipient: str
    publisher: str
    packet_id: int
    text: str


def parse_message(topic, raw, root="msh/EU_868"):
    """Allow only decoded text packets in the named MeshQuest topic.

    JSON formats seen in Meshtastic firmware and external converters are
    supported. A numeric channel index is NOT used to identify a channel
    because indices are local to each radio.
    """
    parts = topic.split("/")
    prefix = root.strip("/").split("/")
    if (len(parts) != len(prefix) + 4 or parts[:len(prefix)] != prefix
            or parts[len(prefix)] not in ("1", "2")
            or parts[len(prefix) + 1] != "json"
            or parts[len(prefix) + 2] != CHANNEL):
        return None
    publisher = node_id(parts[-1])
    if publisher is None or len(raw) > 4096:
        return None
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError, TypeError):
        return None
    if not isinstance(data, dict) or data.get("viaMqtt", data.get("via_mqtt", False)) is True:
        return None
    decoded = data.get("decoded")
    text = None
    if data.get("type") in ("text", "sendtext"):
        payload = data.get("payload")
        text = payload if isinstance(payload, str) else payload.get("text") if isinstance(payload, dict) else None
    elif isinstance(decoded, dict) and decoded.get("portnum") in (1, "1", "TEXT_MESSAGE_APP"):
        payload = decoded.get("payload")
        text = payload.get("text") if isinstance(payload, dict) else payload if isinstance(payload, str) else decoded.get("text")
    if not isinstance(text, str) or not text.startswith("!") or len(text) > 80:
        return None
    sender = node_id(data.get("from", data.get("fromId")))
    recipient = node_id(data.get("to", data.get("toId")))
    packet_id = data.get("id")
    if (sender is None or sender == BROADCAST or recipient is None
            or not isinstance(packet_id, int) or isinstance(packet_id, bool)
            or not 0 < packet_id <= 0xffffffff):
        return None
    return Packet(sender, recipient, publisher, packet_id, text.strip().lower())


@dataclass(frozen=True)
class Reply:
    to: str
    text: str


class PilotBot:
    """Deduplicate packet IDs across RF observers; allow one DM-capable responder."""

    def __init__(self, tx_node, response_delay=2.0, cooldown=5.0):
        self.tx_node = node_id(tx_node)
        if not self.tx_node or self.tx_node == BROADCAST:
            raise ValueError("Specify a concrete --tx-node-id")
        self.response_delay = response_delay
        self.cooldown = cooldown
        self.pending = {}
        self.seen = {}
        self.last_reply = defaultdict(lambda: -1e12)
        self.observers = {}
        self.lock = threading.Lock()

    def ingest(self, packet, now=None):
        """Accept a packet. Never claim a gateway observed RF if viaMqtt=True."""
        now = time.monotonic() if now is None else now
        with self.lock:
            if packet.sender == self.tx_node:
                return []
            key = (packet.sender, packet.packet_id)
            if packet.recipient == BROADCAST:
                if packet.text not in ("!gateways", "!mq", "!help"):
                    return []
                if key not in self.pending and key not in self.seen:
                    self.pending[key] = {"at": now, "text": packet.text, "publishers": set()}
                if key in self.pending:
                    self.pending[key]["publishers"].add(packet.publisher)
                return []
            if packet.recipient != self.tx_node or key in self.seen:
                return []
            self.seen[key] = now
            if now - self.last_reply[packet.sender] < self.cooldown:
                return []
            response = self._dm_reply(packet.sender, packet.text)
            if response is None:
                return []
            self.last_reply[packet.sender] = now
            return [Reply(packet.sender, response)]

    def _dm_reply(self, sender, text):
        if text in ("!help", "!menu"):
            return "MQ: !games giochi; !gateways sul canale; !play salvo demo; !status stato."
        if text in ("!games", "!listgame"):
            return "MQ giochi: salvo (PoC), exploration (PoC). !play salvo"
        if text == "!play salvo":
            return "Salvo: menu demo attivo. Gioco radio e punti non ancora abilitati."
        if text == "!status":
            return "MQ: bot online; nessuna sessione di gioco via radio ancora attiva."
        if text.startswith("!use "):
            try:
                chosen = int(text.split()[1])
            except (IndexError, ValueError):
                return "MQ: usa !use 1 oppure !gateways sul canale."
            options = self.observers.get(sender, [])
            if 1 <= chosen <= len(options):
                if options[chosen - 1] == self.tx_node:
                    return "MQ: DM con gateway attivo. Usa !help o !games."
                return "MQ: gateway osservato, DM non abilitato nel pilot."
            return "MQ: scelta scaduta. Invia !gateways sul canale."
        if text in ("!scan", "!hack"):
            return "Salvo: funzione non disponibile via radio in questo pilot."
        return "MQ: comando sconosciuto. Invia !help."

    def flush(self, now=None):
        now = time.monotonic() if now is None else now
        replies = []
        with self.lock:
            for key, entry in list(self.pending.items()):
                if now - entry["at"] < self.response_delay:
                    continue
                sender, _ = key
                del self.pending[key]
                self.seen[key] = now
                publishers = sorted(entry["publishers"])
                # Only answer if the configured RF TX gateway actually uplinked
                # this packet itself; another observer's report is insufficient.
                if self.tx_node not in publishers or now - self.last_reply[sender] < self.cooldown:
                    continue
                self.observers[sender] = publishers
                if entry["text"] == "!help":
                    text = self._dm_reply(sender, "!help")
                else:
                    shown = publishers[:3]
                    roster = "; ".join("%d:%s%s" % (i + 1, name, "*" if name == self.tx_node else "")
                                       for i, name in enumerate(shown))
                    text = "MQ gateway osservati: " + roster + " (*DM attivo). DM al *: !use N"
                self.last_reply[sender] = now
                replies.append(Reply(sender, text[:MAX_REPLY]))
            for key, stamp in list(self.seen.items()):
                if now - stamp > 120:
                    del self.seen[key]
            # Expire candidate lists; gateway sightings are not permanent availability.
            for sender in list(self.observers):
                if not any(key[0] == sender for key in self.seen):
                    del self.observers[sender]
        return replies


def main(argv=None):
    p = argparse.ArgumentParser(description="MeshQuest MQTT receive/DM pilot (RX-only by default)")
    p.add_argument("--broker", default=os.getenv("MESHQUEST_MQTT_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.getenv("MESHQUEST_MQTT_PORT", "1883")))
    p.add_argument("--root", default=os.getenv("MESHQUEST_MQTT_ROOT", "msh/EU_868"))
    p.add_argument("--tx-node-id", default=os.getenv("MESHQUEST_MQTT_TX_NODE_ID", ""))
    p.add_argument("--tx-channel-index", type=int, default=None)
    p.add_argument("--enable-tx", action="store_true", help="Send real DMs via Meshtastic JSON MQTT downlink")
    p.add_argument("--tls", action="store_true", help="Enable MQTT TLS")
    p.add_argument("--self-test", action="store_true")
    args = p.parse_args(argv)

    if args.self_test:
        raw = json.dumps({"id": 12, "from": 0x11223344, "to": -1, "type": "text", "payload": "!gateways"})
        assert parse_message("msh/EU_868/2/json/MeshQuest/!abcdef12", raw.encode()) is not None
        print("MeshQuest MQTT pilot parser self-test OK")
        return 0

    if not node_id(args.tx_node_id) or node_id(args.tx_node_id) == BROADCAST:
        p.error("--tx-node-id is required (actual transmitting Meshtastic node ID)")
    if args.enable_tx and (args.tx_channel_index is None or not 0 <= args.tx_channel_index <= 7):
        p.error("--enable-tx requires --tx-channel-index matching MeshQuest on the TX radio")
    if "/" in args.broker or ":" in args.broker:
        p.error("--broker must be a hostname or IP (port is a separate option)")

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        p.error("Install paho-mqtt: python3 -m pip install 'paho-mqtt>=2,<3'")

    bot = PilotBot(args.tx_node_id)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="meshquest-mqtt-pilot")
    user = os.getenv("MESHQUEST_MQTT_USER")
    password = os.getenv("MESHQUEST_MQTT_PASSWORD")
    if user:
        client.username_pw_set(user, password)
    if args.tls:
        client.tls_set()
    root = args.root.strip("/")
    subscribe_topic = root + "/+/json/MeshQuest/+"
    downlink = root + "/2/json/mqtt/"

    def respond(reply):
        if not args.enable_tx:
            print("[RX-ONLY] would send DM to %s: %s" % (reply.to, reply.text), flush=True)
            return
        # Explicit destination is mandatory: never accidentally broadcast a reply.
        payload = {"from": int(bot.tx_node[1:], 16), "to": int(reply.to[1:], 16),
                   "channel": args.tx_channel_index, "type": "sendtext", "payload": reply.text}
        status = client.publish(downlink, json.dumps(payload, separators=(",", ":")), qos=0, retain=False)
        print("DM requested for %s; MQTT result=%s (NOT RF delivery proof)"
              % (reply.to, status.rc), flush=True)

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(subscribe_topic, qos=0)
            print("Listening only to %s; TX=%s" % (subscribe_topic, args.enable_tx), flush=True)
        else:
            print("MQTT connection rejected: %s" % reason_code, file=sys.stderr)

    def on_message(client, userdata, msg):
        packet = parse_message(msg.topic, msg.payload, root)
        if packet is None:
            return
        replies = bot.ingest(packet)
        for reply in replies:
            respond(reply)

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.broker, args.port, 30)
    client.loop_start()
    try:
        while True:
            for reply in bot.flush():
                respond(reply)
            time.sleep(0.25)
    except KeyboardInterrupt:
        return 0
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    sys.exit(main())
