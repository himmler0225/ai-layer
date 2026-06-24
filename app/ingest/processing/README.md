# Processing

Tiền xử lý trước khi embed vào `video_chunks`.

| File | Vai trò |
|------|---------|
| `quality.py` | Lọc comment spam / quá ngắn |
| `chunking.py` | Chia transcript; 1 comment = 1 chunk |
| `embeddings.py` | Gọi OpenAI `text-embedding-3-small` |

Handlers gọi processing sau khi ghi Postgres, trước job `chunks.embed`.
