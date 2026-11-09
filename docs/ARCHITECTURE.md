# MeshQuest architecture and RF assumptions

> [English](../README.md) · [Italiano](README.it.md) · [Translations](TRANSLATIONS.md)

## Roles

1. **Central server:** authoritative game state, PostgreSQL, public read-only leaderboard, authenticated observation API.
2. **Radio gateway:** Meshtastic radio attached to a host, envisioned to run a future bridge that collects traceroute results and forwards them via authenticated HTTPS.
3. **Outpost:** any remote registered relay node; no software, Internet or game channel required. The outpost must be identified in a traceroute to be credited.
4. **Player:** participates via a Meshtastic radio on a dedicated MeshQuest application channel.

## RF verification design

- Radio gateways initiate directed Meshtastic traceroutes to player nodes on the configured channel, subject to firmware limits and airtime policies.
- Route evidence is a snapshot of the specific probe, **not a recording of an earlier chat or game message's exact path**.
- `route_to_player` and `route_to_gateway` describe the outgoing and return intermediate node IDs as reported by a trusted gateway. Different directions may take different routes.
- Nodes lacking the relevant channel key may relay the probe, but do not reveal their IDs through encrypted traceroute; unknown hops are counted separately, never arbitrarily assigned an identity.
- Scoring in v0.1: approved NodeID found in `route_to_gateway`, uniquely per player/outpost, yields 50 XP. Other observations are logged without awarding specific outpost credit.
- A valid receipt and even an authenticated gateway report cannot ensure absence of spoofing; the server only authenticates the gateway's API token. No cryptographic attestation of RF measurements exists yet.
- Traceroute rate limiting is essential. Do not trigger one for every casual message or continuously poll the radio.

## Privacy/security work required BEFORE opening registration

- User logins and verifiable Meshtastic NodeID ownership pairing (current alpha is admin-only).
- Outpost ownership claims, moderation and revocation.
- Gateway token revocation and rotation endpoints, per-gateway scope and quotas.
- Public API protection and rate limits, server-side event freshness checks, audit logs and HTTPS only.
- Database migrations, production observability, backups, CI integration tests and multi-worker transaction safety.
- Threat model for compromised gateways, route falsification and leaderboard abuse.

## Standards and official references

- [Meshtastic encryption and rebroadcast](https://meshtastic.org/docs/overview/encryption/)
- [Meshtastic configuration tips](https://meshtastic.org/docs/configuration/tips/)
- [Meshtastic Python CLI traceroute](https://meshtastic.org/docs/software/python/cli/)
- [Meshtastic Python API](https://python.meshtastic.org/)

The official protocol and firmware versions must be checked against hardware during integration. This repository is not an official Meshtastic component.


## Game Masters / community content (v0.3.0-alpha)

A radio gateway with a host computer may also propose story content, without running a separate authoritative game server. It sends a validated declarative pack to the Pisa API using its **existing gateway bearer token**. Content is stored as pending; the Pisa administrator reviews and publishes it. Public readers see only published packages. `main`, `side` and `dlc` are distinct campaign categories; gateway users cannot directly change the canonical narrative or the scoreboard. No custom script execution is permitted. Mission completion and XP award integration are still future work. See [Creator Studio](CONTENT_PACKS.md) / [Italiano](CONTENT_PACKS.it.md).
