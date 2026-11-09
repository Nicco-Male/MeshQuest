"""MeshQuest minimal API. Not ready for public-facing deployment without additional auth hardening."""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .db import ContentPack, Discovery, Gateway, Observation, Outpost, Player, make_session_factory, utcnow
from .game import game_rules, player_profile
from .content import ContentPackIn, public_pack
from .schemas import GatewayIn, OutpostIn, PlayerIn, RouteIn, normalize

BASE_DIR = Path(__file__).resolve().parent.parent


def sha256(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def create_app(database_url: str | None = None, admin_key: str | None = None) -> FastAPI:
    database_url = database_url or os.getenv("MESHQUEST_DATABASE_URL", "sqlite:///./meshquest.db")
    admin_key = admin_key if admin_key is not None else os.getenv("MESHQUEST_ADMIN_KEY", "")
    # Cloud staging remains password protected; never silently fall back to SQLite in cloud.
    staging_password = os.getenv("MESHQUEST_STAGING_PASSWORD", "")
    if os.getenv("MESHQUEST_REQUIRE_STAGING_PASSWORD") == "1":
        if not staging_password:
            raise RuntimeError("MESHQUEST_STAGING_PASSWORD is required for cloud staging")
        if not database_url.startswith("postgresql"):
            raise RuntimeError("PostgreSQL is required for cloud staging (no ephemeral SQLite)")
    SessionLocal = make_session_factory(database_url)
    app = FastAPI(title="MeshQuest", version="0.3.0-alpha", description="Experimental route-observation game API")

    @app.middleware("http")
    async def cloud_staging_guard(request: Request, call_next):
        if not staging_password or request.url.path == "/health":
            return await call_next(request)
        supplied = request.headers.get("x-meshquest-staging-password", "")
        auth = request.headers.get("authorization", "")
        if not supplied and auth.startswith("Basic "):
            try:
                userpass = base64.b64decode(auth[6:], validate=True).decode("utf-8")
                username, separator, password = userpass.partition(":")
                if separator and username == "meshquest":
                    supplied = password
            except (ValueError, UnicodeError, binascii.Error):
                pass
        if not hmac.compare_digest(supplied, staging_password):
            return PlainTextResponse(
                "MeshQuest staging: authentication required",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="MeshQuest staging"'},
            )
        return await call_next(request)

    def session_dep():
        with SessionLocal() as session:
            yield session

    def require_admin(x_admin_key: str | None = Header(default=None)):
        if not admin_key:
            raise HTTPException(503, "Admin API is disabled until MESHQUEST_ADMIN_KEY is configured")
        if not x_admin_key or not hmac.compare_digest(x_admin_key, admin_key):
            raise HTTPException(401, "Invalid administrator key")

    def current_gateway(authorization: str | None = Header(default=None), db=Depends(session_dep)):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(401, "Missing gateway bearer token")
        token = authorization[7:]
        if not token:
            raise HTTPException(401, "Invalid gateway bearer token")
        digest = sha256(token)
        # Prototype lookup: tokens are random 256-bit values; never log or store cleartext tokens.
        gateway = db.scalar(select(Gateway).where(Gateway.token_hash == digest, Gateway.enabled.is_(True)))
        if gateway is None:
            raise HTTPException(401, "Invalid gateway bearer token")
        return gateway

    @app.get("/", include_in_schema=False)
    def home():
        return FileResponse(BASE_DIR / "web" / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.3.0-alpha"}

    @app.post("/api/v1/admin/players", dependencies=[Depends(require_admin)], status_code=201)
    def add_player(data: PlayerIn, db=Depends(session_dep)):
        player = Player(node_id=normalize(data.node_id), nickname=data.nickname.strip())
        db.add(player)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Player NodeID already registered")
        return {"node_id": player.node_id, "nickname": player.nickname}

    @app.post("/api/v1/admin/outposts", dependencies=[Depends(require_admin)], status_code=201)
    def add_outpost(data: OutpostIn, db=Depends(session_dep)):
        outpost = Outpost(node_id=normalize(data.node_id), name=data.name.strip(), approved=False)
        db.add(outpost)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Outpost NodeID already registered")
        return {"node_id": outpost.node_id, "name": outpost.name, "approved": False}

    @app.post("/api/v1/admin/outposts/{node_id}/approve", dependencies=[Depends(require_admin)])
    def approve_outpost(node_id: str, db=Depends(session_dep)):
        outpost = db.scalar(select(Outpost).where(Outpost.node_id == normalize(node_id)))
        if outpost is None:
            raise HTTPException(404, "Unknown outpost")
        outpost.approved = True
        db.commit()
        return {"node_id": outpost.node_id, "approved": True}

    @app.post("/api/v1/admin/gateways", dependencies=[Depends(require_admin)], status_code=201)
    def add_gateway(data: GatewayIn, db=Depends(session_dep)):
        token = secrets.token_urlsafe(32)
        gateway = Gateway(gateway_id=data.gateway_id, radio_node_id=normalize(data.radio_node_id), token_hash=sha256(token))
        db.add(gateway)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Gateway already registered")
        return {"gateway_id": gateway.gateway_id, "radio_node_id": gateway.radio_node_id, "token": token, "warning": "Store the token securely. It is displayed only once."}

    @app.post("/api/v1/gateway/content-packs", status_code=201)
    def submit_content_pack(data: ContentPackIn, gateway: Gateway = Depends(current_gateway), db=Depends(session_dep)):
        # A gateway can submit a side quest, DLC, or a proposed main-story chapter.
        # No gateway token can bypass moderation or directly affect XP.
        pack = ContentPack(
            slug=data.slug,
            author_gateway_id=gateway.gateway_id,
            kind=data.kind,
            status="pending",
            content_json=json.dumps(data.model_dump(mode="json"), ensure_ascii=False),
        )
        db.add(pack)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Content pack slug already used")
        return {"slug": pack.slug, "author_gateway": gateway.gateway_id, "kind": pack.kind, "status": "pending", "published": False}

    @app.get("/api/v1/gateway/content-packs")
    def my_content_packs(gateway: Gateway = Depends(current_gateway), db=Depends(session_dep)):
        packs = db.scalars(select(ContentPack).where(ContentPack.author_gateway_id == gateway.gateway_id).order_by(ContentPack.id.desc())).all()
        return [{"slug": p.slug, "kind": p.kind, "status": p.status, "version": p.version} for p in packs]

    @app.get("/api/v1/admin/content-packs", dependencies=[Depends(require_admin)])
    def review_content_packs(pack_status: str = Query(default="pending", pattern=r"^(pending|published|rejected)$"),
                             limit: int = Query(default=50, ge=1, le=50), db=Depends(session_dep)):
        packs = db.scalars(select(ContentPack).where(ContentPack.status == pack_status)
                           .order_by(ContentPack.id.desc()).limit(limit)).all()
        return [
            {"slug": pack.slug, "kind": pack.kind, "author_gateway": pack.author_gateway_id,
             "status": pack.status, "content": json.loads(pack.content_json)}
            for pack in packs
        ]

    @app.post("/api/v1/admin/content-packs/{slug}/publish", dependencies=[Depends(require_admin)])
    def publish_content_pack(slug: str, db=Depends(session_dep)):
        pack = db.scalar(select(ContentPack).where(ContentPack.slug == slug))
        if pack is None:
            raise HTTPException(404, "Unknown content pack")
        if pack.status != "pending":
            raise HTTPException(409, "Only pending content can be published")
        pack.status = "published"
        pack.reviewed_at = utcnow()
        db.commit()
        return {"slug": pack.slug, "status": pack.status, "kind": pack.kind}

    @app.post("/api/v1/admin/content-packs/{slug}/reject", dependencies=[Depends(require_admin)])
    def reject_content_pack(slug: str, db=Depends(session_dep)):
        pack = db.scalar(select(ContentPack).where(ContentPack.slug == slug))
        if pack is None:
            raise HTTPException(404, "Unknown content pack")
        if pack.status != "pending":
            raise HTTPException(409, "Only pending content can be rejected")
        pack.status = "rejected"
        pack.reviewed_at = utcnow()
        db.commit()
        return {"slug": pack.slug, "status": pack.status}

    @app.get("/api/v1/content-packs")
    def list_public_content_packs(lang: str = Query(default="en", pattern=r"^(en|it)$"),
                                  kind: str | None = Query(default=None, pattern=r"^(main|side|dlc)$"),
                                  limit: int = Query(default=50, ge=1, le=50), db=Depends(session_dep)):
        query = select(ContentPack).where(ContentPack.status == "published")
        if kind is not None:
            query = query.where(ContentPack.kind == kind)
        packs = db.scalars(query.order_by(ContentPack.id.desc()).limit(limit)).all()
        return [public_pack(pack, lang) for pack in packs]

    @app.get("/api/v1/content-packs/{slug}")
    def get_public_content_pack(slug: str, lang: str = Query(default="en", pattern=r"^(en|it)$"), db=Depends(session_dep)):
        pack = db.scalar(select(ContentPack).where(ContentPack.slug == slug, ContentPack.status == "published"))
        if pack is None:
            raise HTTPException(404, "Content pack not published")
        return public_pack(pack, lang)

    @app.get("/api/v1/outposts")
    def list_outposts(db=Depends(session_dep)):
        outposts = db.scalars(select(Outpost).where(Outpost.approved.is_(True)).order_by(Outpost.name)).all()
        return [{"node_id": o.node_id, "name": o.name, "approved": o.approved} for o in outposts]

    @app.get("/api/v1/game/rules")
    def get_game_rules(lang: str = Query(default="en", pattern=r"^(en|it)$")):
        return game_rules(lang)

    @app.get("/api/v1/quests")
    def list_quests(lang: str = Query(default="en", pattern=r"^(en|it)$")):
        return game_rules(lang)["missions"]

    @app.get("/api/v1/players/{node_id}/profile")
    def get_player_profile(node_id: str, lang: str = Query(default="en", pattern=r"^(en|it)$"), db=Depends(session_dep)):
        player = db.scalar(select(Player).where(Player.node_id == normalize(node_id)))
        if player is None:
            raise HTTPException(404, "Unknown player")
        discoveries = db.execute(
            select(Discovery, Outpost).join(Outpost, Outpost.id == Discovery.outpost_id)
            .where(Discovery.player_id == player.id).order_by(Discovery.earned_at, Discovery.id)
        ).all()
        found = [{"node_id": outpost.node_id, "name": outpost.name, "xp": discovery.xp,
                  "discovered_at": discovery.earned_at.isoformat()}
                 for discovery, outpost in discoveries]
        return player_profile(player.node_id, player.nickname, found, lang)

    @app.post("/api/v1/observations")
    def ingest_route(event: RouteIn, gateway: Gateway = Depends(current_gateway), db=Depends(session_dep)):
        # An authenticated gateway attests to a fresh native Meshtastic traceroute.
        # The server CANNOT independently prove gateway honesty or original message path.
        old = db.scalar(select(Observation).where(Observation.gateway_id == gateway.id, Observation.event_id == event.event_id))
        if old:
            return {"observation_id": old.id, "duplicate": True, "credited_outposts": json.loads(old.credited_json), "xp_awarded": old.xp_awarded}

        player_node_id = normalize(event.player_node_id)
        player = db.scalar(select(Player).where(Player.node_id == player_node_id))
        if player is None:
            raise HTTPException(404, "Unknown player; register in closed alpha first")
        path = [normalize(n) for n in event.route_to_gateway]
        outbound = [normalize(n) for n in event.route_to_player]
        if gateway.radio_node_id in path or player_node_id in path or gateway.radio_node_id in outbound or player_node_id in outbound:
            raise HTTPException(422, "Paths must list intermediate nodes only")

        obs = Observation(
            gateway_id=gateway.id, event_id=event.event_id, player_node_id=player_node_id,
            route_to_player_json=json.dumps(outbound), route_to_gateway_json=json.dumps(path),
            unknown_to_player=event.unknown_to_player, unknown_to_gateway=event.unknown_to_gateway,
            credited_json="[]", xp_awarded=0,
        )
        db.add(obs)
        db.flush()
        credited = []
        for node_id in dict.fromkeys(path):
            outpost = db.scalar(select(Outpost).where(Outpost.node_id == node_id, Outpost.approved.is_(True)))
            if outpost is None:
                continue
            existing = db.scalar(select(Discovery).where(Discovery.player_id == player.id, Discovery.outpost_id == outpost.id))
            if existing:
                continue
            db.add(Discovery(player_id=player.id, outpost_id=outpost.id, observation_id=obs.id, xp=50))
            credited.append(node_id)
        obs.credited_json = json.dumps(credited)
        obs.xp_awarded = 50 * len(credited)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Under concurrent ingestion, unique constraints prevent double credit.
            raise HTTPException(409, "Concurrent duplicate event/discovery: retry using a new read")
        return {"observation_id": obs.id, "duplicate": False, "credited_outposts": credited, "xp_awarded": obs.xp_awarded}

    @app.get("/api/v1/leaderboard")
    def leaderboard(scope: str = Query(default="all", pattern=r"^(all|month)$"), db=Depends(session_dep)):
        stmt = select(
            Player.node_id, Player.nickname,
            func.count(Discovery.id).label("outposts"),
            func.coalesce(func.sum(Discovery.xp), 0).label("xp"),
        ).select_from(Player).outerjoin(Discovery, Discovery.player_id == Player.id)
        if scope == "month":
            # Use date boundaries instead of a fixed duration. Include players with zero XP.
            current = datetime.now(timezone.utc)
            start = datetime(current.year, current.month, 1, tzinfo=timezone.utc)
            from sqlalchemy import and_
            stmt = select(
                Player.node_id, Player.nickname,
                func.count(Discovery.id).filter(Discovery.earned_at >= start).label("outposts"),
                func.coalesce(func.sum(Discovery.xp).filter(Discovery.earned_at >= start), 0).label("xp"),
            ).select_from(Player).outerjoin(Discovery, Discovery.player_id == Player.id)
        stmt = stmt.group_by(Player.id).order_by(func.coalesce(func.sum(Discovery.xp), 0).desc(), Player.nickname.asc())
        rows = db.execute(stmt).all()
        result = [{"rank": index, "node_id": row.node_id, "nickname": row.nickname, "xp": int(row.xp or 0), "outposts": int(row.outposts or 0)} for index, row in enumerate(sorted(rows, key=lambda r: (-int(r.xp or 0), r.nickname.casefold())), start=1)]
        return {"scope": scope, "players": result}

    return app


app = create_app()
