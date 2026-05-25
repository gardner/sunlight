import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "tenancy_llm.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("tenancy_llm_request_options", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TenancyLlmRequestOptionsTests(unittest.TestCase):
    def test_chat_json_schema_and_provider_ignore_are_forwarded(self):
        module = load_module()
        calls = {}

        class FakeCompletions:
            def create(self, **kwargs):
                calls.update(kwargs)
                message = SimpleNamespace(content='{"items":[{"document_id":"doc_1"}]}')
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

        module.request_generated_enrichment_for_documents(
            client,
            [{"document_id": "doc_1", "excerpt": "body"}],
            "deepseek/deepseek-v4-flash",
            max_tokens=4096,
            chat_options=module.ChatRequestOptions(
                response_format="json_schema",
                extra_body={"provider": {"ignore": ["deepinfra"]}},
            ),
        )

        self.assertEqual(calls["extra_body"], {"provider": {"ignore": ["deepinfra"]}})
        self.assertEqual(calls["response_format"]["type"], "json_schema")
        self.assertEqual(calls["response_format"]["json_schema"]["strict"], True)
        self.assertIn("items", calls["response_format"]["json_schema"]["schema"]["properties"])


if __name__ == "__main__":
    unittest.main()
