"""Run local search retrieval evals against the FYI LanceDB corpus."""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


DEFAULT_QUESTIONS = Path("manifests/fyi/v1/eval-questions.ndjson")
DEFAULT_PRIMARY_LANCEDB = Path("/mnt/dgx-ssd/src/sunlight_backup/storage/fyi_parallel.lancedb")
DEFAULT_FALLBACK_LANCEDB = Path("storage/fyi_parallel.lancedb")
DEFAULT_TABLE = "chunks"
DEFAULT_OUTPUT_ROOT = Path("storage/evals/search")
DEFAULT_EMBED_MODEL = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_RERANK_MODEL = "BAAI/bge-reranker-base"
DEFAULT_TOP_K = 50
DEFAULT_RERANK_TOP_K = 20
DEFAULT_FINAL_K = 5


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate local FYI search over LanceDB with Qwen embeddings and BGE reranking."
    )
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--lancedb-uri", type=Path, default=default_lancedb_uri())
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--embed-model", default=DEFAULT_EMBED_MODEL)
    parser.add_argument("--rerank-model", default=DEFAULT_RERANK_MODEL)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--rerank-top-k", type=int, default=DEFAULT_RERANK_TOP_K)
    parser.add_argument("--final-k", type=int, default=DEFAULT_FINAL_K)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--device", default="auto", choices=("auto", "cpu", "cuda"))
    parser.add_argument("--no-rerank", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)

    output_dir = args.output_dir or timestamped_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_questions(args.questions, args.limit)
    table = open_lancedb_table(args.lancedb_uri, args.table)
    covered_rows = annotate_corpus_coverage(table, rows)

    device = resolve_device(args.device)
    embedder = load_embedder(args.embed_model, device)
    reranker = None if args.no_rerank else load_reranker(args.rerank_model, device)

    results = []
    for index, row in enumerate(covered_rows, start=1):
        print(f"Evaluating {index}/{len(covered_rows)} {row['id']}: {row['question']}", flush=True)
        results.append(evaluate_question(row, table, embedder, reranker, args))

    write_outputs(output_dir, results, args)
    print(f"Wrote eval results to {output_dir}", flush=True)
    return 0


def validate_args(args: argparse.Namespace) -> None:
    if not args.questions.exists():
        raise SystemExit(f"Questions file not found: {args.questions}")
    if not args.lancedb_uri.exists():
        raise SystemExit(f"LanceDB path not found: {args.lancedb_uri}")
    if args.top_k < 1 or args.rerank_top_k < 1 or args.final_k < 1:
        raise SystemExit("top-k values must be positive")
    if args.rerank_top_k > args.top_k:
        raise SystemExit("--rerank-top-k cannot exceed --top-k")
    if args.final_k > args.rerank_top_k:
        raise SystemExit("--final-k cannot exceed --rerank-top-k")


def default_lancedb_uri() -> Path:
    if DEFAULT_PRIMARY_LANCEDB.exists():
        return DEFAULT_PRIMARY_LANCEDB
    return DEFAULT_FALLBACK_LANCEDB


def timestamped_output_dir() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUTPUT_ROOT / timestamp


def read_questions(path: Path, limit: int | None) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
        if limit is not None and len(rows) >= limit:
            break
    return rows


def open_lancedb_table(uri: Path, table_name: str):
    import lancedb

    database = lancedb.connect(str(uri))
    names = table_names(database)
    if table_name not in names:
        raise SystemExit(f"Table {table_name!r} not found in {uri}; available tables: {names}")
    return database.open_table(table_name)


def table_names(database) -> list[str]:
    if hasattr(database, "list_tables"):
        value = database.list_tables()
        if isinstance(value, list):
            return value
        tables = getattr(value, "tables", None)
        if isinstance(tables, list):
            return tables
    return database.table_names()


