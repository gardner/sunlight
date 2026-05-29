# Inventory: Ingestion, LLM, Embeddings, and RAG

This inventory catalogs the current repo paths that collect documents, convert
documents, call LLMs, calculate embeddings, build retrieval indexes, publish
datasets, or evaluate those systems.

The main architectural boundary is:

* `sunlight.nz` should be the OIA/LGOIMA request engine and first-party
  disclosure workflow. It is one upstream data source for OpenData.
* `apps/opendata` should be the dataset publication surface for public corpora
  such as FYI, Tenancy Tribunal, Disputes Tribunal, and later Sunlight
  disclosure datasets. It should own dataset search and chatbots.
* Scraping and markdown conversion can be owned by an external spider service.
  The handoff to this repo should be an R2/S3 bucket with directory manifests.
* Corpus processing should be shared infrastructure, not a one-off pile of
  FYI-, Tenancy-, or vLLM-specific scripts.

## Product Boundary

| Area | Current files | Current role | Production boundary |
| --- | --- | --- | --- |
| Sunlight operational engine | `apps/admin`, `apps/authority`, `apps/inbound-email`, `cloudflare/migrations` | Create OIA/LGOIMA requests, collect responses, store uploads, review workflow | Keep here. This is the OIA/LGOIMA engine. |
| Sunlight public site/search | `apps/landing` | Landing page plus `/search` and `/api/search` over the current public FYI-style index | Should shrink back to Sunlight request/response product concerns. Broad corpus search and chat belong in OpenData. |
| OpenData publication site | `apps/opendata`, `docs/OPENDATA.md` | Static public-interest data site; no dataset registry or pipeline yet | Should own dataset pages, download manifests, provenance, corpus-specific search, and dataset chatbots. |
| External spider service | Outside this repo | Scrapes public data and converts source documents to markdown | Handoff is R2/S3 prefixes plus manifests. This repo should consume those prefixes as queues. |
| Corpus processing scripts | `scripts/*`, `vllm/*` | Mixed production-ish pipelines, probes, evals, and experiments | Promote stable code into shared corpus pipeline modules with thin CLI entrypoints. |
| Local/vector stores | `storage/**`, `fyi/**`, `justice/**`, `vllm/results/**` | Local source data, converted markdown, LanceDB stores, eval/extraction outputs | Treat as build artifacts and source snapshots, not application code or canonical product boundaries. |

## External Spider Handoff

The production ingestion boundary should be a bucket contract, not local scrape
logic. The spider service should scrape and convert documents to markdown, then
write source objects, markdown, metadata, and a manifest into an R2/S3 bucket.
This repo should read those manifests and process each directory as a resumable
queue.

Recommended bucket shape:

```text
s3://opendata-ingest/
  manifests/
    justice_tenancy/v1/2026-05-29T000000Z.json
    justice_disputes/v1/2026-05-29T000000Z.json
    fyi_oia/v1/2026-05-29T000000Z.json
    sunlight_disclosures/v1/2026-05-29T000000Z.json
  corpora/
    justice_tenancy/v1/markdown/...
    justice_tenancy/v1/assets/...
    justice_tenancy/v1/metadata/...
    justice_disputes/v1/markdown/...
    fyi_oia/v1/markdown/...
    sunlight_disclosures/v1/markdown/...
```

The manifest should tell the importer how to process the directory. It should
not rely on path naming alone.

Minimum manifest fields:

