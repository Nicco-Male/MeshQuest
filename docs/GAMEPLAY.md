# MeshQuest gameplay · First playable loop

> **Languages:** English (this page) · [Italiano](GAMEPLAY.it.md) · [Other translations](TRANSLATIONS.md)

**Status:** v0.2.0-alpha contains a working *simulated* progression flow, three derived quests, narrative unlocks and an API/profile viewer. **The live radio gateway, `!checkin` parser, player self-registration, and automatic Meshtastic traceroute are still missing.**

## One session — intended live experience

1. The player joins the secondary `MeshQuest` channel and links their radio NodeID to an account (future pairing step).
2. The player explores with a normal Meshtastic radio. No GPS is required.
3. `!checkin` requests a bounded radio measurement from an authorized gateway. The gateway must be reachable via LoRa; Internet-only MQTT delivery cannot satisfy the RF route challenge.
4. The gateway collects a **new Meshtastic traceroute**, reports *outgoing* and *return* paths separately and sends its observation to the central server via authenticated HTTPS.
5. The central server deduplicates the event, credits a newly identified/approved outpost **once per player**, updates quests and levels, and later sends a concise reply through a gateway. The RF command and reply pipeline is not yet implemented.

An ordinary relay/outpost **does not need the MeshQuest channel, a computer or Internet** to forward packets if radio settings and rebroadcast policy allow it. However, a relay without the relevant channel key typically will **not reveal its NodeID** in the traceroute and may appear as an unknown hop. It cannot be credited as a specific outpost without additional trustworthy evidence. Traceroute measures the path of the probe, *not* the exact path of the preceding game message; the outgoing and returning paths may also differ.

## First season — rules implemented in the prototype

| Goal | How to qualify | Reward |
|---|---|---|
| First Echo | First unique, approved, identified outpost on return route | 50 XP from discovery |
| The Cartographer | Two different unique outposts discovered | Chapter II unlocked |
| The Lost Archive | Three different unique outposts discovered | Chapter III unlocked |

Each new unique qualifying outpost awards 50 XP. Quest completion unlocks narrative content; it does **not** award additional XP. The same NodeID receives no additional XP for repeating observations from the same outpost. Unknown hops and unapproved outposts award no XP. Level thresholds start at 0 / 100 / 250 / 450 / 700 XP. The current public leaderboard ranks by discovered outposts' XP; its month view is a calendar-month snapshot, not a complete seasonal system.

**This is prototype balancing, not a claim that every outpost can be identified**. A gateway's observation is an attestation, not independent proof: gateway compromise, malicious ownership claims and duplicated identities require a future trust model.

## Run the simulated round (no radio needed)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install '.[test]'
python scripts/demo_game.py --lang en
python -m pytest -q
```

The demo creates a temporary database, registers a dummy explorer and three dummy outposts, submits three deliberately synthetic traceroute-shaped reports through the real API, and shows XP, quests and levels. The temporary DB is deleted on exit. **It does not send LoRa packets.**

To explore the same read-only rules on the API run `python -m meshquest` and visit:

- `/api/v1/game/rules?lang=en` and `?lang=it` — missions, chapters, scoring policy.
- `/api/v1/players/!aabbccdd/profile?lang=it` — only if that node was registered in your development database.
- `/` — leaderboard, outposts, mission board and profile viewer.

## RF traffic budget (design target, not implemented)

`!checkin` should be a direct message, not a channel-wide broadcast. Suggested starting budget: one request per player per 10 minutes; only one in-flight measurement per radio gateway; obey Meshtastic firmware traceroute minimum intervals (30 seconds on current app documentation), and never repeatedly poll idle nodes. Each completed measurement creates at most one short radio reply. Queue or decline excess requests rather than increasing hop limits to chase a mission.

## Next implementation milestone

Build a read-only **Meshtastic serial/TCP adapter** that captures real packets and route metadata into fixtures, then test parser accuracy against specific firmware versions before enabling scoring from live traffic. Do not attach an untested game bot to the public ToscoLig channel.
