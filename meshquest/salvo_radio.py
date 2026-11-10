"""Salvo closed-alpha radio campaign: *fictional* nodes, persistent central state.

Runs on the Pisa/CT 151 server and is invoked only by the DM adapter. It never
touches Meshtastic hardware, network topology, real node permissions or
Exploration XP. All gateways use the same SQLite database.

This is a playtest game independent of the administrator-only Salvo HTTP
simulation. Account/node ownership verification and PvP are NOT implemented.
"""
from __future__ import annotations

import os
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

STARTING_CREDITS = 6
HACK_COST = 2
MAX_CREDITS = 300
MAX_OFFLINE_MINUTES = 1440
CHALLENGE_TTL = 120
LOCK_SECONDS = 60
MAX_ATTEMPTS = 3
NODE_ID = re.compile(r"^![0-9a-f]{8}$")


@dataclass(frozen=True)
class Sector:
    key: str
    name: str
    requires: tuple[str, ...]


# Purely fictional, directed chapter map: a node's prerequisites must be
# captured before that node becomes available. No RF relationship is inferred.
SECTORS = (
    Sector("portale", "Portale", ()),
    Sector("relay", "Relay", ("portale",)),
    Sector("bastione", "Bastione", ("relay",)),
    Sector("archivio", "Archivio", ("relay",)),
    Sector("torre", "Torre", ("bastione", "archivio")),
    Sector("nucleo", "Nucleo", ("torre",)),
)