| Field | Purpose |
| --- | --- |
| `manifest_version` | Version the handoff contract independently from dataset schema versions. |
| `corpus_id` | Stable corpus id such as `justice_tenancy`, `justice_disputes`, `fyi_oia`, or `sunlight_disclosures`. |
| `dataset_id` | Public OpenData dataset id, which may be broader than a single corpus run. |
| `source_system` | `external_spider`, `sunlight`, or another source producer. |
| `import_profile` | Selects the processing recipe, schema, extraction prompt, privacy rules, and indexes. |
| `snapshot_id` | Immutable spider output version for idempotency and reproducibility. |
| `input_prefixes` | Markdown, source assets, metadata sidecars, and optional prior extraction prefixes. |
| `document_id_strategy` | How stable document ids are derived or read. |
| `metadata_schema` | Expected metadata shape and required fields. |
| `extraction_schema` | Optional LLM structured extraction schema to run after import. |
| `privacy_profile` | PII/redaction rules and publication gates. |
| `index_targets` | OpenData search/chat indexes to update after validation. |
| `publish_targets` | Dataset outputs such as OpenData pages, Parquet, JSONL, R2 public prefixes, or Hugging Face. |

Queue behavior:

1. Poll or receive manifest notifications from the ingest bucket.
2. Register an import run keyed by `corpus_id + snapshot_id + manifest_etag`.
3. Enumerate markdown objects under the manifest prefixes.
4. Create idempotent work items with object key, ETag/checksum, document id, and
   selected `import_profile`.
5. Process each item through validation, extraction, chunking, embedding,
   indexing, and publication stages.
6. Persist stage status and output artifact keys so retries never duplicate
   rows or silently skip stale work.
7. Promote a dataset version only after manifest-level eval and validation
   gates pass.

This changes the role of local Docling conversion code. It remains useful for
development, validation, and Sunlight-owned uploaded responses when no spider
conversion exists, but the default public-corpus path should start from
spider-produced markdown in R2/S3.

## Corpus State

| Corpus | Current state | Main source paths | Main processing paths | Gaps |
| --- | --- | --- | --- | --- |
| Sunlight OIA/LGOIMA responses | Operational request/response intake exists. No production corpus export/indexing path found. | R2 `sunlight-request-artifacts`, D1 `sunlight-requests`; later OpenData ingest manifest from approved disclosures | `apps/admin`, `apps/authority`, `apps/inbound-email` | Need approval-to-publication export that makes Sunlight disclosures one OpenData source. |
| FYI OIA/LGOIMA archive | Most mature RAG corpus. Current code owns Docling conversion, local LanceDB vectors, Vectorize export, D1 BM25, Hugging Face dataset export. Target path should consume spider-produced markdown/manifests. | Today: `fyi/data/request`, `fyi/markdown`. Target: R2/S3 `fyi_oia` manifest prefixes. | `scripts/parallel_convert_and_embed.py`, `scripts/export_to_vectorize.py`, `scripts/upload_to_vectorize.py`, `scripts/export_bm25_to_d1.py`, `scripts/export_hf_markdown_dataset.py` | Names and bindings are FYI-specific and currently leak into generic search. Need importer profile from manifests. |
| Tenancy Tribunal | Production-ish local Docling and embedding path exists. Structured vLLM extraction path exists and looks promising. Target path should consume spider-produced tribunal markdown/manifests. | Today: `justice/data/tenancy/**`, `storage/justice/tenancy/markdown_docling`. Target: R2/S3 `justice_tenancy` manifest prefixes. | `scripts/ingest_tenancy.py`, `scripts/tenancy_corpus.py`, `scripts/tenancy_llm.py`, `vllm/tribunal_process_docling.py` | Need source/extraction separation, corpus-neutral indexing, OpenData dataset publication, and better eval gates before publishing. |
| Disputes Tribunal | No first-class ingestion adapter found. Repo searches for `disputes`/`Disputes Tribunal` only found planning-level references. | Target: R2/S3 `justice_disputes` manifest prefixes from external spider. | None found | Needs a manifest import profile and tribunal adapter that reuses the Tenancy/vLLM pipeline contract. |
| Authority/contact metadata | Mature operational metadata ingestion and scraping exists. | FYI authority imports, MoJ directory, authority websites | `scripts/import_fyi_authorities.py`, `scripts/scrape_authority_contacts.py`, `scripts/scrape_moj_directory.py`, `scripts/import_moj_authorities.py`, `scripts/scrape_proactive_pages.py` | This supports the OIA engine, not public corpus RAG directly. Keep it separate from dataset pipelines. |

