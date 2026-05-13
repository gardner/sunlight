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


def _row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _data_cells(regions: list[TableRegion]) -> set[str]:
    values: set[str] = set()
    for region in regions:
        for line in region.lines:
            if SEPARATOR_ROW_RE.match(line):
                continue
            for cell in _row_cells(line):
                if cell:
                    values.add(cell)
    return values


def _is_continuation(region: TableRegion, prior_cells: set[str]) -> bool:
    for line in region.lines:
        if SEPARATOR_ROW_RE.match(line):
            continue
        cells = [c for c in _row_cells(line) if c]
        if not cells:
            return False
        matches = sum(1 for c in cells if c in prior_cells)
        return matches / len(cells) >= 0.5
    return False


def _belongs_with(region: TableRegion, current: list[TableRegion]) -> bool:
    if not current:
        return True
    if region.column_count == current[-1].column_count:
        return True
    return _is_continuation(region, _data_cells(current))


def group_into_logical_tables(regions: list[TableRegion]) -> list[LogicalTable]:
    grouped: list[LogicalTable] = []
    current: list[TableRegion] = []
    for region in regions:
        if _belongs_with(region, current):
            current.append(region)
        else:
            grouped.append(LogicalTable(regions=list(current)))
            current = [region]
    if current:
        grouped.append(LogicalTable(regions=list(current)))
    return grouped


def _read_pipe_csv(lines: list[str]) -> pd.DataFrame:
    df = pd.read_csv(
        io.StringIO("\n".join(lines)),
        sep=r"\s*\|\s*",
        engine="python",
        skipinitialspace=True,
        dtype=str,
        keep_default_na=False,
    )
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _column_emptiness(region: TableRegion) -> list[float]:
    totals: list[int] = []
    empties: list[int] = []
    for line in region.lines:
        if SEPARATOR_ROW_RE.match(line):
            continue
        cells = _row_cells(line)
        if len(cells) > len(totals):
            totals.extend([0] * (len(cells) - len(totals)))
            empties.extend([0] * (len(cells) - len(empties)))
        for i, cell in enumerate(cells):
            totals[i] += 1
            if not cell:
                empties[i] += 1
    return [(empties[i] / totals[i]) if totals[i] else 0.0 for i in range(len(totals))]


def _drop_indices(region: TableRegion, drop: set[int]) -> list[str]:
    out: list[str] = []
    for line in region.lines:
        if SEPARATOR_ROW_RE.match(line):
            continue
        cells = _row_cells(line)
        kept = [c for i, c in enumerate(cells) if i not in drop]
        out.append("|".join(kept))
    return out


def _reconcile_region_lines(region: TableRegion, target_cols: int) -> list[str]:
    if region.column_count <= target_cols:
        return _drop_indices(region, set())
    emptiness = _column_emptiness(region)
    excess = region.column_count - target_cols
    # Drop the `excess` columns with highest emptiness, preferring inner cols
    # (header/last data cols are load-bearing; spacers are interior).
    ranked = sorted(
        range(len(emptiness)),
        key=lambda i: (-emptiness[i], 0 if 0 < i < len(emptiness) - 1 else 1, i),
    )
    drop = set(ranked[:excess])
    return _drop_indices(region, drop)


def _clean_body_lines(regions: list[TableRegion]) -> list[str]:
    target_cols = min(r.column_count for r in regions)
    out: list[str] = []
    for region in regions:
        out.extend(_reconcile_region_lines(region, target_cols))
    return out


def parse_region(region: TableRegion) -> pd.DataFrame:
    return _read_pipe_csv(_clean_body_lines([region]))


def parse_logical_table(table: LogicalTable) -> pd.DataFrame:
    return _read_pipe_csv(_clean_body_lines(table.regions))
