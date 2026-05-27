"""Batch runner and CLI support for tribunal structured extraction evals."""

from __future__ import annotations

import argparse
import json
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

from vllm.tribunal_eval_extract import (
    GENERATED_FIELDS,
    JSON_SCHEMA_NAME,
    SCHEMA_FIELDS,
    application_number_from_citation,
    approximate_token_count,
    build_prompt_content,
    build_response_schema,
    clean_prediction_values,
    extract_citation,
    extract_gold_case_data,
    extract_json_content,
    parse_front_matter,
    extract_teacher_case_data,
    generated_field_score,
    strip_front_matter,
    values_match,
)
from vllm.tribunal_eval_schema import validate_response_schema_object

DEFAULT_MARKDOWN_DIR = Path("storage/justice/tenancy/markdown_docling")
DEFAULT_SIDECAR_DIR = Path("justice/data/tenancy/pdfs")
DEFAULT_OUTPUT_DIR = Path("vllm/results")
DEFAULT_BASE_URL = "http://192.168.88.96:8001"
DEFAULT_MODEL = "RedHatAI/Qwen3.6-35B-A3B-NVFP4"


@dataclass(slots=True)
class CaseRecord:
    order_id: str
    markdown_path: str
    sidecar_path: str
    markdown_text: str
    sidecar: dict[str, Any]
    gold_fields: dict[str, Any]
    approximate_tokens: int
    redacted: bool
    teacher_fields: dict[str, Any] = dataclass_field(default_factory=dict)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--sidecar-dir", type=Path, default=DEFAULT_SIDECAR_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--case-count", type=int, default=48)
    parser.add_argument("--target-batch-tokens", type=int, default=None)
    parser.add_argument("--target-prompt-tokens", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-tokens", type=int, default=320)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--run-name", default=None)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--thinking-token-budget", type=int, default=None)
    parser.add_argument("--no-balanced-redactions", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_case_record(markdown_path: Path, sidecar_path: Path) -> CaseRecord:
    markdown_text = markdown_path.read_text(encoding="utf-8", errors="replace")
    body = strip_front_matter(markdown_text)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    gold_fields = extract_gold_case_data(markdown_text=markdown_text, sidecar=sidecar)
    teacher_fields = extract_teacher_case_data(markdown_text)
    prompt_text = build_prompt_content(body)
    redacted = (
        gold_fields["has_name_redactions"]
        or gold_fields["has_address_redactions"]
        or "redacted" in str(sidecar.get("pdf_url", "")).casefold()
    )
    return CaseRecord(
        order_id=sidecar_path.stem,
        markdown_path=str(markdown_path),
        sidecar_path=str(sidecar_path),
        markdown_text=body,
        sidecar=sidecar,
        gold_fields=gold_fields,
        approximate_tokens=approximate_token_count(prompt_text),
        redacted=redacted,
        teacher_fields=teacher_fields,
    )


def order_id_from_markdown(markdown_path: Path, metadata: dict[str, Any]) -> str:
    tenancy_order_id = metadata.get("tenancy_order_id")
    if tenancy_order_id:
        return str(tenancy_order_id)
    document_id = metadata.get("document_id")
    if isinstance(document_id, str) and document_id.startswith("doc_justice_tenancy_"):
        return document_id.removeprefix("doc_justice_tenancy_")
    return markdown_path.stem.removeprefix("doc_justice_tenancy_")


def load_markdown_only_record(markdown_path: Path) -> CaseRecord:
    markdown_text = markdown_path.read_text(encoding="utf-8", errors="replace")
    metadata, body = parse_front_matter(markdown_text)
    prompt_text = build_prompt_content(body)
    gold_fields = extract_gold_case_data(markdown_text=markdown_text, sidecar={})
    teacher_fields = extract_teacher_case_data(markdown_text)
    redacted = gold_fields["has_name_redactions"] or gold_fields["has_address_redactions"]
    return CaseRecord(
        order_id=order_id_from_markdown(markdown_path, metadata),
        markdown_path=str(markdown_path),
        sidecar_path="",
        markdown_text=body,
        sidecar={},
        gold_fields=gold_fields,
        approximate_tokens=approximate_token_count(prompt_text),
        redacted=redacted,
        teacher_fields=teacher_fields,
    )


def load_candidates(markdown_dir: Path, sidecar_dir: Path) -> list[CaseRecord]:
    candidates: list[CaseRecord] = []
    for sidecar_path in sorted(sidecar_dir.glob("*.json")):
        order_id = sidecar_path.stem
        markdown_path = markdown_dir / f"doc_justice_tenancy_{order_id}.md"
        if not markdown_path.exists():
            continue
        try:
            candidates.append(load_case_record(markdown_path=markdown_path, sidecar_path=sidecar_path))
        except json.JSONDecodeError:
            continue
    if not candidates:
        raise FileNotFoundError("No paired tribunal markdown and sidecar files were found.")
    return candidates


def load_markdown_candidates(markdown_dir: Path) -> list[CaseRecord]:
    candidates: list[CaseRecord] = []
    for markdown_path in sorted(markdown_dir.glob("*.md")):
        candidates.append(load_markdown_only_record(markdown_path))
    if not candidates:
        raise FileNotFoundError("No tribunal markdown files were found.")
    return candidates


def interleave_redacted(candidates: list[CaseRecord], rng: random.Random) -> list[CaseRecord]:
    redacted = [case for case in candidates if case.redacted]
    non_redacted = [case for case in candidates if not case.redacted]
    rng.shuffle(redacted)
    rng.shuffle(non_redacted)
    ordered: list[CaseRecord] = []
    while redacted or non_redacted:
        if redacted:
            ordered.append(redacted.pop())
        if non_redacted:
            ordered.append(non_redacted.pop())
    return ordered


def order_candidates(candidates: list[CaseRecord], seed: int, balanced_redactions: bool) -> list[CaseRecord]:
    rng = random.Random(seed)
    if balanced_redactions:
        return interleave_redacted(candidates, rng)
    ordered = candidates[:]
    rng.shuffle(ordered)
    return ordered


def select_cases(
    ordered: list[CaseRecord],
    case_count: int,
    target_batch_tokens: int | None,
    thinking_token_budget: int | None,
) -> list[CaseRecord]:
    selected: list[CaseRecord] = []
    batch_tokens = 0
    for case in ordered:
        reserved_tokens = reserved_case_tokens(case, thinking_token_budget)
        if case_count and len(selected) >= case_count:
            break
        if target_batch_tokens and selected and batch_tokens + reserved_tokens > target_batch_tokens:
            break
        selected.append(case)
        batch_tokens += reserved_tokens
    return selected


def discover_cases(
    markdown_dir: Path,
    sidecar_dir: Path,
    case_count: int,
    target_batch_tokens: int | None,
    seed: int,
    balanced_redactions: bool,
    thinking_token_budget: int | None,
) -> list[CaseRecord]:
    candidates = load_candidates(markdown_dir=markdown_dir, sidecar_dir=sidecar_dir)
    ordered = order_candidates(candidates=candidates, seed=seed, balanced_redactions=balanced_redactions)
    return select_cases(
        ordered=ordered,
        case_count=case_count,
        target_batch_tokens=target_batch_tokens,
        thinking_token_budget=thinking_token_budget,
    )


def reserved_case_tokens(case: CaseRecord, thinking_token_budget: int | None) -> int:
    return case.approximate_tokens + max(0, thinking_token_budget or 0)


def build_case_batches(
    ordered: list[CaseRecord],
    max_cases_per_batch: int,
    target_batch_tokens: int | None,
    thinking_token_budget: int | None,
) -> list[list[CaseRecord]]:
    remaining = ordered[:]
    batches: list[list[CaseRecord]] = []
    while remaining:
        batch = select_cases(
            ordered=remaining,
            case_count=max_cases_per_batch,
            target_batch_tokens=target_batch_tokens,
            thinking_token_budget=thinking_token_budget,
        )
        if not batch:
            raise ValueError("Batch planning produced an empty batch.")
        batches.append(batch)
        remaining = remaining[len(batch) :]
    return batches


def build_payload(
    *,
    model: str,
    cases: list[CaseRecord],
    temperature: float,
    max_tokens: int,
    enable_thinking: bool,
    thinking_token_budget: int | None,
) -> dict[str, Any]:
    messages = [
        [{"role": "user", "content": build_prompt_content(case.markdown_text)}]
        for case in cases
    ]
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": enable_thinking},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": JSON_SCHEMA_NAME,
                "strict": True,
                "schema": build_response_schema(),
            },
        },
    }
    if thinking_token_budget is not None:
        payload["thinking_token_budget"] = thinking_token_budget
    return payload


