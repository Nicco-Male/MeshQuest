from fastapi.testclient import TestClient

from meshquest.app import create_app

ADMIN = {"x-admin-key": "test-admin-key"}


def make_client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'meshquest-test.db'}", "test-admin-key")
    return TestClient(app)


def seed(client):
    assert client.post("/api/v1/admin/players", json={"node_id": "!AABBCCDD", "nickname": "Scout"}, headers=ADMIN).status_code == 201
    assert client.post("/api/v1/admin/outposts", json={"node_id": "!11223344", "name": "Poggi"}, headers=ADMIN).status_code == 201
    assert client.post("/api/v1/admin/outposts/!11223344/approve", headers=ADMIN).status_code == 200
    resp = client.post("/api/v1/admin/gateways", json={"gateway_id": "pisa-gw", "radio_node_id": "!99887766"}, headers=ADMIN)
    assert resp.status_code == 201
    return {"authorization": "Bearer " + resp.json()["token"]}


def route(event_id="traceroute-0001", route=None, unknown=0):
    return {"event_id": event_id, "player_node_id": "!aabbccdd", "route_to_player": [],
            "route_to_gateway": route if route is not None else ["!11223344"],
            "unknown_to_player": 0, "unknown_to_gateway": unknown, "source": "rf_traceroute"}


def test_complete_gameplay_and_duplicate(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        first = client.post("/api/v1/observations", json=route(), headers=auth)
        assert first.status_code == 200, first.text
        assert first.json()["xp_awarded"] == 50
        assert first.json()["credited_outposts"] == ["!11223344"]
        replay = client.post("/api/v1/observations", json=route(), headers=auth)
        assert replay.status_code == 200 and replay.json()["duplicate"] is True
        second = client.post("/api/v1/observations", json=route("traceroute-0002"), headers=auth)
        assert second.status_code == 200 and second.json()["xp_awarded"] == 0
        board = client.get("/api/v1/leaderboard").json()["players"]
        assert board[0]["xp"] == 50 and board[0]["outposts"] == 1
        assert client.get("/api/v1/outposts").json()[0]["approved"] is True


def test_unknown_relays_and_unapproved_outposts_do_not_score(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        client.post("/api/v1/admin/outposts", json={"node_id": "!55667788", "name": "Pending"}, headers=ADMIN)
        response = client.post("/api/v1/observations", json=route(route=["!55667788"], unknown=2), headers=auth)
        assert response.status_code == 200 and response.json()["xp_awarded"] == 0


def test_auth_and_payload_safety(tmp_path):
    with make_client(tmp_path) as client:
        assert client.post("/api/v1/admin/players", json={"node_id": "!aabbccdd", "nickname": "Scout"}).status_code == 401
        auth = seed(client)
        assert client.post("/api/v1/observations", json=route()).status_code == 401
        bad = client.post("/api/v1/observations", json=route(route=["!99887766"]), headers=auth)
        assert bad.status_code == 422
        bad = client.post("/api/v1/observations", json={**route(), "source": "mqtt"}, headers=auth)
        assert bad.status_code == 422
        bad = client.post("/api/v1/observations", json={**route(), "route_to_gateway": ["!not-valid"]}, headers=auth)
        assert bad.status_code == 422


def test_registration_conflicts(tmp_path):
    with make_client(tmp_path) as client:
        seed(client)
        resp = client.post("/api/v1/admin/players", json={"node_id": "!aabbccdd", "nickname": "Other"}, headers=ADMIN)
        assert resp.status_code == 409



def test_multiple_outposts_and_route_direction(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        client.post("/api/v1/admin/outposts", json={"node_id": "!55667788", "name": "Second relay"}, headers=ADMIN)
        client.post("/api/v1/admin/outposts/!55667788/approve", headers=ADMIN)
        response = client.post("/api/v1/observations", json=route(
            route=["!11223344", "!55667788", "!11223344"], unknown=2), headers=auth)
        assert response.status_code == 200
        assert response.json()["xp_awarded"] == 100
        assert set(response.json()["credited_outposts"]) == {"!11223344", "!55667788"}
        assert client.get("/api/v1/leaderboard").json()["players"][0]["outposts"] == 2
        assert client.get("/api/v1/leaderboard?scope=month").json()["players"][0]["xp"] == 100


def test_outgoing_route_not_credited_and_pending_hidden(tmp_path):
    with make_client(tmp_path) as client:
        auth = seed(client)
        client.post("/api/v1/admin/outposts", json={"node_id": "!55667788", "name": "Pending"}, headers=ADMIN)
        assert len(client.get("/api/v1/outposts").json()) == 1
        data = route(route=[])
        data["route_to_player"] = ["!11223344"]
        result = client.post("/api/v1/observations", json=data, headers=auth)
        assert result.status_code == 200 and result.json()["xp_awarded"] == 0


def test_staging_requires_credentials_and_preserves_bearer_auth(tmp_path, monkeypatch):
    import base64
    monkeypatch.delenv("MESHQUEST_REQUIRE_STAGING_PASSWORD", raising=False)
    monkeypatch.setenv("MESHQUEST_STAGING_PASSWORD", "staging-test-secret")
    with make_client(tmp_path) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 401
        assert client.get("/api/v1/leaderboard").status_code == 401
        basic = base64.b64encode(b"meshquest:staging-test-secret").decode()
        assert client.get("/", headers={"authorization": "Basic " + basic}).status_code == 200
        assert client.get("/api/v1/leaderboard", headers={"x-meshquest-staging-password": "staging-test-secret"}).status_code == 200
        assert client.get("/", headers={"x-meshquest-staging-password": "wrong"}).status_code == 401
        headers = {"x-meshquest-staging-password": "staging-test-secret", **ADMIN}
        assert client.post("/api/v1/admin/players", json={"node_id": "!aabbccdd", "nickname": "Tester"}, headers=headers).status_code == 201


def test_staging_refuses_to_boot_without_password(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("MESHQUEST_REQUIRE_STAGING_PASSWORD", "1")
    monkeypatch.delenv("MESHQUEST_STAGING_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="MESHQUEST_STAGING_PASSWORD"):
        create_app(f"sqlite:///{tmp_path / 'missing.db'}", "test-admin-key")


def test_staging_requires_external_postgres(tmp_path, monkeypatch):
    import pytest
    monkeypatch.setenv("MESHQUEST_REQUIRE_STAGING_PASSWORD", "1")
    monkeypatch.setenv("MESHQUEST_STAGING_PASSWORD", "staging-test-secret")
    with pytest.raises(RuntimeError, match="PostgreSQL is required"):
        create_app(f"sqlite:///{tmp_path / 'missing.db'}", "test-admin-key")
