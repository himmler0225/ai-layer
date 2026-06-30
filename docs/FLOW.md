# Flow ai-layer (tóm tắt)

**RAG chi tiết (đọc khi nâng cấp):** [RAG-GUIDE.md](./RAG-GUIDE.md)  
**LangGraph (thay agent loop):** [LANGGRAPH-GUIDE.md](./LANGGRAPH-GUIDE.md)

## Stack

- **ai-chatbot** — UI, gửi `task` + block `[Phim đang xem]`
- **ai-layer** — agent OpenAI, tool, ingest, RAG search
- **data-miner** — crawl YouTube/TikTok
- **Postgres** — hết dữ liệu app (video, comments, movies, RAG)
- **Supabase** — auth + `config` (có thể override prompt prod)
- **RabbitMQ** — job ingest nền

Review social chỉ từ YouTube/TikTok. Giá FPT/Tiki chatbot nhét vào prompt, không crawl TMĐT.

---

## Đọc — user hỏi → trả lời

```
chatbot POST /agent/run/stream
  → bootstrap_agent → prepare_tools_for_task
       (platform filter → movie context → RAG cache-first)
  → OpenAI Responses API (vòng lặp tool, loop.py)
  → RAG L1/L2/L3 hoặc crawl data-miner
  → schedule_tool_ingest (nền, mỗi tool crawl)
  → SSE text_delta + status + done
```

**Task từ chatbot** khi bấm AI Review:

```
[Phim đang xem]
Tên: iPhone 17 Pro
movie_id: dune-part-two
Giá: ...
[Câu hỏi hiện tại]
...
```

### Chiến lược agent (RAG)

1. **Cache-first** — `RAG_ENABLED` + `movie_has_knowledge` + `is_movie_fresh` (cần L1 trong TTL) → chỉ 4 tool RAG
2. **L1** `search_movie_summary` → `coverage` sufficient / partial / none
3. **L2** `search_aspect_evidence` khi partial
4. **L3** `get_raw_reviews` khi cần nguyên văn
5. **Crawl** YouTube/TikTok khi `none` hoặc chưa có data

| Tầng | Bảng | Tool | Vector |
|------|------|------|--------|
| L1 | `aspect_summaries` | `search_movie_summary` | Có |
| L2 | `aspect_chunks` | `search_aspect_evidence` | Có |
| L3 | `raw_reviews` | `get_raw_reviews` | Không (sort likes) |

Vector search SQL: `repositories/aspect_summaries.py`, `aspect_chunks.py`  
Orchestration + coverage: `rag/search.py`

---

## Ghi — crawl → RAG

Hai track song song mỗi batch comment (`handlers/comments.py`):

```
tool crawl OK
  → schedule_tool_ingest (movie_hint từ task)
  → RabbitMQ
  → comments handler
       ├─ FLAT:  comments + video_chunks (embed)
       └─ RAG:   sync_comments_to_movie_rag
            → raw_reviews + merge curated (incremental)
            → summarize: raw≥20 lần đầu; sau đó delta≥50 (xem RAG-GUIDE §6.3)
            → LLM group aspect → aspect_chunks + embed
            → LLM summary → aspect_summaries + embed
```

| Routing key | Queue | Handler |
|-------------|-------|---------|
| `comments.upsert` | `ingest.comments` | dual flat + RAG |
| `movie.summarize` | `ingest.summarize` | L1/L2 pipeline |
| `chunks.embed` | `ingest.embed` | `video_chunks` flat |

Consumer retry 3 lần → DLQ. Chi tiết: [RAG-GUIDE §6](./RAG-GUIDE.md#6-ghi--chi-tiết-từng-bước).

---

## File hay đụng

| Việc | File |
|------|------|
| API stream | `app/api/agent.py` |
| Agent loop + guards | `app/services/agent/engine.py`, `loop.py`, `stream.py`, `runner.py` |
| Lọc tool + cache-first | `app/services/agent/platform.py` |
| RAG đủ/fresh? | `app/rag/knowledge.py` |
| Product name từ task | `app/rag/movie_hint.py` |
| L1/L2/L3 query | `app/rag/search.py` |
| Vector SQL | `repositories/aspect_summaries.py`, `aspect_chunks.py` |
| Tool RAG | `tools/rag_definitions.py`, `executor.py` |
| Ingest schedule | `ingest/dispatcher/schedule.py`, `routes.py` |
| RAG sync | `ingest/processing/rag_sync.py` |
| Summarize | `ingest/handlers/summarize.py` |
| Curate | `ingest/processing/curate.py`, `quality.py` |
| Lỗi LLM | `app/utils/llm_errors.py` |
| Prompt agent | Supabase `config` · ingest LLM: `services/prompts.py` |

---

## Chạy dev

Dùng venv **ai-layer**, không dùng venv data-miner.

```bash
cd ai-layer && source .venv/bin/activate
pip install -r requirements.txt
# optional: pip install -r requirements-dev.txt

fastapi dev app/main.py --port 8001
# worker riêng: python -m app.ingest
```

Cần: `DATABASE_URL`, `OPENAI_API_KEY`, `RAG_ENABLED=true` (mặc định code là `false` nếu không set), `RABBITMQ_URL` (nếu ingest).

**Lộ trình học RAG từng bước:** [RAG-GUIDE §0](./RAG-GUIDE.md#0-lộ-trình-vừa-làm-vừa-học).

**Alembic:** DB mới `alembic upgrade head` · DB cũ `alembic stamp head` (một lần).

---

## Lỗi OpenAI hay gặp

Message kiểu *"An error occurred while processing your request... req_xxx"* là **500 phía OpenAI**, không phải bug Python.

Đã xử lý trong code:

1. **Thu hẹp tool** khi có `[Phim đang xem]` (~27 → ~9) hoặc cache-first (~4 RAG)
2. **Retry 1 lần** stream/sync nếu 5xx/timeout — `openai_responses.py`
3. **Message tiếng Việt** + log `request_id` — `openai_errors.py`

---

## Ghi chú

- Mongo đã bỏ hẳn.
- Supabase `config` ghi đè `AGENT_SYSTEM` — prod khác local là do đó.
- Python 3.9: `from __future__ import annotations` ở file dùng `str | None`.
- SSE: `text_delta`, `status`, `tool_start`/`tool_done` (có `detail_vi`), `data_preview`, `done` — không còn event `review_summary` riêng.
