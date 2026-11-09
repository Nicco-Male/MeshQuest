# Roadmap

## Multi-game Engine / Game Discovery (proposed — not implemented)

- [x] Architecture, radio event contract, public API/SDK, Game Discovery, Mesh Dominion and migration specifications documented
- [ ] Freeze and test legacy API/gateway compatibility; add additive Alembic database migrations
- [ ] Extract Core event log, registry, game sessions, scoped authorization and durable delivery
- [ ] Convert current route-explorer game into isolated built-in game, add a second simulated game
- [ ] Implement external Game API, signed webhooks, OpenAPI and Python/TypeScript SDKs
- [ ] Add safe radio discovery (!servers, !games, !info, !join) with per-gateway exposure, short paginated responses and rate limits
- [ ] Add capability-negotiated optional radio TX scheduler; maintain v0.4 metadata-only read-only Berry compatibility
- [ ] Hardware-test ARMv6 Raspberry Pi Zero W 32-bit gateway and verify Serial/TCP/Meshtastic dependencies
- [ ] First Pisa playtest: 3 testers, ~12 virtual territories, 3 puzzle classes and consenting radio gateways
- [ ] Only later: independently hosted/federated MeshQuest server discovery and community game publishing

Links: [Italian overview](docs/MULTIGAME_OVERVIEW.it.md) · [Core architecture](docs/MULTIGAME_ENGINE.md) · [Discovery](docs/GAME_DISCOVERY.md) · [SDK](docs/GAME_API_SDK.md) · [Mesh Dominion](docs/GAMES/MESH_DOMINION.md) · [Migration](docs/MULTIGAME_MIGRATION.md).

- [x] Basic data model, API and English/Italian read-only dashboard
- [x] Approved outposts, gateway tokens and manual route observation deduplication
- [x] Lifetime and monthly leaderboard, first-route discovery XP
- [x] Lightweight Python 3.9+ gateway agent: bearer token, heartbeat, read-only serial/TCP capture, channel filter, bounded SQLite queue (synthetic tests; ARMv6 hardware not yet tested)
- [ ] Bidirectional radio game commands and real serial/TCP integration testing on Raspberry Pi Zero W ARMv6
- [ ] Real traceroute parsing and comparison against RF fixtures
- [ ] Website accounts, NodeID challenge verification and outpost self-service
- [x] First derived game progression: three missions, narrative chapters, levels, read-only profile UI and synthetic demo
- [x] Gateway-authored main/side/DLC submissions, moderation, bilingual previews and schema validation (no active rewards)
- [ ] Story pack revisions, Game Master portal, playable quest engine and radio/route objective verification
- [ ] Game channel text command parser and interactive radio mission state machine
- [ ] Website UX, map, moderation, gateway revocation and hardening
- [ ] Multi-gateway matching, seasons, narrative chapters and gameplay balancing

The current code is an alpha scaffold. Checked items indicate working automated API tests, not a publicly deployed game.

- [x] Creator Studio browser prototype for authored chapters, mission objectives, synthetic simulation and moderation submission
- [ ] Deploy and verify the agent on an actual Raspberry Pi Zero W 32-bit using a dedicated MeshQuest radio
