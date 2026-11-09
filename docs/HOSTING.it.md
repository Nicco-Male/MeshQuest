# MeshQuest — server cloud di test (Render + Neon)

> **Lingue:** [English](HOSTING.md) · **Italiano (questa pagina)** · [Traduzioni](TRANSLATIONS.md)

**Stato:** configurazione pronta, **nessun server cloud ancora attivato**. È uno staging per alpha chiusa, protetto da password; non è una produzione pubblica.

## Perché GitHub non basta?

GitHub Pages pubblica solo file statici. I runner di Actions terminano a fine job, mentre Codespaces si arrestano. Per l'API dinamica di gioco serve un servizio esterno.

Proposta: repository pubblica e test su **GitHub**, API FastAPI Python attuale su **Render Free**, database persistente PostgreSQL su **Neon Free**. In futuro un gateway radio Meshtastic avrà comunque bisogno di hardware locale; gli avamposti remoti non richiedono computer o agent.

## Attivazione

1. Crea un database PostgreSQL gratuito su [Neon](https://neon.com/), preferibilmente in Europa. Copia l'URI privato della connessione e cambia il prefisso `postgresql://` in `postgresql+psycopg://`. Conserva l'eventuale `?sslmode=require`. Non salvare mai la password su GitHub.
2. Apri [Render Blueprints](https://dashboard.render.com/blueprints), collega il repository `Nicco-Male/MeshQuest` sul ramo `main` e importa `render.yaml`.
3. Inserisci in Render `MESHQUEST_DATABASE_URL` (URI Neon) e una password casuale robusta per `MESHQUEST_STAGING_PASSWORD`. La chiave amministrativa `MESHQUEST_ADMIN_KEY` è generata da Render.
4. Avvia il servizio e prova `https://<nome-servizio>.onrender.com/health`. Per vedere l'interfaccia usa l'utente **`meshquest`** e la password di staging nella finestra HTTP Basic.
5. Per chiamare l'API da script aggiungi `X-MeshQuest-Staging-Password: <password>` e, quando richiesto, anche `X-Admin-Key` o `Authorization: Bearer <token-gateway>`.

## Limiti da conoscere

- **Render Free si sospende dopo 15 minuti di inattività**; il riavvio può richiedere circa un minuto. Non è ancora adatto a ricevere in tempo reale tutte le trasmissioni.
- Il disco locale Render Free è **temporaneo**: SQLite perderebbe i dati. PostgreSQL esterno è obbligatorio.
- Sono ancora assenti migrazioni, rate limiting, verifica dell'identità radio, revoca dei gateway, controllo della freschezza degli eventi e backup di produzione.
- Solo `/health` è accessibile senza la password di staging. Non disattivare la protezione per esporre l'alpha al pubblico.
- Non è ancora disponibile un gateway RF funzionante: si testano API, dati, UI e round simulati.

Riferimenti: [Render Free](https://render.com/docs/free), [Render Blueprints](https://render.com/docs/infrastructure-as-code), [Neon](https://neon.com/pricing).
