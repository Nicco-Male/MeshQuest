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
        self.dms = []
        self.inboxes = {NAV.source_id: [], PISA.source_id: []}

    def dm(self, gateway, player, text):
        self.dms.append((gateway.source_id, player, text))
        return len(self.dms)

    def read_channel(self, gateway):
        return list(self.rows[gateway.source_id])

    def read_dms(self, gateway):
        return list(self.inboxes[gateway.source_id])

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
    assert api.sent == [(NAV.source_id, 5, "MQ RX Navacchio")]
    bot.flush(now=4)
    assert api.sent == [
        (NAV.source_id, 5, "MQ RX Navacchio"),
        (PISA.source_id, 5, "MQ RX Pisa"),
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
    assert json.loads(req.data) == {"text": "MQ RX Navacchio", "channel": 5}


def test_no_broadcast_without_receiver_rssi_or_snr():
    assert is_rf_discovery(msg(9, rxRssi=-84, rxSnr=None), NAV)
    assert is_rf_discovery(msg(10, rxRssi=None, rxSnr=0), NAV)
    assert not is_rf_discovery(msg(11, rxRssi=None, rxSnr=None), NAV)


def test_named_gateway_selection_initiates_only_selected_dm():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA], allowed_player="!e9a04b31")
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(201))
    api.rows[PISA.source_id].append(msg(201))
    bot.poll(now=1)
    bot.flush(now=6)
    api.rows[NAV.source_id].append(msg(202, text="!use navacchio"))
    api.rows[PISA.source_id].append(msg(202, text="!use navacchio"))
    bot.poll(now=7)
    bot.flush(now=8)
    assert api.dms == [
        (NAV.source_id, "!e9a04b31",
         "MeshQuest connesso a Navacchio. Comandi: !help, !games"),
    ]
    bot.poll(now=9)
    bot.flush(now=15)
    assert len(api.dms) == 1


def test_selection_only_if_named_radio_received_discovery():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA])
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    bot.poll(now=1)
    api.rows[PISA.source_id].append(msg(2, text="!use pisa"))
    bot.poll(now=2)
    bot.flush(now=7)
    assert api.dms == []


def test_selection_requires_fresh_discovery():
    api = API()
    bot = ChannelDiscovery(api, [NAV])
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    bot.poll(now=1)
    api.rows[NAV.source_id].append(msg(2, text="!use navacchio"))
    bot.poll(now=130)
    bot.flush(now=150)
    assert api.dms == []


def test_selection_uses_full_unique_name_and_no_node_id():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA])
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    bot.poll(now=1)
    api.rows[NAV.source_id].append(msg(2, text="!use !eb4a6925"))
    api.rows[NAV.source_id].append(msg(3, text="!use pisa"))
    api.rows[NAV.source_id].append(msg(4, text="!use NAVACCHIO"))
    bot.poll(now=2)
    bot.flush(now=3)
    assert len(api.dms) == 1 and api.dms[0][0] == NAV.source_id
    assert "!" not in make_reply(NAV)


def test_ambiguous_gateway_names_never_trigger_dm():
    other = Gateway(PISA.source_id, "NAVACCHIO", PISA.node_id, 5, 1)
    api = API()
    bot = ChannelDiscovery(api, [NAV, other])
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    api.rows[other.source_id].append(msg(1))
    bot.poll(now=1)
    api.rows[NAV.source_id].append(msg(2, text="!use navacchio"))
    api.rows[other.source_id].append(msg(2, text="!use navacchio"))
    bot.poll(now=2)
    bot.flush(now=8)
    assert api.dms == []


def test_selection_mqtt_echo_and_cooldown():
    api = API()
    bot = ChannelDiscovery(api, [NAV], cooldown=15)
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    bot.poll(now=1)
    api.rows[NAV.source_id].append(msg(2, text="!use navacchio", viaMqtt=True))
    api.rows[NAV.source_id].append(msg(3, text="!use navacchio", rxSnr=None, rxRssi=None))
    bot.poll(now=2)
    bot.flush(now=3)
    assert not api.dms
    api.rows[NAV.source_id].append(msg(4, text="!use navacchio"))
    bot.poll(now=4)
    bot.flush(now=5)
    assert len(api.dms) == 1
    api.rows[NAV.source_id].append(msg(5, text="!use navacchio"))
    bot.poll(now=7)
    bot.flush(now=8)
    assert len(api.dms) == 1
    api.rows[NAV.source_id].append(msg(6, text="!use navacchio"))
    bot.poll(now=21)
    bot.flush(now=22)
    assert len(api.dms) == 2


