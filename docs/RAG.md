# RAG Roadmap

End-to-end plan to finish both retrieval pipelines for the FYI.org.nz corpus and
wire them into the public Sunlight site. `docs/VECTORS.md` is the source of
truth for the dual-pipeline decision, R2 layout, and metadata shapes. This file
tracks the *execution* plan: what is done, what is next, and how each remaining
step ties back to that design.

## Current State

| Pipeline | Status | Notes |
| --- | --- | --- |
| A — Docling → LanceDB → Vectorize | **Done** | 318,749 chunks in `fyi-v2` |
| B — R2 markdown → Cloudflare AI Search | Not started | Markdown exists locally, not uploaded |

### Pipeline A — what landed

* 26,106 FYI PDFs converted to markdown via Docling (10 conversion workers,
  7:3 split across dual RTX 5090s).
* Embeddings produced with `Qwen3-Embedding-0.6B` (bf16, FlashAttention-2,
  GPU 1).
* LanceDB table `chunks_v2` at `./storage/fyi_parallel.lancedb` is the local
  canonical chunk store.
* Vectorize index `fyi-v2` populated from 213 NDJSON shards (1,500 rows each,
  ~28 MB per shard). All shards have `.uploaded` sidecars with the
  Cloudflare `mutationId`.
* Per-chunk Vectorize metadata is enriched with per-request FYI fields via
  `scripts/fyi_request_metadata.py` (96.8% chunk-to-request coverage).
* Six metadata indexes are live and queryable:
  `authority_slug`, `authority_category`, `document_id`, `fyi_request_id`,
  `request_year`, `described_state`.
* Token: `CLOUDFLARE_VECTORIZE_TOKEN` in `.env` (Vectorize Read + Write
  permission groups). Account-wide `TOKEN_TOKEN` was used to mint it — see
  the matching memory entry.

### Pipeline B — what is missing

* `sunlight-corpus` R2 bucket has not been provisioned.
* No canonical PDFs or markdown have been uploaded to R2.
* No AI Search instance exists.
* No eval harness exists; no eval question set has been pinned.
* The public Worker endpoint (`opendata.org.nz/api/ask`) is not yet wired.

## Roadmap

The remaining work is six steps. Steps 1–3 are gated on each other; 4 can run
in parallel with 3; 5 depends on 3 and 4; 6 is its own track.

### 1. Provision the `sunlight-corpus` R2 bucket

A dedicated public/search bucket, separate from the operational
`sunlight-request-artifacts` bucket (which holds private inbound `.eml` and
pre-review authority uploads).

```bash
pnpm dlx wrangler@latest r2 bucket create sunlight-corpus
```

Then add the binding to `wrangler.jsonc` so Workers and Pages can read from it.
Keep public read off the bucket itself; serve through a Worker that enforces the
`visibility=public` custom metadata flag.

### 2. Upload canonical PDFs and markdown

Build `scripts/upload_to_r2.py` that walks `fyi/data/...` plus the converted
markdown tree and uploads to keys matching the Vectorize metadata exactly so
both pipelines resolve to the same objects:

```
canonical/fyi/v1/pdf/request/{request_id}/response/{response_id}/attach/{attach_id}/{sha256}-{safe_filename}.pdf
markdown/fyi/v1/request/{request_id}/response/{response_id}/attach/{attach_id}/{document_id}.md
```

Per-object R2 custom metadata (within the five-field AI Search budget):

```
source        = "fyi"
corpus_version = "1"
visibility    = "public"
source_url    = "https://fyi.org.nz/request/{request_id}/response/{response_id}/attach/{attach_id}/{filename}"
request_url   = "https://fyi.org.nz/request/{request_id}"
```

Exclude FYI JSON/HTML/CSV sidecars from the upload — those are scraper input,
not corpus artifacts. Write `manifests/fyi/v1/upload-report.ndjson` so re-runs
are idempotent (skip when sha256 matches).

### 3. Create the Cloudflare AI Search instance

Scoped only to the markdown prefix so AI Search never touches PDFs or chunk
files:

