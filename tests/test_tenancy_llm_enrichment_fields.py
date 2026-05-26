import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tenancy_llm.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("tenancy_llm_enrichment_fields", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TenancyLlmEnrichmentFieldsTests(unittest.TestCase):
    def test_apply_generated_enrichment_writes_story_fields_and_preserves_body(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "doc.md"
            markdown_path.write_text(
                '---\ndocument_id: "doc_justice_tenancy_1"\n'
                'source: "justice_tenancy"\nparser: "docling"\n'
                'pipeline_version: "tenancy-docling-v1"\n'
                'legal_issue_tags: ["rent_arrears"]\n---\n\nOriginal body.',
                encoding="utf-8",
            )

            module.apply_generated_enrichment(
                markdown_path,
                {
                    "case_summary": "The landlord obtained a rent arrears order.",
                    "catchwords": ["Rent arrears"],
                    "questions_answered": ["What did the Tribunal order?"],
                    "applicant_story": "The landlord says the tenant did not pay rent.",
                    "respondent_story": "The tenant says the rent ledger is wrong.",
                    "neutral_fact_pattern": "A landlord claimed rent arrears.",
                    "claims_made": ["The tenant owed rent arrears."],
                    "remedies_sought": ["Payment of rent arrears."],
                    "legal_principles": [
                        {
                            "principle": "Rent arrears can justify payment.",
                            "confidence": "medium",
                            "source_section": "reasons",
                        }
                    ],
                },
                model="nvidia/regular",
                now="2026-05-20T00:00:00Z",
            )

            metadata, body = module.parse_tenancy_markdown(
                markdown_path.read_text(encoding="utf-8")
            )

        self.assertEqual(body, "Original body.")
        self.assertEqual(metadata["legal_issue_tags"], ["rent_arrears"])
        self.assertEqual(metadata["case_summary"], "The landlord obtained a rent arrears order.")
        self.assertEqual(metadata["applicant_story"], "The landlord says the tenant did not pay rent.")
        self.assertEqual(metadata["respondent_story"], "The tenant says the rent ledger is wrong.")
        self.assertEqual(metadata["neutral_fact_pattern"], "A landlord claimed rent arrears.")
        self.assertEqual(metadata["claims_made"], ["The tenant owed rent arrears."])
        self.assertEqual(metadata["remedies_sought"], ["Payment of rent arrears."])
        self.assertEqual(metadata["llm_enrichment_model"], "nvidia/regular")
        self.assertEqual(metadata["llm_enrichment_version"], module.LLM_ENRICHMENT_VERSION)
        self.assertEqual(metadata["llm_enriched_at"], "2026-05-20T00:00:00Z")

    def test_apply_generated_enrichment_clears_stale_generated_fields(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "doc.md"
            markdown_path.write_text(
                '---\ndocument_id: "doc_justice_tenancy_1"\n'
                'source: "justice_tenancy"\nparser: "docling"\n'
                'pipeline_version: "tenancy-docling-v1"\n'
                'case_summary: "Old summary."\napplicant_story: "Old story."\n'
                'claims_made: ["Old claim."]\n---\n\nOriginal body.',
                encoding="utf-8",
            )

            module.apply_generated_enrichment(
                markdown_path,
                {
                    "case_summary": "New summary.",
                    "catchwords": [],
                    "applicant_story": "",
                    "claims_made": [],
                },
                model="test-model",
                now="2026-05-20T00:00:00Z",
            )

            metadata, body = module.parse_tenancy_markdown(
                markdown_path.read_text(encoding="utf-8")
            )

        self.assertEqual(body, "Original body.")
        self.assertEqual(metadata["case_summary"], "New summary.")
        self.assertNotIn("applicant_story", metadata)
        self.assertNotIn("claims_made", metadata)


if __name__ == "__main__":
    unittest.main()
