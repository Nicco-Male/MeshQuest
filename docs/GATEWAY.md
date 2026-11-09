# MeshQuest Gateway Agent — Raspberry Pi Zero W (32-bit ARMv6)

> **Languages:** English (this page) · [Italiano](GATEWAY.it.md) · [Other translations](TRANSLATIONS.md)

## Design contract

**The Pisa MeshQuest server is the only game authority.** Every remote Raspberry Pi Zero W, Raspberry Pi, Linux PC or Berry runs just a gateway agent. Gateways do **not** compute scores, execute quests, publish campaigns, or host the game database. Passive relay outposts need neither a Berry nor the MeshQuest channel.

The initial agent is **read-only**: it receives packet metadata on the selected local MeshQuest channel index, sends metadata via authenticated HTTPS to Pisa, and heartbeats once a minute. It never sends LoRa messages or traceroutes, never forwards decoded message text or location, and never awards XP. The server stores a minimal authenticated metadata log, **not radio route proof**. The future two-way command protocol requires separate design and firmware tests.

**Hardware compatibility:** Python 3.9+ standard library for the agent core; no FastAPI, SQLAlchemy, Node, Docker, or database-server dependency on the Raspberry. The local bounded SQLite queue is part of Python's standard library. Meshtastic's Python package requires Python >=3.9; physical installation of its transitive dependencies on ARMv6 is **not yet tested**. Check on actual Pi Zero W hardware before labeling it validated.

## 1. Provision gateway token (on Pisa)

Using the existing admin API on a development or protected server, create one gateway for each radio, e.g. `pisa-berry` and `pisa-gw`. The API returns its random token **once**; keep it outside the repository. Refer to [API.md](API.md) for the registration request.

Do not copy a Pisa admin key onto a Berry: it needs only its individual gateway token. Revoke a token centrally if a Berry is lost or compromised using `POST /api/v1/admin/gateways/{gateway_id}/disable` with `X-Admin-Key`. Token rotation by reissuing on the same gateway is still a future feature.

## 2. Prepare the Raspberry (32-bit Raspberry Pi OS Lite)

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
sudo mkdir -p /opt/meshquest /etc/meshquest
sudo chown "$USER":"$USER" /opt/meshquest
sudo chmod 700 /etc/meshquest
# Clone the PUBLIC source as the non-root user:
git clone https://github.com/Nicco-Male/MeshQuest.git /opt/meshquest
cd /opt/meshquest
python3 -m venv .venv
.venv/bin/pip install meshtastic
```

The first hardware compatibility test is whether `pip install meshtastic` and `python -c 'import meshtastic'` work on the target ARMv6 system. Do not attempt to install the full MeshQuest backend or PostgreSQL on the Pi Zero W.

Create a token file owned by the service user with `chmod 600`; use `/etc/meshquest/gateway.token` only if the service user can read it safely. No password is passed on the command line.

## 3. Verify connectivity with **no radio**

```bash
cd /opt/meshquest
python3 gateway_agent/agent.py --self-test
MESHQUEST_SERVER=https://YOUR_PISA_SERVER \
MESHQUEST_TOKEN_FILE=/path/to/private/gateway.token \
  python3 gateway_agent/agent.py --check
```

In optional cloud staging the gateway also needs `MESHQUEST_STAGING_PASSWORD`, separate from its bearer token. Prefer a private HTTPS service for real tests; the HTTP exception is limited to loopback development.

## 4. Start a read-only radio test

Confirm the **local channel index** on the radio, which may differ between gateways. With a USB device (example):

```bash
MESHQUEST_SERVER=https://YOUR_PISA_SERVER \
MESHQUEST_TOKEN_FILE=/path/to/private/gateway.token \
  python3 gateway_agent/agent.py --serial /dev/ttyUSB0 --channel-index 1
```

Or a local radio exposed through the Meshtastic TCP interface:

```bash
MESHQUEST_SERVER=https://YOUR_PISA_SERVER \
MESHQUEST_TOKEN_FILE=/path/to/private/gateway.token \
  python3 gateway_agent/agent.py --tcp 127.0.0.1 --tcp-port 4403 --channel-index 1
```

The agent never configures the radio or changes existing channel settings. Its metadata queue persists in `~/.local/state/meshquest-gateway/queue.db` (max 256 entries; oldest metadata dropped if full). This avoids high RAM usage but does **not** guarantee delivery during long outages. The central API deduplicates packet IDs per gateway and does not turn any metadata into XP.

Check the admin-only status route on Pisa: `GET /api/v1/admin/gateways/status` with `X-Admin-Key`. The endpoint never includes gateway secrets or chat contents.

## Security / operator constraints

- HTTPS is mandatory for remote servers, and gateway tokens are private per installation. Keep configuration files unreadable by other local users.
- No decoded chat text, keys, GPS coordinates, or primary-channel data should be transmitted by the agent. Select only the dedicated MeshQuest channel index.
- Any MQTT-borne packets are ignored by the agent. A received packet alone is **not** proof of a traversed relay; no radio-traceroute based scoring has been implemented.
- In closed alpha, packet metadata is retained for diagnostics; configure retention and consent policy **before** opening the service publicly.
- Avoid attaching multiple Meshtastic API clients to one serial radio. Never deploy an auto-transmitting bot on an existing busy channel without radio testing.

## Current state

- Token authentication + heartbeat, metadata-only ingestion and deduplication: implemented and tested with synthetic packets.
- Bounded on-disk gateway queue, serial/TCP receive callback and 32-bit-compatible core code: implemented; not yet verified on physical Pi Zero W.
- Server-directed game commands, radio response transport, trace route attestation: **not implemented**.
