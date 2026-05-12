# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
#   "llama-index-core",
#   "llama-index-embeddings-huggingface",
#   "lancedb",
#   "docling",
# ]
#
# [tool.uv]
# index-strategy = "unsafe-best-match"
#
# [[tool.uv.index]]
# name = "pytorch-cu130"
# url = "https://download.pytorch.org/whl/cu130"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cu130" }
# ///

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import multiprocessing as mp
import queue
import re
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, unquote

from fyi_lancedb_writer import LanceDBChunkWriter


DEFAULT_DATA_DIR = Path("/mnt/dgx-ssd/src/sunlight_nz/fyi/data/request")
DEFAULT_MARKDOWN_DIR = Path("/mnt/dgx-ssd/src/sunlight_nz/fyi/markdown")
DEFAULT_PERSIST_DIR = Path("./storage/fyi_parallel.lancedb")
DEFAULT_TABLE_NAME = "chunks"
DEFAULT_CONVERT_WORKERS = 3
DEFAULT_EMBED_BATCH_SIZE = 50
DEFAULT_MARKDOWN_QUEUE_SIZE = 32
DEFAULT_MAX_TASKS_PER_WORKER = 25
DEFAULT_CHUNK_SIZE = 1024
DEFAULT_CHUNK_OVERLAP = 128
DEFAULT_MODEL_EMBED_BATCH_SIZE = 4

_cached_converter = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert FYI PDFs to Markdown with Docling workers while one "
            "embedding worker consumes completed Markdown in bounded batches "
            "and streams chunk vectors into LanceDB."
        )
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--convert-workers", type=int, default=DEFAULT_CONVERT_WORKERS)
    parser.add_argument("--embed-batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    parser.add_argument("--markdown-queue-size", type=int, default=DEFAULT_MARKDOWN_QUEUE_SIZE)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--model-embed-batch-size", type=int, default=DEFAULT_MODEL_EMBED_BATCH_SIZE)
    parser.add_argument(
        "--max-tasks-per-worker",
        type=int,
        default=DEFAULT_MAX_TASKS_PER_WORKER,
        help="Recycle each Docling worker after this many PDFs. Use 0 to disable.",
    )
    return parser


def stable_path_digest(path: Path, length: int = 12) -> str:
    return hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:length]


def sanitize_markdown_filename(filename: str) -> str:
    return unquote(filename).replace(" ", "_").replace("%20", "_")


def sanitize_r2_filename(filename: str) -> str:
    normalized = unquote(filename).strip().lower()
    safe_name = re.sub(r"[^a-z0-9.]+", "-", normalized).strip("-")
    return safe_name or "document"


def safe_markdown_path(pdf_path: Path, out_dir: Path) -> Path:
    safe_name = sanitize_markdown_filename(pdf_path.name)
    digest = stable_path_digest(pdf_path)
    return out_dir / f"{safe_name}__{digest}.md"


def embedded_marker_path(markdown_path: Path) -> Path:
    return Path(str(markdown_path) + ".embedded")


