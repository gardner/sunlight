from __future__ import annotations

import re

PIPE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


def detect_table_regions(markdown_body: str) -> list[list[str]]:
    regions: list[list[str]] = []
    run: list[str] = []
    for line in markdown_body.splitlines():
        if PIPE_ROW_RE.match(line):
            run.append(line)
            continue
        if len(run) >= 3:
            regions.append(run)
        run = []
    if len(run) >= 3:
        regions.append(run)
    return regions
