# Progress

## Current Slice

The public `sunlight.nz/search` path now has a custom hybrid retriever: semantic
Vectorize candidates plus D1 FTS5 BM25 candidates, fused with reciprocal rank
fusion and source-diverse citation selection. The current search slice is to
compare bounded agentic retrieval orchestration against that deterministic
hybrid baseline before changing production.

Completed:

* Defined admin, authority response, landing, and implementation planning docs.
* Configured shared pre-commit hooks for McCabe complexity and max source file
  length.
* Created Cloudflare D1 database `sunlight-requests`.
* Created Cloudflare R2 bucket `sunlight-request-artifacts`.
* Added `wrangler.jsonc` with D1 and R2 bindings.
* Added and applied the initial D1 migration locally and remotely.
* Seeded bootstrap admin `sunlight@spunts.net` as `maintainer`.
* Verified remote D1 tables and bootstrap admin row.
* Added pnpm workspace structure.
* Scaffolded Vinext apps:
  * `apps/admin`
  * `apps/authority`
  * `apps/landing`
* Added Wrangler config for each app.
* Added initial admin D1-backed summary page.
* Added authority response token route skeleton.
* Added Cloudflare Access JWT validation helper for admin.
* Added FYI authority import command.
* Imported 3,177 FYI authority records into remote D1.
* Added admin authority list/detail screens.
* Added authority contact verification action.
* Added request template creation screens.
* Added request cycle creation/detail screens.
* Added `SunlightRequest` preparation from verified authorities.
* Added cycle approval.
* Added Cloudflare Email Sending binding for admin.
* Added outbound email rendering, queueing, sending, status updates, and audit
  events.
* Added cycle send preview with request status counts.
* Added outbound send results and failed-email retry controls.
* Added overdue SunlightRequest summary and admin `/requests` list.
* Added authority response metadata submission.
* Added direct-to-R2 presigned upload session and completion routes.
* Configured R2 CORS for browser uploads from `requests.sunlight.nz`.
* Created R2 S3 credentials for authority uploads and stored them in `.env`.
* Added the R2 S3 credentials as authority Worker secrets.
* Deployed the authority Worker and verified a disposable live upload end to end.
* Validated all three Vinext apps for Workers + Static Assets dry-run
  deployment.
* Added `docs/WEB.md` with the public landing page design brief and prompt for
  Stitch and Claude Design.
* Enabled Cloudflare Zero Trust Access for the Sunlight account.
* Created the `admin.sunlight.nz` self-hosted Access application.
* Added an Access allow policy for bootstrap admin `sunlight@spunts.net`.
* Stored `CF_ACCESS_AUD`, `CF_ACCESS_ISSUER`, and `CF_ACCESS_JWKS_URL` as admin
  Worker secrets.
* Deployed the admin Worker to the Access-protected custom domain.
* Added Cloudflare Access One-time PIN login as the Zero Trust identity
  provider.
* Verified the `admin.sunlight.nz` Access login page renders the email code
  form.
* Changed the admin Access application session cookie SameSite setting from
  `strict` to `lax` to avoid post-login redirect loops from the
  `cloudflareaccess.com` auth domain back to `admin.sunlight.nz`.
* Added shadcn/Tailwind v4 plumbing for the admin Vinext app.
* Converted the admin dashboard overview to local shadcn-style `Button`, `Card`,
  and `Badge` components.
* Added paginated authority listing queries and count metadata.
* Added immediate browser-side filtering-as-you-type for the admin authorities page
  using both `onKeyUp` and `onChange` input paths.
* Added authority pagination controls and page-size selection.
* Replaced prohibited proxied apex DNS records that pointed at Cloudflare edge
  IPs with the landing Worker custom-domain DNS record.
* Deployed the Stitch-inspired landing app to `sunlight.nz` and
  `www.sunlight.nz`.
* Moved `sunlight.webp` into the landing app public assets and used it as the
  hero image.
* Added `curl_cffi` and `beautifulsoup4` for the authority contact scraper.
* Added D1 migration `0002_agency_contact_candidates.sql` for scraped contact
  candidates.
* Added tested Python helpers for email normalization, extraction, candidate
  link selection, scoring, and SQL generation.
* Added `scripts/scrape_authority_contacts.py` with conservative dry-run,
  `--write-sql`, `--source-file`, and remote D1 apply support.
* Deployed the updated landing app to `sunlight.nz` and `www.sunlight.nz`.
* Applied contact-candidate migration `0002_agency_contact_candidates.sql`
  locally and remotely.
* Added Brave Search seeding for official same-site contact discovery using
  `BRAVE_SEARCH_API_KEY`, one search request per authority.
* Reworked scraper discovery to prefer Brave-seeded official pages, then expand
  only high-value same-site contact/OIA/privacy/request links.
* Added progress logging and slow-fetch warnings so stuck crawlers can be
  identified by authority and URL.
* Tested scraper output against known authorities using `--write-sql`; strong
  candidates were found for Auckland Council, Ministry of Justice, and
  Wellington City Council.
* Renamed the core domain terminology, admin routes, response app workspace,
  scripts, docs, and tests to use authority and authorities language.
* Restored applied migration filenames/content as immutable history and added
  `0003_rename_agencies_to_authorities.sql` to migrate deployed D1 tables and
  columns from agency naming to authority naming.
* Applied `0003_rename_agencies_to_authorities.sql` locally and remotely.
* Added grouped admin review for scraped contact candidates on authority detail
  pages, with actions to accept primary contacts, accept secondary contacts,
  reject candidates, and mark an authority contact invalid.
* Added audit events for primary accept, secondary accept, reject, invalid
  contact decisions, and a scraper quality rejection.
* Deployed the updated admin Worker to `admin.sunlight.nz`.
* Tightened scraper scoring so external-domain addresses found on an authority
  page are penalized unless they use a strong official-information local part.
* Added `--offset` to the scraper so remote scraping can progress through all
  authorities in controlled batches instead of repeatedly scanning the first
  missing rows.
* Ran two conservative remote scrape batches without Brave Search credentials:
  `--limit 20` and `--limit 30 --offset 20`.
* Rejected the known bad ACC candidate `info@ombudsman.parliament.nz` after the
  scoring fix.
* Split scraper SQL generation into `scripts/contact_scrape_sql.py`.
* Added automatic verification for clear best candidates:
  * one usable candidate at confidence 50+
  * any candidate at confidence 80+
  * a confidence 65+ candidate that beats the next candidate by at least 15
    points
* Added D1 migration `0004_authority_contact_scrape_attempts.sql` so no-result
  authorities are recorded once and skipped by later normal batches.
* Applied `0004_authority_contact_scrape_attempts.sql` locally and remotely.
* Added scraper `--retry-attempted` for explicit re-crawls.
* Added authority-level parallel scraping with `--workers` and a
  `--brave-concurrency` semaphore for Brave Search API calls.
* Re-ran sampled authorities with auto-verification enabled.
* Ran two attempt-ledger remote batches of 100 authorities each.
* Completed the normal first-attempt pass for active authorities using parallel
  24-32 worker batches.
* Added a tested contact seed helper so the scraper probes common contact and
  OIA paths before noisy homepage-discovered links.
* Added FYI source-page fallback for authorities with missing or weak homepage
  metadata, while avoiding FYI internal help/login pages from consuming the page
  budget.
* Expanded scoring for high-quality school and authority role mailboxes such as
  `office@`, `principal@`, `reception@`, and `secretary@` when found on an
  official contact page.
* Confirmed in dry runs that the improved crawler can now auto-verify examples
  missed by the first pass, including Public Service Commission and school
  office-address cases.
* Applied the improved scraper to remote D1 in controlled batches.
* Added the next automated fallback for the remaining high-volume school cases
  to accept same-domain role mailboxes found on official pages.
* Re-ran the scraper on the remote D1, successfully auto-verifying over 300
  additional authorities using the new fallback.
* Wired admin pages/actions through the existing Cloudflare Access JWT validator
  so D1 admin roles are enforced inside the app as well as at the edge.
