-- =====================================================
-- schema v3 变更说明（相对 v2）：
--   api_data 表新增 response_variant_ids 字段（TEXT, NOT NULL, DEFAULT '[]'）
--   用途：记录单条 API 绑定的 response 变体 ID 列表（JSON 数组）
--   api_data 表新增 enabled 字段（INTEGER, NOT NULL, DEFAULT 1）
--   用途：标记 API 是否启用（1 启用，0 禁用）
--   新增 api_response_variants 表
--   用途：存储 api_data 的 response 变体内容
--   删除 static_data 表的 idx_static_url 索引（未使用）
--   迁移方式：
--     ALTER TABLE api_data ADD COLUMN response_variant_ids TEXT NOT NULL DEFAULT '[]';
--     ALTER TABLE api_data ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1;
--     CREATE TABLE IF NOT EXISTS api_response_variants (...);
--     DROP INDEX IF EXISTS idx_static_url;
--   迁移触发：db_lib.py _check_schema_version 中 db_version < 3 时执行
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
  created_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at             TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_type ON api_data(type);

CREATE TABLE IF NOT EXISTS static_data (
  id          TEXT PRIMARY KEY,
  url         TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'MITMPROXY',
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
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_variant_api_data_id ON api_response_variants(api_data_id);