## Current Ingestion Processes

### 1. Operational OIA/LGOIMA Engine

Files:

* `apps/admin`
* `apps/authority`
* `apps/inbound-email/src/index.ts`
* `scripts/import_fyi_authorities.py`
* `scripts/scrape_authority_contacts.py`
* `scripts/scrape_moj_directory.py`
* `scripts/import_moj_authorities.py`
* `scripts/scrape_proactive_pages.py`
* `cloudflare/migrations/*`

Current flow:

1. Authorities and contact addresses are imported/scraped into D1
   `sunlight-requests`.
2. Admin users create templates, cycles, and `SunlightRequest` rows.
3. Outbound email is generated and tracked.
4. Authority response uploads go through `apps/authority` into R2
   `sunlight-request-artifacts`.
5. Inbound emails go through `apps/inbound-email`, store raw email and
   attachments in R2, associate replies by token or `In-Reply-To`, and insert
   response records in D1.

LLM/AI use:

* `apps/inbound-email/src/index.ts` uses Workers AI
  `@cf/moonshotai/kimi-k2.6` to triage whether an inbound email needs human
  review.
* The same worker has a `/test-ai` route using
  `@cf/qwen/qwen3-embedding-0.6b`; this is a smoke/test route, not a corpus
  embedding pipeline.

Production status:

* This is application workflow code, not a dataset pipeline.
* Sunlight should publish approved disclosure snapshots to the OpenData ingest
  bucket or manifest registry. OpenData then owns dataset indexing, search, and
  chat over those disclosures.
* There is no completed path that turns approved Sunlight response artifacts
  into OpenData manifest entries, corpus records, markdown, embeddings,
  Vectorize rows, D1 BM25 rows, or dataset pages.

### 2. FYI Corpus Conversion, Embedding, and Indexing

Prototype paths:

| File | Purpose | Status |
| --- | --- | --- |
| `scripts/ingest_fyi.py` | Early LlamaIndex index over FYI JSON metadata with Qwen embeddings | Prototype only |
| `scripts/ingest_fyi_docling.py` | Early DoclingReader plus LlamaIndex path over 3 PDFs | Prototype only |
| `scripts/convert_and_embed.py` | Early 5-PDF Docling to markdown to LlamaIndex VectorStoreIndex | Prototype only |

Current main path:

| File | Purpose |
| --- | --- |
| `scripts/parallel_convert_and_embed.py` | Main FYI Docling conversion plus Qwen embedding plus LanceDB chunk writer |
| `scripts/fyi_markdown.py` | Frontmatter parsing/rendering and markdown chunking |
| `scripts/fyi_lancedb_writer.py` | Shared-ish LanceDB `chunks_v2` schema and upsert writer |
| `scripts/embedding_helpers.py` | Qwen embedding model kwargs and deterministic chunk IDs |
| `scripts/export_to_vectorize.py` | Streams LanceDB rows into Vectorize NDJSON |
| `scripts/upload_to_vectorize.py` | Uploads NDJSON shards to Cloudflare Vectorize |
| `scripts/export_bm25_to_d1.py` | Exports chunk rows to D1 SQL for FTS5/BM25 |
| `scripts/export_hf_markdown_dataset.py` | Builds a Hugging Face-ready Parquet dataset from FYI markdown |

Data flow:

1. Current local path starts from PDFs under `fyi/data/request`.
2. Current local Docling conversion writes markdown under `fyi/markdown` with
   provenance frontmatter.
3. Markdown is chunked with the same chunking helpers used by search/BM25.
4. Local `Qwen/Qwen3-Embedding-0.6B` embeddings are calculated with
   `llama-index-embeddings-huggingface`.
5. Chunk records are written to LanceDB, usually
   `storage/fyi_parallel.lancedb`, table `chunks_v2`.
