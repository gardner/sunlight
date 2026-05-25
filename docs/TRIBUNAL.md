# Tenancy Tribunal Decisions

This is the plan for making Tenancy Tribunal decisions a first-class public
corpus in Sunlight, not a BM25-only side index.

## Current Findings

Local data is available at:

```text
justice/data/tenancy/pdfs/
```

The directory contains one PDF and one JSON sidecar per scraped order. The
sidecars are consistent enough to ingest directly:

```text
address
application_number
case_name
city
court
date_of_issue
downloaded_at
filename
mbie_order
order_id
parties
pdf_url
published_date
source
source_url
suburb
```

Corpus counts from the current local scrape:

```text
32,383 JSON sidecars / PDFs
32,378 unique PDF URLs after dedupe
53    Tenancy Tribunal 2021
6,471 Tenancy Tribunal 2023
10,646 Tenancy Tribunal 2024
11,557 Tenancy Tribunal 2025
3,656 Tenancy Tribunal 2026
```

Legacy scrape coverage:

```text
justice/data/tenancy/legacy/pdf/

11,476 legacy PDFs
11,411 exact signature dates extracted from the legacy text sidecars
7      fallback dates from standalone date lines
58     citation-year-only fallbacks used for coverage analysis

Legacy date range: 2020-01-01 fallback through 2023-07-07
Current deduped scrape range: 2021-05-20 through 2026-04-16
```

There is no gap between the last legacy scrape date and the current scrape.
The current corpus has a continuous 2023 run beginning on 2023-05-20, while
the legacy scrape continues through 2023-07-07, so the two sources overlap in
May-July 2023. The current scrape also has 49 deduped decisions from
2021-05-20, but does not cover the 2021-05-21 to 2023-05-19 period without
the legacy PDFs.

After recording this coverage, the old legacy `.txt*` extraction sidecars were
deleted. Legacy ingestion now uses the original PDFs and Docling conversion.

The sampled decisions contain useful retrieval and metadata signals:

* formal citation lines such as `[2026] NZTT 5380224`
* application/order identifiers
* issue and publication dates
* party roles, usually landlord and tenant
* suppression/non-publication status
* tenancy address, suburb, and city when not suppressed
* ordered amounts and payment schedules
* outcome types such as rent arrears, conditional termination, compensation,
  bond distribution, access for inspection, rehearing/appeal boilerplate
* statutory references, especially Residential Tenancies Act sections

Some decisions include personal names and street addresses where no suppression
order applies. They are public tribunal decisions, but Sunlight should avoid
adding people-finder style facets. We can preserve source text and provenance
while being conservative about which personal fields become public filters.

`docs/tenancy.md` adds one important warning for extraction quality: orders,
reasons, schedules, and boilerplate can disagree. Monetary and remedy extraction
must therefore carry validation flags rather than being treated as authoritative
without checks.

## Implementation Status

The first production Tenancy ingestion slice is implemented and has completed
locally.

Implemented:

* `scripts/tenancy_corpus.py` discovers Tenancy PDF/JSON sidecars, dedupes by
  `pdf_url`, builds stable `doc_justice_tenancy_<order_id>` document IDs, and
  emits canonical tribunal metadata.
* `scripts/tenancy_corpus.py` also has a legacy PDF adapter for
  `justice/data/tenancy/legacy/pdf`. It builds stable
  `doc_justice_tenancy_legacy_<order_id>` document IDs and reconstructs the
  Justice PDF URL from the legacy filename.
* `scripts/ingest_tenancy.py` converts with Docling, writes Docling markdown to
  `storage/justice/tenancy/markdown_docling`, enriches deterministic metadata,
  optionally enriches generated retrieval metadata through the local
  OpenAI-compatible LLM endpoint, and embeds into LanceDB with Qwen3.
  Legacy ingestion is opt-in with `--include-legacy`.
* The LanceDB writer and Vectorize/BM25 exporters preserve source-aware fields
  such as `source_type`, `retrieval_view`, `canonical_document_id`,
  `source_page_url`, Tenancy IDs, citation/date fields, issue tags, and statute
  sections.
