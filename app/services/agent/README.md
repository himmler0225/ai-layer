# Agent

Vòng lặp tool-calling OpenAI: crawl → tổng hợp → enrich UI.

## Flow

```
API /agent/run
    → runner.run_agent()
        → platform.filter_tools()     # chặn youtube_* hoặc tiktok_* theo câu hỏi
        → OpenAI (tool model)           → function_call?
        → tools.execute_parallel()      → data-miner + ingest + mongo log
        → synthesis.run_synthesis()     # dual-mode: model riêng viết câu trả lời
        → finalize.finish()             → enricher + log_agent_run

API /agent/run/stream
    → stream.run_agent_stream()         # SSE text_delta / tool_start / done
```

| File | Vai trò |
|------|---------|
| `config.py` | Model, token, dual-mode |
| `platform.py` | Nhận diện YouTube/TikTok trong task |
| `serialize.py` | Cắt ngắn tool result trước khi đưa lại model |
| `tools.py` | Gọi tool song song |
| `synthesis.py` | Model tổng hợp (sync + stream delta) |
| `finalize.py` | Enrich + ghi mongo |
| `runner.py` | `run_agent` |
| `stream.py` | `run_agent_stream` |
