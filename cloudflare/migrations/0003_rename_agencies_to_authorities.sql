-- Migration number: 0003

PRAGMA foreign_keys = OFF;

DROP INDEX IF EXISTS idx_sunlight_agencies_status_name;
DROP INDEX IF EXISTS idx_sunlight_agencies_contact_status;
DROP INDEX IF EXISTS idx_sunlight_agencies_source;
DROP INDEX IF EXISTS idx_sunlight_requests_agency_cycle;
DROP INDEX IF EXISTS idx_sunlight_contact_candidates_agency_status_confidence;
DROP INDEX IF EXISTS idx_sunlight_contact_candidates_normalized_email;
DROP INDEX IF EXISTS idx_sunlight_contact_candidates_source_url;
DROP INDEX IF EXISTS idx_sunlight_audit_entity;

ALTER TABLE sunlight_agencies RENAME TO sunlight_authorities;
ALTER TABLE sunlight_requests RENAME COLUMN agency_id TO authority_id;
ALTER TABLE sunlight_responses RENAME COLUMN agency_id TO authority_id;
ALTER TABLE sunlight_responses RENAME COLUMN agency_reference TO authority_reference;
ALTER TABLE sunlight_agency_contact_candidates RENAME COLUMN agency_id TO authority_id;
ALTER TABLE sunlight_agency_contact_candidates RENAME TO sunlight_authority_contact_candidates;

ALTER TABLE sunlight_audit_events RENAME TO sunlight_audit_events_old;

CREATE TABLE sunlight_audit_events (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (
    actor_type IN ('admin', 'system', 'authority_token', 'automated_worker')
  ),
  actor_id TEXT,
  actor_email TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO sunlight_audit_events (
  id,
  entity_type,
  entity_id,
  event_type,
  actor_type,
  actor_id,
  actor_email,
  metadata_json,
  created_at
)
SELECT
  id,
  entity_type,
  entity_id,
  event_type,
  CASE actor_type
    WHEN 'agency_token' THEN 'authority_token'
    ELSE actor_type
  END,
  actor_id,
  actor_email,
  metadata_json,
  created_at
FROM sunlight_audit_events_old;

DROP TABLE sunlight_audit_events_old;

CREATE INDEX idx_sunlight_authorities_status_name
  ON sunlight_authorities (status, name);
CREATE INDEX idx_sunlight_authorities_contact_status
  ON sunlight_authorities (contact_status, status);
CREATE INDEX idx_sunlight_authorities_source
  ON sunlight_authorities (source, source_id);
CREATE INDEX idx_sunlight_requests_authority_cycle
  ON sunlight_requests (authority_id, cycle_id);
CREATE INDEX idx_sunlight_contact_candidates_authority_status_confidence
  ON sunlight_authority_contact_candidates (authority_id, status, confidence);
CREATE INDEX idx_sunlight_contact_candidates_normalized_email
  ON sunlight_authority_contact_candidates (normalized_email);
CREATE INDEX idx_sunlight_contact_candidates_source_url
  ON sunlight_authority_contact_candidates (source_url);
CREATE INDEX idx_sunlight_audit_entity
  ON sunlight_audit_events (entity_type, entity_id, created_at);

PRAGMA foreign_keys = ON;
