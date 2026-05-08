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

1. Wire admin pages/actions through the existing Cloudflare Access JWT validator
   so D1 admin roles are enforced inside the app as well as at the edge.
2. Continue moving admin pages from legacy CSS classes to shadcn-style local
   components.
3. Consider replacing the agencies table/filter controls with shadcn form/table
   primitives after the base behavior has settled.
4. Do a controlled live Cloudflare Email Sending test before sending to real
   agencies.
5. Keep `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY` current in Worker secrets
   if the R2 API token is rotated.
6. Add multipart upload support and per-file retry/remove controls.
7. Investigate the Vinext dev-server 404 and confirm local previews work.
8. Generate two landing page design directions from `docs/WEB.md`, then select
   the implementation direction for the Vinext landing app.
