-- =====================================================
-- schema v6 变更说明（相对 v5）：
--   api_data 表新增 group_id 字段（TEXT, NOT NULL, DEFAULT ''）
--     用途：标记该行的测试组归属；仅 type='TEST_GROUP' 行有值，
--           创建后不可变更（移组 = 拷入新组 + 删除旧条目）
--   新增 test_group 表：测试组（mock 接口数据命名集合）
--     enabled 全局至多一行 1，启用/停用由 enable_test_group /
--     disable_test_group 原子管理，不经 update_test_group 修改
--   迁移方式：
--     ALTER TABLE api_data ADD COLUMN group_id TEXT NOT NULL DEFAULT '';
--     CREATE TABLE IF NOT EXISTS test_group (...);
--   迁移触发：db_lib.py _check_schema_version 中 db_version < 6 时执行
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
  group_id               TEXT NOT NULL DEFAULT '',
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

CREATE TABLE IF NOT EXISTS test_group (
  id          TEXT PRIMARY KEY,
  name        TEXT NOT NULL DEFAULT '',
  enabled     INTEGER NOT NULL DEFAULT 0,   -- 全局至多一行 1
  operator    TEXT NOT NULL DEFAULT '',      -- 最后更新者，每次 update 都变更
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_test_group_enabled ON test_group(enabled);