def annotate_corpus_coverage(table, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated = []
    for row in rows:
        expected_documents = row.get("expected_documents") or []
        expected_requests = row.get("expected_requests") or []
        document_count = sum(count_rows(table, "document_id", value) for value in expected_documents)
        request_count = sum(count_rows(table, "request_url", value) for value in expected_requests)
        annotated.append({
            **row,
            "corpus_document_rows": document_count,
            "corpus_request_rows": request_count,
        })
    return annotated


def count_rows(table, column: str, value: str) -> int:
    return table.count_rows(f"{column} = {json.dumps(value)}")


def resolve_device(value: str) -> str:
    if value != "auto":
        return value
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def load_embedder(model_name: str, device: str):
    import torch
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    kwargs: dict[str, Any] = {
        "device": device,
        "embed_batch_size": 8,
        "max_length": 8192,
        "model_name": model_name,
    }
    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        kwargs["model_kwargs"] = {
            "attn_implementation": "flash_attention_2",
            "torch_dtype": torch.bfloat16,
        }

    try:
        return HuggingFaceEmbedding(**kwargs)
    except Exception:
        kwargs.pop("model_kwargs", None)
        return HuggingFaceEmbedding(**kwargs)


def load_reranker(model_name: str, device: str):
    from sentence_transformers import CrossEncoder

    return CrossEncoder(model_name, device=device)


def evaluate_question(row: dict[str, Any], table, embedder, reranker, args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    embedding_started = time.perf_counter()
    vector = embedder.get_query_embedding(row["question"])
    embedding_ms = elapsed_ms(embedding_started)

    retrieval_started = time.perf_counter()
    vector_results = search_lancedb(table, vector, args.top_k)
    retrieval_ms = elapsed_ms(retrieval_started)

    rerank_results = []
    rerank_ms = 0
    if reranker is not None:
        rerank_started = time.perf_counter()
        rerank_results = rerank(row["question"], vector_results[: args.rerank_top_k], reranker)
        rerank_ms = elapsed_ms(rerank_started)

    final_results = (rerank_results or vector_results)[: args.final_k]
    return {
        "answerable": row.get("answerable"),
        "corpus_document_rows": row["corpus_document_rows"],
        "corpus_request_rows": row["corpus_request_rows"],
        "expected_documents": row.get("expected_documents") or [],
        "expected_requests": row.get("expected_requests") or [],
        "final_hit": has_hit(final_results, row),
        "final_mrr": reciprocal_rank(final_results, row),
        "final_top_k": compact_results(final_results),
        "id": row["id"],
        "kind": row.get("kind"),
        "question": row["question"],
        "rerank_hit_at_final_k": has_hit((rerank_results or [])[: args.final_k], row),
        "rerank_mrr_at_final_k": reciprocal_rank((rerank_results or [])[: args.final_k], row),
        "rerank_top_k": compact_results((rerank_results or [])[: args.rerank_top_k]),
        "timings_ms": {
            "embedding": embedding_ms,
            "retrieval": retrieval_ms,
            "rerank": rerank_ms,
            "total": elapsed_ms(started),
        },
        "vector_hit_at_top_k": has_hit(vector_results, row),
        "vector_mrr_at_top_k": reciprocal_rank(vector_results, row),
        "vector_top_k": compact_results(vector_results),
    }


def search_lancedb(table, vector: list[float], top_k: int) -> list[dict[str, Any]]:
    rows = table.search(vector, vector_column_name="vector").metric("cosine").limit(top_k).to_list()
    return [normalize_result(row, rank) for rank, row in enumerate(rows, start=1)]


def normalize_result(row: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "chunk_id": row.get("chunk_id"),
        "chunk_index": row.get("chunk_index"),
        "distance": round_float(row.get("_distance")),
        "document_id": row.get("document_id"),
        "original_filename": row.get("original_filename"),
        "rank": rank,
        "request_url": row.get("request_url"),
        "source_url": row.get("source_url"),
        "text_preview": row.get("text_preview"),
    }


def rerank(question: str, results: list[dict[str, Any]], reranker) -> list[dict[str, Any]]:
    pairs = [(question, rerank_context(result)) for result in results]
    scores = reranker.predict(pairs)
    scored = [
        {
            **result,
            "rerank_rank": index + 1,
            "rerank_score": round_float(float(score)),
        }
        for index, (result, score) in enumerate(
            sorted(zip(results, scores, strict=True), key=lambda item: float(item[1]), reverse=True)
        )
    ]
    return scored


def rerank_context(result: dict[str, Any]) -> str:
    return "\n".join(
        part for part in [
            f"Document: {result.get('original_filename')}",
            f"Request URL: {result.get('request_url')}",
            f"Snippet: {result.get('text_preview')}",
        ]
        if part
    )


def has_hit(results: list[dict[str, Any]], row: dict[str, Any]) -> bool:
    return reciprocal_rank(results, row) > 0


def reciprocal_rank(results: list[dict[str, Any]], row: dict[str, Any]) -> float:
    expected_documents = set(row.get("expected_documents") or [])
    expected_requests = set(row.get("expected_requests") or [])
    for index, result in enumerate(results, start=1):
        if result.get("document_id") in expected_documents or result.get("request_url") in expected_requests:
            return 1 / index
    return 0


def compact_results(results: list[dict[str, Any]], keep: int = 10) -> list[dict[str, Any]]:
    compact = []
    for result in results[:keep]:
        compact.append({
            key: result.get(key)
            for key in (
                "rank",
                "rerank_rank",
                "document_id",
                "chunk_id",
                "distance",
                "rerank_score",
                "request_url",
                "original_filename",
            )
            if result.get(key) is not None
        })
    return compact


def write_outputs(output_dir: Path, results: list[dict[str, Any]], args: argparse.Namespace) -> None:
    results_path = output_dir / "results.ndjson"
    with results_path.open("w", encoding="utf-8") as handle:
        for result in results:
            handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")

    report_path = output_dir / "report.md"
    report_path.write_text(render_report(results, args), encoding="utf-8")


def render_report(results: list[dict[str, Any]], args: argparse.Namespace) -> str:
    covered = [row for row in results if row["corpus_document_rows"] > 0]
    by_kind = Counter(row.get("kind") or "unknown" for row in results)
    lines = [
        "# Search Eval Report",
        "",
        f"Questions: {len(results)}",
        f"Covered expected documents: {len(covered)}/{len(results)}",
        f"LanceDB: `{args.lancedb_uri}`",
        f"Table: `{args.table}`",
        f"Embedding model: `{args.embed_model}`",
        f"Reranker: `{args.rerank_model if not args.no_rerank else 'disabled'}`",
        "",
        "## Metrics",
        "",
        f"* Vector recall@{args.top_k}: {mean_bool(results, 'vector_hit_at_top_k'):.3f}",
        f"* Vector MRR@{args.top_k}: {mean_value(results, 'vector_mrr_at_top_k'):.3f}",
        f"* Rerank recall@{args.final_k}: {mean_bool(results, 'rerank_hit_at_final_k'):.3f}",
        f"* Rerank MRR@{args.final_k}: {mean_value(results, 'rerank_mrr_at_final_k'):.3f}",
        f"* Final recall@{args.final_k}: {mean_bool(results, 'final_hit'):.3f}",
        f"* Final MRR@{args.final_k}: {mean_value(results, 'final_mrr'):.3f}",
        "",
        "## Metrics By Question Type",
        "",
    ]
    lines.extend(render_grouped_metrics(results, question_kind_group, args))
    lines.extend([
        "",
        "## Metrics By Answerability",
        "",
    ])
    lines.extend(render_grouped_metrics(results, answerability_group, args))
    lines.extend([
        "",
        "## Question Types",
        "",
    ])
    lines.extend(f"* {kind}: {count}" for kind, count in sorted(by_kind.items()))
    lines.extend(["", "## Stage Regressions", ""])
    regressions = stage_regressions(results)
    if not regressions:
        lines.append("No first-stage retrieval hits were lost by final selection.")
    else:
        for row in regressions:
            lines.append(f"* `{row['id']}` {row['question']}")
    lines.extend(["", "## Misses", ""])
    misses = [row for row in results if not row["final_hit"]]
    if not misses:
        lines.append("No final-stage misses.")
    else:
        for row in misses:
            lines.append(f"* `{row['id']}` {row['question']}")
    lines.append("")
    return "\n".join(lines)


def render_grouped_metrics(
    rows: list[dict[str, Any]],
    group_key: Callable[[dict[str, Any]], str],
    args: argparse.Namespace,
) -> list[str]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(group_key(row), []).append(row)

    lines = [
        (
            f"| Group | Questions | Vector Recall@{args.top_k} | "
            f"Final Recall@{args.final_k} | Vector MRR@{args.top_k} | "
            f"Final MRR@{args.final_k} |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group, group_rows in sorted(groups.items()):
        lines.append(
            f"| {group} | {len(group_rows)} | "
            f"{mean_bool(group_rows, 'vector_hit_at_top_k'):.3f} | "
            f"{mean_bool(group_rows, 'final_hit'):.3f} | "
            f"{mean_value(group_rows, 'vector_mrr_at_top_k'):.3f} | "
            f"{mean_value(group_rows, 'final_mrr'):.3f} |"
        )
    return lines


def question_kind_group(row: dict[str, Any]) -> str:
    return str(row.get("kind") or "unknown")


def answerability_group(row: dict[str, Any]) -> str:
    if row.get("answerable") is True:
        return "answerable"
    if row.get("answerable") is False:
        return "not_answerable"
    return "unknown"


def stage_regressions(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in results
        if row.get("vector_hit_at_top_k") and not row.get("final_hit")
    ]


def mean_bool(rows: list[dict[str, Any]], key: str) -> float:
    return mean_value([{key: 1 if row.get(key) else 0} for row in rows], key)


def mean_value(rows: list[dict[str, Any]], key: str) -> float:
    if not rows:
        return 0
    values = [float(row.get(key) or 0) for row in rows]
    return sum(values) / len(values)


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def round_float(value: Any) -> float | None:
    if not isinstance(value, float | int) or not math.isfinite(value):
        return None
    return round(float(value), 6)


if __name__ == "__main__":
    raise SystemExit(main())