def failed_marker_path(markdown_path: Path) -> Path:
    return Path(str(markdown_path) + ".failed")


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_fyi_identifiers(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    parts = list(path.parts)

    for key in ("request", "response", "attach"):
        if key not in parts:
            continue
        key_index = parts.index(key)
        if key_index + 1 >= len(parts):
            continue
        raw_value = parts[key_index + 1]
        if raw_value.isdigit():
            metadata_key = "fyi_attachment_id" if key == "attach" else f"fyi_{key}_id"
            values[metadata_key] = int(raw_value)

    return values


def build_document_id(source: str, path_digest: str, identifiers: dict[str, int]) -> str:
    if source == "fyi" and identifiers.get("fyi_request_id"):
        request_id = identifiers["fyi_request_id"]
        response_id = identifiers.get("fyi_response_id", 0)
        attachment_id = identifiers.get("fyi_attachment_id", 0)
        return f"doc_fyi_{request_id}_{response_id}_{attachment_id}_{path_digest}"
    return f"doc_local_{path_digest}"


def build_r2_keys(
    document_id: str,
    original_filename: str,
    identifiers: dict[str, int],
) -> tuple[str | None, str | None]:
    request_id = identifiers.get("fyi_request_id")
    response_id = identifiers.get("fyi_response_id")
    attachment_id = identifiers.get("fyi_attachment_id")
    if request_id is None or response_id is None or attachment_id is None:
        return None, None

    digest = document_id.rsplit("_", 1)[-1]
    pdf_r2_key = (
        "canonical/fyi/v1/pdf/"
        f"request/{request_id}/response/{response_id}/attach/{attachment_id}/"
        f"{digest}-{sanitize_r2_filename(original_filename)}"
    )
    markdown_r2_key = (
        "markdown/fyi/v1/"
        f"request/{request_id}/response/{response_id}/attach/{attachment_id}/{document_id}.md"
    )
    return pdf_r2_key, markdown_r2_key


def build_document_metadata(pdf_path: Path, markdown_path: Path) -> dict[str, object]:
    identifiers = parse_fyi_identifiers(pdf_path)
    source = "fyi" if "fyi_request_id" in identifiers else "local"
    original_filename = unquote(pdf_path.name)
    path_digest = stable_path_digest(pdf_path)
    document_id = build_document_id(source, path_digest, identifiers)
    pdf_r2_key, markdown_r2_key = build_r2_keys(document_id, original_filename, identifiers)

    metadata: dict[str, object] = {
        "document_id": document_id,
        "source": source,
        "original_filename": original_filename,
    }
    metadata.update(identifiers)

    request_id = identifiers.get("fyi_request_id")
    response_id = identifiers.get("fyi_response_id")
    attachment_id = identifiers.get("fyi_attachment_id")

    if request_id is not None:
        metadata["request_url"] = f"https://fyi.org.nz/request/{request_id}"

    if request_id is not None and response_id is not None and attachment_id is not None:
        encoded_name = quote(unquote(pdf_path.name), safe="")
        metadata["source_url"] = (
            f"https://fyi.org.nz/request/{request_id}/response/{response_id}/"
            f"attach/{attachment_id}/{encoded_name}"
        )

    if pdf_r2_key is not None:
        metadata["pdf_r2_key"] = pdf_r2_key
    if markdown_r2_key is not None:
        metadata["markdown_r2_key"] = markdown_r2_key

    return metadata


def render_markdown_document(metadata: dict[str, object], body: str) -> str:
    lines = ["---"]
    for key in sorted(metadata):
        value = metadata[key]
        if value is None:
            continue
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=True)}")
    lines.extend(["---", "", body])
    return "\n".join(lines)


