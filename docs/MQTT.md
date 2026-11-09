# Passive MQTT transport for MeshQuest Core

> **Languages:** **English** · [Italiano](MQTT.it.md)

This optional MQTT observer runs **only on the MeshQuest server**. It requires no code or configuration changes on Raspberry Pi/Berry gateways, no extra Meshtastic TCP client, and no new radio connection. It does not publish MQTT messages, transmit LoRa packets, invoke game APIs, award points, or persist user data.

## What we verified on Pisa

Broker: `192.168.10.202:1883` (Proxmox CT 120); MeshQuest backend: CT 151 at `192.168.10.226`.

The real `msh/EU_868/1/json/NodeInfo/#` message has envelope keys `channel`, `decoded`, `from`, `gatewayId`, `id`, `sender`, `timestamp`, `to`. NodeInfo is inside `decoded.payload` (keys: `hwModel`, `id`, `longName`, `shortName`); `decoded.portnum` is an integer. The adapter handles this nested structure.

## Run the observer (opt-in, CT 151)

Do **not** blindly update a running alpha deployment. Back up CT 151 and evaluate the current GitHub/API version before pulling into `/opt/meshquest`. The optional observer runs in a separate Docker image and does not depend on the API or PostgreSQL.

1. In `/opt/meshquest/.env` (mode 0600), provide these private settings; never commit them:
   ```dotenv
   MESHQUEST_MQTT_HOST=192.168.10.202
   MESHQUEST_MQTT_PORT=1883
   MESHQUEST_MQTT_USERNAME=meshquest
   MESHQUEST_MQTT_PASSWORD=YOUR_EXISTING_BROKER_PASSWORD
   MESHQUEST_MQTT_TOPIC=msh/EU_868/1/json/#
   ```
2. Test a short bounded subscription (4 accepted messages):
   ```bash
   docker compose -f compose.yaml -f compose.mqtt.yaml run --rm --build mqtt-observer --max-events 4
   ```
   If traffic is quiet, press Ctrl+C to stop manually. The logs show only `portnum`, the retained flag and `rf_verified=false`, not message text, GPS or NodeInfo names.
3. Only if the bounded test succeeds, enable the separate background observer:
   ```bash
   docker compose -f compose.yaml -f compose.mqtt.yaml up -d --build mqtt-observer
   docker compose -f compose.yaml -f compose.mqtt.yaml logs -f --tail=30 mqtt-observer
   ```
   To stop the optional service without affecting the API or DB:
   ```bash
   docker compose -f compose.yaml -f compose.mqtt.yaml stop mqtt-observer
   ```

## Interface and safety

The adapter normalizes JSON into a transport-independent `MeshEvent` and emits it to an in-memory `EventBus` for future Core/plugin handlers. It retains gateway provenance, source node, packet ID, MQTT topic, port number, and whether the broker marked the message retained. Deduplication is bounded in memory, per topic/gateway/source/packet ID; it is not permanent across restarts. Data remains in memory unless a future explicitly designed handler persists it.

**Do not confuse MQTT with RF proof.** A broker may contain retained or Internet-forwarded messages; `rf_verified` is always false. No scoring or quest progression is performed by this observer. It has **no `publish()` call**.

**Credential note:** the broker currently uses password-file authentication, without an active ACL. Although the adapter itself never publishes, this does **not** guarantee read-only authorization at broker level. Configure least-privilege MQTT ACL separately, after auditing other clients. Port 1883 is unencrypted: restrict use to the trusted LAN/VPN (use TLS if crossing untrusted networks). Rotate weak test credentials before public deployment.