* Implemented Cloudflare Email Catch-all routing to `sunlight-inbound-email` worker.
* Upgraded inbound email worker AI triage to correctly parse OpenAI-compatible JSON responses from modern models like Kimi K2.6.
* Updated inbound email worker to associate emails using the `In-Reply-To` header against generated outbound `Message-ID`s.
* Fixed D1 `undefined` binding crashes and null constraints in email tables.
* Updated request templates to separate OIA and LGOIMA specific templates.
* Rebranded "Open Data Limited" to "Sunlight Project" across the website and templates.
* Created a robust PDF-to-Markdown-to-Vector ingestion pipeline using Docling, Qwen3-Embedding-0.6B (CUDA 13.0 fp16), and LlamaIndex.
* Parallelized the ingestion pipeline using `concurrent.futures` to maximize GB10 Grace Blackwell CPU/GPU usage.
* Reworked FYI PDF ingestion to use three recycled Docling conversion workers feeding a bounded Markdown queue consumed by one embedding worker, avoiding an all-convert-then-embed memory spike.
* Created a watchdog script (`scripts/watchdog.sh`) with `.failed` lockfiles to automatically skip corrupt PDFs causing SegFaults and seamlessly restart the pipeline.
* Wrote `scripts/export_to_vectorize.py` to seamlessly convert local LlamaIndex vectors to Cloudflare Vectorize NDJSON format.
* Documented the revised vector storage plan in `docs/VECTORS.md`, now using a dual-pipeline eval: Docling plus LanceDB plus Vectorize for the controlled main path, and R2 markdown plus Cloudflare AI Search for the managed path.
* Replaced the FYI ingestion LlamaIndex JSON persistence with a streaming LanceDB writer that upserts chunk rows by `chunk_id`, keeping the single embedding worker and bounded queue architecture intact.
* Added deterministic markdown filenames with path hashes so duplicate FYI attachment names no longer overwrite each other or share `.failed`/`.embedded` markers.
* Added provenance front matter to converted FYI markdown files so each document carries its FYI request URL, source PDF URL, stable document id, and planned R2 keys into downstream retrieval.
* Replaced the old LlamaIndex export script with a streaming LanceDB-to-Vectorize NDJSON exporter using `pylance`, so the final Vectorize handoff no longer has to load the whole table into memory.
* Smoke-tested the LanceDB pipeline against real FYI PDFs, then fixed the missing direct HuggingFace embedding dependency and a LanceDB table-list compatibility bug in the Vectorize exporter that the test exposed.
* Started the full FYI corpus run in a PTY and confirmed LanceDB streaming flushes work, then stopped it after the embedding worker retained an 86 GiB unified-memory allocation on a long batch.
* Bounded embedding memory by switching to fixed-size sentence chunks, setting an explicit small HuggingFace embedding batch size, and clearing CUDA cache after each persisted embedding flush.
* Added the public `/search` page to the `sunlight.nz` landing app.
* Added `/api/search` to the landing Worker, using Workers AI for query
  embeddings and answer generation against the populated `fyi-v2` Vectorize
  index.
* Added test coverage for landing search input validation, Workers AI embedding
  parsing, Vectorize metadata normalization, prompt construction, and answer
  extraction.
* Bound the landing Worker to Workers AI and `fyi-v2`, with remote bindings
  enabled for local `wrangler dev` checks.
* Deployed the search-enabled landing Worker to `sunlight.nz` and verified the
  live `/search` page plus `/api/search` answer path.
* Added a BGE reranking pass to landing search:
  * query Vectorize for 20 candidates
  * rerank the candidate snippets with `@cf/baai/bge-reranker-base`
  * answer from the top 5 reranked citations
  * preserve both rerank and Vectorize scores in API citations
* Added `docs/SEARCH.md` with the current search path, BM25/D1 hybrid plan,
  AI Search alternative, LlamaIndex decision, and AI SDK/Gateway migration notes.
* Deployed the reranker-enabled landing Worker to `sunlight.nz`.
* Created the separate D1 search database `sunlight-search` for public retrieval
  sidecar tables.
* Added landing Worker `SEARCH_DB` binding and search migrations directory.
* Added `cloudflare/search-migrations/0001_disclosed_chunks_fts.sql` with
  `disclosed_chunks`, `disclosed_chunks_fts`, and synchronization triggers.
* Applied the BM25 sidecar migration to remote D1.
* Added `scripts/export_bm25_to_d1.py` to build and apply D1 import shards from
  FYI markdown using the same chunking defaults as the Vectorize pipeline.
* Imported 160,479 FYI chunks into `sunlight-search`; the remote database is
  about 774 MB after import.
* Added D1 BM25 retrieval to `/api/search`, querying top 50 lexical candidates
  and falling back to Vectorize-only retrieval if BM25 fails.
* Changed `/api/search` to retrieve Vectorize top 50 and BM25 top 50, fuse by
  weighted reciprocal rank fusion, rerank the top 20 fused candidates with
  `@cf/baai/bge-reranker-base`, then answer from the final top 5 by default.
* Preserved `vectorScore`, `vectorRank`, `bm25Score`, `bm25Rank`, and
  `fusedScore` in API citations for debugging and later retrieval evals.
* Added TypeScript coverage for FTS query sanitization, BM25 row mapping, hybrid
  fusion, and reranking score preservation.
* Updated `docs/SEARCH.md` with the implemented BM25 sidecar, importer commands,
  hybrid fusion behavior, AI Search comparison plan, and eval plan.
* Added request-size, content-type, malformed JSON, and D1-backed per-client
  rate-limit protections to the public search API.
* Added search migration `0002_search_rate_limits.sql` and applied it to remote
  `sunlight-search`.
* Added TypeScript coverage for search request validation and rate-limit bucket
  construction.
* Added `scripts/generate_eval_questions.py` to create local LLM-generated FYI
  search eval candidates from markdown excerpts and request metadata.
* Generated the initial `manifests/fyi/v1/eval-questions.ndjson` seed set with
  20 unreviewed questions using local vLLM model `nvidia/Gemma-4-31B-IT-NVFP4`.
* Added `scripts/eval_search.py` to run local retrieval evals against the
  existing LanceDB backup at
  `/mnt/dgx-ssd/src/sunlight_backup/storage/fyi_parallel.lancedb`, loading
  `Qwen/Qwen3-Embedding-0.6B` for query embeddings and
  `BAAI/bge-reranker-base` for reranking inside the eval process.
* Ran the 20-question local LanceDB eval and wrote ignored outputs to
  `storage/evals/search/local-lancedb-20`; the initial result was vector
  recall@50 `1.000`, vector MRR@50 `0.952`, final reranked recall@5 `0.850`,
  and final reranked MRR@5 `0.779`.
* Enhanced `scripts/eval_search.py` reports with per-question-kind and
  answerability metric breakdowns, plus stage-regression callouts for questions
  where first-stage retrieval found the expected document but final selection
  lost it.
* Reviewed and hand-corrected all 20 rows in
  `manifests/fyi/v1/eval-questions.ndjson`, tightening ambiguous question
  wording and verifying every supporting passage resolves to the referenced
  local FYI markdown document.
* Added local SQLite FTS5 BM25 support to `scripts/eval_search.py` via
  `scripts/eval_search_bm25.py`, so the local harness now reports vector-only,
  BM25-only, hybrid RRF, and reranked hybrid retrieval metrics.
* Added reviewed production-failure eval rows for the live Auckland Council
  leisure-centre/contracted-operator search miss, and made the eval report list
  expected documents that are absent from the current local LanceDB snapshot.
* Improved search eval reporting so retrieval metrics are calculated over
  covered expected documents separately from corpus coverage gaps, with
  Vector/BM25/hybrid recall and MRR shown at 5, 10, 20, and the configured
  top-k cutoff.
* Added local eval controls for Vector/BM25 reciprocal-rank-fusion weights so
  search experiments can compare first-stage retrieval tradeoffs without
  editing code between runs.
* Ran local search eval baselines for hybrid reranking, vector-only reranking,
  fused-order final selection, and Vector/BM25 fusion-weight sweeps; fused order
  beat the BGE reranked path on the reviewed set.
* Changed the landing search API to use fused Vectorize + BM25 order directly
  for answer citations while leaving the BGE reranker as an offline experiment.
* Updated final search citation selection to reserve top Vectorize and BM25
  hits, de-duplicate by document, and then fill from fused order, because live
  smoke tests showed BM25-only evidence could otherwise remain below the answer
  context even when D1 found strong lexical hits.
* Hydrated BM25 citation snippets from capped D1 `chunk_text` instead of the
  shorter `text_preview`, improving answer context for exact-term hits whose
  supporting details appear later in the chunk.
* Added `scripts/export_hf_markdown_dataset.py` to package FYI markdown as a
  Hugging Face-ready Parquet dataset folder with Markdown content, frontmatter,
  FYI request metadata, a dataset card, export manifest, record index, and
  optional upload support.
* Added full snapshot mode for replacing the current Hugging Face dataset and
  append-safe delta mode for adding new content-addressed records over time.
