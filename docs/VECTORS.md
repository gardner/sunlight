# Vector Storage Plan

## Decision

Run two ingestion/search pipelines against the same converted markdown corpus so
we can evaluate quality, latency, operational cost, and citation behavior before
standardizing on one path.

1. **Main pipeline:** convert PDFs to markdown with Docling, chunk and embed
   locally, stream chunk records into LanceDB, and upload vectors plus metadata
   to Cloudflare Vectorize.
2. **AI Search pipeline:** upload the converted markdown files to R2 and point
   Cloudflare AI Search at the markdown prefix.

Both pipelines should start from the same canonical PDF and markdown artifacts.
The original FYI.org.nz attachment URL, request URL, R2 keys, and stable document
IDs must be carried through every layer so search results can link to the origin
request page and show an inline markdown preview.

## Why Change

The current FYI pipeline writes through LlamaIndex local storage. In practice
that means large JSON vector and document stores that are expensive to rewrite
and easy to load into process memory. During the latest run the machine was not
compute-bound; it exhausted RAM and swap while the embedding process was blocked
on disk writes. The failure mode points at storage shape, not Docling throughput.

AI Search can convert PDFs to markdown, but it currently has a 4 MB per-file
indexing limit. The local FYI corpus has 26,137 PDFs, and 1,996 of them are
larger than 4 MB. Those large PDFs account for more than half of the PDF bytes.
Converting everything to markdown first gives both pipelines the same input,
avoids AI Search skipping large source PDFs, and gives us markdown previews for
the website.

## Corpus Artifacts

Use a separate public/search corpus bucket instead of pointing AI Search at the
existing operational artifact bucket. The operational bucket contains private
workflow material such as inbound `.eml` files and authority uploads before
review.

Recommended bucket layout:

```text
r2://sunlight-corpus/
  canonical/
    fyi/
      v1/
        pdf/
          request/{fyi_request_id}/response/{fyi_response_id}/attach/{attach_id}/{sha256}-{safe_filename}.pdf

    sunlight/
      v1/
        request/{sunlight_request_id}/response/{sunlight_response_id}/attachment/{attachment_id}/{sha256}-{safe_filename}

  markdown/
    fyi/
      v1/
        request/{fyi_request_id}/response/{fyi_response_id}/attach/{attach_id}/{document_id}.md

    sunlight/
      v1/
        request/{sunlight_request_id}/response/{sunlight_response_id}/attachment/{attachment_id}/{document_id}.md

  chunks/
    fyi/
      v1/
        {document_id}.jsonl

    sunlight/
      v1/
        {document_id}.jsonl

  manifests/
    fyi/v1/files.ndjson
    fyi/v1/upload-report.ndjson
    fyi/v1/eval-documents.ndjson
```

Only the `markdown/...` prefix should be connected to AI Search for the markdown
pipeline. The `canonical/...` prefix preserves source PDFs. The `chunks/...`
prefix is for our own retrieval/debugging pipeline, not for AI Search indexing
unless we intentionally run a chunk-file experiment later.

For new Sunlight responses, keep the private intake path unchanged:

```text
sunlight-request-artifacts/sunlight-requests/{request_id}/...
```

After review/approval, copy public-safe artifacts into `sunlight-corpus`, write
D1 metadata rows, and enqueue conversion/indexing jobs.

## FYI Source URLs

The FYI attachment URL can be derived from the local file path:

```text
/mnt/dgx-ssd/src/sunlight_nz/fyi/data/request/{request_id}/response/{response_id}/attach/{attach_id}/{filename}
```

maps to:

```text
https://fyi.org.nz/request/{request_id}/response/{response_id}/attach/{attach_id}/{filename}
```

Also store the request page URL:

```text
https://fyi.org.nz/request/{request_id}
```

Carry both through the system:

* Markdown front matter for human-readable provenance and markdown previews.
* R2 custom metadata for AI Search filtering/result attributes.
* LanceDB columns for local evaluation and export.
* Vectorize metadata for result cards and citation links.
* D1 disclosed-document rows as the canonical relational record.

