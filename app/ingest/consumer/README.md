# Consumer

Worker chạy `python -m app.ingest`, lắng nghe 4 queue song song.

## Flow

1. `declare_topology()` — đảm bảo queue tồn tại
2. Mỗi queue → `consume(_on_message)`
3. Parse JSON envelope → `handlers.router.dispatch()`
4. Lỗi handler → message vào DLQ (không requeue)

Chạy riêng container `ingest-worker` trong docker-compose.
