# Mappers

Chuẩn hóa response data-miner → dict ghi Postgres.

| File | Nội dung |
|------|----------|
| `unwrap.py` | Bóc `ApiResponse.success/data` |
| `video.py` | YouTube / TikTok video metadata |
| `comment.py` | Comment → `comments` table |

Dispatcher gọi mapper trước khi publish; handler nhận payload đã chuẩn.
