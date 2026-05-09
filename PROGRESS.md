# Progress

## Current Slice

The terminology rename to authorities is complete and the deployed D1 schema has
been migrated forward to match it. The authority contact review loop now exists
in the admin app. The scraper now auto-verifies clear best addresses and records
no-result attempts so human review is only needed for genuinely ambiguous cases.
The current operational focus is completing scrape attempts for the remaining
active authorities before enabling real sends.

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

## Verification

Last verified with:

```bash
uv run pre-commit run --files $(git ls-files --others --exclude-standard)
uv run python -m unittest discover -s tests
uv run python scripts/scrape_authority_contacts.py --help
sqlite3 :memory: ".read cloudflare/migrations/0001_initial_admin_engine.sql" ".read cloudflare/migrations/0002_agency_contact_candidates.sql" ".read cloudflare/migrations/0003_rename_agencies_to_authorities.sql" ".read cloudflare/migrations/0004_authority_contact_scrape_attempts.sql" ".schema sunlight_authorities" ".schema sunlight_authority_contact_candidates" ".schema sunlight_authority_contact_scrape_attempts"
pnpm dlx wrangler@latest d1 migrations apply sunlight-requests --local --config wrangler.jsonc
pnpm dlx wrangler@latest d1 migrations apply sunlight-requests --remote --config wrangler.jsonc
uv run python scripts/scrape_authority_contacts.py --remote --limit 20 --max-pages-per-authority 8 --timeout 12 --delay-ms 200
uv run python scripts/scrape_authority_contacts.py --remote --limit 30 --offset 20 --max-pages-per-authority 8 --timeout 12 --delay-ms 200
uv run python scripts/scrape_authority_contacts.py --remote --limit 100 --max-pages-per-authority 6 --timeout 8 --delay-ms 50
uv run python scripts/scrape_authority_contacts.py --remote --limit 500 --workers 32 --max-pages-per-authority 4 --timeout 5 --delay-ms 0
BRAVE_SEARCH_API_KEY=... uv run python scripts/scrape_authority_contacts.py --brave-search --source-file /tmp/sunlight-known-authorities.json --limit 8 --max-pages-per-authority 20 --timeout 8 --write-sql /tmp/sunlight-known-contact-candidates-brave.sql --delay-ms 250
pnpm test:ts
pnpm exec tsc --noEmit
pnpm admin:build
pnpm authority:build
pnpm landing:build
pnpm exec wrangler deploy apps/admin/dist/server/ssr/index.js --assets apps/admin/dist/client --dry-run --config apps/admin/wrangler.jsonc
pnpm dlx wrangler@latest deploy apps/admin/dist/server/ssr/index.js --assets apps/admin/dist/client --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/authority/dist/server/ssr/index.js --assets apps/authority/dist/client --dry-run --config apps/authority/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
pnpm dlx wrangler@latest d1 execute sunlight-requests --remote --command "SELECT COUNT(*) AS total, SUM(contact_status = 'verified') AS verified, SUM(status = 'inactive') AS inactive FROM sunlight_authorities;"
```

## Notes

Cloudflare resources:

* D1 database: `sunlight-requests`
* D1 database id: `796835ba-d5e5-4ad2-a931-bdf7b3a2b7dc`
* R2 bucket: `sunlight-request-artifacts`
* Zero Trust organization: `Sunlight`
* Access auth domain: `sunlight-nz.cloudflareaccess.com`
* Access identity provider: One-time PIN login
* Access-protected admin app: `admin.sunlight.nz`
* Admin UI component system: shadcn-style local components with Tailwind v4
* Landing app: `sunlight.nz` and `www.sunlight.nz`
* FYI authorities imported: 3,177
* Verified authority contacts: 209
* Authorities needing contact review: 7
* Contact scrape attempts: 203 auto-verified, 7 needs review, 2,723 no
  candidate
* Active authorities still needing first scrape attempt: 0
* Contact candidate rows: 19 accepted, 1 candidate, 1 rejected
* Inactive imported authorities: 238

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

1. Finish the public information scraper:
   * Run a second pass over `no_candidate` outcomes with `BRAVE_SEARCH_API_KEY`
     available:
     `uv run python scripts/scrape_authority_contacts.py --remote --retry-attempted --brave-search --brave-concurrency 1 --limit 500 --workers 32 --max-pages-per-authority 4 --timeout 5 --delay-ms 0`
   * Inspect a sample of no-candidate outcomes and decide the simple fallback
     for form-only authorities.
   * Keep manual review only for future `needs_review` rows caused by genuinely
     ambiguous candidates.
2. Wire admin pages/actions through the existing Cloudflare Access JWT validator
   so D1 admin roles are enforced inside the app as well as at the edge.
3. Continue moving admin pages from legacy CSS classes to shadcn-style local
   components.
4. Consider replacing the authorities table/filter controls with shadcn form/table
   primitives after the base behavior has settled.
5. Do a controlled live Cloudflare Email Sending test before sending to real
   authorities.
6. Keep `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` current in Worker secrets
   if the R2 API token is rotated.
7. Add multipart upload support and per-file retry/remove controls.
8. Investigate the Vinext dev-server 404 and confirm local previews work.
