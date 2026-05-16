"""Generate FYI search eval questions with a local OpenAI-compatible LLM."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fyi_request_metadata
from fyi_markdown import parse_markdown_document


DEFAULT_MARKDOWN_DIR = Path("fyi/markdown")
DEFAULT_FYI_DATA_DIR = Path("fyi/data")
DEFAULT_OUTPUT = Path("manifests/fyi/v1/eval-questions.ndjson")
DEFAULT_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_MODEL = "nvidia/Gemma-4-31B-IT-NVFP4"
DEFAULT_COUNT = 50
DEFAULT_SEED = 20260516
MAX_EXCERPT_CHARS = 5200
MIN_BODY_CHARS = 700
KINDS = ("exact_term", "semantic", "numeric", "no_answer")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate manifests/fyi/v1/eval-questions.ndjson from FYI markdown."
    )
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--fyi-data-dir", type=Path, default=DEFAULT_FYI_DATA_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("LOCAL_CHAT_MODEL", DEFAULT_MODEL))
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"Output exists, pass --force to overwrite: {args.output}")

    request_index = fyi_request_metadata.load_request_metadata(args.fyi_data_dir)
    candidates = collect_candidates(args.markdown_dir, request_index)
    selected = select_candidates(candidates, count=args.count * 3, seed=args.seed)
    if len(selected) < args.count:
        print(f"Only found {len(selected)} usable candidates for {args.count} requested.", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for candidate in selected:
        index = len(rows) + 1
        print(
            f"Generating {index}/{args.count}: {candidate['kind']} "
            f"{candidate['document_id']}",
            flush=True,
        )
        try:
            llm_item = generate_question(args.base_url, args.model, candidate)
        except Exception as exc:
            print(f"Skipping {candidate['document_id']}: {exc}", flush=True)
            continue
        rows.append(build_manifest_row(candidate, llm_item, index, args.model))
        if len(rows) >= args.count:
            break
        time.sleep(0.05)

    if len(rows) < args.count:
        raise SystemExit(f"Only generated {len(rows)} valid questions for {args.count} requested.")

    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"Wrote {len(rows)} eval questions to {args.output}", flush=True)
    return 0


def collect_candidates(markdown_dir: Path, request_index: dict[int, dict]) -> list[dict[str, Any]]:
    candidates = []
    for path in sorted(markdown_dir.glob("*.md")):
        try:
            metadata, body = parse_markdown_document(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            continue
        if len(body.strip()) < MIN_BODY_CHARS:
            continue

        request_id = as_int(metadata.get("fyi_request_id"))
        document_id = as_string(metadata.get("document_id"))
        request_url = as_string(metadata.get("request_url"))
        if request_id is None or not document_id or not request_url:
            continue

        request_metadata = request_index.get(request_id, {})
        if not request_metadata.get("request_title"):
            continue

        candidate = build_candidate(path, metadata, request_metadata, body)
        if candidate:
            candidates.append(candidate)
    return candidates


def build_candidate(
    path: Path,
    metadata: dict[str, object],
    request_metadata: dict,
    body: str,
) -> dict[str, Any] | None:
    document_id = as_string(metadata.get("document_id"))
    request_url = as_string(metadata.get("request_url"))
    source_url = as_string(metadata.get("source_url"))
    if not document_id or not request_url:
        return None

    excerpt = extract_excerpt(body)
    if len(excerpt) < MIN_BODY_CHARS:
        return None

    return {
        "authority_name": request_metadata.get("authority_name"),
        "document_id": document_id,
        "excerpt": excerpt,
        "fyi_attachment_id": metadata.get("fyi_attachment_id"),
        "fyi_request_id": metadata.get("fyi_request_id"),
        "fyi_response_id": metadata.get("fyi_response_id"),
        "kind": classify_candidate(body),
        "markdown_path": str(path),
        "original_filename": metadata.get("original_filename"),
        "request_title": request_metadata.get("request_title"),
        "request_url": request_url,
        "request_year": request_metadata.get("request_year"),
        "source_url": source_url,
    }


def classify_candidate(body: str) -> str:
    lowered = body.lower()
    if any(term in lowered for term in ("not held", "refused under section", "section 18(f)", "section 17(f)")):
        return "no_answer"
    if re.search(r"\$[\d,]+|\b\d{4}/\d{2}\b|\b\d{1,3}(?:,\d{3})+\b|\b\d+\.\d+%", body):
        return "numeric"
    if len(re.findall(r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,}\b", body[:2500])) >= 3:
        return "exact_term"
    return "semantic"


def select_candidates(candidates: list[dict[str, Any]], count: int, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    buckets = {kind: [] for kind in KINDS}
    for candidate in candidates:
        buckets[candidate["kind"]].append(candidate)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    selected = []
    seen_requests = set()
    while len(selected) < count and any(buckets.values()):
        for kind in KINDS:
            while buckets[kind]:
                candidate = buckets[kind].pop()
                request_id = candidate.get("fyi_request_id")
                if request_id in seen_requests:
                    continue
                selected.append(candidate)
                seen_requests.add(request_id)
                break
            if len(selected) >= count:
                break
    return selected


def generate_question(base_url: str, model: str, candidate: dict[str, Any]) -> dict[str, Any]:
    prompt = build_prompt(candidate)
    last_error: Exception | None = None
    for attempt in range(2):
        payload = build_completion_payload(model, prompt, last_error, attempt)
        response = post_json(f"{base_url.rstrip('/')}/chat/completions", payload)
        content = response["choices"][0]["message"]["content"]
        try:
            return validate_llm_item(parse_json_object(content), candidate)
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = exc

    raise RuntimeError(f"LLM did not produce a valid eval item: {last_error}")


def build_completion_payload(
    model: str,
    prompt: str,
    last_error: Exception | None,
    attempt: int,
) -> dict[str, Any]:
    retry_note = ""
    if last_error is not None:
        retry_note = (
            f"\n\nPrevious response failed validation: {last_error}. "
            "Return every required key exactly as named."
        )
    return {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You create evaluation questions for a public-records RAG search system. "
                    "Return one strict JSON object and no markdown."
                ),
            },
            {"role": "user", "content": prompt + retry_note},
        ],
        "model": model,
        "temperature": 0.0 if attempt else 0.2,
        "max_tokens": 900,
    }


def build_prompt(candidate: dict[str, Any]) -> str:
    answerable_instruction = (
        "For no_answer items, ask a question that a user might reasonably ask from the "
        "request title, but where the excerpt shows the exact requested detail was refused, "
        "not held, or not actually provided."
        if candidate["kind"] == "no_answer"
        else "Make the question answerable from the excerpt."
    )
    return f"""
