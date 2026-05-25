import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ingest_tenancy.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("ingest_tenancy_instructor", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TenancyLlmInstructorTests(unittest.TestCase):
    def test_multi_document_instructor_requests_batch_schema(self):
        module = load_module()
        calls = {}

        class FakeCompletions:
            def create(self, **kwargs):
                calls.update(kwargs)
                return module.GeneratedEnrichmentBatch(items=[])

        client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

        module.request_generated_enrichment_for_documents(
            client,
            [{"document_id": "doc_1"}, {"document_id": "doc_2"}],
            "MiniMax-M2.7-highspeed",
            max_tokens=4096,
            api_mode="instructor",
        )

        self.assertEqual(calls["response_model"], module.GeneratedEnrichmentBatch)


if __name__ == "__main__":
    unittest.main()
