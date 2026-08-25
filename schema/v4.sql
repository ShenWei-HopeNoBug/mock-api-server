-- =====================================================
-- schema v4 变更说明（相对 v3）：
--   api_data 表新增 operator 字段（TEXT, NOT NULL, DEFAULT ''）
--   用途：标记操作来源（'USER' / 'MCP'），空字符串表示历史数据或抓包导入
--   static_data 表新增 operator 字段（TEXT, NOT NULL, DEFAULT ''）
--   用途：同上
--   api_response_variants 表新增 operator 字段（TEXT, NOT NULL, DEFAULT ''）
--   用途：同上
--   迁移方式：
--     ALTER TABLE api_data ADD COLUMN operator TEXT NOT NULL DEFAULT '';
--     ALTER TABLE static_data ADD COLUMN operator TEXT NOT NULL DEFAULT '';
--     ALTER TABLE api_response_variants ADD COLUMN operator TEXT NOT NULL DEFAULT '';
--   迁移触发：db_lib.py _check_schema_version 中 db_version < 4 时执行
-- =====================================================

CREATE TABLE IF NOT EXISTS api_data (
  id                     TEXT PRIMARY KEY,
  type                   TEXT NOT NULL DEFAULT 'MITMPROXY',
  url                    TEXT NOT NULL DEFAULT '',
  method                 TEXT NOT NULL DEFAULT 'GET',
  params                 TEXT NOT NULL DEFAULT '{}',
  response               TEXT NOT NULL DEFAULT '{}',
  response_variant_ids   TEXT NOT NULL DEFAULT '[]',
  enabled                INTEGER NOT NULL DEFAULT 1,
  timeout                INTEGER NOT NULL DEFAULT 0,
  request_content_type   TEXT NOT NULL DEFAULT 'NONE',
  operator               TEXT NOT NULL DEFAULT '',
  created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_type ON api_data(type);

CREATE TABLE IF NOT EXISTS static_data (
  id          TEXT PRIMARY KEY,
  url         TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'MITMPROXY',
  operator    TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE TABLE IF NOT EXISTS api_response_variants (
  id          TEXT PRIMARY KEY,
  api_data_id TEXT NOT NULL,
  name        TEXT NOT NULL DEFAULT '',
  response    TEXT NOT NULL DEFAULT '{}',
  enabled     INTEGER NOT NULL DEFAULT 1,
  timeout     INTEGER NOT NULL DEFAULT 0,  -- 单位毫秒；0 表示不启用 idle 回退
  operator    TEXT NOT NULL DEFAULT '',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_variant_api_data_id ON api_response_variants(api_data_id);
