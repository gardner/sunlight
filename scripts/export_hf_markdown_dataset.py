"""Export converted FYI markdown as a Hugging Face dataset folder."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import fyi_request_metadata
from fyi_markdown import parse_markdown_document


DEFAULT_MARKDOWN_DIR = Path("fyi/markdown")
DEFAULT_FYI_DATA_DIR = Path("fyi/data")
DEFAULT_OUTPUT_DIR = Path("storage/huggingface/sunlight-fyi-markdown")
DEFAULT_ROWS_PER_SHARD = 1000
DEFAULT_CORPUS_VERSION = "fyi-v1"
DATASET_PRETTY_NAME = "Sunlight FYI Markdown Corpus"


DATASET_COLUMNS = (
    "record_id",
    "source",
    "corpus_version",
    "document_id",
    "fyi_request_id",
    "fyi_response_id",
    "fyi_attachment_id",
    "authority_name",
    "authority_slug",
    "authority_category",
    "law_used",
    "described_state",
    "request_year",
    "request_created_at",
    "request_title",
    "request_url",
    "source_url",
    "original_filename",
    "markdown_r2_key",
    "pdf_r2_key",
    "markdown_filename",
    "markdown_content",
    "frontmatter_json",
    "text_sha256",
    "content_chars",
    "exported_at",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a Hugging Face dataset folder from FYI markdown."
    )
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--fyi-data-dir", type=Path, default=DEFAULT_FYI_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rows-per-shard", type=int, default=DEFAULT_ROWS_PER_SHARD)
    parser.add_argument("--corpus-version", default=DEFAULT_CORPUS_VERSION)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("full", "delta"),
        default="full",
        help="Use delta with --previous-index to export only new or changed records.",
    )
    parser.add_argument("--previous-index", type=Path)
    parser.add_argument("--repo-id", help="Optional Hugging Face dataset repo id.")
    parser.add_argument(
        "--private",
        action="store_true",
        help="Create repo as private when uploading.",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload output folder to Hugging Face.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)

    exported_at = utc_now_iso()
    export_id = export_id_for(exported_at)
    request_index = fyi_request_metadata.load_request_metadata(args.fyi_data_dir)
    previous_records = read_previous_record_ids(args.previous_index)
    rows = list(iter_dataset_rows(args, request_index, exported_at, previous_records))

    prepare_output_dir(args.output_dir, args.force)
    data_dir, manifest_dir, shard_prefix = export_paths(
        args.output_dir,
        args.mode,
        export_id,
    )
    shards = write_parquet_shards(
        rows,
        data_dir,
        args.rows_per_shard,
        shard_prefix,
        args.output_dir,
    )
    write_record_index(rows, manifest_dir / "record-index.ndjson")
    write_dataset_card(args.output_dir / "README.md", args, len(rows), exported_at)
    write_manifest(manifest_dir / "export-manifest.json", args, rows, shards, exported_at)

    print(f"Wrote {len(rows)} rows to {args.output_dir}")
    for shard in shards[:10]:
        print(shard["path"])
    if len(shards) > 10:
        print(f"... {len(shards) - 10} more shard(s)")

    if args.upload:
        upload_to_hugging_face(
            args.output_dir,
            args.repo_id,
            mode=args.mode,
            private=args.private,
        )

    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.rows_per_shard < 1:
        raise SystemExit("--rows-per-shard must be at least 1")
    if not args.markdown_dir.exists():
        raise SystemExit(f"Markdown directory not found: {args.markdown_dir}")
    if not args.fyi_data_dir.exists():
        raise SystemExit(f"FYI data directory not found: {args.fyi_data_dir}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()) and not args.force:
        raise SystemExit(
            f"Output directory exists and is not empty: {args.output_dir}"
        )
    if args.mode == "delta" and not args.previous_index:
        raise SystemExit("--mode delta requires --previous-index")
    if args.previous_index and not args.previous_index.exists():
        raise SystemExit(f"Previous index not found: {args.previous_index}")
    if args.upload and not args.repo_id:
        raise SystemExit("--upload requires --repo-id")


def iter_dataset_rows(
    args: argparse.Namespace,
    request_index: dict[int, dict],
    exported_at: str,
    previous_records: set[str],
):
    count = 0
    for path in sorted(args.markdown_dir.glob("*.md")):
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        try:
            metadata, body = parse_markdown_document(raw_text)
        except Exception:
            metadata, body = {}, raw_text
        if not body.strip():
            continue

        request_id = as_int(metadata.get("fyi_request_id"))
        request_metadata = (
            request_index.get(request_id, {}) if request_id is not None else {}
        )
        row = build_row(
            path,
            metadata,
            request_metadata,
            body,
            args.corpus_version,
            exported_at,
        )
        if row["record_id"] in previous_records:
            continue

        yield row
        count += 1
        if args.limit and count >= args.limit:
            return


def build_row(
    path: Path,
    metadata: dict[str, object],
    request_metadata: dict,
    body: str,
    corpus_version: str,
    exported_at: str,
) -> dict[str, Any]:
    document_id = as_string(metadata.get("document_id")) or stable_document_id(path)
    text_sha256 = sha256_text(body)
    record_id = sha256_text(f"{document_id}\n{text_sha256}")[:32]
    return {
        "authority_category": request_metadata.get("authority_category"),
        "authority_name": request_metadata.get("authority_name"),
        "authority_slug": request_metadata.get("authority_slug"),
        "content_chars": len(body),
        "corpus_version": corpus_version,
        "described_state": request_metadata.get("described_state"),
        "document_id": document_id,
        "exported_at": exported_at,
        "frontmatter_json": json.dumps(metadata, ensure_ascii=False, sort_keys=True),
        "fyi_attachment_id": as_int(metadata.get("fyi_attachment_id")),
        "fyi_request_id": as_int(metadata.get("fyi_request_id")),
        "fyi_response_id": as_int(metadata.get("fyi_response_id")),
        "law_used": request_metadata.get("law_used"),
        "markdown_content": body,
        "markdown_filename": path.name,
        "markdown_r2_key": as_string(metadata.get("markdown_r2_key")),
        "original_filename": as_string(metadata.get("original_filename")),
        "pdf_r2_key": as_string(metadata.get("pdf_r2_key")),
        "record_id": record_id,
        "request_created_at": request_metadata.get("request_created_at"),
        "request_title": request_metadata.get("request_title"),
        "request_url": as_string(metadata.get("request_url")),
        "request_year": request_metadata.get("request_year"),
        "source": as_string(metadata.get("source")) or "fyi",
        "source_url": as_string(metadata.get("source_url")),
        "text_sha256": text_sha256,
    }


def prepare_output_dir(path: Path, force: bool) -> None:
    if path.exists() and force:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    (path / "data").mkdir(parents=True, exist_ok=True)
    (path / "manifests").mkdir(parents=True, exist_ok=True)


def export_paths(output_dir: Path, mode: str, export_id: str) -> tuple[Path, Path, str]:
    if mode == "delta":
        return (
            output_dir / "data" / "deltas" / export_id,
            output_dir / "manifests" / "deltas" / export_id,
            "fyi_markdown_delta",
        )
    return output_dir / "data", output_dir / "manifests", "fyi_markdown"


def write_parquet_shards(
    rows: list[dict[str, Any]],
    data_dir: Path,
    rows_per_shard: int,
    shard_prefix: str = "fyi_markdown",
    output_dir: Path | None = None,
) -> list[dict[str, Any]]:
    import pyarrow as pa
    import pyarrow.parquet as pq

    data_dir.mkdir(parents=True, exist_ok=True)
    shards = []
    for shard_index, start in enumerate(range(0, len(rows), rows_per_shard)):
        shard_rows = rows[start : start + rows_per_shard]
        path = data_dir / f"{shard_prefix}-{shard_index:05d}.parquet"
        table = pa.Table.from_pylist(
            [normalize_row(row) for row in shard_rows],
            schema=dataset_schema(),
        )
        pq.write_table(table, path, compression="zstd")
        shards.append(shard_info(path, shard_rows, output_dir))
    return shards


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {column: row.get(column) for column in DATASET_COLUMNS}


def dataset_schema():
    import pyarrow as pa

    int_columns = {
        "content_chars",
        "fyi_attachment_id",
        "fyi_request_id",
        "fyi_response_id",
        "request_year",
    }
    fields = []
    for column in DATASET_COLUMNS:
        field_type = pa.int64() if column in int_columns else pa.string()
        fields.append(pa.field(column, field_type))
    return pa.schema(fields)


def write_record_index(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            item = {
                "document_id": row["document_id"],
                "record_id": row["record_id"],
                "request_url": row["request_url"],
                "source_url": row["source_url"],
                "text_sha256": row["text_sha256"],
            }
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def write_manifest(
    path: Path,
    args: argparse.Namespace,
    rows: list[dict[str, Any]],
    shards: list[dict[str, Any]],
    exported_at: str,
) -> None:
    manifest = {
        "columns": list(DATASET_COLUMNS),
        "corpus_version": args.corpus_version,
        "exported_at": exported_at,
        "mode": args.mode,
        "previous_index": str(args.previous_index) if args.previous_index else None,
        "row_count": len(rows),
        "shards": shards,
        "source": "fyi",
    }
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_dataset_card(path: Path, args: argparse.Namespace, row_count: int, exported_at: str) -> None:
    repo_hint = args.repo_id or "your-org/sunlight-fyi-markdown"
    card = f"""---
