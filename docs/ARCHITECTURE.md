# Kiến trúc & luồng logic — ai-layer

Tài liệu định hướng: **đọc file nào trước để hiểu toàn bộ repo**, không phải tài liệu API. Chi tiết từng mảng đã có ở [FLOW.md](./FLOW.md), [RAG-GUIDE.md](./RAG-GUIDE.md), [LANGGRAPH-GUIDE.md](./LANGGRAPH-GUIDE.md) — doc này là bản đồ tổng để biết lúc nào nên mở file nào.

---

## 1. ai-layer là gì, nằm ở đâu

```
ai-chatbot (Next.js)
     │  X-API-Key
     ▼
ai-layer ── agent loop ──► data-miner (crawl YouTube/TikTok)
     │
     ├─ Supabase Postgres   chat, video cache, movies, RAG vectors
     ├─ Redis               auth + history cache
     ├─ in-process ingest   background task (comments → RAG → summarize)
     └─ Supabase REST       Auth, config runtime (AI_MODELS, prompts, rate limit...)
```

ai-layer nhận 1 câu hỏi tiếng Việt/Anh về phim → LLM tự quyết định gọi tool nào (crawl YouTube/TikTok qua data-miner, tra catalog phim, hoặc tra RAG cache) → tổng hợp thành câu trả lời. Không tự crawl — luôn qua `data-miner`.

---

## 2. Bản đồ thư mục — biết cái gì nằm ở đâu