* Deleted 2,039 duplicate legacy markdown files that predated provenance
  frontmatter after confirming each had a deterministic `__<hash>.md`
  replacement.
* Updated the Hugging Face exporter to skip frontmatterless markdown files so
  dataset rows always carry provenance metadata.
* Built the current local full dataset at
  `storage/huggingface/sunlight-fyi-markdown`: 9,665 rows, 10 Parquet shards,
  and about 54 MB.
* Added `docs/DATASET.md` with the Hugging Face dataset plan, schema, source of
  truth, full and delta publishing workflows, living dataset update loop,
  validation gates, responsible-use notes, and open release decisions.
* Inspected the local Tenancy Tribunal scrape and added `docs/TRIBUNAL.md` with
  the first-class Docling, embedding, Vectorize, D1 BM25, metadata enrichment,
  UI, and eval plan for tribunal decisions.
* Added tested Tenancy ingestion modules:
  * `scripts/tenancy_corpus.py` for source discovery, sidecar metadata,
    deterministic enrichment, and generated retrieval views.
  * `scripts/ingest_tenancy.py` for Docling conversion, optional LLM metadata
    enrichment, and Qwen/LanceDB embedding.
* Extended the LanceDB writer, Vectorize exporter, BM25 exporter, and chunk
  record builder to preserve source-aware tribunal metadata and generated
  retrieval-view fields.
* Removed the scratch MarkItDown Tenancy production path; Docling is now the
  canonical Tenancy converter.
* Ran the full local Tenancy import:
  * 32,378 unique Tenancy Tribunal PDFs discovered after deduping by `pdf_url`.
  * 32,378 Docling markdown files written under
    `storage/justice/tenancy/markdown_docling`.
  * 32,378 embedding markers written.
  * 412,537 chunk rows written to
    `storage/justice/tenancy/lancedb/chunks_v2`.
* Verified GPU usage during the import: Docling/RapidOCR selected GPU 0 for
  OCR/model stages, and Qwen embedding ran on CUDA with
  `CUDA_VISIBLE_DEVICES=0`.
* Verified Tenancy ingestion idempotency: a rerun skipped all 32,378 converted
  markdown files, and the embedding pass found zero pending files.
* Left full-corpus LLM enrichment as a separate resumable batch.
* Updated Tenancy LLM enrichment to target the local-network vLLM host at
  `http://192.168.88.96:8000/v1`, using served model
  `Qwen/Qwen3.6-27B-FP8` with the `Qwen/Qwen3.6-27B` tokenizer for prompt
  accounting.
* Added Qwen-token-budgeted LLM batching, JSON response mode, disabled Qwen
  thinking via vLLM chat-template kwargs, and configurable concurrency. Defaults
  now target a 14,336-token prompt budget and concurrency 2, with concurrency 4
  planned as the first throughput benchmark.
* Sampled 1,000 existing Tenancy markdown files with the Qwen tokenizer at the
  current 5,000-character excerpt cap: the 14,336-token prompt budget produced
  137 requests, mean 7.3 decisions per request, median 7, and maximum 8.
* Smoke-tested remote Qwen enrichment on two temporary Tenancy markdown copies;
  both enriched successfully with summaries, catchwords, and questions.
* Ran a sustained remote Qwen enrichment test on 1,000 temporary Tenancy
  markdown copies using `--llm-concurrency 2`: 999 pending files enriched, 0
  failures, 136 LLM requests, 47.57 minutes elapsed, about 21.0 documents/minute
  and 2.86 requests/minute. One copied markdown file already had the current
  enrichment marker before the run, so it was skipped.
* Analyzed the legacy Tenancy scrape in `justice/data/tenancy/legacy/pdf`:
  11,476 PDFs, exact signature dates for 11,411, 65 fallback dates, and no gap
  before the current scrape because legacy runs through 2023-07-07 while the
  current continuous 2023 scrape begins on 2023-05-20.
* Added opt-in legacy Tenancy ingestion support that normalizes legacy PDF
  filenames to `doc_justice_tenancy_legacy_<order_id>` documents and uses
  Docling output, not the old text sidecars, for deterministic date metadata.
* Deleted 11,478 old legacy Tenancy `.txt*` extraction files after recording
  date coverage; 11,476 legacy PDFs remain for Docling conversion.
* Smoke-tested one legacy PDF through Docling after deleting the text sidecars;
  RapidOCR selected GPU 0 and the generated frontmatter included
  `decision_date`, `nztt_citation`, `request_year`, and R2 keys.
* Added a Cloudflare-vs-Docling markdown conversion comparison utility and a
  temporary Worker AI binding proxy. Direct Cloudflare REST calls returned
  `403`, but the Worker binding converted sample PDFs successfully.
* Compared Cloudflare Workers AI Markdown Conversion against Docling on one
  legacy and one current Tenancy PDF. Cloudflare was much faster on the sample
  but flattened tables and joined decision-date text, so Docling remains the
  canonical Tenancy converter for now.
* Counted Tenancy markdown tokens with the `gpt-4o` tokenizer across 32,380
  existing Docling markdown files: 106,670,461 full-document tokens total,
  84,331,062 body-only tokens total, and 42,336,807 tokens when capped to the
  first 5,000 body characters for enrichment-style prompts.
* Benchmarked the legacy Tenancy Docling ingestion path on an isolated 24-PDF
  sample: Docling conversion finished in 18.33 seconds, conversion plus
  embedding finished in 54.53 seconds, and the remaining 11,474 legacy PDFs are
  estimated at about 2.5 hours for conversion alone or roughly 6-8 hours
  end-to-end with `--skip-llm`.
* Confirmed the resumed legacy run has not completed yet: 2 legacy markdown
  files currently exist, 0 legacy embedding markers exist, and 11,474 legacy
  PDFs remain to convert and embed. A PTY run was stopped during the skip phase
  before it reached legacy conversion.
* Added `docs/AGENTIC_RAG.md` and an offline `scripts/eval_search.py --agentic`
  mode that analyzes query intent, records a retrieval plan, inspects first-pass
  evidence, and runs a bounded expansion pass only when exact or numeric
  evidence appears weak.
* Added streamed search progress events to `/api/search` and updated the public
  search UI to show each stage as it runs: BM25 keyword search, query embedding,
  Vectorize search, hybrid fusion, citation selection, and answer generation.
* Tightened the public search page layout so the heading, input, examples, and
  compact progress grid fit much higher on a standard laptop viewport.
* Replaced the hard-coded search example chips with a random three-question
  rotation drawn from the reviewed FYI eval questions on each page load.
* Completed legacy Tenancy Docling conversion for all 11,476 legacy PDFs:
  `storage/justice/tenancy/markdown_docling` now contains 11,476
  `doc_justice_tenancy_legacy_*.md` files, and the resumed conversion reported
  10,321 converted, 33,533 skipped, and 0 failed for the combined current plus
  legacy corpus.
* Fixed Tenancy LLM batch preparation after the full run exposed a silent
  O(n²)-style tokenization delay before the first LLM request. The batch builder
  now tokenizes documents incrementally, loads the Qwen tokenizer local-first,
  prints batch-build progress every 1,000 files, and still records exact final
  prompt-token counts with a split safeguard for over-budget batches.
* Verified the local-network Qwen/vLLM endpoint at `192.168.88.96:8000` is
  currently unreachable from this machine; the full enrichment run was stopped
  after six connection-error batches and before any successful LLM progress was
  logged.
* Checked the local `localhost:8080` OpenAI-compatible gateway. The NVIDIA
  chat-completions routes are reachable but did not produce usable enrichment
  JSON with `json_object` mode for real Tenancy decisions. Added
  `--llm-api-mode responses` so the ingestion path can use Responses API
  structured parsing; a real one-document smoke with the regular NVIDIA route
  enriched successfully. However, a 4-document Responses batch took about 158
  seconds, making full-corpus enrichment multi-day at current throughput.
  A direct Groq regular route followed the schema quickly, but its 8k TPM limit makes
  it unsuitable for useful full-corpus batching.
* Copied the load-balanced Bifrost gateway setup from
  `/home/dev/src/bifrost/config.json` into `bifrost/` with a repo-local Docker
  Compose wrapper, ignored local `.env`, debug JSON logging, and
  environment-referenced provider plus virtual keys. Fixed the copied routing
  rules for the current Bifrost runtime by replacing invalid `request.model`
  CEL with `provider`/`model`, adding explicit `global` scope, setting
  provider-specific target model aliases, and changing fallback entries to
  `provider/model` form. Verified the debug gateway boots on `localhost:8081`
  and that `nvidia/regular` now logs matched routing decisions for both NVIDIA
  and OpenRouter weighted targets.
