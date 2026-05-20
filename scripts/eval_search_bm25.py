"""Local SQLite FTS5 BM25 helpers for search evals."""

from __future__ import annotations

import math
import sqlite3
import time
import unicodedata
from contextlib import closing
from pathlib import Path
from typing import Any


DEFAULT_BM25_DB = Path("storage/evals/search/local-bm25.sqlite3")
DEFAULT_BM25_BATCH_SIZE = 1000
FINAL_VECTOR_RESERVED = 1
FINAL_BM25_RESERVED = 2
MAX_FTS_TERMS = 12
VECTOR_WEIGHT = 0.55
BM25_WEIGHT = 0.45
RRF_K = 60
FTS_STOP_WORDS = {
    "about",
    "after",
    "all",
    "also",
    "and",
    "any",
    "are",
    "been",
    "between",
    "but",
    "can",
    "could",
    "did",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "information",
    "into",
    "its",
    "near",
    "not",
    "official",
    "or",
    "please",
    "provide",
    "provided",
    "release",
    "released",
    "request",
    "requested",
    "show",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
}
BM25_COLUMNS = (
    "chunk_id",
    "document_id",
    "authority_name",
    "request_title",
    "original_filename",
    "chunk_text",
    "request_url",
    "source_url",
    "chunk_index",
    "text_preview",
)


class LocalBm25Index:
    def __init__(self, path: Path):
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row

    def search(self, question: str, top_k: int) -> list[dict[str, Any]]:
        match_query = build_fts_match_query(question)
        if not match_query:
            return []
        rows = self.connection.execute(
            """
            SELECT
              c.chunk_id,
              c.document_id,
              c.request_url,
              c.source_url,
              c.original_filename,
              c.chunk_index,
              c.text_preview,
              bm25(disclosed_chunks_fts, 0.0, 0.0, 2.0, 3.0, 1.0, 1.0) AS bm25_score
            FROM disclosed_chunks_fts
            JOIN disclosed_chunks c ON c.rowid = disclosed_chunks_fts.rowid
            WHERE disclosed_chunks_fts MATCH ?
            ORDER BY bm25_score
            LIMIT ?
            """,
            (match_query, top_k),
        ).fetchall()
        return [normalize_bm25_result(dict(row), rank) for rank, row in enumerate(rows, start=1)]

    def close(self) -> None:
        self.connection.close()


def open_or_build_bm25_index(table, db_path: Path, batch_size: int, rebuild: bool) -> LocalBm25Index:
    if rebuild or not bm25_index_ready(db_path):
        build_bm25_index(table, db_path, batch_size)
    return LocalBm25Index(db_path)


def bm25_index_ready(path: Path) -> bool:
    if not path.exists():
        return False
    with closing(sqlite3.connect(path)) as connection:
        try:
            row = connection.execute("SELECT COUNT(*) FROM disclosed_chunks").fetchone()
        except sqlite3.Error:
            return False
    return bool(row and row[0] > 0)


