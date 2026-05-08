-- Migration number: 0001 	 2026-05-08T16:56:35.828Z

PRAGMA foreign_keys = ON;

CREATE TABLE admin_users (
  id TEXT PRIMARY KEY,
  access_subject_id TEXT UNIQUE,
  email TEXT NOT NULL UNIQUE,
  display_name TEXT,
  role TEXT NOT NULL CHECK (role IN ('operator', 'reviewer', 'maintainer')),
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
  last_seen_at TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE sunlight_agencies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  legal_regime TEXT NOT NULL CHECK (legal_regime IN ('OIA', 'LGOIMA', 'other')),
  primary_request_email TEXT,
  secondary_request_emails_json TEXT NOT NULL DEFAULT '[]',
  contact_status TEXT NOT NULL CHECK (
    contact_status IN ('missing', 'needs_review', 'verified', 'invalid')
  ),
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
  default_template_id TEXT,
  default_cadence TEXT NOT NULL DEFAULT 'monthly',
  source TEXT,
  source_id TEXT,
  source_url TEXT,
  source_updated_at TEXT,
  source_metadata_json TEXT NOT NULL DEFAULT '{}',
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  UNIQUE (source, source_id)
);

CREATE TABLE sunlight_request_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  subject_template TEXT NOT NULL,
  body_template TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active', 'inactive')),
  created_by_admin_id TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (created_by_admin_id) REFERENCES admin_users(id)
);

CREATE TABLE sunlight_request_cycles (
  id TEXT PRIMARY KEY,
  cycle_month TEXT NOT NULL UNIQUE,
  covered_from TEXT NOT NULL,
  covered_until TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('draft', 'previewed', 'approved', 'sending', 'sent', 'closed')
  ),
  created_by_admin_id TEXT,
  approved_by_admin_id TEXT,
  approved_at TEXT,
  sent_at TEXT,
  closed_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (created_by_admin_id) REFERENCES admin_users(id),
  FOREIGN KEY (approved_by_admin_id) REFERENCES admin_users(id)
);

CREATE TABLE sunlight_requests (
  id TEXT PRIMARY KEY,
  agency_id TEXT NOT NULL,
  cycle_id TEXT NOT NULL,
  template_id TEXT NOT NULL,
  case_token_hash TEXT NOT NULL UNIQUE,
  case_token_hint TEXT NOT NULL,
  reply_email TEXT NOT NULL UNIQUE,
  response_url TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN (
      'draft',
      'scheduled',
      'queued',
      'sent',
      'delivered',
      'bounced',
      'awaiting_response',
      'response_received',
      'partially_received',
      'held',
      'failed',
      'closed'
    )
  ),
  expected_due_at TEXT,
  last_sent_at TEXT,
  last_response_at TEXT,
  closed_at TEXT,
  closed_reason TEXT,
  operator_notes TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  UNIQUE (agency_id, cycle_id),
  FOREIGN KEY (agency_id) REFERENCES sunlight_agencies(id),
  FOREIGN KEY (cycle_id) REFERENCES sunlight_request_cycles(id),
  FOREIGN KEY (template_id) REFERENCES sunlight_request_templates(id)
);

CREATE TABLE sunlight_outbound_emails (
  id TEXT PRIMARY KEY,
  sunlight_request_id TEXT NOT NULL,
  to_emails_json TEXT NOT NULL,
  from_email TEXT NOT NULL,
  reply_email TEXT NOT NULL,
  subject TEXT NOT NULL,
  body_text TEXT NOT NULL,
  body_html TEXT,
  response_url TEXT NOT NULL,
  provider TEXT NOT NULL CHECK (provider IN ('cloudflare_email')),
  provider_message_id TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('queued', 'sent', 'failed', 'bounced', 'delivered')
  ),
  sent_at TEXT,
  error_code TEXT,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id)
);

CREATE TABLE sunlight_responses (
  id TEXT PRIMARY KEY,
  sunlight_request_id TEXT NOT NULL,
  agency_id TEXT NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('email', 'upload', 'manual')),
  category TEXT NOT NULL CHECK (
    category IN (
      'acknowledgement',
      'clarification_request',
      'extension_notice',
      'transfer_notice',
      'refusal',
      'partial_response',
      'full_response',
      'no_records_held',
      'follow_up',
      'bounce',
      'unknown'
    )
  ),
  status TEXT NOT NULL CHECK (
    status IN ('received', 'needs_review', 'accepted', 'held', 'duplicate', 'rejected')
  ),
  received_at TEXT NOT NULL,
  agency_reference TEXT,
  submitter_name TEXT,
  submitter_email TEXT,
  notes TEXT,
  operator_notes TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id),
  FOREIGN KEY (agency_id) REFERENCES sunlight_agencies(id)
);

