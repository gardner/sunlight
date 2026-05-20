import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "export_bm25_to_d1.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("export_bm25_to_d1", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ExportBm25ToD1Tests(unittest.TestCase):
    def test_build_row_uses_non_fyi_frontmatter_metadata(self):
        module = load_module()
        metadata = {
            "authority_category": "Tribunal",
            "authority_name": "Tenancy Tribunal",
            "authority_slug": "tenancy-tribunal",
            "document_id": "doc_justice_tenancy_172069933",
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
        }

        row = module.build_row(metadata, {}, 0, "  Tribunal   order body.  ", 100)

        self.assertEqual(row["authority_category"], "Tribunal")
        self.assertEqual(row["authority_name"], "Tenancy Tribunal")
        self.assertEqual(row["authority_slug"], "tenancy-tribunal")
        self.assertEqual(row["request_title"], "Tenancy Tribunal order 4294057 - 20/05/2021")
        self.assertEqual(row["request_year"], 2021)
        self.assertEqual(row["retrieval_view"], "case_summary")
        self.assertEqual(row["source_type"], "tribunal_decision")
        self.assertEqual(row["source"], "justice_tenancy")
        self.assertEqual(row["source_page_url"], metadata["source_page_url"])
        self.assertEqual(row["tenancy_order_id"], "172069933")
        self.assertEqual(row["tenancy_application_number"], "4294057")
        self.assertEqual(row["nztt_citation"], "[2021] NZTT 4294057")
        self.assertEqual(row["decision_date"], "2021-05-20")
        self.assertEqual(row["text_preview"], "Tribunal order body.")

    def test_build_row_prefers_fyi_request_index_when_available(self):
        module = load_module()
        metadata = {
            "document_id": "doc_fyi_1_2_3_abcd",
            "fyi_request_id": 1,
            "source": "fyi",
        }
        request_metadata = {
            "authority_name": "Auckland Council",
            "request_title": "Council contracts",
            "request_year": 2024,
        }

        row = module.build_row(metadata, request_metadata, 0, "body", 100)

        self.assertEqual(row["authority_name"], "Auckland Council")
        self.assertEqual(row["request_title"], "Council contracts")
        self.assertEqual(row["request_year"], 2024)


if __name__ == "__main__":
    unittest.main()
