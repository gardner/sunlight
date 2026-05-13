from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

PIPE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
SEPARATOR_ROW_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")


@dataclass(frozen=True)
class TableRegion:
    line_start: int
    line_end: int
    lines: list[str]

    @property
    def column_count(self) -> int:
        for line in self.lines:
            if SEPARATOR_ROW_RE.match(line):
                continue
            cells = line.strip().strip("|").split("|")
            return len(cells)
        return 0


@dataclass(frozen=True)
class LogicalTable:
    regions: list[TableRegion]

    @property
    def column_count(self) -> int:
        return self.regions[0].column_count


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


def group_into_logical_tables(regions: list[TableRegion]) -> list[LogicalTable]:
    grouped: list[LogicalTable] = []
    current: list[TableRegion] = []
    current_cols: int | None = None
    for region in regions:
        if current_cols is None or region.column_count == current_cols:
            current.append(region)
            current_cols = region.column_count
            continue
        grouped.append(LogicalTable(regions=list(current)))
        current = [region]
        current_cols = region.column_count
    if current:
        grouped.append(LogicalTable(regions=list(current)))
    return grouped


def parse_region(region: TableRegion) -> pd.DataFrame:
    body_lines = [
        ln.strip().strip("|")
        for ln in region.lines
        if not SEPARATOR_ROW_RE.match(ln)
    ]
    df = pd.read_csv(
        io.StringIO("\n".join(body_lines)),
        sep=r"\s*\|\s*",
        engine="python",
        skipinitialspace=True,
        dtype=str,
        keep_default_na=False,
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df
