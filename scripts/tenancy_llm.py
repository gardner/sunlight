from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from tenancy_corpus import (
    PIPELINE_VERSION,
    SOURCE,
    parse_tenancy_markdown,
    render_tenancy_markdown,
)
from tenancy_instructor import (
    DEFAULT_INSTRUCTOR_MODE,
    instructor_client,
)
from tenancy_llm_messages import build_enrichment_messages
from tenancy_llm_request import ChatRequestOptions, chat_completion_kwargs, llm_error_summary
from tenancy_rate_limit import RequestRateLimiter


LLM_ENRICHMENT_VERSION = "tenancy-llm-v2"
LLM_PROMPT_TOKEN_MARGIN = 1024
LLM_BATCH_BUILD_PROGRESS_INTERVAL = 1000
LLM_API_MODE_CHAT = "chat"
LLM_API_MODE_INSTRUCTOR = "instructor"
LLM_API_MODE_RESPONSES = "responses"


class LegalPrinciple(BaseModel):
    principle: str = ""
    confidence: str = "medium"
    source_section: str = ""

class GeneratedEnrichment(BaseModel):
    document_id: str
    case_summary: str = ""
    catchwords: list[str] = Field(default_factory=list)
    questions_answered: list[str] = Field(default_factory=list)
    applicant_story: str = ""
    respondent_story: str = ""
    neutral_fact_pattern: str = ""
    claims_made: list[str] = Field(default_factory=list)
    remedies_sought: list[str] = Field(default_factory=list)
    legal_principles: list[LegalPrinciple] = Field(default_factory=list)
    llm_suggested_tags: list[str] = Field(default_factory=list)


class GeneratedEnrichmentBatch(BaseModel):
    items: list[GeneratedEnrichment]

@dataclass(frozen=True)
class LlmBatch:
    markdown_paths: list[Path]
    documents: list[dict[str, object]]
    prompt_tokens: int


GENERATED_ENRICHMENT_FIELDS = (
    "case_summary", "catchwords", "questions_answered",
    "applicant_story", "respondent_story", "neutral_fact_pattern",
    "claims_made", "remedies_sought", "legal_principles", "llm_suggested_tags",
)


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
    for key in GENERATED_ENRICHMENT_FIELDS:
        merged.pop(key, None)
    for key in GENERATED_ENRICHMENT_FIELDS:
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


def build_llm_input(markdown_paths: list[Path]) -> list[dict[str, object]]:
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
                "document_text": body.strip(),
            }
        )
    return items


def load_qwen_tokenizer(model: str):
    from transformers import AutoTokenizer

    try:
        return AutoTokenizer.from_pretrained(model, local_files_only=True)
    except OSError:
        return AutoTokenizer.from_pretrained(model)


def build_llm_batches(
    markdown_paths: list[Path],
    *,
    tokenizer,
    prompt_token_budget: int,
    max_batch_size: int,
    progress_interval: int = LLM_BATCH_BUILD_PROGRESS_INTERVAL,
) -> list[LlmBatch]:
    if not markdown_paths:
        return []

    batches: list[LlmBatch] = []
    current_paths: list[Path] = []
    current_documents: list[dict[str, object]] = []
    current_document_tokens: list[int] = []
    base_prompt_tokens = estimate_llm_batch_prompt_tokens([], tokenizer)
    document_separator_tokens = len(tokenizer.encode(", "))

    for index, path in enumerate(markdown_paths, start=1):
        [document] = build_llm_input([path])
        document_tokens = estimate_llm_document_tokens(document, tokenizer)
        candidate_tokens = estimate_llm_batch_prompt_tokens_from_parts(
            base_prompt_tokens,
            [*current_document_tokens, document_tokens],
            document_separator_tokens,
        )
        would_exceed_tokens = current_documents and candidate_tokens > prompt_token_budget
        would_exceed_count = len(current_documents) >= max_batch_size
        if would_exceed_tokens or would_exceed_count:
            append_llm_batch(
                batches,
                current_paths,
                current_documents,
                tokenizer,
                prompt_token_budget,
            )
            current_paths = []
            current_documents = []
            current_document_tokens = []
            candidate_tokens = estimate_llm_batch_prompt_tokens_from_parts(
                base_prompt_tokens,
                [document_tokens],
                document_separator_tokens,
            )

        current_paths.append(path)
        current_documents.append(document)
        current_document_tokens.append(document_tokens)

        if candidate_tokens > prompt_token_budget and len(current_documents) == 1:
            append_llm_batch(
                batches,
                current_paths,
                current_documents,
                tokenizer,
                prompt_token_budget,
            )
            current_paths = []
            current_documents = []
            current_document_tokens = []

        if progress_interval and index % progress_interval == 0:
            print(
                f"LLM batch build progress {index}/{len(markdown_paths)}: "
                f"{len(batches)} request(s)",
                flush=True,
            )

    if current_documents:
        append_llm_batch(
            batches,
            current_paths,
            current_documents,
            tokenizer,
            prompt_token_budget,
        )

    return batches


