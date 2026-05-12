-- Migration number: 0008 	 2026-05-11T00:00:00.000Z

PRAGMA foreign_keys = ON;

ALTER TABLE sunlight_request_templates ADD COLUMN deleted_at TEXT;
