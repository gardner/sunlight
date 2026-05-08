# Sunlight Requests - Phase 0 PRD

## Product Name

**Sunlight Requests**

## Parent Initiative

**Sunlight Project**

## Version

Phase 0 Draft

## Status

Working draft

## Document Owner

Sunlight Project

## 1. Executive Summary

Sunlight Requests is the first-party request and response collection engine for
Sunlight NZ.

Phase 0 focuses only on the operational core: sending recurring OIA/LGOIMA
requests to authorities, receiving responses by email, associating those responses
with the correct outgoing request, extracting usable text and metadata, and
storing the resulting records safely with clear provenance.

The product is not a public search site, chat interface, historical archive
importer, analytics platform, or general-purpose public OIA portal in this
phase. Those can be built later on top of a reliable request/response engine.

## 2. Problem Statement

Official information responses in New Zealand are distributed across many
authorities, formats, inboxes, websites, and release practices. Authorities may
disclose responses voluntarily, but there is no simple shared intake path that
makes recurring disclosure easy to operate, easy to audit, and easy to reuse.

Sunlight needs a durable collection system that can:

* maintain a directory of authorities and request contacts
* send recurring requests at a predictable cadence
* receive and preserve authority replies
* keep replies tied to the correct outgoing request
* process attachments and message bodies into structured records
* store raw and parsed material for later review, publication, search, or other
  downstream products

## 3. Vision

Sunlight Requests should become dependable infrastructure for collecting
voluntarily disclosed OIA/LGOIMA response material from authorities.

The Phase 0 system should make the monthly request workflow boring, auditable,
and repeatable. Later Sunlight products can use the stored data, but Phase 0 is
successful when the request/response engine itself works reliably.

## 4. Phase 0 Goal

Build a system that:

* manages an authority directory and request templates
* sends recurring OIA/LGOIMA disclosure requests to selected authorities
* generates a unique reply alias for each outgoing request
* receives inbound email responses automatically
* stores raw email, headers, bodies, and attachments immutably
* associates inbound messages with the correct request case
* classifies inbound messages into operational response categories
* extracts text from email bodies and supported attachments
* stores parsed text, metadata, files, and processing status
* exposes an internal operator interface or API for monitoring and correction

## 5. Non-Goals for Phase 0

Phase 0 will not aim to:

* import historical datasets from FYI.org.nz or other public archives
* build public search, public browse, or public record pages
* build a public chat or RAG interface
* support arbitrary public user-submitted OIA requests
* publish records automatically
* make final legal or redaction decisions automatically
* build authority compliance analytics
* build alerts, subscriptions, dashboards for the public, or an external API
* ingest broad public-record sources such as court decisions, Hansard, gazette
  notices, regulator publications, or authority release logs
* provide collaborative investigation tooling

## 6. Target Users

### Primary Users

* Sunlight operators maintaining the authority directory and request cycles
* Sunlight reviewers inspecting inbound responses and processing failures
* technical maintainers monitoring mail, parsing, storage, and job health

### Secondary Users

* authority staff responding to recurring disclosure requests by email
* future Sunlight products that consume the stored request/response records

## 7. User Needs

### Operators Need To:

* manage authorities, contacts, legal regimes, and active/inactive status
* configure request templates and monthly cycles
* see which authorities are due, sent, replied, overdue, or failed
* inspect all outbound request records and inbound response records
* correct metadata and association mistakes
* retry failed sends or processing jobs

### Reviewers Need To:

* inspect raw inbound material and extracted text
* see classification, parsing, and metadata extraction results
* identify suspicious files, unsupported files, and low-confidence parsing
* mark records as ready for later review, held, rejected, duplicate, or needing
  follow-up

### Technical Maintainers Need To:

* audit mail delivery and receipt
* diagnose parsing and storage failures
* verify that raw material is preserved before downstream processing
* reprocess older records when parsers improve

## 8. Product Principles

