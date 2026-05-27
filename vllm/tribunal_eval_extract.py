"""Extraction and scoring helpers for tribunal batch evals."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any


SCHEMA_FIELDS = [
    "citation",
    "application_number",
    "decision_date",
    "tribunal_location",
    "adjudicator",
    "applicant_name",
    "applicant_role",
    "respondent_name",
    "respondent_role",
    "tenancy_address",
    "has_name_redactions",
    "has_address_redactions",
    "total_award_nzd",
    "payable_by",
    "payable_to",
]
GENERATED_TEXT_FIELDS = ["case_summary", "applicant_story", "respondent_story", "neutral_fact_pattern"]
GENERATED_LIST_FIELDS = ["catchwords", "questions_answered", "claims_made", "remedies_sought", "llm_suggested_tags"]
GENERATED_PRINCIPLE_FIELDS = ["legal_principles"]
GENERATED_FIELDS = GENERATED_TEXT_FIELDS + GENERATED_LIST_FIELDS + GENERATED_PRINCIPLE_FIELDS

ROLE_VALUES = ["landlord", "tenant", "other"]
PAYABLE_VALUES = ["landlord", "tenant", "other", "none"]
JSON_SCHEMA_NAME = "tribunal_extraction"
PROMPT = """You extract structured metadata from a New Zealand Tenancy Tribunal decision.

