# ChatAPI — Embeddable AI Chat for Local Businesses

Give every local business an AI chat agent grounded in its own documents,
bookable via a one-line embeddable widget.

## Architecture

```
                  +------------------+
                  |  Any website     |
                  |  widget/widget.js|  60px bubble -> iframe
                  +--------+---------+
                           | {base}/c/{slug}?embed=true
                           v
+----------------+   +-----+--------+   +------------------+
| Visitor browser+--->+  Frontend    +--->+  Backend (FastAPI)|
|                |   |  Next.js :3000|   |  :8000           |
+----------------+   +-----+--------+   +--------+---------+
                                                 |
                                                 v
                                        +--------+---------+
                                        |  SQLite + uploads|
                                        |  (local, no server)|
                                        +------------------+
```

- **backend/** (FastAPI, `:8000`): local JWT auth, agent CRUD, document
  ingest, local SQLite storage + hybrid (vector + BM25) retrieval,
  OpenRouter chat completions (default free model
  `google/gemma-4-31b-it:free`).
- **frontend/** (Next.js + shadcn/ui, `:3000`): landing, local
  signup/login, dashboard + agent builder wizard + playground, public
  chat pages at `/c/[slug]` (`?embed=true` renders a chromeless panel
  for the iframe).
- **widget/** (vanilla JS, no deps): floating bubble + lazy `380×600` iframe.
- No external DB or auth provider. Storage is a local SQLite file
  (`backend/chatapi.db`) + `backend/uploads/`. External calls are limited to
  the site being crawled and OpenRouter for embeddings/chat.

## Quickstart (local, no Docker needed)

```bash
# 1. Backend
cd backend
cp .env.example .env   # then put your key in .env: OPENROUTER_API_KEY=sk-or-...
python3 -m venv .venv && source .venv/bin/activate
pip install fastapi "uvicorn[standard]" sqlalchemy python-jose bcrypt \
  httpx beautifulsoup4 requests pypdf python-docx python-multipart \
  nanoid email-validator python-dotenv
uvicorn app.main:app --reload --port 8000

# 2. Frontend (second terminal)
cd frontend
cp .env.local.example .env.local
npm install && npm run dev
```

- Frontend: http://localhost:3000 (sign up → creates a local account)
- Backend:  http://localhost:8000 (health: `/health`, docs: `/docs`)
- Widget demo: serve `widget/test.html`, e.g.
  `cd widget && python3 -m http.server 5500`, using your agent slug.

`docker-compose.yml` is kept as an optional deployment path; local dev
needs nothing but the two commands above.

## How knowledge is indexed

- **URL ingestion** (`scrape_site`) reads `robots.txt`, collects URLs from
  the sitemap(s) and the seed page, canonicalizes them (tracking params,
  `www`, trailing slashes), and ranks candidates against the agent's
  name/description. When `OPENROUTER_API_KEY` is set, a cheap LLM ranks the
  candidates and a second pass drops junk pages; it may only choose URLs
  discovered by the crawler, never invented ones.
- Pages are fetched concurrently (`SCRAPE_CONCURRENCY`) with a global
  politeness delay (`SCRAPE_DELAY_MS`, raised to `Crawl-delay` when
  advertised). PDFs are text-extracted, and thin pages can be retried with
  headless Chromium if `playwright` is installed (`pip install playwright &&
  playwright install chromium`, set `SCRAPE_JS_RENDER=1`).
- Text is chunked per section with the heading path stored on each chunk
  (`Opening Hours › Weekends`) so answers can cite `URL › section`.
- Retrieval combines vector similarity with BM25 keyword scores and applies
  `MIN_SIMILARITY`; when nothing is relevant the model is told there is no
  context instead of being handed unrelated chunks.

Crawler tuning lives in `backend/.env.example` (`SCRAPE_MAX_PAGES`,
`SCRAPE_LLM_RANK`, `SCRAPE_RANK_MODEL`, ...). Without an OpenRouter key the
crawler falls back to lexical ranking and chat runs in embed-only mode.

## API reference

| Method | Path                          | Description                              |
| ------ | ----------------------------- | ---------------------------------------- |
| `GET`  | `/health`                     | Liveness check.                          |
| `GET`  | `/api/agents`                 | List agents.                             |
| `POST` | `/api/agents`                 | Create an agent (`slug`, `primaryColor`).|
| `GET`  | `/api/agents/{slug}`          | Get one agent (widget reads brand colour).|
| `POST` | `/api/agents/{slug}/ingest`   | Ingest documents for an agent.           |
| `POST` | `/api/agents/{slug}/chat`     | RAG chat completion via OpenRouter.      |

Interactive docs when the backend is running: http://localhost:8000/docs

## Widget snippet

```html
<script
  src="http://localhost:3000/widget.js"
  data-agent="demo-bakery"
  data-api="http://localhost:8000"
  data-base="http://localhost:3000"
></script>
```

See [widget/README.md](widget/README.md) for attributes and behaviour.
