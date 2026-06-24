# Hướng dẫn triển khai RAG (tự làm)

Tài liệu này mô tả **phần còn lại** của pipeline RAG trong `ai-layer`. Phần **ghi dữ liệu (ingest)** đã có sẵn; bạn sẽ tự implement phần **đọc (retrieval)** và tích hợp vào agent.

---

## Tổng quan

### Đã có sẵn

```
Agent gọi crawl tool (youtube_search, comments, transcript…)
    → dispatcher/schedule.py
    → RabbitMQ (exchange: knowledge.ingest)
    → ingest-worker (python -m app.ingest)
    → handlers/ → videos, comments
    → processing/ → chunk + embed OpenAI
    → video_chunks (pgvector)
```

| File / module | Vai trò |
|---|---|
| `app/ingest/` | Toàn bộ pipeline ghi |
| `app/repositories/videos.py` | CRUD video |
| `app/repositories/comments.py` | CRUD comment |
| `app/repositories/chunks.py` | **Chỉ có `upsert_chunks`** — chưa có search |
| `app/repositories/search_cache.py` | **Chỉ ghi** — `get_search_cache` chưa được dùng |
| `app/tools/definitions.py` | Chỉ có crawl tools — **chưa có `knowledge_search`** |
| `app/db/models/video.py` | Bảng `video_chunks` + HNSW index |

### Chưa có (bạn sẽ làm)

```
User hỏi
    → knowledge_search (vector search)
    → nếu đủ dữ liệu → trả lời từ DB
    → nếu thiếu / cũ → crawl như hiện tại → ingest nền
```

---

## Kiến trúc mục tiêu

```mermaid
flowchart TB
    subgraph read [Read path — cần làm]
        Q[User query] --> KS[knowledge_search tool]
        KS --> E[Embed query]
        E --> VS[Vector search video_chunks]
        VS --> R[Top-K chunks + metadata]
    end

    subgraph write [Write path — đã có]
        T[Crawl tools] --> MQ[RabbitMQ]
        MQ --> W[ingest-worker]
        W --> DB[(Postgres + pgvector)]
    end

    subgraph smart [Cache-first — cần làm]
        S[youtube_search] --> C{Cache đủ?}
        C -->|Có| DB
        C -->|Không| T
    end

    R --> Agent[Agent tổng hợp câu trả lời]
    DB --> VS
```

---

## Bước 0 — Checklist môi trường

Trước khi code RAG, xác nhận các điều kiện sau:

- [ ] PostgreSQL có extension **pgvector**
- [ ] `RABBITMQ_URL` đúng trong `ai-layer/.env` (biến phải là `RABBITMQ_URL`, không phải `ABBITMQ_URL`)
- [ ] RabbitMQ Management UI login được (`ingest` / `changeme` hoặc user bạn đã tạo)
- [ ] **ingest-worker** đang chạy
- [ ] `OPENAI_API_KEY` có trong Supabase config hoặc env (worker cần để embed)
- [ ] `INGEST_ENABLED=true`

### Env cần có (`.env`)

```env
DATABASE_URL=postgresql://...
RABBITMQ_URL=amqp://ingest:changeme@localhost:5672/
RABBITMQ_EXCHANGE=knowledge.ingest
INGEST_ENABLED=true
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536

# Thêm sau khi implement RAG:
RAG_ENABLED=true
RAG_TOP_K=8
RAG_MIN_SCORE=0.65
CACHE_TTL_DAYS=7
```

---

## Bước 1 — Cài pgvector

RAG **không chạy** nếu Postgres thiếu pgvector. Log sẽ có:

```
[db] pgvector unavailable — video_chunks table skipped
```

### Cách A — Dùng Docker Compose (khuyến nghị)

Trong `/Users/mypc/Youtube/docker-compose.yml` đã có service `postgres` image `pgvector/pgvector:pg16`.

```bash
cd /Users/mypc/Youtube

# Dừng postgres cũ nếu đang chiếm port 5432
docker stop postgres-db   # hoặc container postgres bạn đang dùng

docker compose up -d postgres
```

Cập nhật `DATABASE_URL` trong `ai-layer/.env`:

```env
DATABASE_URL=postgresql://ai_user:K9xmP2vQz!8wRtL@localhost:5432/ai_layer_db
```

### Cách B — Giữ Postgres hiện tại

Cài extension pgvector trên server Postgres 16, rồi restart ai-layer để `init_db()` chạy lại.

### Verify

```bash
# Khởi động ai-layer, xem log:
# [db] tables initialized vector=True

# Hoặc query trực tiếp:
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;"
psql "$DATABASE_URL" -c "\d video_chunks"
```