CREATE TABLE sunlight_inbound_emails (
  id TEXT PRIMARY KEY,
  sunlight_request_id TEXT,
  sunlight_response_id TEXT,
  provider TEXT NOT NULL CHECK (provider IN ('cloudflare_email_routing')),
  provider_message_id TEXT,
  raw_r2_bucket TEXT NOT NULL,
  raw_r2_key TEXT NOT NULL,
  from_email TEXT,
  to_emails_json TEXT NOT NULL DEFAULT '[]',
  cc_emails_json TEXT NOT NULL DEFAULT '[]',
  subject TEXT,
  message_id_header TEXT,
  in_reply_to_header TEXT,
  received_at TEXT NOT NULL,
  association_status TEXT NOT NULL CHECK (
    association_status IN ('matched', 'unmatched', 'ambiguous')
  ),
  association_reason TEXT,
  status TEXT NOT NULL CHECK (status IN ('stored', 'failed', 'held')),
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id),
  FOREIGN KEY (sunlight_response_id) REFERENCES sunlight_responses(id)
);

CREATE TABLE sunlight_upload_sessions (
  id TEXT PRIMARY KEY,
  sunlight_request_id TEXT NOT NULL,
  sunlight_response_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('open', 'completed', 'expired', 'cancelled')),
  expires_at TEXT NOT NULL,
  created_ip_hash TEXT,
  user_agent_hash TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id),
  FOREIGN KEY (sunlight_response_id) REFERENCES sunlight_responses(id)
);

CREATE TABLE sunlight_uploads (
  id TEXT PRIMARY KEY,
  sunlight_request_id TEXT NOT NULL,
  sunlight_response_id TEXT,
  upload_session_id TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  safe_filename TEXT NOT NULL,
  content_type TEXT,
  size_bytes INTEGER,
  r2_bucket TEXT NOT NULL,
  r2_key TEXT NOT NULL,
  etag TEXT,
  checksum_sha256 TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('pending', 'uploading', 'uploaded', 'failed', 'abandoned', 'held')
  ),
  validation_status TEXT NOT NULL CHECK (
    validation_status IN ('not_checked', 'accepted', 'warning', 'blocked')
  ),
  validation_warnings_json TEXT NOT NULL DEFAULT '[]',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  completed_at TEXT,
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (sunlight_request_id) REFERENCES sunlight_requests(id),
  FOREIGN KEY (sunlight_response_id) REFERENCES sunlight_responses(id),
  FOREIGN KEY (upload_session_id) REFERENCES sunlight_upload_sessions(id)
);

CREATE TABLE sunlight_audit_events (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor_type TEXT NOT NULL CHECK (
    actor_type IN ('admin', 'system', 'agency_token', 'automated_worker')
  ),
  actor_id TEXT,
  actor_email TEXT,
  metadata_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX idx_sunlight_agencies_status_name
  ON sunlight_agencies (status, name);
CREATE INDEX idx_sunlight_agencies_contact_status
  ON sunlight_agencies (contact_status, status);
CREATE INDEX idx_sunlight_agencies_source
  ON sunlight_agencies (source, source_id);
CREATE INDEX idx_sunlight_requests_cycle_status
  ON sunlight_requests (cycle_id, status);
CREATE INDEX idx_sunlight_requests_agency_cycle
  ON sunlight_requests (agency_id, cycle_id);
CREATE INDEX idx_sunlight_requests_due_status
  ON sunlight_requests (expected_due_at, status);
CREATE INDEX idx_sunlight_requests_reply_email
  ON sunlight_requests (reply_email);
CREATE INDEX idx_sunlight_responses_request_received
  ON sunlight_responses (sunlight_request_id, received_at);
CREATE INDEX idx_sunlight_responses_category_status
  ON sunlight_responses (category, status);
CREATE INDEX idx_sunlight_inbound_request_received
  ON sunlight_inbound_emails (sunlight_request_id, received_at);
CREATE INDEX idx_sunlight_inbound_association
  ON sunlight_inbound_emails (association_status);
CREATE INDEX idx_sunlight_uploads_request_status
  ON sunlight_uploads (sunlight_request_id, status);
CREATE INDEX idx_sunlight_audit_entity
  ON sunlight_audit_events (entity_type, entity_id, created_at);

INSERT INTO admin_users (
  id,
  email,
  display_name,
  role,
  status
) VALUES (
  'adm_bootstrap_sunlight',
  'sunlight@spunts.net',
  'Sunlight Bootstrap Admin',
  'maintainer',
  'active'
);

INSERT INTO sunlight_audit_events (
  id,
  entity_type,
  entity_id,
  event_type,
  actor_type,
  actor_id,
  actor_email,
  metadata_json
) VALUES (
  'aud_bootstrap_admin_user',
  'admin_user',
  'adm_bootstrap_sunlight',
  'admin_user.created',
  'system',
  'migration:0001',
  NULL,
  '{"bootstrap":true}'
);
