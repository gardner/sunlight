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


if __name__ == "__main__":
    unittest.main()
