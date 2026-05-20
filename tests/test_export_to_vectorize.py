import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_to_vectorize.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("export_to_vectorize", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportToVectorizeTests(unittest.TestCase):
    def test_clean_metadata_preserves_non_fyi_source_metadata(self):
        module = load_module()
        row = {
            "authority_category": "Tribunal",
            "authority_name": "Tenancy Tribunal",
            "authority_slug": "tenancy-tribunal",
            "chunk_id": "chunk_doc_justice_tenancy_172069933_0000_abcd",
            "chunk_index": 0,
            "canonical_document_id": "doc_justice_tenancy_172069933",
            "document_id": "doc_justice_tenancy_172069933",
            "generated": True,
            "original_filename": "172069933.pdf",
            "request_title": "Tenancy Tribunal order 4294057 - 20/05/2021",
            "request_year": 2021,
            "retrieval_view": "case_summary",
            "source_type": "tribunal_decision",
            "source": "justice_tenancy",
            "source_url": "https://forms.justice.govt.nz/search/Documents/TTV2/PDF/6718197-Tribunal_Order_Redacted.pdf",
            "source_page_url": "https://forms.justice.govt.nz/search/TT/abstract.html?id=6718197_172069933",
            "tenancy_order_id": "172069933",
            "tenancy_application_number": "4294057",
            "nztt_citation": "[2021] NZTT 4294057",
            "decision_date": "2021-05-20",
            "legal_issue_tags": '["rent_arrears"]',
            "statute_sections": '["55(1)(a)"]',
            "suppression_status": "none",
            "text_preview": "Tribunal order body.",
        }

        metadata = module.clean_metadata(row, {})

        self.assertEqual(metadata["authority_category"], "Tribunal")
        self.assertEqual(metadata["authority_name"], "Tenancy Tribunal")
        self.assertEqual(metadata["authority_slug"], "tenancy-tribunal")
        self.assertEqual(metadata["request_title"], "Tenancy Tribunal order 4294057 - 20/05/2021")
        self.assertEqual(metadata["request_year"], 2021)
        self.assertEqual(metadata["retrieval_view"], "case_summary")
        self.assertEqual(metadata["source_type"], "tribunal_decision")
        self.assertEqual(metadata["source"], "justice_tenancy")
        self.assertEqual(metadata["source_page_url"], row["source_page_url"])
        self.assertEqual(metadata["tenancy_order_id"], "172069933")
        self.assertEqual(metadata["tenancy_application_number"], "4294057")
        self.assertEqual(metadata["nztt_citation"], "[2021] NZTT 4294057")
        self.assertEqual(metadata["decision_date"], "2021-05-20")
        self.assertEqual(metadata["generated"], True)
        self.assertEqual(metadata["canonical_document_id"], "doc_justice_tenancy_172069933")


if __name__ == "__main__":
    unittest.main()
