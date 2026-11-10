"""Deterministic safety checks for MQTT-only discovery PoC; no network or RF TX."""
import json

from gateway_agent.mqtt_pilot import BROADCAST, Packet, PilotBot, parse_message, topic_info, topic_subscriptions

TOPIC = "msh/EU_868/2/json/MeshQuest/!aaaabbbb"


def payload(sender="!11112222", to=BROADCAST, text="!gateways", packet_id=8, **kwargs):
    message = {
        "id": packet_id,
        "from": int(sender[1:], 16),
        "to": int(to[1:], 16),
        "type": "text",
        "payload": {"text": text},
    }
    message.update(kwargs)
    return json.dumps(message).encode()


def test_filter_exact_channel_and_text():
    assert parse_message(TOPIC, payload()).text == "!gateways"
    assert parse_message(TOPIC.replace("/2/", "/1/"), payload()) is not None
    assert parse_message(TOPIC.replace("MeshQuest", "LongFast"), payload()) is None
    assert parse_message(TOPIC.replace("/json/", "/e/"), payload()) is None
    assert parse_message(TOPIC.replace("/MeshQuest/", "/mqtt/"), payload()) is None
    assert parse_message(TOPIC, payload(type="nodeinfo")) is None
    assert parse_message(TOPIC, payload(viaMqtt=True)) is None
    assert parse_message(TOPIC, b"{bad-json}") is None
    assert parse_message(TOPIC, payload(text="ping")) is None
    assert parse_message(TOPIC, payload(text="!a" * 100)) is None


def test_nested_geographic_meshquest_topics_from_pisa_scan():
    # Observed root: msh/EU_868/IT/Tuscany/Pisa/2/e|json/MeshQuest/<node>.
    root = "msh/EU_868"
    protobuf = "msh/EU_868/IT/Tuscany/Pisa/2/e/MeshQuest/!eb4a6925"
    decoded = protobuf.replace("/e/", "/json/")
    assert topic_info(protobuf, root) == ("e", "!eb4a6925")
    assert parse_message(protobuf, payload(), root) is None  # binary, not JSON
    pkt = parse_message(decoded, payload(), root)
    assert pkt is not None and pkt.text == "!gateways"
    assert pkt.publisher == "!eb4a6925"

    assert topic_info(decoded.replace("/MeshQuest/", "/MeshQuest2/"), root) is None
    assert topic_info(decoded.replace("/MeshQuest/", "/LongFast/"), root) is None
    assert topic_info("msh/EU_868/2/json/MeshQuest/!aaaabbbb", root) is not None
    assert topic_info("msh/EU_868/IT/Tuscany/Pisa/2/json/MeshQuest/bad", root) is None


def test_specific_subscriptions_cover_geo_depth_without_broad_root_wildcard():
    subscriptions = topic_subscriptions("msh/EU_868")
    assert "msh/EU_868/+/json/MeshQuest/+" in subscriptions
    assert "msh/EU_868/+/+/+/+/json/MeshQuest/+" in subscriptions
    assert "msh/EU_868/+/+/+/+/e/MeshQuest/+" in subscriptions
    assert "msh/EU_868/#" not in subscriptions
    assert len(subscriptions) == 18


def test_discovery_aggregates_only_one_responder():
    bot = PilotBot("!aaaabbbb", response_delay=2, cooldown=5)
    a = parse_message(TOPIC, payload())
    b = parse_message(TOPIC.replace("!aaaabbbb", "!ccccdddd"), payload())
    assert bot.ingest(a, now=0) == []
    assert bot.ingest(b, now=0.1) == []
    assert bot.flush(now=1) == []
    replies = bot.flush(now=3)
    assert len(replies) == 1
    assert replies[0].to == "!11112222"
    assert "!aaaabbbb" in replies[0].text
    assert "!ccccdddd" in replies[0].text
    assert bot.ingest(a, now=4) == []
    assert bot.flush(now=5) == []


def test_discovery_without_local_receiver_never_replies():
    bot = PilotBot("!aaaabbbb", response_delay=1)
    packet = parse_message(TOPIC.replace("!aaaabbbb", "!ccccdddd"), payload())
    bot.ingest(packet, now=0)
    assert bot.flush(now=2) == []


def test_dm_only_responds_to_local_gateway_and_respects_cooldown():
    bot = PilotBot("!aaaabbbb", response_delay=1, cooldown=5)
    wrong = Packet("!11112222", "!ccccdddd", "!aaaabbbb", 10, "!games")
    right = Packet("!11112222", "!aaaabbbb", "!aaaabbbb", 11, "!games")
    assert bot.ingest(wrong, now=0) == []
    reply = bot.ingest(right, now=0)
    assert len(reply) == 1 and "salvo" in reply[0].text.lower()
    assert bot.ingest(right, now=0.5) == []
    assert bot.ingest(Packet("!11112222", "!aaaabbbb", "!aaaabbbb", 12, "!help"), now=2) == []
    assert len(bot.ingest(Packet("!11112222", "!aaaabbbb", "!aaaabbbb", 13, "!help"), now=6)) == 1


def test_untrusted_or_invalid_sender_and_broadcast_commands_ignored():
    assert parse_message(TOPIC, payload(sender=BROADCAST)) is None
    assert parse_message(TOPIC, payload(packet_id=0)) is None
    bot = PilotBot("!aaaabbbb", response_delay=1)
    p = Packet("!11112222", BROADCAST, "!aaaabbbb", 23, "!hack")
    assert bot.ingest(p, now=0) == []
    assert bot.flush(now=2) == []


def test_mqtt_pilot_self_test(capsys):
    from gateway_agent.mqtt_pilot import main
    assert main(["--self-test"]) == 0
    assert "self-test OK" in capsys.readouterr().out

def test_downlink_requires_exact_control_topic_and_no_node_suffix(capsys):
    import pytest
    from gateway_agent.mqtt_pilot import main
    args = ["--tx-node-id", "!eb4a6925", "--allowed-player-node-id", "!e9a04b31", "--tx-channel-index", "5", "--enable-tx"]
    with pytest.raises(SystemExit):
        main(args + ["--downlink-topic", "msh/EU_868/IT/Tuscany/Pisa/2/json/mqtt/!eb4a6925"])
    assert "requires --downlink-topic" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        main(args + ["--downlink-topic", "msh/EU_868/IT/Tuscany/Pisa/2/json/MeshQuest/"])
    assert "requires --downlink-topic" in capsys.readouterr().err
