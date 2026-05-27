from __future__ import annotations

import json
import unittest

from vllm import tribunal_batch_eval as module


UNSUPPRESSED_MARKDOWN = """---
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

1. Symphony Minnie Leigh Nicol must pay Inspire Property Management Limited As Agent For Anyos Gonczy $2,450.44 immediately, being rent arrears to 16 January 2024.

| Description                         | Landlord   | Tenant   |
|-------------------------------------|------------|----------|
| Rent arrears                        | $2,430.00  |          |
| Filing fee reimbursement            | $20.44     |          |
| Total award                         | $2,450.44  |          |
| Total payable by Tenant to Landlord | $2,450.44  |          |

## Reasons:

## [2024] NZTT 4744510

M Manhire 18 January 2024
"""


REDACTED_MARKDOWN = """---
document_id: "doc_justice_tenancy_240127915"
---

## [2025] NZTT 5335322

## TENANCY TRIBUNAL AT [Event location suppressed]

APPLICANT:

[The applicant/s]

Landlord

RESPONDENT:

Sarah Mummery

Tenant

TENANCY ADDRESS:

65 Saffron Street, Birkdale, Auckland 0626

## ORDER

1. An application for suppression has been made in this case, and the Tribunal orders suppression of the Landlord's name.
2. Sarah Mummery must pay [The landlord/s] $0.00 immediately, as calculated in the table below:

| Description              | Landlord   | Tenant   |
|--------------------------|------------|----------|
| Rent arrears to 14/10/25 | $841.43    |          |
| Water rates to 12/09/25  | $124.22    |          |
| Filing fee reimbursement | $28.00     |          |
| Total award              | $993.65    |          |

## Reasons:

N Small 15 October 2025
"""


TEACHER_MARKDOWN = """---
document_id: "doc_justice_tenancy_240225060"
llm_enrichment_model: "MiniMax-M2.7-highspeed"
case_summary: "The Tribunal distributed the bond and dismissed exemplary damages."
catchwords: ["bond distribution", "exemplary damages"]
questions_answered: ["How should the bond be distributed?", "Should exemplary damages be awarded?"]
applicant_story: "The tenant sought return of the bond and exemplary damages."
respondent_story: "The landlord agreed to the bond distribution at the hearing."
neutral_fact_pattern: "The parties disputed the bond distribution after the tenancy ended."
claims_made: ["Tenant claimed return of the bond", "Tenant sought exemplary damages"]
remedies_sought: ["Return of the bond", "Exemplary damages"]
legal_principles: [{"principle": "Exemplary damages require unlawful conduct.", "confidence": "medium", "source_section": "reasons"}]
---

TENANCY TRIBUNAL Remote Location
"""


class StripFrontMatterTests(unittest.TestCase):
    def test_strip_front_matter_returns_body(self) -> None:
        stripped = module.strip_front_matter(UNSUPPRESSED_MARKDOWN)

        self.assertNotIn('document_id: "doc_justice_tenancy_209594856"', stripped)
        self.assertIn("TENANCY TRIBUNAL Remote Location", stripped)


class GoldExtractionTests(unittest.TestCase):
    def test_extract_gold_case_data_for_unsuppressed_case(self) -> None:
        sidecar = {
            "application_number": "4744510",
            "date_of_issue": "18/01/2024",
        }

        gold = module.extract_gold_case_data(
            markdown_text=UNSUPPRESSED_MARKDOWN,
            sidecar=sidecar,
        )

        self.assertEqual(gold["citation"], "[2024] NZTT 4744510")
        self.assertEqual(gold["application_number"], "4744510")
        self.assertEqual(gold["decision_date"], "2024-01-18")
        self.assertEqual(gold["tribunal_location"], "Remote Location")
        self.assertEqual(gold["adjudicator"], "M Manhire")
        self.assertEqual(
            gold["applicant_name"],
            "Inspire Property Management Limited As Agent For Anyos Gonczy",
        )
        self.assertEqual(gold["applicant_role"], "landlord")
        self.assertEqual(gold["respondent_name"], "Symphony Minnie Leigh Nicol")
        self.assertEqual(gold["respondent_role"], "tenant")
        self.assertEqual(
            gold["tenancy_address"],
            "Unit/Flat 7, 2 Totara Street, Marton, Marton 4710",
        )
        self.assertFalse(gold["has_name_redactions"])
        self.assertFalse(gold["has_address_redactions"])
        self.assertEqual(gold["total_award_nzd"], 2450.44)
        self.assertEqual(gold["payable_by"], "tenant")
        self.assertEqual(gold["payable_to"], "landlord")

    def test_extract_gold_case_data_for_redacted_case(self) -> None:
        sidecar = {
            "application_number": "5335322",
            "date_of_issue": "15/10/2025",
        }

        gold = module.extract_gold_case_data(
            markdown_text=REDACTED_MARKDOWN,
            sidecar=sidecar,
        )

        self.assertEqual(gold["citation"], "[2025] NZTT 5335322")
        self.assertEqual(gold["decision_date"], "2025-10-15")
        self.assertEqual(gold["tribunal_location"], "[Event location suppressed]")
        self.assertEqual(gold["adjudicator"], "N Small")
        self.assertEqual(gold["applicant_name"], "[The applicant/s]")
        self.assertTrue(gold["has_name_redactions"])
        self.assertFalse(gold["has_address_redactions"])
        self.assertEqual(gold["total_award_nzd"], 993.65)

    def test_extract_teacher_case_data_reads_generated_frontmatter_fields(self) -> None:
        teacher = module.extract_teacher_case_data(TEACHER_MARKDOWN)

        self.assertEqual(
            teacher["case_summary"],
            "The Tribunal distributed the bond and dismissed exemplary damages.",
        )
        self.assertEqual(teacher["catchwords"], ["bond distribution", "exemplary damages"])
        self.assertEqual(
            teacher["questions_answered"],
            [
                "How should the bond be distributed?",
                "Should exemplary damages be awarded?",
            ],
        )
        self.assertEqual(
            teacher["legal_principles"],
            [
                {
                    "principle": "Exemplary damages require unlawful conduct.",
                    "confidence": "medium",
                    "source_section": "reasons",
                }
            ],
        )


