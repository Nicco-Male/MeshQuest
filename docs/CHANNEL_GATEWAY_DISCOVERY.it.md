# Discovery broadcast sul canale MeshQuest — più gateway

**Stato:** implementato come pilot centrale in `gateway_agent/channel_discovery.py`.
Non serve collegarsi direttamente alla porta TCP 4403: MeshMonitor è già connesso
alle radio `meshtasticd` sulle Berry/HAT LoRa.

## Protocollo richiesto

Il giocatore invia UNA volta `!gateways` sul canale radio **MeshQuest**.
Ogni sorgente `meshtastic_tcp` collegata a MeshMonitor, con canale secondario
configurato esattamente `MeshQuest`, esamina esclusivamente i messaggi
ricevuti nel proprio archivio **per sorgente**.

Se una sorgente ha osservato un nuovo comando (non un'eco MQTT con
`viaMqtt=true`, con dati RF RSSI/SNR) trasmette essa stessa un piccolo
messaggio in **broadcast sullo stesso canale MeshQuest**:

```text
!gateways
MQ RX Navacchio
MQ RX Pisa
```

Questi due messaggi sono esempi: la risposta di Pisa compare **solo**
se la sua radio ha davvero registrato il comando con metadati RF, e se la
configurazione MeshQuest sulla sorgente è valida. Non viene fabbricata una
lista di risposte per gateway che non hanno ricevuto.

L'utente vede nella propria radio quali trasmettitori riesce a ricevere
in risposta. I NodeID rimangono interni al server e non devono essere
digitati. RSSI/SNR non provano che F e il gateway siano collegati
direttamente **a un solo hop**: in Meshtastic esistono relay.

### Selezione per nome e primo DM

Il giocatore invia **sullo stesso canale**:

```text
!use navacchio
```

Il server risolve il nome esatto (ignorando maiuscole e minuscole).
Se due sorgenti hanno lo stesso nome, non viene inviato alcun DM.
Il gateway scelto deve avere ricevuto via radio **sia** `!gateways`
(negli ultimi 120 secondi) **sia** `!use navacchio`.
Solo allora Navacchio invia il primo messaggio **diretto**:

```text
MeshQuest connesso a Navacchio. Comandi: !help, !games
```

Per Pisa il comando è `!use pisa`, con risposta privata da Pisa.
Il cooldown del primo DM è di 15 secondi per giocatore e gateway.

### Comandi nei DM dopo la selezione

Una volta ricevuto il primo DM, il giocatore risponde **nella stessa chat
privata con il gateway selezionato**, per esempio:

```text
!help
MQ Navacchio: !games lista giochi; !play salvo demo; !status; !exit

!games
MQ giochi: Salvo (demo), Exploration (demo). Usa !play salvo

!play salvo
Salvo demo disponibile: gameplay radio e punti non ancora attivi.
```

Il bot esegue un polling dei DM dalla stessa sorgente con
`GET /api/v1/sources/<uuid>/messages?channel=-1&limit=100` e usa
`toNodeId` nell'API v1 per ogni risposta. Non apre connessioni TCP 4403.

Sono supportati anche `!menu`, `!listgame`, `!join salvo`,
`!status` e `!exit`. Sessioni in memoria per 30 minuti dall'ultimo
comando riconosciuto; `!exit` le chiude. Non vengono assegnati XP
o crediti, non viene avviata una partita reale, né è ancora attiva
l'identificazione dell'account: questo è il menu **demo radio**.

La prima scansione all'avvio ignora i DM storici; dopo l'aggiornamento
occorre quindi effettuare di nuovo `!gateways` e `!use navacchio`
prima di provare `!help` o `!games`. I comandi vengono accettati
solo dal NodeID che ha completato la selezione e sulla radio
selezionata. Le risposte sono distanziate di almeno 2 secondi
per sessione quando arrivano più comandi contemporaneamente.


## Esecuzione sul CT 151

Sul container `meshquest`, dove il repository è già clonato:

```bash
cd /opt/meshquest-radio-pilot
git pull --ff-only
export MM_TOKEN
python3 -m gateway_agent.channel_discovery \
  --meshmonitor-url http://192.168.10.39:3001 \
  --allow-http-lan
```

