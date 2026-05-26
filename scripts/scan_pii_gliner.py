from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from fyi_markdown import parse_markdown_document


DEFAULT_MODEL = "nvidia/gliner-PII"
DEFAULT_LABELS = (
    "person",
    "address",
    "email",
    "phone_number",
    "user_name",
    "date_of_birth",
    "national_id",
    "driver_license",
    "passport_number",
    "bank_account",
    "credit_card",
)
GLINER_TOKEN_RE = re.compile(r"\w+(?:[-_]\w+)*|\S")


@dataclass(frozen=True)
class TextChunk:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class PiiEntity:
    start: int
    end: int
    text: str
    label: str
    score: float


def chunk_text(
    text: str,
    chunk_chars: int,
    chunk_overlap: int,
    chunk_tokens: int = 300,
) -> list[TextChunk]:
    if chunk_chars <= 0:
        raise ValueError("chunk_chars must be greater than 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be 0 or greater")
    if chunk_overlap >= chunk_chars:
        raise ValueError("chunk_overlap must be smaller than chunk_chars")
    if chunk_tokens <= 0:
        raise ValueError("chunk_tokens must be greater than 0")
    if not text:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(text):
        char_end = min(len(text), start + chunk_chars)
        end = end_for_token_budget(text, start, char_end, chunk_tokens)
        chunks.append(TextChunk(start=start, end=end, text=text[start:end]))
        if end == len(text):
            break
        start = max(start + 1, end - chunk_overlap)
    return chunks


def end_for_token_budget(text: str, start: int, char_end: int, chunk_tokens: int) -> int:
    token_count = 0
    for match in GLINER_TOKEN_RE.finditer(text[start:char_end]):
        token_count += 1
        if token_count >= chunk_tokens:
            return start + match.end()
    return char_end


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


def prediction_to_entity(
    prediction: dict[str, Any],
    chunk: TextChunk,
    full_text: str,
) -> PiiEntity | None:
    label = str(prediction.get("label") or "").strip()
    if not label:
        return None
    try:
        relative_start = int(prediction["start"])
        relative_end = int(prediction["end"])
    except (KeyError, TypeError, ValueError):
        return None

    start = chunk.start + relative_start
    end = chunk.start + relative_end
    if start < 0 or end <= start or end > len(full_text):
        return None

    raw_score = prediction.get("score", 0.0)
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0

    predicted_text = prediction.get("text")
    text = str(predicted_text) if predicted_text else full_text[start:end]
    return PiiEntity(start=start, end=end, text=text, label=label, score=score)


def merge_entities(entities: Iterable[PiiEntity]) -> list[PiiEntity]:
    best_by_span: dict[tuple[int, int, str], PiiEntity] = {}
    for entity in entities:
        key = (entity.start, entity.end, entity.label)
        existing = best_by_span.get(key)
        if existing is None or entity.score > existing.score:
            best_by_span[key] = entity
    return sorted(best_by_span.values(), key=lambda item: (item.start, item.end, item.label))


def scan_text(
    model: Any,
    text: str,
    labels: Sequence[str],
    threshold: float,
    chunk_chars: int,
    chunk_overlap: int,
    chunk_tokens: int = 300,
) -> list[PiiEntity]:
    entities: list[PiiEntity] = []
    for chunk in chunk_text(
        text,
        chunk_chars=chunk_chars,
        chunk_overlap=chunk_overlap,
        chunk_tokens=chunk_tokens,
    ):
        predictions = model.predict_entities(chunk.text, labels, threshold=threshold)
        for prediction in predictions:
            entity = prediction_to_entity(prediction, chunk, text)
            if entity is not None:
                entities.append(entity)
    return merge_entities(entities)


def selected_non_overlapping_entities(entities: Sequence[PiiEntity]) -> list[PiiEntity]:
    selected: list[PiiEntity] = []
    for entity in sorted(
        entities,
        key=lambda item: (-(item.end - item.start), -item.score, item.start),
    ):
        if all(entity.end <= current.start or entity.start >= current.end for current in selected):
            selected.append(entity)
    return sorted(selected, key=lambda item: item.start)


def redact_text(text: str, entities: Sequence[PiiEntity]) -> str:
    redacted = text
    for entity in reversed(selected_non_overlapping_entities(entities)):
        token = f"[{entity.label.upper()}]"
        redacted = redacted[: entity.start] + token + redacted[entity.end :]
    return redacted


def scan_markdown_path(
    model: Any,
    path: Path,
    labels: Sequence[str],
    threshold: float,
    chunk_chars: int,
    chunk_overlap: int,
    chunk_tokens: int = 300,
    include_frontmatter: bool = False,
    include_redacted_text: bool = False,
) -> dict[str, Any]:
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    metadata, body = parse_markdown_document(raw_text)
    scanned_text = raw_text if include_frontmatter else body
    entities = scan_text(
        model,
        scanned_text,
        labels=labels,
        threshold=threshold,
        chunk_chars=chunk_chars,
        chunk_overlap=chunk_overlap,
        chunk_tokens=chunk_tokens,
    )

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
    if limit is not None:
        return paths[:limit]
    return paths


def load_gliner_model(model_name: str, device: str | None) -> Any:
    from gliner import GLiNER

    model = GLiNER.from_pretrained(model_name)
    if device and hasattr(model, "to"):
        model.to(device)
    return model


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
    finally:
        if output_path:
            output.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan markdown documents for PII spans with NVIDIA GLiNER-PII."
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
    parser.add_argument("--device", help="Optional torch device, for example cuda or cpu.")
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument(
        "--labels",
        action="append",
        help="Comma-separated labels to scan for. Can be passed more than once.",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--chunk-chars", type=int, default=3000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--chunk-tokens", type=int, default=300)
    parser.add_argument("--include-frontmatter", action="store_true")
    parser.add_argument("--include-redacted-text", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    labels = parse_labels(args.labels)
    paths = iter_markdown_paths(args.markdown_dir, args.glob, args.limit)
    model = load_gliner_model(args.model, args.device)
    summary: dict[str, Any] = {
        "model": args.model,
        "threshold": args.threshold,
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
                    model,
                    path,
                    labels=labels,
                    threshold=args.threshold,
                    chunk_chars=args.chunk_chars,
                    chunk_overlap=args.chunk_overlap,
                    chunk_tokens=args.chunk_tokens,
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
