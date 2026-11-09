"""Community-authored story packs. Publishing does not grant XP or emit radio packets.

Content data is declarative, never executable. The central server curates all public packs.
"""
from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated

from .schemas import NodeID

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,63}$")]
GatewaySlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{2,39}$")]


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TranslatedText(ContentModel):
    en: str = Field(min_length=3, max_length=2000)
    it: str = Field(min_length=3, max_length=2000)


class ObjectiveIn(ContentModel):
    kind: Literal["reach_gateway", "discover_outpost", "discover_count", "solve_riddle"]
    gateway_id: GatewaySlug | None = None
    outpost_node_id: NodeID | None = None
    unique_outposts: int | None = Field(default=None, ge=1, le=20)

    @model_validator(mode="after")
    def validate_target(self):
        expected = {
            "reach_gateway": "gateway_id",
            "discover_outpost": "outpost_node_id",
            "discover_count": "unique_outposts",
            "solve_riddle": None,
        }[self.kind]
        supplied = {field for field in ("gateway_id", "outpost_node_id", "unique_outposts") if getattr(self, field) is not None}
        if supplied != ({expected} if expected else set()):
            raise ValueError("Objective target must match its kind, without unrelated fields")
        return self


class MissionIn(ContentModel):
    slug: Slug
    title: TranslatedText
    description: TranslatedText
    objective: ObjectiveIn
    suggested_xp: int = Field(default=0, ge=0, le=50)


class ChapterIn(ContentModel):
    slug: Slug
    title: TranslatedText
    story: TranslatedText
    missions: list[MissionIn] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def unique_missions(self):
        ids = [mission.slug for mission in self.missions]
        if len(ids) != len(set(ids)):
            raise ValueError("Mission slugs must be unique within the chapter")
        return self


class ContentPackIn(ContentModel):
    slug: Slug
    kind: Literal["main", "side", "dlc"]
    title: TranslatedText
    summary: TranslatedText
    chapters: list[ChapterIn] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def unique_chapters(self):
        ids = [chapter.slug for chapter in self.chapters]
        if len(ids) != len(set(ids)):
            raise ValueError("Chapter slugs must be unique within the pack")
        return self


def public_pack(record, lang: Literal["en", "it"] = "en") -> dict:
    """Render approved-only content; the calling endpoint enforces visibility."""
    raw = json.loads(record.content_json)
    return {
        "slug": record.slug,
        "kind": record.kind,
        "version": record.version,
        "author_gateway": record.author_gateway_id,
        "title": raw["title"][lang],
        "summary": raw["summary"][lang],
        "chapters": [
            {
                "slug": chapter["slug"],
                "title": chapter["title"][lang],
                "story": chapter["story"][lang],
                "missions": [
                    {
                        "slug": mission["slug"],
                        "title": mission["title"][lang],
                        "description": mission["description"][lang],
                        "objective": mission["objective"],
                        "suggested_xp": mission["suggested_xp"],
                        "awarded_xp": 0,
                    }
                    for mission in chapter["missions"]
                ],
            }
            for chapter in raw["chapters"]
        ],
        "playable": False,
        "note": "Published narrative preview only: radio quest validation and reward payouts are not implemented.",
    }


class SimulationEvidenceIn(ContentModel):
    """Synthetic, declarative inputs to preview objectives; never radio evidence."""
    discovered_outposts: list[NodeID] = Field(default_factory=list, max_length=50)
    reached_gateways: list[GatewaySlug] = Field(default_factory=list, max_length=50)
    solved_riddles: list[Slug] = Field(default_factory=list, max_length=50)


class ContentSimulationIn(ContentModel):
    pack: ContentPackIn
    evidence: SimulationEvidenceIn


def simulate_pack(pack: ContentPackIn, evidence: SimulationEvidenceIn) -> dict:
    """Evaluate a draft against hypothetical facts without persistence or XP."""
    outposts = {node.lower() for node in evidence.discovered_outposts}
    gateways = set(evidence.reached_gateways)
    riddles = set(evidence.solved_riddles)
    result = []
    for chapter in pack.chapters:
        missions = []
        for mission in chapter.missions:
            objective = mission.objective
            completed = {
                "reach_gateway": lambda: objective.gateway_id in gateways,
                "discover_outpost": lambda: objective.outpost_node_id.lower() in outposts,
                "discover_count": lambda: len(outposts) >= objective.unique_outposts,
                "solve_riddle": lambda: mission.slug in riddles,
            }[objective.kind]()
            missions.append({"slug": mission.slug, "completed": completed,
                             "suggested_xp": mission.suggested_xp, "awarded_xp": 0})
        result.append({"slug": chapter.slug, "missions": missions})
    return {"slug": pack.slug, "simulated": True, "persisted": False,
            "radio_verified": False, "awarded_xp": 0, "chapters": result}
