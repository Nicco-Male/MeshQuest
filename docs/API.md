# API prototype walkthrough

> [English](../README.md) · [Italiano](README.it.md)

This is a **manual, simulated observation** example. It does not perform any LoRa transmissions, radio tracing or route validation. The admin API is locked without `MESHQUEST_ADMIN_KEY`.

With the server running locally:

```bash
export URL=http://127.0.0.1:8000
export ADMIN_KEY='your-development-admin-secret'

curl -fsS -X POST "$URL/api/v1/admin/players" -H "X-Admin-Key: $ADMIN_KEY" -H 'Content-Type: application/json' \
  -d '{"node_id":"!aabbccdd","nickname":"Explorer"}'

curl -fsS -X POST "$URL/api/v1/admin/outposts" -H "X-Admin-Key: $ADMIN_KEY" -H 'Content-Type: application/json' \
  -d '{"node_id":"!11223344","name":"Relay Poggi"}'

curl -fsS -X POST "$URL/api/v1/admin/outposts/!11223344/approve" -H "X-Admin-Key: $ADMIN_KEY"

# This response reveals a newly generated token exactly once. Keep it confidential.
curl -fsS -X POST "$URL/api/v1/admin/gateways" -H "X-Admin-Key: $ADMIN_KEY" -H 'Content-Type: application/json' \
  -d '{"gateway_id":"pisa-gw","radio_node_id":"!99887766"}'

# Copy the token from the response into a protected local shell variable:
export GATEWAY_TOKEN='paste-token-from-the-previous-response'

# SIMULATION ONLY: fabricated input to exercise the scoring engine.
curl -fsS -X POST "$URL/api/v1/observations" -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"simulation-0001","player_node_id":"!aabbccdd","route_to_player":[],"route_to_gateway":["!11223344"],"unknown_to_player":0,"unknown_to_gateway":1,"source":"rf_traceroute"}'

curl -fsS "$URL/api/v1/leaderboard"
```

The ingestion endpoint only verifies **that an authenticated gateway attested** to a traceroute-shaped result. `source="rf_traceroute"` is a claim by that gateway; the API does not independently validate RF hardware. A real gateway adapter and additional proof checks remain future work.

## Read-only game progression (v0.2.0-alpha)

`GET /api/v1/game/rules?lang=en` (or `lang=it`) returns mission definitions, narrative chapters, level thresholds and proof limitations.

`GET /api/v1/quests?lang=it` returns the localized mission board.

`GET /api/v1/players/{node_id}/profile?lang=it` returns a registered player's unique discovered outposts, level, quest progress and unlocked chapters. These endpoints **never award XP or emit radio traffic**. Live RF evidence collection and self-registration are not implemented.

Run `python scripts/demo_game.py --lang it` after installing `.[test]` to exercise an entire **synthetic** three-observation round.
