# MeshQuest cloud staging (Render + Neon)

> **Language:** **English (this page)** · [Italiano](HOSTING.it.md) · [Translations](TRANSLATIONS.md)

**Status:** deployment blueprint prepared, **no cloud service deployed yet**. This is a password-protected closed-alpha staging environment, not a public production release.

## Why not GitHub-hosted servers?

GitHub Pages can serve only static assets, while GitHub Actions runners are disposed of after each job and Codespaces stop automatically. None is a persistent, stateful FastAPI game server.

We keep the public GitHub repository for code and CI, use **Render Web Service (Free)** for the existing Python FastAPI app, and **Neon PostgreSQL (Free)** for persistent state. The physical Meshtastic gateway/radio still needs a local host later, but registered relay outposts do not.

## First deployment

1. Create a free PostgreSQL project in [Neon](https://neon.com/), ideally in a nearby European region. Copy its **password-protected** connection URI. Change the URI scheme from `postgresql://` to `postgresql+psycopg://` for the installed SQLAlchemy driver. Keep any `?sslmode=require` query string. Never commit the URI.
2. Sign in to [Render Blueprints](https://dashboard.render.com/blueprints) and create a new Blueprint from `Nicco-Male/MeshQuest`, branch `main`, using the repository's `render.yaml`.
3. In the Render Blueprint setup, supply `MESHQUEST_DATABASE_URL` (the adjusted Neon URI) and a strong random `MESHQUEST_STAGING_PASSWORD`. Render generates `MESHQUEST_ADMIN_KEY`. Treat both as private secrets.
4. Deploy and check `https://<your-render-service>.onrender.com/health` (returns `{"status":"ok",...}`). When browsing the UI, use **username `meshquest`** and the staging password in the browser's HTTP Basic prompt.
5. For scripted API requests, send `X-MeshQuest-Staging-Password: <password>` in addition to any `X-Admin-Key` or `Authorization: Bearer <gateway-token>` required by the endpoint. Do not publish these secrets or expose the prototype as an unrestricted public game.

The Render service uses the existing `Dockerfile`, existing `/health` check and existing `MESHQUEST_DATABASE_URL` support. It serves the current HTML and API together on one origin; there is no separate frontend or CORS setup.

## Important limitations

- **Render Free sleeps after 15 minutes idle**. First access after sleep can take around a minute. Radio gateways must not depend on it for timely delivery; retries and durable local buffering are future work.
- **Render Free has ephemeral local disks**. Never deploy with SQLite there; use external Neon PostgreSQL.
- The present SQLAlchemy prototype uses `metadata.create_all` instead of migrations. Before production: add Alembic, rate limiting, account/NodeID verification, gateway revocation, server-side event freshness checks and backups.
- Only `/health` is public without staging authentication. Other routes require Basic auth (browser) or the custom staging header (API clients). Do not disable the staging guard while the alpha is unsafe for public use.
- **No live RF gateway is implemented yet**. This environment tests only API, database, UI, and simulated gameplay.
- When ready for an always-on RF service, move to a persistent paid host or an existing always-on home server. GitHub remains the source-of-truth and CI platform.

Useful references: [Render free limitations](https://render.com/docs/free), [Render Blueprints](https://render.com/docs/infrastructure-as-code), [Neon pricing](https://neon.com/pricing).