1. **Collection first**
   Phase 0 optimizes for reliable collection and preservation, not public
   presentation.

2. **Provenance first**
   Every stored response must trace back to an outbound request, inbound email,
   authority, timestamp, and original artifact where possible.

3. **Safe by default**
   No unreviewed first-party material is automatically published.

4. **Operator-correctable**
   Automation should handle the common path, but operators must be able to fix
   association, classification, parsing, and metadata errors.

5. **Simple interfaces**
   Authorities should only need to reply by email. The system should not require
   authorities to learn a portal in Phase 0.

6. **Downstream-ready storage**
   Store raw and parsed data in a way that future publication, search, analytics,
   or disclosure products can build on without re-collecting the source material.

## 9. Product Scope

### In Scope for Phase 0

* authority directory
* request template management
* monthly request scheduling
* outbound email generation and delivery tracking
* unique reply alias per outgoing request
* inbound email ingestion
* raw email and attachment storage
* basic safety scanning and file validation
* inbound association with request cases
* response classification
* attachment parsing and OCR where feasible
* structured metadata extraction
* processing status and error tracking
* internal operator dashboard or API
* durable audit log for sends, receives, processing, and manual corrections

### Out of Scope for Phase 0

* FYI.org.nz import
* public website
* public search
* public chat
* public API
* broad public-record ingestion
* automatic publication
* compliance scoring
* public request submission

## 10. Core Product Features

### 10.1 Authority Directory

The system maintains a directory of authorities and local authorities, including:

* organization name
* legal regime: OIA, LGOIMA, or other
* primary request email address
* optional secondary contact email addresses
* active/inactive status
* request template assignment
* notes for operators

### 10.2 Request Templates

Operators can maintain reusable email templates for recurring disclosure
requests.

Templates should support variables such as:

* authority name
* request month
* date range covered
* reply instructions
* Sunlight contact details

### 10.3 Monthly Request Scheduling

The system selects authorities due for a request cycle and creates outbound request
records for the relevant month.

The scheduler should support:

* monthly cadence by default
* manual inclusion/exclusion of authorities
* dry-run previews before sending
* operator approval before a batch is sent
* retry of failed sends

### 10.4 Outbound Email Delivery

The system sends recurring OIA/LGOIMA disclosure request emails to authorities and
records:

* generated subject and body
* recipient addresses
* sender address
* unique reply alias
* send provider message id
* send timestamp
* send status
* delivery or bounce events where available

### 10.5 Unique Reply Alias

Each outgoing request receives a unique reply address or alias tied to the
request record. Incoming email to that alias is automatically associated with
the request case.

Thread metadata and headers may be used as supporting evidence, but the unique
alias is the primary association mechanism.

### 10.6 Inbound Email Intake

The system receives authority replies by email and stores:

* raw message
* envelope sender and recipients
* headers
* subject
* text body
* HTML body where present
* attachments
* receive timestamp
* mail provider event metadata

### 10.7 Raw Artifact Storage

Raw emails and attachments are preserved before parsing. Storage should be
append-only from the perspective of normal application workflows.

Every parsed record should retain a pointer to the original artifact.

### 10.8 Safety Scanning

Inbound email and attachments are checked before processing.

The system should detect and record:

* unsupported file types
* suspicious file names or MIME types
* malware scan status where integrated
* oversized files
* encrypted or password-protected files
* parser failures

Suspicious or unsupported material should be held for manual review rather than
silently discarded.

### 10.9 Response Classification

The system classifies inbound messages into operational categories such as:

* acknowledgement
* clarification request
* extension notice
* transfer notice
* refusal
* partial response
* full response
* no records held
* follow-up correspondence
* bounce or delivery failure
* unrelated or unknown

Classification results should include confidence and be operator-correctable.

### 10.10 Document Parsing and Text Extraction

The system extracts text from supported message bodies and attachments,
including:

* PDF
* scanned PDF where OCR is available
* DOCX
* plain text
* CSV
* common image formats where OCR is available

