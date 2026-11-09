# MeshQuest

> **Language / Lingua / Languages:** **English (this page)** · [🇮🇹 Guida italiana](docs/README.it.md) · [🌐 Translations & contributing languages](docs/TRANSLATIONS.md)

**MeshQuest is an experimental, open-source exploration/RPG project for Meshtastic networks.** Players discover *observed radio routes*, identify registered relay outposts and gain experience points (XP). The game backend runs on a central server; ordinary remote Meshtastic nodes can become outposts **without a computer, dedicated agent or MeshQuest channel**.

**Project status: v0.4.0-alpha — gameplay and community-authored content API prototype. The live bidirectional Meshtastic game bridge, traceroute validation, self-service accounts and radio commands are NOT implemented yet. Do not deploy this prototype as a public game service.**

## The idea

- **Players** join the MeshQuest channel using a Meshtastic device and later connect a verified NodeID to their website account.
- **Radio gateways** located in homes or server installations communicate with the central API over HTTPS using individual bearer tokens. Their lightweight agent (Python 3.9+, including 32-bit ARMv6 design target) performs no game logic. A read-only capture and heartbeat prototype is available.
- **Outposts** are ordinary Meshtastic relay nodes registered by NodeID. They do not require the MeshQuest channel, an Internet connection or an agent.
- **Game server** maintains approved outposts, observations, discoveries, XP and leaderboards. The primary instance is planned for Pisa, but the software is portable.

```text
Player (MeshQuest channel) --LoRa--> ordinary relay/outpost --LoRa--> radio gateway
                                       (no agent)                           |
                                                                    HTTPS (future agent)
                                                                            |
                                                                  MeshQuest game server
                                                                 API + database + web UI
```

A secondary MeshQuest channel separates application messages **logically**, but does **not** reserve separate airtime or change LoRa modem settings. The primary channel, region, preset and frequency slot must be compatible for relaying. A relay without the channel key can still retransmit packets, subject to its rebroadcast configuration.

## Critical distinction: route observations are not proof of message paths

Normal data packets don't reveal every relay they traversed. Meshtastic traceroute provides a **separate route measurement**. Only relays able to participate in the traceroute's channel encryption can identify themselves; others may appear as *unknown hops*. The forward and return paths may differ, and a new traceroute does **not** prove the path taken by an earlier game message.

The API prototype accepts trusted gateway **reports** from a traceroute initiated by the gateway towards a player:

- `route_to_player`: intermediate identifiers on the outgoing measurement;
- `route_to_gateway`: intermediate identifiers on its return measurement;
- `unknown_to_*`: number of unidentifiable hops, as reported by the gateway.

**Alpha scoring rule:** 50 XP once per player and approved outpost that is explicitly present in `route_to_gateway`. Unknown hops never yield outpost-specific credit. A unique event ID prevents replay scoring. Unapproved nodes get no XP. This is **gateway attestation**, not cryptographic RF proof: a compromised gateway can fabricate evidence. Hardware testing and an abuse-resistant proof protocol are future work.

## Current functionality

| Feature | Status |
| --- | --- |
| REST API, schema, SQLite (development), PostgreSQL (Compose) | Implemented (prototype) |
| Admin-only registration of players/outposts/gateways | Implemented (closed alpha) |
| Manual outpost approval | Implemented |
| Authenticated gateway observation ingestion and deduplication | Implemented; no live RF adapter |
| Unique-outpost XP and lifetime/monthly leaderboard | Implemented |
| Three progress-based quests, chapters/levels, player profile API and simulated round | Implemented; no radio adapter |
| English/Italian read-only home page, quest board, community adventures and profile viewer | Implemented |
| Gateway-authored main-story proposals, side quests and DLC, with Pisa admin moderation | Implemented (preview only; no quest completion or DLC XP) |
| Read-only serial/TCP gateway agent, token heartbeat and metadata ingestion | Implemented; untested on physical ARMv6 |
| Bidirectional Meshtastic game bridge and RF traceroute verification | Not implemented |
| Website login, radio ownership verification, mission/command parser | Not implemented |
| Autonomous local/offline play and federated servers | Not implemented |

## Salvo: Node Conquest (proposed proof of concept)

The optional **Salvo** module adds an **admin-only gameplay simulation**: a
server-side game catalog (`GET /api/v1/games`, gateway-scoped catalog with
bearer auth), explicitly configured fictional adjacency, arithmetic node
puzzles, virtual capture and accruing game credits. `!listgame`,
`!join salvo`, `!scan`, `!hack` and `!status` are interpreted through a
protected HTTP simulation endpoint, **not through Meshtastic radio**.
Salvo balances do not affect exploration XP. A radio command adapter and
public player authentication are still missing.

