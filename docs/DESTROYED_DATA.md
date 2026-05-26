# Tenancy LLM Truncation Incident

Date investigated: 2026-05-26.

## Executive Summary

The Tenancy source corpus was not destroyed. The original PDFs and converted
Docling markdown bodies remain present in `storage/justice/tenancy/markdown_docling`.

The damaged data is generated LLM metadata written into markdown frontmatter.
The LLM enrichment code sent only the first 5,000 characters of each decision
body to the model. That makes summaries, catchwords, questions answered, legal
principles, and suggested tags unreliable for any document whose body exceeded
5,000 characters.

Current confirmed impact:

| Item | Count | Status |
| --- | ---: | --- |
| Current Docling Tenancy markdown files | 43,854 | Source body present |
| Current markdown files with `llm_enrichment_version` | 8,940 | Generated metadata suspect |
| Enriched files whose body is over 5,000 chars | 8,007 | Confirmed generated from partial input |
| Enriched files whose body is at or under 5,000 chars | 933 | Not truncated by length, but same run/version |
| Pending LLM markdown files after DeepSeek reset | 34,914 | Not currently enriched |
| OpenRouter DeepSeek rows written by aborted run | 79 | Reset during incident response |
| Current OpenRouter DeepSeek metadata rows | 0 | Reset completed |
| LanceDB Tenancy rows | 412,537 | Mostly source chunks |
| LanceDB generated-view rows | 4 | Generated metadata vectors exist only for one document |

Do not trust `tenancy-llm-v1` generated metadata. Regenerate it from full,
explicitly cleaned text under a new enrichment version.

## Root Cause

The production LLM enrichment path had an excerpt cap:

```python
DEFAULT_LLM_MAX_CHARS = 5000
```

and then built the model input with:

```python
"excerpt": body.strip()[:max_chars]
```

That code existed in the committed production path before the OpenRouter work
and remained present in commit `ff0874f`:

```text
scripts/ingest_tenancy.py: DEFAULT_LLM_MAX_CHARS = 5000
scripts/tenancy_llm.py: "excerpt": body.strip()[:max_chars]
```

This was a bad carry-over from constrained provider testing. It silently
converted full decisions into prefix excerpts before metadata generation. The
model was instructed to answer from an `excerpt`, so it produced plausible
metadata from incomplete evidence.

## Timeline

Known sequence from repo history and logs:

1. The Tenancy ingestion path already contained `DEFAULT_LLM_MAX_CHARS = 5000`
   and `body.strip()[:max_chars]` when direct MiniMax enrichment was configured.
2. Direct MiniMax production run:
   `logs/tenancy-llm-minimax-direct-rpm15-20260525-232159.log`.
   The log shows 8,874 request starts and 8,846 progress lines before the run
   was manually stopped.
3. Current markdown state shows 8,917 files stamped with
   `llm_enrichment_model: MiniMax-M2.7-highspeed`.
4. Short OpenRouter production attempt:
   `logs/tenancy-llm-openrouter-deepseek-rpm60-conc30-20260526-102409.log`.
   It started 114 requests and logged 79 successful enrichments before being
   stopped.
5. Those 79 OpenRouter DeepSeek metadata rows were reset by removing only LLM
   generated frontmatter fields. Current markdown state has 0 files stamped
   with `llm_enrichment_model: deepseek/deepseek-v4-flash`.

## Current Metadata Impact

Current model breakdown in markdown frontmatter:

| `llm_enrichment_model` | Files | Body > 5,000 chars | Body <= 5,000 chars | Contains `Please read carefully:` |
| --- | ---: | ---: | ---: | ---: |
| `MiniMax-M2.7-highspeed` | 8,917 | 7,988 | 929 | 8,880 |
| `nvidia/nemotron-3-super-120b-a12b` | 21 | 18 | 3 | 21 |
| `nvidia/regular-nvidia` | 1 | 1 | 0 | 1 |
| `nvidia/regular` | 1 | 0 | 1 | 1 |

