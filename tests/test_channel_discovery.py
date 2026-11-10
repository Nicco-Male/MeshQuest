"""Channel discovery tests: separate radio sources, RF-only guard, bounded TX."""
import json
from urllib.parse import urlsplit
from gateway_agent.channel_discovery import (
    ChannelDiscovery, Gateway, MeshMonitorAPI, is_rf_discovery, make_reply,
)

NAV = Gateway("1b7e5af4-b3f0-4dba-83fc-9a9517abb262", "Navacchio", "!eb4a6925", 5, 0)
PISA = Gateway("627bca65-825a-469b-935a-64579e66dc66", "Pisa", "!847eb6bb", 5, 1)


def msg(i, sender="!e9a04b31", **kwargs):
    data = {
        "id": "3947_" + str(i), "fromNodeId": sender, "toNodeId": "!ffffffff",
        "text": "!gateways", "channel": 5, "rxRssi": -96, "rxSnr": 4.3,
        "viaMqtt": False
    }
    data.update(kwargs)
    return data


class API:
    def __init__(self):
        self.rows = {NAV.source_id: [], PISA.source_id: []}
        self.sent = []

    def read_channel(self, gateway):
        return list(self.rows[gateway.source_id])

    def broadcast(self, gateway, text):
        self.sent.append((gateway.source_id, gateway.channel, text))
        return len(self.sent)


def test_each_receiver_replies_once_on_channel_not_dm():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA], allowed_player="!e9a04b31")
    bot.poll(now=0)  # history is ignored on initial scan
    both = msg(123)
    api.rows[NAV.source_id].append(both)
    api.rows[PISA.source_id].append(both)
    bot.poll(now=1)
    assert api.sent == []
    bot.flush(now=1.9)
    assert api.sent == [(NAV.source_id, 5, "MQ RX Navacchio !eb4a6925")]
    bot.flush(now=4)
    assert api.sent == [
        (NAV.source_id, 5, "MQ RX Navacchio !eb4a6925"),
        (PISA.source_id, 5, "MQ RX Pisa !847eb6bb"),
    ]
    bot.poll(now=6)
    bot.flush(now=100)
    assert len(api.sent) == 2


def test_only_actual_observer_replies():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA])
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    bot.poll(now=1)
    bot.flush(now=5)
    assert [item[0] for item in api.sent] == [NAV.source_id]


def test_mqtt_echo_and_missing_rf_metadata_do_not_trigger():
    api = API()
    bot = ChannelDiscovery(api, [NAV])
    bot.poll(now=0)
    api.rows[NAV.source_id].extend([
        msg(1, viaMqtt=True),
        msg(2, rxSnr=None, rxRssi=None),
        msg(3, channel=0),
        msg(4, text="MQ RX Pisa !847eb6bb"),
        msg(5, fromNodeId=NAV.node_id),
        msg(6, toNodeId="!00000001"),
    ])
    bot.poll(now=1)
    bot.flush(now=30)
    assert not api.sent


def test_old_history_ignored_and_cooldown_rate_limit():
    api = API()
    api.rows[NAV.source_id].append(msg(1))
    bot = ChannelDiscovery(api, [NAV], cooldown=15)
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(2))
    bot.poll(now=1)
    api.rows[NAV.source_id].append(msg(3))
    bot.poll(now=2)
    bot.flush(now=5)
    assert len(api.sent) == 1
    api.rows[NAV.source_id].append(msg(4))
    bot.poll(now=22)
    bot.flush(now=24)
    assert len(api.sent) == 2


def test_dry_run_never_transmits_and_allowlist():
    api = API()
    bot = ChannelDiscovery(api, [NAV], dry_run=True, allowed_player="!e9a04b31")
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1, sender="!12121212"))
    bot.poll(now=2)
    bot.flush(now=50)
    assert not api.sent
    api.rows[NAV.source_id].append(msg(2))
    bot.poll(now=51)
    bot.flush(now=60)
    assert not api.sent


class Response:
    status = 200

    def __init__(self, obj, status=200):
        self.obj = obj
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, maximum):
        return json.dumps(self.obj).encode()


def test_discovery_autofinds_meshquest_in_connected_sources():
    def fake_open(req, timeout):
        path = urlsplit(req.full_url).path
        if path == "/api/v1/sources":
            return Response({"success": True, "data": [
                {"id": NAV.source_id, "name": "Navacchio", "type": "meshtastic_tcp"},
                {"id": PISA.source_id, "name": "Pisa", "type": "meshtastic_tcp"},
                {"id": "6c97b21a-48b8-459c-9cb4-f842fff64a93", "name": "MQTT", "type": "mqtt_bridge"},
            ]})
        if path.endswith("/status"):
            return Response({"success": True, "data": {
                "connected": True, "localNodeId": NAV.node_id if NAV.source_id in path else PISA.node_id,
            }})
        if path.endswith("/channels"):
            return Response({"success": True, "data": [
                {"id": 0, "name": "", "role": 1},
                {"id": 5, "name": "MeshQuest", "role": 2},
            ]})
        raise AssertionError(path)

    api = MeshMonitorAPI("http://192.168.10.39:3001", "api-secret",
                         allow_http_lan=True, opener=fake_open)
    assert api.discover() == [NAV, PISA]


def test_radio_tx_uses_v1_channel_and_no_destination():
    calls = []

    def fake_open(req, timeout):
        calls.append(req)
        return Response({"success": True, "data": {
            "messageCount": 1, "channel": 5, "toNodeId": "broadcast", "requestId": 123,
        }}, status=201)

    api = MeshMonitorAPI("http://192.168.10.39:3001", "api-secret",
                         allow_http_lan=True, opener=fake_open)
    assert api.broadcast(NAV, make_reply(NAV)) == 123
    req = calls[0]
    assert req.get_method() == "POST"
    assert req.full_url.endswith("/api/v1/sources/" + NAV.source_id + "/messages")
    assert req.get_header("Authorization") == "Bearer api-secret"
    assert json.loads(req.data) == {"text": "MQ RX Navacchio !eb4a6925", "channel": 5}


def test_no_broadcast_without_receiver_rssi_or_snr():
    assert is_rf_discovery(msg(9, rxRssi=-84, rxSnr=None), NAV)
    assert is_rf_discovery(msg(10, rxRssi=None, rxSnr=0), NAV)
    assert not is_rf_discovery(msg(11, rxRssi=None, rxSnr=None), NAV)