def post_json(url: str, payload: dict[str, Any], timeout_seconds: int) -> tuple[int, bytes, float]:
    raw_payload = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw_payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started_at = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read()
            status = response.status
    except urllib.error.HTTPError as exc:
        body = exc.read()
        status = exc.code
    return status, body, time.time() - started_at


def parse_predictions(cases: list[CaseRecord], response_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    predictions: dict[str, dict[str, Any]] = {}
    for choice in response_json.get("choices", []):
        index = choice.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(cases):
            continue
        content = choice.get("message", {}).get("content", "")
        try:
            parsed = clean_prediction_values(extract_json_content(content))
            if not parsed.get("application_number") and parsed.get("citation"):
                citation = extract_citation(str(parsed["citation"]))
                parsed["application_number"] = application_number_from_citation(citation)
        except (ValueError, json.JSONDecodeError):
            parsed = {"_parse_error": content}
        predictions[cases[index].order_id] = parsed
    return predictions


def build_generated_field_totals() -> dict[str, dict[str, Any]]:
    return {
        field: {
            "scored": 0,
            "predicted": 0,
            "exact": 0,
            "precision_sum": 0.0,
            "recall_sum": 0.0,
            "f1_sum": 0.0,
        }
        for field in GENERATED_FIELDS
    }


def round_score_value(value: Any) -> Any:
    return round(value, 4) if isinstance(value, float) else value


def build_schema_totals() -> dict[str, Any]:
    return {
        "parse_success_cases": 0,
        "schema_valid_cases": 0,
        "parse_error_cases": 0,
        "missing_prediction_cases": 0,
        "error_counts": {
            "missing_required": 0,
            "type": 0,
            "enum": 0,
            "extra_property": 0,
        },
    }


def summarize_schema_totals(schema_totals: dict[str, Any], cases: list[CaseRecord]) -> dict[str, Any]:
    case_count = len(cases)
    return {
        "cases": case_count,
        "json_parse_success_cases": schema_totals["parse_success_cases"],
        "json_parse_success_rate": round(schema_totals["parse_success_cases"] / case_count, 4) if case_count else None,
        "schema_valid_cases": schema_totals["schema_valid_cases"],
        "schema_valid_rate": round(schema_totals["schema_valid_cases"] / case_count, 4) if case_count else None,
        "parse_error_cases": schema_totals["parse_error_cases"],
        "missing_prediction_cases": schema_totals["missing_prediction_cases"],
        "error_counts": schema_totals["error_counts"],
    }


def validate_case_prediction(case: CaseRecord, predictions: dict[str, dict[str, Any]]) -> tuple[bool, list[str]]:
    prediction = predictions.get(case.order_id)
    if prediction is None:
        return False, ["missing_prediction"]
    if "_parse_error" in prediction:
        return False, ["parse_error"]
    return True, validate_response_schema_object(prediction)


def update_schema_totals(schema_totals: dict[str, Any], schema_errors: list[str], parse_success: bool) -> None:
    if parse_success:
        schema_totals["parse_success_cases"] += 1
    else:
        if "missing_prediction" in schema_errors:
            schema_totals["missing_prediction_cases"] += 1
        else:
            schema_totals["parse_error_cases"] += 1
    if not schema_errors:
        schema_totals["schema_valid_cases"] += 1
    for error in schema_errors:
        category = error.split(":", 1)[0]
        if category in schema_totals["error_counts"]:
            schema_totals["error_counts"][category] += 1


def summarize_generated_fields(
    field_totals: dict[str, dict[str, Any]],
    total_scored: int,
    total_predicted: int,
    total_exact: int,
    precision_sum: float,
    recall_sum: float,
    f1_sum: float,
) -> dict[str, Any]:
    field_summary = {
        field: {
            "scored": totals["scored"],
            "predicted_field_instances": totals["predicted"],
            "exact_matches": totals["exact"],
            "exact_accuracy": round(totals["exact"] / totals["scored"], 4) if totals["scored"] else None,
            "average_precision": round(totals["precision_sum"] / totals["scored"], 4) if totals["scored"] else None,
            "average_recall": round(totals["recall_sum"] / totals["scored"], 4) if totals["scored"] else None,
            "average_f1": round(totals["f1_sum"] / totals["scored"], 4) if totals["scored"] else None,
        }
        for field, totals in field_totals.items()
    }
    overall = {
        "field_instances": total_scored,
        "predicted_field_instances": total_predicted,
        "exact_matches": total_exact,
        "exact_accuracy": round(total_exact / total_scored, 4) if total_scored else None,
        "average_precision": round(precision_sum / total_scored, 4) if total_scored else None,
        "average_recall": round(recall_sum / total_scored, 4) if total_scored else None,
        "average_f1": round(f1_sum / total_scored, 4) if total_scored else None,
    }
    return {
        "reference": "minimax_frontmatter",
        "overall": overall,
        "fields": field_summary,
    }


def score_predictions(cases: list[CaseRecord], predictions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    field_totals = {field: {"correct": 0, "scored": 0} for field in SCHEMA_FIELDS}
    generated_totals = build_generated_field_totals()
    schema_totals = build_schema_totals()
    case_results: list[dict[str, Any]] = []
    fully_correct_cases = 0
    generated_scored = 0
    generated_predicted = 0
    generated_exact = 0
    generated_precision_sum = 0.0
    generated_recall_sum = 0.0
    generated_f1_sum = 0.0
    for case in cases:
        predicted = predictions.get(case.order_id, {})
        parse_success, schema_errors = validate_case_prediction(case, predictions)
        update_schema_totals(schema_totals, schema_errors, parse_success)
        mismatched_fields: list[str] = []
        matched_fields = 0
        scored_fields = 0
        generated_field_scores: dict[str, dict[str, Any]] = {}
        for field in SCHEMA_FIELDS:
            gold_value = case.gold_fields.get(field)
            if gold_value is None:
                continue
            scored_fields += 1
            field_totals[field]["scored"] += 1
            if values_match(field, gold_value, predicted.get(field)):
                matched_fields += 1
                field_totals[field]["correct"] += 1
            else:
                mismatched_fields.append(field)
        for field, gold_value in case.teacher_fields.items():
            score = generated_field_score(field, gold_value, predicted.get(field))
            if score is None:
                continue
            generated_scored += 1
            generated_totals[field]["scored"] += 1
            if score["predicted"]:
                generated_predicted += 1
                generated_totals[field]["predicted"] += 1
            if score["exact"]:
                generated_exact += 1
                generated_totals[field]["exact"] += 1
            generated_precision_sum += score["precision"]
            generated_recall_sum += score["recall"]
            generated_f1_sum += score["f1"]
            generated_totals[field]["precision_sum"] += score["precision"]
            generated_totals[field]["recall_sum"] += score["recall"]
            generated_totals[field]["f1_sum"] += score["f1"]
            generated_field_scores[field] = {
                key: round_score_value(value)
                for key, value in score.items()
                if key != "predicted"
            }
        if scored_fields and matched_fields == scored_fields:
            fully_correct_cases += 1
        case_results.append(
            {
                "order_id": case.order_id,
                "redacted": case.redacted,
                "matched_fields": matched_fields,
                "scored_fields": scored_fields,
                "mismatched_fields": mismatched_fields,
                "schema_valid": not schema_errors,
                "schema_errors": schema_errors,
                "generated_field_scores": generated_field_scores,
            }
        )
    field_summary = {
        field: {
            "correct": totals["correct"],
            "scored": totals["scored"],
            "accuracy": round(totals["correct"] / totals["scored"], 4) if totals["scored"] else None,
        }
        for field, totals in field_totals.items()
    }
    return {
        "overall": {
            "cases": len(cases),
            "fully_correct_cases": fully_correct_cases,
            "fully_correct_case_accuracy": round(fully_correct_cases / len(cases), 4) if cases else None,
        },
        "fields": field_summary,
        "schema": summarize_schema_totals(schema_totals, cases),
        "generated_fields": summarize_generated_fields(
            field_totals=generated_totals,
            total_scored=generated_scored,
            total_predicted=generated_predicted,
            total_exact=generated_exact,
            precision_sum=generated_precision_sum,
            recall_sum=generated_recall_sum,
            f1_sum=generated_f1_sum,
        ),
        "case_results": case_results,
    }


def compact_case_manifest(cases: list[CaseRecord]) -> list[dict[str, Any]]:
    return [
        {
            "order_id": case.order_id,
            "markdown_path": case.markdown_path,
            "sidecar_path": case.sidecar_path,
            "approximate_tokens": case.approximate_tokens,
            "redacted": case.redacted,
            "gold_fields": case.gold_fields,
            "teacher_fields": case.teacher_fields,
        }
        for case in cases
    ]


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    cases = discover_cases(
        markdown_dir=args.markdown_dir.resolve(),
        sidecar_dir=args.sidecar_dir.resolve(),
        case_count=args.case_count,
        target_batch_tokens=args.target_batch_tokens or args.target_prompt_tokens,
        seed=args.seed,
        balanced_redactions=not args.no_balanced_redactions,
        thinking_token_budget=args.thinking_token_budget,
    )
    payload = build_payload(
        model=args.model,
        cases=cases,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        enable_thinking=args.enable_thinking,
        thinking_token_budget=args.thinking_token_budget,
    )
    run_name = args.run_name or time.strftime("tribunal_batch_eval_%Y%m%d_%H%M%S", time.gmtime())
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / f"{run_name}_cases.json"
    payload_path = output_dir / f"{run_name}_payload.json"
    response_path = output_dir / f"{run_name}_response.json"
    summary_path = output_dir / f"{run_name}_summary.json"
    manifest = {
        "run_name": run_name,
        "base_url": args.base_url,
        "model": args.model,
        "enable_thinking": args.enable_thinking,
        "thinking_token_budget": args.thinking_token_budget,
        "case_count": len(cases),
        "redacted_cases": sum(1 for case in cases if case.redacted),
        "target_batch_tokens": args.target_batch_tokens or args.target_prompt_tokens,
        "approximate_prompt_tokens": sum(case.approximate_tokens for case in cases),
        "approximate_reserved_tokens": sum(
            reserved_case_tokens(case, args.thinking_token_budget) for case in cases
        ),
        "cases": compact_case_manifest(cases),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.dry_run:
        summary = {
            "status": "dry_run",
            "manifest_path": str(manifest_path),
            "payload_path": str(payload_path),
            "case_count": len(cases),
            "redacted_cases": manifest["redacted_cases"],
            "approximate_prompt_tokens": manifest["approximate_prompt_tokens"],
            "approximate_reserved_tokens": manifest["approximate_reserved_tokens"],
            "enable_thinking": args.enable_thinking,
            "thinking_token_budget": args.thinking_token_budget,
        }
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary
    status, response_body, elapsed_seconds = post_json(
        url=f"{args.base_url.rstrip('/')}/v1/chat/completions/batch",
        payload=payload,
        timeout_seconds=args.timeout_seconds,
    )
    response_path.write_bytes(response_body)
    response_json = json.loads(response_body)
    predictions = parse_predictions(cases=cases, response_json=response_json)
    score_summary = score_predictions(cases=cases, predictions=predictions)
    summary = {
        "status": status,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "usage": response_json.get("usage"),
        "case_count": len(cases),
        "redacted_cases": manifest["redacted_cases"],
        "approximate_prompt_tokens": manifest["approximate_prompt_tokens"],
        "approximate_reserved_tokens": manifest["approximate_reserved_tokens"],
        "enable_thinking": args.enable_thinking,
        "thinking_token_budget": args.thinking_token_budget,
        "manifest_path": str(manifest_path),
        "payload_path": str(payload_path),
        "response_path": str(response_path),
        "predictions": predictions,
        "scores": score_summary,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary
