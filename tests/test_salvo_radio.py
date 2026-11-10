"""Playable Salvo radio chapter: virtual-only puzzles, adjacency and persistence."""
import sqlite3
from meshquest.salvo_radio import SalvoRadio, SECTORS


PLAYER = "!e9a04b31"
OTHER = "!11223344"


def game(tmp_path, randbelow=None):
    return SalvoRadio(tmp_path / "salvo-radio.db", randbelow=randbelow or (lambda upper: 0))


def test_first_real_radio_game_loop(tmp_path):
    g = game(tmp_path)
    assert g.handle(PLAYER, "!scan", now=1) == "Salvo: inizia con !play salvo."
    assert "6 crediti" in g.handle(PLAYER, "!play salvo", now=1)
    assert "1:Portale" in g.handle(PLAYER, "!scan", now=2)
    assert "Portale: 3+2=?" in g.handle(PLAYER, "!hack 1", now=3)
    assert "2 tentativi" in g.handle(PLAYER, "!solve 99", now=4)
    assert "Portale conquistato!" in g.handle(PLAYER, "!solve 5", now=5)
    assert "4c" in g.handle(PLAYER, "!status", now=6)
    assert "1:Relay" in g.handle(PLAYER, "!scan", now=7)
    assert "nessun" in g.handle(PLAYER, "!solve 5", now=8).lower()
    assert "non raggiungibile" in g.handle(PLAYER, "!hack 2", now=9)


def test_progress_survives_restart_and_is_shared_between_gateways(tmp_path):
    g = game(tmp_path)
    g.handle(PLAYER, "!play salvo", now=100)
    g.handle(PLAYER, "!hack 1", now=101)
    g.handle(PLAYER, "!solve 5", now=102)
    # Create a different instance as if a different MeshMonitor source opened it.
    g2 = SalvoRadio(tmp_path / "salvo-radio.db", randbelow=lambda upper: 0)
    assert "1 nodi" in g2.handle(PLAYER, "!play salvo", now=105)
    assert "1:Relay" in g2.handle(PLAYER, "!scan", now=106)
    assert g2.handle(OTHER, "!status", now=107) is None
    assert "6 crediti" in g2.handle(OTHER, "!play salvo", now=108)
    assert "1:Portale" in g2.handle(OTHER, "!scan", now=109)


def test_income_and_credits_never_mint_when_replaying_solve(tmp_path):
    g = game(tmp_path)
    g.handle(PLAYER, "!play salvo", now=100)
    g.handle(PLAYER, "!hack 1", now=101)
    g.handle(PLAYER, "!solve 5", now=102)
    assert "1/6 nodi" in g.handle(PLAYER, "!status", now=102)
    assert "7c" in g.handle(PLAYER, "!status", now=282)  # 3 minutes income
    assert "7c" in g.handle(PLAYER, "!status", now=283)
    assert g.handle(PLAYER, "!solve 5", now=284).startswith("Nessun puzzle")
    assert "7c" in g.handle(PLAYER, "!status", now=285)
    with sqlite3.connect(tmp_path / "salvo-radio.db") as db:
        assert db.execute("SELECT COUNT(*) FROM salvo_radio_captures").fetchone()[0] == 1


def test_three_failed_solutions_lock_puzzle_for_60s(tmp_path):
    g = game(tmp_path)
    g.handle(PLAYER, "!play salvo", now=0)
    g.handle(PLAYER, "!hack 1", now=1)
    assert "2 tentativi" in g.handle(PLAYER, "!solve 99", now=2)
    assert "1 tentativi" in g.handle(PLAYER, "!solve 99", now=3)
    assert "Riprova tra 60s" in g.handle(PLAYER, "!solve 99", now=4)
    assert "Blocco puzzle" in g.handle(PLAYER, "!hack 1", now=5)
    assert "Puzzle Portale" in g.handle(PLAYER, "!hack 1", now=65)
    assert "Portale conquistato" in g.handle(PLAYER, "!solve 5", now=66)