See [Salvo pilot guide](docs/SALVO_POC.md). The PoC is suitable for local
API tests only, not public gameplay.

## Cloud staging (optional)

A password-protected **Render + Neon** blueprint is available for API/UI testing without a home-server LXC. **No cloud service is deployed automatically by this repository.** GitHub Pages and Actions alone cannot host the persistent game API. See [cloud staging instructions](docs/HOSTING.md) ([italiano](docs/HOSTING.it.md)). The free Render instance sleeps when idle and the alpha is **not** ready for public gameplay.

## Run locally

Requirements: Python 3.11+, Git.

```bash
git clone https://github.com/Nicco-Male/MeshQuest.git
cd MeshQuest
python3 -m venv .venv
source .venv/bin/activate
pip install '.[test]'
export MESHQUEST_ADMIN_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m meshquest
```

Visit `http://127.0.0.1:8000/` for the read-only leaderboard or `http://127.0.0.1:8000/docs` for the interactive API. The default local database is `./meshquest.db`.

To verify the foundation:

```bash
pytest -q
```

### Run with Docker Compose (local development only)

```bash
cp .env.example .env
# Replace BOTH placeholder secrets in .env with strong independent random values.
docker compose up --build -d
```

The API binds to `127.0.0.1:8765` by default. Do **not** expose it publicly before authentication, rate limiting, migrations and RF integration are complete. PostgreSQL volumes persist data.

### Prototype walkthrough

Use an `X-Admin-Key` HTTP header for admin requests. Register a player, an outpost, approve the outpost and register a gateway using `POST /api/v1/admin/...`. Gateway creation returns a bearer token **once**. Submit `POST /api/v1/observations` with `Authorization: Bearer <gateway-token>`. Test calls report **simulated evidence** and must never be represented as live RF validations.

See the **[first gameplay loop](docs/GAMEPLAY.md)** ([italiano](docs/GAMEPLAY.it.md)), [API examples](docs/API.md) and [architecture/verification notes](docs/ARCHITECTURE.md).

Community Game Masters can submit bilingual **main story proposals**, **side quests** and **DLC packs** with their gateway token. The central server reviews and publishes each pack. Open **`/creator`** after starting the local server ([editor source](web/creator.html)). See **[Creator Studio / Content Packs](docs/CONTENT_PACKS.md)** ([italiano](docs/CONTENT_PACKS.it.md)) and the [Tuscany sample DLC](examples/tuscany-lost-signal.json). These packs are **preview-only**: posting or approving a pack grants no XP and does not execute radio commands.

### Simulate a complete round (no radio transmissions)

```bash
python scripts/demo_game.py --lang en
```

The simulation runs against the actual backend scoring code with a temporary database; all observations are deliberately fabricated test data. The game API now includes `GET /api/v1/game/rules?lang=en` and `GET /api/v1/players/{node_id}/profile?lang=en` (also `it`).


### Raspberry Pi Zero W gateway (32-bit ARMv6)

**Do not install the MeshQuest game server on the Raspberry.** It runs only `gateway_agent/agent.py`, authenticated to Pisa using a dedicated bearer token. Python 3.9+ stdlib for the agent core, with Meshtastic as an optional radio adapter. Test the radio package on the real ARMv6 device before relying on it.

```bash
python3 gateway_agent/agent.py --self-test
# With a private mode-0600 token file and a running Pisa API:
MESHQUEST_SERVER=https://YOUR_SERVER MESHQUEST_TOKEN_FILE=/path/to/token \
  python3 gateway_agent/agent.py --check
```

See **[Gateway setup](docs/GATEWAY.md)** ([italiano](docs/GATEWAY.it.md)). Captured packet metadata never scores XP and the read-only agent never transmits LoRa packets.

## Contributions and multilingual docs

- Canonical technical content: English (`README.md`).
- Italian guide: [`docs/README.it.md`](docs/README.it.md).
- Language structure and translation workflow: [`docs/TRANSLATIONS.md`](docs/TRANSLATIONS.md).
- Please report protocol corrections with firmware versions and reproduction traces where possible.

## License and attribution

MIT License. Independent community project; **not affiliated with or endorsed by Meshtastic**. Respect local radio regulations and avoid excessive traceroute traffic.
