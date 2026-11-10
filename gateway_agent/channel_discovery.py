#!/usr/bin/env python3
"""MeshQuest channel discovery via MeshMonitor's per-radio Meshtastic sources.

The daemon checks each connected TCP radio's received channel messages (not
MQTT JSON echoes). Every radio with the exact MeshQuest channel independently
answers a NEW !gateways broadcast on that same channel. After the player
broadcasts !use <gateway-name>, only the named gateway that recently heard
their discovery command initiates a private DM.

Transmission is enabled when this command is run; --dry-run disables it.
No Meshtastic TCP client is opened, so MeshMonitor keeps ownership of port 4403.
"""
import argparse
import heapq
import json
import os
import sys
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from gateway_agent.meshmonitor_dm import validate_base_url
from gateway_agent.mqtt_pilot import BROADCAST, node_id

COMMAND = "!gateways"
CHANNEL_NAME = "MeshQuest"
MAX_GATEWAYS = 8
POLL_SECONDS = 2
COOLDOWN_SECONDS = 15
DISCOVERY_TTL_SECONDS = 120
SESSION_TTL_SECONDS = 30 * 60
DM_RESPONSE_INTERVAL_SECONDS = 2.0
MAX_COMMAND_QUEUE = 32


@dataclass(frozen=True)
class Gateway:
    source_id: str
    name: str
    node_id: str
    channel: int
    position: int


