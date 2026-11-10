# Salvo: Node Conquest — Proof of Concept (2026-11-09)

> **Scope of this document:** SQLAlchemy/FastAPI admin-controlled Salvo simulation.
> This legacy simulation remains admin-only. A **separate, playable closed-alpha
> radio pilot** now exists on the central CT 151 server: see
> [Salvo via DM — Capitolo 1 (Italiano)](SALVO_RADIO_CHAPTER1.it.md).
> The pilot saves fictional sector captures and Salvo credits in a separate
> SQLite database, not in the admin simulation's tables. Neither version
> changes real Meshtastic nodes or awards Exploration XP.

## Design decisions for the closed Pisa pilot

- **One central authority.** The Pisa MeshQuest API persists game state and computes all rewards.
  Raspberry Pi Zero W gateways continue using the existing Python 3.9+ read-only agent; nothing
  in the new Salvo code runs on ARMv6 gateways.
- **Separate game module.** The existing Exploration XP, traceroute/discovery rules and
  leaderboard are unchanged; virtual Salvo credits are a separate currency.
- **Explicit topology.** Admins select approved outposts as game targets and manually declare
  fictional adjacency links. Receiving packets through MQTT, GPS proximity or route telemetry
  is **not** interpreted as a verified radio link.
- **Entry points.** A new player may tackle an explicitly configured entry node. After the
  first capture, only directly adjacent nodes can be attacked.
- **Community evolution.** This is a fixed alpha game; a future game registry can expose
  additional modules, and gateways may later advertise different subsets of approved games.

## Commands available in simulated HTTP requests

| Command | Effect |
| --- | --- |
| `!listgame` | Lists the games on this server |
| `!join salvo` | Starts the player's virtual profile with 6 credits |
| `!scan` | Shows reachable game nodes and their arithmetic puzzles |
| `!hack <nodeid> <answer>` | Captures an eligible node for 2 credits if the puzzle is correct |
| `!status` | Shows virtual credits and controlled game nodes |

Controlled nodes earn **1 credit per complete minute**, calculated on the server.
The starting balance is 6 credits, capture costs 2, credits are capped at 300,
and at most 24 hours of offline income is accrued per update. These are initial
balancing values **for feedback**, not final gameplay rules.

The current puzzle is intentionally trivial: `(A + B) mod 20`, with operands
derived from the fictional target NodeID. Failed answers are free, allowing
brute force; do **not** expose this demo command endpoint to real players.
Future chapters can replace the puzzle using a pluggable challenge interface
and add server-side anti-spam, freshness and ownership verification.

## Try it locally (no Meshtastic radio necessary)

Install and run the **existing** MeshQuest server:

```bash
pip install '.[test]'
export MESHQUEST_ADMIN_KEY='your-random-private-development-key'
python -m meshquest
```

In another terminal, replace the admin key and run:

```bash
export URL=http://127.0.0.1:8000
export ADMIN_KEY='your-random-private-development-key'

# Closed-alpha player and an approved outpost already exist? Skip their registration.
curl -sS -X POST "$URL/api/v1/admin/players" -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"node_id":"!aabbccdd","nickname":"Scout"}'
curl -sS -X POST "$URL/api/v1/admin/outposts" -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"node_id":"!11223344","name":"Demo relay"}'
curl -sS -X POST "$URL/api/v1/admin/outposts/!11223344/approve" -H "X-Admin-Key: $ADMIN_KEY"
curl -sS -X POST "$URL/api/v1/admin/games/salvo/nodes" -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"node_id":"!11223344","entry_point":true}'

# Game discovery is read-only, or may be scoped to an authenticated gateway.
curl -sS "$URL/api/v1/games"

# Simulated text commands; never sent over LoRa:
curl -sS -X POST "$URL/api/v1/admin/games/salvo/command" -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"player_node_id":"!aabbccdd","text":"!join salvo"}'
curl -sS -X POST "$URL/api/v1/admin/games/salvo/command" -H "X-Admin-Key: $ADMIN_KEY" -H "Content-Type: application/json" \
  -d '{"player_node_id":"!aabbccdd","text":"!scan"}'
# Solve the displayed puzzle before issuing !hack.
```

To form a chain, approve and add another outpost, then POST
`{"a_node_id":"!11223344","b_node_id":"!55667788"}` to
`/api/v1/admin/games/salvo/links`. The link is a **game-only** edge.

Run the automated PoC tests with `pytest -q tests/test_salvo.py`.

## Physical nodes: primary vs secondary (design decision, NOT implemented)

A player's **primary NodeID** (e.g. F) is the identity used for play and must be
associated with a website account through a future ownership verification
flow. Additional registered **secondary real radios** (e.g. B/C) are not passive
point generators. Physical node uptime or an MQTT NodeInfo message **alone
must award zero network XP**.

Proposed meaningful, bounded contribution events:
- A secondary is **explicitly identified** as an intermediate hop in a
  trustworthy, fresh radio traceroute observation between unrelated participants.
  It establishes an observation for that probe, **not** proof that it forwarded
  arbitrary prior messages; identity and gateway integrity remain limitations.
- An independent player completes a game mission tied to that secondary
  outpost, as verified by the central engine (requires future live RF bridge).
- A node helps verify newly reachable network coverage, with separate
  independent observations and moderation; simple geographic coordinates
  or MQTT sightings alone do not earn credit.

Do not reward self-pings, total message volume, device count, routine beaconing
or high-frequency traceroutes. Deduplicate events, impose per-day caps and
cooldowns, apply anti-collusion rules and minimize additional LoRa airtime.
Normal packets do not reliably list every relay: radio observations and
optional self-reported telemetry require a conservative trust model.

**Economy separation:** contribution-based *Network XP* is distinct from
*Salvo virtual credits*. The current simulated virtual-node minute-based
credit accrual remains a provisional Salvo mechanic, not a reward for
physical secondary nodes. Its continuation and conversion rules are pending
playtesting. No Proof-of-Use endpoint or node-account pairing exists yet.

## API boundaries and next decisions

`GET /api/v1/games` lists server games. `GET /api/v1/gateway/games` requires the
existing gateway token and returns a catalog scoped to that gateway identity,
but **does not yet apply gateway-specific availability rules**.

`POST /api/v1/admin/games/salvo/command`, node provisioning and adjacency
setup are administrator-only; the command body is **not a trusted radio message**.

Before a public alpha we must decide player identity/pairing, anti-replay
and rate limits, whether game adjacency is hand-authored or attested by
measurements, safe bidirectional radio transport, and how local games are
published/moderated. Nothing here creates a radio bridge or a real-time
Meshtastic presence/availability guarantee.
