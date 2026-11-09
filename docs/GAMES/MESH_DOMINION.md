# Mesh Dominion — proposed first competitive game on MeshQuest Engine

> Status: gameplay concept / playtest specification. **No real device hacking takes place.** All captures, malware, backdoors, firewalls, weapons and node ownership are fictional game mechanics; never modify actual devices, traffic, credentials or Meshtastic routing.

## Pitch

A persistent multiplayer territory-control game played on a virtual graph inspired by **consented** Meshtastic radio nodes and/or fictional NPC nodes. Players solve simulated cyber puzzles to capture territories, establish connected paths, farm virtual resources and defend chokepoints. Rival teams can contest control and cut **virtual game reachability**, without impacting actual radio connectivity.

This proposal grew out of a community gameplay idea from Salvo.

## Core game loop

1. Start at a home base (virtual territory associated with a registered player/team).
2. Inspect adjacent, **game-reachable** territories using your controlled graph.
3. Spend virtual energy to initiate an attack and complete a minigame.
4. On success, change only the territory's owner in the game's database.
5. Earn credits from held connected territories, upgrade attacks/defenses and defend strategic paths.

Support solo players and teams; initial playtests should use teams that can have one member. Separate **physical equipment ownership** from **in-game territory control**.

## Graph model: realistic constraints

A graph edge can be an administrator-created virtual connection or a verified-enough radio observation with provenance and an expiration. Neighbor Info and traceroute are possible **evidence inputs**, never universal proof of permanent direct links. Normal Meshtastic traffic does not disclose every relay. Geographical proximity alone is not a valid edge. A game edge must state its evidence class (simulated, reported, curated), freshness and rule that currently permits use.

Each game territory has an in-game id, optional opt-in radio NodeID link, owner (player or team), defenses, cooldown and resource production. Unregistered third-party nodes must not become automatically conquerable. NPC nodes allow a meaningful graph without deploying large amounts of hardware.

An attack is allowed only from a controlled territory adjacent to a target under current game connectivity rules. Losing an intermediate territory can disconnect the *game graph* to downstream holdings. It cannot disable radio, message relaying, other players' devices or real communications.

## Minigame classes

- Pattern decryption: reconstruct a short symbol/code sequence within a timer.
- Virtual network routing: solve a path/link puzzle while avoiding fictional defenses.
- Turn-based cyber duel: spend game energy and counters against a defender's configured virtual protections.

Difficulty varies by game tier and defenses, not by actual exploitability or device configuration. Minigame APIs report signed/validated results to the game runtime; do not accept arbitrary client-side success flags.

## Proposed economy: playtest-only numbers

| Territory class | Credits / 10 minutes | Capture difficulty |
| --- | ---: | --- |
| Common | 3 | Easy |
| Relay | 5 | Medium |
| Strategic | 8 | Hard |
| Hub | 12 | Very hard |

Balance constraints: diminishing income returns, limited offline accumulation, attack cooldowns, spawn protection, comeback mechanics and seasonal resets of virtual territory (not accounts). No pay-to-win. Rate-limit attacks and reward active, fair defense rather than 24/7 presence.

## Real-node owner benefit (virtual recovery access)

A verified owner of an **opted-in** physical node may receive a limited virtual recovery perk for that territory (for example fewer puzzle stages, with cooldown), even if an opponent controls it in-game. The perk never gives access to device administration, passwords, firmware, channel keys or radio settings. Owners can opt out; competitive rules must prevent permanent invincibility.

Deploying radio devices is never mandatory for casual participation. No encouragement to install unauthorized nodes, exceed legal RF limits, or monopolize the shared Meshtastic airtime.

## Event and state examples

Domain events: dominion.attack.started, dominion.attack.resolved, dominion.territory.captured, dominion.graph.edge_changed, dominion.income.accrued.

Game-owned state: territories, graph_edges, factions, attacks, defense_loadouts, resource_ledger, virtual_access_passes and seasons. No other game should directly write these structures.

## First Pisa playtest

Start with **3 testers, approximately 12 territories and 3 puzzle types**, mixing approved real nodes and NPC/virtual edges. First use only simulated observations, then opt-in real RF once the core event and radio scheduler contracts have been tested.

Success criteria: a player captures a node, earns currency, spends it, experiences a virtual supply-line cut, and recovers via another route or an allowed recapture. Measure onboarding time, match completion, conflict frequency and fairness; iterate balance before public deployment.
