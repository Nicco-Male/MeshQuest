# Roadmap

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