* Cleaned the repo-local Bifrost model aliases to exactly `fast`, `regular`,
  and `reasoning` for each provider. Removed the task-specific Tenancy alias,
  provider-suffixed aliases, raw model IDs, and wildcard virtual-key model
  permissions from the committed config. Updated Tenancy ingestion defaults to
  call `model=nvidia/regular`, which keeps Bifrost's normal provider-prefix
  behavior while routing through the currently usable high-context providers:
  NVIDIA `regular` and OpenRouter `regular`.
* Added Tenancy LLM request-start logging with a rolling 60-second RPM window so
  sustained enrichment runs can be monitored directly from the log. Each request
  start now reports the active `rpm_window`, batch file count, document count,
  and prompt-token estimate before the provider call begins.
* Added the Tenancy LLM enrichment path for direct NVIDIA NIM calls to
  `deepseek-ai/deepseek-v4-pro` through Instructor `from_openai()`. The current
  defaults use one decision per request, `json_schema` Instructor mode, 40 RPM,
  concurrency 20, and 3-15 seconds of random startup jitter so parallel workers
  do not burst the provider at launch. `json_mode` and `md_json` remain
  available as explicit fallback modes.
* Stopped the first direct NVIDIA Instructor run after early 429s showed that
  Instructor's internal retries were bypassing the outer RPM limiter. Fixed the
  retry path so Instructor performs one provider attempt per outer attempt, and
  every outer retry now passes through the shared `RequestRateLimiter` before
  another provider call is made.
* After the host reboot, restarted Tenancy LLM enrichment attempts from the
  unchanged 43,831-file pending set. Direct NVIDIA still returned only 429s at
  40 RPM/concurrency 20, then at 20 RPM/concurrency 4, and finally in a
  5-document canary at 5 RPM/concurrency 1. No successful enrichment progress
  was logged, and no partial enrichment markers were written.
* Inspected the direct NVIDIA 429 response for `deepseek-ai/deepseek-v4-pro`.
  The HTTP body contains only `{"status":429,"title":"Too Many Requests"}` and
  no explanatory `message`, `detail`, `Retry-After`, or rate-limit headers were
  present. Tiny same-key requests to NVIDIA Nemotron models succeeded, so the
  current blocker appears specific to DeepSeek model availability or
  model-specific throttling rather than a key-wide NVIDIA outage.
* Switched Tenancy LLM enrichment defaults to MiniMax's OpenAI-compatible API at
  `https://api.minimax.io/v1` with model `MiniMax-M2.7-highspeed`, loading
  `MINIMAX_API_KEY` from the repo-root `.env`. The model id is now explicit in
  code and is not hidden behind a `TENANCY_LLM_MODEL` environment override.
* Verified MiniMax structured extraction with Instructor. `json_schema`,
  `json_mode`, and `md_json` work when `reasoning_split` is enabled; MiniMax
  otherwise includes `<think>` content in `message.content`, which breaks JSON
  parsing. A 5-document temp-copy canary enriched 5/5 with no failures after the
  single-document Instructor path was changed to request one enrichment object
  and wrap it internally.
* Updated the MiniMax request budget to match the actual limit of 4,500 model
  requests per 5 hours. The default is 12 RPM, which consumes 3,600 requests per
  5-hour window and leaves 900 requests of retry/probe headroom.
* Probed NVIDIA `minimaxai/minimax-m2.7` with real Tenancy enrichment prompts
  and actual markdown excerpts. A one-document request through chat completions
  with `response_format={"type":"json_object"}` returned valid parseable JSON,
  but took about 53 seconds end to end.
* Tested scheduled-start NVIDIA `minimaxai/minimax-m2.7` real-data request
  rates. A 40 RPM probe hit HTTP 429 after the first several starts, with body
  `{"status":429,"title":"Too Many Requests"}`. A cooled-down 15 RPM probe
  against 15 real documents returned 11 valid parsed enrichments and 4 HTTP
  429s; successful request latency ranged from 26.14 to 63.47 seconds, with
  36.54 seconds median. NVIDIA is therefore not safe to mix into the production
  Tenancy enrichment run at 15+ scheduled RPM without a lower rate and/or
  explicit in-flight cap.
* Skipped NVIDIA for the production Tenancy enrichment path and restarted the
  resumable direct MiniMax run in tmux session `tenancy-llm-minimax-direct`.
  The command uses `https://api.minimax.io/v1`, model `MiniMax-M2.7-highspeed`,
  `--llm-rpm 15`, and logs to
  `logs/tenancy-llm-minimax-direct-rpm15-20260525-232159.log`. The run found
  43,759 pending files and the first monitored minute reached
  `rpm_window=15/15` with 19 enrichments and 0 failures.
* The direct MiniMax run was manually stopped after 8,874 request starts and
  8,846 logged completions. Its final logged counters were 8,845 enriched and 1
  failed/missing-output item, with 28 requests started but not logged complete
  before the kill. The corpus now has 8,940 enriched markdown files and 34,914
  pending.
* Added `scripts/probe_nvidia_tenancy_models.py` to run reproducible real
  Tenancy enrichment probes against NVIDIA OpenAI-compatible model IDs, writing
  per-request JSONL results and a rolling summary JSON.
* Stopped the NVIDIA serial benchmark after 19 `stepfun-ai/step-3.5-flash`
  real requests all returned HTTP 200 with empty `message.content`. The model's
  JSON answer appeared in `reasoning_content`, so the current production parser
  cannot use it safely.
* Added `docs/NVIDIA_NIM.md` with the NVIDIA capability matrix, raw artifact
  references, and recommendations. The best NVIDIA result was
  `meta/llama-4-maverick-17b-128e-instruct`: 10/10 parseable real Tenancy
  enrichments, usually 2.44-5.63 seconds but with one 153.48 second tail
  latency outlier.
* Probed paid OpenRouter `deepseek/deepseek-v4-flash` for capabilities and
  recorded the matrix in `docs/NVIDIA_NIM.md`. Plain chat, `json_object`, simple
  `json_schema`, real Tenancy `json_object`, and real Tenancy `json_schema` all
  worked. Reasoning stayed separate from `message.content` for JSON-object mode
  and did not interfere with parsing. The real Tenancy `json_object` probe took
  7.42 seconds and the real Tenancy `json_schema` probe took 22.24 seconds.
* Added explicit Tenancy chat request options for OpenRouter: chat mode can now
  choose `json_object` or `json_schema`, and the CLI can pass repeated
  `--llm-provider-ignore` values through OpenRouter provider routing. Kept the
  existing MiniMax/Qwen chat default request body when no provider route is
  supplied.
* Tested paid OpenRouter `deepseek/deepseek-v4-flash` with
  `provider.ignore=["deepinfra"]`. The routed real Tenancy probe was parseable
  with both response formats; `json_schema` was faster in that sample
  (`5.86s` versus `8.16s`) and kept reasoning separate from `message.content`.
  A five-document temp-copy canary completed 5/5 enriched with 0 failures at
  60 scheduled RPM.
* Audited the Tenancy LLM truncation incident in `docs/DESTROYED_DATA.md`.
  Confirmed that source PDFs and markdown bodies were not truncated by the LLM
  path, but all `tenancy-llm-v1` generated frontmatter metadata is suspect.
* Removed exact standalone `## Please read carefully:` post-ambles from 43,672
  Tenancy markdown bodies, leaving 43,854 non-empty parseable markdown bodies.
  The run wrote before/after hashes to
  `logs/tenancy-postamble-removal-20260526-110737.jsonl`; six OCR/conversion
  phrase outliers required follow-up review.
* Cleaned the six remaining Tenancy `Please read carefully:` OCR/conversion
  outliers while leaving `doc_justice_tenancy_206727790.md` untouched. Preserved
  adjudicator/date blocks that appeared after malformed footer headings in
  `doc_justice_tenancy_208507553.md` and
  `doc_justice_tenancy_legacy_6129174.md`.
* Added Tenancy LLM v2 story-shaped retrieval metadata:
  `applicant_story`, `respondent_story`, `neutral_fact_pattern`, `claims_made`,
  and `remedies_sought`. These fields are written to frontmatter and embedded
  only as separate `generated=true` retrieval views.
* Removed the Tenancy LLM `--llm-max-chars` option, all production `max_chars`
  call paths, and the `excerpt` request field. LLM requests now send the full
  parsed markdown body as `document_text`.
