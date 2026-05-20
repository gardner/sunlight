# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
#   "llama-index-core",
#   "llama-index-embeddings-huggingface",
#   "lancedb",
#   "docling",
#   "flash-attn",
#   "pymupdf",
# ]
#
# [tool.uv]
# index-strategy = "unsafe-best-match"
# no-build-isolation-package = ["flash-attn"]
#
# [[tool.uv.index]]
# name = "pytorch-cu130"
# url = "https://download.pytorch.org/whl/cu130"
# explicit = true
#
# [tool.uv.sources]
# torch = { index = "pytorch-cu130" }
# flash-attn = { url = "https://github.com/mjun0812/flash-attention-prebuild-wheels/releases/download/v0.9.4/flash_attn-2.8.3+cu130torch2.11-cp313-cp313-linux_x86_64.whl" }
# ///

from __future__ import annotations

import argparse
import gc
import hashlib
import multiprocessing as mp
import os
import queue
import re
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote, unquote

from fyi_lancedb_writer import LanceDBChunkWriter
from fyi_markdown import make_chunker, parse_markdown_document, render_markdown_document
from embedding_helpers import chunk_id_for_record, embedding_model_kwargs, metadata_json
from table_extractor import extract_tables


DEFAULT_DATA_DIR = Path("fyi/data/request")
DEFAULT_MARKDOWN_DIR = Path("fyi/markdown")
DEFAULT_TABLES_DIR = Path("fyi/markdown/tables")
DEFAULT_PERSIST_DIR = Path("./storage/fyi_parallel.lancedb")
DEFAULT_TABLE_NAME = "chunks_v2"
PIPELINE_VERSION = "v2"
DEFAULT_CONVERT_WORKERS = 10
DEFAULT_EMBED_BATCH_SIZE = 200
DEFAULT_MARKDOWN_QUEUE_SIZE = 128
DEFAULT_MAX_TASKS_PER_WORKER = 25
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_CHUNK_OVERLAP = 128
DEFAULT_MODEL_EMBED_BATCH_SIZE = 8
DEFAULT_CONVERT_GPU = "0,1,0"
DEFAULT_EMBED_GPU = "1"

_cached_converter = None


