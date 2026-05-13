import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "markdown_tables"

sys.path.insert(0, str(SCRIPTS_DIR))

import table_extractor  # noqa: E402


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


class DetectTableRegionsTests(unittest.TestCase):
    def test_tiny_clean_table_yields_single_region(self):
        body = read_fixture("01_tiny_clean.md")
        regions = table_extractor.detect_table_regions(body)
        self.assertEqual(len(regions), 1)

    def test_pure_prose_yields_no_regions(self):
        body = read_fixture("06_pure_prose.md")
        regions = table_extractor.detect_table_regions(body)
        self.assertEqual(regions, [])

    def test_scattered_pipes_without_blocks_yield_no_regions(self):
        body = read_fixture("05_pipes_no_table.md")
        regions = table_extractor.detect_table_regions(body)
        self.assertEqual(regions, [])

    def test_region_exposes_line_indices_and_lines(self):
        body = read_fixture("01_tiny_clean.md")
        regions = table_extractor.detect_table_regions(body)
        region = regions[0]
        lines = body.splitlines()
        self.assertEqual(region.lines, lines[region.line_start : region.line_end])
        self.assertTrue(all("|" in ln for ln in region.lines))
        self.assertEqual(len(region.lines), 5)

    def test_prose_surrounding_table_is_preserved(self):
        body = read_fixture("04_prose_with_small_table.md")
        lines = body.splitlines()
        regions = table_extractor.detect_table_regions(body)
        self.assertEqual(len(regions), 1)
        region = regions[0]
        prose_before = "\n".join(lines[: region.line_start])
        prose_after = "\n".join(lines[region.line_end :])
        self.assertIn("Pakuranga", prose_before)
        self.assertNotIn("|", prose_after.replace("---", "").strip() or "x")


class ParseRegionTests(unittest.TestCase):
    def test_tiny_clean_table_parses_to_3x2_dataframe(self):
        body = read_fixture("01_tiny_clean.md")
        region = table_extractor.detect_table_regions(body)[0]
        df = table_extractor.parse_region(region)
        self.assertEqual(df.shape, (3, 2))

    def test_wide_table_parses_to_22x26_dataframe(self):
        body = read_fixture("03_wide_table.md")
        region = table_extractor.detect_table_regions(body)[0]
        df = table_extractor.parse_region(region)
        self.assertEqual(df.shape, (22, 26))

    def test_small_clean_table_parses_to_6x3_dataframe(self):
        body = read_fixture("02_small_clean.md")
        region = table_extractor.detect_table_regions(body)[0]
        df = table_extractor.parse_region(region)
        self.assertEqual(df.shape, (6, 3))


class GroupLogicalTablesTests(unittest.TestCase):
    def test_single_region_yields_single_logical_table(self):
        body = read_fixture("01_tiny_clean.md")
        regions = table_extractor.detect_table_regions(body)
        logical = table_extractor.group_into_logical_tables(regions)
        self.assertEqual(len(logical), 1)
        self.assertEqual(logical[0].regions, regions)

    def test_different_schemas_yield_separate_logical_tables(self):
        body = read_fixture("08_multiblock_different_schemas.md")
        regions = table_extractor.detect_table_regions(body)
        self.assertEqual(len(regions), 5)
        logical = table_extractor.group_into_logical_tables(regions)
        self.assertEqual(len(logical), 3)
        column_counts = [lt.column_count for lt in logical]
        self.assertEqual(column_counts, [6, 5, 3])

    def test_adjacent_blocks_with_one_column_shift_merge(self):
        body = read_fixture("07_multiblock_column_shift.md")
        regions = table_extractor.detect_table_regions(body)
        self.assertEqual(len(regions), 2)
        self.assertEqual([r.column_count for r in regions], [5, 4])
        logical = table_extractor.group_into_logical_tables(regions)
        self.assertEqual(len(logical), 1)
        self.assertEqual(logical[0].regions, regions)


if __name__ == "__main__":
    unittest.main()
