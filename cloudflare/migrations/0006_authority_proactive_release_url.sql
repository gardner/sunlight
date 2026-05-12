-- Migration number: 0006 	 2026-05-09T00:00:00.000Z

PRAGMA foreign_keys = ON;

ALTER TABLE sunlight_authorities ADD COLUMN proactive_release_url TEXT;

CREATE TABLE sunlight_authority_proactive_scrape_attempts (
  authority_id TEXT PRIMARY KEY,
  attempted_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  error_message TEXT,
  FOREIGN KEY (authority_id) REFERENCES sunlight_authorities(id) ON DELETE CASCADE
);