* Added `gliner` and a tested output-only NVIDIA GLiNER PII scanner for
  markdown bodies. The scanner emits span-level JSONL and aggregate summary JSON,
  keeps source markdown untouched, chunks text under a conservative GLiNER token budget
  to avoid GLiNER internal truncation, and supports explicit frontmatter audits
  with `--include-frontmatter`.
* Ran the 25-document Tenancy GLiNER canary with the token-capped scanner. The
  valid artifact is `logs/tenancy-pii-gliner-canary-25-token300.jsonl` with
  summary `logs/tenancy-pii-gliner-canary-25-token300-summary.json`: 25/25
  documents scanned, 0 failures, 436 spans, and all 25 documents had at least
  one detected span. Label counts were 357 `person`, 38 `national_id`, 35
  `address`, 3 `bank_account`, 2 `phone_number`, and 1 `credit_card`.
* Added an output-only OpenAI Privacy Filter scanner and ran the same
  25-document Tenancy canary. The artifact is
  `logs/tenancy-pii-openai-privacy-filter-canary-25.jsonl` with summary
  `logs/tenancy-pii-openai-privacy-filter-canary-25-summary.json`: 25/25
  documents scanned, 0 failures, 165 spans, and 21 documents had at least one
  detected span. Label counts were 134 `private_person`, 25 `private_address`,
  and 6 `private_date`; it avoided most redacted-placeholder noise but missed
  some suppressed placeholder-only decisions and still confused some
  organizations/pronouns with people.
* Added a standalone `vllm/tribunal_batch_eval.py` harness plus
  `tests/test_vllm_tribunal_batch_eval.py` so real Tenancy Tribunal markdown can
  be batch-scored through the vLLM OpenAI-compatible endpoint without using the
  existing `scripts/` ingestion pipeline.
* The new harness pairs real decisions from
  `storage/justice/tenancy/markdown_docling` with Justice sidecars only for
  discovery/provenance, derives gold header/order fields from the markdown
  itself, sends one JSON-schema extraction request per case through
  `/v1/chat/completions/batch`, and writes a manifest, payload, raw response,
  and scored summary under `vllm/results/`.
* Ran a balanced real-case batch as `tribunal_big_96_v2`: 96 cases total, 48
  redacted and 48 non-redacted, about 215,596 prompt tokens and 20,544
  completion tokens, completed in 21.695 seconds on
  `RedHatAI/Qwen3.6-35B-A3B-NVFP4`.
* The 96-case batch produced 48/96 fully correct case records (`0.5000`
  exact-case accuracy) and `0.9472` aggregate scored-field accuracy. Strong
  fields were citation, application number, decision date, adjudicator,
  applicant/respondent roles, payable-to direction, and redaction booleans.
  The main weak fields were tribunal location (`0.6702`), applicant name
  (`0.8830`), payable-by (`0.8841`), total award / main payable amount
  (`0.9079`), and respondent name (`0.9247`).
* The balanced run showed the batch endpoint itself is viable for the use case:
  JSON-schema structured extraction stayed stable across a ~236k-token total
  transaction. Accuracy degradation is concentrated in specific metadata fields
  rather than general batch collapse. Redacted cases are meaningfully harder:
  exact-case accuracy was `0.3542` for redacted decisions versus `0.6458` for
  non-redacted decisions.

## Verification

Last verified with:

