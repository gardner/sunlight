## Markdown-table detector / parser fixtures

These markdowns are real Docling output from the FYI corpus (public OIA / LGOIMA
responses on fyi.org.nz). They are committed verbatim except for `07_*` and
`08_*`, which are trimmed to the first ~90 lines of much larger source files so
the pathologies they exercise stay reproducible without committing megabytes.

Detector contract (target behavior):

- `detect_tables(markdown_body) -> list[TableRegion]`
- `parse_table(region) -> ParsedTable | DirtyTable`

Per-fixture expectations the tests should assert:

| File | Detect | First block shape (post-merge) | Pathology |
|---|---|---|---|
| `01_tiny_clean.md` | 1 region | (3, 2) | Smoke test: smallest realistic table. |
| `02_small_clean.md` | 1 region | (6, 3) | Smoke test #2: different column count. |
| `03_wide_table.md` | 1 region | (22, 26) | Wide table — exercises column-axis handling. |
| `04_prose_with_small_table.md` | 1 region surrounded by prose | (3, 2) | Detector must extract the table and leave prose for normal embedding. Mid-document. |
| `05_pipes_no_table.md` | **0 regions** | n/a | Negative test: 5% pipe lines but no ≥3-row table block. Detector must NOT fire. |
| `06_pure_prose.md` | 0 regions | n/a | Negative test: zero pipes. |
| `07_multiblock_column_shift.md` | 1 logical table, ≥2 blocks merged | (≈60, 4 or 5 after cleanup) | Trimmed from the 6.5 MB Daisy Appendix. Docling renders alternating 4- and 5-column layouts across pages, with text fragments (`Information`, `Official`, `under`, `Released`, `Act`, `1982`) bleeding into table cells from page footers. Tests should cover: (a) multi-block merge, (b) column-count reconciliation, (c) cell-content cleanup of footer-leak fragments. |
| `08_multiblock_different_schemas.md` | **3 distinct tables**, not one merged | shapes differ | Trimmed from F2706181 SMS Report. Same page contains three tables with different schemas (incident roster / elapsed times / party-notified log). Detector must NOT merge across schema changes — header signature differs. Tests: (a) schema-based block grouping, (b) headerless-continuation blocks (block 2 has no header row, only a separator), (c) page-number `3/713` leakage into a row. |

Source paths in `fyi/markdown/` (full versions, not committed at full size):

- `07_*` ← `DOIA_2324_0565_Daisy_Appendix.pdf__18dc8f92ea99.md` (lines 1–90 of 29,415)
- `08_*` ← `F2706181_SMS_Report_Walters_Bluff_Redacted.pdf__6673a4f31575.md` (lines 1–90)
