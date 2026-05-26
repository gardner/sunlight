It is usually called **hypothetical question embedding** or **hypothetical questions** in RAG.

The broader family is:

| Term                                                | Meaning                                                                                                                                                    |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hypothetical Question Embeddings**                | Generate likely questions that a chunk/document can answer, embed those questions, then retrieve the original chunk when a user query matches one of them. |
| **Document expansion** / **doc2query**              | Add generated queries/questions to a document so it becomes easier to retrieve. This term comes from classic IR/search.                                    |
| **Metadata enrichment** / **metadata augmentation** | Add LLM-generated metadata like summaries, titles, keywords, entities, questions answered, etc.                                                            |
| **Synthetic QA generation**                         | Generate question-answer pairs from documents, often for evals, fine-tuning, or retrieval improvement.                                                     |
| **QuestionsAnsweredExtractor**                      | LlamaIndex’s concrete name for this pattern: it extracts “a set of questions that each Node can answer.” ([Developer Documentation][1])                    |

The specific thing you described is best named:

> **Question-based document expansion using hypothetical question embeddings**

or, more practically:

> **LLM-generated “questions answered” metadata for retrieval**

It is related to **HyDE**, but not the same thing. **HyDE** usually means: at query time, take the user’s query, generate a hypothetical answer/document, embed that, and retrieve against the corpus. What you described is the inverse/offline version: during ingestion, generate likely questions for each chunk/document, embed those generated questions, and use them as retrieval targets. Some people call this **HyPE**, “Hypothetical Prompt/Question Embeddings,” but the terminology is less standardized. ([Glaforge][2])

A common architecture looks like this:

```text
Document/chunk
  -> LLM generates:
       - questions this chunk answers
       - optional short answers
       - summary
       - entities / keywords
  -> embed generated questions or QA text
  -> store vector with pointer back to original chunk
  -> retrieve original chunk at query time
```

Microsoft’s RAG guidance describes the broader ingestion-stage version as **chunk enrichment**, where extra metadata such as titles, summaries, keywords, entities, and similar fields are added to improve vector comparisons and search behaviour. ([Microsoft Learn][3])

For your docs/code, I’d name the pipeline stage something like:

```ts
generateQuestionsAnsweredMetadata()
```

and the retrieval strategy:

```ts
hypotheticalQuestionRetrieval
```

or:

```ts
questionExpandedChunkRetrieval
```

Best plain-English label: **“Questions Answered metadata enrichment.”**

[1]: https://developers.llamaindex.ai/python/framework/module_guides/loading/documents_and_nodes/usage_metadata_extractor/?utm_source=chatgpt.com "Metadata Extraction Usage Pattern - LlamaParse - LlamaIndex"
[2]: https://glaforge.dev/posts/2025/07/06/advanced-rag-hypothetical-question-embedding/?utm_source=chatgpt.com "Advanced RAG — Hypothetical Question Embedding"
[3]: https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/rag/rag-enrichment-phase?utm_source=chatgpt.com "Develop a RAG Solution - Chunk Enrichment Phase"

---

For Tenancy Tribunal decisions, I’d treat metadata enrichment as two layers:

1. **filterable structured metadata** for faceted search, dashboards, analytics, and deduping.
2. **retrieval-side semantic metadata** for better RAG recall.

The attached example is useful because it has several common features: suppression, party roles, bond distribution, dismissed claims, consent outcome, adjudicator/date, and boilerplate rehearing/appeal/enforcement text. It also has a possible inconsistency worth flagging: the formal order says the bond is paid entirely to the tenant, while the reasons say the parties consented to $143.75 to the landlord and $2,056.25 to the tenant.

## High-value metadata enrichment methods

### 1. Case header extraction

Extract the boring-but-critical stuff:

```json
{
  "jurisdiction": "Tenancy Tribunal",
  "citation": "[2021] NZTT [location suppressed] 4294057",
  "case_number": "4294057",
  "tribunal_location": "suppressed",
  "decision_date": "2021-05-06",
  "adjudicator": "S Young",
  "applicant_role": "tenant",
  "respondent_role": "landlord",
  "tenancy_address_suppressed": true
}
```

This is useful for sorting, deduplication, timeline search, analytics, and linking related documents.

---

### 2. Privacy / suppression metadata

Tenancy decisions often suppress names, addresses, locations, and identifying details.

```json
{
  "suppression_order": true,
  "suppressed_fields": [
    "tenant_names",
    "landlord_names",
    "tenancy_address",
    "bond_number",
    "event_location"
  ],
  "privacy_sensitivity": "high",
  "safe_for_public_display": true,
  "requires_redaction_check": true
}
```

This is important because some documents may be partially suppressed, inconsistently suppressed, or contain residual identifying info in the body.

---

### 2a. PII span audit

