# AI Layer

Orchestration service for **CineFlow AI** — turns a movie question into a researched answer from **YouTube and TikTok** (search, transcripts, comments) with optional **RAG** over previously ingested reviews.

Built on **OpenAI-compatible chat completions** (Responses-shaped adapter). The model plans tool use; this service executes tools against **data-miner**, streams the answer to the chatbot, and runs a background **ingest → RAG** pipeline into PostgreSQL.

```
   ai-chatbot (Next.js)
        │  X-API-Key (+ Supabase JWT for history)
        ▼
   AI Layer ── agent loop (SSE) ──► data-miner (YouTube / TikTok crawl)
        │
        ├─ Supabase Postgres      chat, video cache, movies, RAG vectors (DATABASE_URL)
        ├─ Redis                auth + history cache
        ├─ in-process ingest     background tasks (comments → RAG → summarize)
        └─ Supabase REST        Auth, profiles, runtime config table
```

Further reading: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (bắt đầu từ đây) · [docs/FLOW.md](docs/FLOW.md) · [docs/RAG-GUIDE.md](docs/RAG-GUIDE.md) · [docs/REFACTOR-AUDIT.md](docs/REFACTOR-AUDIT.md) · [../docs/MCP-PHASE2-GUIDE.md](../docs/MCP-PHASE2-GUIDE.md)

---

## Highlights

