# AI Layer

The AI orchestration tier of a 3-service stack. It turns a natural-language question (“is this product worth buying?”) into a multi-step research run over **YouTube and TikTok** — searching, pulling comments/transcripts, and clustering real user opinions into a sourced answer.

Built on **Claude tool-use**: the model decides which tools to call, the layer executes them against the `data-miner` scraping API, and the results are streamed back token-by-token.

```
   ai-chatbot (frontend)
        │  X-API-Key + Supabase JWT
        ▼
   AI Layer  ── Claude agent loop ──►  data-miner (YouTube / TikTok scraping)
        │
        ├─ PostgreSQL   chat history
        ├─ Redis        auth + history cache
        ├─ MongoDB      tool / agent-run logs
        └─ Supabase     JWT auth + remote config
```

---

## Highlights

- **Agentic tool-use loop** — Claude plans and calls from a catalogue of 20 tools (14 YouTube, 5 TikTok, 1 URL extractor); the loop runs to a configurable max-iteration budget.
- **Token streaming (SSE)** — `/agent/run/stream` streams `text_delta`, `tool_start`/`tool_done`, and a final enriched `done` event.
- **Prompt caching** — the system prompt is sent with `cache_control: ephemeral` to cut cost/latency across iterations.
- **Result enrichment** — after the model answers, tool outputs are mined for `sources`, `videos`, and `reviews`, and a quote-based review summary is generated (clusters by topic, quotes verbatim — no sentiment bias).
- **Chat history** — sessions/messages persisted in PostgreSQL, cached in Redis, scoped per user via Supabase JWT.
- **Remote configuration** — model, token budgets, agent limits, the system prompt, and downstream keys are loaded from a Supabase `config` table at startup — tunable without a redeploy.
- **Observability** — every tool call and agent run is logged to MongoDB.

---

## Tech stack

FastAPI · Anthropic Claude · asyncpg / PostgreSQL · Redis · MongoDB (motor) · Supabase · slowapi · Uvicorn

---

## API

All endpoints are mounted under `/ai` and require an `X-API-Key` header. History endpoints additionally require a Supabase `Authorization: Bearer <jwt>`.

### Agent
| Method | Path | Notes |
|--------|------|-------|
| `POST` | `/ai/agent/run` | Run the agent, return the enriched result |
| `POST` | `/ai/agent/run/stream` | Same, streamed as Server-Sent Events |

Body: `{ task, tools: "youtube"\|"tiktok"\|"all", max_iter?, system? }` (`max_iter` defaults to `AGENT_MAX_ITER`).

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
`GET /health` — checks data-miner reachability and that the Claude key is set.

---

## Tools

The agent's capabilities are declared as Claude tool schemas in `tools/definitions.py` and dispatched in `tools/executor.py` (input validated with `jsonschema`, executed against the data-miner client).

- **YouTube** — search, by-topic, shorts, live, by-region, detail, comments (+ batch), transcript (+ batch), channel info/videos/playlists, playlist videos.
- **TikTok** — search, video-info, comments, profile, transcript.
- **Utility** — `extract_id_from_url` (offline parse of YouTube/TikTok links).

Tool sets are selectable per request: `youtube`, `tiktok`, or `all`.

---

## Agent loop (how it works)

1. Send the task to Claude with the selected tools; the first iteration forces a tool call (unless the task carries prior history).
2. On `tool_use`, execute each requested tool, trim the result to a token budget, and feed it back.
3. Repeat until Claude returns `end_turn` (final answer) or the iteration budget is hit.
4. Enrich the final text with collected sources/videos and a review summary; persist the run.

---

## Configuration

Infrastructure settings come from environment variables; **operational settings come from the Supabase `config` table** (`config/remote.py`), applied at startup.

**From Supabase config:** `ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS`, `DATA_MINER_KEY`, `AGENT_SYSTEM` (system prompt), `AGENT_MAX_ITER`, `AGENT_MAX_RESULT_CHARS`, `AGENT_MAX_COMMENTS`, `AGENT_MAX_COMMENT_LEN`, `AGENT_MAX_LIST_ITEMS`.

**From environment** (see `.env.example`): `API_KEYS`, `CORS_ORIGINS`, `DATA_MINER_URL`, `DATABASE_URL`, `REDIS_*`, `MONGODB_*`, `SUPABASE_*`, `GEOIP_DB_PATH`, `LOG_LEVEL`.

---

## Getting started

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Requires reachable PostgreSQL, Redis, and a Supabase project (for auth + config). Interactive docs at `http://localhost:8001/docs`.
