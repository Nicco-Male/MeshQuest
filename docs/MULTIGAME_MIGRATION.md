# Migration plan: existing v0.4.0-alpha to multi-game MeshQuest

> Design plan only; no migrations or runtime changes have been applied by this document. Main branch currently identifies as v0.4.0-alpha in pyproject.toml/README. Earlier design conversations began at v0.3.0-alpha, but implementation must be based on current code.

## Current reusable modules

- meshquest/app.py: FastAPI admin, gateway, profile, content-pack and observation endpoints.
- meshquest/db.py: SQLAlchemy tables players, outposts, gateways, observations, discoveries, content_packs, gateway_runtime and gateway_packets.
- meshquest/game.py: hard-coded route-explorer XP, levels and quests; migrate behind a built-in game adapter.
- meshquest/content.py and web/creator.html: declarative, moderated, preview-only authored packs; do **not** imply packs are playable yet.
- gateway_agent/agent.py: Python 3.9+ stdlib HTTP/token/SQLite offline queue, optional Meshtastic Serial/TCP integration, metadata-only capture. Real ARMv6 radio testing still outstanding.

## Incremental phases

### M0 — Contract freeze, test baseline, backup
Record current OpenAPI output, tests, routes, response schemas, gateway heartbeat and packet payloads. Add backward-compatibility integration fixtures for the unchanged read-only gateway. Establish database backup/restore before schema changes. No changes to gateway deployments yet.

### M1 — Internal Core refactor
Create modules for events, registry, sessions, identity, permissions, state and radio abstraction while preserving existing REST routes through compatibility adapters. Introduce Alembic migrations and the new tables **additively**. Do not overwrite or drop old observations, discovery history, tokens or XP.

### M2 — Two isolated games
Wrap existing route exploration logic as built-in route-explorer, retaining its XP/quests and legacy API projections. Implement a second built-in simulation to prove session/state isolation. Run synthetic playtests before real radio integration.

### M3 — Public game API and external runtime
Add manifest registry, scoped game credentials, authenticated event cursors, signed webhooks, retry/outbox delivery, idempotent actions and Python/TypeScript SDKs. Validate an external example game with mock events, disconnected webhook endpoint and re-delivery.

### M4 — Opt-in radio discovery and command channel
Introduce a versioned gateway capability handshake plus **optional** polling endpoints. Preserve existing /api/v1/gateway/heartbeat and /api/v1/gateway/packets exactly for v0.4 agent compatibility. Enable commands only on specifically permitted upgraded gateways; default to read-only. Add the Radio Scheduler, short discovery replies and server-level deduplication. Test RF hardware, real ARMv6, 32-bit OS, power/network interruptions and rate limits.

### M5 — Hub, moderation and later federation
Publish a Web game catalog, sessions UI, more capable Creator Studio and administration of per-gateway game exposure. Start with one central Pisa instance and several gateways. Add independently operated servers and optional federated directory only after discovery semantics and security are stable.

## Compatibility policy

- Agent v0.4: no mandatory new fields, API routes, libraries or protocol changes; no unsolicited RF transmission; existing token still authenticates until explicitly revoked.
- New gateway: advertises capabilities; opt-in transmit capability is independently authorized and revocable, uses server-issued bounded jobs, and never executes game rules.
- Raspberry Pi Zero W: 32-bit ARMv6, Python 3.9+ for the stdlib agent, small disk queue, outbound HTTPS. Do not require Docker, PostgreSQL, Node.js or the server Python >=3.11 runtime on the Berry.
- Keep a compatibility matrix: old agent/new Core, new agent/new Core, read-only gateway, token revocation, duplicate sightings, delayed events, disconnected external game.
- Current route credits remain attributed to route-explorer. Do not migrate legacy discoveries into global cross-game ranks.
- Add feature flags (engine, registry, discovery, TX) and enable progressively; maintain rollback for application releases, with separate forward-compatible DB migrations.

## Explicit non-goals for this stage

No live federation, no actual hacking or modification of Meshtastic nodes, no proof that game packets traversed listed radio paths, no automatic registration of third-party observed nodes, no globally available game server discovery, and no production-ready claim until security and RF acceptance tests are passed.

## Definition of done

A stable Core runs existing tests and v0.4 gateway requests unchanged, hosts two independent games, serves a scoped external API, consumes durable canonical events, demonstrates opt-in read-only discovery, and proves new optional gateway TX on a tested ARMv6 device without reconfiguring any user's radio.