def parse_markdown_document(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith("---\n"):
        return {}, text

    end_index = text.find("\n---\n", 4)
    if end_index == -1:
        return {}, text

    raw_metadata = text[4:end_index]
    body = text[end_index + len("\n---\n") :]
    if body.startswith("\n"):
        body = body[1:]
    metadata: dict[str, object] = {}

    for line in raw_metadata.splitlines():
        if not line.strip():
            continue
        key, separator, raw_value = line.partition(":")
        if not separator:
            return {}, text
        metadata[key.strip()] = json.loads(raw_value.strip())

    return metadata, body


def fallback_markdown_metadata(markdown_path: Path) -> dict[str, object]:
    digest = stable_path_digest(markdown_path)
    return {
        "document_id": f"doc_markdown_{digest}",
        "source": "local",
        "original_filename": markdown_path.name,
    }


def get_converter():
    global _cached_converter
    if _cached_converter is None:
        import torch
        from docling.document_converter import DocumentConverter

        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True

        _cached_converter = DocumentConverter()
    return _cached_converter


def convert_pdf_to_md(pdf_path: Path, out_dir: Path) -> tuple[bool, Path, Path | str | None]:
    md_file_path = safe_markdown_path(pdf_path, out_dir)
    failed_file = failed_marker_path(md_file_path)

    if md_file_path.exists():
        return True, pdf_path, md_file_path

    if failed_file.exists():
        return False, pdf_path, "Skipped due to previous critical failure (.failed lock exists)"

    failed_file.touch()

    try:
        converter = get_converter()
        result = converter.convert(str(pdf_path))
        body = result.document.export_to_markdown()
        metadata = build_document_metadata(pdf_path, md_file_path)

        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(render_markdown_document(metadata, body))

        failed_file.unlink(missing_ok=True)
        return True, pdf_path, md_file_path
    except Exception as exc:
        return False, pdf_path, str(exc)


def put_markdown_for_embedding(
    markdown_queue: mp.Queue,
    markdown_path: Path,
    consumer_process: mp.Process | None = None,
) -> bool:
    if embedded_marker_path(markdown_path).exists():
        return False

    while True:
        if consumer_process is not None and not consumer_process.is_alive():
            raise RuntimeError("Embedding worker exited before Markdown could be queued")

        try:
            markdown_queue.put(str(markdown_path), timeout=5)
            return True
        except queue.Full:
            continue


def release_embedding_memory() -> None:
    gc.collect()
    try:
        import torch
    except ImportError:
        return

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def node_text(node) -> str:
    text = getattr(node, "text", None)
    if text is not None:
        return text

    get_content = getattr(node, "get_content", None)
    if callable(get_content):
        return get_content()

    raise ValueError("Node does not expose text content")


def chunk_id_for_record(document_id: str, chunk_index: int, chunk_text: str) -> str:
    text_digest = hashlib.sha1(chunk_text.encode("utf-8")).hexdigest()[:12]
    return f"chunk_{document_id}_{chunk_index:04d}_{text_digest}"


def build_chunk_records(nodes, markdown_paths: list[Path], embedding_model_name: str) -> list[dict[str, object]]:
    chunk_counts: dict[str, int] = {}
    records: list[dict[str, object]] = []
    created_at = utc_now_iso()

    for node in nodes:
        metadata = dict(getattr(node, "metadata", {}) or {})
        chunk_text = node_text(node)
        document_id = str(metadata.get("document_id") or f"doc_markdown_{stable_path_digest(Path(markdown_paths[0]))}")
        chunk_index = chunk_counts.get(document_id, 0)
        chunk_counts[document_id] = chunk_index + 1

        records.append(
            {
                "chunk_id": chunk_id_for_record(document_id, chunk_index, chunk_text),
                "document_id": document_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "text_preview": chunk_text[:500],
                "source": metadata.get("source"),
                "source_url": metadata.get("source_url"),
                "request_url": metadata.get("request_url"),
                "fyi_request_id": metadata.get("fyi_request_id"),
                "fyi_response_id": metadata.get("fyi_response_id"),
                "fyi_attachment_id": metadata.get("fyi_attachment_id"),
                "original_filename": metadata.get("original_filename"),
                "pdf_r2_key": metadata.get("pdf_r2_key"),
                "markdown_r2_key": metadata.get("markdown_r2_key"),
                "markdown_path": metadata.get("markdown_path"),
                "embedding_model": embedding_model_name,
                "text_sha256": hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                "created_at": created_at,
                "vectorize_uploaded_at": None,
            }
        )

    return records


def flush_embedding_batch(
    batch: list[Path],
    parser,
    embed_model,
    writer: LanceDBChunkWriter,
    document_class,
    embedding_model_name: str,
) -> None:
    if not batch:
        return

    documents = []
    embedded_paths = []

    for md_path in batch:
        if embedded_marker_path(md_path).exists():
            continue

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            metadata, body = parse_markdown_document(raw_text)
            if not metadata:
                metadata = fallback_markdown_metadata(md_path)
            metadata["markdown_path"] = str(md_path)
            documents.append(document_class(text=body, metadata=metadata))
            embedded_paths.append(md_path)
        except Exception as exc:
            print(f"Error reading {md_path}: {exc}", flush=True)

    if not documents:
        return

    nodes = parser.get_nodes_from_documents(documents)
    print(f"Embedding {len(nodes)} nodes from {len(embedded_paths)} markdown files...", flush=True)

    texts = [node_text(node) for node in nodes]
    embeddings = embed_model.get_text_embedding_batch(texts, show_progress=True)
    records = build_chunk_records(nodes, embedded_paths, embedding_model_name)

    for record, embedding in zip(records, embeddings, strict=True):
        record["vector"] = embedding

    print(f"Persisting embedded batch to {writer.persist_dir}...", flush=True)
    writer.add_records(records)

    for md_path in embedded_paths:
        embedded_marker_path(md_path).touch()

    release_embedding_memory()


def embedding_worker(
    markdown_queue: mp.Queue,
    persist_dir: Path,
    embed_batch_size: int,
    chunk_size: int,
    chunk_overlap: int,
    model_embed_batch_size: int,
) -> None:
    import torch
    from llama_index.core import Document
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    embedding_model_name = "Qwen/Qwen3-Embedding-0.6B"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Embedding worker loading Qwen model on {device}...", flush=True)

    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True

    embed_model = HuggingFaceEmbedding(
        model_name=embedding_model_name,
        device=device,
        max_length=chunk_size,
        embed_batch_size=model_embed_batch_size,
        model_kwargs={"torch_dtype": torch.float16},
    )
    parser = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    writer = LanceDBChunkWriter(persist_dir)

    batch: list[Path] = []
    started = time.time()

    while True:
        try:
            item = markdown_queue.get(timeout=5)
        except queue.Empty:
            flush_embedding_batch(
                batch,
                parser,
                embed_model,
                writer,
                Document,
                embedding_model_name,
            )
            batch.clear()
            continue

        if item is None:
            break

        batch.append(Path(item))
        if len(batch) >= embed_batch_size:
            flush_embedding_batch(
                batch,
                parser,
                embed_model,
                writer,
                Document,
                embedding_model_name,
            )
            batch.clear()

    flush_embedding_batch(batch, parser, embed_model, writer, Document, embedding_model_name)
    print(f"Embedding worker complete in {time.time() - started:.2f}s.", flush=True)


def run_conversion_pool(
    pdf_files: list[Path],
    md_out_dir: Path,
    markdown_queue: mp.Queue,
    embed_process: mp.Process,
    convert_workers: int,
    max_tasks_per_worker: int,
) -> None:
    max_tasks = max_tasks_per_worker or None
    max_pending = max(convert_workers * 2, 1)
    submitted = 0
    completed = 0
    successful = 0
    failed = 0
    queued_for_embedding = 0
    pending = set()

    with ProcessPoolExecutor(
        max_workers=convert_workers,
        max_tasks_per_child=max_tasks,
    ) as executor:
        while submitted < len(pdf_files) and len(pending) < max_pending:
            pending.add(executor.submit(convert_pdf_to_md, pdf_files[submitted], md_out_dir))
            submitted += 1

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)

            for future in done:
                success, path, result_data = future.result()
                completed += 1

                if success:
                    successful += 1
                    if isinstance(result_data, Path) and put_markdown_for_embedding(
                        markdown_queue,
                        result_data,
                        embed_process,
                    ):
                        queued_for_embedding += 1
                    print(f"[{completed}/{len(pdf_files)}] Converted: {path.name}", flush=True)
                else:
                    failed += 1
                    print(f"[{completed}/{len(pdf_files)}] Failed: {path.name} - Error: {result_data}", flush=True)

                while submitted < len(pdf_files) and len(pending) < max_pending:
                    pending.add(executor.submit(convert_pdf_to_md, pdf_files[submitted], md_out_dir))
                    submitted += 1

    print(
        "Conversion phase complete: "
        f"{successful} successful, {failed} failed, {queued_for_embedding} queued for embedding.",
        flush=True,
    )


