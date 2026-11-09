# Salvo: Node Conquest — Proof of Concept (2026-11-09)

> **Status:** API-based, **admin-controlled simulation only**. No radio commands, no radio transmissions,
> no real device takeover, no authorization based solely on a claimed Meshtastic NodeID.

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