6. LanceDB rows export to Vectorize NDJSON.
7. NDJSON uploads to Cloudflare Vectorize index `fyi-v2`.
8. The same chunk source exports to D1 `sunlight-search` table
   `disclosed_chunks` plus `disclosed_chunks_fts`.
9. Public search in `apps/landing` queries Vectorize and D1 BM25.
10. Dataset export writes Parquet/manifest/card artifacts under
    `storage/huggingface/sunlight-fyi-markdown`.

Target handoff:

* External spider writes FYI markdown and metadata into R2/S3.
* This repo imports by reading the FYI manifest and queueing the listed
  prefixes.
* Docling conversion should become a fallback/dev path, not the normal FYI
  import path.

Production status:

* This is the most complete corpus pipeline in the repo.
* It still carries FYI-specific names through generic layers.
* Vectorize binding/index names are not corpus-neutral: `FYI_VECTORS`,
  `fyi-v2`.
* D1 BM25 table names are more generic (`disclosed_chunks`) but the importer is
  still FYI-first by default.

### 3. Tenancy Tribunal Corpus

Files:

| File | Purpose |
| --- | --- |
| `scripts/tenancy_corpus.py` | Source adapter for Tenancy sidecars/PDFs, deterministic document IDs, metadata, R2 keys |
| `scripts/ingest_tenancy.py` | Main Docling conversion, optional LLM enrichment, Qwen embeddings, LanceDB writes |
| `scripts/tenancy_llm.py` | Generated retrieval metadata schema, batching, provider calls, frontmatter update logic |
| `scripts/tenancy_llm_messages.py` | Tenancy enrichment prompt |
| `scripts/tenancy_llm_request.py` | Chat request options, JSON response mode, provider routing extras |
| `scripts/tenancy_instructor.py` | Instructor modes for JSON schema/tools/responses paths |
| `scripts/tenancy_rate_limit.py` | LLM request rate limiting |
| `scripts/scan_pii_gliner.py` | Output-only local PII span scanner |
| `scripts/scan_pii_privacy_filter.py` | Output-only OpenAI Privacy Filter scanner |

Current flow:

1. Current local path discovers source PDFs and sidecars from
   `justice/data/tenancy/pdfs` and `justice/data/tenancy/legacy/pdf`.
2. Current local Docling conversion writes canonical markdown into
   `storage/justice/tenancy/markdown_docling`.
3. Optional LLM enrichment writes generated frontmatter fields such as
   `case_summary`, `questions_answered`, `neutral_fact_pattern`,
   `claims_made`, and `legal_principles`.
4. Markdown and generated retrieval views are chunked with FYI-derived helpers.
5. Local Qwen embeddings are written to LanceDB at
   `storage/justice/tenancy/lancedb`, table `chunks_v2`.

Target handoff:

* External spider writes tribunal markdown and metadata into R2/S3 prefixes
  described by a `justice_tenancy` manifest.
* This repo validates the markdown, runs vLLM structured extraction if the
  manifest import profile requires it, chunks/embeds/indexes the documents, and
  publishes the dataset to OpenData.
* Local Docling conversion remains a validation/development tool or fallback for
  corpus sources that do not yet have spider-produced markdown.

Known local corpus counts from repo docs:

* 43,854 current plus legacy Tenancy Docling markdown files.
* 412,537 LanceDB chunk rows from the earlier current-corpus run.
* Full vLLM Docling structured extraction produced 43,854 extraction rows in
  `vllm/results/tribunal_docling_full_20260527_225730/extractions.jsonl`.

Production status:

* Conversion and embedding are production-ish.
* The old LLM enrichment path has documented risk because generated metadata was
  written into source markdown frontmatter and a truncation incident made prior
  generated values suspect. See `docs/DESTROYED_DATA.md`.
* Future Tenancy extraction should write sidecar JSONL/Parquet extraction
  artifacts, not mutate canonical markdown source.

### 4. vLLM Tribunal Extraction Lab

Files:

| File | Purpose |
| --- | --- |
| `vllm/tribunal_eval_runner.py` | Structured extraction eval over sampled Tenancy markdown with gold fields |
| `vllm/tribunal_process_docling.py` | Full Docling markdown structured extraction runner |
| `vllm/tribunal_eval_schema.py` | Extraction schemas and validation helpers |
| `vllm/tribunal_eval_extract.py` | Field extraction/scoring helpers |
| `vllm/tribunal_judge_spotcheck.py` | LLM judge spot-checks over document plus extraction |
| `vllm/BATCHES.md` | Batch design, token accounting, run notes |

Current flow:

1. Read Docling markdown from `storage/justice/tenancy/markdown_docling`.
2. Build OpenAI-compatible chat/completions batch payloads.
3. Use vLLM model `Qwen/Qwen3.6-27B-FP8` by default.
4. Always send thinking-enabled requests for the tribunal extraction path:
   `chat_template_kwargs.enable_thinking=true`,
   `thinking_token_budget=2048`, and `max_tokens=4096`.
5. Request strict structured JSON and perform local parse/schema validation.
6. Write run artifacts under `vllm/results`.

Production status:

* This path is exploratory but close to the desired structured extraction
  service.
* It intentionally bypasses the older `scripts/` ingestion pipeline.
* The code should become the generic tribunal extraction stage after the schema,
  token accounting, evals, and artifact contracts settle.

### 5. Disputes Tribunal

No runnable Disputes Tribunal corpus pipeline was found.

Production implication:

* Do not copy `scripts/ingest_tenancy.py`.
* Build a generic tribunal source adapter interface, then implement both
  `justice_tenancy` and `justice_disputes` adapters against it.
* Reuse the vLLM extraction schema runner where the legal-document structure is
  compatible, but keep corpus-specific fields in schemas or schema variants.

## LLM Call Catalog

| Path | Provider/model | Purpose | Output controls | Status/risk |
| --- | --- | --- | --- | --- |
| `apps/inbound-email/src/index.ts` | Workers AI `@cf/moonshotai/kimi-k2.6` | Human-review triage for inbound authority email | Prompt asks for JSON object; parser extracts JSON from several response shapes | Operational helper. Should remain separate from corpus extraction. |
| `apps/landing/app/api/search/route.ts` | Workers AI `@cf/google/gemma-4-26b-a4b-it` | Generate grounded public search answer | `max_tokens`/`max_completion_tokens=1600`, `reasoning_effort=low`, `temperature=0.2` | Runtime search answer generation. Not corpus creation. |
| `scripts/generate_eval_questions.py` | Local vLLM model in historical docs | Generate FYI search eval questions | Writes NDJSON eval manifest | Eval data generation only. |
| `scripts/tenancy_llm.py` through `scripts/ingest_tenancy.py` | MiniMax/OpenRouter/NVIDIA/Bifrost capable, defaults currently MiniMax-style in docs/tests | Generate Tenancy retrieval metadata | Instructor JSON schema/json mode or chat `json_object`/`json_schema` | Risky because it mutates markdown frontmatter; preserve only as legacy/resumable path until refactored. |
| `scripts/probe_nvidia_tenancy_models.py` | NVIDIA OpenAI-compatible models | Capability and rate probes over real Tenancy prompts | JSON response parsing and summary artifacts | Probe only. |
| `vllm/tribunal_eval_runner.py` | vLLM `Qwen/Qwen3.6-27B-FP8` | Sampled Tenancy structured extraction eval | Strict JSON schema plus local validation; thinking enabled | Strong candidate for production extraction harness. |
| `vllm/tribunal_process_docling.py` | vLLM `Qwen/Qwen3.6-27B-FP8` | Full Tenancy Docling structured extraction | Strict JSON schema plus repair retries; thinking enabled | Best current full-corpus extraction path. |
| `vllm/tribunal_judge_spotcheck.py` | vLLM and OpenRouter judge models | Judge document-vs-extraction consistency | JSON audit schema | Triage only until false-positive behavior is calibrated. |

