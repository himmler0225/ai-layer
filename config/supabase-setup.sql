-- Chạy trên Supabase Dashboard → SQL Editor (một lần trước khi migrate ai-layer).
-- Sau đó: cd ai-layer && alembic upgrade head

-- 1) pgvector (bắt buộc cho RAG)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2) Kiểm tra
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- DATABASE_URL (Settings → Database → Connection string):
--   Pooler (khuyến nghị prod): port 6543, Transaction mode
--   Direct: port 5432
-- Ví dụ:
-- postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
