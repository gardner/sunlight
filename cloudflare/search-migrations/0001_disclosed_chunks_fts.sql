CREATE TABLE IF NOT EXISTS disclosed_chunks (
  chunk_id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL,
  source TEXT NOT NULL,
  authority_name TEXT,
  authority_slug TEXT,
  authority_category TEXT,
  request_title TEXT,
  request_url TEXT,
  source_url TEXT,
  original_filename TEXT,
  markdown_r2_key TEXT,
  chunk_index INTEGER NOT NULL,
  chunk_text TEXT NOT NULL,
  text_preview TEXT NOT NULL,
  request_year INTEGER,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS disclosed_chunks_document_id_idx
  ON disclosed_chunks(document_id);

CREATE INDEX IF NOT EXISTS disclosed_chunks_request_year_idx
  ON disclosed_chunks(request_year);

CREATE VIRTUAL TABLE IF NOT EXISTS disclosed_chunks_fts USING fts5(
  chunk_id UNINDEXED,
  document_id UNINDEXED,
  authority_name,
  request_title,
  original_filename,
  chunk_text,
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS disclosed_chunks_ai
AFTER INSERT ON disclosed_chunks
BEGIN
  INSERT INTO disclosed_chunks_fts(
    rowid,
    chunk_id,
    document_id,
    authority_name,
    request_title,
    original_filename,
    chunk_text
  )
  VALUES (
    new.rowid,
    new.chunk_id,
    new.document_id,
    new.authority_name,
    new.request_title,
    new.original_filename,
    new.chunk_text
  );
END;

CREATE TRIGGER IF NOT EXISTS disclosed_chunks_ad
AFTER DELETE ON disclosed_chunks
BEGIN
  DELETE FROM disclosed_chunks_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS disclosed_chunks_au
AFTER UPDATE ON disclosed_chunks
BEGIN
  DELETE FROM disclosed_chunks_fts WHERE rowid = old.rowid;

  INSERT INTO disclosed_chunks_fts(
    rowid,
    chunk_id,
    document_id,
    authority_name,
    request_title,
    original_filename,
    chunk_text
  )
  VALUES (
    new.rowid,
    new.chunk_id,
    new.document_id,
    new.authority_name,
    new.request_title,
    new.original_filename,
    new.chunk_text
  );
END;
