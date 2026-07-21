CREATE TABLE IF NOT EXISTS api_data (
  id             TEXT PRIMARY KEY,
  type           TEXT NOT NULL DEFAULT 'MITMPROXY',
  url            TEXT NOT NULL DEFAULT '',
  method         TEXT NOT NULL DEFAULT 'GET',
  params         TEXT NOT NULL DEFAULT '{}',
  response       TEXT NOT NULL DEFAULT '{}',
  created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);

CREATE INDEX IF NOT EXISTS idx_api_type ON api_data(type);

CREATE TABLE IF NOT EXISTS static_data (
  url         TEXT PRIMARY KEY,
  type        TEXT NOT NULL DEFAULT 'MITMPROXY',
  created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now','localtime'))
);
