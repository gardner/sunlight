#!/usr/bin/env python3
"""Spot-check tribunal extractions by asking vLLM to judge them against source markdown."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vllm import tribunal_eval_runner as runner
from vllm.tribunal_eval_extract import extract_json_content, strip_front_matter

JSON_SCHEMA_NAME = "tribunal_spotcheck_judgment"
DEFAULT_MAX_TOKENS = 700
DEFAULT_OUTPUT_ROOT = Path("vllm/results")
MAX_RETRY_TOKENS = 2800


@dataclass(slots=True)
class SpotcheckCandidate:
    order_id: str
    markdown_path: str
    prediction: dict[str, Any]
    schema_valid: bool
    schema_errors: list[str]


@dataclass(slots=True)
class JudgeCase:
    order_id: str
    markdown_path: str
    markdown_text: str
    prediction: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--base-url", default=runner.DEFAULT_BASE_URL)
    parser.add_argument("--model", default=runner.DEFAULT_MODEL)
    parser.add_argument("--sample-size", type=int, default=20)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--order-id", action="append", default=[])
    parser.add_argument("--include-schema-invalid", action="store_true")
    return parser.parse_args()


def default_output_dir(run_dir: Path) -> Path:
    timestamp = time.strftime("judge_spotcheck_%Y%m%d_%H%M%S", time.gmtime())
    return run_dir / timestamp


def number_markdown_lines(markdown_text: str) -> str:
    lines = markdown_text.strip().splitlines()
    return "\n".join(f"{index}: {line}" for index, line in enumerate(lines, start=1))


def build_judge_schema() -> dict[str, Any]:
    issue_schema = {
        "type": "object",
        "properties": {
            "field": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["incorrect", "inconsistent", "missing_support", "unclear"],
            },
            "reason": {"type": "string"},
            "expected_value_json": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "evidence_lines": {
                "type": "array",
                "items": {"type": "integer", "minimum": 1},
            },
        },
        "required": [
            "field",
            "status",
            "reason",
            "expected_value_json",
            "evidence_lines",
        ],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "overall_pass": {"type": "boolean"},
            "summary": {"type": "string"},
            "issues": {
                "type": "array",
                "items": issue_schema,
            },
        },
        "required": ["overall_pass", "summary", "issues"],
        "additionalProperties": False,
    }


def build_judge_prompt(markdown_text: str, extraction: dict[str, Any]) -> str:
    numbered_markdown = number_markdown_lines(strip_front_matter(markdown_text))
    extraction_json = json.dumps(extraction, ensure_ascii=True, indent=2, sort_keys=True)
    return (
        "Review the extraction against the tribunal document.\n"
        "Check whether each extracted field is supported by the document, and flag any "
        "inaccuracies, inconsistencies, or unsupported claims.\n"
        "Use these field conventions:\n"
        "- `application_number`: the docket digits or identifier, not the citation year.\n"
        "- `tribunal_location`: preserve the exact location label, including suppression placeholders.\n"
        "- `total_award_nzd`: prefer the tribunal's stated total award or net award row, not a restatement of immediate payment text.\n"
        "- `payable_by` / `payable_to`: capture who pays the net amount; use `other` for bond or third-party payment.\n"
        "Treat suppression placeholders as meaningful values. Do not unsuppress names or addresses.\n"
        "Use evidence line numbers from the document for every issue you report.\n"
        "Be concise. Keep the summary short and report at most 4 material issues.\n"
        "If a field is ambiguous from the document alone, mark it as `unclear`.\n"
        "If the extraction is fully supported, return an empty issues list and overall_pass=true.\n"
        "Return only JSON that matches the schema.\n\n"
        "Document:\n"
        f"{numbered_markdown}\n\n"
        "Extraction JSON:\n"
        f"{extraction_json}\n"
    )


def load_candidates(run_dir: Path, require_schema_valid: bool) -> list[SpotcheckCandidate]:
    extractions_path = run_dir / "extractions.jsonl"
    if not extractions_path.exists():
        raise FileNotFoundError(f"Missing extractions file: {extractions_path}")
    candidates: list[SpotcheckCandidate] = []
    for raw_line in extractions_path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        payload = json.loads(raw_line)
        prediction = payload.get("prediction")
        if not isinstance(prediction, dict):
            continue
        schema_valid = bool(payload.get("schema_valid"))
        if require_schema_valid and not schema_valid:
            continue
        candidates.append(
            SpotcheckCandidate(
                order_id=str(payload["order_id"]),
                markdown_path=str(payload["markdown_path"]),
                prediction=prediction,
                schema_valid=schema_valid,
                schema_errors=list(payload.get("schema_errors") or []),
            )
        )
    if not candidates:
        raise ValueError("No extraction candidates were loaded for spot-checking.")
    return candidates


def sample_candidates(
    candidates: list[SpotcheckCandidate],
    sample_size: int,
    seed: int,
) -> list[SpotcheckCandidate]:
    if sample_size <= 0 or sample_size >= len(candidates):
        return candidates[:]
    rng = random.Random(seed)
    sampled_indices = sorted(rng.sample(range(len(candidates)), sample_size))
    return [candidates[index] for index in sampled_indices]


def resolve_candidates(
    candidates: list[SpotcheckCandidate],
    sample_size: int,
    seed: int,
    order_ids: list[str],
) -> list[SpotcheckCandidate]:
    if order_ids:
        wanted = set(order_ids)
        selected = [candidate for candidate in candidates if candidate.order_id in wanted]
        missing = sorted(wanted - {candidate.order_id for candidate in selected})
        if missing:
            raise ValueError(f"Requested order ids not found in run: {', '.join(missing)}")
        return selected
    return sample_candidates(candidates, sample_size=sample_size, seed=seed)


def load_judge_cases(candidates: list[SpotcheckCandidate]) -> list[JudgeCase]:
    cases: list[JudgeCase] = []
    for candidate in candidates:
        markdown_path = Path(candidate.markdown_path)
        markdown_text = markdown_path.read_text(encoding="utf-8", errors="replace")
        cases.append(
            JudgeCase(
                order_id=candidate.order_id,
                markdown_path=candidate.markdown_path,
                markdown_text=markdown_text,
                prediction=candidate.prediction,
            )
        )
    return cases


def build_payload(
    *,
    model: str,
    cases: list[JudgeCase],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    messages = [
        [{"role": "user", "content": build_judge_prompt(case.markdown_text, case.prediction)}]
        for case in cases
    ]
    return {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": JSON_SCHEMA_NAME,
                "strict": True,
                "schema": build_judge_schema(),
            },
        },
    }


def parse_judgments(cases: list[JudgeCase], response_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    judgments: dict[str, dict[str, Any]] = {}
    for choice in response_json.get("choices", []):
        index = choice.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(cases):
            continue
        content = choice.get("message", {}).get("content", "")
        try:
            judgments[cases[index].order_id] = extract_json_content(content)
        except (ValueError, json.JSONDecodeError):
            judgments[cases[index].order_id] = {"_parse_error": content}
    return judgments


def retry_token_values(base_max_tokens: int) -> list[int]:
    values: list[int] = []
    current = base_max_tokens
    while current < MAX_RETRY_TOKENS:
        current = min(current * 2, MAX_RETRY_TOKENS)
        if current > base_max_tokens:
            values.append(current)
    return values


def summarize_judgments(cases: list[JudgeCase], judgments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    passed_cases = 0
    flagged_cases = 0
    parse_error_cases = 0
    issue_counts_by_field: dict[str, int] = {}
    issue_counts_by_status: dict[str, int] = {}
    case_results: list[dict[str, Any]] = []
    for case in cases:
        judgment = judgments.get(case.order_id)
        if judgment is None or "_parse_error" in judgment:
            parse_error_cases += 1
            case_results.append(
                {
                    "order_id": case.order_id,
                    "overall_pass": False,
                    "issue_count": None,
                    "parse_error": True,
                }
            )
            continue
        issues = judgment.get("issues", [])
        overall_pass = bool(judgment.get("overall_pass"))
        if overall_pass and not issues:
            passed_cases += 1
        else:
            flagged_cases += 1
        for issue in issues:
            field = str(issue.get("field", "unknown"))
            status = str(issue.get("status", "unknown"))
            issue_counts_by_field[field] = issue_counts_by_field.get(field, 0) + 1
            issue_counts_by_status[status] = issue_counts_by_status.get(status, 0) + 1
        case_results.append(
            {
                "order_id": case.order_id,
                "overall_pass": overall_pass,
                "issue_count": len(issues),
                "summary": judgment.get("summary"),
                "reviewed_fields": judgment.get("reviewed_fields"),
            }
        )
    total_cases = len(cases)
    return {
        "cases": total_cases,
        "passed_cases": passed_cases,
        "flagged_cases": flagged_cases,
        "parse_error_cases": parse_error_cases,
        "pass_rate": round(passed_cases / total_cases, 4) if total_cases else None,
        "flagged_rate": round(flagged_cases / total_cases, 4) if total_cases else None,
        "issue_counts_by_field": issue_counts_by_field,
        "issue_counts_by_status": issue_counts_by_status,
        "case_results": case_results,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_cases_once(
    *,
    base_url: str,
    model: str,
    cases: list[JudgeCase],
    temperature: float,
    max_tokens: int,
    timeout_seconds: int,
) -> tuple[int, bytes, float, dict[str, dict[str, Any]], dict[str, Any]]:
    payload = build_payload(
        model=model,
        cases=cases,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    status, response_body, elapsed_seconds = runner.post_json(
        url=f"{base_url.rstrip('/')}/v1/chat/completions/batch",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )
    response_json = json.loads(response_body)
    judgments = parse_judgments(cases=cases, response_json=response_json)
    return status, response_body, elapsed_seconds, judgments, payload


def run_spotcheck(args: argparse.Namespace) -> Path:
    candidates = load_candidates(
        run_dir=args.run_dir,
        require_schema_valid=not args.include_schema_invalid,
    )
    selected_candidates = resolve_candidates(
        candidates=candidates,
        sample_size=args.sample_size,
        seed=args.seed,
        order_ids=list(args.order_id),
    )
    cases = load_judge_cases(selected_candidates)
    output_dir = args.output_dir or default_output_dir(args.run_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_dir": str(args.run_dir.resolve()),
        "base_url": args.base_url,
        "model": args.model,
        "sample_size": len(cases),
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "include_schema_invalid": args.include_schema_invalid,
        "order_ids": list(args.order_id),
        "cases": [
            {
                "order_id": case.order_id,
                "markdown_path": case.markdown_path,
                "prediction_keys": sorted(case.prediction),
            }
            for case in cases
        ],
    }
    write_json(output_dir / "manifest.json", manifest)
    status, response_body, elapsed_seconds, judgments, payload = run_cases_once(
        base_url=args.base_url,
        model=args.model,
        cases=cases,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        timeout_seconds=args.timeout_seconds,
    )
    retries: list[dict[str, Any]] = []
    merged_judgments = dict(judgments)
    for case in cases:
        judgment = merged_judgments.get(case.order_id, {})
        if "_parse_error" not in judgment:
            continue
        for retry_tokens in retry_token_values(args.max_tokens):
            retry_status, retry_body, retry_elapsed, retry_judgments, retry_payload = run_cases_once(
                base_url=args.base_url,
                model=args.model,
                cases=[case],
                temperature=args.temperature,
                max_tokens=retry_tokens,
                timeout_seconds=args.timeout_seconds,
            )
            write_json(output_dir / f"retry_{case.order_id}_{retry_tokens}_payload.json", retry_payload)
            (output_dir / f"retry_{case.order_id}_{retry_tokens}_response.json").write_bytes(retry_body)
            retry_judgment = retry_judgments.get(case.order_id, {})
            retries.append(
                {
                    "order_id": case.order_id,
                    "max_tokens": retry_tokens,
                    "status": retry_status,
                    "elapsed_seconds": round(retry_elapsed, 3),
                    "parse_error": "_parse_error" in retry_judgment,
                }
            )
            if "_parse_error" not in retry_judgment:
                merged_judgments[case.order_id] = retry_judgment
                break
    (output_dir / "response.json").write_bytes(response_body)
    write_json(output_dir / "payload.json", payload)
    response_json = json.loads(response_body)
    summary = summarize_judgments(cases=cases, judgments=merged_judgments)
    summary.update(
        {
            "status": status,
            "elapsed_seconds": round(elapsed_seconds, 3),
            "usage": response_json.get("usage"),
            "output_dir": str(output_dir.resolve()),
            "retries": retries,
        }
    )
    write_json(output_dir / "judgments.json", merged_judgments)
    write_json(output_dir / "summary.json", summary)
    return output_dir


def main() -> None:
    args = parse_args()
    output_dir = run_spotcheck(args)
    print(json.dumps({"output_dir": str(output_dir.resolve())}, indent=2))


if __name__ == "__main__":
    main()
