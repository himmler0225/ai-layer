-- Cập nhật config Supabase theo schema mới (chạy trên SQL Editor).
-- Giữ nguyên key/secret hiện có — chỉ merge field mới.

-- 1) AI_AGENT: thêm curated_top_n (top review vào summarize)
UPDATE config
SET
  value = jsonb_pretty(
    COALESCE(value::jsonb, '{}'::jsonb)
    || jsonb_build_object('curated_top_n', 300)
  ),
  updated_at = now()
WHERE key = 'AI_AGENT';

-- 2) SERVICES: gom data_miner.url + timeout (giữ key hiện có)
UPDATE config
SET
  value = jsonb_pretty(
    COALESCE(value::jsonb, '{}'::jsonb)
    || jsonb_build_object(
      'data_miner',
      COALESCE(value::jsonb->'data_miner', '{}'::jsonb)
      || jsonb_build_object(
        'url', 'http://data-miner:8000',
        'timeout', 60
      )
    )
  ),
  updated_at = now()
WHERE key = 'SERVICES';

-- Kiểm tra
SELECT key, value FROM config WHERE key IN ('AI_AGENT', 'SERVICES', 'AI_MODELS');