Provider/config fracture points:

* LLM provider configuration is scattered across `.env`, CLI defaults, Bifrost
  config, vLLM scripts, and Workers bindings.
* Some paths are runtime app calls, some are corpus-build calls, and some are
  eval/probe calls. They should not share accidental defaults.
* Thinking and token settings are now enforced in vLLM tribunal extraction, but
  other provider paths have independent knobs and response-shape quirks.

## Embedding Catalog

| Path | Model | Purpose | Output store |
| --- | --- | --- | --- |
| `scripts/parallel_convert_and_embed.py` | `Qwen/Qwen3-Embedding-0.6B` via `HuggingFaceEmbedding` | FYI chunk embeddings | `storage/fyi_parallel.lancedb`, table `chunks_v2` |
| `scripts/ingest_tenancy.py` | `Qwen/Qwen3-Embedding-0.6B` via `HuggingFaceEmbedding` | Tenancy source/generated-view chunk embeddings | `storage/justice/tenancy/lancedb`, table `chunks_v2` |
| `scripts/eval_search.py` | `Qwen/Qwen3-Embedding-0.6B` via `HuggingFaceEmbedding` | Offline FYI retrieval eval query embeddings | In-memory search against LanceDB |
| `apps/landing/app/api/search/route.ts` | Workers AI `@cf/qwen/qwen3-embedding-0.6b` | Runtime user-query embedding | Query-time Vectorize search only |
| `apps/inbound-email/src/index.ts` | Workers AI `@cf/qwen/qwen3-embedding-0.6b` | `/test-ai` smoke route | No corpus output |
| `scripts/test_*embed*.py`, `scripts/test_cf_tokens.py` | Various local/Cloudflare tests | Capability probes | No production output |

Embedding fracture points:

* The embedding model is repeated in multiple scripts instead of centralized as
  a corpus/index version.
* Embedding markers are file-based and can cause stale skip behavior when
  generated views or schemas change.
* LanceDB schema is shared-ish, but the writer still lives under an FYI-named
  script.

## RAG and Index Catalog

| Index/store | Current owner | Input | Purpose | Notes |
| --- | --- | --- | --- | --- |
| LanceDB `chunks_v2` | `scripts/fyi_lancedb_writer.py` | Chunk text, metadata, vectors | Local canonical vector store and export source | Used by FYI and Tenancy. Should become corpus-neutral. |
| Cloudflare Vectorize `fyi-v2` | `scripts/upload_to_vectorize.py`, `apps/landing` | NDJSON exported from LanceDB | Edge semantic retrieval | Name/binding are FYI-specific. Need corpus-neutral indexes or per-corpus routing. |
| D1 `sunlight-search.disclosed_chunks` | `scripts/export_bm25_to_d1.py`, `apps/landing` | Chunk text plus metadata | BM25/FTS5 sidecar retrieval | Good generic table name, but importer defaults are FYI-first. |
| Workers AI answer generation | `apps/landing/app/api/search/route.ts` | Top selected citations | Runtime RAG answer | Should not be confused with corpus ingestion. |
| Cloudflare AI Search | `docs/RAG.md`, `docs/VECTORS.md` | Planned R2 markdown prefixes | Managed retrieval alternative | Planned/eval path, not implemented. |
| R2/S3 ingest bucket | New manifest-driven queue needed | Spider-produced markdown, metadata, assets, and manifests | Handoff point between spider service and corpus importer | The importer should process manifests and prefixes as queues. |
| R2 public corpus bucket | `docs/VECTORS.md` | Validated PDFs, markdown, chunks, manifests, extraction artifacts | Durable public corpus object store | Planned as `sunlight-corpus`; not the same as operational `sunlight-request-artifacts` or the raw ingest bucket. |
| Hugging Face dataset export | `scripts/export_hf_markdown_dataset.py` | FYI markdown | Public dataset snapshot/delta | FYI only today; OpenData should own dataset catalog/links. |

