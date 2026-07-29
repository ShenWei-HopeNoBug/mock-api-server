-- =====================================================
-- schema v2 变更说明（相对 v1）：
--   api_data 表新增 timeout 字段（INTEGER, NOT NULL, DEFAULT 0）
--   用途：记录单条 API 的自定义超时时间（毫秒），0 表示不限制
--   迁移方式：ALTER TABLE api_data ADD COLUMN timeout INTEGER NOT NULL DEFAULT 0
--   迁移触发：db_lib.py _check_schema_version 中 db_version < 2 时执行
-- =====================================================

CREATE TABLE IF NOT EXISTS api_data (
  id             TEXT PRIMARY KEY,
  type           TEXT NOT NULL DEFAULT 'MITMPROXY',
  url            TEXT NOT NULL DEFAULT '',
  method         TEXT NOT NULL DEFAULT 'GET',
  params         TEXT NOT NULL DEFAULT '{}',
  response       TEXT NOT NULL DEFAULT '{}',
  timeout        INTEGER NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_type ON api_data(type);

CREATE TABLE IF NOT EXISTS static_data (
  id          TEXT PRIMARY KEY,
  url         TEXT NOT NULL DEFAULT '',
  type        TEXT NOT NULL DEFAULT 'MITMPROXY',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_static_url ON static_data(url);
