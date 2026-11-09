"""Read-only game design and player progression for route-based exploration.

XP is awarded ONLY by the existing authenticated gateway observation flow.
Mission completion is derived from persisted, unique outpost discoveries; reading
these rules or profiles cannot award XP or emit LoRa traffic.
"""
from __future__ import annotations

LEVEL_THRESHOLDS = (0, 100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700)
OUTPOST_XP = 50

_LOCALIZED = {
    "en": {
        "mission_first_title": "First Echo",
        "mission_first_detail": "Discover one approved outpost on a gateway traceroute return path.",
        "mission_second_title": "The Cartographer",
        "mission_second_detail": "Discover two different approved outposts.",
        "mission_third_title": "The Lost Archive",
        "mission_third_detail": "Discover three different approved outposts and restore the first archive.",
        "chapter_one_title": "Chapter I · The Awakening",
        "chapter_one_story": "The silence breaks. One repeater answers the call.",
        "chapter_two_title": "Chapter II · The Echoes",
        "chapter_two_story": "Two distant fragments hint at a forgotten radio network.",
        "chapter_three_title": "Chapter III · The Archive",
        "chapter_three_story": "Three outposts reveal the first page of the lost archive.",
        "rule_note": "Only uniquely discovered, approved outposts explicitly identified in a trusted gateway's traceroute return observation earn XP. Unidentified hops never identify specific outposts. This is gateway attestation, not cryptographic proof of a radio path.",
    },
    "it": {
        "mission_first_title": "Primo Eco",
        "mission_first_detail": "Scopri un avamposto approvato nel percorso di ritorno di un traceroute del gateway.",
        "mission_second_title": "Il Cartografo",
        "mission_second_detail": "Scopri due avamposti approvati differenti.",
        "mission_third_title": "L'Archivio Perduto",
        "mission_third_detail": "Scopri tre avamposti approvati differenti e ripristina il primo archivio.",
        "chapter_one_title": "Capitolo I · Il Risveglio",
        "chapter_one_story": "Il silenzio si spezza. Un ripetitore risponde alla chiamata.",
        "chapter_two_title": "Capitolo II · Gli Echi",
        "chapter_two_story": "Due frammenti lontani raccontano di una rete radio dimenticata.",
        "chapter_three_title": "Capitolo III · L'Archivio",
        "chapter_three_story": "Tre avamposti rivelano la prima pagina dell'archivio perduto.",
        "rule_note": "Solo gli avamposti approvati e identificati nel ritorno del traceroute dichiarato da un gateway fidato danno XP alla prima scoperta. Gli hop sconosciuti non identificano avamposti. È un'attestazione del gateway, non una prova crittografica del percorso radio.",
    },
}

MISSION_SPECS = (
    ("first-echo", 1, "mission_first_title", "mission_first_detail"),
    ("cartographer", 2, "mission_second_title", "mission_second_detail"),
    ("lost-archive", 3, "mission_third_title", "mission_third_detail"),
)
CHAPTER_SPECS = (
    ("awakening", 1, "chapter_one_title", "chapter_one_story"),
    ("echoes", 2, "chapter_two_title", "chapter_two_story"),
    ("archive", 3, "chapter_three_title", "chapter_three_story"),
)


def _locale(lang: str) -> dict[str, str]:
    if lang not in _LOCALIZED:
        raise ValueError("Unsupported language")
    return _LOCALIZED[lang]


def mission_board(lang: str = "en", completed_count: int = 0) -> list[dict]:
    t = _locale(lang)
    return [
        {
            "id": mission_id,
            "title": t[title_key],
            "description": t[detail_key],
            "target_unique_outposts": target,
            "progress": min(completed_count, target),
            "completed": completed_count >= target,
            "extra_xp": 0,  # XP already comes from unique, attested outpost discoveries.
        }
        for mission_id, target, title_key, detail_key in MISSION_SPECS
    ]


def chapter_board(lang: str = "en", completed_count: int = 0) -> list[dict]:
    t = _locale(lang)
    return [
        {"id": chapter_id, "title": t[title_key], "story": t[story_key], "unlocked": completed_count >= target,
         "required_unique_outposts": target}
        for chapter_id, target, title_key, story_key in CHAPTER_SPECS
    ]


def level_state(xp: int) -> dict:
    if xp < 0:
        raise ValueError("XP cannot be negative")
    for n, start in enumerate(LEVEL_THRESHOLDS):
        if n + 1 == len(LEVEL_THRESHOLDS) or xp < LEVEL_THRESHOLDS[n + 1]:
            next_xp = LEVEL_THRESHOLDS[n + 1] if n + 1 < len(LEVEL_THRESHOLDS) else None
            return {"level": n + 1, "level_start_xp": start, "next_level_xp": next_xp,
                    "xp_to_next_level": max(0, next_xp - xp) if next_xp is not None else None}
    raise AssertionError("Unexpected level calculation")


def game_rules(lang: str = "en") -> dict:
    t = _locale(lang)
    return {
        "language": lang,
        "outpost_first_discovery_xp": OUTPOST_XP,
        "missions": mission_board(lang),
        "chapters": chapter_board(lang),
        "level_thresholds": list(LEVEL_THRESHOLDS),
        "proof_note": t["rule_note"],
        "status": "prototype_only_no_live_radio_bridge",
    }


def player_profile(node_id: str, nickname: str, discoveries: list[dict], lang: str = "en") -> dict:
    _locale(lang)
    unique = len({d["node_id"] for d in discoveries})
    earned_xp = sum(d["xp"] for d in discoveries)
    return {
        "node_id": node_id,
        "nickname": nickname,
        "xp": earned_xp,
        "unique_outposts": unique,
        "level": level_state(earned_xp),
        "missions": mission_board(lang, unique),
        "chapters": chapter_board(lang, unique),
        "discovered_outposts": discoveries,
        "language": lang,
        "evidence": "trusted_gateway_attestation_not_independent_rf_proof",
    }