class SalvoRadio:
    def __init__(self, path, randbelow=None):
        if not path or str(path) == ":memory:":
            raise ValueError("Salvo needs a persistent SQLite file path")
        self.path = str(path)
        self.randbelow = randbelow or secrets.randbelow
        Path(self.path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path, timeout=15) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("""CREATE TABLE IF NOT EXISTS salvo_radio_players (
                node_id TEXT PRIMARY KEY,
                credits INTEGER NOT NULL,
                last_tick REAL NOT NULL,
                active INTEGER NOT NULL,
                cooldown_until REAL NOT NULL DEFAULT 0
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS salvo_radio_captures (
                node_id TEXT NOT NULL,
                sector TEXT NOT NULL,
                captured_at REAL NOT NULL,
                PRIMARY KEY (node_id, sector)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS salvo_radio_challenges (
                node_id TEXT PRIMARY KEY,
                sector TEXT NOT NULL,
                question TEXT NOT NULL,
                answer INTEGER NOT NULL,
                expires_at REAL NOT NULL,
                attempts INTEGER NOT NULL
            )""")

    @staticmethod
    def _owned(db, player):
        return {row[0] for row in db.execute(
            "SELECT sector FROM salvo_radio_captures WHERE node_id = ?", (player,)
        ).fetchall()}

    @staticmethod
    def _reachable(owned):
        return [s for s in SECTORS if s.key not in owned
                and all(req in owned for req in s.requires)]

    @staticmethod
    def _credits(db, player, owned, now):
        row = db.execute(
            "SELECT credits, last_tick FROM salvo_radio_players WHERE node_id = ?",
            (player,)
        ).fetchone()
        credits, last_tick = int(row[0]), float(row[1])
        elapsed = max(0, int((now - last_tick) // 60))
        if elapsed:
            credits = min(MAX_CREDITS, credits + len(owned) * min(elapsed, MAX_OFFLINE_MINUTES))
            updated_tick = now if elapsed > MAX_OFFLINE_MINUTES else last_tick + elapsed * 60
            db.execute(
                "UPDATE salvo_radio_players SET credits=?, last_tick=? WHERE node_id=?",
                (credits, updated_tick, player)
            )
        return credits

    def handle(self, player_id, command, now=None):
        """Return a short radio reply for Salvo commands or None for other games."""
        player = player_id.lower() if isinstance(player_id, str) else ""
        if not NODE_ID.fullmatch(player):
            return None
        if not isinstance(command, str) or len(command) > 80:
            return None
        parts = command.strip().casefold().split()
        if not parts or not parts[0].startswith("!"):
            return None
        relevant = (parts[:1] in (["!scan"], ["!hack"], ["!solve"], ["!map"])
                    or parts in (["!play", "salvo"], ["!join", "salvo"],
                                 ["!leave", "salvo"], ["!help"], ["!menu"],
                                 ["!status"]))
        if not relevant:
            return None
        now = time.time() if now is None else float(now)
        db = sqlite3.connect(self.path, timeout=15)
        try:
            # Serialize read-modify-write across gateways/processes.
            db.execute("BEGIN IMMEDIATE")
            reply = self._handle(db, player, parts, now)
            db.commit()
            if reply is not None and len(reply.encode("utf-8")) > 120:
                raise AssertionError("Salvo reply exceeds one small radio packet")
            return reply
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _handle(self, db, player, parts, now):
        account = db.execute(
            "SELECT credits, active, cooldown_until FROM salvo_radio_players WHERE node_id=?",
            (player,)
        ).fetchone()

        if parts in (["!play", "salvo"], ["!join", "salvo"]):
            if account is None:
                db.execute(
                    "INSERT INTO salvo_radio_players(node_id,credits,last_tick,active) VALUES(?,?,?,1)",
                    (player, STARTING_CREDITS, now)
                )
                return "Salvo avviato: 6 crediti. !scan esplora, !status profilo."
            owned = self._owned(db, player)
            credits = self._credits(db, player, owned, now)
            db.execute("UPDATE salvo_radio_players SET active=1 WHERE node_id=?", (player,))
            return "Salvo ripreso: %d crediti, %d nodi. !scan" % (credits, len(owned))

        if account is None or account[1] != 1:
            if parts[:1] in (["!scan"], ["!hack"], ["!solve"], ["!map"]):
                return "Salvo: inizia con !play salvo."
            return None

        owned = self._owned(db, player)
        credits = self._credits(db, player, owned, now)

        if parts in (["!help"], ["!menu"]):
            return "Salvo: !scan, !hack N, !solve N, !map, !status, !leave salvo"
        if parts == ["!status"]:
            return "Salvo: %dc, %d/%d nodi, +%dc/min. !scan" % (
                credits, len(owned), len(SECTORS), len(owned)
            )
        if parts == ["!map"]:
            owned_names = ",".join(s.name for s in SECTORS if s.key in owned) or "nessuno"
            visible = ",".join(s.name for s in self._reachable(owned)) or "nessuno"
            return "Tu: %s | prossimi: %s" % (owned_names, visible)
        if parts == ["!leave", "salvo"]:
            db.execute("UPDATE salvo_radio_players SET active=0 WHERE node_id=?", (player,))
            db.execute("DELETE FROM salvo_radio_challenges WHERE node_id=?", (player,))
            return "Salvo sospeso. Progressi salvati. Rientra con !play salvo."
        if parts == ["!scan"]:
            targets = self._reachable(owned)
            if not targets:
                return "Salvo: rete conquistata! %d/%d nodi. !status" % (
                    len(owned), len(SECTORS))
            names = " ".join("%d:%s" % (i, s.name) for i, s in enumerate(targets, 1))
            return "Accessibili: %s. !hack N (2c)" % names

        if parts[0] == "!hack":
            targets = self._reachable(owned)
            if len(parts) != 2 or not parts[1].isdigit():
                return "Salvo: !scan, poi !hack N"
            position = int(parts[1])
            if not 1 <= position <= len(targets):
                return "Nodo non raggiungibile. Usa !scan."
            if credits < HACK_COST:
                return "Crediti insufficienti (%dc). Attendi rendita." % credits
            if now < float(account[2]):
                return "Blocco puzzle: riprova tra %ds." % max(1, int(account[2] - now) + 1)
            sector = targets[position - 1]
            pending = db.execute(
                "SELECT sector,question,expires_at FROM salvo_radio_challenges WHERE node_id=?",
                (player,)
            ).fetchone()
            if pending and float(pending[2]) > now:
                return "Puzzle %s: %s !solve N" % (pending[0].capitalize(), pending[1])
            left = self.randbelow(16) + 3
            right = self.randbelow(14) + 2
            question = "%d+%d=?" % (left, right)
            db.execute(
                """INSERT INTO salvo_radio_challenges(node_id,sector,question,answer,expires_at,attempts)
                   VALUES(?,?,?,?,?,0)
                   ON CONFLICT(node_id) DO UPDATE SET
                   sector=excluded.sector,question=excluded.question,
                   answer=excluded.answer,expires_at=excluded.expires_at,attempts=0""",
                (player, sector.key, question, left + right, now + CHALLENGE_TTL)
            )
            return "Puzzle %s: %s Rispondi !solve N" % (sector.name, question)

        if parts[0] == "!solve":
            if len(parts) != 2 or not re.fullmatch(r"-?\d{1,4}", parts[1]):
                return "Salvo: !solve NUMERO (es. !solve 12)"
            row = db.execute(
                "SELECT sector,answer,expires_at,attempts FROM salvo_radio_challenges WHERE node_id=?",
                (player,)
            ).fetchone()
            if row is None:
                return "Nessun puzzle attivo. Usa !scan e !hack N."
            if now >= row[2]:
                db.execute("DELETE FROM salvo_radio_challenges WHERE node_id=?", (player,))
                return "Puzzle scaduto. Usa !hack N."
            if now < float(account[2]):
                return "Blocco puzzle: riprova tra %ds." % max(1, int(account[2] - now) + 1)
            if int(parts[1]) != row[1]:
                attempts = int(row[3]) + 1
                if attempts >= MAX_ATTEMPTS:
                    db.execute("DELETE FROM salvo_radio_challenges WHERE node_id=?", (player,))
                    db.execute("UPDATE salvo_radio_players SET cooldown_until=? WHERE node_id=?",
                               (now + LOCK_SECONDS, player))
                    return "Puzzle fallito 3 volte. Riprova tra 60s."
                db.execute("UPDATE salvo_radio_challenges SET attempts=? WHERE node_id=?",
                           (attempts, player))
                return "Errato: restano %d tentativi." % (MAX_ATTEMPTS - attempts)
            # Validate target still available before spending currency.
            target = str(row[0])
            reachable = {s.key for s in self._reachable(owned)}
            db.execute("DELETE FROM salvo_radio_challenges WHERE node_id=?", (player,))
            if target not in reachable:
                return "Nodo non piu raggiungibile. Usa !scan."
            if credits < HACK_COST:
                return "Crediti insufficienti. Attendi rendita."
            db.execute("INSERT INTO salvo_radio_captures VALUES(?,?,?)",
                       (player, target, now))
            db.execute("UPDATE salvo_radio_players SET credits=? WHERE node_id=?",
                       (credits - HACK_COST, player))
            name = next(s.name for s in SECTORS if s.key == target)
            if len(owned) + 1 == len(SECTORS):
                return "Salvo vinto! Nucleo conquistato, %d nodi. %dc" % (
                    len(SECTORS), credits - HACK_COST)
            return "%s conquistato! %dc, %d nodi. !scan" % (
                name, credits - HACK_COST, len(owned) + 1)
        return None