Use `scripts/scan_pii_gliner.py` for an output-only pass with
`nvidia/gliner-PII` when we want model-assisted review of residual identifiers.
The scanner reads parsed markdown, scans the body by default, preserves absolute
body offsets for each span, and writes JSONL plus optional aggregate summary
JSON. It does not rewrite source markdown.

```bash
uv run python scripts/scan_pii_gliner.py \
  --markdown-dir storage/justice/tenancy/markdown_docling \
  --limit 25 \
  --output-jsonl /tmp/tenancy-pii-gliner.jsonl \
  --summary-json /tmp/tenancy-pii-gliner-summary.json
```

Review the sampled spans and false positives before running the full corpus or
using the results as part of a publication workflow.

---

### 3. Claim / application classification

Classify what the parties were asking for.

For this example:

```json
{
  "applications": [
    {
      "type": "bond_distribution",
      "status": "resolved_by_consent"
    },
    {
      "type": "exemplary_damages",
      "basis": "failure_to_agree_to_bond_distribution",
      "status": "dismissed"
    },
    {
      "type": "filing_fee",
      "status": "no_order"
    }
  ]
}
```

Useful labels might include:

```text
bond refund
rent arrears
damage to premises
cleaning
water charges
meth contamination
termination
notice validity
retaliatory notice
exemplary damages
healthy homes
repairs and maintenance
quiet enjoyment
unlawful entry
abandonment
boarding house
fixed-term tenancy
rent increase
```

This is one of the most useful metadata layers for Tenancy Tribunal RAG.

---

### 4. Outcome / remedy extraction

Extract who won what.

```json
{
  "overall_outcome": "mixed_success",
  "orders": [
    {
      "order_type": "bond_payment",
      "payer": "Bond Centre",
      "amount_total": 2200,
      "currency": "NZD",
      "recipient_breakdown": [
        {
          "party_role": "tenant",
          "amount": 2200
        },
        {
          "party_role": "landlord",
          "amount": 0
        }
      ]
    },
    {
      "order_type": "dismissal",
      "scope": "all_other_applications"
    }
  ],
  "filing_fee_order": "none"
}
```

For analytics, you can also normalise:

```json
{
  "tenant_awarded_amount": 2200,
  "landlord_awarded_amount": 0,
  "net_to_tenant": 2200,
  "net_to_landlord": 0
}
```

But in this example I’d also add an inconsistency warning because the reasons mention a different bond split.

---

### 5. Inconsistency / validation metadata

This is especially valuable for legal decisions because extracted values often conflict between the order, reasons, schedule, and boilerplate.

```json
{
  "validation_flags": [
    {
      "type": "monetary_inconsistency",
      "severity": "high",
      "description": "Formal order says tenant receives $2,200 and landlord $0, but reasons say landlord receives $143.75 and tenant receives $2,056.25."
    }
  ]
}
```

This is fucking useful because your RAG system can avoid confidently answering from a dodgy extraction.

---

### 6. Legal issue taxonomy

Generate controlled tags for the legal issues.

For this document:

```json
{
  "legal_issue_tags": [
    "bond_distribution",
    "exemplary_damages",
    "filing_fee",
    "suppression"
  ],
  "tenancy_stage": "end_of_tenancy",
  "resolution_type": "consent_order",
  "hearing_attendance": "both_parties_attended"
}
```

You can keep two sets of tags:

```json
{
  "controlled_tags": ["bond_distribution", "exemplary_damages"],
  "llm_suggested_tags": ["bond dispute", "tenant-landlord settlement", "consent bond split"]
}
```

Controlled tags are better for filtering. LLM tags are better for recall and discovery.

---

### 7. “Questions answered” metadata

This is the one you already identified. For this document, generate things like:

```json
{
  "questions_answered": [
    "Can exemplary damages be awarded for failing to agree to bond distribution?",
    "How did the Tenancy Tribunal divide the bond in this case?",
    "Did the Tribunal suppress the parties' names?",
    "Who attended the hearing?",
    "Was a filing fee awarded when both parties were partly successful?"
  ]
}
```

Then embed the questions and link each embedding back to the source document or chunk.

This improves retrieval when the user asks a question that does not use the same wording as the decision.

Story-shaped generated views can support users typing their side of a dispute
in plain language:

```json
{
  "applicant_story": "The applicant says...",
  "respondent_story": "The respondent says...",
  "neutral_fact_pattern": "The dispute involved...",
  "claims_made": ["The party claimed..."],
  "remedies_sought": ["The party asked for..."]
}
```

These are synthetic retrieval views, not source documents. Mark them
`generated=true` and keep them separate from source-text embeddings.

---

### 8. Short neutral summary

Generate a tight summary for embedding and display:

```json
{
  "case_summary": "The Tribunal made a suppression order for both parties. The parties resolved the bond distribution by consent. The tenant/landlord bond allocation is recorded inconsistently between the formal order and the reasons. The claim for exemplary damages for failure to agree to bond distribution was dismissed because no unlawful act was established. No filing fee order was made."
}
```