```bash
uv run pre-commit run --files $(git ls-files --others --exclude-standard)
uv run python -m unittest discover -s tests
uv run pre-commit run --files scripts/scrape_authority_contacts.py scripts/contact_scrape_sources.py tests/test_scrape_authority_contacts.py
uv run python scripts/scrape_authority_contacts.py --help
sqlite3 :memory: ".read cloudflare/migrations/0001_initial_admin_engine.sql" ".read cloudflare/migrations/0002_agency_contact_candidates.sql" ".read cloudflare/migrations/0003_rename_agencies_to_authorities.sql" ".read cloudflare/migrations/0004_authority_contact_scrape_attempts.sql" ".schema sunlight_authorities" ".schema sunlight_authority_contact_candidates" ".schema sunlight_authority_contact_scrape_attempts"
pnpm dlx wrangler@latest d1 migrations apply sunlight-requests --local --config wrangler.jsonc
pnpm dlx wrangler@latest d1 migrations apply sunlight-requests --remote --config wrangler.jsonc
uv run python scripts/scrape_authority_contacts.py --remote --limit 20 --max-pages-per-authority 8 --timeout 12 --delay-ms 200
uv run python scripts/scrape_authority_contacts.py --remote --limit 30 --offset 20 --max-pages-per-authority 8 --timeout 12 --delay-ms 200
uv run python scripts/scrape_authority_contacts.py --remote --limit 100 --max-pages-per-authority 6 --timeout 8 --delay-ms 50
uv run python scripts/scrape_authority_contacts.py --remote --limit 500 --workers 32 --max-pages-per-authority 4 --timeout 5 --delay-ms 0
uv run python scripts/scrape_authority_contacts.py --remote --authority-id agy_fyi_psc --retry-attempted --max-pages-per-authority 8 --timeout 10 --delay-ms 0 --dry-run
uv run python scripts/scrape_authority_contacts.py --remote --limit 20 --retry-attempted --max-pages-per-authority 8 --timeout 8 --delay-ms 0 --workers 8 --dry-run
BRAVE_SEARCH_API_KEY=... uv run python scripts/scrape_authority_contacts.py --brave-search --source-file /tmp/sunlight-known-authorities.json --limit 8 --max-pages-per-authority 20 --timeout 8 --write-sql /tmp/sunlight-known-contact-candidates-brave.sql --delay-ms 250
uv run python scripts/parallel_convert_and_embed.py --help
uv run python -m unittest tests/test_parallel_convert_and_embed.py
uv run ruff check scripts/parallel_convert_and_embed.py scripts/export_to_vectorize.py tests/test_parallel_convert_and_embed.py
uv run python scripts/parallel_convert_and_embed.py --data-dir /tmp/fyi-smoke/data/request --markdown-dir /tmp/fyi-smoke/markdown --persist-dir /tmp/fyi-smoke/fyi-test.lancedb --convert-workers 1 --embed-batch-size 2 --markdown-queue-size 4 --max-tasks-per-worker 1
uv run python scripts/export_to_vectorize.py --persist-dir /tmp/fyi-smoke/fyi-test.lancedb --output-dir /tmp/fyi-smoke/vectorize-out --rows-per-file 1000
pnpm test:ts
pnpm exec tsc --noEmit
pnpm admin:build
pnpm authority:build
pnpm landing:build
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
pnpm dlx wrangler@latest dev apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc --ip 0.0.0.0 --port 8787
curl -s http://127.0.0.1:8787/search | rg -o "Search Sunlight|Search the disclosure archive|/api/search"
curl -s -X POST http://127.0.0.1:8787/api/search -H 'content-type: application/json' -d '{"question":"What information was released about council leisure centre contracts?","topK":3}'
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc
curl -I https://sunlight.nz/search
curl -s https://sunlight.nz/search | rg -o "Search Sunlight|Search the disclosure archive"
curl -s -X POST https://sunlight.nz/api/search -H 'content-type: application/json' -d '{"question":"What information was released about council leisure centre contracts?","topK":1}'
curl -s -X POST http://127.0.0.1:8787/api/search -H 'content-type: application/json' -d '{"question":"What information was released about council leisure centre contracts?"}'
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc
curl -s -X POST https://sunlight.nz/api/search -H 'content-type: application/json' -d '{"question":"What information was released about council leisure centre contracts?"}'
pnpm exec wrangler deploy apps/admin/dist/server/ssr/index.js --assets apps/admin/dist/client --dry-run --config apps/admin/wrangler.jsonc
pnpm dlx wrangler@latest deploy apps/admin/dist/server/ssr/index.js --assets apps/admin/dist/client --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/authority/dist/server/ssr/index.js --assets apps/authority/dist/client --dry-run --config apps/authority/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
pnpm dlx wrangler@latest d1 execute sunlight-requests --remote --command "SELECT COUNT(*) AS total, SUM(contact_status = 'verified') AS verified, SUM(status = 'inactive') AS inactive FROM sunlight_authorities;"
pnpm dlx wrangler@latest d1 migrations apply sunlight-search --remote --config apps/landing/wrangler.jsonc
uv run python scripts/export_bm25_to_d1.py --limit 2 --output-dir /tmp/sunlight_bm25_smoke --reset
uv run python scripts/export_bm25_to_d1.py --output-dir storage/d1_bm25_import --rows-per-file 500 --reset
uv run python scripts/export_bm25_to_d1.py --output-dir storage/d1_bm25_import --apply-existing --remote
pnpm dlx wrangler@latest d1 execute sunlight-search --remote --config apps/landing/wrangler.jsonc --command "SELECT count(*) AS rows FROM disclosed_chunks;" --json
pnpm dlx wrangler@latest d1 execute sunlight-search --remote --config apps/landing/wrangler.jsonc --command "SELECT c.request_title, c.authority_name, bm25(disclosed_chunks_fts, 0.0, 0.0, 2.0, 3.0, 1.0, 1.0) AS score, c.text_preview FROM disclosed_chunks_fts JOIN disclosed_chunks c ON c.chunk_id = disclosed_chunks_fts.chunk_id WHERE disclosed_chunks_fts MATCH '\"leisure\" OR \"centre\" OR \"contracts\"' ORDER BY score LIMIT 5;" --json
pnpm test:ts
pnpm exec tsc --noEmit
pnpm landing:build
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc --dry-run
uv run pre-commit run --files apps/landing/app/api/search/route.ts apps/landing/env.d.ts apps/landing/lib/search.ts apps/landing/lib/search.test.ts apps/landing/wrangler.jsonc cloudflare/search-migrations/0001_disclosed_chunks_fts.sql docs/SEARCH.md PROGRESS.md scripts/export_bm25_to_d1.py
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc
curl -s -X POST https://sunlight.nz/api/search -H 'content-type: application/json' -d '{"question":"What information was released about council leisure centre contracts?"}'
timeout 45 pnpm dlx wrangler@latest tail sunlight-landing --format=json --config apps/landing/wrangler.jsonc
pnpm dlx wrangler@latest d1 migrations apply sunlight-search --remote --config apps/landing/wrangler.jsonc
pnpm test:ts
pnpm exec tsc --noEmit
pnpm landing:build
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc --dry-run
uv run pre-commit run --files apps/landing/app/api/search/route.ts apps/landing/lib/search-security.ts apps/landing/lib/search-security.test.ts cloudflare/search-migrations/0002_search_rate_limits.sql docs/SEARCH.md PROGRESS.md
pnpm dlx wrangler@latest deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc
curl -s -o /tmp/sunlight_bad_content_type.json -w '%{http_code}\n' -X POST https://sunlight.nz/api/search -H 'content-type: text/plain' -d '{"question":"What did Auckland Council release?"}'
node -e 'process.stdout.write(JSON.stringify({question:"x".repeat(5000)}))' | curl -s -o /tmp/sunlight_large_body.json -w '%{http_code}\n' -X POST https://sunlight.nz/api/search -H 'content-type: application/json' --data-binary @-
ua="sunlight-rl-test-$(date +%s)"; for i in $(seq 1 13); do curl -s -o /tmp/sunlight_rate_limit.json -w '%{http_code} ' -A "$ua" -X POST https://sunlight.nz/api/search -H 'content-type: application/json' -d '{'; done
curl -s -A "sunlight-normal-smoke-$(date +%s)" -X POST https://sunlight.nz/api/search -H 'content-type: application/json' -d '{"question":"What information was released about council leisure centre contracts?","topK":1}'
curl -s http://127.0.0.1:8000/v1/models | jq '.data[] | {id}'
uv run python scripts/generate_eval_questions.py --help
uv run pre-commit run --files scripts/generate_eval_questions.py
uv run python scripts/generate_eval_questions.py --count 2 --output /tmp/sunlight-eval-smoke.ndjson --force
uv run python scripts/generate_eval_questions.py --count 20 --output manifests/fyi/v1/eval-questions.ndjson --force
uv run python - <<'PY'
import json
from collections import Counter
from pathlib import Path
rows = [json.loads(line) for line in Path("manifests/fyi/v1/eval-questions.ndjson").read_text(encoding="utf-8").splitlines() if line.strip()]
print("rows", len(rows))
print("kinds", dict(Counter(row["kind"] for row in rows)))
print("answerable", dict(Counter(row["answerable"] for row in rows)))
print("reviewed", dict(Counter(row["reviewed"] for row in rows)))
print("unique_ids", len({row["id"] for row in rows}))
PY
uv run python - <<'PY'
import json
import re
from pathlib import Path
rows = [json.loads(line) for line in Path("manifests/fyi/v1/eval-questions.ndjson").read_text(encoding="utf-8").splitlines() if line.strip()]
base = Path("fyi/markdown")
def find_doc(doc_id):
    suffix = doc_id.rsplit("_", 1)[-1]
    for path in base.glob(f"*__{suffix}.md"):
        if doc_id in path.read_text(encoding="utf-8", errors="replace")[:4000]:
            return path
    raise FileNotFoundError(doc_id)
def norm(text):
    return re.sub(r"\s+", " ", text.lower()).strip()
def compact(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())
bad = []
for row in rows:
    text = find_doc(row["document_id"]).read_text(encoding="utf-8", errors="replace")
    if norm(row["supporting_passage"]) not in norm(text) and compact(row["supporting_passage"]) not in compact(text):
        bad.append(row["id"])
print("rows", len(rows), "reviewed", sum(row.get("reviewed") is True for row in rows), "bad_support", bad)
PY
uv run pre-commit run --files scripts/eval_search.py
uv run python -m unittest tests/test_eval_search.py
uv run pre-commit run --files scripts/eval_search.py scripts/eval_search_bm25.py tests/test_eval_search.py
uv run python -m py_compile scripts/eval_search.py scripts/eval_search_bm25.py
uv run python scripts/eval_search.py --limit 1 --no-rerank --output-dir /tmp/sunlight-eval-smoke --device cuda
uv run python scripts/eval_search.py --limit 1 --output-dir /tmp/sunlight-eval-smoke-rerank --device cuda
uv run python scripts/eval_search.py --output-dir storage/evals/search/local-lancedb-20 --device cuda
cat storage/evals/search/local-lancedb-20/report.md
uv run python -m unittest tests/test_export_hf_markdown_dataset.py
uv run pre-commit run --files scripts/export_hf_markdown_dataset.py tests/test_export_hf_markdown_dataset.py
uv run python scripts/export_hf_markdown_dataset.py --limit 5 --output-dir /tmp/sunlight-hf-smoke --force
uv run python scripts/export_hf_markdown_dataset.py --output-dir storage/huggingface/sunlight-fyi-markdown --force
uv run python -m unittest discover -s tests
uv run pre-commit run --files docs/DATASET.md PROGRESS.md
uv run python -m unittest tests/test_eval_search.py
uv run python -m unittest discover -s tests
uv run ruff check scripts/eval_search.py scripts/eval_search_bm25.py tests/test_eval_search.py
uv run pre-commit run --files scripts/eval_search.py tests/test_eval_search.py manifests/fyi/v1/eval-questions.ndjson PROGRESS.md
uv run python -m unittest tests/test_eval_search.py
uv run ruff check scripts/eval_search.py scripts/eval_search_bm25.py tests/test_eval_search.py
uv run python -m unittest tests/test_eval_search.py
uv run ruff check scripts/eval_search.py scripts/eval_search_bm25.py tests/test_eval_search.py
pnpm test:ts
pnpm exec tsc --noEmit
pnpm landing:build
uv run python -m unittest tests/test_eval_search.py
pnpm test:ts
pnpm exec tsc --noEmit
pnpm landing:build
uv run python -m unittest tests.test_tenancy_corpus tests.test_ingest_tenancy tests.test_export_bm25_to_d1 tests.test_export_to_vectorize tests.test_parallel_convert_and_embed
uv run python -m unittest discover -s tests
uv run ruff check scripts/ingest_tenancy.py scripts/tenancy_llm.py scripts/embedding_helpers.py scripts/tenancy_corpus.py scripts/parallel_convert_and_embed.py scripts/export_bm25_to_d1.py scripts/export_to_vectorize.py scripts/fyi_lancedb_writer.py tests/test_ingest_tenancy.py tests/test_tenancy_corpus.py tests/test_parallel_convert_and_embed.py tests/test_export_bm25_to_d1.py tests/test_export_to_vectorize.py
uv run ruff check --select C901 scripts/ingest_tenancy.py scripts/parallel_convert_and_embed.py scripts/tenancy_llm.py scripts/embedding_helpers.py
uv run coverage run --source=scripts -m unittest tests.test_tenancy_corpus tests.test_ingest_tenancy tests.test_export_bm25_to_d1 tests.test_export_to_vectorize tests.test_parallel_convert_and_embed
uv run coverage report -m scripts/tenancy_corpus.py scripts/tenancy_llm.py scripts/embedding_helpers.py scripts/ingest_tenancy.py scripts/parallel_convert_and_embed.py scripts/export_bm25_to_d1.py scripts/export_to_vectorize.py scripts/fyi_lancedb_writer.py
uv run scripts/ingest_tenancy.py --limit 1 --convert-workers 1 --embed-batch-size 1 --llm-batch-size 1 --embed-gpu 0 --llm-timeout 180 --llm-max-tokens 4096
uv run scripts/ingest_tenancy.py --skip-llm --convert-workers 6 --max-tasks-per-worker 20 --embed-batch-size 64 --model-embed-batch-size 8 --embed-gpu 0 --convert-gpu 0
uv run scripts/ingest_tenancy.py --skip-llm --skip-embed --convert-workers 6 --max-tasks-per-worker 200 --convert-gpu 0
uv run scripts/ingest_tenancy.py --skip-convert --skip-llm --embed-gpu 0
uv run python -m unittest tests/test_eval_search.py
uv run python -m unittest discover -s tests
uv run ruff check scripts/eval_search.py scripts/eval_search_agentic.py tests/test_eval_search.py
uv run ruff check --select C901 scripts/eval_search.py scripts/eval_search_agentic.py tests/test_eval_search.py
uv run pre-commit run --files scripts/eval_search.py scripts/eval_search_agentic.py tests/test_eval_search.py docs/AGENTIC_RAG.md docs/SEARCH.md PROGRESS.md
uv run python scripts/eval_search.py --limit 1 --agentic --no-rerank --output-dir /tmp/sunlight-agentic-eval-smoke --device cuda
pnpm test:ts apps/landing/lib/search.test.ts
pnpm test:ts
pnpm exec tsc --noEmit
pnpm landing:build
pnpm dlx playwright screenshot --viewport-size=1366,768 http://127.0.0.1:8787/search /tmp/sunlight-search-desktop-compact.png
pnpm dlx playwright screenshot --viewport-size=390,844 http://127.0.0.1:8787/search /tmp/sunlight-search-mobile-compact.png
pnpm test:ts apps/landing/lib/search-examples.test.ts apps/landing/lib/search.test.ts
docker compose -f bifrost/docker-compose.yml --env-file bifrost/.env config --quiet
curl -s http://127.0.0.1:8081/v1/models
uv run python -m unittest tests.test_bifrost_config tests.test_ingest_tenancy
uv run python -m unittest tests.test_ingest_tenancy
uv run python -m unittest discover -s tests
uv run ruff check scripts/ingest_tenancy.py scripts/tenancy_llm.py scripts/tenancy_instructor.py scripts/tenancy_llm_messages.py scripts/tenancy_rate_limit.py tests/test_ingest_tenancy.py
uv run ruff check --select C901 scripts/ingest_tenancy.py scripts/tenancy_llm.py scripts/tenancy_instructor.py scripts/tenancy_llm_messages.py scripts/tenancy_rate_limit.py
uv run pre-commit run --files scripts/ingest_tenancy.py scripts/tenancy_llm.py scripts/tenancy_instructor.py scripts/tenancy_llm_messages.py scripts/tenancy_rate_limit.py tests/test_ingest_tenancy.py PROGRESS.md pyproject.toml
uv run python -m unittest tests.test_ingest_tenancy.IngestTenancyTests.test_request_generated_enrichment_can_use_instructor tests.test_ingest_tenancy.IngestTenancyTests.test_request_retries_are_rate_limited
uv run python -m unittest tests.test_ingest_tenancy
uv run python -m unittest discover -s tests
uv run ruff check scripts/ingest_tenancy.py scripts/tenancy_llm.py scripts/tenancy_instructor.py scripts/tenancy_llm_messages.py scripts/tenancy_rate_limit.py tests/test_ingest_tenancy.py
uv run pre-commit run --files scripts/tenancy_llm.py tests/test_ingest_tenancy.py
TENANCY_LLM_API_KEY="$NVIDIA_API_KEY" uv run python scripts/ingest_tenancy.py --skip-convert --skip-embed --limit 5 --llm-timeout 600 --llm-rpm 5 --llm-concurrency 1 --llm-start-jitter-min 0 --llm-start-jitter-max 0
uv run python -m unittest tests/test_scan_pii_gliner.py
uv run ruff check scripts/scan_pii_gliner.py tests/test_scan_pii_gliner.py
uv run python scripts/scan_pii_gliner.py --help
uv run python - <<'PY'
from gliner import GLiNER
print(GLiNER.__name__)
PY
uv run python scripts/scan_pii_gliner.py --markdown-dir storage/justice/tenancy/markdown_docling --limit 1 --labels person,address,email,phone_number --threshold 0.3 --output-jsonl /tmp/tenancy-pii-gliner-smoke.jsonl --summary-json /tmp/tenancy-pii-gliner-smoke-summary.json
uv run python scripts/scan_pii_gliner.py --markdown-dir storage/justice/tenancy/markdown_docling --limit 25 --labels person,address,email,phone_number,national_id,driver_license,passport_number,bank_account,credit_card --threshold 0.3 --output-jsonl logs/tenancy-pii-gliner-canary-25-token300.jsonl --summary-json logs/tenancy-pii-gliner-canary-25-token300-summary.json
uv run python -m unittest tests/test_scan_pii_privacy_filter.py
uv run ruff check scripts/scan_pii_privacy_filter.py tests/test_scan_pii_privacy_filter.py
uv run python - <<'PY'
from transformers import AutoConfig, AutoTokenizer
model_id = "openai/privacy-filter"
config = AutoConfig.from_pretrained(model_id)
tokenizer = AutoTokenizer.from_pretrained(model_id)
print(config.model_type, getattr(config, "max_position_embeddings", None), tokenizer.model_max_length)
PY
uv run python scripts/scan_pii_privacy_filter.py --markdown-dir storage/justice/tenancy/markdown_docling --limit 25 --output-jsonl logs/tenancy-pii-openai-privacy-filter-canary-25.jsonl --summary-json logs/tenancy-pii-openai-privacy-filter-canary-25-summary.json
uv run python -m unittest tests/test_vllm_tribunal_batch_eval.py
uv run python vllm/tribunal_batch_eval.py --case-count 96 --run-name tribunal_big_96_v2
```

