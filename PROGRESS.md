# Progress

## Current Slice

The agency contact scraper first slice is complete. The request preparation
slice and outbound email slice remain implemented through dry-run deployment
validation.

Completed:

* Defined admin, agency response, landing, and implementation planning docs.
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
  * `apps/agency`
  * `apps/landing`
* Added Wrangler config for each app.
* Added initial admin D1-backed summary page.
* Added agency response token route skeleton.
* Added Cloudflare Access JWT validation helper for admin.
* Added FYI authority import command.
* Imported 3,177 FYI authority records into remote D1.
* Added admin agency list/detail screens.
* Added agency contact verification action.
* Added request template creation screens.
* Added request cycle creation/detail screens.
* Added `SunlightRequest` preparation from verified agencies.
* Added cycle approval.
* Added Cloudflare Email Sending binding for admin.
* Added outbound email rendering, queueing, sending, status updates, and audit
  events.
* Added cycle send preview with request status counts.
* Added outbound send results and failed-email retry controls.
* Added overdue SunlightRequest summary and admin `/requests` list.
* Added agency response metadata submission.
* Added direct-to-R2 presigned upload session and completion routes.
* Configured R2 CORS for browser uploads from `requests.sunlight.nz`.
* Created R2 S3 credentials for agency uploads and stored them in `.env`.
* Added the R2 S3 credentials as agency Worker secrets.
* Deployed the agency Worker and verified a disposable live upload end to end.
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
* Added paginated agency listing queries and count metadata.
* Added immediate browser-side filtering-as-you-type for the admin agencies page
  using both `onKeyUp` and `onChange` input paths.
* Added agency pagination controls and page-size selection.
* Replaced prohibited proxied apex DNS records that pointed at Cloudflare edge
  IPs with the landing Worker custom-domain DNS record.
* Deployed the Stitch-inspired landing app to `sunlight.nz` and
  `www.sunlight.nz`.
* Moved `sunlight.webp` into the landing app public assets and used it as the
  hero image.
* Added `curl_cffi` and `beautifulsoup4` for the agency contact scraper.
* Added D1 migration `0002_agency_contact_candidates.sql` for scraped contact
  candidates.
* Added tested Python helpers for email normalization, extraction, candidate
  link selection, scoring, and SQL generation.
* Added `scripts/scrape_agency_contacts.py` with conservative dry-run,
  `--write-sql`, `--source-file`, and remote D1 apply support.
* Deployed the updated landing app to `sunlight.nz` and `www.sunlight.nz`.
* Applied contact-candidate migration `0002_agency_contact_candidates.sql`
  locally and remotely.
* Added Brave Search seeding for official same-site contact discovery using
  `BRAVE_SEARCH_API_KEY`, one search request per agency.
* Reworked scraper discovery to prefer Brave-seeded official pages, then expand
  only high-value same-site contact/OIA/privacy/request links.
* Added progress logging and slow-fetch warnings so stuck crawlers can be
  identified by agency and URL.
* Tested scraper output against known agencies using `--write-sql`; strong
  candidates were found for Auckland Council, Ministry of Justice, and
  Wellington City Council.

## Verification

Last verified with:

```bash
uv run pre-commit run --files $(git ls-files --others --exclude-standard)
uv run python -m unittest discover -s tests
uv run python scripts/scrape_agency_contacts.py --help
sqlite3 :memory: ".read cloudflare/migrations/0001_initial_admin_engine.sql" ".read cloudflare/migrations/0002_agency_contact_candidates.sql" ".schema sunlight_agency_contact_candidates"
pnpm dlx wrangler@latest d1 migrations apply sunlight-requests --local --config wrangler.jsonc
pnpm dlx wrangler@latest d1 migrations apply sunlight-requests --remote --config wrangler.jsonc
BRAVE_SEARCH_API_KEY=... uv run python scripts/scrape_agency_contacts.py --brave-search --source-file /tmp/sunlight-known-agencies.json --limit 8 --max-pages-per-agency 20 --timeout 8 --write-sql /tmp/sunlight-known-contact-candidates-brave.sql --delay-ms 250
pnpm test:ts
pnpm exec tsc --noEmit
pnpm admin:build
pnpm agency:build
pnpm landing:build
pnpm exec wrangler deploy apps/admin/dist/server/ssr/index.js --assets apps/admin/dist/client --dry-run --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/agency/dist/server/ssr/index.js --assets apps/agency/dist/client --dry-run --config apps/agency/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/ssr/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
pnpm dlx wrangler@latest d1 execute sunlight-requests --remote --command "SELECT COUNT(*) AS total, SUM(contact_status = 'verified') AS verified, SUM(status = 'inactive') AS inactive FROM sunlight_agencies;"
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
* Verified agency contacts: 0
* Inactive imported agencies: 238

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
   * Deduplicate repeated evidence rows per agency/email before SQL generation
     or make the admin review UI group them cleanly.
   * Decide how to handle form-only agencies where no public intake email is
     visible in fetched HTML.
   * Run a small remote scrape batch.
   * Add admin review UI for filtering `needs_review`, showing candidate
     email/evidence/confidence, accepting primary contacts, accepting secondary
     contacts, rejecting candidates, and marking agency contacts invalid.
   * Add audit events for accept, reject, and invalid decisions.
   * Only after admin review exists, allow verified contacts to feed sending.
2. Wire admin pages/actions through the existing Cloudflare Access JWT validator
   so D1 admin roles are enforced inside the app as well as at the edge.
3. Continue moving admin pages from legacy CSS classes to shadcn-style local
   components.
4. Consider replacing the agencies table/filter controls with shadcn form/table
   primitives after the base behavior has settled.
5. Do a controlled live Cloudflare Email Sending test before sending to real
   agencies.
6. Keep `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` current in Worker secrets
   if the R2 API token is rotated.
7. Add multipart upload support and per-file retry/remove controls.
8. Investigate the Vinext dev-server 404 and confirm local previews work.
