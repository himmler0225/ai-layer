# Flow ai-layer (tóm tắt)

**RAG chi tiết (đọc khi nâng cấp):** [RAG-GUIDE.md](./RAG-GUIDE.md)

## Stack

- **ai-chatbot** — UI, gửi `task` + block `[Sản phẩm đang xem]`
- **ai-layer** — agent OpenAI, tool, ingest, RAG search
- **data-miner** — crawl YouTube/TikTok
- **Postgres** — hết dữ liệu app (video, comments, products, RAG)
- **Supabase** — auth + `config` (có thể override prompt prod)
- **RabbitMQ** — job ingest nền

Review social chỉ từ YouTube/TikTok. Giá FPT/Tiki chatbot nhét vào prompt, không crawl TMĐT.

---

## Đọc — user hỏi → trả lời

```
chatbot POST /agent/run/stream
  → bootstrap_agent → prepare_tools_for_task
       (platform filter → product context → RAG cache-first)
  → OpenAI Responses API (vòng lặp tool, loop.py)
  → RAG L1/L2/L3 hoặc crawl data-miner
  → schedule_tool_ingest (nền, mỗi tool crawl)
  → SSE text_delta + status + done
```

**Task từ chatbot** khi bấm AI Review:

```
[Sản phẩm đang xem]
Tên: iPhone 17 Pro
product_id: iphone-17-pro
Giá: ...
[Câu hỏi hiện tại]
...
```

### Chiến lược agent (RAG)

1. **Cache-first** — nếu `product_has_knowledge` + `is_product_fresh` → chỉ tool RAG (bỏ crawl)
2. **L1** `search_product_summary` → `coverage` sufficient / partial / none
3. **L2** `search_aspect_evidence` khi partial
4. **L3** `get_raw_reviews` khi cần nguyên văn
5. **Crawl** YouTube/TikTok khi `none` hoặc chưa có data

| Tầng | Bảng | Tool | Vector |
|------|------|------|--------|
| L1 | `aspect_summaries` | `search_product_summary` | Có |
| L2 | `aspect_chunks` | `search_aspect_evidence` | Có |
| L3 | `raw_reviews` | `get_raw_reviews` | Không (sort likes) |

Vector search SQL: `repositories/aspect_summaries.py`, `aspect_chunks.py`  
Orchestration + coverage: `rag/search.py`

---

## Ghi — crawl → RAG

Hai track song song mỗi batch comment (`handlers/comments.py`):

```
tool crawl OK
  → schedule_tool_ingest (product_hint từ task)
  → RabbitMQ
  → comments handler
       ├─ FLAT:  comments + video_chunks (embed)
       └─ RAG:   sync_comments_to_product_rag
            → raw_reviews + merge curated (incremental)
            → (raw≥20, delta≥50) job summarize
            → LLM group aspect → aspect_chunks + embed
            → LLM summary → aspect_summaries + embed
```

| Routing key | Queue | Handler |
|-------------|-------|---------|
| `comments.upsert` | `ingest.comments` | dual flat + RAG |
| `product.summarize` | `ingest.summarize` | L1/L2 pipeline |
| `chunks.embed` | `ingest.embed` | `video_chunks` flat |

Consumer retry 3 lần → DLQ. Chi tiết: [RAG-GUIDE §6](./RAG-GUIDE.md#6-ghi--chi-tiết-từng-bước).

---

## File hay đụng

| Việc | File |
|------|------|
| API stream | `app/api/agent.py` |
| Agent loop | `app/services/agent/loop.py`, `runner.py`, `stream.py` |
| Lọc tool + cache-first | `app/services/agent/platform.py` |
| RAG đủ/fresh? | `app/rag/knowledge.py` |
| Product name từ task | `app/rag/product_hint.py` |
| L1/L2/L3 query | `app/rag/search.py` |
| Vector SQL | `repositories/aspect_summaries.py`, `aspect_chunks.py` |
| Tool RAG | `tools/rag_definitions.py`, `executor.py` |
| Ingest schedule | `ingest/dispatcher/schedule.py`, `routes.py` |
| RAG sync | `ingest/processing/rag_sync.py` |
| Summarize | `ingest/handlers/summarize.py` |
| Curate | `ingest/processing/curate.py`, `quality.py` |
| Lỗi OpenAI | `app/utils/openai_errors.py` |
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

Cần: `DATABASE_URL`, `OPENAI_API_KEY`, `RAG_ENABLED=true`, `RABBITMQ_URL` (nếu ingest).

**Alembic:** DB mới `alembic upgrade head` · DB cũ `alembic stamp head` (một lần).

---

## Lỗi OpenAI hay gặp

Message kiểu *"An error occurred while processing your request... req_xxx"* là **500 phía OpenAI**, không phải bug Python.

Đã xử lý trong code:

1. **Thu hẹp tool** khi có `[Sản phẩm đang xem]` (~27 → ~9) hoặc cache-first (~4 RAG)
2. **Retry 1 lần** stream/sync nếu 5xx/timeout — `openai_responses.py`
3. **Message tiếng Việt** + log `request_id` — `openai_errors.py`

---

## Ghi chú

- Mongo đã bỏ hẳn.
- Supabase `config` ghi đè `AGENT_SYSTEM` — prod khác local là do đó.
- Python 3.9: `from __future__ import annotations` ở file dùng `str | None`.
- SSE: `text_delta`, `status`, `tool_start`/`tool_done` (có `detail_vi`), `data_preview`, `done` — không còn event `review_summary` riêng.