Create one eval item for this FYI official-information release.

Kind: {candidate["kind"]}
Authority: {candidate.get("authority_name")}
Request title: {candidate.get("request_title")}
Request URL: {candidate.get("request_url")}
Document ID: {candidate.get("document_id")}
Original filename: {candidate.get("original_filename")}

{answerable_instruction}

Rules:
- The question must sound like a real public user search query.
- Do not mention "the excerpt" or "this document".
- Prefer concrete names, programmes, statutes, amounts, dates, or outcomes.
- expected_answer must be short and grounded only in the excerpt.
- supporting_passage must be copied exactly from the excerpt and be 80-260 characters.
- expected_terms should contain 3-8 useful retrieval terms.
- must_not_claim should list 1-3 claims that would be unsupported or wrong.

Return exactly this JSON shape:
{{
  "question": "...",
  "kind": "{candidate["kind"]}",
  "answerable": true,
  "expected_answer": "...",
  "expected_terms": ["..."],
  "supporting_passage": "...",
  "must_not_claim": ["..."]
}}

Excerpt:
{candidate["excerpt"]}
""".strip()


def build_manifest_row(
    candidate: dict[str, Any],
    llm_item: dict[str, Any],
    index: int,
    model: str,
) -> dict[str, Any]:
    request_id = candidate.get("fyi_request_id")
    attachment_id = candidate.get("fyi_attachment_id")
    return {
        "answerable": llm_item["answerable"],
        "document_id": candidate["document_id"],
        "expected_answer": llm_item["expected_answer"],
        "expected_authorities": compact_list([candidate.get("authority_name")]),
        "expected_documents": [candidate["document_id"]],
        "expected_requests": [candidate["request_url"]],
        "expected_terms": llm_item["expected_terms"],
        "generated_by": model,
        "id": f"fyi-{request_id}-{attachment_id}-{index:03d}",
        "kind": llm_item["kind"],
        "metadata": {
            "authority_name": candidate.get("authority_name"),
            "fyi_attachment_id": attachment_id,
            "fyi_request_id": request_id,
            "fyi_response_id": candidate.get("fyi_response_id"),
            "original_filename": candidate.get("original_filename"),
            "request_title": candidate.get("request_title"),
            "request_year": candidate.get("request_year"),
        },
        "must_not_claim": llm_item["must_not_claim"],
        "question": llm_item["question"],
        "request_url": candidate["request_url"],
        "reviewed": False,
        "source": "llm_generated_from_fyi_markdown",
        "source_url": candidate.get("source_url"),
        "supporting_passage": llm_item["supporting_passage"],
    }


def validate_llm_item(item: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    normalize_aliases(item)
    kind = item.get("kind")
    if kind not in KINDS:
        item["kind"] = candidate["kind"]
    item["answerable"] = bool(item.get("answerable")) and candidate["kind"] != "no_answer"
    return {
        "answerable": item["answerable"],
        "expected_answer": require_string(item, "expected_answer", min_length=8),
        "expected_terms": require_string_list(item, "expected_terms", min_items=3, max_items=8),
        "kind": item["kind"],
        "must_not_claim": require_string_list(item, "must_not_claim", min_items=1, max_items=3),
        "question": require_string(item, "question", min_length=20),
        "supporting_passage": require_string(item, "supporting_passage", min_length=40),
    }


def normalize_aliases(item: dict[str, Any]) -> None:
    aliases = {
        "expected_answer": ("answer", "expected_response"),
        "expected_terms": ("terms", "retrieval_terms"),
        "must_not_claim": ("unsupported_claims", "do_not_claim"),
        "supporting_passage": ("supporting_quote", "evidence"),
    }
    for target, alternatives in aliases.items():
        if target in item:
            continue
        for alternative in alternatives:
            if alternative in item:
                item[target] = item[alternative]
                break


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc


def parse_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"LLM did not return a JSON object: {content[:200]}")
    value = json.loads(stripped[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("LLM returned JSON, but not an object")
    return value


def extract_excerpt(body: str) -> str:
    text = re.sub(r"<!--.*?-->", " ", body, flags=re.DOTALL)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) <= MAX_EXCERPT_CHARS:
        return text

    lowered = text.lower()
    signals = ["you asked", "our response", "we have decided", "refused", "not held"]
    indexes = [lowered.find(signal) for signal in signals if lowered.find(signal) != -1]
    start = max(0, min(indexes) - 500) if indexes else 0
    return text[start : start + MAX_EXCERPT_CHARS].strip()


def require_string(item: dict[str, Any], key: str, min_length: int) -> str:
    value = item.get(key)
    if not isinstance(value, str) or len(value.strip()) < min_length:
        raise ValueError(f"LLM field {key!r} is missing or too short")
    return re.sub(r"\s+", " ", value).strip()


def require_string_list(
    item: dict[str, Any],
    key: str,
    min_items: int,
    max_items: int,
) -> list[str]:
    value = item.get(key)
    if not isinstance(value, list):
        raise ValueError(f"LLM field {key!r} must be a list")
    strings = [re.sub(r"\s+", " ", term).strip() for term in value if isinstance(term, str)]
    strings = [term for term in strings if term]
    if len(strings) < min_items:
        raise ValueError(f"LLM field {key!r} needs at least {min_items} values")
    return strings[:max_items]


def compact_list(values: list[Any]) -> list[str]:
    return [value for value in values if isinstance(value, str) and value.strip()]


def as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def as_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