Parsing should preserve per-document status and errors so failed files do not
block the entire request case.

### 10.11 Metadata Extraction

The system extracts and stores structured metadata where feasible:

* authority
* request month covered
* response date
* authority reference number
* response category
* withholding grounds cited
* attachment count
* document titles
* suggested response title
* short operator-facing summary

Extracted metadata should include extraction method, confidence where relevant,
and manual override support.

### 10.12 Case Tracking

Each monthly request to an authority is tracked as a case with statuses such as:

* draft
* scheduled
* sent
* delivered
* bounced
* acknowledged
* awaiting_response
* response_received
* partially_processed
* processed
* held
* failed
* closed

The system should record expected due dates and overdue status.

### 10.13 Operator Review State

Phase 0 stores review state for future workflows, but does not need to publish
records.

Review states may include:

* unreviewed
* processing_failed
* needs_operator_attention
* ready_for_publication_review
* held
* rejected
* duplicate

### 10.14 Audit Log

The system records an audit trail for:

* request creation
* batch approval
* email send attempt
* email delivery or bounce event
* inbound message receipt
* association decisions
* classification decisions
* parsing attempts
* metadata extraction attempts
* manual corrections
* status changes

## 11. Functional Requirements

### 11.1 Authorities

The system shall maintain an authority directory with request contact details,
legal regime, template assignment, and active status.

### 11.2 Request Cycles

The system shall create monthly request cycles and select eligible authorities.

### 11.3 Outbound Requests

The system shall create one outbound request case per authority per cycle unless an
operator excludes that authority.

### 11.4 Email Aliases

The system shall generate a unique reply alias for each outbound request case.

### 11.5 Sending

The system shall send outbound request emails and record send status, provider
ids, timestamps, and failures.

### 11.6 Inbound Storage

The system shall store raw inbound email and attachments before parsing.

### 11.7 Inbound Association

The system shall associate inbound messages with request cases using the unique
reply alias and supporting email metadata.

### 11.8 Classification

The system shall classify inbound messages into response categories and allow
operator correction.

### 11.9 Parsing

The system shall extract text from supported email and attachment formats and
record per-document parsing status.

### 11.10 Metadata

The system shall persist structured metadata extracted from messages and
attachments.

### 11.11 Status Tracking

The system shall track request case, message, document, parsing, and extraction
statuses.

### 11.12 Internal Operations

The system shall expose internal views or APIs for monitoring, correcting,
retrying, and auditing the request/response workflow.

### 11.13 Publication Boundary

The system shall not expose first-party response material publicly in Phase 0.

## 12. Core Workflows

### 12.1 Monthly Outbound Request Workflow

1. Operator creates or opens the monthly request cycle.
2. Scheduler selects active authorities due for the cycle.
3. Operator previews the batch.
4. Operator approves the batch.
5. System creates request cases and unique reply aliases.
6. System renders email templates.
7. System sends request emails.
8. System records send status and expected due dates.

### 12.2 Inbound Response Workflow

1. Authority replies by email.
2. Mail provider receives the message.
3. System stores the raw email and attachments.
4. System associates the message with the correct request case.
5. Safety scanning and file validation run.
6. Message is classified.
7. Attachments and bodies are parsed.
8. Metadata is extracted.
9. Request case status is updated.
10. Operator attention is requested if confidence is low or processing fails.

### 12.3 Manual Correction Workflow

1. Operator opens a case requiring attention.
2. Operator inspects raw email, attachments, parsed text, and metadata.
3. Operator corrects association, classification, metadata, or status.
4. System records the correction in the audit log.
5. Operator retries processing if needed.

### 12.4 Reprocessing Workflow

1. Maintainer deploys improved parser or extractor.
2. Operator selects cases, messages, or documents for reprocessing.
3. System reruns parsing or metadata extraction.
4. System preserves previous raw artifacts and records new processing results.
5. System updates statuses and audit logs.

