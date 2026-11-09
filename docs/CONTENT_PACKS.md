# MeshQuest Creator Studio: community story packs

> **Languages:** English (this page) · [Italiano](CONTENT_PACKS.it.md) · [Translations](TRANSLATIONS.md)

**Status: v0.3.0-alpha — story pack submission, moderation, persistence and public preview are implemented. Playing custom missions over LoRa, quest completion and content XP are NOT implemented.** Do not expose the prototype API to the Internet as-is.

## Roles and boundaries

- **Main game server (Pisa):** holds the canonical campaign, central player progression, moderation and leaderboards. It is the only authority able to publish content in the alpha.
- **Content-hosting gateway / Game Master:** a PC, Raspberry Pi, Berry or similar host with a MeshQuest gateway radio; its authenticated gateway token can *propose* main-story chapters, side quests and DLC. The submitted pack is stored centrally as a pending proposal. The gateway does **not** receive admin rights.
- **Outpost:** an ordinary Meshtastic relay; no PC, MeshQuest channel, Internet or content engine is required. Outposts cannot upload story packs merely by relaying radio traffic.
- **Player:** can eventually activate an adventure through a MeshQuest gateway's radio interface. In the current alpha, packs are preview-only on the website.

## Content types

| Kind | Description | Publication |
|---|---|---|
| `main` | Suggested chapter for the global, canonical campaign | Pisa admin review, always |
| `side` | Independent, optional mission(s) by a regional gateway | Pisa admin review in alpha; community publishing policy later |
| `dlc` | A standalone expansion with multiple chapters or a seasonal story | Pisa admin review in alpha |

A package contains bilingual title and synopsis, 1–8 chapters, and 1–12 missions per chapter. Each mission is declarative and has an objective of type:

- `reach_gateway` with a registered gateway slug (future proof: RF link, not an Internet-only event);
- `discover_outpost` with a specific Meshtastic NodeID (future proof: identified and approved relay in an observed return path);
- `discover_count` with a minimum count of unique approved discovered outposts;
- `solve_riddle` for narrative puzzles (future verification mechanism). **Do not embed a secret answer in publicly visible JSON.**

English and Italian strings are currently required. The translation system can be generalized later. Mission `suggested_xp` is **only a proposal** (0–50 XP per mission). **Publishing a pack does not award XP**, and the current leaderboard remains based on unique outpost discoveries. The public API sets `playable: false` and `awarded_xp: 0` explicitly.

## Authoring workflow (API prototype)

1. An administrator registers a gateway and safely delivers its bearer token; public self-service gateway registration is not implemented.
2. The gateway submits the JSON to `POST /api/v1/gateway/content-packs` with `Authorization: Bearer $GATEWAY_TOKEN`.
3. An administrator reviews `GET /api/v1/admin/content-packs?pack_status=pending` with `X-Admin-Key`, then publishes with `POST /api/v1/admin/content-packs/{slug}/publish` or rejects with `/reject`.
4. Anyone may browse published adventures via `GET /api/v1/content-packs?lang=en` (or `it`), `?kind=side` and `GET /api/v1/content-packs/{slug}?lang=it`. Pending/rejected packs are not public. A gateway lists its own statuses at `GET /api/v1/gateway/content-packs`.

The first sample pack is [`examples/tuscany-lost-signal.json`](../examples/tuscany-lost-signal.json). To submit it against a **local development instance**, where the gateway is already registered:

```bash
curl -fsS -X POST http://127.0.0.1:8000/api/v1/gateway/content-packs \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/tuscany-lost-signal.json
```

Slugs are globally unique. An approved `main` pack is publicly categorized as main-story content but is **not yet linked to the built-in core campaign or automatic chapter unlocks**. A submitted pack is immutable in this alpha, even after rejection: use a new slug for a revised proposal. In later versions use stable pack IDs plus immutable revisions and allow controlled updates, withdrawal and translations.

## RF design for playable content (future work)

A single player should be able to accept missions from several gateways while progress is stored centrally. A mission must never be marked complete merely because the web API was contacted: route/relay objectives will be backed by a fresh gateway-attested RF observation, subject to freshness, anti-replay and radio budgets. Unknown relays are not assigned specific NodeIDs. Puzzle solutions need server-side verification with rate limits and must not be present in public packs. A compromised gateway may still lie: proper gateway trust, abuse mitigation and review are prerequisites for official XP.

**Important:** the MeshQuest application channel remains required for players and game radio gateways, but optional for passive relays. Channel segregation does not allocate extra airtime. No custom gateway executes arbitrary scripts from a content package.
