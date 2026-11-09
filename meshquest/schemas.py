"""Strict external API payloads: route labels represent *observations*, not guaranteed RF paths."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

NodeID = Annotated[str, StringConstraints(pattern=r"^![0-9a-fA-F]{8}$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlayerIn(StrictModel):
    node_id: NodeID
    nickname: str = Field(min_length=2, max_length=40)


class OutpostIn(StrictModel):
    node_id: NodeID
    name: str = Field(min_length=2, max_length=80)


class GatewayIn(StrictModel):
    gateway_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,39}$")
    radio_node_id: NodeID


class RouteIn(StrictModel):
    event_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    player_node_id: NodeID
    # Traceroute initiated by the gateway towards the player; intermediate IDs only.
    route_to_player: list[NodeID] = Field(max_length=20)
    route_to_gateway: list[NodeID] = Field(max_length=20)
    unknown_to_player: int = Field(default=0, ge=0, le=20)
    unknown_to_gateway: int = Field(default=0, ge=0, le=20)
    source: str = Field(pattern=r"^rf_traceroute$")


def normalize(node_id: str) -> str:
    return node_id.lower()


class GatewayHeartbeatIn(StrictModel):
    agent_version: str = Field(min_length=1, max_length=32, pattern=r"^[a-zA-Z0-9._-]+$")
    transport: Literal["serial", "tcp", "test"]


class GatewayPacketIn(StrictModel):
    """Untrusted radio metadata. Ingestion must NEVER grant game XP."""
    event_id: str = Field(min_length=8, max_length=80, pattern=r"^[a-zA-Z0-9._:-]+$")
    observation_type: Literal["packet_metadata_only"]
    channel_index: int = Field(ge=0, le=7)
    sender_node_id: NodeID | None = None
    portnum: str | None = Field(default=None, max_length=64)
    hop_start: int | None = Field(default=None, ge=0, le=15)
    hop_limit: int | None = Field(default=None, ge=0, le=15)
    rx_rssi: int | None = Field(default=None, ge=-200, le=0)
    rx_snr: float | None = Field(default=None, ge=-100, le=100, allow_inf_nan=False)
    via_mqtt: Literal[False] = False
