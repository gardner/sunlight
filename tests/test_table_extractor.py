import sys
import tempfile
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


class ParseLogicalTableTests(unittest.TestCase):
    def test_single_region_logical_table_matches_parse_region(self):
        body = read_fixture("01_tiny_clean.md")
        regions = table_extractor.detect_table_regions(body)
        logical = table_extractor.group_into_logical_tables(regions)[0]
        self.assertEqual(
            table_extractor.parse_logical_table(logical).shape,
            table_extractor.parse_region(regions[0]).shape,
        )

    def test_multiblock_same_schema_concatenates_rows(self):
        body = read_fixture("08_multiblock_different_schemas.md")
        logical = table_extractor.group_into_logical_tables(
            table_extractor.detect_table_regions(body)
        )
        roster = table_extractor.parse_logical_table(logical[0])
        self.assertEqual(roster.shape[1], 6)
        self.assertGreaterEqual(roster.shape[0], 25)
        self.assertIn("MOTU3611", roster.iloc[:, 0].tolist())
        self.assertIn("RICH337", roster.iloc[:, 0].tolist())

    def test_column_shift_table_reconciles_to_uniform_schema(self):
        body = read_fixture("07_multiblock_column_shift.md")
        logical = table_extractor.group_into_logical_tables(
            table_extractor.detect_table_regions(body)
        )[0]
        df = table_extractor.parse_logical_table(logical)
        # Phantom empty spacer column collapsed: 5-col + 4-col → 4 cols
        self.assertEqual(df.shape[1], 4)
        org_col = df.iloc[:, -1].dropna().astype(str).tolist()
        self.assertTrue(any("3JRS CONSTRUCTION LIMITED" in v for v in org_col))
        self.assertTrue(any("AGVANCE LIMITED" in v for v in org_col))


class SummarizeTableTests(unittest.TestCase):
    def test_summary_states_shape(self):
        body = read_fixture("02_small_clean.md")
        df = table_extractor.parse_region(
            table_extractor.detect_table_regions(body)[0]
        )
        summary = table_extractor.summarize_table(df)
        self.assertIn("6 rows", summary)
        self.assertIn("3 columns", summary)

    def test_summary_lists_column_headers(self):
        body = read_fixture("02_small_clean.md")
        df = table_extractor.parse_region(
            table_extractor.detect_table_regions(body)[0]
        )
        summary = table_extractor.summarize_table(df)
        self.assertIn("South Side", summary)
        self.assertIn("North Side", summary)

    def test_summary_includes_sample_rows(self):
        body = read_fixture("02_small_clean.md")
        df = table_extractor.parse_region(
            table_extractor.detect_table_regions(body)[0]
        )
        summary = table_extractor.summarize_table(df, max_sample_rows=2)
        self.assertIn("Structural Upgrade", summary)
        self.assertIn("Fitout", summary)
        self.assertNotIn("Grand Total", summary)


class DetectFooterPhraseTests(unittest.TestCase):
    def test_finds_official_information_act_footer(self):
        body = read_fixture("07_multiblock_column_shift.md")
        phrase = table_extractor.detect_footer_phrase(body)
        self.assertEqual(phrase, "Released under the Official Information Act 1982")

    def test_returns_none_when_no_footer_present(self):
        body = read_fixture("06_pure_prose.md")
        self.assertIsNone(table_extractor.detect_footer_phrase(body))


class CleanFooterLeakTests(unittest.TestCase):
    def _df(self, values):
        import pandas as pd

        return pd.DataFrame({"col": values})

    def test_strips_trailing_footer_tokens(self):
        df = self._df(
            [
                "4U WOODFLOORING LIMITED Act",
                "AIIZ ASBESTOS & DEMOLITION LIMITED 1982",
                "ALL NEW ZEALAND FINANCIAL SERVICES LIMITED Information",
                "NORMAL COMPANY LIMITED",
            ]
        )
        out = table_extractor.clean_footer_leak(
            df, "Released under the Official Information Act 1982"
        )
        self.assertEqual(
            out["col"].tolist(),
            [
                "4U WOODFLOORING LIMITED",
                "AIIZ ASBESTOS & DEMOLITION LIMITED",
                "ALL NEW ZEALAND FINANCIAL SERVICES LIMITED",
                "NORMAL COMPANY LIMITED",
            ],
        )

    def test_preserves_legitimate_interior_uses(self):
        df = self._df(["INFORMATION SYSTEMS LIMITED"])
        out = table_extractor.clean_footer_leak(
            df, "Released under the Official Information Act 1982"
        )
        self.assertEqual(out["col"].tolist(), ["INFORMATION SYSTEMS LIMITED"])

    def test_no_footer_phrase_is_noop(self):
        df = self._df(["4U WOODFLOORING LIMITED Act"])
        out = table_extractor.clean_footer_leak(df, None)
        self.assertEqual(out["col"].tolist(), ["4U WOODFLOORING LIMITED Act"])


class ExtractTablesTests(unittest.TestCase):
    def test_single_table_writes_csv_and_rewrites_body(self):
        body = read_fixture("02_small_clean.md")
        with tempfile.TemporaryDirectory() as td:
            rewritten, extracted = table_extractor.extract_tables(
                body, document_id="doc_test_02", out_dir=Path(td)
            )
            self.assertEqual(len(extracted), 1)
            et = extracted[0]
            self.assertTrue(et.csv_path.exists())
            csv_text = et.csv_path.read_text(encoding="utf-8")
            self.assertIn("South Side", csv_text)
            self.assertIn("Structural Upgrade", csv_text)
            # Rewritten body keeps the document_id frontmatter and drops pipe rows
            self.assertIn("doc_fyi_15104_57812_4_9d52c5569dd6", rewritten)
            self.assertNotIn("| Structural Upgrade |", rewritten)
            self.assertIn("Table:", rewritten)

    def test_no_tables_returns_body_unchanged(self):
        body = read_fixture("06_pure_prose.md")
        with tempfile.TemporaryDirectory() as td:
            rewritten, extracted = table_extractor.extract_tables(
                body, document_id="doc_test_06", out_dir=Path(td)
            )
            self.assertEqual(extracted, [])
            self.assertEqual(rewritten, body)

    def test_multiple_logical_tables_each_get_a_csv(self):
        body = read_fixture("08_multiblock_different_schemas.md")
        with tempfile.TemporaryDirectory() as td:
            _, extracted = table_extractor.extract_tables(
                body, document_id="doc_test_08", out_dir=Path(td)
            )
            self.assertEqual(len(extracted), 3)
            paths = {et.csv_path for et in extracted}
            self.assertEqual(len(paths), 3)
            for et in extracted:
                self.assertTrue(et.csv_path.exists())

    def test_footer_cleanup_is_applied(self):
        body = read_fixture("07_multiblock_column_shift.md")
        with tempfile.TemporaryDirectory() as td:
            _, extracted = table_extractor.extract_tables(
                body, document_id="doc_test_07", out_dir=Path(td)
            )
            import pandas as pd

            df = pd.read_csv(extracted[0].csv_path, dtype=str, keep_default_na=False)
            org = df.iloc[:, -1].tolist()
            for name in org:
                self.assertFalse(name.endswith(" 1982"), name)
                self.assertFalse(name.endswith(" Act"), name)
                self.assertFalse(name.endswith(" Information"), name)


if __name__ == "__main__":
    unittest.main()