Generated metadata field counts:

| Field | Count |
| --- | ---: |
| `case_summary` | 8,940 |
| `catchwords` | 8,940 |
| `questions_answered` | 8,940 |
| `legal_principles` | 8,796 |

Interpretation:

* 8,007 files are confirmed damaged by prefix-only LLM input because their
  bodies exceed 5,000 characters.
* 933 files were not truncated by length, but they share the same enrichment
  version and should be regenerated for consistency.
* All `tenancy-llm-v1` metadata should be considered invalid until replaced.

## What Was Not Destroyed

The source corpus appears intact:

* PDFs were not modified by the LLM enrichment path.
* Markdown bodies were not truncated by `build_llm_input`; it only created the
  request payload sent to the model.
* `apply_generated_enrichment()` rewrites frontmatter but preserves the parsed
  markdown body when calling `render_tenancy_markdown(merged, body)`.
* Current Docling markdown count is 43,854 and every parsed file had a non-empty
  body in the audit.

The existing LanceDB Tenancy table is mostly not contaminated by generated
metadata vectors:

| LanceDB row category | Count |
| --- | ---: |
| Total `chunks_v2` rows | 412,537 |
| `retrieval_view = 'source_text'` | 412,533 |
| `generated = false` | 412,533 |
| `generated = true` | 4 |
| `case_summary` generated rows | 1 |
| `catchwords` generated rows | 1 |
| `questions_answered` generated rows | 1 |
| `legal_principles` generated rows | 1 |

The four generated rows all belong to `doc_justice_tenancy_172069933`.

Important caveat: 8,940 markdown files currently have embedded marker files.
Those markers mean the embedding step may skip them on a future run unless
forced. If generated metadata is regenerated and generated retrieval views are
desired, the embedding marker strategy must be revisited deliberately.

## Propagation Risks

### Markdown Frontmatter

This is the primary affected store. Generated metadata was written directly into
markdown frontmatter for 8,940 files.

Affected keys:

* `case_summary`
* `catchwords`
* `questions_answered`
* `legal_principles`
* `llm_suggested_tags`
* `llm_enriched_at`
* `llm_enrichment_model`
* `llm_enrichment_version`

### LanceDB

Current LanceDB vectors are almost entirely source-text chunks. The table schema
does not include `llm_enrichment_model`, and only four rows are generated views.

Risk remains for future runs:

* `build_retrieval_documents()` creates generated retrieval views from
  `case_summary`, `catchwords`, `questions_answered`, and `legal_principles`.
* If embeddings are forced while bad metadata remains, bad generated views will
  enter LanceDB and downstream vector exports.

### Hugging Face Markdown Export

`scripts/export_hf_markdown_dataset.py` exports the full markdown body, but also
exports `frontmatter_json`. If a dataset export happened after the bad LLM run,
that export contains suspect generated metadata in frontmatter.

The markdown body in such an export should still be full text.

### BM25 D1 Export

`scripts/export_bm25_to_d1.py` indexes markdown body chunks, not LLM request
payloads. It has its own cap:

```python
DEFAULT_MAX_CHUNK_TEXT_CHARS = 12000
indexed_text = collapse_whitespace(chunk_text)[:max_chunk_text_chars]
```

That is separate from the LLM metadata incident. It is not source corpus
destruction, but it is an indexing truncation risk and should be reviewed before
claiming BM25 has complete chunk text.

### R2 / Vectorize / Public Search

This audit did not prove whether any post-LLM markdown, BM25, R2, Vectorize, or
Hugging Face export was published externally. That needs a separate deployment
and artifact audit.

Local evidence says the main Tenancy LanceDB table currently has only four
generated-view rows, so most local vectors are source text rather than bad LLM
metadata.

## Other Truncation-Like Code Paths

These are not the same incident, but they should be treated as follow-up audit
items:

* `scripts/probe_nvidia_tenancy_models.py` previously used
  `build_llm_input(..., args.max_chars)` for model probes. That probe
  truncation path has been removed; old probe findings from before the fix were
  based on truncated inputs.
