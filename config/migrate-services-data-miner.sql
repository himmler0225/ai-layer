-- Gom DATA_MINER_URL + timeout vào SERVICES (giữ key hiện có).
-- Chạy trên Supabase SQL Editor.
-- Đổi URL theo môi trường: localhost / docker / prod.

-- Cách 1: merge (khuyên dùng — không mất ai_layer.key, data_miner.key)
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

-- Cách 2: ghi đè toàn bộ SERVICES (chỉ khi muốn set lại hết)
/*
INSERT INTO config (key, value, description, is_secret)
VALUES (
  'SERVICES',
  jsonb_pretty(jsonb_build_object(
    'ai_layer', jsonb_build_object(
      'url', 'http://ai-layer:8001',
      'key', 'YOUR_AI_LAYER_KEY'
    ),
    'data_miner', jsonb_build_object(
      'url', 'http://data-miner:8000',
      'key', 'YOUR_DATA_MINER_KEY',
      'timeout', 60
    )
  )),
  'Internal services',
  true
)
ON CONFLICT (key) DO UPDATE SET
  value = EXCLUDED.value,
  description = EXCLUDED.description,
  is_secret = EXCLUDED.is_secret,
  updated_at = now();
*/

-- Kiểm tra sau khi chạy:
SELECT key, value FROM config WHERE key = 'SERVICES';
