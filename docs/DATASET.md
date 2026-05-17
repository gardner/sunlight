# Sunlight Dataset

This document records the plan for publishing Sunlight's converted FYI markdown
corpus as a Hugging Face dataset and keeping it updated over time.

## Goal

Publish a reusable public-record corpus containing:

* converted markdown body text
* FYI request, response, and attachment identifiers
* source citation URLs
* authority metadata where available
* original conversion frontmatter
* stable ids and content hashes for incremental updates

The dataset is intended for search, retrieval, reranking, RAG evaluation,
transparency research, and reproducible experiments. It is not the operational
store for Sunlight's request workflow.

## Current State

Local source markdown:

```text
fyi/markdown/*.md
```

Prepared Hugging Face export:

```text
storage/huggingface/sunlight-fyi-markdown
```

Current local export:

```text
rows: 9,665
parquet shards: 10
size: about 54 MB
empty frontmatter rows: 0
```

The old frontmatterless duplicate markdown files have been deleted. Future
exports intentionally skip markdown that does not parse with provenance
frontmatter, because dataset rows should always carry stable document metadata.

Exporter:

```text
scripts/export_hf_markdown_dataset.py
```

Tests:

```text
tests/test_export_hf_markdown_dataset.py
```

## Source Of Truth

The canonical source is the converted markdown with provenance frontmatter in
`fyi/markdown`. The Hugging Face dataset is a published artifact derived from
that source, not an editing location.

The source markdown is produced by the FYI conversion pipeline. The relevant
frontmatter fields include:

```text
document_id
fyi_request_id
fyi_response_id
fyi_attachment_id
request_url
source_url
original_filename
markdown_r2_key
pdf_r2_key
source
```

Request-level metadata is joined from:

```text
fyi/data/**/*.json
```

## Dataset Format

The publishable folder is Hugging Face-compatible:

```text
README.md
data/fyi_markdown-00000.parquet
data/fyi_markdown-00001.parquet
...
manifests/export-manifest.json
manifests/record-index.ndjson
```

Parquet is the primary data format because it is compact, typed, splittable, and
works well with the Hugging Face dataset viewer and `datasets` loader.

The dataset card is generated as `README.md` and includes Hugging Face metadata
frontmatter plus usage notes, limitations, and the living-update workflow.

## Row Schema

Each Parquet row is one source markdown document.

| Column | Meaning |
| --- | --- |
| `record_id` | Content-addressed row id derived from `document_id` and markdown body hash |
| `source` | Source collection, currently `fyi` |
| `corpus_version` | Export corpus label, currently `fyi-v1` |
| `document_id` | Stable Sunlight document id from markdown frontmatter |
| `fyi_request_id` | FYI request id |
| `fyi_response_id` | FYI response id |
| `fyi_attachment_id` | FYI attachment id |
| `authority_name` | Joined authority name from FYI request metadata |
| `authority_slug` | Joined FYI authority slug |
| `authority_category` | Derived authority category |
| `law_used` | FYI law field, such as OIA or LGOIMA |
| `described_state` | FYI request outcome/state descriptor |
| `request_year` | Year derived from request creation time |
| `request_created_at` | FYI request creation timestamp |
| `request_title` | FYI request title |
| `request_url` | FYI request page URL |
| `source_url` | FYI attachment/source URL |
| `original_filename` | Original attachment filename |
| `markdown_r2_key` | Planned/canonical markdown object key |
| `pdf_r2_key` | Planned/canonical PDF object key |
| `markdown_filename` | Local markdown filename at export time |
| `markdown_content` | Converted markdown body |
| `frontmatter_json` | Original markdown frontmatter serialized as JSON |
| `text_sha256` | SHA-256 hash of `markdown_content` |
| `content_chars` | Character count of `markdown_content` |
| `exported_at` | Export timestamp |

## Identity And Deduplication

`document_id` identifies the source document. It should remain stable across
exports for the same FYI attachment.

`text_sha256` identifies the exact markdown body. If the conversion output
changes, the hash changes.

`record_id` is derived from:

```text
sha256(document_id + "\n" + text_sha256)[:32]
```

This means:

* unchanged documents keep the same `record_id`
* re-converted documents with changed text become new records
* downstream evals can pin exact record ids
* delta exports can skip rows already present in a previous record index

The deleted legacy markdown files were plain `original.pdf.md` outputs from an
older conversion pass. They duplicated deterministic `original.pdf__<hash>.md`
files that include provenance frontmatter. They should not be restored or
published as separate records.

## Full Snapshot Publishing

Full snapshot export is the default and should be used for normal releases:

```bash
uv run python scripts/export_hf_markdown_dataset.py \
  --output-dir storage/huggingface/sunlight-fyi-markdown \
  --force
```

Publish to Hugging Face after choosing the repo id, visibility, and license:

```bash
HF_TOKEN=... uv run python scripts/export_hf_markdown_dataset.py \
  --output-dir storage/huggingface/sunlight-fyi-markdown \
  --repo-id <org>/<dataset> \
  --upload \
  --force
```

For full snapshot uploads, the exporter asks Hugging Face to delete previous
root `data/*.parquet` and root manifest files before uploading the new folder.
That prevents stale shards from surviving when the row count shrinks.

## Delta Publishing

Delta mode is available for append-style updates:

```bash
uv run python scripts/export_hf_markdown_dataset.py \
  --mode delta \
  --previous-index storage/huggingface/sunlight-fyi-markdown/manifests \
  --output-dir storage/huggingface/sunlight-fyi-markdown-delta \
  --force
```

Delta output is written under timestamped folders:

```text
data/deltas/<export-id>/fyi_markdown_delta-00000.parquet
manifests/deltas/<export-id>/record-index.ndjson
manifests/deltas/<export-id>/export-manifest.json
```

Delta mode should be used only when append-only history is useful. Full
snapshots are simpler for consumers and should remain the default until the
dataset grows enough that snapshot replacement becomes expensive.

## Living Dataset Plan

The dataset should be living, but not mutable in place without history. Hugging
Face dataset repos are Git-backed, so repeated uploads to the same dataset repo
preserve update history as commits.

Recommended update loop:

1. Convert new FYI attachments to provenance-rich markdown.
2. Delete or prevent any frontmatterless duplicate markdown outputs.
3. Run the Hugging Face exporter as a full snapshot.
4. Validate row counts, shard count, and zero empty-frontmatter rows.
5. Upload to the same Hugging Face dataset repository.
6. Record the export in `PROGRESS.md` and, when useful, tag a release.

This can later run from a scheduled job after ingestion completes. The scheduled
job should fail closed if validation detects frontmatterless rows, duplicate
record ids, missing required source URLs, or unreadable Parquet shards.

## Validation Gates

Required before publishing:

```bash
uv run python -m unittest tests/test_export_hf_markdown_dataset.py
uv run pre-commit run --files scripts/export_hf_markdown_dataset.py tests/test_export_hf_markdown_dataset.py
uv run python scripts/export_hf_markdown_dataset.py \
  --output-dir storage/huggingface/sunlight-fyi-markdown \
  --force
```

Inspect the generated dataset:

```bash
uv run python - <<'PY'
from pathlib import Path
import json
import pyarrow.parquet as pq

root = Path("storage/huggingface/sunlight-fyi-markdown")
manifest = json.loads((root / "manifests/export-manifest.json").read_text())
total = 0
empty_frontmatter = 0
for path in sorted((root / "data").glob("*.parquet")):
    table = pq.read_table(path, columns=["record_id", "frontmatter_json"])
    total += table.num_rows
    empty_frontmatter += sum(
        1 for row in table.to_pylist() if row["frontmatter_json"] == "{}"
    )
print("manifest_rows", manifest["row_count"])
print("parquet_rows", total)
print("empty_frontmatter_rows", empty_frontmatter)
PY
```

Expected current values:

```text
manifest_rows 9665
parquet_rows 9665
empty_frontmatter_rows 0
```

Run the broader Python suite when exporter logic or dependencies change:

```bash
uv run python -m unittest discover -s tests
```

## Consumer Usage

After publication, consumers should be able to load the dataset with:

```python
from datasets import load_dataset

dataset = load_dataset("<org>/<dataset>", split="train")
```

For reproducible experiments, consumers should pin a Hugging Face revision or
filter by `record_id`, `document_id`, and `text_sha256`.

## Privacy And Responsible Use

The source material is public official-information response material from
FYI.org.nz, but it can contain:

* names and contact details
* official email addresses
* redactions and partial disclosures
* OCR and document-conversion errors
* context-dependent statements from agencies, requesters, or released records

The dataset should preserve source citations and should not claim to be an
official government publication. Users should review the original attachment for
high-stakes claims.

Before public release, choose license wording deliberately. The current generated
dataset card uses `license: other` until the policy is settled.

## Open Decisions

* Hugging Face repo id, for example `<org>/sunlight-fyi-markdown`.
* Public versus private initial visibility.
* Final license text and dataset card wording.
* Whether to publish only markdown or also a second split with chunked retrieval
  rows.
* Whether to add a scheduled CI job, a local cron job, or a manual release
  checklist for living updates.
* Whether future Sunlight-collected disclosures should share this dataset repo
  or use a separate `sunlight-disclosures` dataset.

## References

* Hugging Face dataset cards: https://huggingface.co/docs/hub/datasets-cards
* Hugging Face dataset loading: https://huggingface.co/docs/datasets/loading
* Hugging Face Hub API: https://huggingface.co/docs/huggingface_hub/en/package_reference/hf_api
