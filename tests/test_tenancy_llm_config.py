import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ingest_tenancy.py"


def load_module():
    sys.path.insert(0, str(SCRIPT_PATH.parent))
    spec = importlib.util.spec_from_file_location("ingest_tenancy_config", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TenancyLlmConfigTests(unittest.TestCase):
    def test_defaults_target_minimax(self):
        module = load_module()

        args = module.build_parser(env={}, dotenv_path=Path("/missing/.env")).parse_args([])

        self.assertEqual(args.llm_base_url, "https://api.minimax.io/v1")
        self.assertEqual(args.llm_model, "MiniMax-M2.7-highspeed")
        self.assertEqual(args.llm_rpm, 12)
        self.assertEqual(args.llm_instructor_mode, "json_schema")

    def test_minimax_api_key_is_loaded_from_dotenv(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp_dir:
            dotenv = Path(tmp_dir) / ".env"
            dotenv.write_text("MINIMAX_API_KEY=from-dotenv\n", encoding="utf-8")

            args = module.build_parser(env={}, dotenv_path=dotenv).parse_args([])

        self.assertEqual(args.llm_api_key, "from-dotenv")

    def test_model_default_is_not_hidden_by_environment(self):
        module = load_module()

        args = module.build_parser(
            env={"TENANCY_LLM_MODEL": "hidden-model"},
            dotenv_path=Path("/missing/.env"),
        ).parse_args([])

        self.assertEqual(args.llm_model, "MiniMax-M2.7-highspeed")

    def test_openrouter_provider_and_response_format_flags_are_explicit(self):
        module = load_module()

        args = module.build_parser(env={}, dotenv_path=Path("/missing/.env")).parse_args(
            [
                "--llm-chat-response-format",
                "json_schema",
                "--llm-provider-ignore",
                "deepinfra",
                "--llm-provider-ignore",
                "somewhere-else",
            ]
        )

        self.assertEqual(args.llm_chat_response_format, "json_schema")
        self.assertEqual(args.llm_provider_ignore, ["deepinfra", "somewhere-else"])
        self.assertEqual(
            module.build_provider_extra_body(args.llm_provider_ignore),
            {"provider": {"ignore": ["deepinfra", "somewhere-else"]}},
        )


if __name__ == "__main__":
    unittest.main()
