#!/usr/bin/env python3
"""Process all docling tribunal markdown files through the vLLM extractor."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vllm import tribunal_eval_runner as runner

DEFAULT_MAX_CASES_PER_BATCH = 96
DEFAULT_TARGET_BATCH_TOKENS = 180_000
DEFAULT_OUTPUT_ROOT = Path("vllm/results")
MAX_RETRY_TOKENS = 2048


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--markdown-dir", type=Path, default=runner.DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--base-url", default=runner.DEFAULT_BASE_URL)
    parser.add_argument("--model", default=runner.DEFAULT_MODEL)
    parser.add_argument("--max-cases-per-batch", type=int, default=DEFAULT_MAX_CASES_PER_BATCH)
    parser.add_argument("--target-batch-tokens", type=int, default=DEFAULT_TARGET_BATCH_TOKENS)
    parser.add_argument("--max-tokens", type=int, default=320)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--enable-thinking", action="store_true")
    parser.add_argument("--thinking-token-budget", type=int, default=None)
    parser.add_argument("--max-concurrent-batches", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def default_output_dir() -> Path:
    timestamp = time.strftime("tribunal_docling_all_%Y%m%d_%H%M%S", time.gmtime())
    return DEFAULT_OUTPUT_ROOT / timestamp


def batch_name(index: int) -> str:
    return f"batch_{index:05d}"


def completed_batch_indices(output_dir: Path) -> set[int]:
    completed: set[int] = set()
    for path in output_dir.glob("batch_*_summary.json"):
        try:
            completed.add(int(path.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return completed


def progress_path(output_dir: Path) -> Path:
    return output_dir / "progress.json"


def extractions_path(output_dir: Path) -> Path:
    return output_dir / "extractions.jsonl"


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def initialize_run(output_dir: Path, args: argparse.Namespace, cases: list[runner.CaseRecord], batches: list[list[runner.CaseRecord]]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        output_dir / "run_config.json",
        {
            "markdown_dir": str(args.markdown_dir.resolve()),
            "base_url": args.base_url,
            "model": args.model,
            "max_cases_per_batch": args.max_cases_per_batch,
            "target_batch_tokens": args.target_batch_tokens,
            "max_tokens": args.max_tokens,
            "temperature": args.temperature,
            "timeout_seconds": args.timeout_seconds,
            "enable_thinking": args.enable_thinking,
            "thinking_token_budget": args.thinking_token_budget,
            "max_concurrent_batches": args.max_concurrent_batches,
            "total_cases": len(cases),
            "planned_batches": len(batches),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )


def update_progress(
    output_dir: Path,
    *,
    total_cases: int,
    total_batches: int,
    completed_cases: int,
    completed_batches: int,
    failed_batches: list[str],
    started_at: float,
    current_batches: list[str],
) -> None:
    write_json(
        progress_path(output_dir),
        {
            "total_cases": total_cases,
            "total_batches": total_batches,
            "completed_cases": completed_cases,
            "completed_batches": completed_batches,
            "failed_batches": failed_batches,
            "current_batch": current_batches[0] if len(current_batches) == 1 else None,
            "current_batches": current_batches,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )


def append_extractions(
    output_dir: Path,
    batch: str,
    cases: list[runner.CaseRecord],
    summary: dict[str, Any],
    append_lock: threading.Lock,
) -> None:
    predictions = summary["predictions"]
    case_results = {item["order_id"]: item for item in summary["scores"]["case_results"]}
    with append_lock:
        with extractions_path(output_dir).open("a", encoding="utf-8") as handle:
            for case in cases:
                result = case_results.get(case.order_id, {})
                payload = {
                    "batch": batch,
                    "order_id": case.order_id,
                    "markdown_path": case.markdown_path,
                    "prediction": predictions.get(case.order_id),
                    "schema_valid": result.get("schema_valid"),
                    "schema_errors": result.get("schema_errors"),
                }
                handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def retry_token_values(base_max_tokens: int) -> list[int]:
    values: list[int] = []
    current = base_max_tokens
    while current < MAX_RETRY_TOKENS:
        current = min(current * 2, MAX_RETRY_TOKENS)
        if current > base_max_tokens:
            values.append(current)
    return values


def run_cases_once(
    output_dir: Path,
    args: argparse.Namespace,
    batch: str,
    cases: list[runner.CaseRecord],
    *,
    max_tokens: int,
) -> dict[str, Any]:
    payload = runner.build_payload(
        model=args.model,
        cases=cases,
        temperature=args.temperature,
        max_tokens=max_tokens,
        enable_thinking=args.enable_thinking,
        thinking_token_budget=args.thinking_token_budget,
    )
    manifest = {
        "batch": batch,
        "base_url": args.base_url,
        "model": args.model,
        "enable_thinking": args.enable_thinking,
        "thinking_token_budget": args.thinking_token_budget,
        "max_tokens": max_tokens,
        "case_count": len(cases),
        "approximate_prompt_tokens": sum(case.approximate_tokens for case in cases),
        "approximate_reserved_tokens": sum(
            runner.reserved_case_tokens(case, args.thinking_token_budget) for case in cases
        ),
        "cases": runner.compact_case_manifest(cases),
    }
    write_json(output_dir / f"{batch}_cases.json", manifest)
    write_json(output_dir / f"{batch}_payload.json", payload)
    status, response_body, elapsed_seconds = runner.post_json(
        url=f"{args.base_url.rstrip('/')}/v1/chat/completions/batch",
        payload=payload,
        timeout_seconds=args.timeout_seconds,
    )
    response_path = output_dir / f"{batch}_response.json"
    response_path.write_bytes(response_body)
    response_json = json.loads(response_body)
    predictions = runner.parse_predictions(cases=cases, response_json=response_json)
    scores = runner.score_predictions(cases=cases, predictions=predictions)
    summary = {
        "status": status,
        "elapsed_seconds": round(elapsed_seconds, 3),
        "usage": response_json.get("usage"),
        "case_count": len(cases),
        "approximate_prompt_tokens": manifest["approximate_prompt_tokens"],
        "approximate_reserved_tokens": manifest["approximate_reserved_tokens"],
        "max_tokens": max_tokens,
        "enable_thinking": args.enable_thinking,
        "thinking_token_budget": args.thinking_token_budget,
        "manifest_path": str((output_dir / f"{batch}_cases.json").resolve()),
        "payload_path": str((output_dir / f"{batch}_payload.json").resolve()),
        "response_path": str(response_path.resolve()),
        "predictions": predictions,
        "scores": scores,
    }
    return summary


def run_batch(
    output_dir: Path,
    args: argparse.Namespace,
    batch: str,
    cases: list[runner.CaseRecord],
    append_lock: threading.Lock,
) -> dict[str, Any]:
    summary = run_cases_once(output_dir, args, batch, cases, max_tokens=args.max_tokens)
    retries: list[dict[str, Any]] = []
    predictions = dict(summary["predictions"])
    invalid_cases = [
        case for case, result in zip(cases, summary["scores"]["case_results"], strict=False) if not result["schema_valid"]
    ]
    for case in invalid_cases:
        repaired = False
        for retry_tokens in retry_token_values(args.max_tokens):
            retry_name = f"{batch}_retry_{case.order_id}_{retry_tokens}"
            retry_summary = run_cases_once(output_dir, args, retry_name, [case], max_tokens=retry_tokens)
            retry_result = retry_summary["scores"]["case_results"][0]
            retries.append(
                {
                    "order_id": case.order_id,
                    "max_tokens": retry_tokens,
                    "schema_valid": retry_result["schema_valid"],
                    "summary_path": str((output_dir / f"{retry_name}_summary.json").resolve()),
                }
            )
            write_json(output_dir / f"{retry_name}_summary.json", retry_summary)
            if retry_result["schema_valid"]:
                predictions[case.order_id] = retry_summary["predictions"][case.order_id]
                repaired = True
                break
        if not repaired:
            continue
    if retries:
        summary["predictions"] = predictions
        summary["scores"] = runner.score_predictions(cases=cases, predictions=predictions)
        summary["retries"] = retries
    write_json(output_dir / f"{batch}_summary.json", summary)
    append_extractions(output_dir, batch, cases, summary, append_lock)
    return summary


def current_batch_names(running: dict[Future[dict[str, Any]], tuple[int, str, list[runner.CaseRecord]]]) -> list[str]:
    return sorted(batch for _, batch, _ in running.values())


def process_all(args: argparse.Namespace) -> Path:
    output_dir = (args.output_dir or default_output_dir()).resolve()
    cases = runner.load_markdown_candidates(args.markdown_dir.resolve())
    batches = runner.build_case_batches(
        ordered=cases,
        max_cases_per_batch=args.max_cases_per_batch,
        target_batch_tokens=args.target_batch_tokens,
        thinking_token_budget=args.thinking_token_budget,
    )
    initialize_run(output_dir, args, cases, batches)
    completed = completed_batch_indices(output_dir) if args.resume else set()
    failed_batches: list[str] = []
    completed_cases = 0
    completed_batches = 0
    started_at = time.time()
    append_lock = threading.Lock()
    remaining = [
        (index, batch_name(index), batch_cases)
        for index, batch_cases in enumerate(batches)
        if index not in completed
    ]
    for index, _, batch_cases in [
        (index, batch_name(index), batch_cases)
        for index, batch_cases in enumerate(batches)
        if index in completed
    ]:
        completed_batches += 1
        completed_cases += len(batch_cases)
    running: dict[Future[dict[str, Any]], tuple[int, str, list[runner.CaseRecord]]] = {}
    cursor = 0
    with ThreadPoolExecutor(max_workers=max(1, args.max_concurrent_batches)) as executor:
        while cursor < len(remaining) or running:
            while cursor < len(remaining) and len(running) < max(1, args.max_concurrent_batches):
                index, batch, batch_cases = remaining[cursor]
                cursor += 1
                future = executor.submit(run_batch, output_dir, args, batch, batch_cases, append_lock)
                running[future] = (index, batch, batch_cases)
            update_progress(
                output_dir,
                total_cases=len(cases),
                total_batches=len(batches),
                completed_cases=completed_cases,
                completed_batches=completed_batches,
                failed_batches=failed_batches,
                started_at=started_at,
                current_batches=current_batch_names(running),
            )
            done, _ = wait(running.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                _, batch, batch_cases = running.pop(future)
                try:
                    future.result()
                except Exception:
                    failed_batches.append(batch)
                    for pending in running:
                        pending.cancel()
                    update_progress(
                        output_dir,
                        total_cases=len(cases),
                        total_batches=len(batches),
                        completed_cases=completed_cases,
                        completed_batches=completed_batches,
                        failed_batches=failed_batches,
                        started_at=started_at,
                        current_batches=current_batch_names(running),
                    )
                    raise
                completed_batches += 1
                completed_cases += len(batch_cases)
            update_progress(
                output_dir,
                total_cases=len(cases),
                total_batches=len(batches),
                completed_cases=completed_cases,
                completed_batches=completed_batches,
                failed_batches=failed_batches,
                started_at=started_at,
                current_batches=current_batch_names(running),
            )
    write_json(
        output_dir / "aggregate_summary.json",
        {
            "total_cases": len(cases),
            "total_batches": len(batches),
            "completed_cases": completed_cases,
            "completed_batches": completed_batches,
            "failed_batches": failed_batches,
            "elapsed_seconds": round(time.time() - started_at, 3),
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    return output_dir


def main() -> None:
    output_dir = process_all(parse_args())
    print(json.dumps({"output_dir": str(output_dir)}, indent=2))


if __name__ == "__main__":
    main()