def _init_convert_worker(counter, gpu_list: list[str]) -> None:
    with counter.get_lock():
        idx = counter.value
        counter.value += 1
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_list[idx % len(gpu_list)]


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
    parser.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--table-name", type=str, default=DEFAULT_TABLE_NAME)
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
    parser.add_argument(
        "--convert-gpu",
        type=str,
        default=DEFAULT_CONVERT_GPU,
        help="Comma-separated CUDA_VISIBLE_DEVICES values; conversion workers round-robin across them.",
    )
    parser.add_argument(
        "--embed-gpu",
        type=str,
        default=DEFAULT_EMBED_GPU,
        help="CUDA_VISIBLE_DEVICES value for the embedding worker.",
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
    return Path(f"{markdown_path}.embedded.{PIPELINE_VERSION}")


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


def build_document_metadata(
    pdf_path: Path, markdown_path: Path, parser: str = "docling"
) -> dict[str, object]:
    identifiers = parse_fyi_identifiers(pdf_path)
    source = "fyi" if "fyi_request_id" in identifiers else "local"
    original_filename = unquote(pdf_path.name)
    path_digest = stable_path_digest(pdf_path)
    document_id = build_document_id(source, path_digest, identifiers)
    pdf_r2_key, markdown_r2_key = build_r2_keys(document_id, original_filename, identifiers)

    metadata: dict[str, object] = {
        "document_id": document_id,
        "source": source,
        "parser": parser,
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


def get_converter():
    global _cached_converter
    if _cached_converter is None:
        import torch
        from docling.document_converter import DocumentConverter

        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True

        _cached_converter = DocumentConverter()
    return _cached_converter


def rescue_pdf_to_md_with_pymupdf(
    pdf_path: Path, out_dir: Path
) -> tuple[bool, Path, Path | str | None]:
    import pymupdf

    md_file_path = safe_markdown_path(pdf_path, out_dir)
    try:
        doc = pymupdf.open(str(pdf_path))
    except Exception as exc:
        return False, pdf_path, f"pymupdf open failed: {exc}"

    try:
        if doc.page_count == 0:
            return False, pdf_path, "pymupdf: 0 pages"
        body = "\n\n".join(page.get_text() for page in doc)
    finally:
        doc.close()

    if not body.strip():
        return False, pdf_path, "pymupdf: empty text"

    metadata = build_document_metadata(pdf_path, md_file_path, parser="pymupdf")
    with open(md_file_path, "w", encoding="utf-8") as f:
        f.write(render_markdown_document(metadata, body))
    return True, pdf_path, md_file_path


def convert_pdf_to_md(
    pdf_path: Path, out_dir: Path
) -> tuple[bool, Path, Path | str | None]:
    md_file_path = safe_markdown_path(pdf_path, out_dir)
    failed_file = failed_marker_path(md_file_path)

    if md_file_path.exists():
        return True, pdf_path, md_file_path

    if failed_file.exists():
        return False, pdf_path, "Skipped due to previous critical failure (.failed lock exists)"

    try:
        converter = get_converter()
        result = converter.convert(str(pdf_path))
        body = result.document.export_to_markdown()
        metadata = build_document_metadata(pdf_path, md_file_path)

        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(render_markdown_document(metadata, body))

        return True, pdf_path, md_file_path
    except Exception as docling_exc:
        rescued, _, info = rescue_pdf_to_md_with_pymupdf(pdf_path, out_dir)
        if rescued:
            return True, pdf_path, info
        failed_file.touch()
        return False, pdf_path, f"docling: {docling_exc} | rescue: {info}"


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
    import torch

    gc.collect()
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


def build_chunk_records(nodes, markdown_paths: list[Path], embedding_model_name: str) -> list[dict[str, object]]:
    chunk_counts: dict[tuple[str, str], int] = {}
    records: list[dict[str, object]] = []
    created_at = utc_now_iso()

    for node in nodes:
        metadata = dict(getattr(node, "metadata", {}) or {})
        chunk_text = node_text(node)
        document_id = metadata.get("document_id")
        if not document_id:
            raise ValueError(
                f"Node metadata is missing document_id: {metadata!r}"
            )
        document_id = str(document_id)
        retrieval_view = str(metadata.get("retrieval_view") or "source_text")
        chunk_key = (document_id, retrieval_view)
        chunk_index = chunk_counts.get(chunk_key, 0)
        chunk_counts[chunk_key] = chunk_index + 1

        records.append(
            {
                "chunk_id": chunk_id_for_record(
                    document_id, chunk_index, chunk_text, retrieval_view
                ),
                "document_id": document_id,
                "chunk_index": chunk_index,
                "chunk_text": chunk_text,
                "text_preview": chunk_text[:500],
                "source": metadata.get("source"),
                "source_type": metadata.get("source_type"),
                "retrieval_view": retrieval_view,
                "canonical_document_id": metadata.get("canonical_document_id") or document_id,
                "generated": bool(metadata.get("generated")),
                "authority_name": metadata.get("authority_name"),
                "authority_slug": metadata.get("authority_slug"),
                "authority_category": metadata.get("authority_category"),
                "request_title": metadata.get("request_title"),
                "request_year": metadata.get("request_year"),
                "source_url": metadata.get("source_url"),
                "source_page_url": metadata.get("source_page_url"),
                "request_url": metadata.get("request_url"),
                "fyi_request_id": metadata.get("fyi_request_id"),
                "fyi_response_id": metadata.get("fyi_response_id"),
                "fyi_attachment_id": metadata.get("fyi_attachment_id"),
                "tenancy_order_id": metadata.get("tenancy_order_id"),
                "tenancy_application_number": metadata.get("tenancy_application_number"),
                "nztt_citation": metadata.get("nztt_citation"),
                "decision_date": metadata.get("decision_date"),
                "published_date": metadata.get("published_date"),
                "legal_issue_tags": metadata_json(metadata.get("legal_issue_tags")),
                "statute_sections": metadata_json(metadata.get("statute_sections")),
                "suppression_status": metadata.get("suppression_status"),
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
    chunker,
    embed_model,
    writer: LanceDBChunkWriter,
    document_class,
    embedding_model_name: str,
    tables_dir: Path,
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
            metadata["markdown_path"] = str(md_path)
            document_id = str(metadata["document_id"])
            rewritten_body, _ = extract_tables(body, document_id, tables_dir)
            documents.append(document_class(text=rewritten_body, metadata=metadata))
            embedded_paths.append(md_path)
        except Exception as exc:
            print(f"Error reading {md_path}: {exc}", flush=True)

    if not documents:
        return

    nodes = chunker.run(documents=documents)
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
    table_name: str,
    tables_dir: Path,
    embed_batch_size: int,
    chunk_size: int,
    chunk_overlap: int,
    model_embed_batch_size: int,
    embed_gpu_index: str,
) -> None:
    os.environ["CUDA_VISIBLE_DEVICES"] = embed_gpu_index

    import torch
    from llama_index.core import Document
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    embedding_model_name = "Qwen/Qwen3-Embedding-0.6B"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Embedding worker loading Qwen on {device} (CUDA_VISIBLE_DEVICES={embed_gpu_index})...", flush=True)

    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True

    embed_model = HuggingFaceEmbedding(
        model_name=embedding_model_name,
        device=device,
        max_length=chunk_size,
        embed_batch_size=model_embed_batch_size,
        model_kwargs=embedding_model_kwargs(torch),
    )
    chunker = make_chunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    writer = LanceDBChunkWriter(persist_dir, table_name=table_name)

    batch: list[Path] = []
    started = time.time()

    def _flush() -> None:
        flush_embedding_batch(
            batch, chunker, embed_model, writer, Document,
            embedding_model_name, tables_dir,
        )
        batch.clear()

    while True:
        try:
            item = markdown_queue.get(timeout=5)
        except queue.Empty:
            _flush()
            continue

        if item is None:
            break

        batch.append(Path(item))
        if len(batch) >= embed_batch_size:
            _flush()

    _flush()
    print(f"Embedding worker complete in {time.time() - started:.2f}s.", flush=True)


def run_conversion_pool(
    pdf_files: list[Path],
    md_out_dir: Path,
    markdown_queue: mp.Queue,
    embed_process: mp.Process,
    convert_workers: int,
    max_tasks_per_worker: int,
    convert_gpu_list: list[str],
) -> None:
    max_tasks = max_tasks_per_worker or None
    max_pending = max(convert_workers * 2, 1)
    submitted = completed = successful = failed = queued_for_embedding = 0
    pending: set = set()
    gpu_counter = mp.Value("i", 0)

    with ProcessPoolExecutor(
        max_workers=convert_workers,
        max_tasks_per_child=max_tasks,
        initializer=_init_convert_worker,
        initargs=(gpu_counter, convert_gpu_list),
    ) as executor:
        def _refill() -> None:
            nonlocal submitted
            while submitted < len(pdf_files) and len(pending) < max_pending:
                pending.add(executor.submit(convert_pdf_to_md, pdf_files[submitted], md_out_dir))
                submitted += 1

        _refill()
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                success, path, result_data = future.result()
                completed += 1
                if success:
                    successful += 1
                    if isinstance(result_data, Path) and put_markdown_for_embedding(markdown_queue, result_data, embed_process):
                        queued_for_embedding += 1
                    print(f"[{completed}/{len(pdf_files)}] Converted: {path.name}", flush=True)
                else:
                    failed += 1
                    print(f"[{completed}/{len(pdf_files)}] Failed: {path.name} - Error: {result_data}", flush=True)
                _refill()

    print(f"Conversion phase complete: {successful} successful, {failed} failed, {queued_for_embedding} queued for embedding.", flush=True)


def main() -> None:
    args = build_parser().parse_args()

    for flag, value in (
        ("--convert-workers", args.convert_workers),
        ("--embed-batch-size", args.embed_batch_size),
        ("--markdown-queue-size", args.markdown_queue_size),
        ("--chunk-size", args.chunk_size),
        ("--model-embed-batch-size", args.model_embed_batch_size),
    ):
        if value < 1:
            raise SystemExit(f"{flag} must be at least 1")
    convert_gpu_list = [g.strip() for g in args.convert_gpu.split(",")]

    mp.set_start_method("spawn", force=True)

    args.markdown_dir.mkdir(parents=True, exist_ok=True)
    args.tables_dir.mkdir(parents=True, exist_ok=True)
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
            args.table_name,
            args.tables_dir,
            args.embed_batch_size,
            args.chunk_size,
            args.chunk_overlap,
            args.model_embed_batch_size,
            args.embed_gpu,
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
            convert_gpu_list,
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
