#!/usr/bin/env python3
"""CLI entrypoint and compatibility exports for tribunal batch evals."""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vllm import tribunal_eval_extract as extract
from vllm import tribunal_eval_runner as runner
from vllm import tribunal_eval_schema as schema

CaseRecord = runner.CaseRecord
build_payload = runner.build_payload
build_case_batches = runner.build_case_batches
compact_case_manifest = runner.compact_case_manifest
discover_cases = runner.discover_cases
load_markdown_only_record = runner.load_markdown_only_record
parse_predictions = runner.parse_predictions
post_json = runner.post_json
reserved_case_tokens = runner.reserved_case_tokens
run_eval = runner.run_eval
select_cases = runner.select_cases
score_predictions = runner.score_predictions
strip_front_matter = extract.strip_front_matter
extract_gold_case_data = extract.extract_gold_case_data
extract_teacher_case_data = extract.extract_teacher_case_data
extract_citation = extract.extract_citation
normalize_party_value = extract.normalize_party_value
normalize_string = extract.normalize_string
validate_response_schema_object = schema.validate_response_schema_object
values_match = extract.values_match


def main() -> None:
    args = runner.parse_args()
    summary = run_eval(args)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
