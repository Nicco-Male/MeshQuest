"""Transport-neutral, in-memory event contract.

A transport observation is not proof that a particular LoRa relay was traversed.
Handlers belong to the Core/plugin layer; this module deliberately has no game,
XP, quest, database or radio-specific dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class MeshEvent:
    transport: str
    topic: str
    packet_id: str | None
    sender: str | None
    gateway_id: str | None
    channel: str | int | None
    portnum: str | int | None
    payload: Mapping[str, Any]
    received_at: datetime
    retained: bool
    rf_verified: bool = False


class EventBus:
    """Synchronous dispatch interface for future game plugins and other consumers."""

    def __init__(self) -> None:
        self._handlers: list[Callable[[MeshEvent], None]] = []

    def subscribe(self, handler: Callable[[MeshEvent], None]) -> None:
        self._handlers.append(handler)

    def emit(self, event: MeshEvent) -> None:
        for handler in tuple(self._handlers):
            handler(event)
