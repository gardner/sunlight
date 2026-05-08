# Sunlight Requests Implementation Plan

## Goal

Build the first Cloudflare-backed vertical slice for Sunlight Requests:

* D1 stores operational metadata and state.
* R2 stores raw artifacts and uploaded files.
* Vinext apps provide admin, agency-response, and public landing experiences.
* Cloudflare Email Sending and Email Routing handle request email delivery and
  inbound agency replies.

Phase 0 implementation should collect, preserve, and track Sunlight's own
recurring disclosure requests and agency replies. It should not parse or publish
the underlying OIA/LGOIMA material yet.

## Cloudflare Resources

Use these resource names:

* D1 database: `sunlight-requests`
* R2 bucket: `sunlight-request-artifacts`
* admin app domain: `admin.sunlight.nz`
* agency app domain: `requests.sunlight.nz`
* landing app domains: `sunlight.nz`, `www.sunlight.nz`
* inbound reply address format: `reply-{case_token}@sunlight.nz`

Environment values:

* `CLOUDFLARE_ACCOUNT_ID`
* `CLOUDFLARE_ZONE_ID`
* `CLOUDFLARE_API_TOKEN`

Secrets should stay in `.env`, Wrangler secrets, or deployment secret storage.
They must not be committed.

Worker secrets and variables:

* `CF_ACCESS_AUD`: Cloudflare Access audience for `admin.sunlight.nz`.
* `CF_ACCESS_ISSUER`: Cloudflare Access issuer URL.
* `CF_ACCESS_JWKS_URL`: Cloudflare Access JWKS URL.
* `SUNLIGHT_FROM_EMAIL`: optional override for outbound request sender.
  Defaults to `requests@sunlight.nz`.
* `SUNLIGHT_CONTACT_DETAILS`: optional footer/contact text for request
  templates.
* `R2_ACCOUNT_ID`: Cloudflare account id used to build R2 S3 presigned URLs.
* `R2_ACCESS_KEY_ID`: R2 S3 API access key id for presigned uploads.
* `R2_SECRET_ACCESS_KEY`: R2 S3 API secret access key for presigned uploads.
* `R2_BUCKET_NAME`: R2 bucket name. Defaults in agency Wrangler config to
  `sunlight-request-artifacts`.
* `R2_PRESIGN_EXPIRES_SECONDS`: presigned upload URL lifetime. Defaults in
  agency Wrangler config to `900`.

The admin Worker has a Cloudflare Email Sending binding named `EMAIL`. Its
Wrangler config restricts senders to `requests@sunlight.nz`; dynamic reply
addresses are still set through the message `Reply-To` header.

## Repository Layout

Target layout:

```text
apps/
  admin/
  agency/
  landing/
cloudflare/
  migrations/
  seed/
docs/
scripts/
sunlight_requests/
tests/
wrangler.jsonc
```

`apps/admin` owns internal operations.

`apps/agency` owns the tokenized response page at
`https://requests.sunlight.nz/response/{case_token}`.

`apps/landing` owns the public Sunlight landing site.

`cloudflare/migrations` owns D1 migrations shared by the Cloudflare apps.

Each Vinext app is deployed as Workers + Static Assets:

* server bundle: `dist/server/index.js`
* static assets: `dist/client`

Build before deploying, then pass the generated server bundle and assets
directory to Wrangler explicitly. Do not add `main: "dist/server/index.js"` to
the app Wrangler files; Vinext reads Wrangler config during build, and pointing
it at previous `dist` output causes recursive build failures.

```bash
pnpm admin:build
pnpm agency:build
pnpm landing:build
pnpm exec wrangler deploy apps/admin/dist/server/index.js --assets apps/admin/dist/client --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/agency/dist/server/index.js --assets apps/agency/dist/client --config apps/agency/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/index.js --assets apps/landing/dist/client --config apps/landing/wrangler.jsonc
```

Dry-run deployment checks:

```bash
pnpm exec wrangler deploy apps/admin/dist/server/index.js --assets apps/admin/dist/client --dry-run --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/agency/dist/server/index.js --assets apps/agency/dist/client --dry-run --config apps/agency/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
```

## First Milestone

The first implementation milestone is the admin engine foundation.

Status: complete.

Acceptance criteria:

* D1 database exists.
* R2 bucket exists.
* Wrangler config binds D1 and R2.
* Initial D1 migration creates core admin tables.
* Bootstrap admin `sunlight@spunts.net` is seeded as `maintainer`.
* Agency seed import can load FYI authorities without making them sendable.
* Hooks enforce McCabe complexity and max source file length.

Tables in the first migration:

* `admin_users`
* `sunlight_agencies`
* `sunlight_request_templates`
* `sunlight_request_cycles`
* `sunlight_requests`
* `sunlight_outbound_emails`
* `sunlight_responses`
* `sunlight_inbound_emails`
* `sunlight_upload_sessions`
* `sunlight_uploads`
* `sunlight_audit_events`

