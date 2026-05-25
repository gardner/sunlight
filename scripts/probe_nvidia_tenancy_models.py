from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from openai import OpenAI

from tenancy_corpus import parse_tenancy_markdown
from tenancy_llm import build_llm_input, parse_enrichment_content
from tenancy_llm_messages import build_enrichment_messages


DEFAULT_MODELS = [
    "stepfun-ai/step-3.5-flash",
    "mistralai/mistral-large-3-675b-instruct-2512",
    "bytedance/seed-oss-36b-instruct",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "mistralai/mistral-nemotron",
    "meta/llama-4-maverick-17b-128e-instruct",
    "nvidia/nemotron-3-super-120b-a12b",
]
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
DEFAULT_MARKDOWN_DIR = Path("storage/justice/tenancy/markdown_docling")
DEFAULT_REQUESTS_PER_MODEL = 100
DEFAULT_MAX_CHARS = 5000
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 240


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe NVIDIA OpenAI-compatible models with real Tenancy enrichment prompts."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key-env", default="NVIDIA_API_KEY")
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--requests-per-model", type=int, default=DEFAULT_REQUESTS_PER_MODEL)
    parser.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS)
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--cooldown-seconds", type=float, default=60)
    parser.add_argument("--inter-request-sleep", type=float, default=0)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    return parser


def selected_markdown_paths(markdown_dir: Path, limit: int) -> list[Path]:
    pending: list[Path] = []
    fallback: list[Path] = []
    for path in sorted(markdown_dir.glob("*.md")):
        try:
            metadata, body = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not body.strip():
            continue
        if metadata.get("llm_enrichment_version") == "tenancy-llm-v1":
            fallback.append(path)
        else:
            pending.append(path)
        if len(pending) >= limit:
            return pending[:limit]
    return [*pending, *fallback][:limit]


def http_error_detail(exc: Exception) -> dict[str, Any]:
    detail: dict[str, Any] = {
        "type": type(exc).__name__,
        "status_code": getattr(exc, "status_code", None),
        "message": str(exc)[:1000],
    }
    response = getattr(exc, "response", None)
    if response is not None:
        detail["headers"] = selected_headers(response.headers)
        try:
            detail["response_text"] = response.text[:2000]
            parsed = response.json()
            detail["response_json"] = parsed
            if isinstance(parsed, dict):
                detail["response_title"] = parsed.get("title")
                detail["response_message"] = parsed.get("message") or parsed.get("detail")
        except Exception:
            pass
    body = getattr(exc, "body", None)
    if body is not None:
        detail["body"] = body
    return detail


def selected_headers(headers) -> dict[str, str]:
    interesting = {
        "retry-after",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
    }
    return {
        str(key): str(value)
        for key, value in dict(headers).items()
        if str(key).lower() in interesting
    }


def status_for_error(detail: dict[str, Any]) -> str:
    status_code = detail.get("status_code")
    if status_code == 429:
        return "http_429"
    if status_code:
        return f"http_{status_code}"
    return "client_error"


def compact(text: str, limit: int = 600) -> str:
    return text.replace("\n", "\\n")[:limit]


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(item, ensure_ascii=True, default=str) + "\n")


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")


def summarize_results(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(results)
    counts = Counter(str(row["status"]) for row in rows)
    latencies = [float(row["elapsed_s"]) for row in rows]
    return {
        "total": len(rows),
        "counts": dict(sorted(counts.items())),
        "min_latency_s": round(min(latencies), 2) if latencies else None,
        "max_latency_s": round(max(latencies), 2) if latencies else None,
        "avg_latency_s": round(sum(latencies) / len(latencies), 2) if latencies else None,
    }


def run_model(
    *,
    client: OpenAI,
    model: str,
    documents: list[dict[str, object]],
    max_tokens: int,
    output_jsonl: Path,
    inter_request_sleep: float,
) -> list[dict[str, Any]]:
    model_results: list[dict[str, Any]] = []
    started_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"model_start model={model} requests={len(documents)} started_at={started_at}", flush=True)
    for index, document in enumerate(documents, start=1):
        result = request_one(client, model, document, index, len(documents), max_tokens)
        append_jsonl(output_jsonl, result)
        model_results.append(result)
        print("probe_result " + json.dumps(result, ensure_ascii=True, default=str), flush=True)
        if index % 10 == 0:
            print(
                "model_progress "
                + json.dumps(
                    {"model": model, "completed": index, **summarize_results(model_results)},
                    ensure_ascii=True,
                    default=str,
                ),
                flush=True,
            )
        if inter_request_sleep > 0:
            time.sleep(inter_request_sleep)
    return model_results