* `scripts/generate_eval_questions.py` intentionally extracts excerpts for eval
  question generation. It does not write corpus source data.
* `scripts/parallel_convert_and_embed.py` stores `text_preview =
  chunk_text[:500]`; this is a preview field. The row still stores `chunk_text`.
* `scripts/export_bm25_to_d1.py` truncates indexed chunk text to 12,000
  characters by default. Review before production BM25 use.
* `scripts/tenancy_corpus.py` uses `body.split("Please read carefully:", 1)[0]`
  only for decision date extraction. It does not remove or truncate the body.

## Correct Cleaning Boundary

The user-specified acceptable cleaning boundary is not a character limit.

Acceptable cleanup for LLM input:

* Send full decision text up to a semantic cleanup point.
* Remove only super-redundant boilerplate, such as text after the
  `Please read carefully:` section, if that rule is explicitly implemented and
  tested.
* Preserve source markdown bodies unchanged.

Unacceptable cleanup:

* Prefix truncation.
* Hidden `max_chars` defaults.
* Any request payload cap that silently drops source facts.

If a cleaned body is still too large for a model, the system should fail the
document or use an explicit chunked/merge strategy. It should not silently send
the first N characters.

## Post-Amble Removal Run

The exact standalone post-amble heading removal was run on 2026-05-26.

Rule applied:

```regex
(?m)^##\s*Please read carefully:\s*$
```

For each matched markdown file, everything from the first exact heading match to
EOF was removed. The source frontmatter and all body text before the heading were
left in place.

Run artifact:

```text
logs/tenancy-postamble-removal-20260526-110737.jsonl
logs/tenancy-postamble-removal-20260526-110737.summary.json
```

Result:

| Item | Count |
| --- | ---: |
| Markdown files scanned | 43,854 |
| Files changed | 43,672 |
| Files without exact standalone heading | 182 |
| Files with multiple exact headings | 12 |
| Total characters removed | 133,256,494 |
| Non-empty markdown bodies after removal | 43,854 |
| Parse errors after removal | 0 |
| Remaining exact `## Please read carefully:` in parsed bodies | 0 after outlier cleanup |
| Remaining `Please read carefully:` phrase hits in parsed bodies | 0 after outlier cleanup |

The six remaining phrase hits were not removed by the exact rule and were later
cleaned individually:

* `doc_justice_tenancy_206727788.md`: `## OPlease read carefully:`
* `doc_justice_tenancy_208507553.md`: `## 145. Please read carefully:`
* `doc_justice_tenancy_226645711.md`: `- Please read carefully:`
* `doc_justice_tenancy_228205859.md`: `## Please read carefully:'`
* `doc_justice_tenancy_legacy_6129174.md`: bare `Please read carefully:`
* `doc_justice_tenancy_legacy_7283864.md`: `## ,. Please read carefully:`

Outlier cleanup artifact:

```text
logs/tenancy-postamble-outlier-cleanup-20260526-051512.jsonl
```

The outlier cleanup preserved adjudicator/date blocks that appeared after the
malformed post-amble heading in `doc_justice_tenancy_208507553.md` and
`doc_justice_tenancy_legacy_6129174.md`. The requested leave-alone file
`doc_justice_tenancy_206727790.md` was not modified.

Post-cleanup validation found 43,854 parseable markdown files, 43,854 non-empty
parsed bodies, and zero remaining `Please read carefully:` / `OPlease read
carefully:` phrase hits.

## Current Workspace State

No production Tenancy LLM process was running during the final audit check:

```text
ps search for ingest_tenancy / tenancy-llm / OpenRouter: no matching worker
```

Current uncommitted code changes exist from the mitigation attempt:

* `scripts/ingest_tenancy.py`
* `scripts/tenancy_llm.py`
* `scripts/tenancy_llm_request.py`
* `scripts/probe_nvidia_tenancy_models.py`
* `tests/test_ingest_tenancy.py`
* `tests/test_tenancy_corpus.py`
* `tests/test_tenancy_llm_config.py`
* `tests/test_tenancy_llm_request_options.py`