## 13. Conceptual Data Model

### Authority

Represents a public-sector organization that can receive recurring requests.

Key fields:

* id
* name
* slug
* legal_regime
* request_email
* secondary_emails
* status
* template_id
* notes

### RequestTemplate

Reusable email template for outbound requests.

Key fields:

* id
* name
* subject_template
* body_template
* status
* created_at
* updated_at

### RequestCycle

Represents a monthly request batch.

Key fields:

* id
* month
* status
* created_by
* approved_by
* approved_at
* sent_at

### RequestCase

One authority's request for one cycle.

Key fields:

* id
* authority_id
* cycle_id
* template_id
* reply_alias
* status
* expected_due_at
* sent_at
* closed_at

### OutboundMessage

The email sent to an authority.

Key fields:

* id
* request_case_id
* to_addresses
* from_address
* subject
* body
* provider_message_id
* send_status
* sent_at

### InboundMessage

An email received from an authority or mail provider.

Key fields:

* id
* request_case_id
* raw_artifact_uri
* provider_message_id
* from_address
* to_addresses
* subject
* received_at
* classification
* classification_confidence
* processing_status

### StoredDocument

An attachment or extracted body document belonging to an inbound message.

Key fields:

* id
* inbound_message_id
* filename
* content_type
* size_bytes
* raw_artifact_uri
* parsed_text
* parse_status
* parse_metadata
* safety_status

### ResponseRecord

Structured record derived from one or more inbound messages/documents for a
request case.

Key fields:

* id
* request_case_id
* authority_id
* response_date
* request_month
* response_category
* authority_reference
* title
* summary
* metadata
* review_state
* created_at
* updated_at

### AuditEvent

Append-only event describing important system or operator actions.

Key fields:

* id
* entity_type
* entity_id
* event_type
* actor_type
* actor_id
* metadata
* created_at

## 14. Safety, Privacy, and Publication

Phase 0 stores material that may contain personal, sensitive, or legally risky
information. It must preserve material for review without exposing it publicly.

The system must:

* avoid logging raw email bodies or attachment contents in application logs
* preserve raw material in controlled storage
* keep processing errors free of unnecessary personal information
* track suspicious files and low-confidence extraction
* require a later explicit publication workflow before any public release

## 15. Operational Requirements

* The monthly send process should support dry runs.
* Sending should be idempotent per authority and cycle.
* Inbound receipt should preserve raw material before parsing.
* Processing should be retryable.
* Parser failures should be isolated to individual files where possible.
* Operators should be able to export or inspect case-level provenance.
* System jobs should be observable through logs, metrics, and status tables.

## 16. Rollout Plan

### Phase 0A: Request Intake Foundation

* authority directory
* request templates
* request cycles
* outbound request cases
* unique reply aliases
* send status tracking

### Phase 0B: Inbound Email Foundation

* inbound email receipt
* raw message and attachment storage
* request case association
* inbound message status tracking

### Phase 0C: Processing Pipeline

* safety scanning
* response classification
* text extraction
* metadata extraction
* per-document processing status

### Phase 0D: Operator Controls

* case dashboard or internal API
* manual correction
* retry/reprocess tools
* audit log

## 17. Success Criteria

Phase 0 is successful when Sunlight can:

* send monthly requests to a defined authority list
* receive authority replies through unique aliases
* associate replies with the correct request case
* preserve raw emails and attachments
* parse common attachment formats
* store structured response records and metadata
* identify failed or suspicious processing cases
* let operators correct and retry cases
* maintain a clear audit trail from outbound request to stored response

## 18. Open Questions

* What exact wording should the recurring disclosure request use?
* Which authorities are included in the first pilot?
* Should the first pilot be monthly or quarterly?
* Which mail provider should be used for inbound and outbound processing?
* What attachment file types are required for the first pilot?
* What storage backend should hold raw email and attachments?
* What minimum metadata is required before a response is considered processed?
* What review states should be shared with later publication workflows?
