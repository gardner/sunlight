import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "compare_markdown_converters.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("compare_markdown_converters", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class CompareMarkdownConvertersTests(unittest.TestCase):
    def test_markdown_metrics_capture_retrieval_relevant_structure(self):
        module = load_module()
        markdown = """
# Title

[2020] NZTT Wellington 4243413

| Description | Amount |
| --- | --- |
| Rent arrears | $1,234.50 |

A Henwood 17 August 2020

Please read carefully:
"""

        metrics = module.markdown_metrics(markdown)

        self.assertEqual(metrics["chars"], len(markdown))
        self.assertEqual(metrics["headings"], 1)
        self.assertEqual(metrics["tables"], 1)
        self.assertEqual(metrics["nztt_citations"], ["[2020] NZTT Wellington 4243413"])
        self.assertEqual(metrics["decision_dates"], ["2020-08-17"])
        self.assertEqual(metrics["money_amounts"], 1)
        self.assertTrue(metrics["has_boilerplate"])

    def test_compare_metrics_reports_ratio_and_missing_values(self):
        module = load_module()

        comparison = module.compare_metrics(
            {
                "chars": 100,
                "tables": 2,
                "headings": 3,
                "money_amounts": 4,
                "nztt_citations": ["[2020] NZTT Wellington 4243413"],
                "decision_dates": ["2020-08-17"],
            },
            {
                "chars": 50,
                "tables": 1,
                "headings": 0,
                "money_amounts": 2,
                "nztt_citations": [],
                "decision_dates": ["2020-08-17"],
            },
        )

        self.assertEqual(comparison["cloudflare_to_docling_char_ratio"], 0.5)
        self.assertEqual(comparison["table_delta"], -1)
        self.assertEqual(comparison["heading_delta"], -3)
        self.assertEqual(
            comparison["missing_cloudflare_citations"],
            ["[2020] NZTT Wellington 4243413"],
        )
        self.assertEqual(comparison["missing_cloudflare_dates"], [])

    def test_load_dotenv_file_does_not_override_existing_env(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            dotenv = Path(tmp_dir) / ".env"
            dotenv.write_text("A=from-file\nB=two\n", encoding="utf-8")
            env = {"A": "existing"}

            module.load_dotenv_file(dotenv, env)

        self.assertEqual(env, {"A": "existing", "B": "two"})

    def test_markdown_from_cloudflare_payload_accepts_worker_binding_result(self):
        module = load_module()

        markdown = module.markdown_from_cloudflare_payload(
            [{"format": "markdown", "data": "# Converted"}]
        )

        self.assertEqual(markdown, "# Converted")


if __name__ == "__main__":
    unittest.main()