## Eval and QA Inventory

| Area | Files | Purpose |
| --- | --- | --- |
| Search eval | `scripts/generate_eval_questions.py`, `scripts/eval_search.py`, `scripts/eval_search_bm25.py`, `scripts/eval_search_agentic.py`, `manifests/fyi/v1/eval-questions.ndjson` | Offline FYI retrieval eval, vector/BM25/hybrid metrics, agentic retrieval experiment |
| Tribunal extraction eval | `vllm/tribunal_eval_runner.py`, `vllm/tribunal_eval_schema.py`, `vllm/tribunal_eval_extract.py`, `tests/test_vllm_tribunal_batch_eval.py` | Structured extraction accuracy, schema validity, token budget sweeps |
| Tribunal judge spot-check | `vllm/tribunal_judge_spotcheck.py` | LLM-as-judge document/extraction audits | Current false-positive risk; use for triage only |
| Provider probes | `scripts/probe_nvidia_tenancy_models.py`, `docs/NVIDIA_NIM.md`, `vllm/BATCHES.md` | Capability, latency, parseability, rate behavior |
| PII scans | `scripts/scan_pii_gliner.py`, `scripts/scan_pii_privacy_filter.py` | Output-only redaction/privacy audit over tribunal markdown |
| Markdown converter comparison | `scripts/compare_markdown_converters.py`, `scripts/cloudflare_markdown_worker.ts` | Docling vs Cloudflare markdown conversion comparison |

## Storage and Artifact Layout

| Path/bucket | Contents | Canonical role |
| --- | --- | --- |
| `sunlight-request-artifacts` R2 | Raw inbound emails, authority uploads, operational response artifacts | Private/operational source store for the OIA engine |
| External R2/S3 ingest bucket | Spider-produced markdown, source assets, sidecars, and manifests | Queue source for public corpus processing |
| Planned `sunlight-corpus` R2 | Validated public PDFs, markdown, chunks, manifests, extraction sidecars | Public corpus object store for dataset/search publication |
| `fyi/data/request` | FYI source PDFs | Local source snapshot |
| `fyi/markdown` | FYI Docling markdown plus provenance | Local normalized corpus source |
| `storage/fyi_parallel.lancedb` | FYI chunk vectors | Local index/export source |
| `storage/huggingface/sunlight-fyi-markdown` | FYI Parquet/card/manifest dataset build | Dataset publication artifact |
| `justice/data/tenancy` | Tenancy source PDFs and sidecars | Local source snapshot |
| `storage/justice/tenancy/markdown_docling` | Tenancy Docling markdown | Local normalized corpus source |
| `storage/justice/tenancy/lancedb` | Tenancy chunk vectors | Local index/export source |
| `vllm/results` | Structured extraction/eval/judge artifacts | Extraction lab outputs, not canonical source |

## Main Fracture Points

1. `scripts/` mixes production-ish pipelines, one-off probes, app maintenance
   scripts, old LlamaIndex prototypes, and active corpus code.
2. FYI-specific naming leaks into generic infrastructure:
   `fyi_lancedb_writer.py`, `FYI_VECTORS`, `fyi-v2`,
   `parallel_convert_and_embed.py`, and default paths.
3. Tenancy processing reuses FYI helpers instead of a shared corpus package.
4. Generated LLM metadata has historically been written into canonical markdown
   frontmatter. That couples source conversion, enrichment, embedding, and
   publication too tightly.
5. vLLM exploration is promising but sits outside the production corpus
   pipeline contracts.
6. OpenData is currently a website, not a dataset publication, search, or
   chatbot app.
7. Sunlight public search currently behaves like a broad public corpus search,
   while the product boundary should reserve Sunlight for OIA/LGOIMA operations.
   Sunlight disclosures should flow into OpenData as one dataset source.
8. There is no Disputes Tribunal adapter.
9. Token budgets, model IDs, provider choices, response parsing, and retry
   policies are duplicated across paths.
