# Agency Response App

## Purpose

The agency response app at
`https://requests.sunlight.nz/response/{case_token}` gives an agency a simple
way to respond to a specific `SunlightRequest`.

It exists because email has practical limits. Agencies can still reply by email,
but if files are too large or awkward to send, they can upload them through this
tokenized page.

This app is not a public portal. It is not an OIA request submission form. It is
not a place for members of the public to make requests.

## Naming

The page should consistently describe the workflow as Sunlight's recurring
disclosure request.

Use these terms in code and copy:

* `SunlightRequest`: the request Sunlight sent to the agency.
* `SunlightResponse`: the agency's response to Sunlight.
* `DisclosedRequest`: an OIA/LGOIMA request that the agency is disclosing.
* `DisclosedResponse`: the agency's response to that disclosed OIA/LGOIMA
  request.

Avoid generic names like `Request` and `Response` in this app's domain code
unless they refer only to HTTP request/response objects.

## Route Behavior

Route:

`/response/{case_token}`

Behavior:

* If `case_token` exists and is active, show the response page.
* If `case_token` does not exist, show a 404 page.
* If `case_token` exists but is closed, show a closed-state page with contact
  details.
* If `case_token` exists but is held or disabled, show a contact-support state.

The token is the only access control for this page. Tokens must be long,
unguessable, and unique.

Recommended token shape:

* at least 128 bits of entropy
* URL-safe
* no embedded agency name or cycle date
* stored hashed in D1 if practical

Example URL:

`https://requests.sunlight.nz/response/a-long-random-case-token`

## Page Goals

The page should let an agency:

* confirm which Sunlight request they are responding to
* see the request month/date range
* see the agency name on record
* see the reply email address
* upload large response files
* add optional notes
* submit a response without creating an account
* see a clear confirmation after upload

The page should avoid legal complexity and avoid presenting itself as a public
records publishing interface.

## Primary Screen

For a valid active token, show:

* Sunlight branding
* agency name
* request cycle/month
* covered date range
* short summary of what Sunlight requested
* reply email address
* upload control
* optional agency reference field
* optional contact name
* optional contact email
* optional notes
* submit button

The copy should make clear that Sunlight is requesting copies of the agency's
OIA/LGOIMA requests and responses for the covered period.

The upload UI should support:

* drag-and-drop
* file picker
* multiple files
* per-file upload progress
* retry failed upload
* remove file before final submit
* visible uploaded/failed state

## Upload Flow

The app should use direct-to-R2 upload sessions.

Recommended flow:

1. Agency opens tokenized page.
2. Worker validates `case_token` in D1.
3. Agency selects files.
4. App requests an upload session from the Worker.
5. Worker creates an upload record in D1.
6. Worker returns upload instructions.
7. Browser uploads file directly to R2.
8. Worker marks upload complete after browser confirmation or R2 callback/poll.
9. Agency submits final response notes.
10. Worker creates or updates the `SunlightResponse` record.
11. App shows confirmation.

For very large files, implement multipart upload rather than a single `PUT`.

Phase 0 implementation currently supports direct single-`PUT` presigned uploads.
The Worker creates D1 `sunlight_upload_sessions` and `sunlight_uploads` rows,
returns a presigned R2 URL, and marks the upload complete after the browser
confirms and the Worker can `head()` the R2 object. Multipart upload support is
reserved for the next upload hardening slice.

Required deployed Worker configuration:

* `R2_ACCOUNT_ID`
* `R2_ACCESS_KEY_ID`
* `R2_SECRET_ACCESS_KEY`
* `R2_BUCKET_NAME`
* `R2_PRESIGN_EXPIRES_SECONDS`

The R2 bucket must also allow CORS from `https://requests.sunlight.nz` for
browser `PUT` uploads with the `Content-Type` header.

## Accepted Files

Phase 0 should accept common response material:

* PDF
* DOCX
* TXT
* CSV
* XLSX
* ZIP
* common image formats

The upload page should not promise parsing support. It should only promise that
Sunlight can receive the material.

The app should record but not necessarily block:

* unknown MIME types
* oversized files
* empty files
* duplicate filenames
* suspicious extensions

Blocking should be limited to clear operational risks, such as files larger than
the current configured limit.

## D1 Records

The agency app needs D1 access to:

* look up active `SunlightRequest` records by token
* create upload sessions
* record uploaded files
* create/update `SunlightResponse` records
* record audit events

Minimum `SunlightRequest` fields required by this app:

* id
* case token hash or lookup token
* agency id
* agency display name
* cycle month
* covered date range
* reply email address
* status
* expected due date
* closed timestamp

Minimum upload fields:

* upload id
* request id
* response id where known
* R2 bucket
* R2 object key
* original filename
* content type
* size bytes
* status
* created timestamp
* completed timestamp

## R2 Object Layout

Use deterministic prefixes that keep artifacts grouped by `SunlightRequest`.

Recommended layout:

```text
sunlight-requests/{request_id}/uploads/{upload_id}/{safe_filename}
sunlight-requests/{request_id}/inbound-email/{message_id}/raw.eml
sunlight-requests/{request_id}/inbound-email/{message_id}/attachments/{attachment_id}/{safe_filename}
```

Object keys should not depend on original filenames alone. Include stable IDs to
avoid collisions and to support repeated uploads with the same filename.

## Response Completion

Uploading files should not automatically mean the response is complete unless
the agency clicks a final submit button or the upload flow is explicitly
single-step.

Recommended final submit options:

* `This is our complete response`
* `This is a partial response`
* `No records held`
* `We will respond separately by email`

These map to initial `SunlightResponse` categories but remain operator
correctable in the admin app.

## Email Alternative

Every page should show the reply email address for the case:

`reply-{case_token}@sunlight.nz`

Because Cloudflare reports subaddressing support as disabled, the system should
use unique local-part addresses rather than plus aliases.

The outbound email should include both the reply email address and this response
URL.

## Error States

Required error states:

* unknown token: 404
* closed request
* upload too large
* upload failed
* unsupported browser upload state
* temporary service error

Unknown token pages should not reveal whether the token was almost valid, expired,
or associated with another agency.

## Security And Abuse Controls

The page has no login, so controls must be token and abuse oriented:

* long random tokens
* optional token hashing in D1
* upload size limits
* per-token upload quotas
* per-IP rate limits where available
* file count limits
* R2 object key isolation by request id
* no public listing of uploaded files
* no public download links

Phase 0 should prioritize preserving submitted material, but the admin app should
clearly mark material that needs safety review before local processing.

## Non-Goals

The agency app does not:

* authenticate agency staff
* allow public request submission
* publish uploaded files
* parse uploaded documents
* expose previous responses to the public
* replace email as a response path
* make legal or redaction decisions
