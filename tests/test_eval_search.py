import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import eval_search  # noqa: E402
import eval_search_bm25  # noqa: E402


def args() -> SimpleNamespace:
    return SimpleNamespace(
        embed_model="test-embed",
        final_k=5,
        lancedb_uri=Path("/tmp/fyi.lancedb"),
        no_rerank=False,
        rerank_model="test-rerank",
        table="chunks",
        top_k=50,
    )


def result(
    question_id: str,
    *,
    answerable: bool,
    corpus_document_rows: int = 1,
    final_hit: bool,
    final_mrr: float,
    kind: str,
    vector_hit: bool,
    vector_mrr: float,
) -> dict:
    return {
        "answerable": answerable,
        "corpus_document_rows": corpus_document_rows,
        "final_hit": final_hit,
        "final_mrr": final_mrr,
        "id": question_id,
        "kind": kind,
        "question": f"{kind} question",
        "rerank_hit_at_final_k": final_hit,
        "rerank_mrr_at_final_k": final_mrr,
        "bm25_hit_at_top_k": False,
        "bm25_mrr_at_top_k": 0,
        "expected_documents": [f"doc-{question_id}"],
        "expected_requests": [f"https://fyi.org.nz/request/{question_id}"],
        "hybrid_hit_at_top_k": vector_hit,
        "hybrid_mrr_at_top_k": vector_mrr,
        "vector_hit_at_top_k": vector_hit,
        "vector_mrr_at_top_k": vector_mrr,
    }