| Thư mục | Vai trò |
|---|---|
| `app/api/` | FastAPI router, mỏng — chỉ parse request rồi gọi vào `services/agent` |
| `app/services/agent/` | **Trái tim của repo** — xem mục 4 |
| `app/services/` (top-level) | `enricher.py`/`enricher_collect.py` (build response cuối cho client), `prompts.py` (proxy đọc prompt từ Supabase), `health.py`, `review_summarizer.py` |
| `app/tools/` | Định nghĩa tool cho LLM (`*_definitions.py`) + `executor.py` (dispatch tên tool → hàm thật) + `handlers/` (gọi `data-miner`) |
| `app/clients/data_miner/` | HTTP client gọi sang service `data-miner` |
| `app/rag/` | Vector search (`search.py`), cache-fresh check (`knowledge.py`), tách tên phim từ câu hỏi (`movie_hint.py`) |
| `app/ingest/` | Pipeline nền: comment/transcript → chunk → embed → RAG. Chạy in-process (không còn RabbitMQ, xem [RAG-GUIDE.md §6](./RAG-GUIDE.md#6-ghi--chi-tiết-từng-bước)) |
| `app/mcp/` | Backend thay thế cho `tools/definitions.py` — lấy catalog tool động từ data-miner qua MCP (`AGENT_CRAWL_BACKEND=mcp`) |
| `app/repositories/` | Query Postgres thô (SQLAlchemy), 1 file/bảng |
| `app/ai/` | Adapter LLM đa provider (OpenAI-compatible chat completions), đọc model active từ Supabase `AI_MODELS` |
| `app/config/` | `settings.py` (env), `remote.py` (load config Supabase), `loader.py`/`defaults.py` (schema) |

---

## 3. Đọc từ đâu để hiểu flow — thứ tự khuyến nghị

Đừng đọc theo thứ tự alphabet thư mục — hầu như chắc chắn lạc. Đọc theo đúng đường đi của 1 request thật:

### 3.1 Path chính (đang chạy production — đọc trước)
1. **`app/api/agent.py`** — 2 route (`/agent/run`, `/agent/run/stream`), điểm vào duy nhất. Nhìn nhánh `AGENT_BACKEND` để biết request đi legacy hay multi-agent.
2. **`app/services/agent/core/context.py`** — `ctx` là gì (dict tự chứa: `session_id, task, system, tools, max_iter, input_items, tool_call_log`). Đọc `bootstrap_agent`, `begin_tool_round`, `complete_tool_round`. Đây là state mọi thứ khác thao tác lên.
3. **`app/services/agent/core/iterate.py`** — vòng lặp thật (`run_agent_events`), dùng chung cho stream/non-stream. Đây là 90% logic của agent legacy.
4. **`app/services/agent/tooling/platform.py`** — `prepare_tools_for_task()`: lọc tool theo platform/catalog/review/RAG-cache trước khi đưa cho LLM.
5. **`app/services/agent/guards/budget.py`** — khi nào ép dừng gọi tool, chuyển sang tổng hợp câu trả lời.
6. **`app/services/agent/synthesis/generate.py`** — bước cuối, gộp `tool_call_log` thành 1 prompt, gọi LLM viết câu trả lời.
7. **`app/services/agent/tooling/dispatch.py`** — nơi tool thật sự được `execute_tool()`, và bắn `schedule_tool_ingest()` (nền, không chặn response) để đẩy dữ liệu vào RAG.

Đọc xong 7 file này là hiểu được 1 request thường đi qua đâu.

### 3.2 Path multi-agent (LangGraph, sau cờ `AGENT_BACKEND=multi`, chỉ `/agent/run`)
8. **`app/services/agent/graph/build.py`** — hình dạng graph: `supervisor → Send() fan-out → {youtube,tiktok,movies}_worker → synthesize → finalize`.
9. **`app/services/agent/graph/supervisor.py`** — chọn domain nào chạy (lọc xác định trước, không tốn LLM call cho case rõ ràng).
10. **`app/services/agent/graph/workers.py`** — `run_worker_loop()`, vòng lặp tool-calling riêng mỗi domain — **không dùng chung code với `iterate.py`** (cố ý, xem §5).
11. **`app/services/agent/graph/nodes.py`** — các node LangGraph, mỏng, gọi lại `workers.py`/`synthesis/generate.py`.
12. **`app/services/agent/core/langgraph_runner.py`** — entrypoint `run_agent_multi()`, build state ban đầu, `graph.ainvoke()`.

### 3.3 RAG / ingest nền (chạy độc lập với request, không chặn user)
13. **`app/ingest/handlers/router.py`** — `dispatch()`, map `routing_key` → handler.
14. **`app/ingest/handlers/comments.py`**, **`transcript.py`**, **`embed.py`**, **`summarize.py`** — từng bước của pipeline, tự chain nhau qua `publish()`.
15. **`app/rag/search.py`** — khi user hỏi lại, đọc L1→L2→L3 (`aspect_summaries` → `aspect_chunks` → `raw_reviews`).

Chi tiết đầy đủ pipeline này: [RAG-GUIDE.md](./RAG-GUIDE.md).

---

## 4. Luồng request end-to-end (rút gọn)

**Legacy** (`AGENT_BACKEND` rỗng — mặc định):
```
POST /agent/run
  → resolve_tool_set(body.tools)         # app/tools/definitions.py
  → run_agent() → run_agent_events()     # core/runner.py → core/iterate.py
      → bootstrap_agent()                # prepare_tools_for_task lọc tool
      → [LLM gọi tool] × N vòng          # begin_tool_round/complete_tool_round
          → execute_tool() → data-miner  # tools/executor.py → clients/data_miner/
          → schedule_tool_ingest() nền   # → ingest pipeline, không chặn response
      → run_synthesis()                  # gộp tool_call_log → câu trả lời
      → enrich_agent_result()            # app/services/enricher.py → response cuối
```

**Multi-agent** (`AGENT_BACKEND=multi`):
```
POST /agent/run
  → run_agent_multi()                    # core/langgraph_runner.py
      → supervisor_node                  # graph/supervisor.py: chọn 1..N domain
      → Send() fan-out song song         # graph/build.py, LangGraph tự chạy concurrent
          → worker_node(domain=youtube)  ┐
          → worker_node(domain=tiktok)   ┤ mỗi worker: ctx RIÊNG, tool list RIÊNG,
          → worker_node(domain=movies)   ┘ gọi bootstrap_agent() + run_worker_loop()
      → gộp tool_call_log (reducer)      # chỉ field này được merge — xem §5
      → synthesize_node → finalize_node  # tái dùng run_synthesis/finish_agent y hệt legacy
```

---

## 5. Bẫy đã gặp — nên biết trước khi sửa tiếp

**LangGraph âm thầm drop field không khai báo trong `AgentState`.** Không có lỗi, không exception — field biến mất không dấu vết. Gặp 2 lần trong lúc build: field `result` (finalize_node trả về nhưng chưa khai trong `TypedDict`) và `requested_tool_set` (set vào state ban đầu nhưng chưa khai). Bài học: **mọi key một node trả về hoặc caller set vào `initial_state` đều phải có mặt trong `graph/state.py:AgentState`**, kể cả khi không cần reducer.

**Chỉ `tool_call_log` có reducer (`operator.add`).** Worker không được trả field khác về state chung (`tools`, `input_items`...) — sẽ crash `InvalidUpdateError` khi 2 worker ghi đồng thời. Mỗi worker giữ `ctx` hoàn toàn riêng tư trong `run_worker_loop`, chỉ trả đúng 1 field ra ngoài.

**`iterate.py` và `workers.py` cố ý trùng logic** (vòng gọi LLM + retry, ~40 dòng). Không rút gọn chung — `iterate.py` gắn chặt với SSE `yield`, sửa để dùng chung sẽ đụng vào loop legacy đang chạy production. Chấp nhận trùng lặp nhỏ, khoanh vùng 1 file mới, không sửa file cũ.

**Model LLM đang active (`kira-3.5-flash`) không tuân `tool_choice="required"` một cách nhất quán.** Đôi khi chỉ emit dòng scratchpad nội bộ (`intent=REVIEW, slots={...}`) rồi dừng thay vì gọi tool. `graph/workers.py` có xử lý: parse `last_movie_name` từ dòng đó, tự dựng tool call fallback (`_build_search_fallback`) — xem comment trong file. Nếu đổi provider (Supabase `AI_MODELS.is_active`), cơ chế này vẫn chạy vô hại (chỉ kích hoạt khi thật sự cần).

**`_MOVIE_CORE`** (`tooling/platform.py`) là danh sách tool dùng khi narrow theo "ý định review" — từng thiếu tool TikTok (chỉ có YouTube + RAG), khiến bất kỳ tool list nào chỉ toàn TikTok bị lọc còn gần như rỗng. Đã fix, nhưng nếu thêm domain mới (vd Instagram) thì nhớ update set này.

---

## 6. Trạng thái multi-agent (2026-08)

- **Đã xong (Phase 1):** supervisor routing xác định, fan-out song song thật qua `Send()`, 3 worker domain, merge `tool_call_log`, synthesis dùng chung code path với legacy. Chạy sau `/agent/run` + `AGENT_BACKEND=multi`.
- **Chưa làm:**
  - `/agent/run/stream` + `core/langgraph_stream.py` (Phase 3, SSE cho multi-agent) — route stream hiện 100% đi legacy.
  - LLM classifier cho case supervisor không xác định được domain bằng heuristic (hiện tại: mặc định chọn cả 3 domain, an toàn nhưng tốn worker không cần thiết).
  - Mặc định `AGENT_BACKEND` vẫn là legacy (`single`) — multi-agent chỉ bật khi set env, chưa cutover.
- **Ngoài scope ai-layer:** `data-miner` occasionally trả `403 Forbidden` khi crawl YouTube — hạ tầng proxy/anti-bot riêng, không phải bug ở đây.

---

## 7. Đọc thêm

- [FLOW.md](./FLOW.md) — luồng end-to-end chatbot → ai-layer → data-miner, tóm tắt hơn doc này nhưng có phần "chạy dev".
- [RAG-GUIDE.md](./RAG-GUIDE.md) — chi tiết pipeline ingest + RAG L1/L2/L3, có checklist debug.
- [LANGGRAPH-GUIDE.md](./LANGGRAPH-GUIDE.md) — khái niệm LangGraph (state/node/edge) + lịch sử quyết định đổi từ đơn-chain sang supervisor+worker.
- [../../docs/MCP-PHASE2-GUIDE.md](../../docs/MCP-PHASE2-GUIDE.md) — backend `AGENT_CRAWL_BACKEND=mcp`, tool catalog động từ data-miner.