* Retrieval documents now include the original source text plus generated views
  for `case_summary`, `catchwords`, `questions_answered`, and
  `legal_principles` when those fields exist.

Completed local import:

```text
32,378 unique Tenancy Tribunal PDFs discovered
32,378 Docling markdown files written
32,378 embedding markers written
412,537 LanceDB chunk rows in storage/justice/tenancy/lancedb/chunks_v2
```

Legacy import status:

```text
11,476 legacy PDFs normalized
1 legacy PDF smoke-tested through Docling after deleting old text sidecars
0 legacy PDFs converted in the main markdown directory before the full legacy run
```

The full run used Docling and Qwen embeddings with GPU 0. Docling/RapidOCR logs
confirmed GPU device 0 during OCR/model stages, while CPU remained heavily used
for PDF loading, layout, and text extraction. Embedding ran on CUDA with
`CUDA_VISIBLE_DEVICES=0`.

The full-corpus run intentionally used `--skip-llm`. LLM enrichment is
idempotent and resumable through `llm_enrichment_version`; it should be run as a
separate controlled batch before adding generated retrieval views to public
search.

The current enrichment target is the repo-local Bifrost gateway at
`http://127.0.0.1:8081/v1`. API calls use `nvidia/regular`, which starts from
the high-context route and lets Bifrost fan out across the currently usable
providers: NVIDIA `regular` and OpenRouter `regular`, with provider-specific
fallbacks. Groq is not in the default Tenancy `regular` route because its lower
token limits caused fast 413/TPM failures for batched decision prompts.

Token budgeting still uses the local Qwen tokenizer `Qwen/Qwen3.6-27B` as a
consistent estimator. The practical per-request prompt budget remains 14,336
tokens, leaving room for output while avoiding unnecessarily large fallback
requests. A 1,000-file Qwen-tokenized sample of the existing Tenancy markdown
produced 137 enrichment requests at this budget: mean 7.3 decisions per request,
median 7, and maximum 8. The default LLM request rate is now 60 RPM, matching
the configured aggregate NVIDIA plus OpenRouter route capacity, and default
LLM concurrency is 6.

A sustained concurrency-2 test on 1,000 temporary Tenancy markdown copies
completed cleanly:

```text
999 pending files enriched
0 failures
136 LLM requests
47.57 minutes elapsed
21.0 documents/minute
2.86 requests/minute
```

One copied markdown file already had the current enrichment marker before the
test run, so it was skipped. The next tuning test should use the current
Bifrost defaults first, then compare provider distribution, fallback rate,
structured-output failures, throughput, and generated metadata quality before
raising RPM or concurrency further.

## Converter Decision

Use Docling as the canonical production converter for Tenancy Tribunal PDFs.

MarkItDown is acceptable for quick local inspection, but it should not define
the production corpus. A scratch MarkItDown run exists locally under
`storage/justice/tenancy/markdown`; treat it as inspection output only. It
should be deleted and regenerated once the Docling Tenancy path exists.

Docling is the right default because it is already the project standard for the
owned ingestion pipeline and should produce better structure for headings,
tables, layout, and long-term chunk quality. It is also the fairest input for
hybrid evals because FYI and tribunal documents then pass through the same
conversion family.

Cloudflare Workers AI Markdown Conversion was tested as a comparison path using
the documented `env.AI.toMarkdown` Worker binding. The direct REST endpoint
returned `403 Authentication error` with the current project tokens, but a
temporary Worker with the existing AI binding successfully converted PDFs.

Sample output from `storage/evals/markdown_conversion/20260524T211438Z`:

```text
5825064-Tribunal_Order.pdf
Docling:    8.190s, 13,447 chars, 2 tables, citation kept, date extracted
Cloudflare: 0.214s, 11,957 chars, 0 tables, citation kept, date text joined

172069933.pdf
Docling:    4.458s, 4,683 chars, date extracted
Cloudflare: 0.091s, 4,242 chars, date text joined
```

