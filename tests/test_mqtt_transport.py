"""Transport-only tests: no broker, radio, XP or game-state modification."""
import json

from meshquest.transports import EventBus
from meshquest.transports.mqtt import MAX_JSON_BYTES, MQTTAdapter, parse_mqtt_event


TOPIC = "msh/EU_868/1/json/NodeInfo/!00112233"


def wire(*, packet_id=42, sender="!00112233", gateway="!44556677", payload=None):
    return json.dumps({
        "channel": 1,
        "decoded": {"portnum": 4, "payload": payload or {
            "id": sender, "longName": "Private Name", "shortName": "Priv",
            "hwModel": "test",
        }},
        "from": sender,
        "gatewayId": gateway,
        "id": packet_id,
        "sender": sender,
        "timestamp": 1750000000,
        "to": "!ffffffff",
    }).encode()


def test_actual_nodeinfo_envelope_and_payload_path():
    event = parse_mqtt_event(TOPIC, wire())
    assert event is not None
    assert event.payload["hwModel"] == "test"
    assert event.payload["longName"] == "Private Name"
    assert event.portnum == 4
    assert event.transport == "mqtt"
    assert event.rf_verified is False
    assert event.gateway_id == "!44556677"
    assert event.received_at.tzinfo is not None


def test_no_payload_values_written_to_log(capsys):
    bus = EventBus()
    seen = []
    bus.subscribe(seen.append)
    adapter = MQTTAdapter(bus)
    assert adapter.ingest(TOPIC, wire()) is not None
    assert seen[0].payload["longName"] == "Private Name"
    assert capsys.readouterr().out == ""


def test_bounded_dedup_and_gateway_provenance():
    bus = EventBus()
    seen = []
    bus.subscribe(seen.append)
    adapter = MQTTAdapter(bus, max_recent=2)
    assert adapter.ingest(TOPIC, wire()) is not None
    assert adapter.ingest(TOPIC, wire()) is None
    assert adapter.duplicates == 1
    assert adapter.ingest(TOPIC, wire(gateway="!deadbeef")) is not None
    assert adapter.ingest(TOPIC, wire(packet_id=43)) is not None
    assert adapter.ingest(TOPIC, wire()) is not None  # initial key evicted
    assert adapter.received == 4
    assert len(seen) == 4
    assert len(adapter._seen) == 2


def test_retained_is_not_live_radio_proof():
    event = parse_mqtt_event(TOPIC, wire(), retained=True)
    assert event is not None
    assert event.retained is True
    assert event.rf_verified is False


def test_reject_malformed_non_json_or_unknown_envelopes():
    assert parse_mqtt_event(TOPIC, b"not-json") is None
    assert parse_mqtt_event(TOPIC, b"[]") is None
    assert parse_mqtt_event(TOPIC, b'{"decoded":[] }') is None
    assert parse_mqtt_event("other/topic", wire()) is None
    assert parse_mqtt_event(TOPIC, b" " * (MAX_JSON_BYTES + 1)) is None
    bus = EventBus()
    adapter = MQTTAdapter(bus)
    assert adapter.ingest(TOPIC, b'{}') is None
    assert adapter.ignored == 1


def test_events_no_id_are_not_falsely_deduplicated():
    bus = EventBus()
    seen = []
    bus.subscribe(seen.append)
    adapter = MQTTAdapter(bus)
    content = json.dumps({"decoded": {"portnum": 4, "payload": {}}, "gatewayId": "!00000000"}).encode()
    adapter.ingest(TOPIC, content)
    adapter.ingest(TOPIC, content)
    assert adapter.received == 2
    assert len(seen) == 2


def test_event_bus_separates_transport_from_game_plugins():
    bus = EventBus()
    values = []
    bus.subscribe(lambda event: values.append((event.transport, event.portnum, event.rf_verified)))
    adapter = MQTTAdapter(bus)
    adapter.ingest(TOPIC, wire())
    assert values == [("mqtt", 4, False)]
