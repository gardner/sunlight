"""Bounded agentic retrieval controller for local search evals."""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable

from eval_search_bm25 import FTS_STOP_WORDS, fuse_search_results, tokenize_fts_terms


EXACT_ENTITY_PATTERN = re.compile(
    r"https?://(?:www\.)?fyi\.org\.nz/request/\d+|"
    r"doc_[a-z0-9_]+|\b[a-z]{2,}[-_]?\d{3,}\b|\b\d{4,}\b",
    re.IGNORECASE,
)
AGENTIC_STOP_WORDS = FTS_STOP_WORDS | {
    "a",
    "an",
    "as",
    "at",
    "be",
    "by",
    "in",
    "is",
    "of",
    "on",
    "to",
}
TENANCY_TERMS = {
    "adjudicator",
    "arrears",
    "bond",
    "landlord",
    "rent",
    "tenancy",
    "tenant",
    "termination",
    "tribunal",
}
NUMERIC_TERMS = {"amount", "cost", "date", "number", "total", "year"}


def add_agentic_parser_args(parser) -> None:
    parser.add_argument("--agentic", action="store_true")
    parser.add_argument("--agentic-max-rounds", type=int, default=2)
    parser.add_argument("--agentic-expansions", type=int, default=2)


def validate_agentic_args(args) -> None:
    if args.agentic_max_rounds < 1 or args.agentic_expansions < 0:
        raise SystemExit(
            "--agentic-max-rounds must be positive and --agentic-expansions non-negative"
        )


def retrieval_policy_label(args) -> str:
    return "agentic" if getattr(args, "agentic", False) else "hybrid"


@dataclass(frozen=True)
class AgenticQueryPlan:
    query_kind: str
    source_filter: str
    entities: list[str]
    must_terms: list[str]
    expanded_queries: list[str]
    needs_full_document: bool
    abstain_if_no_exact_evidence: bool


@dataclass(frozen=True)
class AgenticRetrievalResult:
    vector_results: list[dict[str, Any]]
    bm25_results: list[dict[str, Any]]
    hybrid_results: list[dict[str, Any]]
    trace: dict[str, Any]
    timings_ms: dict[str, int]


def build_agentic_query_plan(question: str) -> AgenticQueryPlan:
    terms = normalized_terms(question)
    entities = list(
        dict.fromkeys(match.group(0) for match in EXACT_ENTITY_PATTERN.finditer(question))
    )
    source_filter = "justice_tenancy" if TENANCY_TERMS.intersection(terms) else "all"
    query_kind = classify_query(terms, entities)
    must_terms = terms[:12]
    expanded_queries = build_expanded_queries(question, entities, must_terms, source_filter)
    exact_or_numeric = query_kind in {"exact_lookup", "numeric"}
    return AgenticQueryPlan(
        query_kind=query_kind,
        source_filter=source_filter,
        entities=entities,
        must_terms=must_terms,
        expanded_queries=expanded_queries,
        needs_full_document=exact_or_numeric,
        abstain_if_no_exact_evidence=exact_or_numeric,
    )


def normalized_terms(question: str) -> list[str]:
    return [
        term
        for term in tokenize_fts_terms(question)
        if len(term) >= 2 and term not in AGENTIC_STOP_WORDS
    ]


def classify_query(terms: list[str], entities: list[str]) -> str:
    if entities:
        return "exact_lookup"
    if NUMERIC_TERMS.intersection(terms) or any(term.isdigit() for term in terms):
        return "numeric"
    if TENANCY_TERMS.intersection(terms):
        return "tenancy_legal"
    return "semantic"


def build_expanded_queries(
    question: str,
    entities: list[str],
    terms: list[str],
    source_filter: str,
) -> list[str]:
    entity_terms = set(tokenize_fts_terms(" ".join(entities)))
    query_terms = [term for term in terms if term not in entity_terms]
    candidates = []
    if entities:
        candidates.append(" ".join([*entities, *query_terms]))
    if source_filter == "justice_tenancy":
        candidates.append(" ".join([*entities, "tenancy", "tribunal", *query_terms]))
    candidates.append(" ".join(query_terms or terms))
    return dedupe_queries(candidates, question)


def dedupe_queries(candidates: list[str], original_question: str) -> list[str]:
    original = compact_query(original_question)
    queries = []
    seen: set[str] = set()
    for candidate in candidates:
        query = " ".join(candidate.split())
        key = compact_query(query)
        if not query or key == original or key in seen:
            continue
        seen.add(key)
        queries.append(query)
    return queries


def compact_query(value: str) -> str:
    return " ".join(value.lower().split())