def test_expired_challenge_and_invalid_attack_do_not_spend_credits(tmp_path):
    g = game(tmp_path)
    g.handle(PLAYER, "!play salvo", now=0)
    assert "non raggiungibile" in g.handle(PLAYER, "!hack 9", now=1)
    g.handle(PLAYER, "!hack 1", now=2)
    assert "scaduto" in g.handle(PLAYER, "!solve 5", now=123)
    assert "6c" in g.handle(PLAYER, "!status", now=124)
    assert "Salvo: !scan" in g.handle(PLAYER, "!hack garbage", now=125)


def test_map_adjacency_and_completion(tmp_path):
    g = game(tmp_path)
    assert len(SECTORS) == 6
    g.handle(PLAYER, "!play salvo", now=0)
    t = 10
    for index in range(len(SECTORS)):
        scan = g.handle(PLAYER, "!scan", now=t)
        if index == 0:
            assert "Portale" in scan and "Relay" not in scan
        if index == 1:
            assert "Relay" in scan and "Torre" not in scan
        # Always take the first currently reachable sector. All other sectors
        # become accessible only when their prerequisite nodes are captured.
        g.handle(PLAYER, "!hack 1", now=t + 1)
        solved = g.handle(PLAYER, "!solve 5", now=t + 2)
        assert "conquistato" in solved or "vinto" in solved
        t += 180  # income from controlled sectors makes further captures affordable
    assert "rete conquistata" in g.handle(PLAYER, "!scan", now=t)
    assert "6/6 nodi" in g.handle(PLAYER, "!status", now=t)


def test_leave_and_reenter_keeps_captures(tmp_path):
    g = game(tmp_path)
    g.handle(PLAYER, "!play salvo", now=0)
    g.handle(PLAYER, "!hack 1", now=1)
    g.handle(PLAYER, "!solve 5", now=2)
    assert "Progressi salvati" in g.handle(PLAYER, "!leave salvo", now=3)
    assert g.handle(PLAYER, "!status", now=4) is None
    assert "inserire" not in g.handle(PLAYER, "!scan", now=5)
    assert "1 nodi" in g.handle(PLAYER, "!play salvo", now=6)
    assert "1:Relay" in g.handle(PLAYER, "!scan", now=7)


def test_player_node_id_is_only_virtual_identity(tmp_path):
    g = game(tmp_path)
    assert g.handle("not-node", "!play salvo", now=1) is None
    assert g.handle(PLAYER, "hello", now=1) is None
    assert g.handle(PLAYER, "!hack 1", now=1) == "Salvo: inizia con !play salvo."
    with sqlite3.connect(tmp_path / "salvo-radio.db") as db:
        tables = set(row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
    assert "players" not in tables and "outposts" not in tables


def test_radio_adapter_routes_salvo_commands_and_preserves_gateway_dm(tmp_path):
    from gateway_agent.channel_discovery import ChannelDiscovery
    from test_channel_discovery import API, NAV, PISA, incoming_dm

    api = API()
    bot = ChannelDiscovery(api, [NAV, PISA], allowed_player=PLAYER, salvo_game=game(tmp_path))
    bot.poll(now=0)
    api.inboxes[NAV.source_id].insert(0, incoming_dm(51, text="!play salvo"))
    bot.poll(now=1)
    assert "Salvo avviato" in api.dms[-1][2]
    api.inboxes[NAV.source_id].insert(0, incoming_dm(52, text="!scan"))
    bot.poll(now=4)
    assert "Portale" in api.dms[-1][2]
    api.inboxes[PISA.source_id].insert(0, incoming_dm(53, gateway=PISA, text="!status"))
    bot.poll(now=7)
    assert any("Salvo:" in text for sid, player, text in api.dms if sid == PISA.source_id)
    assert all(sid in (NAV.source_id, PISA.source_id) for sid, _, _ in api.dms)
