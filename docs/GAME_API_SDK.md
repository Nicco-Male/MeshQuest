# Public Game API and SDK contract (design proposal)

> Status: **planned interfaces**. These routes, SDKs and manifests do not exist in v0.4.0-alpha. Do not confuse them with the implemented legacy /api/v1/game/rules and /api/v1/gateway/* endpoints.

## Runtime models

1. **Internal game:** approved declarative rules or trusted code hosted by MeshQuest with an explicit game namespace.
2. **External game:** independent service using platform HTTPS API plus signed webhook delivery or cursor polling; never direct database, MQTT or radio access.
3. The same event/command semantics apply to both. The Core owns accounts, verified radio bindings, game registry, sessions and radio permissions; games own their rule state and scoring.

## Proposed REST endpoints

~~~http
GET  /api/v1/platform/games
GET  /api/v1/platform/games/{game_id}
POST /api/v1/platform/games/{game_id}/sessions
GET  /api/v1/platform/sessions/{session_id}
POST /api/v1/platform/sessions/{session_id}/actions
GET  /api/v1/platform/events?cursor=...
POST /api/v1/platform/radio/requests

POST /api/v1/gateway/capabilities
GET  /api/v1/gateway/commands
POST /api/v1/gateway/commands/{command_id}/receipt
~~~

All above are proposals, not working endpoints. The existing v0.4.0-alpha /api/v1/gateway/heartbeat, /api/v1/gateway/packets and /api/v1/observations endpoints retain their current contract during migration.

## Game manifest v1 (illustrative)

~~~json
{
  "schema_version": 1,
  "id": "mesh-dominion",
  "name": "Mesh Dominion",
  "version": "0.1.0",
  "runtime": "external",
  "players": {"min": 1, "max": 16},
  "capabilities": ["events:read", "sessions:write", "state:write", "radio:request"],
  "event_subscriptions": ["radio.command.validated", "player.action", "game.timer.expired"]
}
~~~

Capabilities require administrator/user approval. A manifest is not an authorization grant. Never include gateway tokens, admin keys or raw secret channel keys in the manifest.

## Event delivery

Use the canonical [Event Envelope v1](MULTIGAME_ENGINE.md). Each subscription is partitioned by game_id and has a durable cursor. Delivery is **at least once**, in stable per-subscription order when possible, and requires consumer idempotency. Retry failed signed HTTPS webhook deliveries with exponential backoff; support dead-letter/quarantine and manual reprocessing. WebSocket may be added for live UI but is not the durable queue.

Webhooks must be authenticated using HMAC or equivalent, body integrity, timestamp, key rotation and replay protection. No automatic access to raw radio message contents; publish minimal, opt-in, scoped events.

## Authentication and authorization

Separate token classes and scopes:
- User auth: account-bound session, verified association to NodeID for radio actions.
- Gateway auth: a token issued to one gateway, permissions for receiving metadata and (later) permitted radio command execution.
- Game auth: per-game service credentials and scoped requests for events:read, sessions:write, state:write and radio:request.
- Admin auth: private server operations including moderation and capability approvals.

Only the Radio Scheduler is permitted to queue a radio transmission. Games may submit a constrained request including target, game/session, TTL, idempotency key and message template; the Core validates consent, opt-in channel, per-gateway airtime budget, rate limit and content policy.

## SDK deliverables

- Python SDK: typed client, auth, event cursor iteration, webhook verifier, reconnect/backoff, idempotency helper and examples.
- TypeScript SDK: matching REST types, async event consumption, webhook validation and sample game integration.
- Machine-readable OpenAPI, event JSON Schemas, contract compatibility suite and versioning policy.
- An external sample game that consumes radio.command.validated but never talks to a Berry directly.

Suggested Python developer experience (not yet executable):

~~~python
from meshquest_sdk import MeshQuestClient

client = MeshQuestClient(server_url="https://example.invalid", token="GAME_API_TOKEN")

for event in client.events(game_id="ghost-signal"):
    if event.type == "radio.command.validated" and event.action == "SCAN":
        client.sessions.submit_result(
            session_id=event.session_id,
            idempotency_key=event.event_id,
            result={"signal_found": True},
        )
~~~

Never imply the example SDK has been published or tested. Version breaking protocol changes separately from non-breaking endpoint additions. Maintain a defined sunset/deprecation window for the gateway protocol, with explicit capability negotiation.
