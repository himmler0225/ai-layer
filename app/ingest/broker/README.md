# Broker

Kết nối RabbitMQ và khai báo topology.

## Flow

1. `connection.py` — mở channel, QoS prefetch=8
2. `topology.py` — exchange `knowledge.ingest` (topic), 4 queue bind routing key
3. Queue lỗi → DLX `knowledge.ingest.dlx` → `ingest.dlq`

## Routing keys

| Key | Queue |
|-----|-------|
| `video.upsert` | `ingest.video` |
| `comments.upsert` | `ingest.comments` |
| `transcript.upsert` | `ingest.transcript` |
| `chunks.embed` | `ingest.embed` |

Producer và consumer đều gọi `declare_topology()` lúc khởi động.