10. Evaluation exists, but each area has its own harness and artifact shape.
11. No manifest-driven queue exists yet for processing spider-produced R2/S3
    directories.

## Recommended Production Shape

Create a shared corpus pipeline with stable manifest, queue, and stage
contracts. The immediate goal is not a huge framework; it is to stop copying
pipeline logic across FYI, Tenancy, Disputes, and Sunlight disclosures.

Suggested stages:

1. `register_manifest`: read an R2/S3 manifest and create an idempotent import
   run.
2. `queue`: enumerate manifest prefixes and create object-level work items.
3. `validate`: verify markdown, sidecars, checksums, required metadata, and
   source provenance.
4. `normalize`: produce deterministic corpus metadata and public R2 keys.
5. `extract`: run structured LLM extraction into sidecar JSONL/Parquet when the
   manifest profile requires it.
6. `enrich`: optionally produce generated retrieval views as separate artifacts.
7. `chunk`: produce deterministic chunks with chunk schema versioning.
8. `embed`: calculate vectors and write a local corpus-neutral vector store.
9. `index`: export to Vectorize, D1 BM25, AI Search, or other retrieval stores
   used by OpenData.
10. `publish`: write OpenData dataset manifests, cards, downloads, search pages,
    and chatbot configuration.
11. `eval`: run schema, extraction, retrieval, privacy, and publication gates.

Optional stage:

* `convert`: create canonical markdown from source PDFs or uploaded files only
  for Sunlight-owned uploads or corpora that do not yet have spider-produced
  markdown. It should not be the default public-corpus ingestion boundary.

Suggested adapters:

| Adapter | Source | Initial implementation |
| --- | --- | --- |
| `fyi_oia` | External spider manifest for FYI public OIA/LGOIMA markdown | Wrap current FYI chunking, embedding, Vectorize, BM25, and dataset export paths; demote local Docling to fallback |
| `sunlight_disclosures` | Approved Sunlight response artifacts exported from operational D1/R2 | New exporter from Sunlight into OpenData manifest format, then normal manifest import |
| `justice_tenancy` | External spider manifest for Tenancy Tribunal markdown | Wrap current tribunal metadata/extraction/indexing logic around manifest queue items |
| `justice_disputes` | External spider manifest for Disputes Tribunal markdown | New adapter modeled on tribunal manifest profile, not copied from Tenancy |

Suggested code organization:

* Keep CLI entrypoints in `scripts/` for now.
* Move reusable code into package modules such as `sunlight/corpus/` or
  `corpora/`.
* Add a manifest importer and queue runner before adding more corpus-specific
  scripts.
* Keep `vllm/` as the lab until the extraction contract stabilizes, then promote
  the shared schema/request/validation code into the corpus package.
* Move dataset publication concerns into `apps/opendata` plus a build-time
  dataset registry, search/chat routes, and per-dataset bot configuration.
* Keep operational OIA/LGOIMA workflow code in `apps/admin`,
  `apps/authority`, `apps/inbound-email`, and D1/R2 operational migrations.

## Immediate Design Decisions

1. Define a corpus manifest schema and R2/S3 queue contract before adding
   Disputes Tribunal.
2. Decide whether Vectorize is one global corpus index with `corpus` metadata
   filters or one index per public corpus.
3. Decide how Sunlight exports approved response artifacts into the OpenData
   manifest format.
4. Rename FYI-specific bindings and scripts only after the corpus manifest
   contract exists.
5. Stop writing future LLM generated fields into canonical markdown
   frontmatter; write sidecars and generated retrieval views instead.
6. Promote the vLLM strict JSON extraction path into the canonical tribunal
   extraction stage after the next accuracy/eval pass.
7. Build the first `apps/opendata` dataset registry, search page, and chatbot
   route from generated manifests, not hard-coded marketing copy.
8. Add a Disputes adapter only after Tenancy is represented as a generic
   tribunal adapter.
