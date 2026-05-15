"""Build D1 SQL shards for the public BM25 search sidecar.

The input is FYI markdown with the frontmatter emitted by
parallel_convert_and_embed.py. The chunker intentionally matches the Vectorize
pipeline so chunk IDs can line up when both indexes contain the same document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import fyi_request_metadata
from fyi_markdown import make_chunker, parse_markdown_document


DEFAULT_MARKDOWN_DIR = Path("fyi/markdown")
DEFAULT_FYI_DATA_DIR = Path("fyi/data")
DEFAULT_OUTPUT_DIR = Path("storage/d1_bm25_import")
DEFAULT_DATABASE = "sunlight-search"
DEFAULT_CONFIG = Path("apps/landing/wrangler.jsonc")
DEFAULT_ROWS_PER_FILE = 100
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_CHUNK_OVERLAP = 128
DEFAULT_MAX_CHUNK_TEXT_CHARS = 12000
CONTROL_TRANSLATION = dict.fromkeys(
    codepoint for codepoint in range(32) if codepoint not in (9, 10, 13)
)

COLUMNS = (
    "chunk_id",
    "document_id",
    "source",
    "authority_name",
    "authority_slug",
    "authority_category",
    "request_title",
    "request_url",
    "source_url",
    "original_filename",
    "markdown_r2_key",
    "chunk_index",
    "chunk_text",
    "text_preview",
    "request_year",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export FYI markdown chunks into D1 BM25 SQL shards."
    )
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--fyi-data-dir", type=Path, default=DEFAULT_FYI_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--rows-per-file", type=int, default=DEFAULT_ROWS_PER_FILE)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--max-chunk-text-chars", type=int, default=DEFAULT_MAX_CHUNK_TEXT_CHARS)
    parser.add_argument("--limit", type=int, help="Limit markdown files for a smoke test.")
    parser.add_argument("--reset", action="store_true", help="Clear disclosed_chunks first.")
    parser.add_argument("--apply", action="store_true", help="Apply generated shards with Wrangler.")
    parser.add_argument("--apply-existing", action="store_true", help="Apply existing shards without regenerating.")
    parser.add_argument("--shard", type=int, action="append", help="Specific 1-based shard number to apply.")
    parser.add_argument("--remote", action="store_true", help="Apply to remote D1.")
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)

    if args.apply_existing:
        output_files = sorted(args.output_dir.glob("bm25_*.sql"))
        if args.shard:
            shard_names = {f"bm25_{shard:05d}.sql" for shard in args.shard}
            output_files = [path for path in output_files if path.name in shard_names]
        if not output_files:
            raise SystemExit(f"No bm25_*.sql files found in {args.output_dir}")
        apply_sql_shards(output_files, args.database, args.config, remote=args.remote)
        return 0

    request_index = fyi_request_metadata.load_request_metadata(args.fyi_data_dir)
    rows = iter_chunk_rows(args, request_index)
    output_files, total_rows = write_sql_shards(rows, args.output_dir, args.rows_per_file, args.reset)

    print(f"Wrote {total_rows} chunk rows to {len(output_files)} SQL shard(s).")
    for path in output_files[:10]:
        print(path)
    if len(output_files) > 10:
        print(f"... {len(output_files) - 10} more shard(s)")

    if args.apply:
        apply_sql_shards(output_files, args.database, args.config, remote=args.remote)

    return 0


def validate_args(args: argparse.Namespace) -> None:
    if args.rows_per_file < 1:
        raise SystemExit("--rows-per-file must be at least 1")
    if not args.markdown_dir.exists():
        raise SystemExit(f"Markdown directory not found: {args.markdown_dir}")
    if not args.fyi_data_dir.exists():
        raise SystemExit(f"FYI data directory not found: {args.fyi_data_dir}")


def iter_chunk_rows(args: argparse.Namespace, request_index: dict[int, dict]):
    from llama_index.core import Document

    chunker = make_chunker(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
    paths = sorted(args.markdown_dir.glob("*.md"))
    if args.limit:
        paths = paths[: args.limit]

    for path in paths:
        try:
            raw_text = path.read_text(encoding="utf-8")
            metadata, body = parse_markdown_document(raw_text)
        except Exception:
            continue

        metadata["markdown_path"] = str(path)
        document_id = str(metadata.get("document_id") or "")
        if not document_id or not body.strip():
            continue

        request_metadata = request_metadata_for(metadata, request_index)
        nodes = chunker.run(documents=[Document(text=body, metadata=metadata)])
        for chunk_index, node in enumerate(nodes):
            chunk_text = node_text(node)
            yield build_row(metadata, request_metadata, chunk_index, chunk_text, args.max_chunk_text_chars)


def request_metadata_for(metadata: dict[str, object], request_index: dict[int, dict]) -> dict:
    request_id = as_int(metadata.get("fyi_request_id"))
    if request_id is None:
        return {}
    return request_index.get(request_id, {})


def build_row(
    metadata: dict[str, object],
    request_metadata: dict,
    chunk_index: int,
    chunk_text: str,
    max_chunk_text_chars: int,
) -> dict[str, object]:
    document_id = str(metadata["document_id"])
    indexed_text = collapse_whitespace(chunk_text)[:max_chunk_text_chars]
    return {
        "chunk_id": chunk_id_for_record(document_id, chunk_index, chunk_text),
        "document_id": document_id,
        "source": metadata.get("source") or "fyi",
        "authority_name": request_metadata.get("authority_name"),
        "authority_slug": request_metadata.get("authority_slug"),
        "authority_category": request_metadata.get("authority_category"),
        "request_title": request_metadata.get("request_title"),
        "request_url": metadata.get("request_url"),
        "source_url": metadata.get("source_url"),
        "original_filename": metadata.get("original_filename"),
        "markdown_r2_key": metadata.get("markdown_r2_key"),
        "chunk_index": chunk_index,
        "chunk_text": indexed_text,
        "text_preview": indexed_text[:800],
        "request_year": request_metadata.get("request_year"),
    }


def write_sql_shards(rows, output_dir: Path, rows_per_file: int, reset: bool) -> tuple[list[Path], int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for old_file in output_dir.glob("bm25_*.sql"):
        old_file.unlink()

    output_files: list[Path] = []
    handle = None
    total_rows = 0

    try:
        for row in rows:
            if total_rows % rows_per_file == 0:
                if handle:
                    handle.close()
                path = output_dir / f"bm25_{len(output_files) + 1:05d}.sql"
                handle = path.open("w", encoding="utf-8")
                output_files.append(path)
                if reset and total_rows == 0:
                    handle.write("DELETE FROM disclosed_chunks;\n")

            handle.write(upsert_statement(row))
            total_rows += 1
    finally:
        if handle:
            handle.close()

    return output_files, total_rows


def upsert_statement(row: dict[str, object]) -> str:
    values = ", ".join(sql_literal(row[column]) for column in COLUMNS)
    assignments = ",\n  ".join(
        f"{column} = excluded.{column}" for column in COLUMNS if column != "chunk_id"
    )
    return f"""