This should be separate from the original text and marked as generated.

---

### 9. Headnote / catchwords

Legal databases often use catchwords. You can generate them automatically.

```json
{
  "catchwords": [
    "Residential tenancy",
    "Bond distribution",
    "Consent order",
    "Exemplary damages",
    "No unlawful act",
    "Suppression",
    "Filing fee"
  ]
}
```

This is excellent for hybrid search because catchwords behave like search-friendly labels.

---

### 10. Ratio decidendi / legal principle extraction

For legal RAG, extract the reusable principle:

```json
{
  "legal_principles": [
    {
      "principle": "A failure to agree to bond distribution does not, by itself, justify exemplary damages unless an unlawful act is established.",
      "confidence": "medium",
      "source_section": "reasons"
    }
  ]
}
```

This is more useful than generic summaries when answering legal research questions.

---

### 11. Boilerplate separation

Tenancy decisions include standard rehearing, appeal, and enforcement text. Split it out.

```json
{
  "contains_standard_boilerplate": true,
  "boilerplate_sections": [
    "rehearings",
    "right_of_appeal",
    "grounds_for_appeal",
    "enforcement"
  ],
  "substantive_pages": [1, 2],
  "boilerplate_pages": [3, 4]
}
```

For RAG, you usually do **not** want boilerplate contaminating retrieval unless the user asks procedural questions like “how long do I have to appeal?”

---

### 12. Money and remedy normalisation

Extract all monetary amounts into a structured table.

```json
{
  "monetary_amounts": [
    {
      "amount": 2200,
      "currency": "NZD",
      "type": "bond_total"
    },
    {
      "amount": 143.75,
      "currency": "NZD",
      "type": "bond_to_landlord_in_reasons"
    },
    {
      "amount": 2056.25,
      "currency": "NZD",
      "type": "bond_to_tenant_in_reasons"
    }
  ]
}
```

Then you can search/report:

```text
average bond disputed
median landlord award
tenant success rate
exemplary damages frequency
orders under/over $1,000
```

---

### 13. Party role and success modelling

Don’t just ask “who won?” Legal outcomes are often mixed.

```json
{
  "party_success": {
    "tenant": {
      "success_level": "partial",
      "received_money": true
    },
    "landlord": {
      "success_level": "partial",
      "received_money": "unclear_due_to_inconsistency"
    }
  },
  "both_parties_successful_to_a_degree": true
}
```

This makes analytics much better than binary win/loss.

---

### 14. Chunk-specific semantic labels

Instead of only document-level metadata, enrich each chunk.

Example:

```json
{
  "chunk_type": "substantive_reasoning",
  "topics": ["exemplary_damages", "bond_distribution"],
  "contains_order": false,
  "contains_legal_test": true,
  "contains_factual_findings": false,
  "contains_boilerplate": false
}
```

Useful chunk types:

```text
case_header
orders
reasons
facts
issues
legal_test
analysis
outcome
appeal_rights
enforcement_boilerplate
```

---

### 15. Retrieval routing metadata

Add metadata that helps decide how to search.

```json
{
  "retrieval_profile": {
    "best_for": [
      "bond distribution questions",
      "exemplary damages questions",
      "suppression questions"
    ],
    "not_best_for": [
      "general appeal procedure unless searching boilerplate"
    ],
    "recommended_index": "tenancy_decisions_substantive"
  }
}
```

For example, you could maintain separate indexes:

```text
tenancy_substantive_decisions
tenancy_boilerplate_procedure
tenancy_case_summaries
tenancy_questions_answered
tenancy_applicant_stories
tenancy_respondent_stories
tenancy_neutral_fact_patterns
tenancy_legal_principles
```

Then route queries to the right index.

---

## Particularly useful enrichment set for Tenancy Tribunal docs

For an MVP, I’d use this set:

```json
{
  "case_metadata": {},
  "suppression_metadata": {},
  "claim_types": [],
  "outcome_summary": {},
  "monetary_orders": [],
  "legal_issue_tags": [],
  "questions_answered": [],
  "applicant_story": "",
  "respondent_story": "",
  "neutral_fact_pattern": "",
  "claims_made": [],
  "remedies_sought": [],
  "case_summary": "",
  "legal_principles": [],
  "boilerplate_removed": true,
  "validation_flags": []
}
```

That gives you search, filtering, analytics, and safer answers.

## Best retrieval pattern

For each decision, store multiple vectors:

```text
1. Original chunks
2. Chunk summaries
3. Questions answered
4. Legal principles
5. Catchwords / issue tags
6. Whole-document summary
```

Each vector points back to the same canonical source chunk/document.

That gives you strong recall without polluting the source text. Your answer generator can still quote or cite the original decision, while the enriched metadata just helps find the right material.
