"""Unit tests for source-scoped MeshMonitor DM calls; no network, no radio."""
import json
import pytest
from gateway_agent.meshmonitor_dm import MeshMonitorDM, validate_base_url


NAVACCHIO = "1b7e5af4-b3f0-4dba-83fc-9a9517abb262"


class FakeHTTPResponse:
    status = 201

    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=None):
        return json.dumps(self.data).encode()


def test_meshmonitor_v1_post_is_unicast_and_source_scoped():
    calls = []

    def fake_open(req, timeout):
        calls.append((req, timeout))
        return FakeHTTPResponse({
            "success": True,
            "data": {
                "toNodeId": "!e9a04b31",
                "requestId": 889140671,
                "deliveryState": "pending",
                "messageCount": 1,
            },
        })

    sender = MeshMonitorDM("http://192.168.10.39:3001", NAVACCHIO, "token-private",
                           allow_http_lan=True, opener=fake_open)
    assert sender.send("!e9a04b31", "MeshQuest: test DM") == 889140671
    assert len(calls) == 1
    req, timeout = calls[0]
    assert req.full_url == "http://192.168.10.39:3001/api/v1/sources/" + NAVACCHIO + "/messages"
    assert req.get_method() == "POST"
    assert req.get_header("Authorization") == "Bearer token-private"
    assert json.loads(req.data) == {"toNodeId": "!e9a04b31", "text": "MeshQuest: test DM"}
    assert timeout == 10


def test_invalid_and_broadcast_destinations_rejected():
    sender = MeshMonitorDM("https://mesh.example", NAVACCHIO, "token")
    with pytest.raises(ValueError):
        sender.send("!ffffffff", "bad")
    with pytest.raises(ValueError):
        sender.send("garbage", "bad")
    with pytest.raises(ValueError):
        sender.send("!e9a04b31", "x" * 151)


def test_http_lan_requires_explicit_consent():
    with pytest.raises(ValueError):
        validate_base_url("http://192.168.10.39:3001")
    assert validate_base_url("http://192.168.10.39:3001", allow_http_lan=True)
    with pytest.raises(ValueError):
        validate_base_url("http://example.com", allow_http_lan=True)
    with pytest.raises(ValueError):
        validate_base_url("https://evil:password@mesh.example")
    assert validate_base_url("https://mesh.example/") == "https://mesh.example"


def test_reject_unexpected_meshmonitor_response():
    def fake_open(req, timeout):
        return FakeHTTPResponse({"success": True, "data": {
            "toNodeId": "broadcast", "deliveryState": "pending", "messageCount": 1
        }})

    sender = MeshMonitorDM("https://mesh.example", NAVACCHIO, "token", opener=fake_open)
    with pytest.raises(ValueError):
        sender.send("!e9a04b31", "test")


def test_meshmonitor_tx_requires_token_and_source(capsys):
    from gateway_agent.mqtt_pilot import main
    args = ["--tx-node-id", "!eb4a6925", "--allowed-player-node-id", "!e9a04b31", "--tx-transport", "meshmonitor",
            "--enable-tx", "--meshmonitor-url", "http://192.168.10.39:3001",
            "--allow-http-lan"]
    with pytest.raises(SystemExit):
        main(args)
    assert "Invalid MeshMonitor source UUID" in capsys.readouterr().err
