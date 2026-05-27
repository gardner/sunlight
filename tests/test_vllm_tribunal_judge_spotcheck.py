from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from vllm import tribunal_judge_spotcheck as module


MARKDOWN = """---
document_id: "doc_justice_tenancy_209594856"
---

TENANCY TRIBUNAL Remote Location

APPLICANT:

Inspire Property Management Limited As Agent For Anyos Gonczy

Landlord

RESPONDENT:

Symphony Minnie Leigh Nicol

Tenant

TENANCY ADDRESS:

Unit/Flat 7, 2 Totara Street, Marton, Marton 4710

## ORDER

1. Symphony Minnie Leigh Nicol must pay Inspire Property Management Limited As Agent For Anyos Gonczy $2,450.44 immediately.

## Reasons:

## [2024] NZTT 4744510

M Manhire 18 January 2024
"""


class SpotcheckPromptTests(unittest.TestCase):
    def test_number_markdown_lines_prefixes_each_line(self) -> None:
        numbered = module.number_markdown_lines("A\nB\n")

        self.assertEqual(numbered, "1: A\n2: B")

    def test_build_judge_prompt_includes_line_numbered_document_and_json(self) -> None:
        prompt = module.build_judge_prompt(
            markdown_text=MARKDOWN,
            extraction={
                "citation": "[2024] NZTT 4744510",
                "application_number": "4744510",
                "total_award_nzd": 2450.44,
            },
        )

        self.assertIn("Review the extraction against the tribunal document.", prompt)
        self.assertIn("1: TENANCY TRIBUNAL Remote Location", prompt)
        self.assertIn('"total_award_nzd": 2450.44', prompt)
        self.assertIn("Return only JSON that matches the schema.", prompt)

    def test_build_judge_schema_requires_auditable_issue_fields(self) -> None:
        schema = module.build_judge_schema()

        self.assertEqual(schema["type"], "object")
        self.assertEqual(
            schema["required"],
            ["overall_pass", "summary", "issues"],
        )
        issue_schema = schema["properties"]["issues"]["items"]
        self.assertIn("field", issue_schema["required"])
        self.assertIn("reason", issue_schema["required"])
        self.assertIn("evidence_lines", issue_schema["required"])
        self.assertEqual(
            issue_schema["properties"]["status"]["enum"],
            ["incorrect", "inconsistent", "missing_support", "unclear"],
        )


class SpotcheckLoadingTests(unittest.TestCase):
    def test_load_candidates_reads_schema_valid_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            run_dir = Path(tmp_dir)
            markdown_path = run_dir / "case.md"
            markdown_path.write_text(MARKDOWN, encoding="utf-8")
            entries = [
                {
                    "order_id": "209594856",
                    "markdown_path": str(markdown_path),
                    "prediction": {"citation": "[2024] NZTT 4744510"},
                    "schema_valid": True,
                    "schema_errors": [],
                },
                {
                    "order_id": "bad",
                    "markdown_path": str(markdown_path),
                    "prediction": {"citation": "[2024] NZTT 0000000"},
                    "schema_valid": False,
                    "schema_errors": ["type:total_award_nzd"],
                },
            ]
            (run_dir / "extractions.jsonl").write_text(
                "\n".join(json.dumps(entry) for entry in entries) + "\n",
                encoding="utf-8",
            )

            candidates = module.load_candidates(run_dir, require_schema_valid=True)

        self.assertEqual([candidate.order_id for candidate in candidates], ["209594856"])
        self.assertEqual(candidates[0].prediction["citation"], "[2024] NZTT 4744510")

    def test_sample_candidates_is_deterministic(self) -> None:
        candidates = [
            module.SpotcheckCandidate(
                order_id=str(index),
                markdown_path=f"{index}.md",
                prediction={"citation": f"[2024] NZTT {index}"},
                schema_valid=True,
                schema_errors=[],
            )
            for index in range(10)
        ]

        sampled = module.sample_candidates(candidates, sample_size=4, seed=19)

        self.assertEqual([candidate.order_id for candidate in sampled], ["0", "1", "4", "8"])


class SpotcheckPayloadTests(unittest.TestCase):
    def test_build_payload_uses_batch_messages_and_json_schema(self) -> None:
        cases = [
            module.JudgeCase(
                order_id="209594856",
                markdown_path="case.md",
                markdown_text="1: TENANCY TRIBUNAL Remote Location",
                prediction={"citation": "[2024] NZTT 4744510"},
            )
        ]

        payload = module.build_payload(
            model="judge-model",
            cases=cases,
            temperature=0.0,
            max_tokens=700,
        )

        self.assertEqual(payload["model"], "judge-model")
        self.assertEqual(payload["max_tokens"], 700)
        self.assertEqual(payload["temperature"], 0.0)
        self.assertEqual(payload["messages"][0][0]["role"], "user")
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(
            payload["response_format"]["json_schema"]["name"],
            "tribunal_spotcheck_judgment",
        )

    def test_parse_judgments_maps_batch_indices_back_to_cases(self) -> None:
        cases = [
            module.JudgeCase(
                order_id="209594856",
                markdown_path="case.md",
                markdown_text="1: TENANCY TRIBUNAL Remote Location",
                prediction={"citation": "[2024] NZTT 4744510"},
            )
        ]
        response = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "content": json.dumps(
                            {
                                "overall_pass": False,
                                "summary": "Amount mismatch.",
                                "issues": [
                                    {
                                        "field": "total_award_nzd",
                                        "status": "incorrect",
                                        "reason": "The amount in the order is different.",
                                        "expected_value_json": "2450.44",
                                        "evidence_lines": [17],
                                    }
                                ],
                            }
                        )
                    },
                }
            ]
        }

        judgments = module.parse_judgments(cases=cases, response_json=response)

        self.assertFalse(judgments["209594856"]["overall_pass"])
        self.assertEqual(judgments["209594856"]["issues"][0]["field"], "total_award_nzd")

    def test_summarize_judgments_counts_flagged_cases_and_issue_fields(self) -> None:
        cases = [
            module.JudgeCase(
                order_id="a",
                markdown_path="a.md",
                markdown_text="1: A",
                prediction={"citation": "A"},
            ),
            module.JudgeCase(
                order_id="b",
                markdown_path="b.md",
                markdown_text="1: B",
                prediction={"citation": "B"},
            ),
        ]
        judgments = {
            "a": {
                "overall_pass": True,
                "summary": "Looks good.",
                "issues": [],
            },
            "b": {
                "overall_pass": False,
                "summary": "One mismatch.",
                "issues": [
                    {
                        "field": "total_award_nzd",
                        "status": "incorrect",
                        "reason": "Wrong amount.",
                        "expected_value_json": "12.34",
                        "evidence_lines": [4],
                    }
                ],
            },
        }

        summary = module.summarize_judgments(cases=cases, judgments=judgments)

        self.assertEqual(summary["cases"], 2)
        self.assertEqual(summary["passed_cases"], 1)
        self.assertEqual(summary["flagged_cases"], 1)
        self.assertEqual(summary["issue_counts_by_field"], {"total_award_nzd": 1})


if __name__ == "__main__":
    unittest.main()
