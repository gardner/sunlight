# Progress

## Current Slice

The public `sunlight.nz/search` path now has a custom hybrid retriever: semantic
Vectorize candidates plus D1 FTS5 BM25 candidates, fused with reciprocal rank
fusion and reranked with Workers AI BGE. The next search slice is to add
Cloudflare AI Search as a managed comparison pipeline and run RAG evaluations
against both retrievers.

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
uv run pre-commit run --files scripts/eval_search.py
uv run python scripts/eval_search.py --limit 1 --no-rerank --output-dir /tmp/sunlight-eval-smoke --device cuda
uv run python scripts/eval_search.py --limit 1 --output-dir /tmp/sunlight-eval-smoke-rerank --device cuda
uv run python scripts/eval_search.py --output-dir storage/evals/search/local-lancedb-20 --device cuda
cat storage/evals/search/local-lancedb-20/report.md
uv run python -m unittest tests/test_export_hf_markdown_dataset.py
uv run pre-commit run --files scripts/export_hf_markdown_dataset.py tests/test_export_hf_markdown_dataset.py
uv run python scripts/export_hf_markdown_dataset.py --limit 5 --output-dir /tmp/sunlight-hf-smoke --force
uv run python scripts/export_hf_markdown_dataset.py --output-dir storage/huggingface/sunlight-fyi-markdown --force
uv run python -m unittest discover -s tests
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

1. Choose the Hugging Face dataset repo id, visibility, and license wording,
   then publish with the exporter upload command.
2. Schedule the Hugging Face export after FYI markdown ingestion so the dataset
   stays living; use full snapshots by default and delta exports when append-only
   updates are useful.
3. Add an R2 upload command for `sunlight-corpus` that uploads only canonical
   PDFs and converted markdown, excluding FYI JSON/HTML/CSV sidecars and local
   metadata.
4. Create a Cloudflare AI Search instance scoped to the R2 markdown prefix and
   run the first eval set against both pipelines.
5. Add R2 markdown hydration to `/api/search` once `sunlight-corpus` is live,
   so answers can use full chunks instead of Vectorize `text_preview` metadata.
6. Review and hand-correct the LLM-generated eval question manifest, especially
   numeric questions where the first prompt had the highest invalid-output rate.
7. Add local BM25 to `scripts/eval_search.py` so the local eval can compare
   vector-only, BM25-only, hybrid fusion, and reranked hybrid runs.
8. Add optional local vLLM answer generation and answer-grounding checks to the
   eval harness after retrieval metrics are stable.
9. Add exact query response caching for `/api/search` to reduce repeated answer
   generation cost and latency.
10. Consider moving the search UI to AI SDK `useChat`/streaming once citations
   can be sent as structured stream data instead of one JSON response.
11. Do a controlled live Cloudflare Email Sending test before sending to real
   authorities.
12. Keep `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` current in Worker secrets
   if the R2 API token is rotated.
