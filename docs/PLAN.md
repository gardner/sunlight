# Sunlight Requests — Detailed Implementation Plan

## Document Purpose

This document translates the Sunlight Requests PRD into a detailed implementation plan. It defines the target architecture, service boundaries, infrastructure, data model, workflows, milestones, backlog structure, operational decisions, and delivery sequence for the MVP and immediate follow-on phases.

This plan reflects a **Cloudflare-native serverless architecture** utilizing Workers, D1, R2, and Email Routing to achieve a highly scalable, low-cost, and maintenance-free operational footprint.

---

# 1. Delivery Goal

Build a production-quality MVP that can:

1. maintain a directory of OIA/LGOIMA authorities
2. send recurring monthly request emails
3. assign unique tokens and URLs to each outgoing request
4. ingest inbound email replies and attachments natively via Cloudflare Email Routing
5. store original inbound artifacts safely and immutably in R2
6. provide a secure upload portal for authorities to submit large responses directly to R2 via multipart upload
7. automatically mitigate unjustified statutory refusals (e.g. s18(d), s18(f))
8. extract text and structured metadata from attachments
9. ingest a mirrored historical corpus of public OIA/LGOIMA request threads
10. provide an internal review workflow
11. publish approved records to a public website (opendata.org.nz / sunlight.nz)
12. provide public search and source-cited chat over the combined corpus

---

# 2. Guiding Technical Decisions

## 2.1 System design principles

The implementation should follow these principles:

* **Raw artifacts are sacred**: never overwrite original inbound email or attached files.
* **Provenance is first-class**: every derived record must be linked back to the original source.
* **Serverless by default**: utilize Cloudflare edge capabilities to eliminate container and database idling costs.
* **Human gate before public publication**: nothing public in MVP should bypass review.
* **Email and mirror ingestion are separate lanes**: they converge downstream but should not share the same early-stage parsing assumptions.
* **Search first, chat second**: public value comes from discoverability and evidence access first; chat sits on top of that.

## 2.2 Recommended stack

### Application layer

* **Next.js / Vinext** for the public website and internal admin/review interface
* **TypeScript** across frontend and backend
* **Cloudflare Workers** for core application API services and background handlers
* **Shadcn UI + Tailwind CSS** for accessible, rapid frontend development

### Ingestion and background processing

* **Cloudflare Email Routing & Email Workers** for inbound email interception and parsing
* **Cloudflare `send_email` binding** for outbound requests
* **Cloudflare Queues** (or direct Worker invocation) for job pipelining between stages
* **Python CLI Scripts** for initial data gathering, scraping, and bulk ingestion tasks

### Storage

* **Cloudflare D1 (SQLite)** for structured metadata and operational state
* **Cloudflare R2** for raw emails, attachments, normalized derivatives, OCR output, and review artifacts
* **Vector Database (TBD)** for semantic search (Cloudflare Vectorize or managed pgvector)

### AI / NLP layer

* **Nvidia NIM & Structured Outputs:** Use `nvidia/nemotron-3-super-120b-a12b` (via free API credits) combined with libraries like `instructor` or `langextract` to conquer messy PDFs and enforce strict structured JSON schema extraction. Data will be ingested slowly in batches to respect the free tier rate limits.
* **Cloudflare Workers AI (LLM / Vision):** `moonshotai/kimi-k2.6` as a fallback or edge-native alternative for vision parsing.
* **Cloudflare Workers AI (Chat / Generation):** `@cf/google/gemma-4-26b-a4b-it` for lightning-fast, source-backed question answering on the public interface.
* **On-Premises Embeddings & Local Store:** Calculate embeddings on an on-prem server to save costs ("scrillah"). Store these initially in a local vector database (like **LanceDB** or **ChromaDB**) for local evaluation, testing, and backup.
* **Cloudflare Vectorize (Edge Store):** Native serverless vector database for edge retrieval. The on-prem pipeline will periodically export new vectors from the local store into NDJSON format and batch-sync them to Vectorize via the Cloudflare REST API.

### Infrastructure and deployment

* `wrangler.jsonc` for declarative infrastructure configuration
* Cloudflare Access (Zero Trust) for securing the Admin UI
* Separate environments handled via Worker environments / preview deployments

---

# 3. Proposed System Architecture

## 3.1 Major bounded services

The MVP is implemented as a modular monorepo containing a set of lightweight Next.js (Vinext) apps and specialized Cloudflare Workers.