The `--llm-max-chars` CLI option, positive `max_chars` production call path,
and `excerpt` LLM payload field have been removed. `build_llm_input()` now sends
full parsed markdown body text under `document_text`.

## Required Remediation

Do not restart LLM enrichment until these are complete:

1. Add a tested `clean_tenancy_llm_body()` function that removes only approved
   redundant boilerplate, especially the section after `Please read carefully:`.
2. Add tests proving that body text after 5,000 characters is included when it
   appears before the approved boilerplate boundary.
3. Add tests proving that `Please read carefully:` boilerplate is removed from
   LLM input while source markdown remains unchanged.
4. Reset or supersede all `tenancy-llm-v1` metadata under the new
   `tenancy-llm-v2` schema. Do not mix old generated
   metadata with regenerated metadata.
5. Run a small canary against copied markdown files and inspect the actual
   request payload length and content boundary before writing production files.
6. Only after canary review, run production regeneration.

## Recommended Metadata Recovery Plan

Use a deliberate recovery step, not an ad hoc edit:

1. Back up current markdown frontmatter or snapshot the whole markdown directory.
2. Remove generated LLM keys from all files with
   `llm_enrichment_version: tenancy-llm-v1`.
3. Keep deterministic metadata such as citation, decision date, legal issue
   tags, statute sections, suppression status, ordered amounts, R2 keys, and
   source URLs.
4. Regenerate LLM metadata under a new version from full cleaned text.
5. Rebuild generated retrieval views only after regenerated metadata passes
   spot checks.
6. Rebuild or force-refresh embedding markers only if generated retrieval views
   are intentionally part of the retrieval design.

## Evidence Commands Used

Representative read-only audit commands:

```bash
git show ff0874f:scripts/ingest_tenancy.py | rg -n "DEFAULT_LLM_MAX_CHARS|llm-max-chars|max_chars"
git show ff0874f:scripts/tenancy_llm.py | rg -n "build_llm_input|body\\.strip\\(\\)\\[:max_chars\\]|max_chars"
rg -n "max_chars|llm-max-chars|DEFAULT_LLM_MAX_CHARS|body\\.strip|Please read carefully" scripts tests docs PROGRESS.md
```

Markdown count audit:

```bash
uv run python - <<'PY'
from pathlib import Path
from collections import Counter
import sys
sys.path.insert(0, 'scripts')
from tenancy_corpus import parse_tenancy_markdown, PIPELINE_VERSION

root = Path('storage/justice/tenancy/markdown_docling')
counts = Counter()
models = Counter()
for path in root.glob('*.md'):
    metadata, body = parse_tenancy_markdown(path.read_text(encoding='utf-8'))
    counts['markdown_files'] += 1
    if body.strip():
        counts['nonempty_body'] += 1
    if metadata.get('pipeline_version') == PIPELINE_VERSION:
        counts['current_pipeline_version'] += 1
    if metadata.get('llm_enrichment_version'):
        counts['llm_enrichment_version_present'] += 1
    if len(body.strip()) > 5000 and metadata.get('llm_enrichment_version'):
        counts['enriched_body_gt_5000'] += 1
    if metadata.get('llm_enrichment_model'):
        models[str(metadata['llm_enrichment_model'])] += 1
print(counts)
print(models)
PY
```

LanceDB count audit:

```bash
uv run python - <<'PY'
import lancedb
table = lancedb.connect('storage/justice/tenancy/lancedb').open_table('chunks_v2')
print(table.count_rows())
for expr in [
    "retrieval_view = 'source_text'",
    "generated = true",
    "generated = false",
    "retrieval_view = 'case_summary'",
    "retrieval_view = 'catchwords'",
    "retrieval_view = 'questions_answered'",
    "retrieval_view = 'legal_principles'",
]:
    print(expr, table.count_rows(expr))
PY
```