def extend_retrieval_with_agentic_rounds(
    question: str,
    initial_vector_results: list[dict[str, Any]],
    initial_bm25_results: list[dict[str, Any]],
    search_vector: Callable[[str], list[dict[str, Any]]],
    search_bm25: Callable[[str], list[dict[str, Any]]],
    *,
    top_k: int,
    vector_weight: float,
    bm25_weight: float,
    max_rounds: int,
    max_expansions: int,
) -> AgenticRetrievalResult:
    started = time.perf_counter()
    plan = build_agentic_query_plan(question)
    vector_rounds = [("original", initial_vector_results)]
    bm25_rounds = [("original", initial_bm25_results)]
    hybrid_results = fuse_search_results(
        initial_vector_results,
        initial_bm25_results,
        top_k,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
    )
    second_pass_reason = second_pass_reason_for(plan, initial_bm25_results, hybrid_results)
    trace_rounds = [trace_round("original", question, initial_vector_results, initial_bm25_results)]
    if second_pass_reason and max_rounds > 1:
        for query in plan.expanded_queries[:max_expansions]:
            vector_results = search_vector(query)
            bm25_results = search_bm25(query)
            vector_rounds.append((query, vector_results))
            bm25_rounds.append((query, bm25_results))
            trace_rounds.append(trace_round("expansion", query, vector_results, bm25_results))
    vector_results = merge_ranked_results(vector_rounds, "vector_rank")
    bm25_results = merge_ranked_results(bm25_rounds, "bm25_rank")
    hybrid_results = fuse_search_results(
        vector_results,
        bm25_results,
        top_k,
        vector_weight=vector_weight,
        bm25_weight=bm25_weight,
    )
    return AgenticRetrievalResult(
        vector_results=vector_results,
        bm25_results=bm25_results,
        hybrid_results=hybrid_results,
        trace={
            "plan": asdict(plan),
            "rounds": trace_rounds,
            "second_pass_reason": second_pass_reason,
        },
        timings_ms={"agentic_controller": elapsed_ms(started)},
    )


def second_pass_reason_for(
    plan: AgenticQueryPlan,
    bm25_results: list[dict[str, Any]],
    hybrid_results: list[dict[str, Any]],
) -> str | None:
    if not hybrid_results:
        return "no_candidates"
    if plan.query_kind in {"exact_lookup", "numeric"} and not has_key_evidence(
        plan,
        hybrid_results,
    ):
        return "exact_terms_missing"
    if plan.query_kind in {"exact_lookup", "numeric"} and not bm25_results:
        return "lexical_missing"
    return None


def has_key_evidence(plan: AgenticQueryPlan, results: list[dict[str, Any]]) -> bool:
    haystack = "\n".join(result_text(result) for result in results[:10]).lower()
    if not haystack:
        return False
    entities_present = all(entity.lower() in haystack for entity in plan.entities)
    content_terms = [term for term in plan.must_terms if not term.isdigit()]
    terms_present = not content_terms or any(term in haystack for term in content_terms)
    return entities_present and terms_present


def result_text(result: dict[str, Any]) -> str:
    return " ".join(
        str(result.get(key) or "")
        for key in ("document_id", "request_url", "source_url", "original_filename", "text_preview")
    )


def merge_ranked_results(
    rounds: list[tuple[str, list[dict[str, Any]]]],
    rank_key: str,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_key: dict[str, dict[str, Any]] = {}
    for query, results in rounds:
        for result in results:
            key = result_key(result)
            if not key:
                continue
            if key in by_key:
                by_key[key]["agentic_queries"].append(query)
                continue
            record = {**result, "agentic_queries": [query]}
            by_key[key] = record
            merged.append(record)
    for rank, result in enumerate(merged, start=1):
        result["rank"] = rank
        result[rank_key] = rank
    return merged


def result_key(result: dict[str, Any]) -> str:
    return str(result.get("chunk_id") or result.get("document_id") or "")


def trace_round(
    kind: str,
    query: str,
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "bm25_results": len(bm25_results),
        "kind": kind,
        "query": query,
        "vector_results": len(vector_results),
    }


def render_agentic_trace_summary(results: list[dict[str, Any]]) -> list[str]:
    agentic_rows = [row for row in results if row.get("retrieval_policy") == "agentic"]
    if not agentic_rows:
        return []
    reasons = Counter(
        agentic_trace(row).get("second_pass_reason")
        for row in agentic_rows
        if agentic_trace(row).get("second_pass_reason")
    )
    second_passes = sum(
        1
        for row in agentic_rows
        if len(agentic_trace(row).get("rounds", [])) > 1
    )
    lines = [
        "",
        "## Agentic Trace Summary",
        "",
        f"* Second-pass retrievals: {second_passes}/{len(agentic_rows)}",
    ]
    lines.extend(f"* {reason}: {count}" for reason, count in sorted(reasons.items()))
    return lines


def agentic_trace(row: dict[str, Any]) -> dict[str, Any]:
    return row.get("agentic_trace") or {}


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