class EvalSearchReportTests(unittest.TestCase):
    def test_report_breaks_metrics_down_by_question_kind_and_answerability(self):
        report = eval_search.render_report(
            [
                result(
                    "q1",
                    answerable=True,
                    final_hit=True,
                    final_mrr=1.0,
                    kind="exact_term",
                    vector_hit=True,
                    vector_mrr=1.0,
                ),
                result(
                    "q2",
                    answerable=True,
                    final_hit=False,
                    final_mrr=0.0,
                    kind="semantic",
                    vector_hit=True,
                    vector_mrr=0.5,
                ),
                result(
                    "q3",
                    answerable=False,
                    final_hit=False,
                    final_mrr=0.0,
                    kind="no_answer",
                    vector_hit=False,
                    vector_mrr=0.0,
                ),
            ],
            args(),
        )

        self.assertIn("## Metrics By Question Type", report)
        self.assertIn(
            "| exact_term | 1 | 1.000 | 0.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.000 | 1.000 |",
            report,
        )
        self.assertIn(
            "| semantic | 1 | 1.000 | 0.000 | 1.000 | 0.000 | 0.500 | 0.000 | 0.500 | 0.000 |",
            report,
        )
        self.assertIn("## Metrics By Answerability", report)
        self.assertIn(
            "| answerable | 2 | 1.000 | 0.000 | 1.000 | 0.500 | 0.750 | 0.000 | 0.750 | 0.500 |",
            report,
        )
        self.assertIn(
            "| not_answerable | 1 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |",
            report,
        )

    def test_report_calls_out_reranker_stage_regressions(self):
        report = eval_search.render_report(
            [
                result(
                    "q1",
                    answerable=True,
                    final_hit=True,
                    final_mrr=1.0,
                    kind="exact_term",
                    vector_hit=True,
                    vector_mrr=1.0,
                ),
                result(
                    "q2",
                    answerable=True,
                    final_hit=False,
                    final_mrr=0.0,
                    kind="semantic",
                    vector_hit=True,
                    vector_mrr=0.5,
                ),
            ],
            args(),
        )

        self.assertIn("## Stage Regressions", report)
        self.assertIn("`q2` semantic question", report)

    def test_report_calls_out_corpus_coverage_gaps(self):
        report = eval_search.render_report(
            [
                result(
                    "q1",
                    answerable=True,
                    final_hit=True,
                    final_mrr=1.0,
                    kind="exact_term",
                    vector_hit=True,
                    vector_mrr=1.0,
                ),
                result(
                    "q2",
                    answerable=True,
                    corpus_document_rows=0,
                    final_hit=False,
                    final_mrr=0.0,
                    kind="production_failure",
                    vector_hit=False,
                    vector_mrr=0.0,
                ),
            ],
            args(),
        )

        self.assertIn("## Corpus Coverage Gaps", report)
        self.assertIn(
            "`q2` production_failure question Expected requests: https://fyi.org.nz/request/q2.",
            report,
        )

    def test_build_fts_match_query_matches_production_sanitization(self):
        query = eval_search_bm25.build_fts_match_query(
            'Council "leisure" OR NEAR(contracts) -x and information'
        )

        self.assertEqual(query, '"council" OR "leisure" OR "contracts"')

    def test_fuse_search_candidates_uses_weighted_reciprocal_rank(self):
        vector = [
            {"chunk_id": "chunk-a", "document_id": "doc-a", "score": 0.91},
            {"chunk_id": "chunk-b", "document_id": "doc-b", "score": 0.72},
        ]
        bm25 = [
            {"chunk_id": "chunk-b", "document_id": "doc-b", "bm25_score": -8.0},
            {"chunk_id": "chunk-c", "document_id": "doc-c", "bm25_score": -9.0},
        ]

        fused = eval_search_bm25.fuse_search_results(vector, bm25, limit=3)

        self.assertEqual([row["chunk_id"] for row in fused], ["chunk-b", "chunk-a", "chunk-c"])
        self.assertEqual(fused[0]["vector_rank"], 2)
        self.assertEqual(fused[0]["bm25_rank"], 1)
        self.assertGreater(fused[0]["fused_score"], fused[1]["fused_score"])

    def test_local_bm25_index_searches_fake_lancedb_rows(self):
        rows = [
            {
                "authority_name": "Auckland Council",
                "chunk_id": "chunk-a",
                "chunk_text": "The council disclosed leisure centre contract material.",
                "document_id": "doc-a",
                "original_filename": "release-a.pdf",
                "request_title": "Leisure centre contracts",
                "request_url": "https://fyi.org.nz/request/1",
                "source_url": "https://fyi.org.nz/request/1/response/1/attach/1/a.pdf",
                "text_preview": "The council disclosed leisure centre contract material.",
            },
            {
                "authority_name": "Other Agency",
                "chunk_id": "chunk-b",
                "chunk_text": "A short note about unrelated procurement.",
                "document_id": "doc-b",
                "original_filename": "release-b.pdf",
                "request_title": "Other release",
                "request_url": "https://fyi.org.nz/request/2",
                "source_url": "https://fyi.org.nz/request/2/response/1/attach/1/b.pdf",
                "text_preview": "A short note about unrelated procurement.",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "bm25.sqlite3"
            eval_search_bm25.build_bm25_index(FakeTable(rows), db_path, batch_size=10)
            index = eval_search_bm25.LocalBm25Index(db_path)
            try:
                matches = index.search("leisure centre contracts", top_k=5)
            finally:
                index.close()

        self.assertEqual(matches[0]["chunk_id"], "chunk-a")
        self.assertEqual(matches[0]["document_id"], "doc-a")
        self.assertEqual(matches[0]["bm25_rank"], 1)


class FakeTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def to_lance(self):
        return FakeLanceTable(self.rows)


class FakeLanceTable:
    def __init__(self, rows: list[dict]):
        self.rows = rows
        self.schema = SimpleNamespace(names=list(rows[0]))

    def scanner(self, columns: list[str], batch_size: int):
        return FakeScanner(self.rows, columns, batch_size)


class FakeScanner:
    def __init__(self, rows: list[dict], columns: list[str], batch_size: int):
        self.rows = rows
        self.columns = columns
        self.batch_size = batch_size

    def to_batches(self):
        for index in range(0, len(self.rows), self.batch_size):
            yield FakeBatch(self.rows[index : index + self.batch_size], self.columns)


class FakeBatch:
    def __init__(self, rows: list[dict], columns: list[str]):
        self.rows = rows
        self.columns = columns

    def to_pylist(self):
        return [{column: row.get(column) for column in self.columns} for row in self.rows]


if __name__ == "__main__":
    unittest.main()