license: other
language:
- en
- mi
pretty_name: {DATASET_PRETTY_NAME}
tags:
- new-zealand
- official-information
- public-records
- markdown
- rag
task_categories:
- text-retrieval
- question-answering
---

# {DATASET_PRETTY_NAME}

This dataset contains Markdown converted from public FYI.org.nz official
information release attachments, with citation and request metadata preserved in
columns. It is prepared by the Sunlight project for search, retrieval, and RAG
evaluation work.

## Contents

Rows in this export: `{row_count}`

Exported at: `{exported_at}`

Each row contains:

- `markdown_content`: converted Markdown body text
- `document_id`: stable Sunlight document id
- `record_id`: content-addressed row id based on `document_id` and text hash
- `request_url` and `source_url`: source citation URLs on FYI.org.nz
- FYI identifiers: request, response, and attachment ids
- authority metadata when available
- original filename and planned R2 keys
- `frontmatter_json`: original Markdown frontmatter from the conversion pipeline

Older Markdown files that predate provenance frontmatter are still included.
Those rows use a stable path-derived `document_id` and an empty
`frontmatter_json` object.

## Living Dataset Updates

This dataset is designed to be updated over time. Re-run the exporter after new
public markdown files are added, then upload the prepared folder to the same
Hugging Face dataset repository. Hugging Face dataset repositories are versioned,
so each update is preserved as a commit.

