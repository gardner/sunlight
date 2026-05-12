# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "torch",
#   "sentence-transformers",
#   "llama-index-core",
#   "llama-index-embeddings-huggingface",
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
import multiprocessing as mp
import queue
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path


DEFAULT_DATA_DIR = Path("/mnt/dgx-ssd/src/sunlight_nz/fyi/data/request")
DEFAULT_MARKDOWN_DIR = Path("/mnt/dgx-ssd/src/sunlight_nz/fyi/markdown")
DEFAULT_PERSIST_DIR = Path("./storage/fyi_parallel_index")
DEFAULT_CONVERT_WORKERS = 3
DEFAULT_EMBED_BATCH_SIZE = 50
DEFAULT_MARKDOWN_QUEUE_SIZE = 32
DEFAULT_MAX_TASKS_PER_WORKER = 25

_cached_converter = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Convert FYI PDFs to Markdown with Docling workers while one "
            "embedding worker consumes completed Markdown in bounded batches."
        )
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--convert-workers", type=int, default=DEFAULT_CONVERT_WORKERS)
    parser.add_argument("--embed-batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    parser.add_argument("--markdown-queue-size", type=int, default=DEFAULT_MARKDOWN_QUEUE_SIZE)
    parser.add_argument(
        "--max-tasks-per-worker",
        type=int,
        default=DEFAULT_MAX_TASKS_PER_WORKER,
        help="Recycle each Docling worker after this many PDFs. Use 0 to disable.",
    )
    return parser


def safe_markdown_path(pdf_path: Path, out_dir: Path) -> Path:
    safe_name = pdf_path.name.replace(" ", "_").replace("%20", "_")
    return out_dir / f"{safe_name}.md"


def embedded_marker_path(markdown_path: Path) -> Path:
    return Path(str(markdown_path) + ".embedded")


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
    failed_file_path = out_dir / f"{md_file_path.stem}.failed"

    if md_file_path.exists():
        return True, pdf_path, md_file_path

    if failed_file_path.exists():
        return False, pdf_path, "Skipped due to previous critical failure (.failed lock exists)"

    failed_file_path.touch()

    try:
        converter = get_converter()
        result = converter.convert(str(pdf_path))
        md_text = result.document.export_to_markdown()

        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(md_text)

        failed_file_path.unlink(missing_ok=True)
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


def flush_embedding_batch(
    batch: list[Path],
    parser,
    index,
    persist_dir: Path,
    document_class,
    vector_index_class,
):
    if not batch:
        return index

    llama_docs = []
    embedded_paths = []

    for md_path in batch:
        if embedded_marker_path(md_path).exists():
            continue

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                text = f.read()
            llama_docs.append(
                document_class(
                    text=text,
                    metadata={"source_file": str(md_path), "file_name": md_path.name},
                )
            )
            embedded_paths.append(md_path)
        except Exception as exc:
            print(f"Error reading {md_path}: {exc}", flush=True)

    if not llama_docs:
        return index

    nodes = parser.get_nodes_from_documents(llama_docs)
    print(f"Embedding {len(nodes)} nodes from {len(embedded_paths)} markdown files...", flush=True)

    if index is None:
        index = vector_index_class(nodes, show_progress=True)
    else:
        index.insert_nodes(nodes)

    print(f"Persisting embedded batch to {persist_dir}...", flush=True)
    index.storage_context.persist(persist_dir=persist_dir)

    for md_path in embedded_paths:
        embedded_marker_path(md_path).touch()

    return index


def embedding_worker(
    markdown_queue: mp.Queue,
    persist_dir: Path,
    embed_batch_size: int,
) -> None:
    import torch
    from llama_index.core import Document, Settings, StorageContext, VectorStoreIndex, load_index_from_storage
    from llama_index.core.node_parser import MarkdownNodeParser
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Embedding worker loading Qwen model on {device}...", flush=True)

    if device == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True

    Settings.embed_model = HuggingFaceEmbedding(
        model_name="Qwen/Qwen3-Embedding-0.6B",
        device=device,
        model_kwargs={"torch_dtype": torch.float16},
    )
    Settings.llm = None

    parser = MarkdownNodeParser()
    if persist_dir.exists() and any(persist_dir.iterdir()):
        print(f"Embedding worker loading existing index from {persist_dir}...", flush=True)
        storage_context = StorageContext.from_defaults(persist_dir=persist_dir)
        index = load_index_from_storage(storage_context)
    else:
        index = None

    batch: list[Path] = []
    started = time.time()

    while True:
        try:
            item = markdown_queue.get(timeout=5)
        except queue.Empty:
            index = flush_embedding_batch(
                batch,
                parser,
                index,
                persist_dir,
                Document,
                VectorStoreIndex,
            )
            batch.clear()
            continue

        if item is None:
            break

        batch.append(Path(item))
        if len(batch) >= embed_batch_size:
            index = flush_embedding_batch(
                batch,
                parser,
                index,
                persist_dir,
                Document,
                VectorStoreIndex,
            )
            batch.clear()

    flush_embedding_batch(batch, parser, index, persist_dir, Document, VectorStoreIndex)
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

    mp.set_start_method("spawn", force=True)

    args.markdown_dir.mkdir(parents=True, exist_ok=True)
    args.persist_dir.parent.mkdir(parents=True, exist_ok=True)

    print(f"Finding PDF files in {args.data_dir}...", flush=True)
    pdf_files = list(args.data_dir.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files.", flush=True)

    markdown_queue = mp.Queue(maxsize=args.markdown_queue_size)
    embed_process = mp.Process(
        target=embedding_worker,
        args=(markdown_queue, args.persist_dir, args.embed_batch_size),
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