Cloudflare is dramatically faster and may be useful for triage, rough previews,
or a managed comparison baseline. For the production Tenancy corpus, keep
Docling as canonical because it preserved tribunal tables and separated
decision structure more reliably in the samples. Cloudflare often joined page
headers, body text, adjudicator names, and dates without whitespace, which makes
deterministic metadata extraction weaker unless we add additional repair logic.

CPU saturation during conversion is expected. Even with Docling, born-digital
PDF loading, layout analysis, text extraction, and table reconstruction are
heavily CPU-bound. GPU usage should mainly appear during embedding, OCR/model
stages, or later model inference. For Tenancy, many PDFs appear born-digital,
so conversion may peg CPU while the GPU stays mostly idle.

## Embedding Decision

Do not skip embeddings for the production Tenancy corpus.

BM25-only is useful as a local smoke test, but it is not the target system.
Tenancy must participate in the same hybrid retrieval path as FYI:

```text
Docling markdown
  -> chunking
  -> Qwen3 embeddings
  -> LanceDB local vector store
  -> Cloudflare Vectorize
  -> D1 FTS5 BM25 sidecar
  -> reciprocal-rank fusion
  -> answer generation with citation metadata
```

The only acceptable reason to temporarily skip embeddings is to unblock a
metadata-only or lexical smoke test while the Docling/embedding pipeline is
being generalized. That temporary state must be named explicitly in docs and
eval reports, and it should not be described as production coverage.

## Canonical Metadata

Add tribunal-specific frontmatter fields while preserving the public fields the
current search UI already understands.

Required shared fields:

```text
document_id
source: justice_tenancy
source_type: tribunal_decision
authority_name: Tenancy Tribunal
authority_slug: tenancy-tribunal
authority_category: Tribunal
request_title
request_year
source_url
source_page_url
original_filename
pdf_r2_key
markdown_r2_key
parser: docling
pipeline_version
```

Required Tenancy fields:

```text
tribunal: Tenancy Tribunal
jurisdiction: NZ
decision_date
published_date
tenancy_application_number
tenancy_order_id
nztt_citation
tribunal_location
adjudicator
case_name
parties
applicant_role
respondent_role
tenancy_city
tenancy_suburb
suppression_status
mbie_order
```

Metadata enrichment should happen in layers.

Layer 1 is deterministic and safe to use as hard metadata:

* parse `[YYYY] NZTT <application_number>` citation lines
* parse suppression/non-publication paragraphs into a small enum
* extract Residential Tenancies Act section references
* detect outcome labels from order/reasons text
* extract ordered dollar amounts conservatively
* normalize dates to ISO `YYYY-MM-DD` while keeping raw source values if useful

Layer 2 is generated retrieval metadata. It should improve search recall but
remain marked as generated:

```text
case_summary
catchwords
questions_answered
legal_principles
llm_suggested_tags
chunk_context
```

Layer 3 is validation and safety metadata:

```text
suppression_order
suppressed_fields
privacy_sensitivity
requires_redaction_check
validation_flags
contains_standard_boilerplate
substantive_page_range
boilerplate_page_range
```

Avoid making names and street addresses first-class filter facets until we have
a deliberate privacy/product decision. Keep them in the source text and sidecar
provenance, but prefer city/suburb, outcome, year, statute section, and tribunal
fields for public filtering.

## Tenancy Enrichment Schema

The high-value Tenancy-specific enrichment set is:

```json
{
  "case_metadata": {
    "citation": "[2026] NZTT 5380224",
    "application_number": "5380224",
    "decision_date": "2026-01-05",
    "tribunal_location": "remote",
    "adjudicator": "A Aiolupotea",
    "applicant_role": "landlord",
    "respondent_role": "tenant"
  },
  "suppression_metadata": {
    "suppression_order": true,
    "suppressed_fields": ["tenant_names", "tenancy_address"],
    "privacy_sensitivity": "high",
    "requires_redaction_check": true
  },
  "claim_types": ["rent_arrears", "conditional_termination"],
  "outcome_summary": {
    "resolution_type": "conditional_order",
    "overall_outcome": "landlord_success_with_conditions"
  },
  "monetary_orders": [
    {
      "amount": 1263,
      "currency": "NZD",
      "type": "rent_arrears"
    }
  ],
  "legal_issue_tags": ["rent_arrears", "termination", "suppression"],
  "questions_answered": [
    "When will the tenancy terminate if rent arrears are not paid?",
    "What repayment schedule did the Tribunal order?"
  ],
  "case_summary": "Generated neutral summary for retrieval and display.",
  "catchwords": ["Residential tenancy", "Rent arrears", "Conditional termination"],
  "legal_principles": [
    {
      "principle": "Generated reusable legal principle.",
      "confidence": "medium",
      "source_section": "reasons"
    }
  ],
  "boilerplate_removed": true,
  "validation_flags": []
}
```

Use controlled tags for filtering and analytics. Keep generated free-form tags
separate:

```json
{
  "controlled_tags": ["bond_distribution", "exemplary_damages"],
  "llm_suggested_tags": [
    "bond dispute",
    "tenant-landlord settlement",
    "consent bond split"
  ]
}
```

Likely controlled claim/outcome tags:

```text
abandonment
access_for_inspection
boarding_house
bond_distribution
cleaning
compensation
conditional_termination
damage_to_premises
exemplary_damages
filing_fee
fixed_term_tenancy
healthy_homes
meth_contamination
notice_validity
quiet_enjoyment
rent_arrears
rent_increase
repairs_and_maintenance
retaliatory_notice
suppression
termination
unlawful_entry
water_charges
```

For money/remedy extraction, preserve raw evidence and add validation flags
when the formal order and reasons disagree. The answer path should prefer the
source text over generated extraction whenever a validation flag is present.

## Retrieval Enrichment

`docs/RAG_IDEAS.md` and `docs/tenancy.md` both point to the same core strategy:
do not rely on one plain source chunk vector per decision.

For each decision, store multiple retrieval views that all point back to the
same canonical document and source chunk:

```text
original_chunk
contextualized_chunk
chunk_summary
questions_answered
catchwords_and_issue_tags
legal_principle
whole_document_summary
```

The original chunk remains the citation source. Generated views are retrieval
helpers, not standalone evidence. The answer generator should cite the original
decision text, not generated summaries or questions.

Contextualized chunks should prepend short document-aware context before
embedding and BM25 indexing:

```text
This chunk is from a 2026 Tenancy Tribunal decision,
Kāinga Ora–Homes and Communities v Love, Sonya, application 5380224.
It concerns access for inspection and conditional termination under the
Residential Tenancies Act.

<original chunk text>
```

This is especially useful for short order paragraphs whose local text does not
repeat the case, date, party roles, or legal issue.

Questions-answered metadata should be embedded separately. Example questions:

```text
Can exemplary damages be awarded for failing to agree to bond distribution?
How did the Tenancy Tribunal divide the bond in this case?
Did the Tribunal suppress the parties' names?
Who attended the hearing?
Was a filing fee awarded when both parties were partly successful?
```

Boilerplate should be routed separately. Rehearing, appeal, and enforcement
text should not dominate substantive tenancy retrieval, but it should remain
searchable for procedural questions.

Future retrieval experiments can include late-interaction reranking over the
hybrid candidate set. Treat that as an eval-driven enhancement after the
Docling, metadata, Vectorize, and D1 baseline is working.

## Artifact Layout

Use the shared public corpus bucket, not the private operational bucket.

Recommended R2 layout:

```text
r2://sunlight-corpus/
  canonical/
    justice/
      tenancy/
        v1/
          pdf/{year}/{order_id}.pdf

  markdown/
    justice/
      tenancy/
        v1/
          {year}/{document_id}.md

  chunks/
    justice/
      tenancy/
        v1/
          {year}/{document_id}.jsonl

  manifests/
    justice/tenancy/v1/files.ndjson
    justice/tenancy/v1/conversion-report.ndjson
    justice/tenancy/v1/index-report.ndjson
```