def request_one(
    client: OpenAI,
    model: str,
    document: dict[str, object],
    index: int,
    total: int,
    max_tokens: int,
) -> dict[str, Any]:
    expected_id = str(document["document_id"])
    started = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=build_enrichment_messages([document]),
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        elapsed = time.monotonic() - started
        detail = http_error_detail(exc)
        return {
            "model": model,
            "index": index,
            "total": total,
            "document_id": expected_id,
            "status": status_for_error(detail),
            "elapsed_s": round(elapsed, 2),
            "error": detail,
        }

    elapsed = time.monotonic() - started
    choice = response.choices[0]
    content = choice.message.content or ""
    base = {
        "model": model,
        "index": index,
        "total": total,
        "document_id": expected_id,
        "elapsed_s": round(elapsed, 2),
        "finish_reason": choice.finish_reason,
        "content_chars": len(content),
        "usage": response.usage.model_dump() if response.usage else None,
    }
    try:
        parsed = parse_enrichment_content(content, default_document_id=expected_id)
    except Exception as exc:
        return {
            **base,
            "status": "parse_error",
            "error": {"type": type(exc).__name__, "message": str(exc)[:1000]},
            "preview": compact(content),
        }
    ids = [item.document_id for item in parsed.items]
    if ids != [expected_id]:
        return {**base, "status": "bad_ids", "ids": ids, "preview": compact(content)}
    item = parsed.items[0]
    return {
        **base,
        "status": "ok",
        "summary_len": len(item.case_summary),
        "catchwords": len(item.catchwords),
        "questions": len(item.questions_answered),
    }


def main() -> None:
    args = build_parser().parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is not set")
    paths = selected_markdown_paths(args.markdown_dir, args.requests_per_model)
    if len(paths) < args.requests_per_model:
        raise SystemExit(
            f"Only found {len(paths)} usable markdown files, need {args.requests_per_model}"
        )
    documents = [build_llm_input([path], args.max_chars)[0] for path in paths]
    client = OpenAI(base_url=args.base_url, api_key=api_key, timeout=args.timeout)
    all_results: list[dict[str, Any]] = []
    run_summary: dict[str, Any] = {
        "base_url": args.base_url,
        "requests_per_model": args.requests_per_model,
        "max_chars": args.max_chars,
        "max_tokens": args.max_tokens,
        "models": {},
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "document_ids": [str(document["document_id"]) for document in documents],
    }
    write_summary(args.summary_json, run_summary)
    if args.cooldown_seconds > 0:
        print(f"cooldown_seconds={args.cooldown_seconds}", flush=True)
        time.sleep(args.cooldown_seconds)
    for model in args.models:
        results = run_model(
            client=client,
            model=model,
            documents=documents,
            max_tokens=args.max_tokens,
            output_jsonl=args.output_jsonl,
            inter_request_sleep=args.inter_request_sleep,
        )
        all_results.extend(results)
        run_summary["models"][model] = summarize_results(results)
        run_summary["overall"] = summarize_results(all_results)
        run_summary["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        write_summary(args.summary_json, run_summary)
        print(
            "model_summary "
            + json.dumps({"model": model, **run_summary["models"][model]}, ensure_ascii=True),
            flush=True,
        )
    print("probe_summary " + json.dumps(run_summary, ensure_ascii=True, default=str), flush=True)


if __name__ == "__main__":
    main()
