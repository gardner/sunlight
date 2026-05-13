from __future__ import annotations

import re
from dataclasses import dataclass

PIPE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")


@dataclass(frozen=True)
class TableRegion:
    line_start: int
    line_end: int
    lines: list[str]


def detect_table_regions(markdown_body: str) -> list[TableRegion]:
    regions: list[TableRegion] = []
    lines = markdown_body.splitlines()
    run_start: int | None = None
    run: list[str] = []

    def _flush(end_index: int) -> None:
        if len(run) >= 3 and run_start is not None:
            regions.append(TableRegion(line_start=run_start, line_end=end_index, lines=list(run)))

    for i, line in enumerate(lines):
        if PIPE_ROW_RE.match(line):
            if run_start is None:
                run_start = i
            run.append(line)
            continue
        _flush(i)
        run_start = None
        run = []

    _flush(len(lines))
    return regions