Return only the JSON object required by the schema.
Rules:
- Copy names, placeholders, and addresses exactly as they appear in the decision.
- Use null when a value is not stated.
- Use JSON null, not the string "null".
- Use YYYY-MM-DD for decision_date.
- application_number is the main NZTT application number from the decision citation, not an internal file id and not an incorporated prior application number.
- Set has_name_redactions to true when any party name is replaced with a placeholder or suppression marker.
- Set has_address_redactions to true when the tenancy address is replaced with a placeholder or suppression marker.
- total_award_nzd must be the final payable amount ordered. Prefer the "Total payable by ... to ..." row, otherwise use the main "must pay" order, otherwise use a single clear total row.
- payable_by and payable_to must use landlord, tenant, other, or none.
"""

STOP_LABELS = {
    "applicant",
    "respondent",
    "tenancy address",
    "order",
    "reasons",
    "introduction",
    "suppression",
}


def strip_front_matter(markdown_text: str) -> str:
    if not markdown_text.startswith("---\n"):
        return markdown_text
    parts = markdown_text.split("---", 2)
    if len(parts) < 3:
        return markdown_text
    return parts[2].lstrip("\n")


def parse_front_matter(markdown_text: str) -> tuple[dict[str, Any], str]:
    if not markdown_text.startswith("---\n"):
        return {}, markdown_text
    end_index = markdown_text.find("\n---\n", 4)
    if end_index == -1:
        return {}, markdown_text
    raw_metadata = markdown_text[4:end_index]
    body = markdown_text[end_index + len("\n---\n") :]
    if body.startswith("\n"):
        body = body[1:]
    metadata: dict[str, Any] = {}
    for line in raw_metadata.splitlines():
        if not line.strip():
            continue
        key, separator, raw_value = line.partition(":")
        if not separator:
            raise ValueError(f"Malformed frontmatter line: {line!r}")
        metadata[key.strip()] = json.loads(raw_value.strip())
    return metadata, body


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


def normalize_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)
    return normalize_whitespace(str(value)).casefold()


def normalize_party_value(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = normalize_whitespace(value).casefold()
    if lowered in {"landlord", "tenant"}:
        return lowered
    if not lowered:
        return None
    return "other"


def line_to_role(value: str) -> str | None:
    lowered = normalize_whitespace(value).casefold()
    if lowered == "landlord":
        return "landlord"
    if lowered == "tenant":
        return "tenant"
    return None


def to_iso_date(value: str | None) -> str | None:
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d %B %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def approximate_token_count(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def has_meaningful_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(has_meaningful_value(item) for item in value)
    if isinstance(value, dict):
        return bool(value)
    return True


def is_placeholder_text(value: str | None) -> bool:
    if not value:
        return False
    lowered = value.casefold()
    return "[" in value and "]" in value or "suppressed" in lowered or lowered == "none"


def extract_citation(body: str) -> str | None:
    for raw_line in body.splitlines():
        line = normalize_whitespace(raw_line.strip())
        if "[20" not in line or "NZTT" not in line.upper():
            continue
        match = re.search(r"\[(20\d{2})\]\s+NZTT", line, flags=re.IGNORECASE)
        if not match:
            continue
        year = match.group(1)
        suffix = line[match.end() :].strip()
        tokens = suffix.split()
        location_tokens: list[str] = []
        number_token: str | None = None
        for token in tokens:
            cleaned = token.strip(",")
            if re.fullmatch(r"\d[\d,]*", cleaned):
                number_token = cleaned
                break
            location_tokens.append(cleaned)
        if not number_token:
            continue
        location = f" {' '.join(location_tokens)}" if location_tokens else ""
        return f"[{year}] NZTT{location} {number_token}"
    return None


def extract_signature(body: str) -> tuple[str | None, str | None]:
    matches = list(
        re.finditer(
            r"^(?P<adjudicator>[A-Z][A-Za-z .'\-]+?)\s+(?P<date>\d{1,2}\s+[A-Z][a-z]+\s+\d{4})$",
            body,
            flags=re.MULTILINE,
        )
    )
    if not matches:
        return None, None
    last = matches[-1]
    return normalize_whitespace(last.group("adjudicator")), to_iso_date(last.group("date"))


def extract_tribunal_location(body: str) -> str | None:
    lines = body.splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip().lstrip("#").strip()
        if not line or not line.upper().startswith("TENANCY TRIBUNAL"):
            continue
        line = line.split("|", 1)[0].strip()
        location = re.sub(r"^TENANCY TRIBUNAL(?:\s+AT)?\s*", "", line, flags=re.IGNORECASE).strip()
        location = location.lstrip("-").strip()
        if not location:
            for look_ahead in lines[index + 1 : index + 4]:
                candidate = look_ahead.strip().lstrip("#").strip()
                if not candidate or "NZTT" in candidate.upper():
                    continue
                if candidate.startswith("[") or "suppressed" in candidate.casefold():
                    return candidate
        return location or None
    return None


def normalized_label(line: str) -> str:
    return line.strip().lstrip("#").strip().rstrip(":").casefold()


def extract_labeled_block(body: str, label: str) -> str | None:
    lines = body.splitlines()
    target = label.casefold()
    collected: list[str] = []
    in_block = False
    for raw_line in lines:
        line = raw_line.strip()
        if not in_block:
            if normalized_label(line) == target:
                in_block = True
            continue
        if not line:
            if collected:
                collected.append("")
            continue
        if normalized_label(line) in STOP_LABELS or line.startswith("## "):
            break
        collected.append(line)
    if not collected:
        return None
    compact = [entry for entry in collected if entry]
    return normalize_whitespace(" ".join(compact)) or None


def extract_segment_lines(body: str, label: str) -> list[str]:
    lines = body.splitlines()
    target = label.casefold()
    in_block = False
    segment_lines: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not in_block:
            if normalized_label(line) == target:
                in_block = True
            continue
        if not line:
            continue
        if normalized_label(line) in STOP_LABELS or line.startswith("## "):
            break
        segment_lines.append(line)
    return segment_lines


def extract_party_details(body: str, label: str) -> tuple[str | None, str | None]:
    segment_lines = extract_segment_lines(body, label)
    role_lines = [line_to_role(line) for line in segment_lines if line_to_role(line)]
    name_lines = [line for line in segment_lines if not line_to_role(line)]
    role = role_lines[0] if role_lines else None
    return normalize_whitespace(" ".join(name_lines)) or None, role


def extract_party_blocks(body: str) -> tuple[tuple[str | None, str | None], tuple[str | None, str | None]]:
    applicant_segment = extract_segment_lines(body, "applicant")
    respondent_segment = extract_segment_lines(body, "respondent")
    applicant_roles = [line_to_role(line) for line in applicant_segment if line_to_role(line)]
    respondent_roles = [line_to_role(line) for line in respondent_segment if line_to_role(line)]
    applicant_names = [line for line in applicant_segment if not line_to_role(line)]
    respondent_names = [line for line in respondent_segment if not line_to_role(line)]
    applicant_role = applicant_roles[0] if applicant_roles else None
    respondent_role = respondent_roles[0] if respondent_roles else None
    if applicant_role is None and len(respondent_roles) >= 2:
        applicant_role = respondent_roles[0]
        respondent_role = respondent_roles[1]
    return (
        normalize_whitespace(" ".join(applicant_names)) or None,
        applicant_role,
    ), (
        normalize_whitespace(" ".join(respondent_names)) or None,
        respondent_role,
    )


def extract_monetary_amounts(line: str) -> list[float]:
    return [float(match.replace(",", "")) for match in re.findall(r"\$([\d,]+(?:\.\d{2})?)", line)]


def extract_main_monetary_order(body: str) -> float | None:
    for raw_line in body.splitlines():
        line = normalize_whitespace(raw_line.strip())
        if not line:
            continue
        if "must pay" not in line.casefold() and "is to pay the bond" not in line.casefold():
            continue
        amounts = extract_monetary_amounts(line)
        if amounts:
            return amounts[-1]
    return None


def extract_total_award(body: str) -> float | None:
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if "total payable by" not in line.casefold():
            continue
        amounts = extract_monetary_amounts(line)
        if amounts:
            return amounts[-1]
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if "total award" not in line.casefold():
            continue
        amounts = extract_monetary_amounts(line)
        if amounts:
            return max(amounts)
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if "net award" not in line.casefold():
            continue
        amounts = extract_monetary_amounts(line)
        if amounts:
            return amounts[-1]
    return extract_main_monetary_order(body)


def extract_payable_direction(body: str) -> tuple[str | None, str | None]:
    match = re.search(
        r"Total payable by\s+([A-Za-z ]+?)\s+to\s+([A-Za-z ]+?)\s*\|",
        body,
        flags=re.IGNORECASE,
    )
    if match:
        return normalize_party_value(match.group(1)), normalize_party_value(match.group(2))
    for raw_line in body.splitlines():
        line = normalize_whitespace(raw_line.strip())
        order_match = re.search(
            r"must pay\s+(?:\[The )?(landlord|tenant)[^\]]*\]?",
            line,
            flags=re.IGNORECASE,
        )
        if order_match:
            payer = "tenant" if "tenant must pay" in line.casefold() else "landlord"
            return payer, normalize_party_value(order_match.group(1))
        if "bond centre is to pay the bond" in line.casefold():
            payee_match = re.search(r"to\s+(?:\[The )?(landlord|tenant)[^\]]*\]?", line, flags=re.IGNORECASE)
            return "other", normalize_party_value(payee_match.group(1)) if payee_match else None
    return None, None


def has_name_redactions(body: str, applicant_name: str | None, respondent_name: str | None) -> bool:
    if is_placeholder_text(applicant_name) or is_placeholder_text(respondent_name):
        return True
    return bool(
        re.search(
            r"\[(?:the )?(?:applicant|respondent|landlord|tenant|owner|property manager)[^\]]*\]",
            body,
            flags=re.IGNORECASE,
        )
    )


def has_address_redactions(tenancy_address: str | None) -> bool:
    return is_placeholder_text(tenancy_address)


def application_number_from_citation(citation: str | None) -> str | None:
    if not citation:
        return None
    match = re.search(r"(\d[\d,]*)$", citation)
    if not match:
        return None
    return match.group(1).replace(",", "")


def extract_gold_case_data(markdown_text: str, sidecar: dict[str, Any]) -> dict[str, Any]:
    body = strip_front_matter(markdown_text)
    (applicant_name, applicant_role), (respondent_name, respondent_role) = extract_party_blocks(body)
    tenancy_address = extract_labeled_block(body, "tenancy address")
    adjudicator, signature_date = extract_signature(body)
    citation = extract_citation(body)
    payable_by, payable_to = extract_payable_direction(body)
    return {
        "citation": citation,
        "application_number": application_number_from_citation(citation) or sidecar.get("application_number"),
        "decision_date": signature_date,
        "tribunal_location": extract_tribunal_location(body),
        "adjudicator": adjudicator,
        "applicant_name": applicant_name,
        "applicant_role": applicant_role,
        "respondent_name": respondent_name,
        "respondent_role": respondent_role,
        "tenancy_address": tenancy_address,
        "has_name_redactions": has_name_redactions(body, applicant_name, respondent_name),
        "has_address_redactions": has_address_redactions(tenancy_address),
        "total_award_nzd": extract_total_award(body),
        "payable_by": payable_by,
        "payable_to": payable_to,
    }


def extract_teacher_case_data(markdown_text: str) -> dict[str, Any]:
    try:
        metadata, _ = parse_front_matter(markdown_text)
    except (ValueError, json.JSONDecodeError):
        return {}
    teacher_fields: dict[str, Any] = {}
    for field in GENERATED_FIELDS:
        value = metadata.get(field)
        if has_meaningful_value(value):
            teacher_fields[field] = value
    return teacher_fields


def schema_property(definition: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [definition, {"type": "null"}]}


def build_response_schema() -> dict[str, Any]:
    properties = {
        "citation": schema_property({"type": "string"}),
        "application_number": schema_property({"type": "string"}),
        "decision_date": schema_property({"type": "string"}),
        "tribunal_location": schema_property({"type": "string"}),
        "adjudicator": schema_property({"type": "string"}),
        "applicant_name": schema_property({"type": "string"}),
        "applicant_role": schema_property({"type": "string", "enum": ROLE_VALUES}),
        "respondent_name": schema_property({"type": "string"}),
        "respondent_role": schema_property({"type": "string", "enum": ROLE_VALUES}),
        "tenancy_address": schema_property({"type": "string"}),
        "has_name_redactions": {"type": "boolean"},
        "has_address_redactions": {"type": "boolean"},
        "total_award_nzd": schema_property({"type": "number"}),
        "payable_by": schema_property({"type": "string", "enum": PAYABLE_VALUES}),
        "payable_to": schema_property({"type": "string", "enum": PAYABLE_VALUES}),
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def build_prompt_content(markdown_body: str) -> str:
    return f"{PROMPT}\n{markdown_body}\n"


def extract_json_content(content: str) -> dict[str, Any]:
    content = content.strip()
    if not content:
        raise ValueError("Empty model response")
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(content[start : end + 1])


def clean_prediction_values(value: Any) -> Any:
    if isinstance(value, str) and value.strip().casefold() == "null":
        return None
    if isinstance(value, list):
        return [clean_prediction_values(item) for item in value]
    if isinstance(value, dict):
        return {key: clean_prediction_values(item) for key, item in value.items()}
    return value


def tokenize_text(value: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_string(value))


def overlap_scores(gold_value: Any, predicted_value: Any) -> tuple[float, float, float]:
    gold_tokens = Counter(tokenize_text(gold_value))
    predicted_tokens = Counter(tokenize_text(predicted_value))
    if not gold_tokens:
        return (1.0, 1.0, 1.0) if not predicted_tokens else (0.0, 0.0, 0.0)
    if not predicted_tokens:
        return 0.0, 0.0, 0.0
    overlap = sum((gold_tokens & predicted_tokens).values())
    precision = overlap / sum(predicted_tokens.values())
    recall = overlap / sum(gold_tokens.values())
    if not precision and not recall:
        return 0.0, 0.0, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def string_items(value: Any) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    items: list[str] = []
    for item in raw_items:
        text = normalize_whitespace(str(item)).strip()
        if text:
            items.append(text)
    return items


def legal_principle_items(value: Any) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    items: list[str] = []
    for item in raw_items:
        principle = item.get("principle") if isinstance(item, dict) else item
        text = normalize_whitespace(str(principle)).strip()
        if text:
            items.append(text)
    return items


def exact_item_signature(items: list[str]) -> list[str]:
    return sorted(normalize_string(item) for item in items)


def greedy_list_overlap_scores(gold_items: list[str], predicted_items: list[str]) -> tuple[float, float, float]:
    if not gold_items:
        return (1.0, 1.0, 1.0) if not predicted_items else (0.0, 0.0, 0.0)
    if not predicted_items:
        return 0.0, 0.0, 0.0
    pairs: list[tuple[float, int, int]] = []
    for gold_index, gold_item in enumerate(gold_items):
        for predicted_index, predicted_item in enumerate(predicted_items):
            _, _, f1 = overlap_scores(gold_item, predicted_item)
            if f1:
                pairs.append((f1, gold_index, predicted_index))
    pairs.sort(reverse=True)
    matched_score = 0.0
    used_gold: set[int] = set()
    used_predicted: set[int] = set()
    for f1, gold_index, predicted_index in pairs:
        if gold_index in used_gold or predicted_index in used_predicted:
            continue
        used_gold.add(gold_index)
        used_predicted.add(predicted_index)
        matched_score += f1
    precision = matched_score / len(predicted_items)
    recall = matched_score / len(gold_items)
    if not precision and not recall:
        return 0.0, 0.0, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def generated_field_score(field: str, gold_value: Any, predicted_value: Any) -> dict[str, Any] | None:
    if field in GENERATED_TEXT_FIELDS:
        precision, recall, f1 = overlap_scores(gold_value, predicted_value)
        return {
            "predicted": has_meaningful_value(predicted_value),
            "exact": normalize_string(gold_value) == normalize_string(predicted_value),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    if field in GENERATED_LIST_FIELDS:
        gold_items = string_items(gold_value)
        predicted_items = string_items(predicted_value)
        precision, recall, f1 = greedy_list_overlap_scores(gold_items, predicted_items)
        return {
            "predicted": bool(predicted_items),
            "exact": exact_item_signature(gold_items) == exact_item_signature(predicted_items),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    if field in GENERATED_PRINCIPLE_FIELDS:
        gold_items = legal_principle_items(gold_value)
        predicted_items = legal_principle_items(predicted_value)
        precision, recall, f1 = greedy_list_overlap_scores(gold_items, predicted_items)
        return {
            "predicted": bool(predicted_items),
            "exact": exact_item_signature(gold_items) == exact_item_signature(predicted_items),
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
    return None


def normalize_redacted_name(value: Any) -> str:
    text = normalize_string(value)
    if not text:
        return text
    if "[" not in str(value) and "suppressed" not in str(value).casefold():
        return text
    lowered = str(value).casefold()
    if "landlord" in lowered or "applicant" in lowered:
        return "__redacted_landlord__"
    if "tenant" in lowered or "respondent" in lowered:
        return "__redacted_tenant__"
    return "__redacted__"


def normalize_tribunal_location(value: Any) -> str:
    text = normalize_string(value)
    if not text:
        return ""
    raw = str(value).strip().casefold()
    if "event location suppressed" in raw:
        return "__suppressed_location__"
    if raw in {"remote", "remote location"}:
        return "remote location"
    return text.strip("[]")


def values_match(field: str, gold_value: Any, predicted_value: Any) -> bool:
    if gold_value is None:
        return predicted_value is None
    if field in {"has_name_redactions", "has_address_redactions"}:
        return gold_value is predicted_value
    if field == "total_award_nzd":
        if predicted_value is None:
            return False
        try:
            return abs(float(gold_value) - float(predicted_value)) < 0.005
        except (TypeError, ValueError):
            return False
    if field in {"applicant_role", "respondent_role", "payable_by", "payable_to"}:
        return normalize_party_value(str(gold_value)) == normalize_party_value(str(predicted_value))
    if field == "citation":
        return extract_citation(str(gold_value)) == extract_citation(str(predicted_value))
    if field == "tribunal_location":
        return normalize_tribunal_location(gold_value) == normalize_tribunal_location(predicted_value)
    if field in {"applicant_name", "respondent_name"}:
        return normalize_redacted_name(gold_value) == normalize_redacted_name(predicted_value)
    return normalize_string(gold_value) == normalize_string(predicted_value)
