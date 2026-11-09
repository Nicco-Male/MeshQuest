# MeshQuest Radio Game & Server Discovery (design proposal)

> **Not implemented** in v0.4.0-alpha. The shipped gateway is read-only. The commands below require a future bidirectional, server-authorized gateway protocol. This specification describes the discovery experience, not a claim that nearby servers can be enumerated today.

## User experience

A player entering a new radio area can ask the MeshQuest network which **reachable** registered server instances and their exposed games are available. The system lists services actually advertised by responding gateways, not every server on the Internet and not necessarily every geographically nearby instance.

Default command set (case-insensitive aliases may be provided after implementation):

| Command | Meaning |
| --- | --- |
| !servers | Request a short list of responding MeshQuest instances/gateways. |
| !games | List games advertised through responding gateways (short/paginated). |
| !games LU1 | List games offered through a particular advertised server alias. |
| !info LU1 2 | Detail for listed game #2 from server LU1. |
| !join LU1 2 | Request session entry; account/NodeID verification may be required. |
| !more LU1 | Get another page from LU1's last listing. |

Example RF exchange, **simulation only**:

~~~text
Player: !servers
LU1: MQ servers: LU1 Lucca (3 games). !games LU1
PI1: MQ servers: PI1 Pisa (4 games). !games PI1

Player: !games LU1
LU1: MQ games LU1 [1/1]: 1 Dominion [PvP], 2 Ghost Signal [COOP], 3 Radio Hunt [Puzzle]. !join LU1 1
~~~

The responses should respect safe payload sizes and actual airtime constraints; if necessary send an even shorter page with a web URL or token to fetch details. Three items are a **target maximum**, not a promise that a verbose list fits within one RF payload.

## Catalog and exposure rules

A registered game can be **online**, **radio-exposed** on specific gateways, **reachable** via a gateway's reply path, or **joinable** for an authenticated player. These statuses are intentionally distinct.

Each instance has a stable public server_id and short radio alias. Its catalog chooses which games to expose on each gateway, per-channel, locale, status and rate quota. Example administrative configuration:

~~~json
{
  "server_id": "lucca-01",
  "alias": "LU1",
  "gateway_id": "lucca-gw",
  "discovery_enabled": true,
  "exposed_games": ["mesh-dominion", "ghost-signal", "radio-hunt"]
}
~~~

This is a configuration example, not a valid input to the existing API. A gateway does **not** install games; it reports observations and executes safe server-authorized replies.

## Delivery design and collision control

1. A player voluntarily sends !servers or !games on an opt-in MeshQuest channel.
2. A receiving gateway forwards the command metadata to its authenticated Core. A gateway does not autonomously broadcast the full catalog.
3. Each Core deduplicates incoming command observations across its own gateways, validates cooldown/rate limits and evaluates eligible advertised games.
4. For an instance with multiple radio gateways hearing the request, the Core selects one responder based on policy. Its Radio Scheduler queues a short direct reply when technically supported.
5. Multiple **independent** server instances cannot rely on a common central deduplicator. They must use conservative randomized response delays, per-instance throttling and deterministic priority rules to reduce simultaneous replies. Delivery is best-effort.
6. Number aliases in listings are short-lived, scoped to server, requesting NodeID and listing token/expiry. They must not be interpreted globally, nor reused after the catalog changes.

Avoid periodic full-catalog RF beacons. Use bounded replies, cooldowns, quotas and optional Web details. Do not claim ACK at the transport interface proves end-to-end delivery. Discovery should still work as a read-only service for an unpaired device; joining competitive games requires verified identity.

## Federation phases

- **Phase 1:** One Pisa Core, several gateways, distinct per-gateway advertised game lists. Test !games and !servers using a single coordination domain.
- **Phase 2:** Two independent MeshQuest Cores, each with its own server_id. They answer discovery independently; no cross-server account trust is assumed.
- **Phase 3:** Optional opt-in Internet federation directory with signed server listings, expiration and moderation. Directory availability must not be required for local radio discovery.

Gateway range does not equal physical proximity. A gateway heard through multiple relay hops may be geographically distant. Never infer an exact physical radio path from ordinary packet metadata.

## Implementation contracts

Core service: DiscoveryService; game registry: GameExposure and GatewayExposure; events: discovery.query.received and discovery.reply.queued; actions: list_servers, list_games, game_info, request_join. No game code executes inside the Berry. API endpoints and scopes are described in [GAME_API_SDK.md](GAME_API_SDK.md).

Test fixtures should cover simultaneous gateway receptions, multiple independently hosted servers, expired menu indexes, RF rate limits, message pagination, invalid NodeID, offline Core, outdated Berry, and a disabled/exhausted TX quota.
