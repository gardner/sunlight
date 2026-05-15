CREATE TABLE IF NOT EXISTS search_rate_limits (
  bucket_key TEXT PRIMARY KEY,
  client_hash TEXT NOT NULL,
  limit_name TEXT NOT NULL,
  window_start INTEGER NOT NULL,
  window_seconds INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  request_count INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS search_rate_limits_expires_at_idx
  ON search_rate_limits(expires_at);

CREATE INDEX IF NOT EXISTS search_rate_limits_client_hash_idx
  ON search_rate_limits(client_hash);
