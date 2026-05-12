# Vector Storage Plan

## Decision

Use a plain local SQLite spool for ingestion output now, not ChromaDB, FAISS, or
LanceDB. The local store does not need to answer nearest-neighbor queries during
the FYI import. It needs to accept a large stream of chunks, vectors, and source
metadata without holding the corpus in memory, and then export deterministic
NDJSON batches for Cloudflare Vectorize.

For production on Cloudflare:

* Use Cloudflare Vectorize for vector search.
* Use R2 for raw PDFs, full markdown, and other large derived artifacts.
* Use D1 for structured relational metadata, processing state, public records,
  and pointers into R2 and Vectorize.
* Store only compact retrieval metadata and optional snippets in Vectorize
  metadata. Do not make Vectorize the canonical full-text store.

## Why Change

The current FYI pipeline writes through LlamaIndex local storage. In practice
that means large JSON vector and document stores that are expensive to rewrite
and easy to load into process memory. During the latest run the machine was not
compute-bound; it exhausted RAM and swap while the embedding process was blocked
on disk writes. The failure mode points at storage shape, not Docling throughput.

The next storage layer should therefore be append-friendly, transactional, and
streamable. A single SQLite file with vector BLOBs is enough for that.

## Local Store Options

### Plain SQLite

Recommended for the current importer.

Pros:

* Already in the Python standard library.
* Append-only writes are simple and robust.
* Can store embeddings as compact `float32` BLOBs instead of huge JSON arrays.
* Can store chunk text, markdown file pointers, model name, dimensions, status,
  and export checkpoints in one transactional file.
* Easy to stream rows back out to Vectorize NDJSON without loading the whole
  corpus.
* Mirrors the relational shape we will use in Cloudflare D1 for metadata.

Cons:

* No local approximate nearest-neighbor index unless we add an extension later.
* Large chunk text can make the SQLite file bulky if we store full text inline.

This is acceptable because the immediate requirement is durable staging and
export, not local semantic search.

### LanceDB

Useful later if we want a local vector database for exploratory search,
evaluation, or a long-lived local AI data lake. LanceDB OSS is an embedded
database that can run against a local path and is built for vector search and AI
datasets.

It is more than we need for the current memory problem. If the importer only
needs to persist vectors and export them, SQLite gives us less operational
surface area and fewer format/API decisions.

### ChromaDB

Chroma stores documents, embeddings, and metadata in collections and can generate
embeddings itself if only documents are provided. That is convenient for local
RAG experiments, but our pipeline already controls chunking and embeddings, and
our production retrieval target is Vectorize.

Chroma would add a second vector database abstraction for a stage that does not
need vector search. It is a poor fit as a neutral export spool.

### FAISS

FAISS is excellent at similarity search over dense vectors. It is not a document
store, job-state store, or metadata database. We would still need a sidecar
SQLite/Parquet/JSON layer for chunk text, source IDs, markdown paths, export
status, and provenance.

Because we do not need local nearest-neighbor search right now, FAISS solves the
wrong part of the problem.

### sqlite-vec / Vec1-Style SQLite Extensions

SQLite vector extensions are attractive if we later want local vector search
without leaving SQLite. They are not needed for staging, and Cloudflare D1 only
supports a subset of SQLite extensions. D1 currently documents FTS5, JSON, and
math functions, not sqlite-vec or Vec1-style vector tables.

Use plain SQLite first. Add a vector extension only if local vector search
becomes a real requirement.

## Proposed Local Schema

Keep the local ingestion database separate from Cloudflare D1:

```sql
CREATE TABLE markdown_files (
  markdown_path TEXT PRIMARY KEY,
  pdf_path TEXT NOT NULL,
  markdown_sha256 TEXT,
  status TEXT NOT NULL,
  error TEXT,
  converted_at TEXT,
  embedded_at TEXT
);

CREATE TABLE chunks (
  id TEXT PRIMARY KEY,
  markdown_path TEXT NOT NULL REFERENCES markdown_files(markdown_path),
  chunk_index INTEGER NOT NULL,
  text TEXT NOT NULL,
  vector BLOB NOT NULL,
  dimensions INTEGER NOT NULL,
  embedding_model TEXT NOT NULL,
  source_file TEXT NOT NULL,
  text_sha256 TEXT NOT NULL,
  vectorize_exported_at TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX chunks_markdown_path_idx ON chunks(markdown_path);
CREATE INDEX chunks_export_idx ON chunks(vectorize_exported_at, id);
```

Implementation notes:

* Store vectors as little-endian `float32` BLOBs. This is compact and converts
  cleanly to JSON arrays only at NDJSON export time.