Example markdown front matter:

```markdown
---
document_id: doc_fyi_12117_47232_2_abcd1234
source: fyi
source_url: https://fyi.org.nz/request/12117/response/47232/attach/2/Morrison%20OIA%20response.pdf
request_url: https://fyi.org.nz/request/12117
fyi_request_id: 12117
fyi_response_id: 47232
fyi_attachment_id: 2
original_filename: Morrison OIA response.pdf
pdf_r2_key: canonical/fyi/v1/pdf/request/12117/response/47232/attach/2/abcd1234-morrison-oia-response.pdf
markdown_r2_key: markdown/fyi/v1/request/12117/response/47232/attach/2/doc_fyi_12117_47232_2_abcd1234.md
---
```

AI Search can read custom metadata from R2 objects through S3-compatible
`x-amz-meta-*` headers, but each instance has only five custom metadata fields
and text values are capped at 500 characters. Use those fields carefully.
Recommended AI Search custom metadata schema:

```text
source: text
corpus_version: number
visibility: text
source_url: text
request_url: text
```

The object key already carries request/response/attachment IDs, so do not spend
scarce AI Search metadata fields on IDs that are recoverable from the key. If we
need richer filtering later, create a second AI Search instance with a different
schema rather than overloading this one.

## Main Pipeline: Docling, LanceDB, Vectorize

The main pipeline is the one we own end to end:

```text
FYI PDFs
  -> Docling workers
  -> markdown files on local disk
  -> upload markdown/PDF artifacts to R2
  -> bounded markdown queue
  -> single embedding worker
  -> LanceDB append-only table
  -> Vectorize upsert or NDJSON upload
```

Use LanceDB as the local streaming vector store for this path. The previous
SQLite plan was a good minimal spool, but LanceDB is now a better fit because we
want local A/B evaluation, ad hoc similarity checks, and a durable local backup
of chunk vectors without building our own vector-table conventions.

LanceDB table columns should include:

```text
chunk_id
vector
document_id
chunk_index
chunk_text
text_preview
source
source_url
request_url
fyi_request_id
fyi_response_id
fyi_attachment_id
original_filename
pdf_r2_key
markdown_r2_key
embedding_model
text_sha256
created_at
vectorize_uploaded_at
```

Vectorize metadata should be compact but citation-ready:

```json
{
  "id": "chunk_...",
  "values": [0.0123, -0.0456],
  "metadata": {
    "document_id": "doc_fyi_12117_47232_2_abcd1234",
    "chunk_id": "chunk_...",
    "source": "fyi",
    "source_url": "https://fyi.org.nz/request/12117/response/47232/attach/2/Morrison%20OIA%20response.pdf",
    "request_url": "https://fyi.org.nz/request/12117",
    "markdown_r2_key": "markdown/fyi/v1/request/12117/response/47232/attach/2/doc_fyi_12117_47232_2_abcd1234.md",
    "chunk_index": 12,
    "embedding_model": "Qwen3-Embedding-0.6B",
    "text_preview": "First few hundred characters..."
  }
}
```

Do not make Vectorize the canonical full-text store. It should have enough
metadata to render a useful result immediately, then the app can fetch markdown
from R2 for inline preview and citations.

## AI Search Pipeline: R2 Markdown Source

The AI Search eval path should index the same markdown artifacts:

```text
Docling markdown files
  -> R2 `markdown/fyi/v1/**`
  -> AI Search R2 source with prefix/path filters
  -> AI Search search/chat API
```

Create the AI Search instance against the corpus bucket and scope it to the
markdown prefix:

```bash
pnpm dlx wrangler@latest ai-search create sunlight-fyi-markdown \
  --type r2 \
  --source sunlight-corpus \
  --prefix markdown/fyi/v1/ \
  --include-items '/markdown/fyi/v1/**/*.md'