def build_bm25_index(table, path: Path, batch_size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    with closing(sqlite3.connect(path)) as connection:
        create_bm25_schema(connection)
        total = insert_bm25_rows(connection, iter_lancedb_rows(table, BM25_COLUMNS, batch_size))
    print(f"Built local BM25 index with {total} chunks in {elapsed_ms(started)} ms: {path}", flush=True)


def create_bm25_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        DROP TABLE IF EXISTS disclosed_chunks;
        DROP TABLE IF EXISTS disclosed_chunks_fts;

        CREATE TABLE disclosed_chunks (
          chunk_id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          authority_name TEXT,
          request_title TEXT,
          original_filename TEXT,
          chunk_text TEXT NOT NULL,
          request_url TEXT,
          source_url TEXT,
          chunk_index INTEGER,
          text_preview TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE disclosed_chunks_fts USING fts5(
          chunk_id UNINDEXED,
          document_id UNINDEXED,
          authority_name,
          request_title,
          original_filename,
          chunk_text,
          tokenize='unicode61 remove_diacritics 2'
        );
        """
    )


def insert_bm25_rows(connection: sqlite3.Connection, rows) -> int:
    rowid = 0
    for row in rows:
        record = bm25_record(row)
        if not record["chunk_id"] or not record["document_id"] or not record["chunk_text"]:
            continue
        rowid += 1
        insert_bm25_row(connection, rowid, record)
        if rowid % 5000 == 0:
            connection.commit()
            print(f"Indexed {rowid} BM25 chunks", flush=True)
    connection.commit()
    return rowid


def insert_bm25_row(connection: sqlite3.Connection, rowid: int, record: dict[str, Any]) -> None:
    values = (rowid, *[record[column] for column in BM25_COLUMNS])
    connection.execute(
        f"INSERT INTO disclosed_chunks (rowid, {', '.join(BM25_COLUMNS)}) "
        f"VALUES ({', '.join(['?'] * (len(BM25_COLUMNS) + 1))})",
        values,
    )
    connection.execute(
        """
        INSERT INTO disclosed_chunks_fts(
          rowid, chunk_id, document_id, authority_name, request_title,
          original_filename, chunk_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rowid,
            record["chunk_id"],
            record["document_id"],
            record["authority_name"],
            record["request_title"],
            record["original_filename"],
            record["chunk_text"],
        ),
    )


def bm25_record(row: dict[str, Any]) -> dict[str, Any]:
    chunk_text = collapse_whitespace(str(row.get("chunk_text") or row.get("text_preview") or ""))
    return {
        "chunk_id": row.get("chunk_id"),
        "document_id": row.get("document_id"),
        "authority_name": row.get("authority_name"),
        "request_title": row.get("request_title"),
        "original_filename": row.get("original_filename"),
        "chunk_text": chunk_text,
        "request_url": row.get("request_url"),
        "source_url": row.get("source_url"),
        "chunk_index": row.get("chunk_index"),
        "text_preview": collapse_whitespace(str(row.get("text_preview") or chunk_text[:800])),
    }


def iter_lancedb_rows(table, columns: tuple[str, ...], batch_size: int):
    selected = selected_table_columns(table, columns)
    scanner = table.to_lance().scanner(columns=selected, batch_size=batch_size)
    for batch in scanner.to_batches():
        yield from batch.to_pylist()


def selected_table_columns(table, columns: tuple[str, ...]) -> list[str]:
    available = table_column_names(table)
    if not available:
        return list(columns)
    return [column for column in columns if column in available]


def table_column_names(table) -> set[str]:
    schema = getattr(table, "schema", None)
    if callable(schema):
        schema = schema()
    names = getattr(schema, "names", None)
    if names is None and hasattr(table, "to_lance"):
        names = getattr(table.to_lance().schema, "names", None)
    return set(names or [])


def normalize_bm25_result(row: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "bm25_rank": rank,
        "bm25_score": round_float(row.get("bm25_score")),
        "chunk_id": row.get("chunk_id"),
        "chunk_index": row.get("chunk_index"),
        "document_id": row.get("document_id"),
        "original_filename": row.get("original_filename"),
        "rank": rank,
        "request_url": row.get("request_url"),
        "source_url": row.get("source_url"),
        "text_preview": row.get("text_preview"),
    }


def build_fts_match_query(question: str) -> str:
    terms = [
        term
        for term in tokenize_fts_terms(question)
        if len(term) >= 2 and term not in FTS_STOP_WORDS
    ]
    unique_terms = list(dict.fromkeys(terms))[:MAX_FTS_TERMS]
    return " OR ".join(quote_fts_term(term) for term in unique_terms)


def tokenize_fts_terms(question: str) -> list[str]:
    terms: list[str] = []
    current: list[str] = []
    for character in question.lower():
        if character == "_" or character.isalnum():
            current.append(character)
        elif current:
            terms.append("".join(current))
            current = []
    if current:
        terms.append("".join(current))
    return [strip_diacritics(term) for term in terms]


def strip_diacritics(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(character for character in normalized if not unicodedata.combining(character))


def quote_fts_term(term: str) -> str:
    escaped = term.replace('"', '""')
    return f'"{escaped}"'


def fuse_search_results(
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    limit: int,
    vector_weight: float = VECTOR_WEIGHT,
    bm25_weight: float = BM25_WEIGHT,
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    for index, result in enumerate(vector_results, start=1):
        upsert_fused_candidate(
            candidates,
            result,
            fused_contribution=vector_weight * rrf_score(index),
            vector_rank=index,
            vector_score=result.get("score"),
        )
    for index, result in enumerate(bm25_results, start=1):
        upsert_fused_candidate(
            candidates,
            result,
            bm25_rank=index,
            bm25_score=result.get("bm25_score"),
            fused_contribution=bm25_weight * rrf_score(index),
        )
    return sorted(
        candidates.values(),
        key=lambda item: (-(item.get("fused_score") or 0), item.get("chunk_id") or ""),
    )[:limit]


def select_source_diverse_results(
    fused_results: list[dict[str, Any]],
    vector_results: list[dict[str, Any]],
    bm25_results: list[dict[str, Any]],
    final_k: int,
) -> list[dict[str, Any]]:
    if final_k <= 0:
        return []
    if final_k < 3:
        return dedupe_results(fused_results)[:final_k]

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    add_selected_results(selected, seen, vector_results, FINAL_VECTOR_RESERVED, final_k)
    add_selected_results(
        selected,
        seen,
        bm25_results,
        min(FINAL_BM25_RESERVED, final_k - len(selected)),
        final_k,
    )
    add_selected_results(selected, seen, fused_results, float("inf"), final_k)
    return selected


def dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    add_selected_results(selected, seen, results, float("inf"), len(results))
    return selected


def add_selected_results(
    selected: list[dict[str, Any]],
    seen: set[str],
    results: list[dict[str, Any]],
    result_limit: float,
    total_limit: int,
) -> None:
    added = 0
    for result in results:
        if len(selected) >= total_limit or added >= result_limit:
            return
        key = result_dedupe_key(result)
        if key in seen:
            continue
        seen.add(key)
        selected.append(result)
        added += 1


def result_dedupe_key(result: dict[str, Any]) -> str:
    return str(result.get("document_id") or result.get("source_url") or result.get("chunk_id"))


def upsert_fused_candidate(
    candidates: dict[str, dict[str, Any]],
    result: dict[str, Any],
    *,
    fused_contribution: float,
    bm25_rank: int | None = None,
    bm25_score: float | None = None,
    vector_rank: int | None = None,
    vector_score: float | None = None,
) -> None:
    chunk_id = str(result.get("chunk_id") or "")
    if not chunk_id:
        return
    existing = candidates.get(chunk_id, {})
    fused_score = float(existing.get("fused_score") or 0) + fused_contribution
    candidates[chunk_id] = {
        **result,
        **existing,
        "bm25_rank": existing.get("bm25_rank") or bm25_rank or result.get("bm25_rank"),
        "bm25_score": existing.get("bm25_score") or bm25_score or result.get("bm25_score"),
        "fused_score": round_float(fused_score),
        "score": round_float(fused_score),
        "vector_rank": existing.get("vector_rank") or vector_rank or result.get("vector_rank"),
        "vector_score": existing.get("vector_score") or vector_score or result.get("vector_score"),
    }


def rrf_score(rank: int) -> float:
    return 1 / (RRF_K + rank)


def collapse_whitespace(value: str) -> str:
    return " ".join(value.split())


def elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def round_float(value: Any) -> float | None:
    if not isinstance(value, float | int) or not math.isfinite(value):
        return None
    return round(float(value), 6)
