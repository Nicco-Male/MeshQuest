"""Transport layer for MeshQuest Core. No game rules or radio I/O here."""
from .events import EventBus, MeshEvent

__all__ = ["EventBus", "MeshEvent"]
