import json
import unittest
from pathlib import Path


CONFIG_PATH = Path(__file__).resolve().parents[1] / "bifrost" / "config.json"


class BifrostConfigTests(unittest.TestCase):
    def test_regular_alias_routes_across_usable_tenancy_providers(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        rules = {
            rule["id"]: rule
            for rule in config["governance"]["routing_rules"]
        }
        rule = rules["tenancy-regular"]

        self.assertEqual(
            rule["cel_expression"],
            "provider == 'nvidia' && model == 'tenancy-regular'",
        )
        self.assertEqual(rule["scope"], "global")
        self.assertEqual(
            {(target["provider"], target["model"]) for target in rule["targets"]},
            {
                ("nvidia", "regular"),
                ("openrouter", "regular-openrouter"),
            },
        )
        self.assertEqual(
            rule["fallbacks"],
            ["nvidia/regular", "openrouter/regular-openrouter"],
        )

    def test_routing_rules_use_supported_cel_and_fallback_shapes(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

        for rule in config["governance"]["routing_rules"]:
            self.assertNotIn("request.model", rule["cel_expression"])
            self.assertEqual(rule["scope"], "global")
            for fallback in rule.get("fallbacks", []):
                self.assertIn("/", fallback)

    def test_tenancy_regular_alias_is_listed_on_configured_provider(self):
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        nvidia_key = config["providers"]["nvidia"]["keys"][0]

        self.assertIn("tenancy-regular", nvidia_key["models"])
        self.assertEqual(
            nvidia_key["aliases"]["tenancy-regular"],
            "nvidia/nemotron-3-super-120b-a12b",
        )
