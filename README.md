# AI Layer

The AI orchestration tier of a 3-service stack. It turns a natural-language question (“is this product worth buying?”) into a multi-step research run over **YouTube and TikTok** — searching, pulling comments/transcripts, and clustering real user opinions into a sourced answer.

Built on **OpenAI Responses API** with tool-use: the model decides which tools to call, the layer executes them against the `data-miner` scraping API, and the results are streamed back token-by-token.

```
   ai-chatbot (Next.js)
        │  X-API-Key + Supabase JWT
        ▼
   AI Layer  ── OpenAI agent loop ──►  data-miner (YouTube / TikTok scraping)
        │
        ├─ PostgreSQL   chat history + video cache (SQLAlchemy)
        ├─ Redis        auth + history cache
        ├─ MongoDB      tool / agent-run logs
        └─ Supabase     JWT auth + remote config
```

---

## Highlights

- **Agentic tool-use loop** — OpenAI plans and calls from a catalogue of 20 tools (14 YouTube, 5 TikTok, 1 URL extractor); configurable max-iteration budget.
- **Dual-model mode** — optional `OPENAI_TOOL_MODEL` (e.g. `gpt-4o-mini`) for tool selection + `OPENAI_MODEL` (e.g. `gpt-4o`) for final synthesis.
- **Token streaming (SSE)** — `/agent/run/stream` streams `text_delta`, `tool_start`/`tool_done`, and a final enriched `done` event.
- **Result enrichment** — after the model answers, tool outputs are mined for `sources`, `videos`, and `reviews`; a quote-based review summary is generated (clusters by topic, quotes verbatim).
- **Chat history** — sessions/messages in PostgreSQL via SQLAlchemy, cached in Redis, scoped per user via Supabase JWT.
- **Remote configuration** — model, token budgets, agent limits, system prompt, and downstream keys loaded from Supabase `config` at startup.
- **Observability** — every tool call and agent run logged to MongoDB.

---

## Tech stack

FastAPI · OpenAI (Responses API) · SQLAlchemy 2 (async) · asyncpg · pgvector · Redis · MongoDB (motor) · Supabase · slowapi · Uvicorn

---

## Project structure

```
app/
├── api/
│   ├── agent.py          # POST /ai/agent/run[/stream]
│   ├── youtube.py        # direct YouTube AI endpoints
│   ├── utilities.py      # URL shortener, QR generator
│   └── history.py        # chat sessions + messages
├── services/
│   ├── agent.py          # agent loop (sync + SSE stream)
│   ├── enricher.py       # sources / videos / review summary
│   ├── review_summarizer.py
│   └── chatgpt.py        # re-exports complete / complete_json
├── utils/
│   ├── openai_responses.py   # shared responses.create wrapper
│   └── openai_client.py
├── tools/
│   ├── definitions.py    # OpenAI tool schemas
│   └── executor.py       # dispatch + jsonschema validation
├── repositories/         # SQLAlchemy data access
│   ├── chat.py
│   ├── videos.py
│   ├── comments.py
│   └── search_cache.py
├── db/
│   ├── session.py        # engine + init_db
│   └── models/           # declarative models (chat, video, cache, vectors)
├── clients/data_miner.py
├── cache/client.py       # Redis
└── db/mongo.py           # optional tool/agent logs
```

---

## API

All endpoints are mounted under `/ai` and require an `X-API-Key` header. History endpoints additionally require `Authorization: Bearer <supabase_jwt>`.

### Agent

| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/ai/agent/run` | Run the agent, return enriched result |
| `POST` | `/ai/agent/run/stream` | Same, streamed as Server-Sent Events |

Body: `{ "task": "...", "tools": "youtube"|"tiktok"|"all", "max_iter?": 10, "system?": "..." }`

SSE event types: `text_delta` · `tool_start` · `tool_done` · `data_preview` · `done` · `error`

### YouTube AI (direct, no agent loop)

| Method | Path |
|--------|------|
| `GET` | `/ai/youtube/videos/{video_id}/summary` |
| `GET` | `/ai/youtube/videos/{video_id}/comments/analysis` |
| `GET` | `/ai/youtube/trending/analysis` |

### Utilities

| Method | Path |
|--------|------|
| `POST` | `/ai/utilities/shorten` |
| `POST` | `/ai/utilities/qr` |

### History (Supabase JWT)

`GET/POST /ai/history/sessions` · `PATCH/DELETE /ai/history/sessions/{id}` · `GET/POST /ai/history/sessions/{id}/messages`

### Health

`GET /health` — checks data-miner reachability and OpenAI key presence.

---

## Tools

Declared as OpenAI function schemas in `tools/definitions.py`, dispatched in `tools/executor.py` (validated with `jsonschema`, executed via `clients/data_miner.py`).

| Set | Tools |
|-----|-------|
| **YouTube** | search, by-topic, shorts, live, by-region, detail, comments (+batch), transcript (+batch), channel info/videos/playlists, playlist videos |
| **TikTok** | search, video-info, comments, profile, transcript |
| **Utility** | `extract_id_from_url` (offline URL parse) |

Selectable per request: `youtube`, `tiktok`, or `all`. When the user explicitly names a platform in the task, cross-platform tools are blocked at the code level.

---

## OpenAI integration

All `responses.create` calls go through `app/utils/openai_responses.py`:

- `create_response()` — unified wrapper with logging
- `complete()` / `complete_json()` — simple text/JSON completions
- `extract_response_text()`, `status_error()`, `output_items_to_input()` — shared helpers for the agent loop

---

## Database

PostgreSQL schema is managed via SQLAlchemy models in `app/db/models/`:

| Table | Purpose |
|-------|---------|
| `chat_sessions` / `chat_messages` | Chat history |
| `videos` / `comments` | Video + comment cache |
| `search_cache` | Search result cache |
| `video_chunks` | Vector RAG chunks (`vector(1536)` + HNSW index) |

Requires the **pgvector** extension. Tables are created on startup via `init_db()`.

---

## Agent loop

1. Send the task to OpenAI with selected tools; first iteration forces a tool call unless the task carries prior history.
2. On `function_call`, execute tools in parallel, trim results to a token budget, feed outputs back.
3. Repeat until the model returns a final answer or the iteration budget is hit.
4. In dual-model mode, a synthesis pass on `OPENAI_MODEL` produces the final user-facing text.
5. Enrich with sources/videos/review summary; persist run to MongoDB.

---

## Configuration

**From Supabase `config` table** (`config/remote.py`):  
`OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_TOOL_MODEL`, `OPENAI_MAX_TOKENS`, `OPENAI_TOOL_MAX_TOKENS`, `DATA_MINER_KEY`, `AGENT_SYSTEM`, `AGENT_MAX_ITER`, `AGENT_MAX_RESULT_CHARS`, `AGENT_MAX_COMMENTS`, `AGENT_MAX_COMMENT_LEN`, `AGENT_MAX_LIST_ITEMS`

**From environment** (see `.env.example`):

```env
API_KEYS=
CORS_ORIGINS=http://localhost:3000

DATA_MINER_URL=http://localhost:8000
DATA_MINER_TIMEOUT=60

OPENAI_MODEL=gpt-4o
OPENAI_TOOL_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=4096
OPENAI_TOOL_MAX_TOKENS=2048

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/youtube
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=1

MONGODB_URL=
MONGODB_NAME=

SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

GEOIP_DB_PATH=
LOG_LEVEL=INFO
```

---

## Logging

Convention: `logger.info("[module] message key=%s", value)` — e.g. `[agent]`, `[openai]`, `[data_miner]`, `[db]`, `[mongo]`.

---

## Getting started

```bash
pip install -r requirements.txt
fastapi run app/main.py --host 0.0.0.0 --port 8001
# or: uvicorn app.main:app --reload --port 8001
```

Requires PostgreSQL (with pgvector), Redis, and a Supabase project (auth + config). MongoDB is optional (logging only).

Interactive docs: `http://localhost:8001/docs`
