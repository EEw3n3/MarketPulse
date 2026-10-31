# MarketPulse

Price monitoring for the Latvian perfume market. MarketPulse collects the catalogues of Latvian online stores,
recognises the same perfume across stores, records every price change and alerts users by Telegram and e-mail.

Live: [marketpulse1.me](https://marketpulse1.me) · Built solo as my qualification project at Rīgas Valsts tehnikums (2026).
Latvian version of this README: [README.lv.md](README.lv.md).

## What it does

- **One collector per store.** Each store is read from its most reliable source: a REST API (Makeup.lv), JSON
  embedded in the page (Douglas), the store's own XHR requests (Notino) or widget JSON (220.lv). `curl_cffi` is
  used where plain HTTP is enough, Playwright where the page needs a browser.
- **Normalisation and cross-store matching.** Titles are reduced to brand, name, volume and concentration
  (EDP, EDT, Parfum, Latvian and Lithuanian spellings), then the same perfume is linked into one comparison group
  across stores. Different products stay apart (Molecule 01 is not Molecule 02, Intense is not Intensely).
- **Price history and alerts.** Every price and stock change is stored. Users follow products and get Telegram or
  e-mail alerts when a price drops past their threshold.
- **Dashboard.** React + TypeScript: catalogue with cross-store comparison, product price history, market
  analytics charts, favourites, CSV / Excel / PDF export and an AI chat that answers from the catalogue (Gemini).
- **AI selector generation.** For a store without a verified rule, Gemini proposes CSS selectors from the page
  HTML; a rule is accepted only when it finds at least 5 product cards.
- **Scheduled collection.** The server queues jobs in Redis every night. Stores that block data-centre IPs are
  scraped by a worker on a home PC, which uploads the results to the API.

1a.lv is supported in code but paused: its catalogue is behind a Cloudflare check, and MarketPulse does not try to
get around such checks.

## Architecture

```
stores ──> collectors (curl_cffi / Playwright) ──> normaliser ──> matcher ──> PostgreSQL
                 ▲                                                               │
     Redis job queue <── nightly timer / admin panel                    FastAPI REST API
                 │                                                               │
        home-PC worker (uploads results)                              React dashboard, alerts
```

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.11, FastAPI, SQLModel / SQLAlchemy (asyncpg), Pydantic, Alembic, JWT |
| Data | PostgreSQL 15, Redis (job queue), thefuzz |
| Scraping | Playwright, curl_cffi |
| AI | Google Gemini (`google-genai`) |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, Recharts |
| Notifications | Telegram Bot API, Resend |
| Exports | openpyxl, ReportLab, matplotlib |
| Infrastructure | Docker Compose (db, redis, app, frontend, caddy), Caddy with automatic HTTPS, Linux VPS, GitHub Actions |

CI (`.github/workflows/ci.yml`) runs on every push: compile check, import smoke test, single Alembic head, ruff
and the frontend build.

## Run locally

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) and Git.

```bash
git clone https://github.com/EEw3n3/MarketPulse.git
cd MarketPulse
cp .env.example .env    # set at least POSTGRES_PASSWORD, GOOGLE_API_KEY and JWT_SECRET
docker compose up -d db redis
docker compose up -d --no-deps app frontend
```

- Dashboard: http://localhost:8080
- API docs (Swagger): http://localhost:8000/docs
- The `app` container applies the database migrations (`alembic upgrade head`) on start.
- Do not start the `caddy` service locally: it is the production reverse proxy.

To collect data, start a worker in another terminal and queue jobs from Admin → Scraping:

```bash
docker compose exec app python scripts/scrape_worker.py
```

To check a store's scraper against the live site (HTML report in `reports/`):

```bash
docker compose exec -T app python scripts/scrape_review.py makeup --pages 3
```

The user whose e-mail is set in `ADMIN_EMAIL` becomes an administrator after registering.
