import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scan_pii_privacy_filter.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("scan_pii_privacy_filter", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["scan_pii_privacy_filter"] = module
    spec.loader.exec_module(module)
    return module


class FakePrivacyFilter:
    def __call__(self, text):
        predictions = []
        for value, label, score in (
            (" Jane", "private_person", 0.99),
            (" Smith", "private_person", 0.98),
            (" jane@example", "private_email", 0.97),
            (".com", "private_email", 0.96),
            (" 10 Main", "private_address", 0.95),
            (" Street", "private_address", 0.94),
        ):
            index = text.find(value)
            if index >= 0:
                predictions.append(
                    {
                        "entity_group": label,
                        "score": score,
                        "word": value,
                        "start": index,
                        "end": index + len(value),
                    }
                )
        return predictions


class ScanPiiPrivacyFilterTests(unittest.TestCase):
    def test_prediction_to_entity_trims_whitespace_offsets(self):
        module = load_module()
        text = "Hello Jane"

        entity = module.prediction_to_entity(
            {
                "entity_group": "private_person",
                "score": 0.9,
                "start": 5,
                "end": 10,
            },
            text,
        )

        self.assertEqual(entity.start, 6)
        self.assertEqual(entity.end, 10)
        self.assertEqual(entity.text, "Jane")

    def test_scan_text_merges_adjacent_same_label_spans(self):
        module = load_module()
        text = "Tenant Jane Smith emailed jane@example.com from 10 Main Street."

        entities = module.scan_text(FakePrivacyFilter(), text, labels=module.DEFAULT_LABELS)

        by_label = {entity.label: entity for entity in entities}
        self.assertEqual(by_label["private_person"].text, "Jane Smith")
        self.assertEqual(by_label["private_email"].text, "jane@example.com")
        self.assertEqual(by_label["private_address"].text, "10 Main Street")
        self.assertEqual(by_label["private_person"].score, 0.98)

    def test_parse_labels_accepts_comma_separated_and_repeated_values(self):
        module = load_module()

        labels = module.parse_labels(["private_person, private_email", "private_person"])

        self.assertEqual(labels, ["private_person", "private_email"])

    def test_redact_text_prefers_longer_overlapping_span(self):
        module = load_module()
        text = "Tenant Jane Smith lives here."

        redacted = module.redact_text(
            text,
            [
                module.PrivacyEntity(7, 11, "Jane", "private_person", 0.99),
                module.PrivacyEntity(7, 17, "Jane Smith", "private_person", 0.9),
            ],
        )

        self.assertEqual(redacted, "Tenant [PRIVATE_PERSON] lives here.")

    def test_scan_markdown_path_scans_body_by_default(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "doc.md"
            path.write_text(
                "\n".join(
                    [
                        "---",
                        'document_id: "doc_1"',
                        'source: "justice_tenancy"',
                        'source_url: "https://example.test/doc.pdf"',
                        "---",
                        "",
                        "Tenant Jane Smith emailed jane@example.com from 10 Main Street.",
                    ]
                ),
                encoding="utf-8",
            )

            record = module.scan_markdown_path(
                FakePrivacyFilter(),
                path,
                labels=module.DEFAULT_LABELS,
            )

        self.assertEqual(record["document_id"], "doc_1")
        self.assertEqual(record["scan_scope"], "body")
        self.assertEqual(record["entity_count"], 3)

    def test_main_writes_jsonl_and_summary_without_loading_real_model(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_dir = Path(tmp_dir) / "markdown"
            markdown_dir.mkdir()
            (markdown_dir / "doc.md").write_text(
                "---\n"
                'document_id: "doc_1"\n'
                'source: "justice_tenancy"\n'
                "---\n\n"
                "Tenant Jane Smith emailed jane@example.com.\n",
                encoding="utf-8",
            )
            output_jsonl = Path(tmp_dir) / "privacy.jsonl"
            summary_json = Path(tmp_dir) / "summary.json"

            with patch.object(module, "load_classifier", return_value=FakePrivacyFilter()):
                exit_code = module.main(
                    [
                        "--markdown-dir",
                        str(markdown_dir),
                        "--output-jsonl",
                        str(output_jsonl),
                        "--summary-json",
                        str(summary_json),
                    ]
                )

            records = [json.loads(line) for line in output_jsonl.read_text().splitlines()]
            summary = json.loads(summary_json.read_text())

        self.assertEqual(exit_code, 0)
        self.assertEqual(records[0]["entity_count"], 2)
        self.assertEqual(summary["documents_scanned"], 1)
        self.assertEqual(summary["label_counts"], {"private_email": 1, "private_person": 1})


if __name__ == "__main__":
    unittest.main()