class PayloadTests(unittest.TestCase):
    def test_build_payload_uses_batch_message_shape_and_json_schema(self) -> None:
        cases = [
            module.CaseRecord(
                order_id="209594856",
                markdown_path="a.md",
                sidecar_path="a.json",
                markdown_text="Case A",
                sidecar={"application_number": "4744510", "date_of_issue": "18/01/2024"},
                gold_fields={"application_number": "4744510"},
                approximate_tokens=10,
                redacted=False,
            ),
            module.CaseRecord(
                order_id="240127915",
                markdown_path="b.md",
                sidecar_path="b.json",
                markdown_text="Case B",
                sidecar={"application_number": "5335322", "date_of_issue": "15/10/2025"},
                gold_fields={"application_number": "5335322"},
                approximate_tokens=20,
                redacted=True,
            ),
        ]

        payload = module.build_payload(
            model="test-model",
            cases=cases,
            temperature=0.0,
            max_tokens=300,
            enable_thinking=True,
            thinking_token_budget=4096,
        )

        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["temperature"], 0.0)
        self.assertEqual(payload["max_tokens"], 300)
        self.assertEqual(payload["thinking_token_budget"], 4096)
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": True})
        self.assertEqual(len(payload["messages"]), 2)
        self.assertEqual(payload["messages"][0][0]["role"], "user")
        self.assertIn("You extract structured metadata from a New Zealand Tenancy Tribunal decision.", payload["messages"][0][0]["content"])
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(
            payload["response_format"]["json_schema"]["name"],
            "tribunal_extraction",
        )

    def test_validate_schema_flags_missing_keys_enums_and_extra_properties(self) -> None:
        errors = module.validate_response_schema_object(
            {
                "citation": "[2024] NZTT 4744510",
                "application_number": "4744510",
                "decision_date": "2024-01-18",
                "tribunal_location": "Remote Location",
                "adjudicator": "M Manhire",
                "applicant_name": "A",
                "applicant_role": "owner",
                "respondent_name": "B",
                "respondent_role": "tenant",
                "tenancy_address": "Somewhere",
                "has_name_redactions": False,
                "total_award_nzd": 2450.44,
                "payable_by": "tenant",
                "payable_to": "landlord",
                "extra_field": "unexpected",
            }
        )

        self.assertIn("missing_required:has_address_redactions", errors)
        self.assertIn("enum:applicant_role", errors)
        self.assertIn("extra_property:extra_field", errors)

    def test_select_cases_uses_prompt_plus_reasoning_budget(self) -> None:
        cases = [
            module.CaseRecord(
                order_id="1",
                markdown_path="a.md",
                sidecar_path="a.json",
                markdown_text="A",
                sidecar={},
                gold_fields={},
                approximate_tokens=100,
                redacted=False,
            ),
            module.CaseRecord(
                order_id="2",
                markdown_path="b.md",
                sidecar_path="b.json",
                markdown_text="B",
                sidecar={},
                gold_fields={},
                approximate_tokens=150,
                redacted=False,
            ),
            module.CaseRecord(
                order_id="3",
                markdown_path="c.md",
                sidecar_path="c.json",
                markdown_text="C",
                sidecar={},
                gold_fields={},
                approximate_tokens=200,
                redacted=False,
            ),
        ]

        selected = module.select_cases(
            ordered=cases,
            case_count=10,
            target_batch_tokens=1200,
            thinking_token_budget=400,
        )

        self.assertEqual([case.order_id for case in selected], ["1", "2"])
        self.assertEqual(module.reserved_case_tokens(cases[0], 400), 500)
        self.assertEqual(module.reserved_case_tokens(cases[1], 400), 550)


