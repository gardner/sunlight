from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from fyi_markdown import parse_markdown_document, render_markdown_document


PIPELINE_VERSION = "tenancy-docling-v1"
SOURCE = "justice_tenancy"
SOURCE_TYPE = "tribunal_decision"
AUTHORITY_NAME = "Tenancy Tribunal"
AUTHORITY_SLUG = "tenancy-tribunal"
AUTHORITY_CATEGORY = "Tribunal"
LEGACY_SOURCE_COLLECTION = "justice_tenancy_legacy"
JUSTICE_PDF_BASE_URL = "https://forms.justice.govt.nz/search/Documents/TTV2/PDF"
LEGACY_PDF_NAME_RE = re.compile(
    r"^(?P<order_id>\d+)-(?P<title>(?:Tenancy_|UTA_)?Tribunal_Order(?:_Redacted)?)\.pdf$",
    flags=re.IGNORECASE,
)


class TenancyDocument:
    def __init__(self, sidecar_path: Path, pdf_path: Path, metadata: dict[str, object]):
        self.sidecar_path = sidecar_path
        self.pdf_path = pdf_path
        self.metadata = metadata


class RetrievalDocument:
    def __init__(self, text: str, metadata: dict[str, object]):
        self.text = text
        self.metadata = metadata


CONTROLLED_TAGS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("rent_arrears", ("rent arrears", "arrears of rent", "rent owing")),
    ("conditional_termination", ("conditional termination", "conditional order")),
    ("termination", ("terminate the tenancy", "termination order", "tenancy will terminate")),
    ("bond_distribution", ("bond", "bond is to be paid", "bond refund")),
    ("compensation", ("compensation", "compensate")),
    ("exemplary_damages", ("exemplary damages",)),
    ("healthy_homes", ("healthy homes",)),
    ("access", ("access for inspection", "right of entry", "inspection")),
    ("repairs", ("repair", "maintenance")),
    ("abandonment", ("abandoned", "abandonment")),
    ("suppression", ("suppression", "must not be published")),
)


