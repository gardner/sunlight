# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "lancedb",
#   "pylance",
# ]
# ///

from __future__ import annotations

import argparse
import json
from pathlib import Path

import lancedb


DEFAULT_PERSIST_DIR = Path("./storage/fyi_parallel.lancedb")
DEFAULT_TABLE_NAME = "chunks"
DEFAULT_OUTPUT_DIR = Path("./storage/vectorize_export")
DEFAULT_ROWS_PER_FILE = 5000
DEFAULT_BATCH_SIZE = 1024


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Stream LanceDB chunk vectors into Cloudflare Vectorize NDJSON files "
            "without materializing the whole table in memory."
        )
    )
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rows-per-file", type=int, default=DEFAULT_ROWS_PER_FILE)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser


def clean_metadata(row: dict[str, object]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in (
        "document_id",
        "chunk_id",
        "chunk_index",
        "source",
        "source_url",
        "request_url",
        "fyi_request_id",
        "fyi_response_id",
        "fyi_attachment_id",
        "original_filename",
        "pdf_r2_key",
        "markdown_r2_key",
        "embedding_model",
        "text_preview",
    ):
        value = row.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = str(value)
    return metadata


def open_output_file(output_dir: Path, file_index: int):
    output_path = output_dir / f"fyi_vectors_{file_index:05d}.ndjson"
    handle = output_path.open("w", encoding="utf-8")
    return output_path, handle


def validate_args(args) -> None:
    if args.rows_per_file < 1:
        raise SystemExit("--rows-per-file must be at least 1")
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be at least 1")
    if not args.persist_dir.exists():
        raise SystemExit(f"LanceDB directory not found: {args.persist_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)


def open_chunks_table(persist_dir: Path, table_name: str):
    db = lancedb.connect(str(persist_dir))
    listed = db.list_tables()
    raw_names = listed.tables if hasattr(listed, "tables") else listed
    table_names = set(raw_names)
    if table_name not in table_names:
        raise SystemExit(
            f"LanceDB table {table_name!r} not found in {persist_dir}. "
            f"Available tables: {sorted(table_names)}"
        )

    return db.open_table(table_name)


def iter_rows(table, batch_size: int):
    dataset = table.to_lance()
    scanner = dataset.scanner(
        columns=[
            "chunk_id",
            "vector",
            "document_id",
            "chunk_index",
            "source",
            "source_url",
            "request_url",
            "fyi_request_id",
            "fyi_response_id",
            "fyi_attachment_id",
            "original_filename",
            "pdf_r2_key",
            "markdown_r2_key",
            "embedding_model",
            "text_preview",
        ],
        batch_size=batch_size,
    )
    reader = scanner.to_reader()

    while True:
        try:
            batch = reader.read_next_batch()
        except StopIteration:
            return

        yield from batch.to_pylist()


def export_rows(rows, output_dir: Path, rows_per_file: int) -> tuple[int, list[Path]]:
    total_rows = 0
    file_index = 1
    rows_in_file = 0
    output_path, handle = open_output_file(output_dir, file_index)
    output_files = [output_path]

    try:
        for row in rows:
            vectorize_row = {
                "id": row["chunk_id"],
                "values": row["vector"],
                "metadata": clean_metadata(row),
            }
            handle.write(json.dumps(vectorize_row) + "\n")
            total_rows += 1
            rows_in_file += 1

            if rows_in_file >= rows_per_file:
                handle.close()
                file_index += 1
                rows_in_file = 0
                output_path, handle = open_output_file(output_dir, file_index)
                output_files.append(output_path)
    finally:
        handle.close()

    if output_files and output_files[-1].stat().st_size == 0:
        output_files[-1].unlink()
        output_files.pop()

    return total_rows, output_files


def main() -> None:
    args = build_parser().parse_args()
    validate_args(args)

    table = open_chunks_table(args.persist_dir, args.table_name)
    total_rows, output_files = export_rows(
        iter_rows(table, args.batch_size),
        args.output_dir,
        args.rows_per_file,
    )

    print(f"Exported {total_rows} vectors into {len(output_files)} NDJSON file(s).")
    for path in output_files:
        print(path)

    print("\nNext step when ready:")
    print("1. Ensure your CLOUDFLARE_API_TOKEN has 'Vectorize: Edit' permissions.")
    print("2. Create the index: wrangler vectorize create fyi_index --dimensions=1024 --metric=cosine")
    for path in output_files:
        print(f"3. Upload: wrangler vectorize insert fyi_index --file={path}")


if __name__ == "__main__":
    main()
