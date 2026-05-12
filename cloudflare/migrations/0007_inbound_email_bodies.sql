-- Migration number: 0007 	 2026-05-11T00:00:00.000Z

PRAGMA foreign_keys = ON;

ALTER TABLE sunlight_inbound_emails ADD COLUMN body_text TEXT;
ALTER TABLE sunlight_inbound_emails ADD COLUMN body_html TEXT;
