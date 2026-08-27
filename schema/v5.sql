-- =====================================================
-- schema v5 变更说明（相对 v4）：
--   api_response_variants 表新增 type 字段（TEXT, NOT NULL, DEFAULT 'USER'）
--   用途：标记响应变体的创建来源类型（'USER' / 'MCP'），创建后不可变更
--   与 operator 字段的区别：
--     type     = 创建者身份，创建后永不变（update 时忽略）
--     operator = 最后更新者，每次 update/copy 都变更为当前操作者
--   迁移方式：
--     ALTER TABLE api_response_variants ADD COLUMN type TEXT NOT NULL DEFAULT 'USER';
--   迁移触发：db_lib.py _check_schema_version 中 db_version < 5 时执行
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
  operator    TEXT NOT NULL DEFAULT '',     -- 最后更新者，每次 update/copy 都变更
  type        TEXT NOT NULL DEFAULT 'USER', -- 创建来源类型，创建后永不变
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_variant_api_data_id ON api_response_variants(api_data_id);