* Use deterministic chunk IDs, for example a hash of source path, chunk index,
  text hash, and embedding model. That gives idempotent restarts.
* Commit per file or per small batch so an interruption loses little work.
* Replace `.embedded` marker files with database status where practical. If
  marker files remain for watchdog compatibility, derive them from the database
  rather than treating them as the source of truth.

## Markdown And Chunk Text

Store markdown in two layers:

1. Local ingestion: write markdown files to disk as we do now, and store chunk
   text inline in the local SQLite spool for export and debugging.
2. Cloudflare production: store the full markdown and raw PDFs in R2. Store D1
   rows that point to the R2 keys and Vectorize IDs.

Do not store full markdown only in Vectorize metadata. Vectorize metadata is
useful for IDs, source paths, filtering fields, and small snippets, but it is
not the right canonical document store.

D1 can store text, but it should not be the bulk artifact store for the FYI
corpus. D1 has relational query value, but it has database and row-size limits.
Use it for structured metadata and workflow state:

```sql
CREATE TABLE disclosed_documents (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_url TEXT,
  pdf_r2_key TEXT,
  markdown_r2_key TEXT,
  markdown_sha256 TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE disclosed_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES disclosed_documents(id),
  chunk_index INTEGER NOT NULL,
  vectorize_id TEXT NOT NULL UNIQUE,
  text_r2_key TEXT,
  text_preview TEXT,
  embedding_model TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

For small chunks, `text_preview` can be enough for immediate search-result
display. For complete answer synthesis, fetch full chunk text from R2 using
`text_r2_key`, or fetch the full markdown document via `markdown_r2_key` and
slice by stored offsets if we add offsets.

## Vectorize Metadata

Vectorize should receive enough metadata to make query results useful without a
second lookup for every display card:

```json
{
  "id": "chunk_...",
  "values": [0.0123, -0.0456],
  "metadata": {
    "document_id": "doc_...",
    "chunk_id": "chunk_...",
    "source": "fyi",
    "source_file": "path/to/file.pdf",
    "markdown_r2_key": "fyi/markdown/...",
    "chunk_index": 12,
    "embedding_model": "Qwen3-Embedding-0.6B",
    "text_preview": "First few hundred characters..."
  }
}
```

Metadata indexes should be sparse and intentional. Candidate indexed fields:

* `source`
* `document_id`
* `embedding_model`

Avoid indexing long strings. Vectorize string metadata indexes only use the
first 64 bytes of an indexed string for filtering, and each Vectorize index can
have only a limited number of metadata indexes.

## Queue Shape

The existing queue-based local architecture is still right:

```text
Docling workers -> markdown files -> bounded markdown queue -> embedding worker
    -> SQLite vector spool -> streaming NDJSON export -> Vectorize
```

Cloudflare Queues maps well to the deployed version:

```text
R2 object uploaded
  -> conversion queue
  -> chunking queue
  -> embedding queue
  -> Vectorize upsert queue
  -> D1 status/update rows
```

For the FYI bulk import, keep the heavy Docling and local GPU embedding work on
the workstation. Use Cloudflare Queues later for new inbound documents, retries,
and smaller ongoing ingestion jobs.

## Recommended Next Implementation Slice

1. Replace LlamaIndex `VectorStoreIndex` persistence in
   `scripts/parallel_convert_and_embed.py` with a plain SQLite writer.
2. Keep the current single embedding worker and bounded queues.
3. Write chunk vectors to `storage/fyi_vectors.sqlite` as `float32` BLOBs.
4. Update `scripts/export_to_vectorize.py` to stream from SQLite and write
   <= 5000 vectors per NDJSON file.
5. Restart FYI ingestion from the SQLite-backed state.

## Sources

* Cloudflare Vectorize metadata and metadata index limits:
  https://developers.cloudflare.com/vectorize/get-started/intro/
* Cloudflare Vectorize insert and NDJSON guidance:
  https://developers.cloudflare.com/vectorize/best-practices/insert-vectors/
* Cloudflare D1 supported SQLite extensions:
  https://developers.cloudflare.com/d1/sql-api/sql-statements/
* Cloudflare D1 limits:
  https://developers.cloudflare.com/d1/platform/limits/
* Cloudflare storage product guidance:
  https://developers.cloudflare.com/workers/platform/storage-options/
* Cloudflare R2 storage guidance:
  https://developers.cloudflare.com/r2/how-r2-works/
* LanceDB quickstart:
  https://docs.lancedb.com/quickstart
* Chroma add-data docs:
  https://docs.trychroma.com/docs/collections/add-data
* FAISS docs:
  https://faiss.ai/
* sqlite-vec project:
  https://github.com/asg017/sqlite-vec