### A. Admin App (`apps/admin`)
Secured by Cloudflare Access. Manages the Authority Registry, Request Templates, Cycle Generation, and the Response Review UI. Uses D1 for state.

### B. Authority Portal (`apps/authority`)
A public-facing secure portal where authorities can upload massive response datasets (via multipart chunking) directly to R2, bypassing email size limits.

### C. Inbound Email Worker (`apps/inbound-email`)
A specialized Cloudflare Worker triggered by Email Routing. Parses incoming raw MIME payloads, extracts attachments, saves to R2, identifies the original request via unique `reply-TOKEN`, and drafts automated refusal mitigations.

### D. Public Web Application (`apps/opendata` & `apps/landing`)
Exposes public search, record pages, authority pages, document views, and chat (sunlight.nz / opendata.org.nz). Content pages powered by edge-rendered Markdown.

### E. Parsing and Enrichment Pipeline (Future Phase)
Uses Cloudflare Workers AI Vision/LLM models (`moonshotai/kimi-k2.6`) to extract text and structured metadata directly from email bodies and PDFs. Generates searchable chunks and embeddings using `@cf/qwen/qwen3-embedding-0.6b` and stores them in Cloudflare Vectorize.

### F. Mirror Import Pipeline (Future Phase)
Imports mirrored HTML pages and attachments from the historical corpus (e.g., FYI.org.nz), reconstructs threads, and emits normalized records.

---

# 4. Repository and Codebase Layout

Monorepo structure utilizing `pnpm workspaces`:

```text
/apps
  /admin                 # Internal review and management UI (Vinext/Next.js)
  /authority             # Secure portal for agencies to upload responses (Vinext/Next.js)
  /opendata              # Public site for Open Data Limited (Vinext/Next.js)
  /landing               # Original/alternative landing app
  /inbound-email         # Cloudflare Worker for processing inbound mail
/cloudflare
  /migrations            # D1 SQLite migrations
/scripts                 # Python tools for data seeding, scraping, and one-off tasks
/docs                    # Architecture, runbooks, schemas, decisions
/tests                   # Unit and integration tests (Vitest / Python unittest)
```

---

# 5. Core Data Model

## 5.1 Primary tables (Operational / Sunlight Workflow)

### sunlight_authorities
Stores every local authority or covered body.
Fields: `id`, `name`, `slug`, `legal_regime`, `primary_request_email`, `contact_status`, `status`, `default_template_id`, `default_cadence`, `created_at`, `updated_at`.

### sunlight_request_cycles
Represents a generated monthly request batch.
Fields: `id`, `cycle_year`, `cycle_month`, `covered_from`, `covered_until`, `status`, `approved_at`, `created_at`, `updated_at`.

### sunlight_requests
Represents an outbound request to a specific authority in a cycle.
Fields: `id`, `authority_id`, `cycle_id`, `template_id`, `status`, `case_token_hash`, `case_token_hint`, `reply_email`, `expected_due_at`, `last_response_at`, `closed_at`, `created_at`, `updated_at`.

### sunlight_responses
Represents a response (email or portal upload) from an authority.
Fields: `id`, `sunlight_request_id`, `authority_id`, `channel` (email/portal), `category`, `status`, `received_at`, `submitter_email`, `notes`.

### sunlight_inbound_emails
Represents one inbound raw email intercepted by the worker.
Fields: `id`, `sunlight_request_id`, `sunlight_response_id`, `provider`, `raw_r2_bucket`, `raw_r2_key`, `from_email`, `to_emails_json`, `subject`, `message_id_header`, `in_reply_to_header`, `association_status`, `status`, `received_at`.

### sunlight_inbound_attachments
Represents files extracted from inbound emails.
Fields: `id`, `inbound_email_id`, `sunlight_request_id`, `filename`, `content_type`, `size_bytes`, `r2_bucket`, `r2_key`, `status`, `created_at`.

### sunlight_uploads & sunlight_upload_sessions
Tracks files uploaded directly to R2 by authorities via the secure portal.
Fields: `id`, `sunlight_request_id`, `upload_session_id`, `original_filename`, `safe_filename`, `content_type`, `size_bytes`, `r2_bucket`, `r2_key`, `status`.

### sunlight_refusal_mitigations
Automated drafted responses to unjustified statutory refusals.
Fields: `id`, `sunlight_request_id`, `sunlight_response_id`, `refusal_reason`, `status`, `drafted_response`, `created_at`, `updated_at`.

## 5.2 Corpus tables (Future Phase - Public Records)
* `disclosed_requests`, `disclosed_responses`, `disclosed_documents`, `document_chunks`, `extracted_metadata`

