"""Passive MQTT transport adapter for MeshQuest Core.

Read-only by construction: SUBSCRIBE only. No MQTT PUBLISH, API writes,
game scoring or LoRa radio commands. Payloads are delivered only in memory
to explicitly registered event handlers and are never logged by this observer.

Use a broker-side ACL for a genuinely read-only account in production.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from .events import EventBus, MeshEvent

MAX_JSON_BYTES = 65536
DEFAULT_TOPIC = "msh/EU_868/1/json/#"


def parse_mqtt_event(topic: str, body: bytes, *, retained: bool = False) -> MeshEvent | None:
    """Normalize the observed Meshtastic JSON envelope, not the RF route.

    The broker's live NodeInfo sample uses decoded.portnum and decoded.payload.
    Other opaque/encrypted/non-JSON packets are ignored in this first adapter.
    """
    if not isinstance(topic, str) or "/json/" not in topic:
        return None
    if not isinstance(body, bytes) or len(body) > MAX_JSON_BYTES:
        return None
    try:
        raw = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    decoded = raw.get("decoded")
    if not isinstance(decoded, dict):
        return None
    payload = decoded.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    port = decoded.get("portnum")
    if not isinstance(port, (int, str)) or isinstance(port, bool):
        port = None
    raw_id = raw.get("id")
    packet_id = str(raw_id) if isinstance(raw_id, (int, str)) and not isinstance(raw_id, bool) else None
    sender = raw.get("sender") if isinstance(raw.get("sender"), str) else None
    if sender is None:
        sender = raw.get("from") if isinstance(raw.get("from"), str) else None
    gateway = raw.get("gatewayId") if isinstance(raw.get("gatewayId"), str) else None
    channel = raw.get("channel")
    if not isinstance(channel, (int, str)) or isinstance(channel, bool):
        channel = None
    return MeshEvent(
        transport="mqtt", topic=topic, packet_id=packet_id, sender=sender,
        gateway_id=gateway, channel=channel, portnum=port,
        payload=payload, retained=bool(retained), received_at=datetime.now(timezone.utc),
        rf_verified=False,
    )


class MQTTAdapter:
    """Bounded in-memory duplicate filter and event forwarder."""

    def __init__(self, events: EventBus, *, max_recent: int = 4096) -> None:
        if max_recent < 1:
            raise ValueError("max_recent must be positive")
        self.events = events
        self.max_recent = max_recent
        self._seen: OrderedDict[tuple[str, str, str, str], None] = OrderedDict()
        self.received = 0
        self.duplicates = 0
        self.ignored = 0

    def ingest(self, topic: str, body: bytes, *, retained: bool = False) -> MeshEvent | None:
        event = parse_mqtt_event(topic, body, retained=retained)
        if event is None:
            self.ignored += 1
            return None
        # Packet IDs are scoped by publisher + gateway + MQTT topic.
        # No packet ID => no deduplication, avoiding accidental data loss.
        if event.packet_id:
            key = (event.topic, event.gateway_id or "", event.sender or "", event.packet_id)
            if key in self._seen:
                self.duplicates += 1
                self._seen.move_to_end(key)
                return None
            self._seen[key] = None
            if len(self._seen) > self.max_recent:
                self._seen.popitem(last=False)
        self.events.emit(event)
        self.received += 1
        return event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Passive MeshQuest MQTT observer (no gameplay or radio TX)")
    parser.add_argument("--max-events", type=int, default=0, help="Exit after N accepted events; 0 keeps listening")
    args = parser.parse_args(argv)
    if args.max_events < 0:
        parser.error("--max-events must be nonnegative")

    host = os.getenv("MESHQUEST_MQTT_HOST", "").strip()
    username = os.getenv("MESHQUEST_MQTT_USERNAME", "").strip()
    password = os.getenv("MESHQUEST_MQTT_PASSWORD", "")
    topic = os.getenv("MESHQUEST_MQTT_TOPIC", DEFAULT_TOPIC).strip()
    try:
        port = int(os.getenv("MESHQUEST_MQTT_PORT", "1883"))
    except ValueError:
        parser.error("MESHQUEST_MQTT_PORT must be an integer")
    if not host or not username or not password or not topic or not 1 <= port <= 65535:
        parser.error("Set valid MESHQUEST_MQTT_HOST, _USERNAME, _PASSWORD, _TOPIC and _PORT")

    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        parser.error("Install optional MQTT dependencies: pip install '.[mqtt]'")

    bus = EventBus()
    adapter = MQTTAdapter(bus)
    # The current observer logs event kind and transport only (not names, coordinates, text).
    def observe(event: MeshEvent) -> None:
        print(json.dumps({
            "type": "mqtt_event", "portnum": event.portnum,
            "retained": event.retained, "rf_verified": False,
        }), flush=True)
    bus.subscribe(observe)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="meshquest-observer-" + uuid.uuid4().hex[:12],
        protocol=mqtt.MQTTv311,
    )
    client.username_pw_set(username, password)
    # Intentionally no on_publish and never call client.publish().
    def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        if reason_code.is_failure:
            print("MQTT connection rejected by broker", file=sys.stderr, flush=True)
            return
        client.subscribe(topic, qos=0)
        print("MQTT subscribed: " + topic, flush=True)

    def on_message(client: Any, userdata: Any, message: Any) -> None:
        event = adapter.ingest(message.topic, message.payload, retained=message.retain)
        if event is not None and args.max_events and adapter.received >= args.max_events:
            client.disconnect()

    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(host, port, keepalive=60)
        client.loop_forever(retry_first_connection=True)
    except (OSError, ValueError) as exc:
        print("MQTT observer connection failed: " + type(exc).__name__, file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        client.disconnect()
    print(json.dumps({
        "type": "mqtt_summary", "received": adapter.received,
        "duplicates": adapter.duplicates, "ignored": adapter.ignored,
        "rf_verified": False,
    }), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