def main() -> None:
    args = build_parser().parse_args()

    if args.convert_workers < 1:
        raise SystemExit("--convert-workers must be at least 1")
    if args.embed_batch_size < 1:
        raise SystemExit("--embed-batch-size must be at least 1")
    if args.markdown_queue_size < 1:
        raise SystemExit("--markdown-queue-size must be at least 1")
    if args.chunk_size < 1:
        raise SystemExit("--chunk-size must be at least 1")
    if args.chunk_overlap < 0:
        raise SystemExit("--chunk-overlap must be at least 0")
    if args.chunk_overlap >= args.chunk_size:
        raise SystemExit("--chunk-overlap must be smaller than --chunk-size")
    if args.model_embed_batch_size < 1:
        raise SystemExit("--model-embed-batch-size must be at least 1")

    mp.set_start_method("spawn", force=True)

    args.markdown_dir.mkdir(parents=True, exist_ok=True)
    args.persist_dir.mkdir(parents=True, exist_ok=True)

    print(f"Finding PDF files in {args.data_dir}...", flush=True)
    pdf_files = list(args.data_dir.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files.", flush=True)

    markdown_queue = mp.Queue(maxsize=args.markdown_queue_size)
    embed_process = mp.Process(
        target=embedding_worker,
        args=(
            markdown_queue,
            args.persist_dir,
            args.embed_batch_size,
            args.chunk_size,
            args.chunk_overlap,
            args.model_embed_batch_size,
        ),
        name="fyi-embedding-worker",
    )
    embed_process.start()

    start_conversion = time.time()
    try:
        run_conversion_pool(
            pdf_files,
            args.markdown_dir,
            markdown_queue,
            embed_process,
            args.convert_workers,
            args.max_tasks_per_worker,
        )
    finally:
        if embed_process.is_alive():
            markdown_queue.put(None)
        embed_process.join()

    if embed_process.exitcode:
        raise SystemExit(f"Embedding worker failed with exit code {embed_process.exitcode}")

    print(f"Full pipeline complete in {time.time() - start_conversion:.2f}s.", flush=True)


if __name__ == "__main__":
    main()