```

Use the exact Wrangler syntax supported by the installed Wrangler version when
we run it; the important configuration is R2 source, markdown prefix, and a
narrow include filter.

The website search/chat UI should treat AI Search results similarly to Vectorize
results:

1. Read `source_url` and `request_url` from AI Search custom metadata when
   present.
2. Use the returned `folder`/`filename` attributes to reconstruct the markdown
   R2 key.
3. Fetch the markdown object from R2 for inline preview.
4. Link the public citation to `request_url` or `source_url` depending on the UI
   context.

## D1 Metadata

D1 remains the canonical relational layer for public records and provenance. It
should not store the full markdown corpus inline.

Recommended shape:

```sql
CREATE TABLE disclosed_documents (
  id TEXT PRIMARY KEY,
  source TEXT NOT NULL,
  source_url TEXT NOT NULL,
  request_url TEXT,
  original_filename TEXT,
  pdf_r2_key TEXT,
  markdown_r2_key TEXT,
  markdown_sha256 TEXT,
  visibility TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE disclosed_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES disclosed_documents(id),
  chunk_index INTEGER NOT NULL,
  vectorize_id TEXT UNIQUE,
  chunk_r2_key TEXT,
  text_preview TEXT,
  embedding_model TEXT,
  created_at TEXT NOT NULL
);
```

This lets the public app resolve either pipeline's search result back to the
same canonical document record.

## Evaluation Plan

Evaluate both pipelines on the same question set and document subset.

Metrics:

* Does the answer cite the right FYI request or source attachment?
* Does the retrieved markdown preview contain the supporting passage?
* Retrieval latency and end-to-end answer latency.
* Conversion quality for tables, scanned documents, and long attachments.
* Coverage: documents indexed, documents skipped, conversion failures.
* Cost: local GPU time plus Vectorize/R2 versus AI Search/Workers AI usage.
* Operational control: retry behavior, provenance quality, re-indexing friction.

Use a manifest such as `manifests/fyi/v1/eval-documents.ndjson` to pin the eval
set so both pipelines are tested against the same documents.

## Recommended Next Implementation Slice

1. Update the FYI conversion step to emit markdown with provenance front matter
   and deterministic document IDs.
2. Add an R2 upload command that uploads only markdown and canonical PDFs into
   `sunlight-corpus`, excluding FYI JSON/HTML/CSV sidecars and local metadata.
3. Add LanceDB streaming storage to the embedding worker and stop using
   LlamaIndex JSON persistence.
4. Upload main-pipeline vectors to Vectorize with `source_url`, `request_url`,
   and `markdown_r2_key` metadata.
5. Create an AI Search instance scoped to the R2 markdown prefix.
6. Build a small eval harness that queries both systems and records comparable
   results.

## Sources

* Cloudflare AI Search R2 data source:
  https://developers.cloudflare.com/ai-search/configuration/data-source/r2/
* Cloudflare AI Search supported file types and 4 MB file limit:
  https://developers.cloudflare.com/ai-search/configuration/data-source/
* Cloudflare AI Search path filtering:
  https://developers.cloudflare.com/ai-search/configuration/indexing/path-filtering/
* Cloudflare AI Search metadata limits and R2 custom metadata behavior:
  https://developers.cloudflare.com/ai-search/configuration/indexing/metadata/
* Cloudflare AI Search limits and pricing:
  https://developers.cloudflare.com/ai-search/platform/limits-pricing/
* Cloudflare Vectorize metadata and metadata index limits:
  https://developers.cloudflare.com/vectorize/get-started/intro/
* Cloudflare Vectorize insert and NDJSON guidance:
  https://developers.cloudflare.com/vectorize/best-practices/insert-vectors/
* Cloudflare D1 supported SQLite extensions:
  https://developers.cloudflare.com/d1/sql-api/sql-statements/
* Cloudflare D1 limits:
  https://developers.cloudflare.com/d1/platform/limits/
* Cloudflare R2 storage guidance:
  https://developers.cloudflare.com/r2/how-r2-works/
* LanceDB quickstart:
  https://docs.lancedb.com/quickstart
