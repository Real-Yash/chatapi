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
                                        | Postgres pgvector|
                                        | pg16 + pgdata vol|
                                        +------------------+
```

- **backend/** (FastAPI, `:8000`): local JWT auth, agent CRUD, document
  ingest, local SQLite storage + in-Python cosine retrieval,   OpenRouter
  chat completions (default free model `google/gemma-4-31b-it:free`).
- **frontend/** (Next.js + shadcn/ui, `:3000`): landing, local
  signup/login, dashboard + agent builder wizard + playground, public
  chat pages at `/c/[slug]` (`?embed=true` renders a chromeless panel
  for the iframe).
- **widget/** (vanilla JS, no deps): floating bubble + lazy `380×600` iframe.
- No external DB or auth provider. Storage is a local SQLite file
   (`backend/chatapi.db`) + `backend/uploads/`. The only network call is
  OpenRouter for embeddings/chat.

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
