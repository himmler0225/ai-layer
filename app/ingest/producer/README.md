# Producer

API ai-layer publish job sau khi agent crawl — **fire-and-forget**, không block response.

## Flow

1. `init_producer()` — lifespan startup: declare topology + sẵn sàng publish
2. `publish(routing_key, ...)` — bọc `IngestEnvelope` JSON → exchange
3. RabbitMQ lỗi → log warning, API vẫn chạy (`INGEST_ENABLED=false` để tắt)

Gọi từ `dispatcher/` (sau tool) và `handlers/` (comments/transcript → embed).
