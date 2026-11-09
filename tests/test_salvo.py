"""Proof-of-concept tests: no real radio or hacking operations."""
from datetime import timedelta

from meshquest.db import make_session_factory, utcnow
from meshquest.salvo import SalvoAccount, _puzzle
from test_api import ADMIN, make_client, seed


def command(client, text, node_id="!aabbccdd", headers=ADMIN):
    return client.post("/api/v1/admin/games/salvo/command",
                       json={"player_node_id": node_id, "text": text}, headers=headers)


def add_outpost(client, node_id, name):
    assert client.post("/api/v1/admin/outposts", headers=ADMIN,
                       json={"node_id": node_id, "name": name}).status_code == 201
    assert client.post(f"/api/v1/admin/outposts/{node_id}/approve",
                       headers=ADMIN).status_code == 200


def add_salvo_node(client, node_id, entry=False):
    return client.post("/api/v1/admin/games/salvo/nodes", headers=ADMIN,
                       json={"node_id": node_id, "entry_point": entry})


def test_catalog_and_gateway_scope(tmp_path):
    with make_client(tmp_path) as client:
        catalog = client.get("/api/v1/games")
        assert catalog.status_code == 200
        assert [g["id"] for g in catalog.json()["games"]] == ["exploration", "salvo"]
        assert all(not g["radio_enabled"] for g in catalog.json()["games"])
        assert client.get("/api/v1/gateway/games").status_code == 401
        gateway_auth = seed(client)
        gateway = client.get("/api/v1/gateway/games", headers=gateway_auth)
        assert gateway.status_code == 200
        assert gateway.json()["gateway_id"] == "pisa-gw"
        assert command(client, "!listgame").json()["simulated"] is True


def test_entry_adjacency_puzzle_and_capture(tmp_path):
    with make_client(tmp_path) as client:
        seed(client)
        add_outpost(client, "!55667788", "Relay B")
        add_outpost(client, "!a1b2c3d4", "Relay C")
        for node, entry in [("!11223344", True), ("!55667788", False),
                            ("!a1b2c3d4", False)]:
            assert add_salvo_node(client, node, entry).status_code == 201
        assert client.post("/api/v1/admin/games/salvo/links", headers=ADMIN,
                           json={"a_node_id": "!11223344",
                                 "b_node_id": "!55667788"}).status_code == 201
        assert command(client, "!scan").status_code == 409
        assert command(client, "!join salvo").status_code == 200
        scan = command(client, "!scan").json()["nodes"]
        assert [n["node_id"] for n in scan] == ["!11223344"]
        unreachable = command(client, f"!hack !55667788 {_puzzle('!55667788')[1]}")
        assert unreachable.status_code == 409
        incorrect = command(client, "!hack !11223344 999")
        assert incorrect.status_code == 200 and incorrect.json()["success"] is False
        first = command(client, f"!hack !11223344 {_puzzle('!11223344')[1]}")
        assert first.status_code == 200 and first.json()["success"] is True
        assert first.json()["credits"] == 4
        scan2 = command(client, "!scan").json()["nodes"]
        assert [n["node_id"] for n in scan2] == ["!55667788"]
        second = command(client, f"!hack !55667788 {_puzzle('!55667788')[1]}")
        assert second.status_code == 200 and second.json()["success"] is True
        assert command(client, "!scan").json()["nodes"] == []
        status = command(client, "!status").json()
        assert status["owned_nodes"] == ["!11223344", "!55667788"]
        assert status["credits"] == 2


def test_virtual_capture_does_not_award_exploration_xp(tmp_path):
    with make_client(tmp_path) as client:
        seed(client)
        add_salvo_node(client, "!11223344", True)
        command(client, "!join salvo")
        assert command(client, f"!hack !11223344 {_puzzle('!11223344')[1]}").status_code == 200
        assert client.get("/api/v1/leaderboard").json()["players"][0]["xp"] == 0
        assert client.get("/api/v1/players/!aabbccdd/profile").json()["xp"] == 0


def test_income_is_server_calculated_and_persistent(tmp_path):
    db_path = tmp_path / "meshquest-test.db"
    with make_client(tmp_path) as client:
        seed(client)
        add_salvo_node(client, "!11223344", True)
        command(client, "!join salvo")
        command(client, f"!hack !11223344 {_puzzle('!11223344')[1]}")
        Session = make_session_factory(f"sqlite:///{db_path}")
        with Session() as db:
            account = db.get(SalvoAccount, 1)
            assert account.credits == 4
            account.last_tick_at = utcnow() - timedelta(minutes=3)
            db.commit()
        result = command(client, "!status")
        assert result.status_code == 200
        assert result.json()["credits"] >= 7
        assert command(client, "!status").json()["credits"] == result.json()["credits"]


def test_game_auth_and_manual_topology(tmp_path):
    with make_client(tmp_path) as client:
        gateway_auth = seed(client)
        assert add_salvo_node(client, "!01010101", True).status_code == 404
        assert client.post("/api/v1/admin/games/salvo/nodes",
                           json={"node_id": "!11223344", "entry_point": True}).status_code == 401
        assert command(client, "!join salvo", headers=gateway_auth).status_code == 401
        assert add_salvo_node(client, "!11223344", True).status_code == 201
        assert add_salvo_node(client, "!11223344", True).status_code == 409
        assert client.post("/api/v1/admin/games/salvo/links", headers=ADMIN,
                           json={"a_node_id": "!11223344", "b_node_id": "!11223344"}).status_code == 422
        assert command(client, "!badcommand").status_code == 409
        command(client, "!join salvo")
        assert command(client, "!badcommand").status_code == 422
