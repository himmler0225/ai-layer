# Flow ai-layer (tóm tắt)

**RAG chi tiết (đọc khi nâng cấp):** [RAG-GUIDE.md](./RAG-GUIDE.md)  
**Kiến trúc multi-agent (LangGraph) + thứ tự đọc file:** [ARCHITECTURE.md](./ARCHITECTURE.md)  
**MCP Phase 2 (tool auto-discovery từ data-miner):** [../../docs/MCP-PHASE2-GUIDE.md](../../docs/MCP-PHASE2-GUIDE.md)  
**Refactor audit + lộ trình:** [REFACTOR-AUDIT.md](./REFACTOR-AUDIT.md)

## Stack

- **ai-chatbot** — UI, gửi `task` + block `[Phim đang xem]`
- **ai-layer** — agent OpenAI, tool, ingest, RAG search
- **data-miner** — crawl YouTube/TikTok
- **Supabase Postgres** (`DATABASE_URL`) — dữ liệu app (video, comments, movies, RAG)
- **Supabase REST** — auth + `config` (có thể override prompt prod)
- **Ingest ngầm** — background task trong-process (không broker), spawn từ `producer/publisher.py`

Review social chỉ từ YouTube/TikTok. Giá FPT/Tiki chatbot nhét vào prompt, không crawl TMĐT.

---

## Đọc — user hỏi → trả lời

```
chatbot POST /agent/run/stream
  → run_agent_multi_stream → supervisor chọn 1..N domain (youtube/tiktok/movies)
  → Send() fan-out song song, mỗi worker: bootstrap_agent → prepare_tools_for_task
       (platform filter → movie context → RAG cache-first) → LLM tool loop riêng
  → RAG L1/L2/L3 hoặc crawl data-miner
  → schedule_tool_ingest (nền, mỗi tool crawl)
  → gộp tool_call_log → synthesize_node → SSE text_delta + tool_start/done (tag worker) + done
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
  → publish() spawn asyncio.create_task (fire-and-forget, trong process API)
  → comments handler
       ├─ FLAT:  comments + video_chunks (embed)
       └─ RAG:   sync_comments_to_movie_rag
            → raw_reviews + merge curated (incremental)
            → summarize: raw≥20 lần đầu; sau đó delta≥50 (xem RAG-GUIDE §6.3)
            → LLM group aspect → aspect_chunks + embed
            → LLM summary → aspect_summaries + embed
```

| Routing key | Handler |
|-------------|---------|
| `comments.upsert` | dual flat + RAG |
| `movie.summarize` | L1/L2 pipeline |
| `chunks.embed` | `video_chunks` flat |

Handler lỗi → log + task dừng (không retry/DLQ — đã bỏ broker, xem RAG-GUIDE §6 cho lộ trình thay bằng Kafka). Chi tiết: [RAG-GUIDE §6](./RAG-GUIDE.md#6-ghi--chi-tiết-từng-bước).

---

## File hay đụng

| Việc | File |
|------|------|
| API stream | `app/api/agent.py` |
| Agent loop + guards | `app/services/agent/core/engine.py`, `core/context.py`, `core/langgraph_runner.py`, `core/langgraph_stream.py`, `graph/`, `guards/` |
| Lọc tool + cache-first | `app/services/agent/tooling/platform.py` |
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
```

Cần: `DATABASE_URL`, `OPENAI_API_KEY`, `RAG_ENABLED=true` (mặc định code là `false` nếu không set), `INGEST_ENABLED=true` (nếu muốn ingest chạy).

**Lộ trình học RAG từng bước:** [RAG-GUIDE §0](./RAG-GUIDE.md#0-lộ-trình-vừa-làm-vừa-học).

**Alembic:** DB mới `alembic upgrade head` · DB cũ `alembic stamp head` (một lần).

---

## Lỗi LLM hay gặp

Message kiểu *"An error occurred while processing your request... req_xxx"* là **500 phía upstream**, không phải bug Python.

Đã xử lý trong code:

1. **Thu hẹp tool** khi có `[Phim đang xem]` (~27 → ~9) hoặc cache-first (~4 RAG)
2. **Retry tại provider** (`providers.py` `_with_retry`) — không lặp retry ở `langgraph_stream.py` / `synthesis.py`
3. **Synthesis stream fallback** — gateway lỗi SSE (vd. xah + opus) → non-stream `run_synthesis`
4. **Message tiếng Việt** + log `request_id` — `llm_errors.py`

---

## Ghi chú

- Mongo đã bỏ hẳn.
- Supabase `config` ghi đè `AGENT_SYSTEM` — prod khác local là do đó.
- Python 3.14+: dùng cú pháp hiện đại (`str | None`, `list[str]`, `dict[str, Any]`).
- SSE: `text_delta`, `status`, `tool_start`/`tool_done` (có `detail_vi`), `data_preview`, `done` — không còn event `review_summary` riêng.
