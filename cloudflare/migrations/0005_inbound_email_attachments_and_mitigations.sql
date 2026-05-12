-- Migration number: 0005 	 2026-05-09T00:00:00.000Z

PRAGMA foreign_keys = ON;

CREATE TABLE sunlight_inbound_attachments (
  id TEXT PRIMARY KEY,
  inbound_email_id TEXT NOT NULL,
  sunlight_request_id TEXT NOT NULL,
  filename TEXT NOT NULL,
  content_type TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  r2_bucket TEXT NOT NULL,
  r2_key TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('stored', 'failed')),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (inbound_email_id) REFERENCES sunlight_inbound_emails(id),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id)
);

CREATE TABLE sunlight_refusal_mitigations (
  id TEXT PRIMARY KEY,
  sunlight_request_id TEXT NOT NULL,
  sunlight_response_id TEXT NOT NULL,
  refusal_reason TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('drafted', 'sent', 'resolved', 'escalated')),
  drafted_response TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id),
  FOREIGN KEY (sunlight_response_id) REFERENCES sunlight_responses(id)
);

CREATE INDEX idx_sunlight_inbound_attachments_email
  ON sunlight_inbound_attachments (inbound_email_id);

CREATE INDEX idx_sunlight_refusal_mitigations_request
  ON sunlight_refusal_mitigations (sunlight_request_id);
