# Handlers

Worker xử lý từng loại job theo `routing_key`.

## Flow

```
dispatch(envelope)
    ├─ video.upsert      → videos + search_cache
    ├─ comments.upsert   → comments → queue chunks.embed
    ├─ transcript.upsert → transcript → queue chunks.embed
    └─ chunks.embed      → embed → video_chunks
```

Mỗi handler đảm bảo video tồn tại (FK) trước khi ghi comment/transcript.
