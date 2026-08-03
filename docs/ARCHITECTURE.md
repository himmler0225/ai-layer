# Kiến trúc & luồng logic — ai-layer

Tài liệu định hướng: **đọc file nào trước để hiểu toàn bộ repo**, không phải tài liệu API. Chi tiết từng mảng đã có ở [FLOW.md](./FLOW.md), [RAG-GUIDE.md](./RAG-GUIDE.md) — doc này là bản đồ tổng để biết lúc nào nên mở file nào.

---

## 1. ai-layer là gì, nằm ở đâu

```
ai-chatbot (Next.js)
     │  X-API-Key
     ▼
ai-layer ── multi-agent (LangGraph) ──► data-miner (crawl YouTube/TikTok)
     │
     ├─ Supabase Postgres   chat, video cache, movies, RAG vectors
     ├─ Redis               auth + history cache
     ├─ in-process ingest   background task (comments → RAG → summarize)
     └─ Supabase REST       Auth, config runtime (AI_MODELS, prompts, rate limit...)
```

ai-layer nhận 1 câu hỏi tiếng Việt/Anh về phim → supervisor chọn 1..N "worker" theo nền tảng (YouTube/TikTok/movie catalog) → mỗi worker tự gọi tool qua `data-miner` → gộp lại, LLM tổng hợp thành câu trả lời. Không tự crawl — luôn qua `data-miner`.

---

## 2. Bản đồ thư mục — biết cái gì nằm ở đâu

| Thư mục | Vai trò |
|---|---|
| `app/api/` | FastAPI router, mỏng — chỉ parse request rồi gọi vào `services/agent` |
| `app/services/agent/` | **Trái tim của repo** — xem mục 3-4 |
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

### 3.1 Điểm vào + state dùng chung
1. **`app/api/agent.py`** — 2 route (`/agent/run` non-stream, `/agent/run/stream` SSE), điểm vào duy nhất. Cả 2 đều gọi thẳng LangGraph, không còn nhánh backend nào khác.
2. **`app/services/agent/core/context.py`** — `ctx` là gì (dict tự chứa: `session_id, task, system, tools, max_iter, input_items, tool_call_log`). Đọc `bootstrap_agent`, `begin_tool_round`, `complete_tool_round` — mỗi worker dựng 1 `ctx` riêng từ đây.
3. **`app/services/agent/domains.py`** — `DOMAINS`: nguồn duy nhất cho danh sách nền tảng (youtube/tiktok/movies), mỗi entry có `tool_set`, `role_prompt`, `search_tool`, `capabilities`, `mention_re`. Thêm/xoá nền tảng chỉ sửa file này.

### 3.2 LangGraph — supervisor + worker
4. **`app/services/agent/graph/build.py`** — hình dạng graph: `supervisor → Send() fan-out → {domain}_worker → synthesize → finalize`.
5. **`app/services/agent/graph/supervisor.py`** — `classify_workers_deterministic()`: chọn domain nào chạy, suy ra hoàn toàn từ `DOMAINS` (không hard-code tên nền tảng).
6. **`app/services/agent/graph/workers.py`** — `run_worker_loop()`: vòng lặp tool-calling riêng mỗi domain (LLM call + retry + fallback), độc lập với domain khác — xem §5 vì sao không dùng chung 1 hàm.
7. **`app/services/agent/graph/nodes.py`** — các node LangGraph: `worker_node` (dùng chung cho mọi domain), `synthesize_node` (stream text qua `get_stream_writer()`), `finalize_node`.
8. **`app/services/agent/core/langgraph_runner.py`** / **`langgraph_stream.py`** — entrypoint `run_agent_multi()` (`.ainvoke()`) và `run_agent_multi_stream()` (`.astream(stream_mode=["updates","custom"])` → map ra SSE).

### 3.3 Bên trong 1 worker (tái dùng từ trước khi có multi-agent)
9. **`app/services/agent/tooling/platform.py`** — `prepare_tools_for_task()`: lọc tiếp tool trong domain (catalog/review/RAG-cache); `detect_platform()`/`filter_tools_by_platform()` cũng suy từ `DOMAINS`.
10. **`app/services/agent/guards/budget.py`** — khi nào ép dừng gọi tool, chuyển sang tổng hợp câu trả lời (`tool_round_action`).
11. **`app/services/agent/synthesis/generate.py`** — bước cuối, gộp `tool_call_log` thành 1 prompt, stream câu trả lời.
12. **`app/services/agent/tooling/dispatch.py`** — nơi tool thật sự được `execute_tool()`, và bắn `schedule_tool_ingest()` (nền, không chặn response) để đẩy dữ liệu vào RAG.

### 3.4 RAG / ingest nền (chạy độc lập với request, không chặn user)
13. **`app/ingest/handlers/router.py`** — `dispatch()`, map `routing_key` → handler.
14. **`app/ingest/handlers/comments.py`**, **`transcript.py`**, **`embed.py`**, **`summarize.py`** — từng bước của pipeline, tự chain nhau qua `publish()`.
15. **`app/rag/search.py`** — khi user hỏi lại, đọc L1→L2→L3 (`aspect_summaries` → `aspect_chunks` → `raw_reviews`).

Chi tiết đầy đủ pipeline này: [RAG-GUIDE.md](./RAG-GUIDE.md).

---

## 4. Luồng request end-to-end (rút gọn)