## Notes

Cloudflare resources:

* D1 database: `sunlight-requests`
* D1 database id: `796835ba-d5e5-4ad2-a931-bdf7b3a2b7dc`
* Search D1 database: `sunlight-search`
* Search D1 database id: `be61ceef-eed3-43cd-95d2-cd762f5fd59f`
* R2 bucket: `sunlight-request-artifacts`
* Zero Trust organization: `Sunlight`
* Access auth domain: `sunlight-nz.cloudflareaccess.com`
* Access identity provider: One-time PIN login
* Access-protected admin app: `admin.sunlight.nz`
* Admin UI component system: shadcn-style local components with Tailwind v4
* Landing app: `sunlight.nz` and `www.sunlight.nz`
* FYI authorities imported: 3,177
* Verified authority contacts: 1375
* Authorities needing contact review: 4
* Missing contacts (no candidate): 1798
* Active authorities still needing first scrape attempt: 0
* Inactive imported authorities: 238
* Current blocker for a complete send-ready set: A large portion of authorities still lack a candidate email address. The search-seeded pass has been run, yielding a modest improvement. Further investigation into difficult-to-scrape authorities or alternative data sources may be needed.
* Extended the standalone `vllm/tribunal_batch_eval.py` harness with non-LLM
  MiniMax teacher scoring for generated retrieval fields. Real tribunal case
  manifests now carry frontmatter-derived `teacher_fields` for
  `case_summary`, `catchwords`, `questions_answered`, `applicant_story`,
  `respondent_story`, `neutral_fact_pattern`, `claims_made`,
  `remedies_sought`, and `legal_principles`. The scorer uses lexical token
  overlap for free-text fields plus greedy item-level precision/recall/F1 for
  list and legal-principle fields, so future vLLM parameter sweeps can be
  graded without an LLM judge. A `--dry-run` over real cases confirmed the
  sampled records carried all nine teacher fields.
