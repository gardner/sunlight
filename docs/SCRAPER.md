# Authority Contact Scraper

## Purpose

Sunlight needs public submission email addresses for authorities so it can send
`SunlightRequest` emails asking for OIA/LGOIMA request and response material.

The FYI authority import gives us authority identity, source URLs, home pages, and
legal-regime hints. It does not provide reliable public request-intake email
addresses. Most imported authorities therefore start with:

* `primary_request_email = null`
* `secondary_request_emails_json = []`
* `contact_status = missing`

The scraper should discover candidate public-information email addresses, but it
must not automatically mark them verified. Sending requests to the wrong address
has legal and operational consequences, so scraped contacts should enter an
admin review queue.

## Outcome

For each authority, the scraper should produce:

* candidate email addresses
* evidence URLs where each candidate appeared
* evidence text snippets where useful
* confidence score and reason
* scrape status and last checked time
* enough metadata for an operator to approve or reject the contact

After review, an operator can set:

* `sunlight_authorities.primary_request_email`
* `sunlight_authorities.secondary_request_emails_json`
* `sunlight_authorities.contact_status = verified`

## Source Priority

Scraping should prefer official sources over aggregators.

Priority order:

1. Authority home page from FYI metadata.
2. Authority contact page linked from the home page.
3. Authority OIA, LGOIMA, official information, privacy, or information request
   pages linked from the home page.
4. FYI authority page as supporting evidence.
5. Search-engine result pages only if explicitly enabled later.

Do not treat random third-party directories as authoritative.

## Candidate Signals

High-confidence page terms:

* `official information`
* `OIA`
* `LGOIMA`
* `Local Government Official Information`
* `request information`
* `information request`
* `privacy`
* `contact us`
* `make a request`

High-confidence email local parts:

* `oia`
* `officialinformation`
* `official.information`
* `information`
* `informationrequests`
* `information.requests`
* `lgoinfo`
* `lgoima`
* `privacy`
* `requests`

Medium-confidence local parts:

* `info`
* `enquiries`
* `contact`
* `admin`
* `records`

Low-confidence or usually wrong:

* personal staff addresses
* media-only addresses
* recruitment addresses
* procurement addresses
* webmaster addresses
* no-reply addresses
* bounce addresses

## Data Model

Add a candidate table rather than immediately mutating the authority contact field.

Recommended table: `sunlight_authority_contact_candidates`

Fields:

* `id`
* `authority_id`
* `email`
* `normalized_email`
* `source_url`
* `source_page_title`
* `source_snippet`
* `discovery_method`: `homepage`, `linked_page`, `fyi_page`, or later `search`
* `confidence`: integer 0-100
* `confidence_reason`
* `status`: `candidate`, `accepted`, `rejected`, `stale`
* `first_seen_at`
* `last_seen_at`
* `created_at`
* `updated_at`

Indexes:

* `(authority_id, status, confidence)`
* `(normalized_email)`
* `(source_url)`

The scraper may also update `sunlight_authorities.contact_status` from `missing` to
`needs_review` when at least one candidate is found. It must not overwrite
`contact_status = verified`.

Candidate metadata can also be mirrored into `source_metadata_json`, but the
candidate table should be the primary review surface.

## Scraper Architecture

Use Python and `curl_cffi` for fetching.

Why `curl_cffi`:

* better browser-like TLS behavior than basic urllib/requests
* useful for government CMS pages and bot-sensitive front ends
* still simple enough for a batch scraper

Suggested dependencies:

```bash
uv add curl_cffi beautifulsoup4
```

Use standard library modules for URL handling, email parsing, JSON, SQLite/D1 SQL
generation, and concurrency where possible.

## Fetching Strategy

For each authority:

1. Read authority rows where:
   * `status = active`
   * `contact_status IN ('missing', 'needs_review', 'invalid')`
   * optional `--authority-id` or `--limit` filter
2. Extract home page from `source_metadata_json.home_page`.
3. Fetch the home page.
4. Extract:
   * `mailto:` links
   * visible email addresses
   * page title
   * internal links likely to contain contact or OIA details
5. Fetch a small number of high-value internal links.
6. Score all discovered candidate emails.
7. Emit SQL upserts for candidate rows.
8. Mark authority `needs_review` if candidates exist and the authority is not already
   `verified`.

