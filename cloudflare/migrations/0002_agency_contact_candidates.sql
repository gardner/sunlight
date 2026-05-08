-- Migration number: 0002

PRAGMA foreign_keys = ON;

CREATE TABLE sunlight_agency_contact_candidates (
  id TEXT PRIMARY KEY,
  agency_id TEXT NOT NULL,
  email TEXT NOT NULL,
  normalized_email TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_page_title TEXT,
  source_snippet TEXT,
  discovery_method TEXT NOT NULL CHECK (
    discovery_method IN ('homepage', 'linked_page', 'fyi_page', 'search')
  ),
  confidence INTEGER NOT NULL CHECK (confidence >= 0 AND confidence <= 100),
  confidence_reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('candidate', 'accepted', 'rejected', 'stale')),
  first_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  UNIQUE (agency_id, normalized_email, source_url),
  FOREIGN KEY (agency_id) REFERENCES sunlight_agencies(id)
);

CREATE INDEX idx_sunlight_contact_candidates_agency_status_confidence
  ON sunlight_agency_contact_candidates (agency_id, status, confidence);
CREATE INDEX idx_sunlight_contact_candidates_normalized_email
  ON sunlight_agency_contact_candidates (normalized_email);
CREATE INDEX idx_sunlight_contact_candidates_source_url
  ON sunlight_agency_contact_candidates (source_url);
