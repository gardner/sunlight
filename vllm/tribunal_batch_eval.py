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

CaseRecord = runner.CaseRecord
build_payload = runner.build_payload
compact_case_manifest = runner.compact_case_manifest
discover_cases = runner.discover_cases
parse_predictions = runner.parse_predictions
post_json = runner.post_json
run_eval = runner.run_eval
score_predictions = runner.score_predictions
strip_front_matter = extract.strip_front_matter
extract_gold_case_data = extract.extract_gold_case_data
extract_citation = extract.extract_citation
normalize_party_value = extract.normalize_party_value
normalize_string = extract.normalize_string
values_match = extract.values_match


def main() -> None:
    args = runner.parse_args()
    summary = run_eval(args)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