def append_llm_batch(
    batches: list[LlmBatch],
    markdown_paths: list[Path],
    documents: list[dict[str, object]],
    tokenizer,
    prompt_token_budget: int,
) -> None:
    prompt_tokens = estimate_llm_batch_prompt_tokens(documents, tokenizer)
    if prompt_tokens <= prompt_token_budget or len(documents) == 1:
        batches.append(
            LlmBatch(
                markdown_paths=list(markdown_paths),
                documents=list(documents),
                prompt_tokens=prompt_tokens,
            )
        )
        return

    midpoint = max(1, len(documents) // 2)
    append_llm_batch(
        batches,
        markdown_paths[:midpoint],
        documents[:midpoint],
        tokenizer,
        prompt_token_budget,
    )
    append_llm_batch(
        batches,
        markdown_paths[midpoint:],
        documents[midpoint:],
        tokenizer,
        prompt_token_budget,
    )


def estimate_llm_document_tokens(document: dict[str, object], tokenizer) -> int:
    return len(tokenizer.encode(json.dumps(document, ensure_ascii=True)))


def estimate_llm_batch_prompt_tokens_from_parts(
    base_prompt_tokens: int,
    document_tokens: list[int],
    document_separator_tokens: int,
) -> int:
    if not document_tokens:
        return base_prompt_tokens
    return (
        base_prompt_tokens
        + sum(document_tokens)
        + max(0, len(document_tokens) - 1) * document_separator_tokens
    )


def estimate_llm_batch_prompt_tokens(documents: list[dict[str, object]], tokenizer) -> int:
    messages = build_enrichment_messages(documents)
    return sum(len(tokenizer.encode(message["content"])) + 4 for message in messages)


def llm_prompt_token_budget(context_tokens: int, max_tokens: int) -> int:
    return max(1, context_tokens - max_tokens - LLM_PROMPT_TOKEN_MARGIN)


def effective_llm_prompt_token_budget(
    *,
    context_tokens: int,
    max_tokens: int,
    requested_prompt_tokens: int,
) -> int:
    return min(
        requested_prompt_tokens,
        llm_prompt_token_budget(context_tokens, max_tokens),
    )


def enrich_with_llm(
    markdown_paths: list[Path],
    *,
    base_url: str,
    api_key: str,
    model: str,
    tokenizer_model: str,
    context_tokens: int,
    prompt_token_budget: int,
    rpm: int,
    batch_size: int,
    concurrency: int,
    timeout: int,
    max_tokens: int,
    api_mode: str = LLM_API_MODE_CHAT,
    instructor_mode: str = DEFAULT_INSTRUCTOR_MODE,
    chat_options: ChatRequestOptions | None = None,
    start_jitter_seconds: tuple[float, float] = (0, 0),
) -> dict[str, int]:
    from openai import OpenAI

    client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
    if api_mode == LLM_API_MODE_INSTRUCTOR:
        client = instructor_client(client, instructor_mode)
    print(f"Loading LLM tokenizer: {tokenizer_model}", flush=True)
    tokenizer = load_qwen_tokenizer(tokenizer_model)
    print(f"Loaded LLM tokenizer: {tokenizer_model}", flush=True)
    effective_prompt_budget = effective_llm_prompt_token_budget(
        context_tokens=context_tokens,
        max_tokens=max_tokens,
        requested_prompt_tokens=prompt_token_budget,
    )
    batches = build_llm_batches(
        markdown_paths,
        tokenizer=tokenizer,
        prompt_token_budget=effective_prompt_budget,
        max_batch_size=batch_size,
    )
    print(
        f"LLM enrichment batching: {len(markdown_paths)} files -> {len(batches)} request(s), "
        f"model={model}, tokenizer={tokenizer_model}, concurrency={concurrency}, "
        f"prompt_budget={effective_prompt_budget}",
        flush=True,
    )
    return enrich_batches_with_llm(
        client=client,
        batches=batches,
        model=model,
        max_tokens=max_tokens,
        api_mode=api_mode,
        instructor_mode=instructor_mode,
        chat_options=chat_options,
        start_jitter_seconds=start_jitter_seconds,
        rpm=rpm,
        concurrency=concurrency,
        total_files=len(markdown_paths),
    )


def enrich_batches_with_llm(
    *,
    client,
    batches: list[LlmBatch],
    model: str,
    max_tokens: int,
    api_mode: str,
    instructor_mode: str,
    chat_options: ChatRequestOptions | None,
    start_jitter_seconds: tuple[float, float],
    rpm: int,
    concurrency: int,
    total_files: int,
) -> dict[str, int]:
    counts = {"enriched": 0, "failed": 0}
    processed = 0
    rate_limiter = RequestRateLimiter(rpm)
    max_workers = max(1, min(concurrency, len(batches) or 1))

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        pending = {}
        next_batch_index = 0

        def submit_next() -> None:
            nonlocal next_batch_index
            if next_batch_index >= len(batches):
                return
            batch = batches[next_batch_index]
            future = executor.submit(
                request_batch_with_rate_limit, client, batch, model, max_tokens, api_mode,
                rate_limiter, instructor_mode, start_jitter_seconds, chat_options,
            )
            pending[future] = (next_batch_index, batch)
            next_batch_index += 1

        for _ in range(max_workers):
            submit_next()

        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                batch_index, batch = pending.pop(future)
                try:
                    parsed = future.result()
                except Exception as exc:
                    counts["failed"] += len(batch.markdown_paths)
                    processed += len(batch.markdown_paths)
                    print(f"LLM enrichment failed for request {batch_index + 1}: {exc}", flush=True)
                    submit_next()
                    continue

                apply_batch_enrichment(batch, parsed, model, counts)
                processed += len(batch.markdown_paths)
                print(
                    f"LLM enrichment progress {processed}/{total_files}: {counts} "
                    f"(request {batch_index + 1}/{len(batches)}, "
                    f"files={len(batch.markdown_paths)}, prompt_tokens={batch.prompt_tokens})",
                    flush=True,
                )
                submit_next()

    return counts


def request_batch_with_rate_limit(
    client,
    batch: LlmBatch,
    model: str,
    max_tokens: int,
    api_mode: str,
    rate_limiter: RequestRateLimiter,
    instructor_mode: str = DEFAULT_INSTRUCTOR_MODE,
    start_jitter_seconds: tuple[float, float] = (0, 0),
    chat_options: ChatRequestOptions | None = None,
    *,
    sleep: Callable[[float], None] = time.sleep,
    random_uniform: Callable[[float, float], float] = random.uniform,
    attempts: int = 3,
) -> GeneratedEnrichmentBatch:
    jitter_min, jitter_max = start_jitter_seconds
    if jitter_max > 0:
        sleep(max(0, random_uniform(jitter_min, jitter_max)))
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        snapshot = rate_limiter.wait()
        print(
            "LLM request start: "
            f"started_at={utc_now_iso()} "
            f"rpm_window={snapshot.starts_last_60s}/{snapshot.rpm_limit} "
            f"attempt={attempt}/{attempts} "
            f"files={len(batch.markdown_paths)} "
            f"documents={len(batch.documents)} "
            f"prompt_tokens={batch.prompt_tokens}",
            flush=True,
        )
        try:
            return request_generated_enrichment_for_documents(
                client, batch.documents, model, max_tokens, api_mode=api_mode,
                instructor_mode=instructor_mode, chat_options=chat_options,
            )
        except Exception as exc:
            last_error = exc
            print(
                f"LLM request attempt failed: attempt={attempt}/{attempts} "
                f"{llm_error_summary(exc)}",
                flush=True,
            )
            if attempt == attempts:
                break
            sleep(min(2**attempt, 10))
    assert last_error is not None
    raise last_error


def apply_batch_enrichment(
    batch: LlmBatch,
    parsed: GeneratedEnrichmentBatch,
    model: str,
    counts: dict[str, int],
) -> None:
    by_id = {item.document_id: item for item in parsed.items}
    now = utc_now_iso()
    for path in batch.markdown_paths:
        metadata, _ = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
        item = by_id.get(str(metadata["document_id"]))
        if item is None:
            print(f"LLM enrichment missing item for {metadata['document_id']}: returned_ids={list(by_id)}", flush=True)
            counts["failed"] += 1
            continue
        apply_generated_enrichment(
            path,
            item.model_dump(exclude_none=True),
            model=model,
            now=now,
        )
        counts["enriched"] += 1


def request_generated_enrichment(
    client,
    markdown_paths: list[Path],
    model: str,
    max_tokens: int,
    api_mode: str = LLM_API_MODE_CHAT,
    instructor_mode: str = DEFAULT_INSTRUCTOR_MODE,
    chat_options: ChatRequestOptions | None = None,
) -> GeneratedEnrichmentBatch:
    return request_generated_enrichment_for_documents(
        client, build_llm_input(markdown_paths), model, max_tokens,
        api_mode=api_mode, instructor_mode=instructor_mode, chat_options=chat_options,
    )


def request_generated_enrichment_for_documents(
    client,
    documents: list[dict[str, object]],
    model: str,
    max_tokens: int,
    api_mode: str = LLM_API_MODE_CHAT,
    instructor_mode: str = DEFAULT_INSTRUCTOR_MODE,
    chat_options: ChatRequestOptions | None = None,
) -> GeneratedEnrichmentBatch:
    if api_mode == LLM_API_MODE_RESPONSES:
        response = client.responses.parse(
            model=model,
            input=build_enrichment_messages(documents),
            text_format=GeneratedEnrichmentBatch,
            temperature=0,
        )
        return response.output_parsed

    if api_mode == LLM_API_MODE_INSTRUCTOR:
        response_model = GeneratedEnrichment if len(documents) == 1 else GeneratedEnrichmentBatch
        parsed = client.chat.completions.create(
            model=model,
            response_model=response_model,
            messages=build_enrichment_messages(documents),
            temperature=0,
            max_tokens=max_tokens,
            max_retries=1,
            extra_body={"reasoning_split": True},
        )
        if isinstance(parsed, GeneratedEnrichment):
            return GeneratedEnrichmentBatch(items=[parsed])
        return parsed

    response = client.chat.completions.create(
        **chat_completion_kwargs(
            model=model, messages=build_enrichment_messages(documents), max_tokens=max_tokens,
            response_schema=GeneratedEnrichmentBatch.model_json_schema(),
            options=chat_options,
        )
    )
    content = response.choices[0].message.content or ""
    if not content.strip():
        raise ValueError(f"LLM enrichment response content was empty; finish_reason={response.choices[0].finish_reason}")
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
    max_tokens: int,
    *,
    api_mode: str = LLM_API_MODE_CHAT,
    instructor_mode: str = DEFAULT_INSTRUCTOR_MODE,
    attempts: int = 3,
) -> GeneratedEnrichmentBatch:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_generated_enrichment(
                client, markdown_paths, model, max_tokens,
                api_mode=api_mode, instructor_mode=instructor_mode,
            )
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(2**attempt, 10))
    assert last_error is not None
    raise last_error


def request_generated_enrichment_for_documents_with_retries(
    client,
    documents: list[dict[str, object]],
    model: str,
    max_tokens: int,
    *,
    api_mode: str = LLM_API_MODE_CHAT,
    instructor_mode: str = DEFAULT_INSTRUCTOR_MODE,
    attempts: int = 3,
) -> GeneratedEnrichmentBatch:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return request_generated_enrichment_for_documents(
                client, documents, model, max_tokens,
                api_mode=api_mode, instructor_mode=instructor_mode,
            )
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(2**attempt, 10))
    assert last_error is not None
    raise last_error
