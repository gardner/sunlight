# Progress

## Current Slice

The request preparation slice is complete and the outbound email slice is
implemented through dry-run deployment validation.

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
* Validated all three Vinext apps for Workers + Static Assets dry-run
  deployment.

## Verification

Last verified with:

```bash
uv run pre-commit run --files $(git ls-files --others --exclude-standard)
uv run python -m unittest discover -s tests
pnpm test:ts
pnpm exec tsc --noEmit
pnpm admin:build
pnpm agency:build
pnpm landing:build
pnpm exec wrangler deploy apps/admin/dist/server/index.js --assets apps/admin/dist/client --dry-run --config apps/admin/wrangler.jsonc
pnpm exec wrangler deploy apps/agency/dist/server/index.js --assets apps/agency/dist/client --dry-run --config apps/agency/wrangler.jsonc
pnpm exec wrangler deploy apps/landing/dist/server/index.js --assets apps/landing/dist/client --dry-run --config apps/landing/wrangler.jsonc
pnpm dlx wrangler@latest d1 execute sunlight-requests --remote --command "SELECT COUNT(*) AS total, SUM(contact_status = 'verified') AS verified, SUM(status = 'inactive') AS inactive FROM sunlight_agencies;"
```

## Notes

Cloudflare resources:

* D1 database: `sunlight-requests`
* D1 database id: `796835ba-d5e5-4ad2-a931-bdf7b3a2b7dc`
* R2 bucket: `sunlight-request-artifacts`
* FYI authorities imported: 3,177
* Verified agency contacts: 0
* Inactive imported agencies: 238

Known issue:

* `vinext build` succeeds for all three apps, but `vinext dev` currently returns
  404 for `/`. Investigate Vinext dev-server routing before relying on local
  browser previews.

Important naming boundary:

* `SunlightRequest` and `sunlight_*` tables represent Sunlight's own recurring
  disclosure collection workflow.
* `DisclosedRequest`, `DisclosedResponse`, and future `disclosed_*` tables are
  reserved for later extraction of underlying OIA/LGOIMA material.

## Next Steps

1. Configure Cloudflare Access for `admin.sunlight.nz` and add the Access
   issuer/audience values as Worker secrets.
2. Do a controlled live Cloudflare Email Sending test before sending to real
   agencies.
3. Configure R2 S3 API credentials for the agency Worker and run a live upload
   test against a disposable token.
4. Add multipart upload support and per-file retry/remove controls.
5. Investigate the Vinext dev-server 404 and confirm local previews work.
