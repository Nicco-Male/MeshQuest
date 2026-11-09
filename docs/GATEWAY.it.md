# MeshQuest Gateway Agent — Raspberry Pi Zero W (ARMv6, 32 bit)

> **Lingue:** [English](GATEWAY.md) · Italiano (questa pagina) · [Altre traduzioni](TRANSLATIONS.md)

## Regola fondamentale

**Il server MeshQuest di Pisa è l'unico motore del gioco.** Le Berry, le Raspberry Pi Zero W e i PC di amici eseguono esclusivamente `meshquest-agent` per collegare una radio Meshtastic al server. Non eseguono il Game Engine, non archiviano le classifiche, non assegnano XP e non gestiscono le missioni. Gli avamposti relay passivi non richiedono Berry, software o canale MeshQuest.

La prima versione dell'agent è **in sola lettura**: ascolta i metadati dei pacchetti del canale MeshQuest, comunica con Pisa via HTTPS usando un token specifico, invia heartbeat e conserva una piccola coda SQLite locale. Non trasmette su LoRa e non comunica testo dei messaggi, chiavi o coordinate GPS. I pacchetti grezzi **non** certificano un percorso radio e non assegnano XP.

### Requisiti Zero W 32 bit

- Python 3.9+; l'agent usa soltanto librerie standard Python, compresa SQLite.
- Per collegare la radio si installa a parte `meshtastic`, che dichiara compatibilità con Python 3.9+; le dipendenze effettive su **ARMv6 devono ancora essere verificate sulla Berry fisica**.
- Non installare FastAPI, PostgreSQL, Docker, Node.js o il backend MeshQuest sulla Berry.

## Installazione di prova

1. **Crea un gateway sul server Pisa** con l'API admin (`POST /api/v1/admin/gateways`) e conserva il token restituito. Un token per ogni radio; nessuna chiave amministrativa sul gateway. Pisa può revocare immediatamente il token con `POST /api/v1/admin/gateways/{gateway_id}/disable`.
2. Installa Raspberry Pi OS Lite 32 bit e prepara l'agent:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip
sudo mkdir -p /opt/meshquest
sudo chown "$USER":"$USER" /opt/meshquest
git clone https://github.com/Nicco-Male/MeshQuest.git /opt/meshquest
cd /opt/meshquest
python3 -m venv .venv
.venv/bin/pip install meshtastic
```

3. Salva il token in un file **privato** (permessi `chmod 600`) leggibile dall'utente che esegue il servizio. Prima controlla la comunicazione **senza accendere o modificare la radio**:

```bash
cd /opt/meshquest
python3 gateway_agent/agent.py --self-test
MESHQUEST_SERVER=https://SERVER_PISA \
MESHQUEST_TOKEN_FILE=/percorso/privato/gateway.token \
  python3 gateway_agent/agent.py --check
```

4. Per provare la ricezione via USB, indicando l'indice **locale** del canale MeshQuest:

```bash
MESHQUEST_SERVER=https://SERVER_PISA \
MESHQUEST_TOKEN_FILE=/percorso/privato/gateway.token \
  python3 gateway_agent/agent.py --serial /dev/ttyUSB0 --channel-index 1
```

In alternativa, per un nodo Meshtastic accessibile via TCP:

```bash
MESHQUEST_SERVER=https://SERVER_PISA \
MESHQUEST_TOKEN_FILE=/percorso/privato/gateway.token \
  python3 gateway_agent/agent.py --tcp 127.0.0.1 --tcp-port 4403 --channel-index 1
```

Le chiamate agli URL remoti devono usare HTTPS; HTTP è ammesso soltanto verso `localhost`/loopback. Se lo staging Render usa password, aggiungi `MESHQUEST_STAGING_PASSWORD` all'ambiente della Berry, distinta dal token gateway.

## Stato dei test

L'agent è stato testato con dati sintetici: token, heartbeat, filtraggio del canale, rifiuto MQTT, coda SQLite (massimo 256 record) e deduplicazione sul server. **Non è ancora stata verificata l'installazione su una Zero W fisica**, né la connessione con i tuoi nodi Meshtastic.

Per vedere dal server i gateway collegati usa `GET /api/v1/admin/gateways/status` autenticandoti con `X-Admin-Key`. La risposta mostra solo stato e conteggio metadati, non i token.

I comandi radio di gioco, le risposte ai giocatori e la certificazione traceroute restano da sviluppare. Il server di Pisa sarà l'unica autorità per missioni, Creator Studio, XP e classifiche.
