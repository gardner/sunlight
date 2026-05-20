from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from tenancy_corpus import (
    PIPELINE_VERSION,
    SOURCE,
    parse_tenancy_markdown,
    render_tenancy_markdown,
)


LLM_ENRICHMENT_VERSION = "tenancy-llm-v1"


class LegalPrinciple(BaseModel):
    principle: str = ""
    confidence: str = "medium"
    source_section: str = ""


class GeneratedEnrichment(BaseModel):
    document_id: str
    case_summary: str = ""
    catchwords: list[str] = Field(default_factory=list)
    questions_answered: list[str] = Field(default_factory=list)
    legal_principles: list[LegalPrinciple] = Field(default_factory=list)
    llm_suggested_tags: list[str] = Field(default_factory=list)


class GeneratedEnrichmentBatch(BaseModel):
    items: list[GeneratedEnrichment]


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def pending_llm_markdown_paths(
    markdown_dir: Path,
    *,
    limit: int | None = None,
    force: bool = False,
) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(markdown_dir.glob("*.md")):
        try:
            metadata, body = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            metadata.get("source") != SOURCE
            or metadata.get("parser") != "docling"
            or metadata.get("pipeline_version") != PIPELINE_VERSION
        ):
            continue
        if not force and metadata.get("llm_enrichment_version") == LLM_ENRICHMENT_VERSION:
            continue
        if body.strip():
            paths.append(path)
        if limit and len(paths) >= limit:
            break
    return paths


def apply_generated_enrichment(
    markdown_path: Path,
    enrichment: dict[str, object],
    *,
    model: str,
    now: str | None = None,
) -> None:
    metadata, body = parse_tenancy_markdown(markdown_path.read_text(encoding="utf-8"))
    merged = dict(metadata)
    for key in (
        "case_summary",
        "catchwords",
        "questions_answered",
        "legal_principles",
        "llm_suggested_tags",
    ):
        value = enrichment.get(key)
        if value not in (None, "", [], {}):
            merged[key] = normalize_generated_value(value)
    merged["llm_enrichment_model"] = model
    merged["llm_enrichment_version"] = LLM_ENRICHMENT_VERSION
    merged["llm_enriched_at"] = now or utc_now_iso()
    markdown_path.write_text(render_tenancy_markdown(merged, body), encoding="utf-8")


def normalize_generated_value(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(exclude_none=True)
    if isinstance(value, list):
        return [normalize_generated_value(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_generated_value(item) for key, item in value.items()}
    return value


def build_llm_input(markdown_paths: list[Path], max_chars: int) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for path in markdown_paths:
        metadata, body = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
        items.append(
            {
                "document_id": metadata["document_id"],
                "title": metadata.get("request_title"),
                "decision_date": metadata.get("decision_date"),
                "legal_issue_tags": metadata.get("legal_issue_tags"),
                "statute_sections": metadata.get("statute_sections"),
                "excerpt": body.strip()[:max_chars],
            }
        )
    return items


def enrich_with_llm(
    markdown_paths: list[Path],
    *,
    base_url: str,
    api_key: str,
    model: str,
    rpm: int,
    batch_size: int,
    max_chars: int,
    timeout: int,
    max_tokens: int,
) -> dict[str, int]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    counts = {"enriched": 0, "failed": 0}
    min_interval = 60 / max(rpm, 1)
    last_call_at = 0.0

    for batch_start in range(0, len(markdown_paths), batch_size):
        batch = markdown_paths[batch_start : batch_start + batch_size]
        elapsed = time.time() - last_call_at
        if last_call_at and elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        last_call_at = time.time()

        try:
            parsed = request_generated_enrichment_with_retries(
                client, batch, model, max_chars, max_tokens
            )
        except Exception as exc:
            counts["failed"] += len(batch)
            print(f"LLM enrichment failed for batch starting {batch_start}: {exc}", flush=True)
            continue

        by_id = {item.document_id: item for item in parsed.items}
        now = utc_now_iso()
        for path in batch:
            metadata, _ = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
            item = by_id.get(str(metadata["document_id"]))
            if item is None:
                counts["failed"] += 1
                continue
            apply_generated_enrichment(
                path,
                item.model_dump(exclude_none=True),
                model=model,
                now=now,
            )
            counts["enriched"] += 1
        print(
            f"LLM enrichment progress {min(batch_start + len(batch), len(markdown_paths))}/"
            f"{len(markdown_paths)}: {counts}",
            flush=True,
        )
    return counts


def request_generated_enrichment(
    client,
    markdown_paths: list[Path],
    model: str,
    max_chars: int,
    max_tokens: int,
) -> GeneratedEnrichmentBatch:
    documents = build_llm_input(markdown_paths, max_chars)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You enrich New Zealand Tenancy Tribunal decisions for retrieval. "
                    "Return only valid JSON matching the requested schema. "
                    "Return neutral, concise metadata. Do not invent facts. "
                    "Use empty lists or an empty string when the excerpt does not support a field."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "instructions": {
                            "document_id": (
                                "Every item must repeat the exact document_id "
                                "from its input document."
                            ),
                            "case_summary": "One neutral sentence under 45 words.",
                            "catchwords": "Three to eight short legal/retrieval catchwords.",
                            "questions_answered": (
                                "Three to six natural-language questions this decision answers."
                            ),
                            "legal_principles": (
                                "Zero to four reusable principles. confidence must be "
                                "low, medium, or high; source_section should be order, "
                                "reasons, or boilerplate."
                            ),
                        },
                        "documents": documents,
                    },
                    ensure_ascii=True,
                ),
            },
        ],
        temperature=0,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content or ""
    default_document_id = str(documents[0]["document_id"]) if len(documents) == 1 else None
    return parse_enrichment_content(content, default_document_id=default_document_id)


def parse_enrichment_content(
    content: str,
    *,
    default_document_id: str | None = None,
) -> GeneratedEnrichmentBatch:
    payload = parse_json_payload(content)
    if "items" not in payload and default_document_id and "document_id" not in payload:
        payload["document_id"] = default_document_id
    if "items" not in payload and "document_id" in payload:
        payload = {"items": [payload]}
    return GeneratedEnrichmentBatch.model_validate(payload)


def parse_json_payload(content: str) -> dict[str, object]:
    try:
        payload = json.loads(content)
    except Exception:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        payload = json.loads(content[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("LLM enrichment response must be a JSON object")
    return payload


def request_generated_enrichment_with_retries(
    client,
    markdown_paths: list[Path],
    model: str,
    max_chars: int,
    max_tokens: int,
    *,
    attempts: int = 3,
) -> GeneratedEnrichmentBatch:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_generated_enrichment(
                client, markdown_paths, model, max_chars, max_tokens
            )
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(2**attempt, 10))
    assert last_error is not None
    raise last_error