class ScoringTests(unittest.TestCase):
    def test_score_predictions_reports_per_field_matches(self) -> None:
        case = module.CaseRecord(
            order_id="209594856",
            markdown_path="a.md",
            sidecar_path="a.json",
            markdown_text="Case A",
            sidecar={"application_number": "4744510", "date_of_issue": "18/01/2024"},
            gold_fields={
                "application_number": "4744510",
                "decision_date": "2024-01-18",
                "total_award_nzd": 2450.44,
                "has_name_redactions": False,
            },
            approximate_tokens=10,
            redacted=False,
        )
        predictions = {
            "209594856": {
                "application_number": "4744510",
                "decision_date": "2024-01-18",
                "total_award_nzd": 2450.45,
                "has_name_redactions": False,
            }
        }

        summary = module.score_predictions(cases=[case], predictions=predictions)

        self.assertEqual(summary["overall"]["cases"], 1)
        self.assertEqual(summary["overall"]["fully_correct_cases"], 0)
        self.assertEqual(summary["fields"]["application_number"]["correct"], 1)
        self.assertEqual(summary["fields"]["decision_date"]["correct"], 1)
        self.assertEqual(summary["fields"]["total_award_nzd"]["correct"], 0)
        self.assertEqual(summary["fields"]["has_name_redactions"]["correct"], 1)
        self.assertEqual(summary["schema"]["json_parse_success_cases"], 1)
        self.assertEqual(summary["schema"]["schema_valid_cases"], 0)
        self.assertEqual(summary["schema"]["error_counts"]["missing_required"], 11)
        self.assertEqual(summary["case_results"][0]["matched_fields"], 3)
        self.assertEqual(summary["case_results"][0]["mismatched_fields"], ["total_award_nzd"])
        self.assertFalse(summary["case_results"][0]["schema_valid"])

    def test_score_predictions_reports_teacher_field_overlap_scores(self) -> None:
        case = module.CaseRecord(
            order_id="240225060",
            markdown_path="teacher.md",
            sidecar_path="teacher.json",
            markdown_text="Case A",
            sidecar={},
            gold_fields={"application_number": "4744510"},
            approximate_tokens=10,
            redacted=False,
            teacher_fields=module.extract_teacher_case_data(TEACHER_MARKDOWN),
        )
        predictions = {
            "240225060": {
                "application_number": "4744510",
                "case_summary": "The Tribunal distributed the bond.",
                "catchwords": ["bond distribution", "damages exemplary"],
                "questions_answered": ["How should the bond be distributed?"],
                "legal_principles": [
                    {
                        "principle": "Exemplary damages require unlawful conduct.",
                        "confidence": "high",
                        "source_section": "order",
                    }
                ],
            }
        }

        summary = module.score_predictions(cases=[case], predictions=predictions)

        generated = summary["generated_fields"]
        self.assertEqual(generated["reference"], "minimax_frontmatter")
        self.assertEqual(generated["overall"]["field_instances"], 9)
        self.assertEqual(generated["overall"]["predicted_field_instances"], 4)
        self.assertAlmostEqual(generated["fields"]["case_summary"]["average_f1"], 0.7143)
        self.assertEqual(generated["fields"]["catchwords"]["exact_matches"], 0)
        self.assertAlmostEqual(generated["fields"]["catchwords"]["average_f1"], 1.0)
        self.assertAlmostEqual(generated["fields"]["questions_answered"]["average_recall"], 0.5)
        self.assertAlmostEqual(generated["fields"]["legal_principles"]["exact_accuracy"], 1.0)
        self.assertEqual(summary["case_results"][0]["generated_field_scores"]["respondent_story"]["f1"], 0.0)
        self.assertAlmostEqual(
            summary["case_results"][0]["generated_field_scores"]["legal_principles"]["f1"],
            1.0,
        )

    def test_parse_predictions_maps_batch_choice_indices_back_to_cases(self) -> None:
        body = {
            "choices": [
                {
                    "index": 1,
                    "message": {
                        "content": json.dumps({"application_number": "5335322"}),
                    },
                },
                {
                    "index": 0,
                    "message": {
                        "content": json.dumps({"application_number": "4744510"}),
                    },
                },
            ]
        }
        cases = [
            module.CaseRecord(
                order_id="209594856",
                markdown_path="a.md",
                sidecar_path="a.json",
                markdown_text="Case A",
                sidecar={},
                gold_fields={},
                approximate_tokens=10,
                redacted=False,
            ),
            module.CaseRecord(
                order_id="240127915",
                markdown_path="b.md",
                sidecar_path="b.json",
                markdown_text="Case B",
                sidecar={},
                gold_fields={},
                approximate_tokens=20,
                redacted=True,
            ),
        ]

        predictions = module.parse_predictions(cases=cases, response_json=body)

        self.assertEqual(predictions["209594856"]["application_number"], "4744510")
        self.assertEqual(predictions["240127915"]["application_number"], "5335322")


if __name__ == "__main__":
    unittest.main()
