# Pilot MeshQuest: MQTT receive → Navacchio DM via MeshMonitor v1

**Status:** implemented on `feature/salvo-poc` and unit-tested, not yet run on
your live broker from this repository. TX is off unless explicitly enabled.

## Verified manually on 2026-11-10

- Incoming MeshQuest command `!gateways` appeared as a JSON text payload
  via MQTT under `msh/EU_868/IT/Tuscany/Pisa/2/json/MeshQuest/!eb4a6925`.
- Source `Navacchio` is `!eb4a6925` and has MeshMonitor source UUID
  `1b7e5af4-b3f0-4dba-83fc-9a9517abb262`.
- A MeshMonitor **v1** POST to `/api/v1/sources/<uuid>/messages` with
  `{"toNodeId":"!e9a04b31","text":"MeshQuest: test DM 003"}`
  returned HTTP 201 / `deliveryState: pending`; the user confirmed real
  receipt on personal radio `!e9a04b31`.
- Legacy `/api/messages/send` failed with HTTP 403. Use the v1 source-scoped
  endpoint. **No additional channel named `mqtt` is needed for the
  MeshMonitor API transport.**

## Installation (inside CT 151, not on the LoRa gateway)

```bash
git clone --depth 1 -b feature/salvo-poc \
  https://github.com/Nicco-Male/MeshQuest.git /opt/meshquest-radio-pilot
python3 -m venv /opt/meshquest-radio-pilot/.venv
/opt/meshquest-radio-pilot/.venv/bin/pip install 'paho-mqtt>=2,<3'
cd /opt/meshquest-radio-pilot
```

Use environment variables for credentials. Never commit API tokens or
passwords. The example below assumes `MQPASS` and `MM_TOKEN` have already
been entered securely in this shell, e.g. with `read -rsp`. No script clears
those shell variables.

### First: receive only

```bash
MESHQUEST_MQTT_USER=meshquest MESHQUEST_MQTT_PASSWORD="$MQPASS" \
  .venv/bin/python -m gateway_agent.mqtt_pilot \
  --broker 192.168.10.202 --port 1883 \
  --root msh/EU_868 \
  --tx-node-id '!eb4a6925' \
  --allowed-player-node-id '!e9a04b31' \
  --tx-transport meshmonitor
```

Send `!gateways` *once* from the personal radio on channel MeshQuest.
Expect `RX MeshQuest ... command=!gateways`, then an
`[RX-ONLY] would send DM ...` log. MQTT publishers reporting the
same original packet ID are deduplicated.

### Second: enable ONE real Navacchio DM

```bash
MM_TOKEN="$MM_TOKEN" MESHQUEST_MQTT_USER=meshquest MESHQUEST_MQTT_PASSWORD="$MQPASS" \
  .venv/bin/python -m gateway_agent.mqtt_pilot \
  --broker 192.168.10.202 --port 1883 \
  --root msh/EU_868 \
  --tx-node-id '!eb4a6925' \
  --allowed-player-node-id '!e9a04b31' \
  --tx-transport meshmonitor \
  --meshmonitor-url http://192.168.10.39:3001 \
  --meshmonitor-source-id 1b7e5af4-b3f0-4dba-83fc-9a9517abb262 \
  --allow-http-lan --enable-tx
```

Send one *new* `!gateways` on MeshQuest. A successful API request
logs `DM requested via MeshMonitor ...`. Validate the **radio arrival** on
the player's DM screen. Stop with Ctrl+C. Do not run multiple active bot
instances: the current PoC has only **in-process** de-duplication and rate
limiting.

**Security notes:** Explicit `--allow-http-lan` permits sending a Bearer
token over the private LAN in plaintext. Prefer HTTPS before a public
deployment. The JSON MQTT record does not cryptographically prove that a
gateway received the packet via RF; do not score RF proof from this pilot.
The sender allowlist is a pilot guard, not anti-spoofing authentication.

## Known limitations

- The `e` topics are detected but not decoded; the command requires a
  companion `json` topic from an eligible publisher.
- DM-originated command receipts may be reported under a different topic
  (such as PKI), not under the MeshQuest channel; discovery replies are the
  first live acceptance test. DM gameplay must be independently verified.
- MeshMonitor HTTP 201 means a **send was requested**, not a radio ACK.
- No player/account pairing, XP changes, production command execution,
  persistent queue or centrally coordinated multi-server gateway arbitration.
