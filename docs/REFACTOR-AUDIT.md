# Refactor audit — ai-layer (Phase A done)

Tài liệu này ghi **đã làm gọn gì**, **còn gì cho bạn** (MCP, LangGraph), và **thứ tự đề xuất**.

Liên quan:
- [FLOW.md](./FLOW.md) — luồng runtime
- [MCP Phase 2](../../docs/MCP-PHASE2-GUIDE.md) — tool discovery từ data-miner
- [LANGGRAPH-GUIDE.md](./LANGGRAPH-GUIDE.md) — thay vòng lặp agent bằng graph

---

## Phase A — đã làm (cleanup, không đổi hành vi chính)

| Hạng mục | Thay đổi |
|----------|----------|
| **Guards** | `tiktok_get_comments_batch` → `tiktok_comments` (tên tool thật) |
| **Aliases LLM** | Xóa `openai_responses.py`, `openai_errors.py`; dùng `llm_responses` / `llm_errors` |
| **Dead code** | Xóa `run_tool_round`, `PROVIDER_SPECS`, native Responses API path trong `providers.py` |
| **Retry** | Một lớp retry ở `ConfiguredLLM._with_retry`; bỏ retry ngoài ở `stream.py` / `synthesis.py` |
| **Đặt tên** | `response_stream_with_retry` → `response_stream` (wrapper mỏng, không retry riêng) |
| **Synthesis stream** | 1 lần stream/model; lỗi SSE → fallback `run_synthesis` (non-stream) |
| **definitions** | Bỏ alias `_RAG_TOOLS` |
| **data-miner client** | `get_trending()` → `search_youtube(..., sort=view_count)` (route trending YouTube không tồn tại) |
| **Thư mục `services/agent/`** | 20 file phẳng → nhóm theo concern: `core/` (runner, stream, iterate, engine, context, langgraph stub), `guards/` (budget, fallback), `synthesis/` (generate, finalize), `tooling/` (platform, dispatch, serialize), `events/` (schema, tool_status). Public API giữ nguyên qua `__init__.py` re-export — hầu hết import path bên ngoài (`app.services.agent.guards`, `.synthesis`, `.tooling`, `.events`, `.core`) không đổi. |

### Kiến trúc LLM sau Phase A

```
core/stream.py / synthesis/generate.py / core/runner.py
    → llm_responses.response_stream | create_response
        → router (TASK_AGENT_TOOL | TASK_AGENT_SYNTH)
            → ConfiguredLLM (chat completions + adapter)
                → _with_retry (HTTP_MAX_ATTEMPTS)
```

Responses API **shape** vẫn dùng nội bộ (`LLMResponse`, `output_items_to_input`) qua adapter — không gọi `client.responses.*` trực tiếp.

---

## Phase B — unify runner (bạn có thể làm sau MCP)

**Vấn đề:** `runner.py` (sync JSON) và `stream.py` (SSE) lặp logic tool round.

**Hướng:**
1. Tách `engine.py` thành generator events: `tool_start`, `text_delta`, `done`
2. `stream.py` map events → SSE; `runner.py` gom text + metadata
3. Giữ `bootstrap_agent` / `complete_tool_round` / `finish_agent` như hiện tại

**Không bắt buộc** trước MCP/LangGraph.

---

## Phase C — MCP (bạn làm tiếp)

Theo [MCP-PHASE2-GUIDE.md](../../docs/MCP-PHASE2-GUIDE.md):

1. MCP server trên **data-miner** (expose tool schemas + execute)
2. **ai-layer** client: list tools → merge với RAG tools → executor gọi MCP thay hardcode `definitions.py` + `data_miner.py`
3. Giữ `executor.py` validation + ingest side-effects

Sau MCP, `tools/definitions.py` có thể chỉ còn RAG + util.

---

## Phase D — LangGraph (sau MCP)

Theo [LANGGRAPH-GUIDE.md](./LANGGRAPH-GUIDE.md):

- Stub `graph/state.py` đã có; deps `langgraph` chưa wire
- `AGENT_BACKEND=langgraph` chưa dùng — implement khi graph ổn
- **Hybrid trước:** graph cho routing/state; `response_stream` bọc ngoài cho SSE

---

## File map nhanh

| Vai trò | File |
|---------|------|
| SSE agent | `services/agent/core/stream.py` |
| Sync agent | `services/agent/core/runner.py` |
| Tool round | `services/agent/core/context.py`, `core/engine.py` |
| Synthesis | `services/agent/synthesis/generate.py`, `synthesis/finalize.py` |
| Platform filter | `services/agent/tooling/platform.py` |
| LLM provider | `ai/providers.py`, `ai/router.py` |
| Tool dispatch | `tools/executor.py`, `clients/data_miner.py` |

---

## Checklist sau khi pull

```bash
cd ai-layer && pytest -q
# restart uvicorn nếu đang chạy
```

Nếu synthesis stream với xah + opus vẫn lỗi SSE: log `[agent] synthesis_stream unavailable` → fallback non-stream (expected).
