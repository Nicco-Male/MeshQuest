# Trasporto MQTT passivo per MeshQuest Core

> **Lingue:** [English](MQTT.md) · **Italiano**

Questo observer MQTT è **opzionale e gira soltanto sul server MeshQuest**. Nessuna installazione sulle Berry di produzione, nessun client TCP Meshtastic aggiuntivo, nessun comando o trasmissione LoRa. Non pubblica su MQTT, non modifica il database né assegna XP.

## Risultati verificati a Pisa

Broker: `192.168.10.202:1883` (CT 120); server MeshQuest: CT 151, `192.168.10.226`.

L'envelope JSON contiene `channel`, `decoded`, `from`, `gatewayId`, `id`, `sender`, `timestamp`, `to`. I dati NodeInfo sono in `decoded.payload` (`hwModel`, `id`, `longName`, `shortName`), mentre `decoded.portnum` è intero.

## Avvio controllato sul CT 151

**Non aggiornare automaticamente il backend già funzionante.** Prima di fare pull di GitHub in `/opt/meshquest`, effettua un backup del CT 151 e verifica le differenze tra le versioni delle API. L'observer usa un'immagine Docker separata e non dipende né dalle API né da PostgreSQL.

1. Nel file privato `/opt/meshquest/.env` (permessi 0600) configura:
   ```dotenv
   MESHQUEST_MQTT_HOST=192.168.10.202
   MESHQUEST_MQTT_PORT=1883
   MESHQUEST_MQTT_USERNAME=meshquest
   MESHQUEST_MQTT_PASSWORD=PASSWORD_GIA_USATA_SUL_BROKER
   MESHQUEST_MQTT_TOPIC=msh/EU_868/1/json/#
   ```
   Non caricare mai il file `.env` su GitHub.
2. Avvia una sottoscrizione limitata a 4 eventi accettati:
   ```bash
   docker compose -f compose.yaml -f compose.mqtt.yaml run --rm --build mqtt-observer --max-events 4
   ```
   Se non arrivano nuovi messaggi, interrompi con Ctrl+C. I log contengono soltanto il portnum, il flag retained e `rf_verified=false`; nessun testo, posizione GPS o nome dei nodi.
3. Dopo il test, se vuoi lasciare il servizio attivo:
   ```bash
   docker compose -f compose.yaml -f compose.mqtt.yaml up -d --build mqtt-observer
   docker compose -f compose.yaml -f compose.mqtt.yaml logs -f --tail=30 mqtt-observer
   ```
   Per arrestarlo senza toccare API e database:
   ```bash
   docker compose -f compose.yaml -f compose.mqtt.yaml stop mqtt-observer
   ```

## Contratto Core e sicurezza

`MeshEvent` è il formato indipendente dal trasporto, distribuito in memoria tramite `EventBus`. L'adapter conserva in memoria provenienza del gateway, NodeID sorgente, ID pacchetto, topic, portnum e flag retained. La deduplicazione è limitata in RAM e riparte a ogni avvio. Nessun handler salva i dati nel database in questa fase.

**Un messaggio MQTT non è una prova di un percorso LoRa.** Può essere retained oppure inoltrato da Internet. `rf_verified` rimane sempre false; gameplay, punteggi e missioni sono esclusi dall'adapter.

**Nota sulle credenziali:** attualmente Mosquitto usa autenticazione tramite password file, ma non risultano ACL attive. L'adapter non pubblica, tuttavia non è un account con permessi broker realmente di sola lettura. Prima dell'uso pubblico serviranno ACL dedicate, dopo avere verificato gli altri client. La porta 1883 non cifra il traffico: usala solo su LAN/VPN affidabile oppure imposta TLS.
