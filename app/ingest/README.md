# Ingest pipeline

Luồng lưu tri thức từ agent crawl → Postgres + vector (RAG).

```
Agent gọi tool
    → dispatcher/   map kết quả → job RabbitMQ
    → producer/     publish (API, không chờ worker)
    → broker/       exchange + queue + DLQ

ingest-worker (python -m app.ingest)
    → consumer/     nhận job
    → handlers/     ghi DB, queue embed
    → processing/   chunk + embed OpenAI
    → repositories/ videos, comments, chunks
```

| Thư mục | Vai trò |
|---------|---------|
| `broker/` | Kết nối RabbitMQ, khai báo topology |
| `producer/` | Publish job từ ai-layer API |
| `consumer/` | Worker lắng nghe queue |
| `dispatcher/` | Sau tool call → quyết định job nào publish |
| `mappers/` | Chuẩn hóa response data-miner |
| `handlers/` | Xử lý từng loại job |
| `processing/` | Lọc comment, chia chunk, embedding |

Env: `RABBITMQ_URL`, `INGEST_ENABLED`, `OPENAI_API_KEY` (worker embed).

Monitoring:
- `GET /health` — Postgres, Redis, Mongo (optional), RabbitMQ, data-miner, OpenAI key
- `GET /ai/admin/ingest/queues` — queue depth + DLQ (cần `X-API-Key`)
- RabbitMQ Management UI: `http://localhost:15672` (user `ingest`)
