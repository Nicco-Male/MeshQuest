"""Salvo: centrally authoritative *fictional* node-control game (admin simulation).

This module never sends Meshtastic packets or changes a real node's state.
Topology is manually configured by the admin; MQTT presence is not an edge.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException
from pydantic import Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, or_, select
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, Outpost, Player, utcnow
from .schemas import NodeID, StrictModel, normalize

STARTING_CREDITS = 6
HACK_COST = 2
CREDITS_PER_NODE_MINUTE = 1
MAX_CREDITS = 300
MAX_OFFLINE_MINUTES = 1440


class SalvoNode(Base):
    __tablename__ = "salvo_nodes"

    node_id: Mapped[str] = mapped_column(String(9), ForeignKey("outposts.node_id"), primary_key=True)
    entry_point: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SalvoLink(Base):
    __tablename__ = "salvo_links"

    a_node_id: Mapped[str] = mapped_column(String(9), ForeignKey("salvo_nodes.node_id"), primary_key=True)
    b_node_id: Mapped[str] = mapped_column(String(9), ForeignKey("salvo_nodes.node_id"), primary_key=True)


class SalvoAccount(Base):
    __tablename__ = "salvo_accounts"

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), primary_key=True)
    credits: Mapped[int] = mapped_column(Integer, default=STARTING_CREDITS)
    last_tick_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NodeSetup(StrictModel):
    node_id: NodeID
    entry_point: bool = False


class LinkSetup(StrictModel):
    a_node_id: NodeID
    b_node_id: NodeID


class SimulatedCommand(StrictModel):
    player_node_id: NodeID
    text: str = Field(min_length=1, max_length=80)


def game_catalog() -> list[dict]:
    return [
        {"id": "exploration", "name": "MeshQuest Exploration",
         "status": "existing_simulation", "radio_enabled": False},
        {"id": "salvo", "name": "Salvo: Node Conquest",
         "status": "admin_simulation_only", "radio_enabled": False},
    ]


def _puzzle(node_id: str) -> tuple[str, str]:
    """Deliberately small, deterministic *game* puzzle, never a security check."""
    a, b = int(node_id[1:5], 16) % 20, int(node_id[5:], 16) % 20
    return f"({a} + {b}) mod 20", str((a + b) % 20)


def _now_aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _tick(db, account: SalvoAccount, now: datetime) -> None:
    """Accrue whole minutes once, using current ownership before transfers."""
    elapsed = int((now - _now_aware(account.last_tick_at)).total_seconds() // 60)
    if elapsed < 1:
        return
    owned = db.scalar(select(func.count()).select_from(SalvoNode).where(
        SalvoNode.owner_player_id == account.player_id)) or 0
    minutes = min(elapsed, MAX_OFFLINE_MINUTES)
    account.credits = min(MAX_CREDITS, account.credits + minutes * owned * CREDITS_PER_NODE_MINUTE)
    # Discard time beyond the 24-hour offline cap; retain only a sub-minute remainder.
    account.last_tick_at = now if elapsed > MAX_OFFLINE_MINUTES else (
        _now_aware(account.last_tick_at) + timedelta(minutes=elapsed))


def _accessible(db, player_id: int) -> list[SalvoNode]:
    owned = set(db.scalars(select(SalvoNode.node_id).where(
        SalvoNode.owner_player_id == player_id)).all())
    if not owned:
        return list(db.scalars(select(SalvoNode).where(
            SalvoNode.entry_point.is_(True)).order_by(SalvoNode.node_id)).all())
    links = db.scalars(select(SalvoLink).where(or_(
        SalvoLink.a_node_id.in_(owned), SalvoLink.b_node_id.in_(owned)))).all()
    targets = {link.b_node_id if link.a_node_id in owned else link.a_node_id
               for link in links}
    if not targets:
        return []
    return list(db.scalars(select(SalvoNode).where(
        SalvoNode.node_id.in_(targets), SalvoNode.owner_player_id != player_id).order_by(
            SalvoNode.node_id)).all()) + list(db.scalars(select(SalvoNode).where(
        SalvoNode.node_id.in_(targets), SalvoNode.owner_player_id.is_(None)).order_by(
            SalvoNode.node_id)).all())


def install_salvo(app: FastAPI, session_dep, require_admin, current_gateway) -> None:
    """Attach catalog and simulation routes to the existing MeshQuest API."""

    @app.get("/api/v1/games")
    def available_games():
        return {"games": game_catalog(), "radio_commands_enabled": False}

    @app.get("/api/v1/gateway/games")
    def gateway_games(gateway=Depends(current_gateway)):
        return {"gateway_id": gateway.gateway_id, "games": game_catalog(),
                "radio_commands_enabled": False}

    @app.post("/api/v1/admin/games/salvo/nodes", status_code=201,
              dependencies=[Depends(require_admin)])
    def add_node(data: NodeSetup, db=Depends(session_dep)):
        node_id = normalize(data.node_id)
        outpost = db.scalar(select(Outpost).where(
            Outpost.node_id == node_id, Outpost.approved.is_(True)))
        if outpost is None:
            raise HTTPException(404, "Register and approve the outpost before adding it to Salvo")
        if db.get(SalvoNode, node_id) is not None:
            raise HTTPException(409, "Salvo node already registered")
        db.add(SalvoNode(node_id=node_id, entry_point=data.entry_point))
        db.commit()
        return {"node_id": node_id, "entry_point": data.entry_point,
                "virtual_only": True}

    @app.post("/api/v1/admin/games/salvo/links", status_code=201,
              dependencies=[Depends(require_admin)])
    def add_link(data: LinkSetup, db=Depends(session_dep)):
        a, b = sorted((normalize(data.a_node_id), normalize(data.b_node_id)))
        if a == b:
            raise HTTPException(422, "Self-links are not permitted")
        if db.get(SalvoNode, a) is None or db.get(SalvoNode, b) is None:
            raise HTTPException(404, "Both nodes must be registered in Salvo")
        if db.get(SalvoLink, (a, b)) is not None:
            raise HTTPException(409, "Link already exists")
        db.add(SalvoLink(a_node_id=a, b_node_id=b))
        db.commit()
        return {"a_node_id": a, "b_node_id": b,
                "source": "admin_defined_game_topology_not_measured_rf"}

    @app.post("/api/v1/admin/games/salvo/command",
              dependencies=[Depends(require_admin)])
    def simulate_command(data: SimulatedCommand, db=Depends(session_dep)):
        parts = data.text.strip().lower().split()
        if parts == ["!listgame"]:
            return {"reply": "Giochi disponibili: exploration, salvo",
                    "games": game_catalog(), "simulated": True}
        player_id = normalize(data.player_node_id)
        player = db.scalar(select(Player).where(Player.node_id == player_id))
        if player is None:
            raise HTTPException(404, "Unknown player: admin registration required")
        if parts == ["!join", "salvo"]:
            account = db.get(SalvoAccount, player.id)
            if account is None:
                account = SalvoAccount(player_id=player.id, credits=STARTING_CREDITS,
                                       last_tick_at=utcnow())
                db.add(account)
                db.commit()
            return {"reply": "Salvo attivo. Usa !scan, !hack e !status.",
                    "credits": account.credits, "simulated": True}
        account = db.get(SalvoAccount, player.id)
        if account is None:
            raise HTTPException(409, "Join Salvo first with !join salvo")
        now = utcnow()
        _tick(db, account, now)
        if parts == ["!status"]:
            owned = db.scalars(select(SalvoNode.node_id).where(
                SalvoNode.owner_player_id == player.id).order_by(SalvoNode.node_id)).all()
            db.commit()
            return {"reply": f"Crediti: {account.credits}; nodi: {len(owned)}",
                    "credits": account.credits, "owned_nodes": list(owned),
                    "simulated": True}
        if parts == ["!scan"]:
            nodes = _accessible(db, player.id)
            answer = []
            for node in sorted(nodes, key=lambda n: n.node_id):
                outpost = db.scalar(select(Outpost).where(Outpost.node_id == node.node_id))
                question, _ = _puzzle(node.node_id)
                answer.append({"node_id": node.node_id, "name": outpost.name,
                               "owner_player_id": node.owner_player_id,
                               "puzzle": question})
            db.commit()
            return {"reply": f"Nodi raggiungibili nel gioco: {len(answer)}",
                    "nodes": answer, "simulated": True}
        if len(parts) == 3 and parts[0] == "!hack":
            target_id, provided = parts[1:]
            if len(target_id) != 9 or not target_id.startswith("!") or any(
                    c not in "0123456789abcdef" for c in target_id[1:]):
                raise HTTPException(422, "Invalid target NodeID")
            node = db.get(SalvoNode, target_id)
            if node is None:
                raise HTTPException(404, "Unknown Salvo target")
            if node.owner_player_id == player.id or node.node_id not in {
                    item.node_id for item in _accessible(db, player.id)}:
                raise HTTPException(409, "Target not adjacent to your territory")
            if account.credits < HACK_COST:
                raise HTTPException(409, "Not enough game credits")
            _, expected = _puzzle(target_id)
            if provided != expected:
                db.commit()
                return {"success": False, "reply": "Puzzle non risolto",
                        "credits": account.credits, "simulated": True}
            if node.owner_player_id is not None:
                previous = db.get(SalvoAccount, node.owner_player_id)
                if previous is not None:
                    _tick(db, previous, now)
            account.credits -= HACK_COST
            node.owner_player_id = player.id
            node.captured_at = now
            db.commit()
            return {"success": True, "reply": "Nodo conquistato nel gioco",
                    "node_id": node.node_id, "credits": account.credits,
                    "virtual_only": True, "simulated": True}
        raise HTTPException(422, "Valid commands: !listgame, !join salvo, !scan, !hack <nodeid> <answer>, !status")