Full snapshot export:

```bash
uv run python scripts/export_hf_markdown_dataset.py \\
  --output-dir storage/huggingface/sunlight-fyi-markdown \\
  --force
```

Upload:

```bash
HF_TOKEN=... uv run python scripts/export_hf_markdown_dataset.py \\
  --output-dir storage/huggingface/sunlight-fyi-markdown \\
  --repo-id {repo_hint} \\
  --upload \\
  --force
```

Delta exports can use `--mode delta --previous-index <record-index.ndjson>` to
write only records whose `record_id` was not present in an earlier export. The
`--previous-index` argument may also point at a downloaded `manifests/` directory;
all `*record-index.ndjson` files below it will be used for the skip set.

## Intended Use

- public-record search
- retrieval and reranking experiments
- grounded answer generation tests
- transparency and accountability research

## Limitations and Responsible Use

The source material is public official-information response material, but it can
include names, email addresses, redactions, OCR/conversion errors, and statements
that are context-dependent. Users should cite the source URLs, review original
attachments for important claims, and avoid treating this dataset as an official
government publication.
"""
    path.write_text(card, encoding="utf-8")


def upload_to_hugging_face(output_dir: Path, repo_id: str | None, *, mode: str, private: bool) -> None:
    from huggingface_hub import HfApi

    if not repo_id:
        raise SystemExit("--repo-id is required for upload")
    delete_patterns = None
    if mode == "full":
        delete_patterns = [
            "data/*.parquet",
            "data/deltas/**",
            "manifests/*.json",
            "manifests/*.ndjson",
            "manifests/deltas/**",
        ]
    api = HfApi()
    api.create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    api.upload_folder(
        folder_path=str(output_dir),
        repo_id=repo_id,
        repo_type="dataset",
        commit_message="Update Sunlight FYI markdown dataset",
        delete_patterns=delete_patterns,
    )


def read_previous_record_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    paths = sorted(path.rglob("*record-index.ndjson")) if path.is_dir() else [path]
    records = set()
    for index_path in paths:
        for line in index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                record_id = item.get("record_id")
                if isinstance(record_id, str):
                    records.add(record_id)
    return records


def shard_info(path: Path, rows: list[dict[str, Any]], output_dir: Path | None = None) -> dict[str, Any]:
    display_path = path
    if output_dir:
        try:
            display_path = path.relative_to(output_dir)
        except ValueError:
            pass
    return {
        "bytes": path.stat().st_size,
        "path": display_path.as_posix(),
        "rows": len(rows),
        "sha256": sha256_file(path),
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_document_id(path: Path) -> str:
    return f"doc_local_{sha256_text(path.as_posix())[:16]}"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def export_id_for(exported_at: str) -> str:
    return exported_at.replace("-", "").replace(":", "").replace("T", "-").removesuffix("Z")


def as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def as_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
