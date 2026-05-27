from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from fyi_markdown import parse_markdown_document


DEFAULT_MODEL = "openai/privacy-filter"
DEFAULT_LABELS = (
    "account_number",
    "private_address",
    "private_date",
    "private_email",
    "private_person",
    "private_phone",
    "private_url",
    "secret",
)


@dataclass(frozen=True)
class PrivacyEntity:
    start: int
    end: int
    text: str
    label: str
    score: float


def trim_entity_offsets(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def prediction_to_entity(prediction: dict[str, Any], text: str) -> PrivacyEntity | None:
    raw_label = prediction.get("entity_group") or prediction.get("entity")
    if not raw_label:
        return None
    try:
        start = int(prediction["start"])
        end = int(prediction["end"])
    except (KeyError, TypeError, ValueError):
        return None

    start, end = trim_entity_offsets(text, start, end)
    if start < 0 or end <= start or end > len(text):
        return None

    try:
        score = float(prediction.get("score", 0.0))
    except (TypeError, ValueError):
        score = 0.0

    label = str(raw_label).removeprefix("B-").removeprefix("I-").removeprefix("E-").removeprefix("S-")
    return PrivacyEntity(start=start, end=end, text=text[start:end], label=label, score=score)


def merge_adjacent_entities(entities: Sequence[PrivacyEntity], text: str) -> list[PrivacyEntity]:
    merged: list[PrivacyEntity] = []
    for entity in sorted(entities, key=lambda item: (item.start, item.end, item.label)):
        if not merged:
            merged.append(entity)
            continue

        previous = merged[-1]
        gap = text[previous.end : entity.start]
        if previous.label == entity.label and gap.strip() == "":
            merged[-1] = PrivacyEntity(
                start=previous.start,
                end=entity.end,
                text=text[previous.start : entity.end],
                label=previous.label,
                score=min(previous.score, entity.score),
            )
        else:
            merged.append(entity)
    return merged


def filter_entities(entities: Sequence[PrivacyEntity], labels: Sequence[str]) -> list[PrivacyEntity]:
    allowed = set(labels)
    return [entity for entity in entities if entity.label in allowed]


def scan_text(classifier: Any, text: str, labels: Sequence[str]) -> list[PrivacyEntity]:
    predictions = classifier(text)
    entities = [entity for row in predictions if (entity := prediction_to_entity(row, text))]
    return filter_entities(merge_adjacent_entities(entities, text), labels)


def selected_non_overlapping_entities(entities: Sequence[PrivacyEntity]) -> list[PrivacyEntity]:
    selected: list[PrivacyEntity] = []
    for entity in sorted(
        entities,
        key=lambda item: (-(item.end - item.start), -item.score, item.start),
    ):
        if all(entity.end <= current.start or entity.start >= current.end for current in selected):
            selected.append(entity)
    return sorted(selected, key=lambda item: item.start)


def redact_text(text: str, entities: Sequence[PrivacyEntity]) -> str:
    redacted = text
    for entity in reversed(selected_non_overlapping_entities(entities)):
        token = f"[{entity.label.upper()}]"
        redacted = redacted[: entity.start] + token + redacted[entity.end :]
    return redacted


def scan_markdown_path(
    classifier: Any,
    path: Path,
    labels: Sequence[str],
    include_frontmatter: bool = False,
    include_redacted_text: bool = False,
) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    metadata, body = parse_markdown_document(raw_text)
    scanned_text = raw_text if include_frontmatter else body
    entities = scan_text(classifier, scanned_text, labels=labels)

    record: dict[str, Any] = {
        "path": str(path),
        "document_id": metadata.get("document_id"),
        "source": metadata.get("source"),
        "source_url": metadata.get("source_url"),
        "suppression_status": metadata.get("suppression_status"),
        "requires_redaction_check": metadata.get("requires_redaction_check"),
        "scan_scope": "document" if include_frontmatter else "body",
        "entity_count": len(entities),
        "entities": [asdict(entity) for entity in entities],
    }
    if include_redacted_text:
        record["redacted_text"] = redact_text(scanned_text, entities)
    return record


def iter_markdown_paths(markdown_dir: Path, glob_pattern: str, limit: int | None) -> list[Path]:
    paths = sorted(path for path in markdown_dir.glob(glob_pattern) if path.is_file())
    return paths[:limit] if limit is not None else paths


def parse_labels(values: Sequence[str] | None) -> list[str]:
    if not values:
        return list(DEFAULT_LABELS)

    labels: list[str] = []
    seen: set[str] = set()
    for value in values:
        for raw_label in value.split(","):
            label = raw_label.strip()
            if label and label not in seen:
                labels.append(label)
                seen.add(label)
    if not labels:
        raise ValueError("at least one label is required")
    return labels


def load_classifier(model_name: str, device_map: str, dtype: str) -> Any:
    from transformers import pipeline

    return pipeline(
        task="token-classification",
        model=model_name,
        aggregation_strategy="simple",
        device_map=device_map,
        dtype=dtype,
    )


def summarize_record(summary: dict[str, Any], record: dict[str, Any]) -> None:
    summary["documents_scanned"] += 1
    entities = record.get("entities") or []
    if entities:
        summary["documents_with_entities"] += 1
    summary["entity_count"] += len(entities)
    for entity in entities:
        label = str(entity.get("label") or "")
        if label:
            summary["label_counts"][label] = summary["label_counts"].get(label, 0) + 1


def write_jsonl(records: Iterable[dict[str, Any]], output_path: Path | None) -> None:
    output = output_path.open("w", encoding="utf-8") if output_path else sys.stdout
    try:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            output.flush()
    finally:
        if output_path:
            output.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan markdown documents with OpenAI Privacy Filter."
    )
    parser.add_argument(
        "--markdown-dir",
        type=Path,
        default=Path("storage/justice/tenancy/markdown_docling"),
    )
    parser.add_argument("--glob", default="*.md", help="Markdown glob inside --markdown-dir.")
    parser.add_argument("--output-jsonl", type=Path, help="Write per-document scan records.")
    parser.add_argument("--summary-json", type=Path, help="Write aggregate scan counts.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--dtype", default="auto")
    parser.add_argument("--labels", action="append", help="Comma-separated labels to keep.")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--include-frontmatter", action="store_true")
    parser.add_argument("--include-redacted-text", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    labels = parse_labels(args.labels)
    paths = iter_markdown_paths(args.markdown_dir, args.glob, args.limit)
    classifier = load_classifier(args.model, args.device_map, args.dtype)
    summary: dict[str, Any] = {
        "model": args.model,
        "labels": labels,
        "scan_scope": "document" if args.include_frontmatter else "body",
        "documents_requested": len(paths),
        "documents_scanned": 0,
        "documents_with_entities": 0,
        "documents_failed": 0,
        "entity_count": 0,
        "label_counts": {},
    }

    def records() -> Iterable[dict[str, Any]]:
        for path in paths:
            try:
                record = scan_markdown_path(
                    classifier,
                    path,
                    labels=labels,
                    include_frontmatter=args.include_frontmatter,
                    include_redacted_text=args.include_redacted_text,
                )
            except Exception as exc:  # noqa: BLE001
                summary["documents_failed"] += 1
                record = {"path": str(path), "error": type(exc).__name__, "message": str(exc)}
            else:
                summarize_record(summary, record)
            yield record

    write_jsonl(records(), args.output_jsonl)
    if args.summary_json:
        args.summary_json.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 1 if summary["documents_failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
