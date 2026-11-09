# MeshQuest radio discovery and DM gameplay (design proposal)

> **Status: protocol proposal, not implemented.** The current gateway agent is
> read-only and intentionally never transmits. No MeshQuest channel discovery
> command, gateway DM response, RF pairing or command processing exists yet.

## Requirement

A roaming player with one primary Meshtastic radio (e.g. F) must discover which
MeshQuest gateways actually observed a **broadcast on the MeshQuest channel**,
without assuming a DM can reach all gateways. The backend in Pisa coordinates
gateway selection and retains game state across gateways. Only verified RF
observations qualify a gateway as a candidate; MQTT forwarding alone is not RF
reachability evidence.

## Proposed exchange

1. Player broadcasts `!mq` or `!gateways` **once on the MeshQuest channel**.
   Include an optional short random request nonce; the RF packet has its own
   sender and packet ID. The channel is for discovery, not game commands.
2. Each listening gateway with the matching configured channel submits
   `(sender_node_id, packet_id, gateway_id, rx_time, rx_snr/rssi if available)`
   to the central service over its authenticated HTTPS connection. De-duplicate
   repeated receives and enforce an expiry window. Verify port is text.
3. The central server aggregates candidates and selects **one** gateway
   that both observed the broadcast and is eligible to send a response, to
   avoid radio reply storms. Keep returned list concise (up to a few gateways).
   This is a shortlist of **observers**, not verified bidirectional links.
4. The selected gateway sends one short DM to player F, e.g.:

   `MQ: 1 Pisa (!abcd1234), 2 Poggi (!deadbeef). Rispondi !use 1`

   This requires the gateway to know F's public key from NodeInfo. If no key
   or no radio reply path is available, mark discovery unresolved; do **not**
   fall back to unrestricted broadcast replies.
5. Player replies to the responder in DM with `!use 1`. If choosing
   another gateway, the central server asks that gateway to initiate its own
   DM handshake; a gateway must never claim success until the DM exchange
   with that gateway succeeds. Subsequent commands target the selected
   gateway's NodeID (one-to-one DM), e.g. `!help`, `!games`,
   `!play salvo`, `!scan`, `!status`, `!exit`.
6. Gateway forwards authenticated-source packet metadata and DM content to
   the central service over HTTPS. The central service owns session, gameplay
   and reward validation. A command reply is sent as a DM by the **same**
   selected gateway, with per-player idempotency/rate limiting and compact
   payloads. Re-discovery is possible after moving out of range.

## RF and security boundaries

- A DM is addressed to exactly one node and encrypted for that node;
  other nodes may relay it but **cannot read it or respond as independent
  MeshQuest gateways**. Multi-gateway discovery therefore MUST use a channel
  broadcast, not a DM.
- Do not assume the channel index is the same on every device. A gateway
  needs its **locally configured** MeshQuest secondary-channel index and
  matching key; no other channels should invoke MeshQuest.
- Direct messages require public-key availability. ACK or a gateway observing
  a broadcast is not proof of end-to-end bidirectional gameplay; use a
  DM-level request/reply handshake.
- Ignore duplicates/replays and restrict broadcast discovery frequency;
  one responder per discovery cycle to avoid multiple DM storms. Short
  messages are important for LoRa airtime.
- Do not grant node ownership or points from a claimed source NodeID until
  account-to-node pairing and appropriate replay/authorization checks exist.
- Do not treat MQTT observations as evidence of LoRa reachability. Track RF
  and MQTT receipt separately. Local gateway's received packet sender/channel
  data still requires conservative trust assumptions.
- The gateway may decrypt Meshtastic DMs in order to forward application
  commands; this is *not* end-to-end encryption to the Pisa game server.
  Use TLS and scoped gateway tokens for the HTTP hop.
- Initial implementation should be behind an explicit RF-TX opt-in flag;
  keep the existing read-only agent the safe default.

## Pilot acceptance checks

- Two gateways receiving the same `!gateways` broadcast yield **one**
  coordinated DM response with a list of both observer IDs.
- An unrelated channel message generates zero MeshQuest events and replies.
- Duplicate delivery / MQTT-only copies cannot inflate candidates or responses.
- A gateway without the player's public key is not chosen as the DM responder.
- DM handshake to chosen gateway succeeds; missing ACK/reply fails closed.
- `!games` and `!play salvo` work only after handshake on the selected DM.
- Moving across coverage areas preserves the centrally stored game profile.
- Multiple player requests are independently deduplicated and rate-limited.

## Relevant upstream documentation

- https://meshtastic.org/docs/software/android/user/messages-and-channels/
- https://meshtastic.org/docs/getting-started/joining-your-local-mesh/
- https://python.meshtastic.org/mesh_interface.html