* Added local post-hoc JSON-schema validation to the standalone tribunal eval
  harness instead of trusting vLLM `strict: true` alone. Summaries now report
  parse-success and schema-valid rates plus counts for missing required fields,
  type violations, enum violations, and extra properties. Re-scoring the saved
  `tribunal_big_96_v2`, `tribunal_big_96_think_2048`, and
  `tribunal_big_96_think_4096` outputs showed all 96/96 responses in each run
  were parseable and schema-valid, so the quality differences are extraction
  errors rather than schema drift.
* Changed tribunal batch sizing to reserve `prompt_tokens + thinking_budget`
  per selected case when a target batch token budget is used, and surfaced
  `approximate_reserved_tokens` in run summaries so thinking-enabled sweeps do
  not over-pack batches on prompt length alone.
* Added `vllm/tribunal_process_docling.py` to run the structured extractor
  across all Docling markdown directly, without requiring Justice sidecars. It
  shards the corpus into token-bounded batches, writes per-batch manifest,
  payload, response, summary, and append-only `extractions.jsonl` outputs into
  a dedicated result folder, and tracks live progress in `progress.json`. The
  runner also retries schema-invalid or truncated cases individually with larger
  `max_tokens` so long-name outliers do not poison whole-batch completeness.
  The active full-corpus run is
  `vllm/results/tribunal_docling_full_20260527_225730`; after the first two
  batches it had processed 192 documents with no failed batches, and repaired a
  known truncation outlier (`172070039`) by retrying it at `640` output tokens.
* Updated the full-corpus Docling runner to dispatch up to two batch HTTP
  requests concurrently, which matches the two vLLM instances behind the load
  balancer. The active run was resumed in place with
  `--max-concurrent-batches 2`, and the first resumed window completed 384
  documents across four clean batches in about 39 seconds, roughly doubling the
  earlier single-lane throughput while keeping `96/96` parseable and
  `96/96` schema-valid outputs per batch.
* Completed the full Docling tribunal extraction run in
  `vllm/results/tribunal_docling_full_20260527_225730`: all `43,854` markdown
  documents produced an extraction with `0` failed batches and a final
  `extractions.jsonl` count of `43,854`.
* Added `vllm/tribunal_judge_spotcheck.py` plus focused tests so sampled
  extraction rows can be sent back to the vLLM endpoint as strict JSON
  document-vs-extraction audits. The runner samples completed `extractions`,
  numbers markdown lines for evidence references, saves payload/response
  artifacts, and retries parse-error judgments one case at a time with larger
  `max_tokens`. A real 20-case sample at
  `vllm/results/tribunal_docling_full_20260527_225730/judge_spotcheck_20260527_125453`
  cut parse errors from `16/20` to `3/20`, but the same Qwen judge still
  over-flagged many likely-correct cases, so the audit is currently useful for
  triage rather than as a trustworthy automatic score.
* Added `TOKEN_DISTRIBUTION.md` as a sysadmin-oriented summary of the tribunal
  vLLM request shapes: per-item prompt percentiles across all `43,854` Docling
  markdowns, actual prompt/completion percentiles across the completed
  `483`-batch corpus run, and the no-thinking versus thinking-budget usage
  deltas from the fixed `96`-case benchmark runs. The note also records the key
  distinction between the true per-item context formula (`prompt + max_tokens`)
  and the repo's current batch-packing heuristic
  (`approximate_prompt + thinking_budget`).

Known issue:

* `vinext build` succeeds for all three apps, but `vinext dev` currently returns
  404 for `/`. Investigate Vinext dev-server routing before relying on local
  browser previews.
* The local resolver in this workspace did not resolve `admin.sunlight.nz`
  immediately after deployment, but Cloudflare's public resolver did and the
  Cloudflare edge returned the expected Access login redirect.

Important naming boundary:

* `SunlightRequest` and `sunlight_*` tables represent Sunlight's own recurring
  disclosure collection workflow.
* `DisclosedRequest`, `DisclosedResponse`, and future `disclosed_*` tables are
  reserved for later extraction of underlying OIA/LGOIMA material.

## Next Steps

1. Inspect the `tribunal_big_96_v2` misses by field and by document, especially
   tribunal-location normalization, placeholder-party naming, and ambiguous
   payable-direction cases.
2. Review the judge-spotcheck false positives and tighten the audit rubric for
   application numbers, bilingual tribunal-location headers, role-vs-name
   fields, and bond-driven payable direction before relying on LLM judging.
3. Make the tribunal harness context-aware per item by recording and checking
   `prompt + max_tokens` against the chosen model limit, separately from the
   scheduler-style batch reserve heuristic.
4. Expand the vLLM output schema to emit the MiniMax-style generated retrieval
   fields so the new non-LLM teacher scorer can grade real predictions instead
   of just the structured header/order slice.
5. Run a small generated-field sweep first on batch sizes `1` and `8`, then
   compare structured exact-field accuracy, schema-valid rate, and teacher-field
   overlap metrics before scaling back up to the balanced 96-case run.
6. Keep monitoring the active `tenancy-minimax-v2` tmux run until the
   `tenancy-llm-v2` refresh completes, watching persisted failures and
   Instructor retry volume.
7. Compare the GLiNER and OpenAI Privacy Filter canaries side by side. OpenAI
   Privacy Filter currently looks cleaner for redacted-placeholder noise, while
   GLiNER has more configurable-label recall and more false positives.
6. Tune Privacy Filter post-filters first: remove pronouns/role words, treat
   known agency/property-management names separately, and decide whether
   adjudicator names should count as review-relevant PII.
7. If the tuned Privacy Filter canary is useful, run the full JSONL audit and summarize
   documents that need human redaction review before using results in a
   publication workflow.
8. Do not add NVIDIA `minimaxai/minimax-m2.7` to the production enrichment loop
   at 15+ scheduled RPM. If it is still worth using, first test a lower
   scheduled rate with an explicit in-flight cap, then implement provider-level
   caps before alternating providers.
9. If `json_schema` proves unstable with `MiniMax-M2.7-highspeed`, retry with
   `json_mode` before falling back to `md_json`, since `md_json` has the
   broadest compatibility but the weakest speed and accuracy profile.
10. Run the reviewed search eval set with `scripts/eval_search.py --no-rerank`
   and `scripts/eval_search.py --agentic --no-rerank`, then compare final
   recall@5, MRR@5, exact/numeric misses, second-pass rate, and latency.
11. Resume Tenancy embedding for the converted legacy markdown with
   `--skip-convert --skip-llm`, then verify 11,476 legacy embedding markers and
   updated LanceDB row counts.
12. Add Tenancy eval questions for exact IDs/citations, city/suburb, rent
   arrears, bond, suppression, statute-section, amount-heavy, and
   absent-answer cases.
13. Export Tenancy source chunks to the D1 BM25 sidecar without resetting
   existing FYI rows, then export Tenancy vectors to the corpus Vectorize index.
14. Compare Tenancy vector, BM25, hybrid, agentic, and generated-view retrieval before
   enabling Tenancy in public search.
15. Update the landing search API and UI for multi-source citations, labels, and
   source filters.
16. Upload canonical Tenancy PDFs and Docling markdown to `sunlight-corpus`.
17. Choose the Hugging Face dataset repo id, visibility, and license wording,
   then publish with the exporter upload command.
18. Schedule the Hugging Face export after FYI markdown ingestion so the dataset
   stays living; use full snapshots by default and delta exports when append-only
   updates are useful.
19. Add an R2 upload command for `sunlight-corpus` that uploads only canonical
   PDFs and converted markdown, excluding FYI JSON/HTML/CSV sidecars and local
   metadata.
20. Create a Cloudflare AI Search instance scoped to the R2 markdown prefix and
   run the first eval set against both pipelines.
21. Add R2 markdown hydration to `/api/search` once `sunlight-corpus` is live,
   so answers can use full chunks instead of Vectorize `text_preview` metadata.
22. Run `scripts/eval_search.py --rebuild-bm25` once on the full LanceDB corpus
   to materialize `storage/evals/search/local-bm25.sqlite3`, then compare the
   reviewed set across vector, BM25, hybrid, and reranked hybrid stages.
23. Continue expanding the reviewed eval manifest, especially with more
   numeric/table-heavy FYI records and additional production failures once
   search logs expose them.
24. Add optional local vLLM answer generation and answer-grounding checks to the
   eval harness after retrieval metrics are stable.
25. Add exact query response caching for `/api/search` to reduce repeated answer
   generation cost and latency.
26. Consider moving the search UI to AI SDK `useChat`/streaming once citations
   can be sent as structured stream data instead of one JSON response.
27. Do a controlled live Cloudflare Email Sending test before sending to real
   authorities.
28. Keep `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` current in Worker secrets
   if the R2 API token is rotated.