def load_sidecar(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def discover_tenancy_documents(pdf_dir: Path) -> list[TenancyDocument]:
    documents: list[TenancyDocument] = []
    seen_pdf_urls: set[str] = set()

    for sidecar_path in sorted(pdf_dir.glob("*.json"), key=sort_key_for_path):
        sidecar = load_sidecar(sidecar_path)
        pdf_path = pdf_dir / str(sidecar.get("filename") or f"{sidecar_path.stem}.pdf")
        if not pdf_path.exists():
            continue

        pdf_url = str(sidecar.get("pdf_url") or pdf_path)
        if pdf_url in seen_pdf_urls:
            continue
        seen_pdf_urls.add(pdf_url)

        documents.append(
            TenancyDocument(
                sidecar_path=sidecar_path,
                pdf_path=pdf_path,
                metadata=build_tenancy_metadata(sidecar, sidecar_path),
            )
        )

    return documents


def discover_legacy_tenancy_documents(pdf_dir: Path) -> list[TenancyDocument]:
    documents: list[TenancyDocument] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf"), key=sort_key_for_path):
        metadata = build_legacy_tenancy_metadata(pdf_path)
        if metadata is None:
            continue
        documents.append(TenancyDocument(pdf_path, pdf_path, metadata))
    return documents


def sort_key_for_path(path: Path) -> tuple[int, str]:
    leading_id = path.stem.split("-", 1)[0]
    return (int(leading_id), path.name) if leading_id.isdigit() else (10**18, path.name)


def build_tenancy_metadata(sidecar: dict[str, Any], sidecar_path: Path) -> dict[str, object]:
    order_id = str(sidecar.get("order_id") or sidecar_path.stem)
    application_number = str(sidecar.get("application_number") or "")
    decision_date = normalize_date(sidecar.get("date_of_issue"))
    published_date = normalize_date(sidecar.get("published_date"))
    request_year = year_from_date(decision_date) or year_from_category(sidecar.get("category"))
    document_id = f"doc_justice_tenancy_{order_id}"
    original_filename = str(sidecar.get("filename") or f"{order_id}.pdf")

    metadata: dict[str, object] = {
        "document_id": document_id,
        "source": SOURCE,
        "source_type": SOURCE_TYPE,
        "authority_name": AUTHORITY_NAME,
        "authority_slug": AUTHORITY_SLUG,
        "authority_category": AUTHORITY_CATEGORY,
        "request_title": build_request_title(sidecar, decision_date),
        "request_year": request_year,
        "source_url": sidecar.get("pdf_url"),
        "source_page_url": sidecar.get("source_url"),
        "original_filename": original_filename,
        "parser": "docling",
        "pipeline_version": PIPELINE_VERSION,
        "tribunal": AUTHORITY_NAME,
        "jurisdiction": "NZ",
        "decision_date": decision_date,
        "published_date": published_date,
        "tenancy_application_number": application_number,
        "tenancy_order_id": order_id,
        "case_name": sidecar.get("case_name"),
        "parties": sidecar.get("parties") or [],
        "tenancy_city": sidecar.get("city"),
        "tenancy_suburb": sidecar.get("suburb"),
        "mbie_order": bool(sidecar.get("mbie_order")),
        "downloaded_at": sidecar.get("downloaded_at"),
    }
    return finalize_tenancy_metadata(metadata)


def build_legacy_tenancy_metadata(pdf_path: Path) -> dict[str, object] | None:
    match = LEGACY_PDF_NAME_RE.match(pdf_path.name)
    if not match:
        return None

    order_id = match.group("order_id")
    document_id = f"doc_justice_tenancy_legacy_{order_id}"
    metadata: dict[str, object] = {
        "document_id": document_id,
        "source": SOURCE,
        "source_type": SOURCE_TYPE,
        "source_collection": LEGACY_SOURCE_COLLECTION,
        "authority_name": AUTHORITY_NAME,
        "authority_slug": AUTHORITY_SLUG,
        "authority_category": AUTHORITY_CATEGORY,
        "request_title": f"Tenancy Tribunal legacy order {order_id}",
        "source_url": f"{JUSTICE_PDF_BASE_URL}/{pdf_path.name}",
        "source_page_url": None,
        "original_filename": pdf_path.name,
        "parser": "docling",
        "pipeline_version": PIPELINE_VERSION,
        "tribunal": AUTHORITY_NAME,
        "jurisdiction": "NZ",
        "tenancy_order_id": order_id,
        "legacy_scrape": True,
    }
    return metadata


def finalize_tenancy_metadata(metadata: dict[str, object]) -> dict[str, object]:
    finalized = dict(metadata)
    request_year = (
        as_int(finalized.get("request_year"))
        or year_from_date(as_str(finalized.get("decision_date")))
        or year_from_date(as_str(finalized.get("published_date")))
        or as_int(finalized.get("extracted_decision_year"))
        or year_from_category(finalized.get("category"))
    )
    if request_year is not None:
        finalized["request_year"] = request_year

    order_id = as_str(finalized.get("tenancy_order_id"))
    document_id = as_str(finalized.get("document_id"))
    if request_year is not None and order_id and document_id:
        finalized.setdefault(
            "pdf_r2_key",
            f"canonical/justice/tenancy/v1/pdf/{request_year}/{order_id}.pdf",
        )
        finalized.setdefault(
            "markdown_r2_key",
            f"markdown/justice/tenancy/v1/{request_year}/{document_id}.md",
        )
    return finalized


def build_request_title(sidecar: dict[str, Any], decision_date: str | None) -> str:
    case_name = public_case_name(sidecar.get("case_name"))
    application_number = str(sidecar.get("application_number") or "").strip()
    date_suffix = f" - {decision_date}" if decision_date else ""
    order_title = f"Tenancy Tribunal order {application_number}{date_suffix}".strip()
    if case_name:
        return f"{case_name} - {order_title}"
    return order_title


def public_case_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = " ".join(value.split())
    if not stripped:
        return None
    if stripped.upper().replace(" ", "") in {"NONEVNONE", "NONENONE"}:
        return None
    return stripped


def as_str(value: object) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def as_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_date(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def year_from_date(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value[:4])
    except ValueError:
        return None


def year_from_category(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.search(r"\b(20\d{2})\b", value)
    return int(match.group(1)) if match else None


def markdown_path_for_document(metadata: dict[str, object], markdown_dir: Path) -> Path:
    return markdown_dir / f"{metadata['document_id']}.md"


def needs_docling_conversion(markdown_path: Path, document_id: str) -> bool:
    if not markdown_path.exists():
        return True
    try:
        metadata, body = parse_markdown_document(markdown_path.read_text(encoding="utf-8"))
    except Exception:
        return True
    return not (
        metadata.get("document_id") == document_id
        and metadata.get("parser") == "docling"
        and metadata.get("pipeline_version") == PIPELINE_VERSION
        and bool(body.strip())
    )


def render_tenancy_markdown(metadata: dict[str, object], body: str) -> str:
    return render_markdown_document(metadata, body)


def parse_tenancy_markdown(text: str) -> tuple[dict[str, object], str]:
    return parse_markdown_document(text)


def deterministic_enrichment(body: str) -> dict[str, object]:
    normalized = " ".join(body.split())
    lower = normalized.lower()
    suppression = suppression_metadata(lower)
    enrichment: dict[str, object] = {
        "nztt_citation": extract_nztt_citation(body),
        "decision_date": extract_decision_date(body),
        "extracted_decision_year": extract_nztt_year(body),
        "tribunal_location": extract_tribunal_location(body),
        "statute_sections": extract_statute_sections(body),
        "legal_issue_tags": extract_controlled_tags(lower),
        "ordered_amounts": extract_ordered_amounts(body),
        "contains_standard_boilerplate": contains_standard_boilerplate(body),
        "validation_flags": [],
    }
    enrichment.update(suppression)
    return enrichment


def merge_enrichment(metadata: dict[str, object], enrichment: dict[str, object]) -> dict[str, object]:
    merged = dict(metadata)
    for key, value in enrichment.items():
        if value not in (None, "", [], {}):
            merged[key] = value
    return merged


def extract_nztt_citation(body: str) -> str | None:
    match = re.search(
        r"\[\d{4}\][^\S\r\n]+NZTT(?:[^\S\r\n]+[A-Za-z][A-Za-z /'-]+)?[^\S\r\n]+\d[\d, ]*",
        body,
        flags=re.IGNORECASE,
    )
    return " ".join(match.group(0).replace("nztt", "NZTT").split()) if match else None


def extract_nztt_year(body: str) -> int | None:
    match = re.search(r"\[(20\d{2})\]\s+NZTT", body, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def extract_decision_date(body: str) -> str | None:
    prefix = body.split("Please read carefully:", 1)[0]
    tail = "\n".join(prefix.splitlines()[-30:])
    candidates = extract_long_dates(tail)
    if candidates:
        return candidates[-1]

    candidates = extract_standalone_long_dates(body)
    return candidates[-1] if candidates else None


def extract_long_dates(text: str) -> list[str]:
    month_names = (
        "January|February|March|April|May|June|July|August|"
        "September|October|November|December"
    )
    dates: list[str] = []
    for match in re.finditer(
        rf"\b([0-3]?\d\s+(?:{month_names})\s+20\d{{2}})\b",
        text,
    ):
        normalized = normalize_date(match.group(1))
        if normalized:
            dates.append(normalized)
    return dates


def extract_standalone_long_dates(text: str) -> list[str]:
    month_names = (
        "January|February|March|April|May|June|July|August|"
        "September|October|November|December"
    )
    dates: list[str] = []
    for match in re.finditer(
        rf"(?m)^\s*([0-3]?\d\s+(?:{month_names})\s+20\d{{2}})\s*$",
        text,
    ):
        normalized = normalize_date(match.group(1))
        if normalized:
            dates.append(normalized)
    return dates


def extract_tribunal_location(body: str) -> str | None:
    match = re.search(r"TENANCY\s+TRIBUNAL\s+AT\s+([A-Z][A-Z '\/-]+)", body)
    if not match:
        return None
    location = " ".join(match.group(1).split())
    location = re.split(r"\s{2,}|#", location)[0]
    return location.title()


def extract_statute_sections(body: str) -> list[str]:
    sections: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(
        r"\b(?:section|s)\.?\s+([0-9]+[A-Z]?(?:\([0-9A-Za-z]+\))*)",
        body,
        flags=re.IGNORECASE,
    ):
        section = match.group(1)
        if section not in seen:
            seen.add(section)
            sections.append(section)
    return sections


def extract_controlled_tags(lower_text: str) -> list[str]:
    tags: list[str] = []
    for tag, phrases in CONTROLLED_TAGS:
        if any(phrase in lower_text for phrase in phrases):
            tags.append(tag)
    return tags


def extract_ordered_amounts(body: str) -> list[dict[str, object]]:
    amounts: list[dict[str, object]] = []
    for match in re.finditer(r"\$\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", body):
        value = float(match.group(1).replace(",", ""))
        amounts.append({"amount": value, "currency": "NZD"})
    return amounts


def suppression_metadata(lower_text: str) -> dict[str, object]:
    if "no suppression orders apply" in lower_text:
        return {
            "suppression_status": "none",
            "suppression_order": False,
            "suppressed_fields": [],
            "privacy_sensitivity": "normal",
            "requires_redaction_check": False,
        }

    suppression_order = "suppression" in lower_text or "must not be published" in lower_text
    fields: list[str] = []
    if suppression_order:
        if "tenant" in lower_text and "name" in lower_text:
            fields.append("tenant_names")
        if "landlord" in lower_text and "name" in lower_text:
            fields.append("landlord_names")
        if "address" in lower_text:
            fields.append("tenancy_address")
    return {
        "suppression_status": "suppressed" if suppression_order else "unknown",
        "suppression_order": suppression_order,
        "suppressed_fields": fields,
        "privacy_sensitivity": "high" if suppression_order else "normal",
        "requires_redaction_check": suppression_order,
    }


def contains_standard_boilerplate(body: str) -> bool:
    boilerplate_terms = (
        "Rehearings",
        "Right of Appeal",
        "Enforcement",
        "How to enforce this order",
    )
    return any(term.lower() in body.lower() for term in boilerplate_terms)


def build_retrieval_documents(metadata: dict[str, object], body: str) -> list[RetrievalDocument]:
    documents: list[RetrievalDocument] = []
    source_text = body.strip()
    if source_text:
        documents.append(
            RetrievalDocument(
                text=source_text,
                metadata=retrieval_metadata(metadata, "source_text", generated=False),
            )
        )

    for view, text in generated_retrieval_texts(metadata):
        documents.append(
            RetrievalDocument(
                text=text,
                metadata=retrieval_metadata(metadata, view, generated=True),
            )
        )

    return documents


def retrieval_metadata(
    metadata: dict[str, object],
    retrieval_view: str,
    *,
    generated: bool,
) -> dict[str, object]:
    copied = dict(metadata)
    document_id = str(copied["document_id"])
    copied["canonical_document_id"] = document_id
    copied["retrieval_view"] = retrieval_view
    copied["generated"] = generated
    return copied


def generated_retrieval_texts(metadata: dict[str, object]) -> list[tuple[str, str]]:
    views: list[tuple[str, str]] = []
    case_summary = clean_text(metadata.get("case_summary"))
    if case_summary:
        views.append(("case_summary", case_summary))

    catchwords = list_value(metadata.get("catchwords"))
    if catchwords:
        views.append(("catchwords", "\n".join(catchwords)))

    questions = list_value(metadata.get("questions_answered"))
    if questions:
        views.append(("questions_answered", "\n".join(questions)))

    principles = format_legal_principles(metadata.get("legal_principles"))
    if principles:
        views.append(("legal_principles", principles))
    return views


def list_value(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def clean_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def format_legal_principles(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    lines: list[str] = []
    for item in value:
        if isinstance(item, dict):
            principle = clean_text(item.get("principle"))
            if not principle:
                continue
            confidence = clean_text(item.get("confidence"))
            source_section = clean_text(item.get("source_section"))
            details = ", ".join(
                part
                for part in (
                    f"confidence: {confidence}" if confidence else "",
                    f"source: {source_section}" if source_section else "",
                )
                if part
            )
            lines.append(f"{principle} ({details})" if details else principle)
        else:
            text = clean_text(item)
            if text:
                lines.append(text)
    return "\n".join(lines) or None