```bash
pnpm dlx wrangler@latest ai-search create sunlight-fyi-markdown \
  --type r2 \
  --source sunlight-corpus \
  --prefix markdown/fyi/v1/ \
  --include-items '/markdown/fyi/v1/**/*.md'
```

Adjust to the actual Wrangler flag shape at the time of execution. Confirm the
instance picks up the five custom metadata fields from R2 object headers.

### 4. Build the eval harness

`scripts/eval_rag.py` runs a pinned question set through both pipelines and
records comparable results.

Inputs:

* `manifests/fyi/v1/eval-documents.ndjson` — the subset of documents the eval
  is allowed to cite (so both pipelines see the same target universe).
* `manifests/fyi/v1/eval-questions.ndjson` — questions with expected
  request/response/attachment IDs and an expected supporting passage.

Per-question output row:

```json
{
  "question_id": "...",
  "pipeline": "vectorize" | "ai_search",
  "top_k": [{"document_id": "...", "score": 0.78, "request_url": "..."}],
  "cited_correct_request": true,
  "retrieval_ms": 134,
  "answer_ms": 812,
  "answer_text": "...",
  "passage_overlap": 0.61
}
```

Metrics aggregated across the run, per `docs/VECTORS.md` "Evaluation Plan":
citation accuracy, retrieved-passage overlap, latency, conversion quality on
the cited document, coverage gaps, cost, and operational friction. Output a
side-by-side markdown report into `manifests/fyi/v1/eval-report-{timestamp}.md`.

The harness is the artifact that lets us decide whether to standardize on one
pipeline or keep both.

### 5. Wire the public `opendata.org.nz/api/ask` Worker

A Worker that takes a natural-language question and returns a grounded answer
plus citations. Composition:

1. Embed the question with `@cf/qwen/qwen3-embedding-0.6b` (Workers AI).
2. Query Vectorize `fyi-v2` with the embedding and a metadata filter when the
   user constrains by authority/year/state.
3. Hydrate the top-k results by fetching markdown chunks from R2 via
   `markdown_r2_key`.
4. Generate the answer with `@cf/google/gemma-4-26b-a4b-it` using a strict
   citations-required prompt.
5. Return JSON with answer text, citation list (each linking to `request_url`
   on fyi.org.nz), and the chunk snippets used.

Same Worker exposes a second route that calls AI Search instead of Vectorize so
the public site can toggle pipelines or compare answers.

Bindings required: `VECTORIZE` (index `fyi-v2`), `AI` (Workers AI),
`SUNLIGHT_CORPUS` (R2), and a future AI Search binding once available.

### 6. Integrate first-party Sunlight inbound documents

Once Sunlight starts receiving real authority responses (`apps/authority` is
already live), gate them through the existing review/publish step in admin,
then copy public-safe artifacts into `sunlight-corpus/{canonical,markdown}/sunlight/v1/...`
with the same key shape and custom metadata schema. The same ingestion
pipeline used for FYI then embeds them into Vectorize and AI Search picks them
up via the prefix scan.

Per `docs/VECTORS.md`, D1 (`disclosed_documents`, `disclosed_chunks`) is the
canonical relational layer that resolves either pipeline's search result back
to the same document record.

## Open Questions

* Do we want a single AI Search instance covering both `fyi/` and `sunlight/`
  markdown, or one per source? Single instance is simpler but spends the five
  metadata fields once for both.
* Should the Worker stream answers (SSE) for the website, or return a single
  JSON object? Streaming is nicer UX but doubles the Worker complexity.
* What is the eval question set? We need ~50 questions drawn from real FYI
  threads with known correct citations. This is the next concrete blocker on
  step 4.

## Pointers

* Design rationale, R2 layout, metadata schemas, evaluation criteria —
  `docs/VECTORS.md`.
* Phase-level project plan (Phases 5 and 7 cover this work) — `docs/PLAN.md`.
* Operational state and verification commands — `PROGRESS.md`.
* Vectorize export — `scripts/export_to_vectorize.py`.
* Vectorize upload — `scripts/upload_to_vectorize.py`.
* Per-request FYI metadata join — `scripts/fyi_request_metadata.py`.
