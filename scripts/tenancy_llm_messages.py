from __future__ import annotations

import json


ENRICHMENT_SYSTEM_PROMPT = (
    "You enrich New Zealand Tenancy Tribunal decisions for retrieval. "
    "Return only valid JSON matching the requested schema. "
    "Return neutral, concise metadata. Do not invent facts. "
    "Use empty lists or an empty string when the document text does not support a field."
)
ENRICHMENT_INSTRUCTIONS = {
    "items": "Return exactly one item for every input document, with no omissions.",
    "document_id": "Every item must repeat the exact document_id from its input document.",
    "case_summary": "One neutral sentence under 45 words.",
    "catchwords": "Three to eight short legal/retrieval catchwords.",
    "questions_answered": "Three to six natural-language questions this decision answers.",
    "applicant_story": (
        "One to three plain-language sentences from the applicant or claimant side "
        "of the dispute. Use only claims/facts stated in the decision, and do not "
        "include the Tribunal outcome unless it was part of what the applicant sought."
    ),
    "respondent_story": (
        "One to three plain-language sentences from the respondent side of the "
        "dispute. Use an empty string if the decision does not state their position."
    ),
    "neutral_fact_pattern": (
        "One to three neutral plain-language sentences describing the dispute facts "
        "without stating who won."
    ),
    "claims_made": (
        "Three to eight short claims, allegations, or issues raised by the parties. "
        "Use only claims visible in the decision."
    ),
    "remedies_sought": (
        "One to six remedies or orders requested by the parties, not the final order "
        "unless the request and order are the same."
    ),
    "legal_principles": (
        "Zero to four reusable principles. confidence must be low, medium, or high; "
        "source_section should be order, reasons, or boilerplate."
    ),
}


def build_enrichment_messages(documents: list[dict[str, object]]) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": ENRICHMENT_SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "instructions": ENRICHMENT_INSTRUCTIONS,
                    "documents": documents,
                },
                ensure_ascii=True,
            ),
        },
    ]
