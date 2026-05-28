# Inventory: Ingestion, LLM, Embeddings, and RAG

This inventory catalogs the current repo paths that collect documents, convert
documents, call LLMs, calculate embeddings, build retrieval indexes, publish
datasets, or evaluate those systems.

The main architectural boundary is:

* `sunlight.nz` should be the OIA/LGOIMA request engine and first-party
  disclosure workflow.
* `apps/opendata` should be the dataset publication surface for public corpora
  such as FYI, Tenancy Tribunal, Disputes Tribunal, and later Sunlight
  disclosure datasets.
* Corpus processing should be shared infrastructure, not a one-off pile of
  FYI-, Tenancy-, or vLLM-specific scripts.

## Product Boundary

| Area | Current files | Current role | Production boundary |
| --- | --- | --- | --- |
| Sunlight operational engine | `apps/admin`, `apps/authority`, `apps/inbound-email`, `cloudflare/migrations` | Create OIA/LGOIMA requests, collect responses, store uploads, review workflow | Keep here. This is the OIA/LGOIMA engine. |
| Sunlight public site/search | `apps/landing` | Landing page plus `/search` and `/api/search` over the current public FYI-style index | Search may remain for Sunlight disclosures, but broad public corpora should move behind OpenData. |
| OpenData publication site | `apps/opendata`, `docs/OPENDATA.md` | Static public-interest data site; no dataset registry or pipeline yet | Should own dataset pages, download manifests, provenance, and corpus-specific public search. |
| Corpus processing scripts | `scripts/*`, `vllm/*` | Mixed production-ish pipelines, probes, evals, and experiments | Promote stable code into shared corpus pipeline modules with thin CLI entrypoints. |
| Local/vector stores | `storage/**`, `fyi/**`, `justice/**`, `vllm/results/**` | Local source data, converted markdown, LanceDB stores, eval/extraction outputs | Treat as build artifacts and source snapshots, not application code or canonical product boundaries. |

## Corpus State

| Corpus | Current state | Main source paths | Main processing paths | Gaps |
| --- | --- | --- | --- | --- |
| Sunlight OIA/LGOIMA responses | Operational request/response intake exists. No production corpus conversion/indexing path found. | R2 `sunlight-request-artifacts`, D1 `sunlight-requests` | `apps/admin`, `apps/authority`, `apps/inbound-email` | Need approval-to-publication pipeline: response artifacts to canonical markdown, metadata, chunks, embeddings, dataset rows, and search indexes. |
| FYI OIA/LGOIMA archive | Most mature RAG corpus. Docling conversion, local LanceDB vectors, Vectorize export, D1 BM25, Hugging Face dataset export exist. | `fyi/data/request`, `fyi/markdown` | `scripts/parallel_convert_and_embed.py`, `scripts/export_to_vectorize.py`, `scripts/upload_to_vectorize.py`, `scripts/export_bm25_to_d1.py`, `scripts/export_hf_markdown_dataset.py` | Names and bindings are FYI-specific and currently leak into generic search. |
| Tenancy Tribunal | Production-ish Docling and embedding path exists. Structured vLLM extraction path exists and looks promising. Historical LLM enrichment path is riskier. | `justice/data/tenancy/**`, `storage/justice/tenancy/markdown_docling` | `scripts/ingest_tenancy.py`, `scripts/tenancy_corpus.py`, `scripts/tenancy_llm.py`, `vllm/tribunal_process_docling.py` | Need source/extraction separation, corpus-neutral indexing, OpenData dataset publication, and better eval gates before publishing. |
| Disputes Tribunal | No first-class ingestion adapter found. Repo searches for `disputes`/`Disputes Tribunal` only found planning-level references. | None found | None found | Needs a new tribunal adapter that reuses the Tenancy/vLLM pipeline contract instead of copying Tenancy scripts. |
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
* There is no completed path that turns approved Sunlight response artifacts
  into public corpus records, markdown, embeddings, Vectorize rows, D1 BM25
  rows, or OpenData datasets.

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

1. Input PDFs under `fyi/data/request`.
2. Docling conversion writes markdown under `fyi/markdown` with provenance
   frontmatter.
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

1. Source PDFs and sidecars are discovered from `justice/data/tenancy/pdfs` and
   `justice/data/tenancy/legacy/pdf`.