```
POST /agent/run  (non-stream)                POST /agent/run/stream (SSE)
  → run_agent_multi()                          → run_agent_multi_stream()
      graph.ainvoke(initial_state)                  graph.astream(state, stream_mode=["updates","custom"])
                    │                                              │
                    ▼                                              ▼
       supervisor_node (graph/supervisor.py)      chọn 1..N domain, suy từ DOMAINS
                    │
                    ▼
       Send() fan-out song song (graph/build.py) — LangGraph tự chạy concurrent
           worker_node(domain=youtube)  ┐
           worker_node(domain=tiktok)   ┤ mỗi worker: ctx RIÊNG, tool list RIÊNG
           worker_node(domain=movies)   ┘ (bootstrap_agent() + run_worker_loop())
                    │
                    ▼
       gộp tool_call_log (reducer operator.add) — field DUY NHẤT được merge, xem §5
                    │
                    ▼
       synthesize_node — iter_synthesis_deltas(), mỗi delta đẩy qua get_stream_writer()
           (no-op nếu gọi qua ainvoke; thành SSE text_delta thật nếu gọi qua astream)
                    │
                    ▼
       finalize_node — finish_agent() → response cuối (giống hệt 2 route)
```

Với route stream, `run_agent_multi_stream()` còn dịch `updates` event (mỗi khi 1 node xong) thành SSE `tool_start`/`tool_done`/`data_preview` — gắn tag `worker` để client biết event đến từ domain nào, cho phép hiện đồng thời "đang tra cứu YouTube..." / "đang tra cứu TikTok...".

---

## 5. Bẫy đã gặp — nên biết trước khi sửa tiếp

**LangGraph âm thầm drop field không khai báo trong `AgentState`.** Không có lỗi, không exception — field biến mất không dấu vết. Gặp 2 lần trong lúc build: field `result` (finalize_node trả về nhưng chưa khai trong `TypedDict`) và `requested_tool_set` (set vào state ban đầu nhưng chưa khai). Bài học: **mọi key một node trả về hoặc caller set vào `initial_state` đều phải có mặt trong `graph/state.py:AgentState`**, kể cả khi không cần reducer.

**Chỉ `tool_call_log` có reducer (`operator.add`).** Worker không được trả field khác về state chung (`tools`, `input_items`...) — sẽ crash `InvalidUpdateError` khi 2 worker ghi đồng thời. Mỗi worker giữ `ctx` hoàn toàn riêng tư trong `run_worker_loop`, chỉ trả đúng 1 field ra ngoài.

**`get_stream_writer()` an toàn gọi vô điều kiện.** Đã verify thực nghiệm: khi node chạy qua `.ainvoke()` (không stream), writer là no-op thật (không exception, không side-effect); khi chạy qua `.astream(stream_mode="custom")`, mỗi lần gọi writer xuất hiện thành 1 chunk. Nhờ vậy `synthesize_node` chỉ cần **1 code path** cho cả `run_agent_multi` lẫn `run_agent_multi_stream`, không phải branch theo caller.

**`run_worker_loop()` (graph/workers.py) không dùng chung code với bất kỳ vòng lặp nào khác** — nó tự implement LLM-call + retry (~50 dòng), không tái dùng qua kế thừa/composition với node khác. Lý do: mỗi worker cần `ctx` hoàn toàn riêng tư (không global state), và logic retry/fallback đặc thù cho việc "chỉ thu thập dữ liệu, không tự trả lời" (khác với 1 agent chat thông thường).

**Model LLM đang active (`kira-3.5-flash`) không tuân `tool_choice="required"` một cách nhất quán.** Đôi khi chỉ emit dòng scratchpad nội bộ (`intent=REVIEW, slots={...}`) rồi dừng thay vì gọi tool. `graph/workers.py` có xử lý: parse `last_movie_name` từ dòng đó, tự dựng tool call fallback (`_build_search_fallback`) — xem comment trong file. Nếu đổi provider (Supabase `AI_MODELS.is_active`), cơ chế này vẫn chạy vô hại (chỉ kích hoạt khi thật sự cần).

**`domains.py`'s `DOMAINS`** là nguồn duy nhất cho tên nền tảng — `tooling/platform.py`, `graph/supervisor.py`, `graph/build.py`, `graph/nodes.py` đều suy từ đây (`DOMAIN_IDS`, `DOMAIN_BY_ID`, `capabilities`, `mention_re`). Thêm domain mới (vd Instagram): thêm 1 entry vào `DOMAINS` + tool definitions riêng (`app/tools/`) + key trong `TOOL_SETS` — không cần sửa logic routing ở nơi khác.

---

## 6. Trạng thái (2026-08)

- **LangGraph là đường duy nhất** cho cả `/agent/run` và `/agent/run/stream` — không còn loop cũ, không còn cờ backend nào để chọn.
- **Chưa làm:** LLM classifier cho case supervisor không xác định được domain bằng heuristic (hiện tại: mặc định chọn cả 3 domain, an toàn nhưng tốn worker không cần thiết).
- **Ngoài scope ai-layer:** `data-miner` occasionally trả `403 Forbidden` khi crawl YouTube — hạ tầng proxy/anti-bot riêng, không phải bug ở đây.

---

## 7. Đọc thêm

- [FLOW.md](./FLOW.md) — luồng end-to-end chatbot → ai-layer → data-miner, tóm tắt hơn doc này nhưng có phần "chạy dev".
- [RAG-GUIDE.md](./RAG-GUIDE.md) — chi tiết pipeline ingest + RAG L1/L2/L3, có checklist debug.
- [../../docs/MCP-PHASE2-GUIDE.md](../../docs/MCP-PHASE2-GUIDE.md) — backend `AGENT_CRAWL_BACKEND=mcp`, tool catalog động từ data-miner.