Bảng `video_chunks` phải có cột `embedding vector(1536)`.

---

## Bước 2 — Chạy ingest-worker

Worker consume queue và ghi DB. Không có worker → crawl vẫn chạy nhưng **không có vector**.

### Docker

```bash
cd /Users/mypc/Youtube
docker compose up -d rabbitmq ingest-worker
docker logs -f ingest-worker
```

### Local dev

```bash
cd ai-layer
pip install -r requirements.txt
python -m app.ingest
```

### Verify queue

```bash
curl -H "X-API-Key: YOUR_API_KEY" http://localhost:8001/ai/admin/ingest/queues
```

Sau khi agent crawl một lần, queue depth về 0 và DB có dữ liệu.

---

## Bước 3 — Test ingest end-to-end

1. Gọi agent với câu hỏi review sản phẩm (vd: "review iPhone 16").
2. Agent sẽ gọi `youtube_search` → `youtube_get_comments_batch` → `youtube_get_transcript_batch`.
3. Kiểm tra DB:

```sql
SELECT COUNT(*) FROM videos;
SELECT COUNT(*) FROM comments;
SELECT COUNT(*) FROM video_chunks;
SELECT COUNT(*) FROM video_chunks WHERE embedding IS NOT NULL;
SELECT COUNT(*) FROM search_cache;
```

Nếu `video_chunks` = 0:

- Worker có chạy không?
- Log worker có lỗi OpenAI embed không?
- `comments` handler có chạy sau `video.upsert` không? (worker xử lý song song — thường OK vì handler tự `upsert_video` nếu thiếu)

---

## Bước 4 — Retrieval layer

Tạo module mới, gợi ý cấu trúc:

```
app/
  rag/
    __init__.py
    search.py      # search_similar_chunks()
    README.md
  repositories/
    chunks.py      # thêm search_similar() hoặc để logic trong rag/search.py
```

### 4.1 Thêm settings

File: `app/config/settings.py`

```python
RAG_ENABLED: bool = os.getenv("RAG_ENABLED", "true").lower() == "true"
RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "8"))
RAG_MIN_SCORE: float = float(os.getenv("RAG_MIN_SCORE", "0.65"))
CACHE_TTL_DAYS: int = int(os.getenv("CACHE_TTL_DAYS", "7"))
```

### 4.2 Hàm search vector

File: `app/rag/search.py`

Logic:

1. Embed `query` bằng `app.ingest.processing.embeddings.embed_texts([query])`
2. Query Postgres cosine distance trên `video_chunks.embedding`
3. Join `videos` lấy `title`, `url`, `author`
4. Lọc theo `platform`, `video_ids`, `chunk_type` (metadata JSONB)
5. Trả list dict: `content`, `score`, `video_id`, `url`, `title`, `chunk_type`, `metadata`

**SQL tham khảo** (cosine similarity = `1 - distance`):

```sql
SELECT
    c.id,
    c.video_id,
    c.platform,
    c.content,
    c.metadata,
    v.title,
    v.url,
    1 - (c.embedding <=> :query_vector) AS score
FROM video_chunks c
JOIN videos v ON v.id = c.video_id
WHERE c.embedding IS NOT NULL
  AND (:platform IS NULL OR c.platform = :platform)
ORDER BY c.embedding <=> :query_vector
LIMIT :top_k;
```

**SQLAlchemy async** — dùng `text()` + bind param vector, hoặc pgvector operators qua raw SQL.

**Lọc score sau query:**

```python
results = [r for r in rows if r["score"] >= settings.RAG_MIN_SCORE]
```

**Dedupe (tùy chọn):** giữ chunk score cao nhất mỗi `video_id` để đa dạng nguồn.

### 4.3 Hàm bọc cấp cao

```python
async def knowledge_search(
    query: str,
    *,
    platform: str | None = None,
    top_k: int | None = None,
) -> dict:
    """
    Trả về:
    {
        "query": "...",
        "found": true/false,
        "chunks": [...],
        "coverage": "sufficient" | "partial" | "none",
    }
    """
```

Quy tắc `coverage`:

| Điều kiện | coverage |
|---|---|
| ≥ 3 chunk, score ≥ min, có cả comment + transcript | `sufficient` |
| 1–2 chunk hoặc score trung bình thấp | `partial` |
| 0 chunk | `none` |

Agent dùng `coverage` để quyết định có crawl thêm không.

---

## Bước 5 — Tool `knowledge_search`

### 5.1 Schema tool

File: `app/tools/definitions.py` — thêm vào `ALL_TOOLS` và `TOOL_SETS`:

```python
{
    "type": "function",
    "name": "knowledge_search",
    "description": (
        "Tìm tri thức đã lưu trong DB (comment + transcript đã embed) theo câu hỏi. "
        "DÙNG TRƯỚC khi crawl khi user hỏi review/sản phẩm/chủ đề đã từng phân tích. "
        "TRẢ VỀ: danh sách đoạn text liên quan kèm video_id, url, score. "
        "Nếu coverage=none hoặc partial → tiếp tục youtube_search + batch comments/transcript."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Câu hỏi hoặc tên sản phẩm/chủ đề"},
            "platform": {
                "type": "string",
                "enum": ["youtube", "tiktok"],
                "description": "Lọc nền tảng (tùy chọn)",
            },
            "top_k": {"type": "integer", "default": 8, "maximum": 20},
        },
        "required": ["query"],
    },
},
```

### 5.2 Executor

File: `app/tools/executor.py`

```python
async def _knowledge_search(inp: Dict) -> Any:
    from app.rag.search import knowledge_search
    return await knowledge_search(
        inp["query"],
        platform=inp.get("platform"),
        top_k=inp.get("top_k"),
    )

_HANDLERS["knowledge_search"] = _knowledge_search
```

Thêm schema vào `_SCHEMAS` (tự động nếu append vào list tools).

### 5.3 Guard khi RAG tắt / pgvector thiếu

```python
if not settings.RAG_ENABLED:
    return {"found": False, "coverage": "none", "reason": "RAG disabled"}
```

---

## Bước 6 — Cache-first (giảm crawl)

Mục tiêu: trước khi gọi data-miner, kiểm tra DB đã có dữ liệu đủ mới chưa.

### 6.1 Search cache

File: `app/repositories/search_cache.py` — `get_search_cache()` đã có.

Tạo helper mới, vd. `app/rag/cache.py`:

```python
async def is_search_fresh(query: str, platform: str) -> bool:
    """Cache còn hạn TTL và video_ids không rỗng."""
    ...

async def videos_have_knowledge(video_ids: list[str], *, min_comments: int = 10) -> bool:
    """Mỗi video có comment/chunk trong DB."""
    ...
```

### 6.2 Wrap executor

Trong `_youtube_search`:

```python
async def _youtube_search(inp: Dict) -> Any:
    keyword = inp["keyword"]
    if settings.RAG_ENABLED:
        cached_ids = await get_search_cache(keyword, "youtube")
        if cached_ids and await is_search_fresh(keyword, "youtube"):
            if await videos_have_knowledge(cached_ids):
                videos = [await get_video(vid) for vid in cached_ids]
                return {"videos": videos, "_from_cache": True}
    return await data_miner.search_youtube(...)
```

Tương tự cho `_youtube_get_comments_batch`:

- Nếu mỗi `video_id` đã có `count_comments(vid) >= max_per_video` → ghép từ `get_comments()` thay vì crawl.

**Lưu ý:** Trả `_from_cache: true` để debug; agent vẫn ingest nếu có dữ liệu mới (dispatcher có thể skip nếu không có thay đổi — tùy chọn phase 2).

### 6.3 TTL

Dùng `search_cache.updated_at` và `videos.updated_at`:

```python
from datetime import datetime, timedelta, timezone

def is_within_ttl(updated_at: datetime, days: int) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return updated_at >= cutoff
```

---

## Bước 7 — Cập nhật agent prompt

File: `app/services/prompts.py` (hoặc Supabase `AGENT_SYSTEM`)

Thêm workflow:

```
Khi user hỏi review / so sánh / ý kiến cộng đồng:

1. knowledge_search(query) — tra tri thức đã lưu
2. Nếu coverage=sufficient → trả lời từ chunks, cite video_id/url
3. Nếu coverage=partial hoặc none:
   a. youtube_search(keyword)
   b. youtube_get_comments_batch(video_ids, sort=top)
   c. youtube_get_transcript_batch(video_ids) — nếu cần nội dung reviewer
4. Tổng hợp: ưu tiên chunk RAG + dữ liệu crawl mới
```

**Iteration đầu (tùy chọn):** Trong `app/services/agent/runner.py`, nếu task chứa từ khóa review và `RAG_ENABLED`, có thể inject kết quả `knowledge_search` vào context trước vòng tool — giảm phụ thuộc model tự chọn tool.

---

## Bước 8 — Enricher & trích dẫn nguồn

File: `app/services/enricher.py`

Khi build response cuối, nếu tool log có `knowledge_search`:

- Parse `chunks[].video_id`, `url`, `title`
- Thêm vào field `sources` / `videos` trong response JSON

User thấy link video nguồn — quan trọng cho trust.

---

## Bước 9 — Admin debug API (khuyến nghị)

File: `app/api/admin.py`