def test_dm_api_v1_uses_destination_without_channel():
    requests = []
    def fake_open(req, timeout):
        requests.append(req)
        return Response({"success": True, "data": {
            "messageCount": 1, "channel": -1, "toNodeId": "!e9a04b31",
            "requestId": 42
        }}, status=201)
    api = MeshMonitorAPI("http://192.168.10.39:3001", "api-secret",
                         allow_http_lan=True, opener=fake_open)
    assert api.dm(NAV, "!e9a04b31", "MeshQuest connesso a Navacchio") == 42
    assert json.loads(requests[0].data) == {
        "text": "MeshQuest connesso a Navacchio", "toNodeId": "!e9a04b31"
    }
    assert "/sources/" + NAV.source_id + "/messages" in requests[0].full_url


def test_dm_and_broadcast_dry_run_both_blocked():
    api = API()
    bot = ChannelDiscovery(api, [NAV], dry_run=True)
    bot.poll(now=0)
    api.rows[NAV.source_id].append(msg(1))
    bot.poll(now=1)
    bot.flush(now=4)
    api.rows[NAV.source_id].append(msg(2, text="!use navacchio"))
    bot.poll(now=5)
    bot.flush(now=7)
    assert api.sent == [] and api.dms == []


def incoming_dm(i, gateway=NAV, sender="!e9a04b31", text="!help", **kwargs):
    data = {
        "id": "dm_" + str(i), "fromNodeId": sender,
        "toNodeId": gateway.node_id, "channel": -1, "portnum": 1,
        "text": text, "viaMqtt": False,
    }
    data.update(kwargs)
    return data


def open_session(api, bot, gateway=NAV):
    bot.poll(now=0)  # Establish channel AND DM history baseline.
    api.rows[gateway.source_id].append(msg(300))
    bot.poll(now=1)
    bot.flush(now=3)
    api.rows[gateway.source_id].append(msg(301, text="!use " + gateway.name.lower()))
    bot.poll(now=4)
    bot.flush(now=5)  # DM accepted; session now active.


def test_dm_help_and_games_after_named_selection():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA])
    open_session(api, bot)
    assert len(api.dms) == 1 and "connesso" in api.dms[0][2]
    api.inboxes[NAV.source_id].extend([
        incoming_dm(1, text="!help"),
        incoming_dm(2, text="!games"),
    ])
    bot.poll(now=6)
    assert len(api.dms) == 2
    assert "!games" in api.dms[-1][2]
    bot.poll(now=9)
    assert len(api.dms) == 3
    assert "Salvo" in api.dms[-1][2]
    assert all(x[0] == NAV.source_id for x in api.dms)
    bot.poll(now=20)
    assert len(api.dms) == 3


def test_dm_ignored_for_unselected_gateway_or_wrong_destination():
    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA])
    open_session(api, bot)
    api.inboxes[PISA.source_id].append(incoming_dm(1, gateway=PISA))
    api.inboxes[NAV.source_id].extend([
        incoming_dm(2, text="!help", toNodeId=PISA.node_id),
        incoming_dm(3, text="!help", fromNodeId=NAV.node_id),
        incoming_dm(4, text="!help", viaMqtt=True),
        incoming_dm(5, text="!help", channel=5),
        incoming_dm(6, text="!help", portnum=5),
        incoming_dm(7, text="hi"),
    ])
    bot.poll(now=7)
    bot.poll(now=9)
    assert len(api.dms) == 1


def test_session_expires_and_dm_exit_rejects_followups():
    api = API()
    bot = ChannelDiscovery(api, [NAV])
    open_session(api, bot)
    api.inboxes[NAV.source_id].append(incoming_dm(1, text="!exit"))
    bot.poll(now=6)
    assert len(api.dms) == 2 and "chiusa" in api.dms[-1][2]
    api.inboxes[NAV.source_id].append(incoming_dm(2, text="!games"))
    bot.poll(now=9)
    assert len(api.dms) == 2


def test_no_dm_without_first_greeting_send_success():
    api = API()
    def unavailable(gateway, player, text):
        raise RuntimeError("API unavailable")
    api.dm = unavailable
    bot = ChannelDiscovery(api, [NAV])
    open_session(api, bot)
    api.inboxes[NAV.source_id].append(incoming_dm(1, text="!help"))
    bot.poll(now=8)
    assert not bot.sessions


def test_old_dms_never_replied_after_restart():
    api = API()
    api.inboxes[NAV.source_id].append(incoming_dm(1, text="!games"))
    bot = ChannelDiscovery(api, [NAV])
    open_session(api, bot)
    bot.poll(now=6)
    assert len(api.dms) == 1


def test_dm_gameplay_is_only_demo():
    api = API()
    bot = ChannelDiscovery(api, [NAV])
    open_session(api, bot)
    api.inboxes[NAV.source_id].append(incoming_dm(1, text="!play salvo"))
    bot.poll(now=7)
    assert "non ancora attivi" in api.dms[-1][2]