Recommended limits:

* default authorities per run: 50
* max pages per authority: 8
* request timeout: 20 seconds
* delay between authorities: configurable, default 250-500 ms
* skip files such as PDF, DOCX, images, archives, and videos

## URL Selection

Only crawl same-site links by default.

Follow links where the link text or URL contains:

* `contact`
* `contacts`
* `official-information`
* `official_information`
* `information-request`
* `information-requests`
* `oia`
* `lgoima`
* `privacy`
* `about`

Avoid links containing:

* `facebook`
* `linkedin`
* `twitter`
* `x.com`
* `instagram`
* `youtube`
* `rss`
* `login`
* `careers`
* `jobs`
* `procurement`
* `tenders`

## Email Extraction

Extract from:

* `mailto:` links
* visible text
* lightly obfuscated text such as `name [at] authority.govt.nz`

Normalize by:

* lowercasing
* stripping `mailto:`
* removing query strings
* trimming punctuation
* IDNA-normalizing domains where needed

Reject:

* invalid syntax
* domains without a dot
* `example.*`
* `noreply`, `no-reply`, `donotreply`

## Scoring

Score should be deterministic and explainable.

Suggested scoring:

* +35 email local part strongly matches OIA/LGOIMA/request terms
* +20 source URL contains OIA/LGOIMA/official-information terms
* +15 page title or nearby text contains OIA/LGOIMA/request terms
* +10 domain appears to match authority home-page domain
* +5 source is authority home page or linked page
* -30 local part looks personal
* -25 local part is media/recruitment/procurement/webmaster
* -40 no-reply style address

Suggested thresholds:

* `80+`: strong candidate
* `50-79`: review candidate
* `<50`: keep only if no better candidates found, or drop by default

## CLI Shape

Recommended script:

```bash
uv run python scripts/scrape_authority_contacts.py --database sunlight-requests --remote --limit 50
```

Useful options:

* `--authority-id agy_fyi_example`
* `--source-file path/to/authorities.json`
* `--limit 50`
* `--max-pages-per-authority 8`
* `--write-sql out.sql`
* `--remote`
* `--dry-run`
* `--min-confidence 50`
* `--timeout 20`
* `--delay-ms 500`

For safety, default to `--dry-run` unless `--write-sql` or `--remote` is
provided.

## D1 Application Strategy

The scraper should generate SQL and apply it through Wrangler, matching the
existing FYI import workflow.

Remote example:

```bash
uv run python scripts/scrape_authority_contacts.py --remote --limit 50
```

Generated SQL should:

* upsert candidates by `(authority_id, normalized_email, source_url)`
* update `last_seen_at` when seen again
* preserve accepted/rejected status where possible
* set authority `contact_status = needs_review` only when current status is
  `missing` or `invalid`
* never change `primary_request_email` directly
* never downgrade `verified`

## Admin Review Workflow

Admin should support:

* filter authorities by `contact_status = needs_review`
* show candidate emails on authority detail page
* show evidence URL and confidence reason
* accept a candidate as primary
* accept additional candidates as secondary
* reject candidate
* mark authority contact invalid if no correct address exists

Accepting a candidate should:

* set `primary_request_email`
* set `contact_status = verified`
* mark that candidate `accepted`
* audit the event

Rejecting a candidate should:

* mark candidate `rejected`
* preserve the evidence for future debugging

## Safety Rules

The scraper must:

* respect reasonable rate limits
* use a clear User-Agent identifying Sunlight
* avoid deep crawling
* avoid scraping private portals or login pages
* avoid storing full page bodies in D1
* store only short snippets and evidence URLs
* never auto-send requests based on scraped candidates
* never overwrite verified operator decisions

## First Implementation Slice

1. Add `curl_cffi` and `beautifulsoup4`.
2. Add D1 migration for `sunlight_authority_contact_candidates`.
3. Add pure Python extraction/scoring helpers with unit tests.
4. Add scraper CLI with `--write-sql` and `--dry-run`.
5. Test against 5-10 known authorities.
6. Apply a small remote scrape batch.
7. Add admin candidate review UI on authority detail pages.
8. Only then allow operators to verify contacts for sending.