**La trasmissione è attiva per questa esecuzione** (l'opzione
`--dry-run` è disponibile se si vuole solo osservare). La variabile
`MM_TOKEN` deve già contenere il token e deve essere esportata:
`export MM_TOKEN` non ne cancella il valore.

Il pilot autodetecta sorgenti MeshMonitor abilitate e connesse di tipo
`meshtastic_tcp` su cui esiste un unico canale attivo con nome `MeshQuest`.
Legge l'indice locale per sorgente (non presuppone che sia uguale su tutte).
Non usa altre radio e non modifica i canali.

Attendi che compaia `Watching ... (history ignored)` per tutti i gateway.
A quel punto manda `!gateways` una sola volta sul canale MeshQuest da F.
Dopo aver ricevuto le risposte manda `!use navacchio` sul canale.
Verifica il primo DM proveniente da Navacchio sul nodo F e invia
`!help` **in DM**, non sul canale.

Se vuoi limitare il primo test a Navacchio e Pisa:

```bash
python3 -m gateway_agent.channel_discovery \
  --meshmonitor-url http://192.168.10.39:3001 --allow-http-lan \
  --only-sources 1b7e5af4-b3f0-4dba-83fc-9a9517abb262,627bca65-825a-469b-935a-64579e66dc66
```

Se vuoi limitare anche chi può provocare risposte, aggiungi
`--allowed-player-node-id '!e9a04b31'`.

Ferma il processo con Ctrl+C. Evita di avviare due copie: deduplicazione,
blocco anti-replay e cooldown (15 secondi per gateway/giocatore) sono per
processo, non distribuiti.

### Risoluzione problemi

- Non appare `Watching`: verifica che `MM_TOKEN` sia esportato, che la
  sorgente sia connessa e che il canale abbia nome esatto `MeshQuest`.
- Non arriva nessuna risposta: controlla il log. Il pilot considera solo
  messaggi **nuovi** dopo l'avvio, ricevuti via radio con RSSI o SNR,
  e scarta `viaMqtt=true`. Il precedente traffico MQTT non basta.
- Appare `TX accepted`: MeshMonitor ha accettato il POST v1, ma la
  consegna LoRa si verifica **solo osservando il messaggio sul nodo F**.

## API interne

Lettura sorgenti e radio:
`GET /api/v1/sources`,
`GET /api/v1/sources/<uuid>/status`,
`GET /api/v1/sources/<uuid>/channels`,
`GET /api/v1/sources/<uuid>/messages?channel=N&limit=100`.

Trasmissione del gateway specifico:
`POST /api/v1/sources/<uuid>/messages` con
`{"channel":N,"text":"MQ RX <name>"}`.

Primo DM e successive risposte in privato:
`POST /api/v1/sources/<uuid>/messages` con
`{"toNodeId":"<player nodeid>","text":"MeshQuest connesso a <name>..."}`.
Il NodeID appare soltanto nel payload interno della richiesta API.

Il testo broadcast non contiene `toNodeId` (quel campo serve invece
per il DM v1). Non viene usato l'endpoint legacy `/api/messages/send`.

## Limiti e sicurezza

- Trasmissione limitata a un piccolo messaggio per gateway e richiesta,
  con cooldown e ritardi sfalsati per ridurre collisioni radio.
- Autenticazione via token MeshMonitor. L'opzione `--allow-http-lan` autorizza
  l'uso del token su HTTP in chiaro **solo** a un IP privato: preferire
  HTTPS in futuro e non pubblicare il token.
- Fonte dell'osservazione: record del MeshMonitor associato a ciascuna
  radio TCP. Questo prova la registrazione di un ricevimento con
  RSSI/SNR, non identifica in modo crittografico la sorgente aerea.
- Nessun punto, account o stato di gioco viene modificato.
- L'implementazione è un pilot del server centrale. In produzione,
  le gateway Berry dovranno riportare eventi RX al server MeshQuest con
  token proprio; il gameplay dopo il primo DM è uno step separato.