The manifest should include PDF path, JSON sidecar path, SHA-256 hashes,
dedupe key, conversion status, parser, failure reason, Markdown path, R2 keys,
and generated document id.

## Pipeline Changes

Generalize the FYI-specific ingestion code into a corpus-aware pipeline instead
of creating a one-off Tenancy importer.

Implementation direction:

1. Introduce a `CorpusDocument` or source adapter boundary.
2. Add a `tenancy` adapter that reads PDF/JSON pairs, dedupes by `pdf_url`,
   builds stable document IDs, and emits Docling frontmatter.
3. Keep Docling conversion and PyMuPDF fallback shared.
4. Keep table extraction and chunking shared.
5. Add deterministic enrichment for citations, suppression, statute sections,
   claim/outcome tags, boilerplate ranges, and validation flags.
6. Add generated retrieval metadata for summaries, catchwords, legal
   principles, and questions answered.
7. Extend LanceDB columns for generic public metadata plus tribunal fields.
8. Export original chunks and generated retrieval views to Vectorize with
   pointers back to canonical source chunks.
9. Export source chunks to D1 BM25, with contextual text only where evals show
   it helps and does not degrade citation clarity.
10. Add upload support for canonical PDFs and Markdown to `sunlight-corpus`.

The existing binding and index names are FYI-specific:

```text
FYI_VECTORS
fyi-v2
```

Tenancy should not be hidden behind FYI naming. Either create a new combined
Vectorize index such as `sunlight-v1`, or introduce `SUNLIGHT_VECTORS` as the
Worker binding while keeping `fyi-v2` as a temporary implementation detail
during migration.

## D1 And Vectorize

The D1 BM25 sidecar already has the right broad shape for chunks, but it needs
source-aware document metadata for first-class corpus behavior.

Add or formalize a canonical document table before loading tribunal data:

```sql
disclosed_documents(
  document_id,
  source,
  source_type,
  authority_name,
  authority_slug,
  authority_category,
  title,
  year,
  decision_date,
  source_url,
  source_page_url,
  original_filename,
  pdf_r2_key,
  markdown_r2_key,
  metadata_json,
  visibility,
  created_at
)
```

Keep `disclosed_chunks` for retrieval text and citation-ready fields. Add only
the most useful tribunal fields directly to chunk rows if they are needed for
ranking or filtering; store richer tribunal metadata on the document row.

Vectorize metadata should remain compact but citation-ready:

```json
{
  "document_id": "doc_justice_tenancy_243662289",
  "chunk_id": "chunk_...",
  "source": "justice_tenancy",
  "source_type": "tribunal_decision",
  "authority_name": "Tenancy Tribunal",
  "authority_slug": "tenancy-tribunal",
  "authority_category": "Tribunal",
  "request_title": "Kāinga Ora–Homes and Communities v Love, Sonya",
  "request_year": 2026,
  "source_url": "https://forms.justice.govt.nz/search/Documents/TTV2/PDF/...",
  "source_page_url": "https://forms.justice.govt.nz/search/TT/abstract.html?...",
  "markdown_r2_key": "markdown/justice/tenancy/v1/2026/doc_justice_tenancy_243662289.md",
  "text_preview": "TENANCY TRIBUNAL AT..."
}
```

If generated retrieval views are stored in Vectorize, add:

```json
{
  "retrieval_view": "questions_answered",
  "canonical_chunk_id": "chunk_doc_justice_tenancy_243662289_0002_abcd",
  "generated": true
}
```

D1 should index source text and selected contextual text for lexical retrieval,
but generated summaries/questions should either live in separate FTS columns or
separate rows with `retrieval_view` so evals can identify whether generated
metadata is helping or hurting.

## Search Product Changes

The public search route currently describes answers as being about official
information releases. It needs broader corpus language before Tenancy goes live.

Required runtime changes:

* rename `FYI_VECTORS` usage to a corpus-neutral binding
* include `source` and `source_type` in citation responses
* label result cards as `Official information release` or `Tribunal decision`
* label Tenancy `source_url` as `Decision PDF`, not `Attachment URL`
* include `source_page_url` where available for the Justice search abstract
* allow optional source filters: all, FYI releases, Tenancy Tribunal decisions
* adjust answer system prompt to cover public records, not only OIA/LGOIMA
  releases
* preserve hybrid retrieval behavior across all selected sources

The source filter must apply to both Vectorize and D1 where possible. If
Vectorize metadata filters are not available or not reliable for the chosen
index, retrieve broadly and filter before fusion, then measure the recall cost.

## Evaluation

Add a Tenancy eval subset before production import. The set should cover:

* exact application number and citation queries
* named party queries where names are public
* city/suburb queries
* rent arrears and conditional termination questions
* bond distribution and compensation questions
* access/inspection breach questions
* suppression/non-publication questions
* Residential Tenancies Act section queries
* amount/table-heavy questions
* absent-answer questions
* generated-questions retrieval cases where the user phrasing does not match
  the decision wording
* boilerplate-routing cases, such as rehearing or appeal procedure questions
* validation-flag cases where the system should avoid overconfident extracted
  monetary answers

Measure:

* Vectorize-only recall
* BM25-only recall
* hybrid fused recall
* generated-view contribution by `retrieval_view`
* final citation recall
* answer groundedness
* citation label correctness
* source-filter behavior
* conversion failure rate and markdown quality
* abstention quality when evidence is absent or extraction is inconsistent

Do not compare Tenancy BM25-only results against FYI hybrid results as if they
are equivalent. The baseline must clearly say which corpora have embeddings.

Store full traces for Tenancy eval runs:

```text
query
expected document/chunk IDs
metadata filters
retrieved source chunks
retrieved generated views
fused order
final context
answer
citations
latency
model versions
embedding version
parser version
prompt version
```

## Rollout Plan

1. Done: add source adapter tests using a small Tenancy fixture set.
2. Done: add corpus-aware metadata and retrieval-view preservation to the
   ingestion/export path.
3. Done: implement Docling Tenancy conversion with deterministic document IDs
   and dedupe by `pdf_url`.
4. Done: add deterministic metadata enrichment for citations, suppression,
   claim tags, statute references, ordered amounts, and boilerplate flags.
5. Done: run Docling smoke tests, inspect output, and reject the scratch
   MarkItDown path as production input.
6. Done: embed the full Tenancy corpus into LanceDB with Qwen3.
7. Next: benchmark controlled LLM enrichment at concurrency 4 using the
   Qwen-tokenized 14,336-token prompt budget, compare it with the clean
   concurrency-2 result, then inspect summaries, catchwords, legal principles,
   and questions answered.
8. Next: run Tenancy evals comparing source-only retrieval against generated
   retrieval views before public search export.
9. Next: export Tenancy vectors to the corpus Vectorize index with citation
   metadata.
10. Next: export Tenancy source chunks to D1 BM25 without resetting existing
    FYI rows.
11. Next: update the landing search API and UI for multi-source citations and
    filters.
12. Next: upload canonical PDFs and Markdown to `sunlight-corpus`.
13. Next: import to production only after the eval report confirms hybrid
    coverage and citation labels are working.

## Immediate Next Slice

Do not import the scratch MarkItDown output.

The next slice should make the completed LanceDB corpus comparable in the
retrieval stack:

* run a small LLM enrichment batch and inspect generated retrieval metadata
  quality before scaling it across all 32k decisions
* add Tenancy eval questions for exact IDs/citations, city/suburb, rent arrears,
  bond, suppression, statute-section, and amount-heavy cases
* export source-text Tenancy chunks to the D1 BM25 sidecar
* export Tenancy vectors to the corpus Vectorize index
* compare vector, BM25, hybrid, and generated-view retrieval before enabling
  Tenancy in public search