---

# 6. Cloudflare Infrastructure Plan

## 6.1 Email setup
### Outbound
* Handled by Cloudflare Workers `send_email` binding.
* SPF, DKIM, and DMARC configured on `sunlight.nz` to exit the Cloudflare sandbox for production sending.
* Sender address (`requests@sunlight.nz`) explicitly verified in the Cloudflare dashboard.

### Inbound
* Cloudflare Email Routing configured to catch `*@sunlight.nz`.
* Routes directly to the `inbound-email` Worker.

## 6.2 Storage & Databases
* **R2 Bucket:** `sunlight-request-artifacts` (stores raw `.eml` files and uploaded attachments).
* **D1 Database:** `sunlight-requests` (SQLite).

## 6.3 Security
* Admin app protected by Cloudflare Access (Zero Trust) with One-Time PIN.
* Only explicitly allowed emails (e.g., `sunlight@spunts.net`) can log in.
* App-level JWT verification helper explicitly re-verifies the Access token.

---

# 7. Dev Milestones and Phases

## Phase 0 — Foundation Setup ✅ (Completed)
* Monorepo initialized (`pnpm`, `vinext`).
* Cloudflare D1 and R2 provisioned.
* Admin app scaffolding and D1 schema defined.
* Cloudflare Access (Zero Trust) configured for `admin.sunlight.nz`.
* Python web scraper built to discover authority contact emails.

## Phase 1 — Authority Registry and Outbound Requests ✅ (Completed)
* Scraped, seeded, and verified 1,300+ authority email addresses.
* Built Admin UI for Authority management and Contact verification.
* Built Request Templates and Cycle Generation workflows.
* Implemented outbound Cloudflare Email Sending.
* Configured automated tracking of OIA due dates.

## Phase 2 — Inbound Responses & Refusal Mitigation ✅ (Completed)
* Built `requests.sunlight.nz` Authority Portal for direct R2 multipart file uploads.
* Configured Cloudflare Email Routing to catch authority replies.
* Wrote `inbound-email` Worker to parse MIME, extract attachments to R2, and map to D1 requests.
* Implemented Automated Refusal Mitigation engine (detects s18d/s18f refusals and drafts Ombudsman-compliant counter-arguments).
* Built Admin UI for reviewing inbound email threads and managing mitigations.

## Phase 3 — Classification and Parsing (Next Up)
* Build a worker to normalize extracted files (PDF, DOCX, XLSX).
* Implement PDF parsing and structured extraction utilizing Cloudflare Workers AI Vision models (e.g., `moonshotai/kimi-k2.6`) or Nvidia NIM endpoints (e.g., `nvidia/nemotron-3-super-120b-a12b`).
* Use structured output libraries like `instructor` or `langextract` to strictly constrain JSON schema generation from complex or messy documents.
* Build Cloudflare Queues for processing heavy OCR/parsing jobs asynchronously.

## Phase 4 — Internal Review Workflow
* Build Admin UI pages for inspecting parsed documents.
* Implement reviewer editing tools and approval/reject workflows.
* Add publication state machine.

## Phase 5 — Mirror Corpus Import
* Build parser for historical OIA threads (e.g., FYI.org.nz exports).
* Ingest attachments and normalize legacy authorities.
* Run batch extraction and indexing over historical data.

## Phase 6 — Public Search and Record Pages
* Implement full-text and metadata queries over approved records.
* Build public UI (`opendata.org.nz`) for browsing responses and documents.
* Add provenance labels and citations.

## Phase 7 — Chat / RAG Interface
* Provision Cloudflare Vectorize database.
* Implement vector embedding pipeline using `@cf/qwen/qwen3-embedding-0.6b`.
* Build source-backed answer generation using `@cf/google/gemma-4-26b-a4b-it`.
* Add chat UI to the public site (`opendata.org.nz`).

---

# 8. Definition of Done for MVP

The MVP is complete when:
* A configured set of authorities can receive automated request emails.
* Replies and portal uploads can be ingested automatically.
* Raw emails and attachments are preserved immutably in R2.
* Replies can be associated to request cycles correctly.
* Documents can be parsed and indexed.
* A mirrored corpus can be imported into the same archive.
* Internal reviewers can inspect and approve records.
* Approved records can be published publicly.
* The public can search across the combined corpus.
* The public can ask source-cited questions over the corpus.
lished publicly.
* The public can search across the combined corpus.
* The public can ask source-cited questions over the corpus.