INSERT INTO disclosed_chunks ({", ".join(COLUMNS)})
VALUES ({values})
ON CONFLICT(chunk_id) DO UPDATE SET
  {assignments};
"""


def apply_sql_shards(paths: list[Path], database: str, config: Path, *, remote: bool) -> None:
    for index, path in enumerate(paths, start=1):
        print(f"Applying {index}/{len(paths)}: {path}", flush=True)
        command = [
            "pnpm",
            "dlx",
            "wrangler@latest",
            "d1",
            "execute",
            database,
            "--file",
            str(path),
            "--config",
            str(config),
            "-y",
        ]
        if remote:
            command.append("--remote")
        subprocess.run(command, check=True)


def chunk_id_for_record(document_id: str, chunk_index: int, chunk_text: str) -> str:
    text_digest = hashlib.sha1(chunk_text.encode("utf-8")).hexdigest()[:12]
    return f"chunk_{document_id}_{chunk_index:04d}_{text_digest}"


def node_text(node) -> str:
    text = getattr(node, "text", None)
    if text is not None:
        return text

    get_content = getattr(node, "get_content", None)
    if callable(get_content):
        return get_content()

    raise ValueError("Node does not expose text content")


def collapse_whitespace(value: str) -> str:
    return " ".join(value.translate(CONTROL_TRANSLATION).split())


def as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int | float):
        return str(value)
    text = str(value).translate(CONTROL_TRANSLATION).replace("'", "''")
    return f"'{text}'"


if __name__ == "__main__":
    raise SystemExit(main())
