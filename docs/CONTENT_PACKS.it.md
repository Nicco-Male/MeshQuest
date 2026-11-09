# MeshQuest Creator Studio: campagne e missioni della comunità

> **Lingue:** [English](CONTENT_PACKS.md) · Italiano (questa pagina) · [Traduzioni](TRANSLATIONS.md)

**Stato: v0.3.0-alpha — proposte, moderazione, salvataggio e anteprima pubblica dei pacchetti sono implementati. Non sono ancora implementati l'esecuzione delle missioni via LoRa, il completamento delle quest o l'assegnazione degli XP dei DLC.** Non pubblicare direttamente su Internet questa API sperimentale.

## Ruoli

- **Server centrale Pisa:** conserva campagna ufficiale, progresso dei giocatori, moderazione e classifiche. Nell'alpha è l'unico che può pubblicare contenuti.
- **Gateway Game Master:** un computer, Raspberry o Berry con una radio e un token MeshQuest può proporre campagne principali, missioni secondarie e DLC. Non diventa amministratore del server.
- **Avamposto radio:** un normale nodo Meshtastic che fa da relay. Non ha bisogno di computer, Internet, software o canale MeshQuest e non può caricare campagne soltanto perché inoltra pacchetti.
- **Giocatore:** in una fase successiva potrà avviare un'avventura collegandosi via LoRa al gateway. Per adesso i pacchetti sono consultabili dal sito come anteprime.

## Tipi di contenuto

| Tipo | Ruolo | Pubblicazione |
|---|---|---|
| `main` | Capitoli proposti per la storia globale | Approvazione Pisa obbligatoria |
| `side` | Missioni opzionali create dai gateway regionali | Approvazione Pisa nell'alpha |
| `dlc` | Espansioni autonome o stagionali con più capitoli | Approvazione Pisa nell'alpha |

Ogni pacchetto contiene titolo e riassunto in inglese/italiano, da 1 a 8 capitoli e da 1 a 12 missioni per capitolo. Le missioni descrivono un obiettivo tra `reach_gateway`, `discover_outpost`, `discover_count` e `solve_riddle`.

- `reach_gateway`: raggiungi via radio un gateway specifico (la prova via Internet non sarà sufficiente).
- `discover_outpost`: scopri un NodeID approvato e identificato in una misura traceroute valida.
- `discover_count`: raggiungi un numero definito di avamposti unici.
- `solve_riddle`: risolvi un enigma; il sistema di verifica sarà sviluppato successivamente. Non inserire la risposta segreta nel JSON pubblico.

Gli XP indicati da un autore (`suggested_xp`, massimo 50 per missione) sono **solo proposte**, non ricompense attive. Pubblicare un DLC non modifica la classifica; le missioni comunitarie non sono ancora giocabili. Ogni testo richiede per ora sia la versione inglese che quella italiana.

## Procedura di pubblicazione

1. Un amministratore registra il gateway e consegna il token personale. L'autoregistrazione dal sito verrà in seguito.
2. Il Game Master invia il proprio JSON a `POST /api/v1/gateway/content-packs` usando `Authorization: Bearer $GATEWAY_TOKEN`.
3. Pisa consulta `GET /api/v1/admin/content-packs?pack_status=pending` usando `X-Admin-Key`, approva con `POST /api/v1/admin/content-packs/{slug}/publish` oppure rifiuta con `/reject`.
4. Le avventure pubblicate compaiono in `GET /api/v1/content-packs?lang=it` e `GET /api/v1/content-packs/{slug}?lang=it`; quelle in attesa o respinte restano private. L'autore consulta i propri stati via `GET /api/v1/gateway/content-packs`.

Un pacchetto di esempio è disponibile in [`examples/tuscany-lost-signal.json`](../examples/tuscany-lost-signal.json). Da una installazione **locale di sviluppo**, con gateway registrato:

```bash
curl -fsS -X POST http://127.0.0.1:8000/api/v1/gateway/content-packs \
  -H "Authorization: Bearer $GATEWAY_TOKEN" \
  -H 'Content-Type: application/json' \
  --data-binary @examples/tuscany-lost-signal.json
```

Un pacchetto `main` approvato viene pubblicato come contenuto della storia principale, ma **non si collega ancora ai capitoli base o agli sblocchi automatici**. Gli identificativi dei pacchetti (`slug`) sono globalmente unici e i contenuti inviati sono immutabili in questa alpha. Per correggere una proposta occorre inviarne una nuova con altro slug; versioni modificabili, ritiro dei DLC e traduzioni aggiuntive verranno in seguito.

## Gameplay futuro e sicurezza

Un giocatore potrà affrontare missioni di gateway diversi, mantenendo i progressi sul server centrale. Il completamento radio richiederà prove RF appena osservate, deduplicazione e limiti di traffico: un semplice click sul sito non basta. Gli hop sconosciuti non vengono attribuiti a NodeID precisi. Enigmi e premi richiederanno controlli lato server, senza includere risposte segrete nel pacchetto scaricabile. Un gateway compromesso potrebbe comunque falsificare un report e il sistema dovrà tenerne conto prima di abilitare premi ufficiali.

Il canale `MeshQuest` rimane previsto per giocatori e gateway radio, **non obbligatorio per i relay passivi**. Nessun contenuto può far eseguire script arbitrari sui gateway.
