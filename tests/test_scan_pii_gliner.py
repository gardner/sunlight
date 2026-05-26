import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "scan_pii_gliner.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("scan_pii_gliner", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["scan_pii_gliner"] = module
    spec.loader.exec_module(module)
    return module


class FakeGlinerModel:
    def predict_entities(self, text, labels, threshold):
        predictions = []
        if "email" in labels:
            email = "jane@example.com"
            index = text.find(email)
            if index >= 0:
                predictions.append(
                    {
                        "start": index,
                        "end": index + len(email),
                        "text": email,
                        "label": "email",
                        "score": threshold + 0.1,
                    }
                )
        if "person" in labels:
            name = "Jane Smith"
            index = text.find(name)
            if index >= 0:
                predictions.append(
                    {
                        "start": index,
                        "end": index + len(name),
                        "text": name,
                        "label": "person",
                        "score": 0.9,
                    }
                )
        return predictions


class ScanPiiGlinerTests(unittest.TestCase):
    def test_chunk_text_preserves_offsets_with_overlap(self):
        module = load_module()

        chunks = module.chunk_text("abcdefghijklmnopqrst", chunk_chars=8, chunk_overlap=3)

        self.assertEqual(
            [(chunk.start, chunk.end, chunk.text) for chunk in chunks],
            [(0, 8, "abcdefgh"), (5, 13, "fghijklm"), (10, 18, "klmnopqr"), (15, 20, "pqrst")],
        )

    def test_parse_labels_accepts_comma_separated_and_repeated_values(self):
        module = load_module()

        labels = module.parse_labels(["email, phone_number", "email", "person"])

        self.assertEqual(labels, ["email", "phone_number", "person"])

    def test_chunk_text_honors_gliner_token_budget(self):
        module = load_module()

        chunks = module.chunk_text(
            "one, two, three, four",
            chunk_chars=100,
            chunk_overlap=0,
            chunk_tokens=4,
        )

        self.assertEqual([chunk.text for chunk in chunks], ["one, two,", " three, four"])

    def test_scan_text_converts_chunk_offsets_to_document_offsets(self):
        module = load_module()
        text = "Intro text before Jane Smith can be contacted at jane@example.com."

        entities = module.scan_text(
            FakeGlinerModel(),
            text,
            labels=["email", "person"],
            threshold=0.5,
            chunk_chars=80,
            chunk_overlap=10,
        )

        by_label = {entity.label: entity for entity in entities}
        self.assertEqual(by_label["person"].start, text.index("Jane Smith"))
        self.assertEqual(by_label["email"].start, text.index("jane@example.com"))

    def test_merge_entities_keeps_highest_score_for_duplicate_span(self):
        module = load_module()

        entities = module.merge_entities(
            [
                module.PiiEntity(5, 9, "Jane", "person", 0.6),
                module.PiiEntity(5, 9, "Jane", "person", 0.8),
            ]
        )

        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0].score, 0.8)

    def test_redact_text_prefers_longer_overlapping_span(self):
        module = load_module()
        text = "Tenant Jane Smith lives here."

        redacted = module.redact_text(
            text,
            [
                module.PiiEntity(7, 11, "Jane", "person", 0.99),
                module.PiiEntity(7, 17, "Jane Smith", "person", 0.9),
            ],
        )

        self.assertEqual(redacted, "Tenant [PERSON] lives here.")

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
                        "The tenant Jane Smith used jane@example.com.",
                    ]
                ),
                encoding="utf-8",
            )

            record = module.scan_markdown_path(
                FakeGlinerModel(),
                path,
                labels=["email", "person"],
                threshold=0.5,
                chunk_chars=100,
                chunk_overlap=10,
            )

        self.assertEqual(record["document_id"], "doc_1")
        self.assertEqual(record["scan_scope"], "body")
        self.assertEqual(record["entity_count"], 2)
        starts = {entity["label"]: entity["start"] for entity in record["entities"]}
        self.assertEqual(starts["person"], "The tenant Jane Smith".index("Jane Smith"))

    def test_main_writes_jsonl_and_summary_without_loading_real_model(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_dir = Path(tmp_dir) / "markdown"
            markdown_dir.mkdir()
            markdown_path = markdown_dir / "doc.md"
            markdown_path.write_text(
                "---\n"
                'document_id: "doc_1"\n'
                'source: "justice_tenancy"\n'
                "---\n\n"
                "Email jane@example.com.\n",
                encoding="utf-8",
            )
            output_jsonl = Path(tmp_dir) / "pii.jsonl"
            summary_json = Path(tmp_dir) / "summary.json"

            with patch.object(module, "load_gliner_model", return_value=FakeGlinerModel()):
                exit_code = module.main(
                    [
                        "--markdown-dir",
                        str(markdown_dir),
                        "--output-jsonl",
                        str(output_jsonl),
                        "--summary-json",
                        str(summary_json),
                        "--labels",
                        "email",
                    ]
                )

            records = [json.loads(line) for line in output_jsonl.read_text().splitlines()]
            summary = json.loads(summary_json.read_text())

        self.assertEqual(exit_code, 0)
        self.assertEqual(records[0]["entity_count"], 1)
        self.assertEqual(summary["documents_scanned"], 1)
        self.assertEqual(summary["label_counts"], {"email": 1})


if __name__ == "__main__":
    unittest.main()
