# MeshQuest Engine: multi-game platform architecture (design proposal)

> Status: **design only**, not an implemented feature of v0.4.0-alpha. See [migration plan](MULTIGAME_MIGRATION.md), [Game API/SDK](GAME_API_SDK.md), [radio discovery](GAME_DISCOVERY.md), and [Mesh Dominion](GAMES/MESH_DOMINION.md).

## Purpose and architectural boundaries

MeshQuest is evolving from a single route-discovery RPG prototype into an open-source platform for creating independent games that use Meshtastic as an optional interaction and observation layer. Its first deployment model is **hybrid (model C)**: centrally hosted, approved internal games plus externally hosted games communicating over a versioned API. The engine must also support web-only gameplay; not every action needs to occupy RF airtime.

**Core-owned:** authentication, user-to-NodeID links, registered gateways and their scopes, approved playable radio resources, normalized event intake, session lifecycle, durable event delivery, authorized radio command scheduling, catalog/discovery, moderation, audit and platform quotas.

**Game-owned:** story, levels, crafting, territory rules, inventories, competitive ranking, puzzles, reward economy and victory conditions. Global platform identity must never imply global XP across games.

**Gateway-owned:** low-memory serial/TCP radio adapter, outbound HTTPS bearer-authenticated communication, bounded local SQLite queue, heartbeat, and (only after explicit capability enablement) authorized radio command execution. Gateway devices have no authority to award XP or run game plugins.

## Initial deployment: modular monolith + isolated workers

~~~text
                    Web / mobile UI / Creator Studio
                                 |
                        HTTPS REST / WebSocket
                                 |
                   +----------------------------+
                   |       MeshQuest Core       |
                   | identity & permissions     |
                   | game registry & sessions   |
                   | canonical event envelope   |
                   | radio ingestion & scheduler|
                   | event outbox & delivery    |
                   +-----------+----------------+
                               |
                    PostgreSQL + worker(s)
                     /                     \
              Internal games         External game hosts
           declarative/trusted       signed webhooks + API
                               |
                    Gateway API (HTTPS)
                               |
              Berry Zero W 32-bit or other gateway
               Serial / TCP / meshtasticd adapter
                               |
                 Meshtastic RF (not game-controlled)
~~~

Use the existing FastAPI + SQLAlchemy + PostgreSQL stack. A transactional outbox backed by PostgreSQL and a worker is adequate initially. Avoid Kafka/Redis/Kubernetes unless load and reliability measurements justify them. Untrusted Python game plugins must never execute in the FastAPI process; start with declarative content and trusted built-ins, then use isolation for external/community code.

## Canonical Event Envelope v1 (proposed)

Events describe **observations** and validated game actions, not cryptographic proof of a transmission route.

~~~json
{
  "schema_version": 1,
  "event_id": "evt_demo_001",
  "event_type": "radio.packet.received",
  "occurred_at": "2026-11-09T15:30:00Z",
  "recorded_at": "2026-11-09T15:30:01Z",
  "source": {
    "gateway_id": "pisa-gw",
    "transport": "tcp",
    "origin": "rf",
    "channel_index": 1
  },
  "radio": {
    "sender_node_id": "!433b96ac",
    "packet_id": 4242,
    "portnum": "TEXT_MESSAGE_APP",
    "rx_rssi": -96,
    "rx_snr": 3.2
  },
  "trust": "gateway_reported",
  "game_context": null
}
~~~

The example is illustrative. The optional game_context is attached **after** the platform has parsed and authorized a game command; raw packet ingestion must not trust a client-provided game_id. API consumers receive only data granted by their scopes, not arbitrary chat contents, sensitive payloads or exact positions.

Initial event types: radio.packet.received, radio.command.validated, radio.traceroute.observed, gateway.online, gateway.offline, player.action, game.session.started, game.timer.expired, radio.tx.status. Games may define separately namespaced domain events (for example dominion.territory.captured), which do not mutate the universal RF contract.

- Distinguish direct RF ingestion from MQTT/Internet-origin traffic and simulations. Do not treat MQTT reports as independently measured RF evidence.
- Preserve each gateway's individual sighting and metrics, while deriving a separately deduplicated logical packet event. Avoid assuming packet ID alone is globally unique.
- Use stable event IDs, uniqueness constraints, idempotency keys, transactional writes and monotonic per-subscription delivery cursors. Deliver at least once; consumers must deduplicate.
- Distinguish gateway attestation from independently verified facts. Normal packets do not reveal their full hop path; a traceroute measures its own route, not the route of prior game traffic.
- Store timestamps and evidence provenance. Enforce TTL/freshness and ownership authorization before awarding game-specific achievements.

## Radio command boundary

Games cannot send arbitrary Meshtastic payloads or change node configurations. They request bounded, server-authorized interactions through the Radio Scheduler. The scheduler enforces opt-in channel policies, per-game/per-gateway quotas, length/priority limits, destination allowlists and local radio regulations. No automatic scans, route probes or bulk unsolicited transmissions. A queued or submitted radio packet is **not** proof of delivery to a player.

Proposed readable protocol prefix: MQ1, followed by game alias, action and compact arguments. Example: MQ1 G7 SCAN B18. For basic discovery use !servers, !games, !info and !join; details in [GAME_DISCOVERY.md](GAME_DISCOVERY.md). Restrict parsing to opted-in MeshQuest application channels. The secondary channel does not provide separate RF airtime.

## Platform state

Add separate tables/collections for users and verified node_links, games and game_versions, game_sessions and session_players, per-game state, event_log and event_delivery, per-gateway radio_sightings, radio_tx_jobs, API clients/scopes and audit log. Preserve legacy players/outposts/observations/discoveries/content_packs during migration. Existing route-discovery XP stays with the original game, not with platform identity.

The architecture must support multiple gateway sightings of a single packet and multiple independent games referencing the same **consented, registered** radio node without sharing ownership of its device.

## Security and trust

- Verify NodeID ownership with a scoped, expiring challenge before account binding. A received node identifier or untrusted chat text is not sufficient authentication.
- Separate gateway bearer tokens, game credentials, admin credentials and user sessions. Rotate/revoke individually; least-privilege permissions and audit every radio request.
- Validate webhook signatures, timestamps and replay windows; retry with backoff and dead-letter delivery. Externally hosted games cannot directly reach the central database, MQTT broker or Berry.
- Publish a minimal radio identity and optional coarse area only after consent. Do not publish arbitrary observed third-party nodes as conquerable targets.
- Approve/review public game listings and user-generated content; untrusted game code executes only under isolation and resource limits.

## Acceptance criteria

1. Existing v0.4.0-alpha endpoints and metadata-only Berry agent pass unchanged integration tests against the new server.
2. Two independent games consume authorized events with isolated state, scoring and permissions.
3. Duplicate packet sightings do not double-award gameplay while preserving individual gateway metrics.
4. Loss of connectivity or third-party game service does not block the Core or force LoRa traffic.
5. No game can transmit directly, enumerate other games' private states, or control a real Meshtastic device.
