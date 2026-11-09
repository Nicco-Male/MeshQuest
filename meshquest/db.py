"""Persistence models. Dev uses SQLite; deployment can use PostgreSQL."""
from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[str] = mapped_column(String(9), unique=True, index=True)
    nickname: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Outpost(Base):
    __tablename__ = "outposts"
    id: Mapped[int] = mapped_column(primary_key=True)
    node_id: Mapped[str] = mapped_column(String(9), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Gateway(Base):
    __tablename__ = "gateways"
    id: Mapped[int] = mapped_column(primary_key=True)
    gateway_id: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    radio_node_id: Mapped[str] = mapped_column(String(9))
    token_hash: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (UniqueConstraint("gateway_id", "event_id", name="uq_gateway_event"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    gateway_id: Mapped[int] = mapped_column(ForeignKey("gateways.id"))
    event_id: Mapped[str] = mapped_column(String(80))
    player_node_id: Mapped[str] = mapped_column(String(9))
    route_to_player_json: Mapped[str] = mapped_column(Text)
    route_to_gateway_json: Mapped[str] = mapped_column(Text)
    unknown_to_player: Mapped[int] = mapped_column(Integer)
    unknown_to_gateway: Mapped[int] = mapped_column(Integer)
    credited_json: Mapped[str] = mapped_column(Text, default="[]")
    xp_awarded: Mapped[int] = mapped_column(Integer, default=0)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Discovery(Base):
    __tablename__ = "discoveries"
    __table_args__ = (UniqueConstraint("player_id", "outpost_id", name="uq_player_outpost"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    outpost_id: Mapped[int] = mapped_column(ForeignKey("outposts.id"))
    observation_id: Mapped[int] = mapped_column(ForeignKey("observations.id"))
    xp: Mapped[int] = mapped_column(Integer, default=50)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_session_factory(database_url: str):
    opts = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite:") else {}
    engine = create_engine(database_url, pool_pre_ping=True, **opts)
    Base.metadata.create_all(engine)  # Initial prototype only: add migrations before production rollout.
    return sessionmaker(bind=engine, expire_on_commit=False)
