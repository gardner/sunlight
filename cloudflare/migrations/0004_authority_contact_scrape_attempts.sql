-- Migration number: 0004

PRAGMA foreign_keys = ON;

CREATE TABLE sunlight_authority_contact_scrape_attempts (
  id TEXT PRIMARY KEY,
  authority_id TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (
    outcome IN ('auto_verified', 'needs_review', 'no_candidate')
  ),
  candidate_count INTEGER NOT NULL CHECK (candidate_count >= 0),
  auto_verified_email TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (authority_id) REFERENCES sunlight_authorities(id)
);

CREATE INDEX idx_sunlight_contact_scrape_attempts_authority_created
  ON sunlight_authority_contact_scrape_attempts (authority_id, created_at);
CREATE INDEX idx_sunlight_contact_scrape_attempts_outcome_created
  ON sunlight_authority_contact_scrape_attempts (outcome, created_at);