2. Docling conversion writes canonical markdown into
   `storage/justice/tenancy/markdown_docling`.
3. Optional LLM enrichment writes generated frontmatter fields such as
   `case_summary`, `questions_answered`, `neutral_fact_pattern`,
   `claims_made`, and `legal_principles`.
4. Markdown and generated retrieval views are chunked with FYI-derived helpers.
5. Local Qwen embeddings are written to LanceDB at
   `storage/justice/tenancy/lancedb`, table `chunks_v2`.

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
| R2 public corpus bucket | `docs/VECTORS.md` | Planned canonical PDFs, markdown, chunks, manifests | Durable public corpus object store | Planned as `sunlight-corpus`; not the same as operational `sunlight-request-artifacts`. |
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
| Planned `sunlight-corpus` R2 | Canonical public PDFs, markdown, chunks, manifests | Public corpus object store for dataset/search publication |
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
6. OpenData is currently a website, not a dataset publication app.
7. Sunlight public search currently behaves like a broad public corpus search,
   while the product boundary should reserve Sunlight for OIA/LGOIMA operations
   and first-party disclosures.
8. There is no Disputes Tribunal adapter.
9. Token budgets, model IDs, provider choices, response parsing, and retry
   policies are duplicated across paths.
10. Evaluation exists, but each area has its own harness and artifact shape.

## Recommended Production Shape

Create a shared corpus pipeline with stable stage contracts and corpus adapters.
The immediate goal is not a huge framework; it is to stop copying pipeline
logic across FYI, Tenancy, Disputes, and Sunlight disclosures.

Suggested stages:

1. `discover`: enumerate source documents and immutable source metadata.
2. `convert`: create canonical markdown from source PDFs or uploaded files.
3. `normalize`: produce deterministic corpus metadata and public R2 keys.
4. `extract`: run structured LLM extraction into sidecar JSONL/Parquet.
5. `enrich`: optionally produce generated retrieval views as separate artifacts.
6. `chunk`: produce deterministic chunks with chunk schema versioning.
7. `embed`: calculate vectors and write a local corpus-neutral vector store.
8. `index`: export to Vectorize, D1 BM25, AI Search, or other retrieval stores.
9. `publish`: write OpenData dataset manifests, cards, downloads, and pages.
10. `eval`: run schema, extraction, retrieval, privacy, and publication gates.

Suggested adapters:

| Adapter | Source | Initial implementation |
| --- | --- | --- |
| `fyi_oia` | FYI public OIA/LGOIMA archive | Wrap current FYI Docling, LanceDB, Vectorize, BM25, and HF export paths |
| `sunlight_disclosures` | Approved Sunlight response artifacts | New adapter from D1/R2 operational records into public corpus artifacts |
| `justice_tenancy` | Tenancy Tribunal decisions | Wrap current Tenancy Docling source adapter and vLLM extraction output |
| `justice_disputes` | Disputes Tribunal decisions | New adapter modeled on tribunal interface, not copied from Tenancy |

Suggested code organization:

* Keep CLI entrypoints in `scripts/` for now.
* Move reusable code into package modules such as `sunlight/corpus/` or
  `corpora/`.
* Keep `vllm/` as the lab until the extraction contract stabilizes, then promote
  the shared schema/request/validation code into the corpus package.
* Move dataset publication concerns into `apps/opendata` plus a build-time
  dataset registry.
* Keep operational OIA/LGOIMA workflow code in `apps/admin`,
  `apps/authority`, `apps/inbound-email`, and D1/R2 operational migrations.

## Immediate Design Decisions

1. Define a corpus manifest schema before adding Disputes Tribunal.
2. Decide whether Vectorize is one global corpus index with `corpus` metadata
   filters or one index per public corpus.
3. Rename FYI-specific bindings and scripts only after the corpus manifest
   contract exists.
4. Stop writing future LLM generated fields into canonical markdown
   frontmatter; write sidecars and generated retrieval views instead.
5. Promote the vLLM strict JSON extraction path into the canonical tribunal
   extraction stage after the next accuracy/eval pass.
6. Build the first `apps/opendata` dataset registry page from generated
   manifests, not hard-coded marketing copy.
7. Add a Disputes adapter only after Tenancy is represented as a generic
   tribunal adapter.