```python
@router.get("/rag/stats")
async def rag_stats(...):
    # COUNT videos, comments, chunks, chunks có embedding

@router.post("/rag/search")
async def rag_search_debug(body: {"query": str, "top_k": int}):
    # Gọi knowledge_search, trả raw chunks + score — không qua agent
```

Giúp debug retrieval mà không cần chạy full agent loop.

---

## Bước 10 — Test plan

| # | Test | Cách verify | Kỳ vọng |
|---|---|---|---|
| 1 | pgvector | `\d video_chunks` | Có cột `embedding` |
| 2 | Ingest | Agent crawl 1 lần | `video_chunks` > 0 |
| 3 | Vector search | `POST /ai/admin/rag/search` | Trả chunk liên quan |
| 4 | knowledge_search tool | Agent hỏi lại cùng sản phẩm | Gọi tool, không crawl |
| 5 | Cache-first | Hỏi lần 2 trong TTL | Log `_from_cache: true` |
| 6 | Hết TTL | Đặt `CACHE_TTL_DAYS=0` test | Crawl lại |
| 7 | RAG tắt | `RAG_ENABLED=false` | Fallback crawl only |

### Query debug hữu ích

```sql
-- Chunk mới nhất
SELECT video_id, left(content, 80), metadata->>'chunk_type', created_at
FROM video_chunks ORDER BY created_at DESC LIMIT 10;

-- Video chưa có chunk
SELECT v.id, v.title FROM videos v
LEFT JOIN video_chunks c ON c.video_id = v.id
WHERE c.id IS NULL;

-- Search cache
SELECT query, platform, jsonb_array_length(video_ids), updated_at
FROM search_cache ORDER BY updated_at DESC LIMIT 10;
```

---

## Thứ tự implement gợi ý

| Phase | Việc | Thời gian ước lượng |
|---|---|---|
| **P1** | pgvector + ingest-worker + verify E2E | 0.5–1 ngày |
| **P2** | `app/rag/search.py` + admin debug search | 1 ngày |
| **P3** | Tool `knowledge_search` + prompt | 0.5 ngày |
| **P4** | Cache-first trong executor | 1 ngày |
| **P5** | Enricher sources + polish | 0.5 ngày |

Làm xong **P2** là đã có RAG cơ bản. **P4** tối ưu chi phí crawl.

---

## Cải tiến sau (optional)

- **Hybrid search:** vector + PostgreSQL full-text (`tsvector`) cho tên sản phẩm chính xác
- **Rerank:** lấy top 20 vector → LLM rerank → top 5
- **Filter `product_hint`:** metadata từ ingest đã gắn hint — lọc khi search
- **Re-embed job:** cron re-embed video cũ khi đổi `EMBEDDING_MODEL`
- **TikTok parity:** đảm bảo `tiktok_search` + comments/transcript cũng vào chunk

---

## File tham chiếu trong repo

| Path | Ghi chú |
|---|---|
| `app/ingest/README.md` | Luồng ingest chi tiết |
| `app/ingest/processing/embeddings.py` | Reuse cho embed query |
| `app/ingest/processing/chunking.py` | Cách chia transcript/comment |
| `app/repositories/chunks.py` | Thêm search ở đây hoặc `app/rag/` |
| `app/repositories/search_cache.py` | Cache-first |
| `app/tools/definitions.py` | Thêm tool schema |
| `app/tools/executor.py` | Thêm handler + cache wrap |
| `app/services/prompts.py` | Workflow RAG cho agent |
| `app/db/models/video.py` | Schema `video_chunks` |
| `docker-compose.yml` | postgres pgvector, ingest-worker |

---

## Troubleshooting

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Login RabbitMQ fail | User `ingest` chưa tạo / sai pass | Tạo user hoặc dùng `guest/guest` trên container cũ |
| `video_chunks` không tồn tại | Thiếu pgvector | Bước 1 |
| Queue tích message | Worker không chạy | Bước 2 |
| Chunk = 0, comments > 0 | Embed lỗi (OpenAI key) | Xem log ingest-worker |
| Search trả rỗng | Chưa ingest hoặc score < min | Hạ `RAG_MIN_SCORE`, crawl trước |
| Agent vẫn crawl mọi lần | Chưa có tool / prompt | Bước 5 + 7 |
| Port 5432 conflict | Postgres cũ vs compose | Dừng container cũ hoặc đổi port |

---

## Liên hệ module

Sau khi làm xong, thêm link trong `README.md` gốc:

```markdown
## RAG
Xem [docs/RAG-GUIDE.md](docs/RAG-GUIDE.md) — hướng dẫn triển khai retrieval + knowledge_search.
```