class MeshMonitorAPI:
    def __init__(self, url, token, allow_http_lan=False, opener=urlopen):
        self.url = validate_base_url(url, allow_http_lan)
        if not token:
            raise ValueError("MM_TOKEN missing; export the token before starting")
        self.token = token
        self.opener = opener

    def request(self, path, body=None):
        url = self.url + path
        data = json.dumps(body, separators=(",", ":")).encode() if body is not None else None
        req = Request(url, data=data, method="POST" if body is not None else "GET", headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        with self.opener(req, timeout=12) as response:
            expected = 201 if body is not None else 200
            if response.status != expected:
                raise RuntimeError("MeshMonitor HTTP status " + str(response.status))
            result = json.loads(response.read(131072))
        if not isinstance(result, dict) or result.get("success") is not True:
            raise ValueError("MeshMonitor returned unsuccessful or malformed response")
        return result

    def discover(self, only_ids=None):
        data = self.request("/api/v1/sources").get("data", [])
        gateways = []
        for row in data:
            if not isinstance(row, dict) or row.get("type") != "meshtastic_tcp":
                continue
            sid = row.get("id")
            if not isinstance(sid, str) or (only_ids is not None and sid not in only_ids):
                continue
            if len(gateways) >= MAX_GATEWAYS:
                break
            try:
                # Status + channel list are scoped to the physical source.
                state = self.request("/api/v1/sources/" + sid + "/status").get("data", {})
                if state.get("connected") is not True:
                    print("SKIP disconnected: " + str(row.get("name", sid)), flush=True)
                    continue
                local_id = node_id(state.get("localNodeId"))
                if local_id is None or local_id == BROADCAST:
                    continue
                channels = self.request("/api/v1/sources/" + sid + "/channels").get("data", [])
                exact = [c for c in channels if isinstance(c, dict)
                         and c.get("name") == CHANNEL_NAME
                         and c.get("role") == 2 and isinstance(c.get("id"), int)
                         and 0 <= c["id"] <= 7]
                if len(exact) != 1:
                    print("SKIP no unique MeshQuest channel: " + str(row.get("name", sid)),
                          flush=True)
                    continue
                name = str(row.get("name") or state.get("shortName") or local_id)
                name = "".join(ch for ch in name if ch.isprintable() and ch not in "\r\n")[:20]
                gateways.append(Gateway(sid, name, local_id, exact[0]["id"], len(gateways)))
            except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                print("SKIP source %s (%s)" % (sid, type(exc).__name__), file=sys.stderr,
                      flush=True)
        return gateways

    def read_channel(self, gateway):
        q = urlencode({"channel": gateway.channel, "limit": 100})
        return self.request("/api/v1/sources/" + gateway.source_id + "/messages?" + q).get("data", [])

    def read_dms(self, gateway):
        # Meshtastic direct messages are stored by MeshMonitor as channel -1.
        # This is a read-only per-source v1 query; no TCP/LoRa side connection.
        q = urlencode({"channel": -1, "limit": 100})
        return self.request("/api/v1/sources/" + gateway.source_id + "/messages?" + q).get("data", [])

    def broadcast(self, gateway, text):
        if not isinstance(text, str) or not text or len(text.encode("utf-8")) > 120:
            raise ValueError("Channel reply exceeds 120 UTF-8 bytes")
        data = self.request("/api/v1/sources/" + gateway.source_id + "/messages", {
            "text": text,
            "channel": gateway.channel,
        }).get("data", {})
        if (not isinstance(data, dict) or data.get("messageCount") != 1
                or data.get("channel") != gateway.channel
                or data.get("toNodeId") != "broadcast"):
            raise ValueError("Unexpected channel broadcast response")
        return data.get("requestId")

    def dm(self, gateway, player, text):
        # A DM is selected by toNodeId alone, with NO 'channel' field.
        if node_id(player) in (None, BROADCAST):
            raise ValueError("Invalid DM destination")
        if not isinstance(text, str) or not text or len(text.encode("utf-8")) > 120:
            raise ValueError("DM greeting exceeds 120 UTF-8 bytes")
        data = self.request("/api/v1/sources/" + gateway.source_id + "/messages", {
            "text": text,
            "toNodeId": player,
        }).get("data", {})
        if (not isinstance(data, dict) or data.get("messageCount") != 1
                or data.get("channel") != -1 or data.get("toNodeId") != player):
            raise ValueError("Unexpected DM response")
        return data.get("requestId")


def message_key(message):
    if not isinstance(message, dict):
        return None
    mid = message.get("id")
    if isinstance(mid, (str, int)) and not isinstance(mid, bool) and str(mid):
        return str(mid)
    # No stable ID means that we cannot safely de-duplicate or reply.
    return None


def is_rf_channel_command(message, gateway):
    """Require fresh radio metadata from this physical source, not MQTT."""
    if not isinstance(message, dict):
        return False
    if message.get("channel") != gateway.channel or message.get("viaMqtt") is True:
        return False
    if message.get("rxRssi") is None and message.get("rxSnr") is None:
        return False
    sender = node_id(message.get("fromNodeId"))
    if sender is None or sender in (BROADCAST, gateway.node_id):
        return False
    recipient = node_id(message.get("toNodeId"))
    if recipient is not None and recipient != BROADCAST:
        return False
    return True


def command_text(message):
    text = message.get("text")
    return text.strip().casefold() if isinstance(text, str) else ""


def is_rf_discovery(message, gateway):
    return is_rf_channel_command(message, gateway) and command_text(message) == COMMAND


def selected_gateway_name(message, gateway):
    """Only a named selection, never a NodeID or numeric shortcut."""
    if not is_rf_channel_command(message, gateway):
        return None
    command = command_text(message)
    if not command.startswith("!use "):
        return None
    name = command[5:].strip()
    if not name or name.startswith("!") or len(name) > 60:
        return None
    return name


def make_reply(gateway):
    # Names only: never expose NodeIDs in channel protocol.
    return "MQ RX %s" % gateway.name


def make_dm_greeting(gateway):
    return "MeshQuest connesso a %s. Comandi: !help, !games" % gateway.name


def dm_command_reply(text, gateway):
    """Tiny, truthful pilot command menu; no game credits or state changes."""
    command = text.strip().casefold()
    if command in ("!help", "!menu"):
        return "MQ %s: !games lista giochi; !play salvo demo; !status; !exit" % gateway.name
    if command in ("!games", "!listgame"):
        return "MQ giochi: Salvo (demo), Exploration (demo). Usa !play salvo"
    if command in ("!play salvo", "!join salvo"):
        return "Salvo demo disponibile: gameplay radio e punti non ancora attivi."
    if command == "!status":
        return "MQ %s: collegato. Modalita demo, nessun punto assegnato." % gateway.name
    if command == "!exit":
        return "MQ: sessione chiusa. Rientra con !gateways sul canale."
    if command.startswith("!"):
        return "MQ: comando sconosciuto. Usa !help."
    return None


def is_incoming_dm(message, gateway):
    """Only a new direct text command addressed to this exact radio."""
    if not isinstance(message, dict) or message.get("channel") != -1:
        return False
    if message.get("viaMqtt") is True or message.get("portnum") not in (1, None):
        return False
    sender = node_id(message.get("fromNodeId"))
    if sender is None or sender in (BROADCAST, gateway.node_id):
        return False
    if node_id(message.get("toNodeId")) != gateway.node_id:
        return False
    text = message.get("text")
    return isinstance(text, str) and 0 < len(text) <= 80 and text.strip().startswith("!")


class ChannelDiscovery:
    def __init__(self, api, gateways, dry_run=False, allowed_player=None,
                 cooldown=COOLDOWN_SECONDS):
        self.api = api
        self.gateways = gateways
        self.dry_run = dry_run
        self.allowed_player = node_id(allowed_player) if allowed_player else None
        if allowed_player and (self.allowed_player is None or self.allowed_player == BROADCAST):
            raise ValueError("Invalid allowed-player NodeID")
        self.cooldown = cooldown
        self.baselined = set()
        self.seen = {g.source_id: set() for g in gateways}
        self.last = {}
        self.pending = []
        self.queued = set()
        self.seq = 0
        self.discovery = {}
        self.pending_dm = []
        self.queued_dm = set()
        self.last_dm = {}
        self.gateways_by_name = {}
        self.sessions = {}
        self.dm_baselined = set()
        self.dm_seen = {g.source_id: set() for g in gateways}
        self.pending_commands = []
        self.last_command_scheduled = {}
        for gateway in gateways:
            self.gateways_by_name.setdefault(gateway.name.strip().casefold(), []).append(gateway)

    def poll(self, now=None):
        now = time.monotonic() if now is None else now
        for gateway in self.gateways:
            try:
                messages = self.api.read_channel(gateway)
                if not isinstance(messages, list):
                    raise ValueError("Invalid messages list")
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
                print("Read failed from %s: %s" % (gateway.name, type(exc).__name__),
                      file=sys.stderr, flush=True)
                continue
            current = {k for m in messages if (k := message_key(m)) is not None}
            known = self.seen[gateway.source_id]
            if gateway.source_id not in self.baselined:
                known.update(current)
                self.baselined.add(gateway.source_id)
                print("Watching %s %s channel=%s (history ignored)"
                      % (gateway.name, gateway.node_id, gateway.channel), flush=True)
                continue
            for message in reversed(messages):
                key = message_key(message)
                if key is None or key in known:
                    continue
                known.add(key)
                if not is_rf_channel_command(message, gateway):
                    continue
                player = node_id(message.get("fromNodeId"))
                if self.allowed_player and player != self.allowed_player:
                    continue
                if not is_rf_discovery(message, gateway):
                    name = selected_gateway_name(message, gateway)
                    if name is not None:
                        # Only the named, unique gateway that heard the
                        # selection and recently heard this player can DM.
                        candidates = self.gateways_by_name.get(name, [])
                        key_dm = (gateway.source_id, player)
                        if (len(candidates) == 1 and candidates[0] == gateway
                                and key_dm in self.discovery
                                and 0 <= now - self.discovery[key_dm] <= DISCOVERY_TTL_SECONDS
                                and now - self.last_dm.get(key_dm, -1e12) >= self.cooldown
                                and key_dm not in self.queued_dm):
                            self.seq += 1
                            heapq.heappush(self.pending_dm, (now + 0.5, self.seq, gateway, player))
                            self.queued_dm.add(key_dm)
                            print("Selection %s <- %s; first DM queued" % (gateway.name, player),
                                  flush=True)
                    continue
                last_key = (gateway.source_id, player)
                self.discovery[last_key] = now
                if now - self.last.get(last_key, -1e12) < self.cooldown:
                    continue
                if last_key in self.queued:
                    continue
                # Stagger replies across radios to reduce collision risk.
                due = now + 0.8 + 1.6 * gateway.position
                self.seq += 1
                heapq.heappush(self.pending, (due, self.seq, gateway, player))
                self.queued.add(last_key)
                print("RF observation %s <- %s; reply queued" % (gateway.name, player),
                      flush=True)
            # Keep finite memory. This tracks only the latest 100 returned records
            # plus any queued IDs, rather than unbounded packet history.
            if len(known) > 1000:
                self.seen[gateway.source_id] = current | {k for k in known if k in current}
        self.discovery = {
            key: stamp for key, stamp in self.discovery.items()
            if now - stamp <= DISCOVERY_TTL_SECONDS
        }
        self.flush(now)
        self.poll_dms(now)

    def poll_dms(self, now):
        for gateway in self.gateways:
            try:
                messages = self.api.read_dms(gateway)
                if not isinstance(messages, list):
                    raise ValueError("Invalid DM messages list")
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
                print("DM read failed from %s: %s" % (gateway.name, type(exc).__name__),
                      file=sys.stderr, flush=True)
                continue
            seen = self.dm_seen[gateway.source_id]
            current = {k for m in messages if (k := message_key(m)) is not None}
            if gateway.source_id not in self.dm_baselined:
                seen.update(current)
                self.dm_baselined.add(gateway.source_id)
                print("Watching DM %s (history ignored)" % gateway.name, flush=True)
                continue
            for message in reversed(messages):
                key = message_key(message)
                if key is None or key in seen:
                    continue
                seen.add(key)
                if not is_incoming_dm(message, gateway):
                    continue
                player = node_id(message["fromNodeId"])
                session_key = (gateway.source_id, player)
                if self.allowed_player and self.allowed_player != player:
                    continue
                active_until = self.sessions.get(session_key, -1e12)
                if now >= active_until:
                    continue
                reply = dm_command_reply(message["text"], gateway)
                if reply is None:
                    continue
                if len(self.pending_commands) >= MAX_COMMAND_QUEUE:
                    print("DM command queue full; request ignored", file=sys.stderr, flush=True)
                    continue
                due = max(now, self.last_command_scheduled.get(session_key, -1e12)
                          + DM_RESPONSE_INTERVAL_SECONDS)
                self.last_command_scheduled[session_key] = due
                self.seq += 1
                is_exit = message["text"].strip().casefold() == "!exit"
                heapq.heappush(self.pending_commands,
                               (due, self.seq, gateway, player, reply, is_exit))
                if is_exit:
                    self.sessions.pop(session_key, None)
                else:
                    self.sessions[session_key] = now + SESSION_TTL_SECONDS
                print("DM command %s <- %s %s; queued" %
                      (gateway.name, player, message["text"].strip().casefold()), flush=True)
            if len(seen) > 1000:
                self.dm_seen[gateway.source_id] = current
        self.flush_commands(now)

    def flush_commands(self, now):
        while self.pending_commands and self.pending_commands[0][0] <= now:
            _, _, gateway, player, reply, is_exit = heapq.heappop(self.pending_commands)
            if not is_exit and self.sessions.get((gateway.source_id, player), -1e12) <= now:
                continue
            if self.dry_run:
                print("DRY-RUN DM reply %s -> %s: %s" %
                      (gateway.name, player, reply), flush=True)
                continue
            try:
                request_id = self.api.dm(gateway, player, reply)
                print("DM reply accepted %s -> %s id=%s (delivery unverified)" %
                      (gateway.name, player, request_id), flush=True)
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
                print("DM reply failed %s: %s" % (gateway.name, type(exc).__name__),
                      file=sys.stderr, flush=True)

    def flush(self, now=None):
        now = time.monotonic() if now is None else now
        while self.pending and self.pending[0][0] <= now:
            _, _, gateway, player = heapq.heappop(self.pending)
            self.queued.discard((gateway.source_id, player))
            self.last[(gateway.source_id, player)] = now
            reply = make_reply(gateway)
            if self.dry_run:
                print("DRY-RUN %s -> MeshQuest #%s: %s" %
                      (gateway.name, gateway.channel, reply), flush=True)
                continue
            try:
                req_id = self.api.broadcast(gateway, reply)
                print("TX accepted %s -> MeshQuest #%s id=%s: %s (delivery unverified)"
                      % (gateway.name, gateway.channel, req_id, reply), flush=True)
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
                print("TX failed %s: %s" % (gateway.name, type(exc).__name__),
                      file=sys.stderr, flush=True)
        while self.pending_dm and self.pending_dm[0][0] <= now:
            _, _, gateway, player = heapq.heappop(self.pending_dm)
            key = (gateway.source_id, player)
            self.queued_dm.discard(key)
            # If discovery expired while queued, don't attempt a DM.
            if now - self.discovery.get(key, -1e12) > DISCOVERY_TTL_SECONDS:
                continue
            self.last_dm[key] = now
            greeting = make_dm_greeting(gateway)
            if self.dry_run:
                print("DRY-RUN %s -> DM %s: %s" % (gateway.name, player, greeting),
                      flush=True)
                self.sessions[key] = now + SESSION_TTL_SECONDS
                continue
            try:
                request_id = self.api.dm(gateway, player, greeting)
                self.sessions[key] = now + SESSION_TTL_SECONDS
                print("DM accepted %s -> %s id=%s (delivery unverified)" %
                      (gateway.name, player, request_id), flush=True)
            except (HTTPError, URLError, TimeoutError, RuntimeError, ValueError) as exc:
                print("DM failed %s: %s" % (gateway.name, type(exc).__name__),
                      file=sys.stderr, flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MeshQuest: named gateway discovery and first DM")
    parser.add_argument("--meshmonitor-url", default="http://192.168.10.39:3001")
    parser.add_argument("--allow-http-lan", action="store_true",
                        help="Allow token over plaintext HTTP only to a private LAN IP")
    parser.add_argument("--dry-run", action="store_true", help="Observe only; no radio transmission")
    parser.add_argument("--allowed-player-node-id", default="",
                        help="Optional pilot filter; only reply to this NodeID")
    parser.add_argument("--only-sources", default="", help="Comma-separated source UUIDs; defaults to all connected sources with MeshQuest")
    parser.add_argument("--poll-seconds", type=float, default=POLL_SECONDS)
    args = parser.parse_args(argv)
    if not 0.5 <= args.poll_seconds <= 30:
        parser.error("--poll-seconds must be between 0.5 and 30")
    try:
        api = MeshMonitorAPI(args.meshmonitor_url, os.getenv("MM_TOKEN"),
                             allow_http_lan=args.allow_http_lan)
        ids = {v.strip() for v in args.only_sources.split(",") if v.strip()} or None
        gateways = api.discover(only_ids=ids)
        if not gateways:
            parser.error("No connected MeshMonitor TCP source with exact MeshQuest channel")
        bot = ChannelDiscovery(api, gateways, dry_run=args.dry_run,
                               allowed_player=args.allowed_player_node_id)
    except (HTTPError, URLError, ValueError, RuntimeError) as exc:
        parser.error("%s (%s)" % (type(exc).__name__, "check MeshMonitor URL/token/config"))
    print("MeshQuest discovery TX=%s gateways=%s" %
          ("OFF" if args.dry_run else "ON", len(gateways)), flush=True)
    for g in gateways:
        print("  %s %s channel=%d" % (g.name, g.node_id, g.channel), flush=True)

    try:
        while True:
            bot.poll()
            time.sleep(args.poll_seconds)
    except KeyboardInterrupt:
        print("Discovery stopped", flush=True)
        return 0


if __name__ == "__main__":
    sys.exit(main())
