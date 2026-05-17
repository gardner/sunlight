import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import eval_search  # noqa: E402


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
    final_hit: bool,
    final_mrr: float,
    kind: str,
    vector_hit: bool,
    vector_mrr: float,
) -> dict:
    return {
        "answerable": answerable,
        "corpus_document_rows": 1,
        "final_hit": final_hit,
        "final_mrr": final_mrr,
        "id": question_id,
        "kind": kind,
        "question": f"{kind} question",
        "rerank_hit_at_final_k": final_hit,
        "rerank_mrr_at_final_k": final_mrr,
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
        self.assertIn("| exact_term | 1 | 1.000 | 1.000 | 1.000 | 1.000 |", report)
        self.assertIn("| semantic | 1 | 1.000 | 0.000 | 0.500 | 0.000 |", report)
        self.assertIn("## Metrics By Answerability", report)
        self.assertIn("| answerable | 2 | 1.000 | 0.500 | 0.750 | 0.500 |", report)
        self.assertIn("| not_answerable | 1 | 0.000 | 0.000 | 0.000 | 0.000 |", report)

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


if __name__ == "__main__":
    unittest.main()
