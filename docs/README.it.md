# MeshQuest — Guida italiana

> **Lingue / Languages:** [🇬🇧 English (documentazione principale)](../README.md) · **🇮🇹 Italiano** · [🌐 Traduzioni](TRANSLATIONS.md)

**MeshQuest** è un progetto open source sperimentale che unisce esplorazione radio Meshtastic e meccaniche RPG. La base implementata comprende API, database, registrazione amministrativa dei nodi, osservazioni dei percorsi, punti esperienza e classifica.

**Stato: v0.2.0-alpha.** La connessione radio Meshtastic reale, i traceroute automatici, l'autenticazione degli utenti sul sito e i comandi radio **non sono ancora implementati**. Non pubblicare questa versione su Internet come servizio di gioco.

## Architettura

- **Server centrale:** gestisce identità, avamposti, eventi, punti, classifiche e sito Web. L'istanza principale è prevista a Pisa.
- **Gateway radio:** un computer in una postazione dotata di radio Meshtastic, che in futuro invierà osservazioni al server via HTTPS.
- **Avamposto:** un normale nodo Meshtastic remoto registrato per NodeID. Non richiede Raspberry, PC, Internet, token software né necessariamente il canale MeshQuest.
- **Giocatore:** un nodo con canale MeshQuest; in futuro l'account Web sarà collegato al proprio NodeID con una verifica radio.

Il canale secondario MeshQuest separa logicamente il gioco, ma non riserva banda radio. I relay devono essere compatibili per regione, preset e frequency slot e devono consentire la ritrasmissione.

## Regola delle conquiste

I messaggi normali non indicano l'elenco completo dei nodi attraversati. Un traceroute è una **nuova misura**, il cui percorso può essere diverso da quello del messaggio di gioco. I nodi che non conoscono la chiave del canale possono comunque inoltrare, ma non sempre essere identificati nel traceroute.

Nel prototipo un gateway autorizzato segnala un traceroute diretto al giocatore e distingue `route_to_player` (andata) e `route_to_gateway` (ritorno). Un avamposto approvato ed **esplicitamente identificato** nel ritorno vale **50 XP, una sola volta per giocatore**. Gli hop sconosciuti non danno punti individuali. La prova si basa sulla fiducia nel gateway; non è una certificazione antifrode.

## Avvio per sviluppo

Prerequisiti: Python 3.11+ e Git.

```bash
git clone https://github.com/Nicco-Male/MeshQuest.git
cd MeshQuest
python3 -m venv .venv
source .venv/bin/activate
pip install '.[test]'
export MESHQUEST_ADMIN_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m meshquest
```

Apri `http://127.0.0.1:8000/` per la pagina della classifica o `http://127.0.0.1:8000/docs` per le API. Per i test automatici: `pytest -q`.

Per Docker Compose: copia `.env.example` in `.env`, cambia **entrambe** le password d'esempio e usa `docker compose up --build -d`. L'API risponde solo localmente su `127.0.0.1:8765`.

## Stato delle funzionalità

| Funzione | Stato |
| --- | --- |
| FastAPI, SQLite/PostgreSQL | Prototipo funzionante |
| Registrazione amministrativa di giocatori, gateway e avamposti | Implementata |
| Approvazione avamposti e deduplicazione eventi | Implementata |
| XP per avamposti unici, classifica totale/mensile | Implementata |
| Homepage in inglese e italiano | Implementata |
| Missioni progressive, livelli, capitoli e profilo giocatore | Implementati in modalità simulata |
| Traceroute radio, comandi `!quest`/`!checkin`, verifica proprietà NodeID | Da sviluppare |
| Account utente pubblici e registrazione autonoma avamposti | Da sviluppare |

Le chiamate di esempio alle API utilizzano **osservazioni simulate**, non prove radio effettive. La versione attuale non va presentata come un sistema che certifica i percorsi.

Ulteriori dettagli: [API](API.md) · [Architettura](ARCHITECTURE.md) · [Traduzioni](TRANSLATIONS.md).

**Licenza:** MIT. Progetto indipendente e non affiliato a Meshtastic.

## Prima partita simulata

Per provare tre missioni e lo sblocco dei capitoli usando il vero backend, senza trasmissioni radio:

```bash
python scripts/demo_game.py --lang it
```

La **[guida al gameplay](GAMEPLAY.it.md)** ([English](GAMEPLAY.md)) descrive regole, comandi previsti e limiti dei traceroute.


## Avventure create dalla comunità (v0.3.0-alpha)

I gateway MeshQuest con un computer (Raspberry, Berry, PC) possono proporre **capitoli della storia principale**, **missioni secondarie** e **DLC**. Pisa approva le proposte prima della pubblicazione. Gli avamposti relay passivi non devono installare nulla.

Consulta la **[guida italiana per creare e proporre campagne](CONTENT_PACKS.it.md)** e il **[DLC di esempio](../examples/tuscany-lost-signal.json)**. Il sistema permette per ora solo anteprima e moderazione: le missioni personalizzate non assegnano ancora XP e non sono giocabili via radio.

## Gateway leggero per Berry Zero W (32 bit)

Il server Pisa gestisce tutto il gameplay, inclusi Creator Studio, missioni, XP e classifiche. Ogni Berry/PC collega esclusivamente una radio Meshtastic al server con un token individuale. L'agent (`gateway_agent/agent.py`) utilizza Python 3.9+ e soltanto librerie standard per HTTPS, coda SQLite e autenticazione; il pacchetto `meshtastic` è necessario solo per l'accesso radio. La compatibilità ARMv6 completa deve ancora essere verificata sul dispositivo fisico.

[Guida di installazione gateway in italiano](GATEWAY.it.md) · [Creator Studio / server locale](../web/creator.html).
