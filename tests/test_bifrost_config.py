import json
import unittest
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[1] / "bifrost" / "config.json"
MODEL_ALIASES = {"fast", "regular", "reasoning"}


class BifrostConfigTests(unittest.TestCase):
    def test_provider_model_lists_only_expose_public_aliases(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        for provider_name, provider_config in config["providers"].items():
            with self.subTest(provider=provider_name):
                key = provider_config["keys"][0]
                self.assertEqual(set(key["models"]), MODEL_ALIASES)
                self.assertEqual(set(key["aliases"]), MODEL_ALIASES)

    def test_virtual_key_allows_only_public_models(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        virtual_key = config["governance"]["virtual_keys"][0]
        for provider_config in virtual_key["provider_configs"]:
            self.assertEqual(set(provider_config["allowed_models"]), MODEL_ALIASES)

    def test_regular_route_targets_usable_high_context_providers(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        rules = {rule["id"]: rule for rule in config["governance"]["routing_rules"]}
        rule = rules["regular"]

        self.assertEqual(rule["cel_expression"], "provider == 'nvidia' && model == 'regular'")
        self.assertEqual(rule["scope"], "global")
        self.assertEqual(
            {(target["provider"], target["model"]) for target in rule["targets"]},
            {
                ("nvidia", "regular"),
                ("openrouter", "regular"),
            },
        )
        self.assertEqual(rule["fallbacks"], ["nvidia/regular", "openrouter/regular"])

    def test_routing_rules_use_supported_cel_and_fallback_shapes(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        for rule in config["governance"]["routing_rules"]:
            self.assertNotIn("request.model", rule["cel_expression"])
            self.assertEqual(rule["scope"], "global")
            for fallback in rule.get("fallbacks", []):
                self.assertIn("/", fallback)

    def test_public_routing_rules_match_public_models(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        rules = {rule["id"]: rule for rule in config["governance"]["routing_rules"]}

        self.assertEqual(set(rules), MODEL_ALIASES)
        for model in MODEL_ALIASES:
            rule = rules[model]
            self.assertEqual(rule["name"], model)
            self.assertEqual(
                rule["cel_expression"],
                f"provider == 'nvidia' && model == '{model}'",
            )
