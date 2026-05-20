import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tenancy_corpus.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("tenancy_corpus", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class TenancyCorpusTests(unittest.TestCase):
    def sample_sidecar(self, **overrides):
        sidecar = {
            "source": "Tenancy",
            "category": "Tenancy Tribunal 2021",
            "source_url": "https://forms.justice.govt.nz/search/TT/abstract.html?id=6718197_172069933&applicationNumber=4294057",
            "pdf_url": "https://forms.justice.govt.nz/search/Documents/TTV2/PDF/6718197-Tribunal_Order_Redacted.pdf",
            "filename": "172069933.pdf",
            "case_name": "NONE v NONE",
            "court": "Tenancy Tribunal",
            "application_number": "4294057",
            "order_id": "172069933",
            "date_of_issue": "20/05/2021",
            "published_date": "20/05/21",
            "address": "11A Kings Drive, Wanaka, Wanaka 9305",
            "suburb": "Wanaka",
            "city": "Wanaka",
            "parties": ["NONE", "NONE", "NONE"],
            "mbie_order": True,
            "downloaded_at": "2026-05-19T05:46:38.128205+00:00",
        }
        sidecar.update(overrides)
        return sidecar

    def test_build_metadata_normalizes_tenancy_sidecar(self):
        module = load_module()

        metadata = module.build_tenancy_metadata(
            self.sample_sidecar(),
            Path("/repo/justice/data/tenancy/pdfs/172069933.json"),
        )

        self.assertEqual(metadata["document_id"], "doc_justice_tenancy_172069933")
        self.assertEqual(metadata["source"], "justice_tenancy")
        self.assertEqual(metadata["source_type"], "tribunal_decision")
        self.assertEqual(metadata["authority_name"], "Tenancy Tribunal")
        self.assertEqual(metadata["authority_slug"], "tenancy-tribunal")
        self.assertEqual(metadata["authority_category"], "Tribunal")
        self.assertEqual(metadata["parser"], "docling")
        self.assertEqual(metadata["pipeline_version"], module.PIPELINE_VERSION)
        self.assertEqual(metadata["request_title"], "Tenancy Tribunal order 4294057 - 2021-05-20")
        self.assertEqual(metadata["request_year"], 2021)
        self.assertEqual(metadata["source_page_url"], self.sample_sidecar()["source_url"])
        self.assertEqual(metadata["source_url"], self.sample_sidecar()["pdf_url"])
        self.assertEqual(metadata["decision_date"], "2021-05-20")
        self.assertEqual(metadata["published_date"], "2021-05-20")
        self.assertEqual(metadata["tenancy_application_number"], "4294057")
        self.assertEqual(metadata["tenancy_order_id"], "172069933")
        self.assertEqual(
            metadata["pdf_r2_key"],
            "canonical/justice/tenancy/v1/pdf/2021/172069933.pdf",
        )
        self.assertEqual(
            metadata["markdown_r2_key"],
            "markdown/justice/tenancy/v1/2021/doc_justice_tenancy_172069933.md",
        )

    def test_build_metadata_uses_case_name_when_public(self):
        module = load_module()

        metadata = module.build_tenancy_metadata(
            self.sample_sidecar(
                case_name="Bray Property Management v Bain, Michael John",
                application_number="4387201",
                order_id="198781519",
                filename="198781519.pdf",
                date_of_issue="20/05/2023",
                published_date="20/05/23",
            ),
            Path("/repo/justice/data/tenancy/pdfs/198781519.json"),
        )

        self.assertEqual(
            metadata["request_title"],
            "Bray Property Management v Bain, Michael John - Tenancy Tribunal order 4387201 - 2023-05-20",
        )
        self.assertEqual(metadata["request_year"], 2023)

    def test_discover_tenancy_documents_skips_duplicate_pdf_urls(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_dir = Path(tmp_dir)
            first = self.sample_sidecar(order_id="100", filename="100.pdf")
            duplicate = self.sample_sidecar(order_id="101", filename="101.pdf")
            unique = self.sample_sidecar(
                order_id="102",
                filename="102.pdf",
                pdf_url="https://forms.justice.govt.nz/search/Documents/TTV2/PDF/unique.pdf",
            )
            for sidecar in (first, duplicate, unique):
                (pdf_dir / sidecar["filename"]).write_bytes(b"%PDF-1.4")
                (pdf_dir / f"{sidecar['order_id']}.json").write_text(
                    json.dumps(sidecar), encoding="utf-8"
                )

            documents = module.discover_tenancy_documents(pdf_dir)

        self.assertEqual([doc.metadata["tenancy_order_id"] for doc in documents], ["100", "102"])

    def test_needs_docling_conversion_rejects_markitdown_or_old_pipeline_output(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            markdown_path = Path(tmp_dir) / "doc.md"

            self.assertTrue(
                module.needs_docling_conversion(
                    markdown_path, "doc_justice_tenancy_1"
                )
            )

            markdown_path.write_text(
                '---\ndocument_id: "doc_justice_tenancy_1"\nparser: "markitdown"\n---\n\nbody',
                encoding="utf-8",
            )
            self.assertTrue(
                module.needs_docling_conversion(
                    markdown_path, "doc_justice_tenancy_1"
                )
            )

            markdown_path.write_text(
                '---\ndocument_id: "doc_justice_tenancy_1"\nparser: "docling"\npipeline_version: "old"\n---\n\nbody',
                encoding="utf-8",
            )
            self.assertTrue(
                module.needs_docling_conversion(
                    markdown_path, "doc_justice_tenancy_1"
                )
            )

            markdown_path.write_text(
                f'---\ndocument_id: "doc_justice_tenancy_1"\nparser: "docling"\npipeline_version: "{module.PIPELINE_VERSION}"\n---\n\nbody',
                encoding="utf-8",
            )
            self.assertFalse(
                module.needs_docling_conversion(
                    markdown_path, "doc_justice_tenancy_1"
                )
            )

    def test_deterministic_enrichment_extracts_tribunal_retrieval_metadata(self):
        module = load_module()
        body = """
[2026] NZTT 5380224

TENANCY TRIBUNAL AT AUCKLAND

The tenant must pay the landlord $1,263.50 for rent arrears.
The bond is to be paid to the landlord.
This order is made under section 55(1)(a) and s 78A of the Residential Tenancies Act 1986.

No suppression orders apply.

Rehearings
You may apply for a rehearing.
"""

        enrichment = module.deterministic_enrichment(body)

        self.assertEqual(enrichment["nztt_citation"], "[2026] NZTT 5380224")
        self.assertEqual(enrichment["tribunal_location"], "Auckland")
        self.assertIn("rent_arrears", enrichment["legal_issue_tags"])
        self.assertIn("bond_distribution", enrichment["legal_issue_tags"])
        self.assertEqual(enrichment["statute_sections"], ["55(1)(a)", "78A"])
        self.assertEqual(enrichment["ordered_amounts"][0]["amount"], 1263.50)
        self.assertEqual(enrichment["suppression_status"], "none")
        self.assertFalse(enrichment["suppression_order"])
        self.assertTrue(enrichment["contains_standard_boilerplate"])

    def test_deterministic_enrichment_marks_suppressed_decisions_for_review(self):
        module = load_module()
        body = """
[2025] NZTT 5000000

The Tribunal orders suppression of the tenant names and tenancy address.
Those details must not be published.
"""

        enrichment = module.deterministic_enrichment(body)

        self.assertEqual(enrichment["suppression_status"], "suppressed")
        self.assertTrue(enrichment["suppression_order"])
        self.assertIn("tenant_names", enrichment["suppressed_fields"])
        self.assertIn("tenancy_address", enrichment["suppressed_fields"])
        self.assertEqual(enrichment["privacy_sensitivity"], "high")
        self.assertTrue(enrichment["requires_redaction_check"])

    def test_build_retrieval_documents_adds_generated_metadata_views(self):
        module = load_module()
        metadata = {
            "document_id": "doc_justice_tenancy_172069933",
            "source": "justice_tenancy",
            "case_summary": "The landlord received a conditional termination order.",
            "catchwords": ["Rent arrears", "Conditional termination"],
            "questions_answered": [
                "When will the tenancy terminate if arrears are not paid?"
            ],
            "legal_principles": [
                {
                    "principle": "Rent arrears may support a conditional termination order.",
                    "confidence": "medium",
                    "source_section": "reasons",
                }
            ],
        }

        documents = module.build_retrieval_documents(metadata, "Original tribunal reasons.")

        views = {doc.metadata["retrieval_view"]: doc for doc in documents}
        self.assertEqual(views["source_text"].text, "Original tribunal reasons.")
        self.assertFalse(views["source_text"].metadata["generated"])
        self.assertEqual(views["case_summary"].metadata["canonical_document_id"], metadata["document_id"])
        self.assertTrue(views["case_summary"].metadata["generated"])
        self.assertIn("tenancy terminate", views["questions_answered"].text)
        self.assertIn("Rent arrears", views["catchwords"].text)
        self.assertIn("Rent arrears may support", views["legal_principles"].text)


if __name__ == "__main__":
    unittest.main()