## Second Milestone

The second milestone is request preparation.

Status: complete.

Acceptance criteria:

* Admin can view agencies.
* Admin can mark an agency contact verified.
* Admin can create a request template.
* Admin can create a monthly request cycle.
* System previews sendable agencies.
* System creates `SunlightRequest` records with:
  * case token hash
  * token hint
  * reply email
  * agency response URL
  * expected due date

No real email needs to be sent in this milestone.

Implemented admin screens:

* `/agencies`
* `/agencies/{agency_id}`
* `/templates`
* `/templates/new`
* `/cycles`
* `/cycles/new`
* `/cycles/{cycle_id}`

Sendability currently requires:

* `sunlight_agencies.status = 'active'`
* `sunlight_agencies.contact_status = 'verified'`
* `sunlight_agencies.primary_request_email IS NOT NULL`
* `sunlight_agencies.default_template_id IS NOT NULL`

Due dates are calculated as 20 working days after preparation, skipping
weekends. Public-holiday support is available in the pure helper, but no
holiday calendar has been loaded yet.

## Third Milestone

The third milestone is outbound email sending.

Status: partially complete.

Acceptance criteria:

* Admin can approve a request cycle.
* System renders outbound email.
* System sends through Cloudflare Email Sending.
* D1 records `sunlight_outbound_emails`.
* Audit events capture queued/sent/failed state.
* Request state moves to `awaiting_response`.

Implemented:

* Cycle approval transition from `previewed` to `approved`.
* Outbound email rendering from request templates.
* Cloudflare Email Sending message construction.
* `sunlight_outbound_emails` queue row creation.
* `EMAIL.send()` integration in the admin Worker.
* Sent/failed status updates for outbound emails.
* Request transition to `awaiting_response` after a successful send.
* Audit events for queued, sent, and failed email states.
* Admin cycle page shows outbound send results and status counts.
* Admin can retry failed outbound emails for a cycle.

Remaining:

* Configure Cloudflare Email Sending domain prerequisites in the dashboard if
  the account still requires them.
* Send a controlled live test to a verified address before sending to agencies.
* Add a controlled live send test before any real agency batch.
* Store provider message IDs if Cloudflare Email Sending exposes them in the
  binding result.

## Fourth Milestone

The fourth milestone is agency response intake.

Status: started.

Acceptance criteria:

* `requests.sunlight.nz/response/{case_token}` returns 404 for invalid tokens.
* Valid tokens show the agency response page.
* Agencies can submit response metadata.
* Agencies can upload files to R2.
* Upload metadata is recorded in D1.
* A `SunlightResponse` record is created or updated.

Implemented:

* Invalid `case_token` returns a 404.
* Valid `case_token` resolves by SHA-256 token hash.
* Valid response page shows agency, cycle period, reply email, and upload
  form.
* Agencies can submit response metadata.
* Upload session route creates D1 upload session and upload rows.
* Upload route returns direct-to-R2 presigned `PUT` URLs.
* Upload completion route verifies the object exists in R2 and marks D1 upload
  state complete.
* R2 bucket CORS allows browser `PUT` uploads from `https://requests.sunlight.nz`.

Remaining:

* Configure `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, and `R2_SECRET_ACCESS_KEY` for
  the deployed agency Worker.
* Run a live browser upload test against a disposable token.
* Add multipart upload support for files that need resumability or exceed the
  single-`PUT` operating limit.
* Add clearer per-file retry/remove controls.

## Fifth Milestone

The fifth milestone is inbound email intake.

Status: not started.

Acceptance criteria:

* Cloudflare Email Routing sends inbound email to a Worker.
* Worker stores raw `.eml` in R2 before downstream work.
* Worker matches email by reply address token.
* Matched email creates `sunlight_inbound_emails` and `sunlight_responses`.
* Unmatched email is preserved and appears in admin triage.

## Implementation Rules

* Use `SunlightRequest` and `SunlightResponse` naming for Sunlight's operational
  workflow.
* Do not create `disclosed_*` records in Phase 0.
* Do not store raw email bodies or file contents in audit events.
* Compute overdue state from request due dates and response state.
* Keep raw artifacts immutable from normal application workflows.
* Use TDD where practical.
* Run shared hooks before committing.

## Verification

Run the core checks after each implementation slice:

```bash
uv run python -m unittest discover -s tests
pnpm test:ts
pnpm exec tsc --noEmit
pnpm admin:build
pnpm agency:build
pnpm landing:build
pnpm exec wrangler deploy apps/admin/dist/server/index.js --assets apps/admin/dist/client --dry-run --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/agency/dist/server/index.js --assets apps/agency/dist/client --dry-run --config apps/agency/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
```

Before committing, install and run the shared hooks:

```bash
uv run pre-commit install
uv run pre-commit run --all-files
```

Do not use `--no-verify` unless the user explicitly confirms it.
