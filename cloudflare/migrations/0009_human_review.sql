-- Migration number: 0009 	 2026-05-11T00:00:00.000Z

PRAGMA foreign_keys = ON;

ALTER TABLE sunlight_inbound_emails ADD COLUMN needs_human_review INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sunlight_inbound_emails ADD COLUMN human_review_status TEXT;
ALTER TABLE sunlight_inbound_emails ADD COLUMN ai_triage_reason TEXT;