- **Agent loop** — LLM tool calling (YouTube, TikTok, RAG); platform-aware filtering; guards (search budget, force synthesis). Shared logic: `services/agent/core/engine.py`.
- **Dual-model mode** — optional different `tool_model` vs `model` on the same provider (e.g. XAH); synthesis streams separately when they differ.
- **SSE streaming** — token-by-token `text_delta` (including live synthesis in dual-mode); tool progress events; metadata without blocking the text stream.
- **Enrichment** — derives `sources`, analyzed `videos` (only videos actually crawled, not full search pages); narrative answer lives in the agent bubble only.
- **3-tier RAG** — L1 `aspect_summaries` → L2 `aspect_chunks` → L3 `raw_reviews`; vector search via pgvector; ingest pipeline runs as an in-process background task (fire-and-forget, no broker).
- **Chat history** — sessions/messages in PostgreSQL, Redis cache, scoped by Supabase JWT.
- **Remote config** — prompts, OpenAI keys, agent limits, and rate limits loaded from Supabase `config` at startup (see [Configuration](#configuration)).

---

## Tech stack

FastAPI · OpenAI-compatible LLM (chat completions adapter) · SQLAlchemy 2 (async) · asyncpg · pgvector · Redis · Supabase · slowapi · Uvicorn

---

## Project structure

```
app/
├── api/
│   ├── agent.py           # POST /ai/agent/run[/stream]
│   ├── youtube.py         # direct YouTube AI endpoints
│   ├── history.py         # chat sessions + messages
│   ├── utilities.py       # URL shortener, QR
│   └── admin.py           # health detail, ingest queue stats
├── services/
│   ├── agent/
│   │   ├── core/          # context, engine, iterate, runner, stream, langgraph_runner/stream
│   │   ├── events/        # SSE event schema, tool_status
│   │   ├── guards/        # budget, fallback
│   │   ├── synthesis/     # finalize, generate
│   │   ├── tooling/       # dispatch, platform filter, serialize
│   │   └── graph/         # LangGraph nodes/state (see Roadmap below)
│   ├── enricher.py        # orchestrate UI metadata
│   ├── enricher_collect.py # parse tool_call_log → reviews/videos/sources
│   ├── review_summarizer.py
│   ├── prompts.py         # ASPECT_* for ingest LLM; agent prompts from Supabase
│   └── health.py
├── tools/
│   ├── definitions.py     # YouTube / TikTok tool schemas
│   ├── rag_definitions.py # RAG tool schemas (when RAG_ENABLED)
│   └── executor.py        # dispatch + jsonschema validation
├── rag/                   # vector search, movie_id, movie_hint
├── ingest/                # background dispatch, handlers, RAG sync, summarize
├── repositories/          # SQLAlchemy data access
├── config/db/models/      # chat, video, movie RAG tables
├── clients/data_miner.py
├── utilities/             # QR code, URL shortener (active)
├── config/
│   ├── settings.py        # env / infra
│   ├── loader.py          # schema binders
│   └── remote.py          # Supabase config load + validate
├── ai/
│   ├── providers.py       # ConfiguredLLM (chat completions + stream adapter)
│   ├── factory.py
│   └── router.py
└── utils/
    ├── llm_responses.py   # LLM response helpers (stream, create_response)
    └── llm_errors.py      # user-facing LLM error messages
```

---

## API

Mounted under `/ai`. Most routes require `X-API-Key`. History requires `Authorization: Bearer <supabase_jwt>`.

### Agent

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/ai/agent/run` | Full JSON result |
| `POST` | `/ai/agent/run/stream` | Server-Sent Events (preferred for UI) |

Body: `{ "task": "...", "tools": "youtube"|"tiktok"|"all", "max_iter?": 10, "system?": "..." }`

**SSE event types**

| Event | Purpose |
|-------|---------|
| `text_delta` | Answer text chunk (streamed as generated) |
| `tool_start` / `tool_done` | Tool execution progress (`detail` localized via `X-Lang`) |
| `status` | Phase hints (analyzing, writing answer, …) |
| `data_preview` | Early video list from tool results |
| `done` | `sources`, `videos`, `tool_calls` |
| `error` | User-safe error message |

### Other

| Area | Paths |
|------|-------|
| YouTube AI | `GET /ai/youtube/videos/{id}/summary`, `.../comments/analysis`, `.../trending/analysis` |
| Utilities | `POST /ai/utilities/shorten`, `POST /ai/utilities/qr` |
| History | `/ai/history/sessions`, `.../messages` |
| Health | `GET /health` |
| Admin | `GET /ai/admin/health/detail`, `GET /ai/admin/ingest/queues` |

---

## Tools

Schemas in `tools/definitions.py` + `tools/rag_definitions.py`, executed in `tools/executor.py` via `clients/data_miner.py` (social) or `rag/search.py` (RAG).

| Set | Examples |
|-----|----------|
| **YouTube** | search, comments_batch, transcript_batch, detail, channel, … |
| **TikTok** | search, video_info, comments, transcript, profile |
| **RAG** | `search_movie_summary`, `search_aspect_evidence`, `get_raw_reviews` |
| **Util** | `extract_id_from_url` |

Per request: `tools: "youtube" | "tiktok" | "all"`. `prepare_tools_for_task()` narrows by platform, movie context block, and **RAG cache-first** when saved summaries are fresh.

---

## Agent loop (current)

1. OpenAI Responses API call with selected tools (`tool_choice: auto`).
2. On `function_call` → execute tools in parallel → trim results → append to conversation → repeat.
3. Final answer: stream tokens directly, or in **dual-mode** run a separate synthesis stream on `OPENAI_MODEL`.
4. Emit `done` with `sources`, `videos`, `tool_calls`.

Prompts and limits come from **Supabase `config`**, not hardcoded in the repo.

---

## Database

**Supabase Postgres** via `DATABASE_URL` (pooler port 6543 khuyến nghị). Auth + `config` vẫn qua Supabase REST (`SUPABASE_*`).

**Setup một lần:**
1. Supabase SQL Editor: chạy `config/supabase-setup.sql` (bật `vector`)
2. `cd ai-layer && alembic upgrade head`

**Migrations (Alembic)** — `alembic/`:
- Fresh DB: `alembic upgrade head`
- DB đã có bảng từ `init_db()`: `alembic stamp head` (một lần), rồi `alembic revision --autogenerate` cho thay đổi tiếp theo
- Vector search SQL nằm trong `repositories/aspect_summaries.py` + `aspect_chunks.py` (không còn trong `rag/search.py`)

| Area | Tables |
|------|--------|
| Chat | `chat_sessions`, `chat_messages` |
| Video cache | `videos`, `comments`, `search_cache`, `video_chunks` |
| Movie RAG | `movies`, `raw_reviews`, `curated_reviews`, `aspect_chunks`, `aspect_summaries` |

---

## Configuration

### Supabase `config` table (required at startup)

Loaded by `app/config/remote.py`. Missing keys → startup error.

| Keys | Purpose |
|------|---------|
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TOOL_MODEL` | Models |
| `OPENAI_MAX_TOKENS`, `OPENAI_TOOL_MAX_TOKENS` | Token budgets |
| `DATA_MINER_KEY` | Downstream scrape API |
| `AGENT_SYSTEM`, `REVIEW_SUMMARY_SYSTEM`, `REVIEW_SUMMARY_PROMPT` | Prompts |
| `AGENT_MAX_ITER`, `AGENT_MAX_RESULT_CHARS`, `AGENT_MAX_COMMENTS`, … | Agent tuning |
| `AGENT_RATE_LIMIT`, `QR_RATE_LIMIT`, … | slowapi limits |

Manage via ai-chatbot admin `/admin/config` or Supabase SQL.

### Environment (infra)

See `.env.example` — `API_KEYS`, `DATABASE_URL`, `REDIS_*`, `SUPABASE_*`, `RAG_ENABLED`, `INGEST_ENABLED`, etc.

OpenAI model values are **not** defaulted in code; they must exist in Supabase `config` (or env before remote load in dev).

---

## Getting started

```bash
cd ai-layer
python3 -m venv .venv && source .venv/bin/activate   # Python 3.14+; use ai-layer venv, not data-miner
pip install -r requirements.txt
cp .env.example .env
# Fill API_KEYS, DATABASE_URL (Supabase Postgres), SUPABASE_*
# Supabase: config/supabase-setup.sql → alembic upgrade head

fastapi dev app/main.py --port 8001
```

Ingest (comments/transcript → RAG) runs as an in-process background task — no separate worker or broker to stand up; toggle with `INGEST_ENABLED`.

Docker stack lives in the parent monorepo (`docker-compose.yml`): redis, `ai-layer`, `data-miner`. Postgres = Supabase (không còn container local).

Docs UI: `http://localhost:8001/docs`

---

## Logging

`logger.info("[module] message key=%s", value)` — namespaces like `[agent]`, `[openai]`, `[ingest]`, `[rag_sync]`. Rotating files under `logs/` (gitignored).

---

## Multi-agent orchestration (LangGraph)

The agent is a **supervisor + per-platform worker** graph on LangGraph — supervisor routes a question to 1..N workers (YouTube/TikTok/movie catalog), workers run in parallel via `Send()` fan-out, results merge and go through one shared synthesis step. Both `/agent/run` and `/agent/run/stream` run through the same graph — there is no alternate backend/flag.

**Chi tiết kiến trúc + thứ tự đọc file:** [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## License / stack context

Part of the CineFlow AI monorepo: **ai-chatbot** (UI) · **ai-layer** (this repo) · **data-miner** (scraping).
