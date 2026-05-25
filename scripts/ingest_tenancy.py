from __future__ import annotations

import argparse
import gc
import multiprocessing as mp
import os
import time
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

from fyi_lancedb_writer import LanceDBChunkWriter
from fyi_markdown import make_chunker
from parallel_convert_and_embed import build_chunk_records, embedding_model_kwargs, node_text
from tenancy_corpus import (
    PIPELINE_VERSION,
    SOURCE,
    build_retrieval_documents,
    deterministic_enrichment,
    discover_legacy_tenancy_documents,
    discover_tenancy_documents,
    finalize_tenancy_metadata,
    markdown_path_for_document,
    merge_enrichment,
    needs_docling_conversion,
    parse_tenancy_markdown,
    render_tenancy_markdown,
)
from tenancy_instructor import (
    DEFAULT_INSTRUCTOR_MODE,
    INSTRUCTOR_MODE_CHOICES,
    resolve_instructor_mode,
)
from tenancy_rate_limit import RateLimitSnapshot, RequestRateLimiter
from tenancy_llm import (
    LLM_ENRICHMENT_VERSION,
    LLM_API_MODE_INSTRUCTOR,
    GeneratedEnrichment,
    GeneratedEnrichmentBatch,
    LlmBatch,
    apply_generated_enrichment,
    build_llm_batches,
    build_llm_input,
    enrich_with_llm,
    estimate_llm_batch_prompt_tokens,
    effective_llm_prompt_token_budget,
    llm_prompt_token_budget,
    parse_enrichment_content,
    pending_llm_markdown_paths,
    request_batch_with_rate_limit,
    request_generated_enrichment,
    request_generated_enrichment_for_documents,
    request_generated_enrichment_for_documents_with_retries,
    request_generated_enrichment_with_retries,
)


__all__ = [
    "LLM_ENRICHMENT_VERSION",
    "LLM_API_MODE_INSTRUCTOR",
    "GeneratedEnrichment",
    "GeneratedEnrichmentBatch",
    "LlmBatch",
    "RateLimitSnapshot",
    "RequestRateLimiter",
    "apply_generated_enrichment",
    "build_llm_batches",
    "build_llm_input",
    "estimate_llm_batch_prompt_tokens",
    "effective_llm_prompt_token_budget",
    "llm_prompt_token_budget",
    "parse_enrichment_content",
    "request_batch_with_rate_limit",
    "request_generated_enrichment",
    "request_generated_enrichment_for_documents",
    "request_generated_enrichment_for_documents_with_retries",
    "request_generated_enrichment_with_retries",
    "resolve_instructor_mode",
]


DEFAULT_PDF_DIR = Path("justice/data/tenancy/pdfs")
DEFAULT_LEGACY_PDF_DIR = Path("justice/data/tenancy/legacy/pdf")
DEFAULT_MARKDOWN_DIR = Path("storage/justice/tenancy/markdown_docling")
DEFAULT_TABLES_DIR = Path("storage/justice/tenancy/tables")
DEFAULT_PERSIST_DIR = Path("storage/justice/tenancy/lancedb")
DEFAULT_TABLE_NAME = "chunks_v2"
DEFAULT_CONVERT_WORKERS = 6
DEFAULT_MAX_TASKS_PER_WORKER = 20
DEFAULT_CONVERT_GPU = "0"
DEFAULT_EMBED_GPU = "0"
DEFAULT_EMBED_BATCH_SIZE = 128
DEFAULT_CHUNK_SIZE = 8192
DEFAULT_CHUNK_OVERLAP = 128
DEFAULT_MODEL_EMBED_BATCH_SIZE = 8
DEFAULT_DOTENV_PATH = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_LLM_BASE_URL = "https://api.minimax.io/v1"
DEFAULT_LLM_API_KEY = ""
DEFAULT_LLM_MODEL = "MiniMax-M2.7-highspeed"
DEFAULT_LLM_TOKENIZER_MODEL = "Qwen/Qwen3.6-27B"
DEFAULT_LLM_CONTEXT_TOKENS = 131072
DEFAULT_LLM_PROMPT_TOKEN_BUDGET = 14336
DEFAULT_LLM_RPM = 12
DEFAULT_LLM_BATCH_SIZE = 1
DEFAULT_LLM_CONCURRENCY = 20
DEFAULT_LLM_MAX_CHARS = 5000
DEFAULT_LLM_TIMEOUT = 120
DEFAULT_LLM_MAX_TOKENS = 4096
DEFAULT_LLM_START_JITTER_MIN = 3
DEFAULT_LLM_START_JITTER_MAX = 15

EMBED_PIPELINE_VERSION = f"{PIPELINE_VERSION}-qwen3-views-v1"

_cached_converter = None


def load_dotenv_values(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def default_llm_api_key(env: Mapping[str, str], dotenv: Mapping[str, str]) -> str:
    return (
        env.get("TENANCY_LLM_API_KEY")
        or env.get("MINIMAX_API_KEY")
        or dotenv.get("MINIMAX_API_KEY")
        or DEFAULT_LLM_API_KEY
    )


def build_parser(
    *,
    env: Mapping[str, str] | None = None,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
) -> argparse.ArgumentParser:
    env = os.environ if env is None else env
    dotenv = load_dotenv_values(dotenv_path)
    parser = argparse.ArgumentParser(
        description=(
            "Ingest Tenancy Tribunal PDFs as a first-class hybrid-search corpus: "
            "Docling Markdown, deterministic metadata, LLM retrieval metadata, "
            "and Qwen/LanceDB vectors."
        )
    )
    parser.add_argument("--pdf-dir", type=Path, default=DEFAULT_PDF_DIR)
    parser.add_argument("--legacy-pdf-dir", type=Path, default=DEFAULT_LEGACY_PDF_DIR)
    parser.add_argument("--include-legacy", action="store_true")
    parser.add_argument("--markdown-dir", type=Path, default=DEFAULT_MARKDOWN_DIR)
    parser.add_argument("--tables-dir", type=Path, default=DEFAULT_TABLES_DIR)
    parser.add_argument("--persist-dir", type=Path, default=DEFAULT_PERSIST_DIR)
    parser.add_argument("--table-name", default=DEFAULT_TABLE_NAME)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--skip-convert", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--skip-embed", action="store_true")
    parser.add_argument("--force-convert", action="store_true")
    parser.add_argument("--force-llm", action="store_true")
    parser.add_argument("--force-embed", action="store_true")
    parser.add_argument("--convert-workers", type=int, default=DEFAULT_CONVERT_WORKERS)
    parser.add_argument("--max-tasks-per-worker", type=int, default=DEFAULT_MAX_TASKS_PER_WORKER)
    parser.add_argument("--convert-gpu", default=DEFAULT_CONVERT_GPU)
    parser.add_argument("--embed-gpu", default=DEFAULT_EMBED_GPU)
    parser.add_argument("--embed-batch-size", type=int, default=DEFAULT_EMBED_BATCH_SIZE)
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument("--model-embed-batch-size", type=int, default=DEFAULT_MODEL_EMBED_BATCH_SIZE)
    parser.add_argument("--llm-base-url", default=env.get("TENANCY_LLM_BASE_URL", DEFAULT_LLM_BASE_URL))
    parser.add_argument("--llm-api-key", default=default_llm_api_key(env, dotenv))
    parser.add_argument("--llm-model", default=DEFAULT_LLM_MODEL)
    parser.add_argument(
        "--llm-tokenizer-model",
        default=env.get("TENANCY_LLM_TOKENIZER_MODEL", DEFAULT_LLM_TOKENIZER_MODEL),
    )
    parser.add_argument("--llm-context-tokens", type=int, default=DEFAULT_LLM_CONTEXT_TOKENS)
    parser.add_argument(
        "--llm-prompt-token-budget",
        type=int,
        default=DEFAULT_LLM_PROMPT_TOKEN_BUDGET,
        help="Target prompt tokens per LLM request before output; tune to vLLM max batched tokens.",
    )
    parser.add_argument("--llm-rpm", type=int, default=DEFAULT_LLM_RPM)
    parser.add_argument("--llm-batch-size", type=int, default=DEFAULT_LLM_BATCH_SIZE)
    parser.add_argument("--llm-concurrency", type=int, default=DEFAULT_LLM_CONCURRENCY)
    parser.add_argument("--llm-max-chars", type=int, default=DEFAULT_LLM_MAX_CHARS)
    parser.add_argument("--llm-timeout", type=int, default=DEFAULT_LLM_TIMEOUT)
    parser.add_argument("--llm-max-tokens", type=int, default=DEFAULT_LLM_MAX_TOKENS)
    parser.add_argument("--llm-start-jitter-min", type=float, default=DEFAULT_LLM_START_JITTER_MIN)
    parser.add_argument("--llm-start-jitter-max", type=float, default=DEFAULT_LLM_START_JITTER_MAX)
    parser.add_argument(
        "--llm-api-mode",
        choices=("chat", "responses", "instructor"),
        default=env.get("TENANCY_LLM_API_MODE", LLM_API_MODE_INSTRUCTOR),
        help="Use chat completions, Responses API structured parsing, or Instructor for enrichment.",
    )
    parser.add_argument(
        "--llm-instructor-mode",
        choices=INSTRUCTOR_MODE_CHOICES,
        default=env.get("TENANCY_LLM_INSTRUCTOR_MODE", DEFAULT_INSTRUCTOR_MODE),
        help="Instructor mode used when --llm-api-mode=instructor.",
    )
    return parser


def embedded_marker_path(markdown_path: Path) -> Path:
    return Path(f"{markdown_path}.embedded.{EMBED_PIPELINE_VERSION}")


def pending_embedding_markdown_paths(
    markdown_dir: Path,
    *,
    limit: int | None = None,
    force: bool = False,
) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(markdown_dir.glob("*.md")):
        if not force and embedded_marker_path(path).exists():
            continue
        try:
            metadata, body = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (
            metadata.get("source") == SOURCE
            and metadata.get("parser") == "docling"
            and metadata.get("pipeline_version") == PIPELINE_VERSION
            and body.strip()
        ):
            paths.append(path)
        if limit and len(paths) >= limit:
            break
    return paths


def get_converter():
    global _cached_converter
    if _cached_converter is None:
        import torch
        from docling.document_converter import DocumentConverter

        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
        _cached_converter = DocumentConverter()
    return _cached_converter


def _init_convert_worker(counter, gpu_list: list[str]) -> None:
    with counter.get_lock():
        idx = counter.value
        counter.value += 1
    os.environ["CUDA_VISIBLE_DEVICES"] = gpu_list[idx % len(gpu_list)]


def conversion_task(document, markdown_dir: Path, force: bool) -> dict[str, object]:
    metadata = dict(document.metadata)
    markdown_path = markdown_path_for_document(metadata, markdown_dir)
    if not force and not needs_docling_conversion(markdown_path, str(metadata["document_id"])):
        return {
            "status": "skipped",
            "document_id": metadata["document_id"],
            "markdown_path": str(markdown_path),
        }

    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    converter = get_converter()
    result = converter.convert(str(document.pdf_path))
    body = result.document.export_to_markdown()
    metadata = merge_enrichment(metadata, deterministic_enrichment(body))
    metadata = finalize_tenancy_metadata(metadata)
    markdown_path.write_text(render_tenancy_markdown(metadata, body), encoding="utf-8")
    return {
        "status": "converted",
        "document_id": metadata["document_id"],
        "markdown_path": str(markdown_path),
    }


def run_conversion(
    documents,
    markdown_dir: Path,
    *,
    workers: int,
    max_tasks_per_worker: int,
    convert_gpu: str,
    force: bool,
) -> dict[str, int]:
    if not documents:
        return conversion_counts()

    if workers <= 1:
        return run_conversion_sequential(documents, markdown_dir, force)

    return run_conversion_parallel(
        documents,
        markdown_dir,
        workers=workers,
        max_tasks_per_worker=max_tasks_per_worker,
        convert_gpu=convert_gpu,
        force=force,
    )


def conversion_counts() -> dict[str, int]:
    return {"converted": 0, "skipped": 0, "failed": 0}


def run_conversion_sequential(documents, markdown_dir: Path, force: bool) -> dict[str, int]:
    counts = conversion_counts()
    for document in documents:
        counts[run_conversion_task(document, markdown_dir, force)] += 1
    return counts


def run_conversion_parallel(
    documents,
    markdown_dir: Path,
    *,
    workers: int,
    max_tasks_per_worker: int,
    convert_gpu: str,
    force: bool,
) -> dict[str, int]:
    counts = conversion_counts()
    gpu_list = conversion_gpu_list(convert_gpu)
    max_tasks = max_tasks_per_worker or None
    counter = mp.Value("i", 0)
    pending: set = set()
    submitted = completed = 0
    max_pending = max(workers * 2, 1)
    with ProcessPoolExecutor(
        max_workers=workers,
        max_tasks_per_child=max_tasks,
        initializer=_init_convert_worker,
        initargs=(counter, gpu_list),
    ) as executor:

        def refill() -> None:
            nonlocal submitted
            while submitted < len(documents) and len(pending) < max_pending:
                pending.add(
                    executor.submit(
                        conversion_task, documents[submitted], markdown_dir, force
                    )
                )
                submitted += 1

        refill()
        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                completed += 1
                try:
                    result = future.result()
                    status = str(result["status"])
                except Exception as exc:
                    status = "failed"
                    print(f"[{completed}/{len(documents)}] Failed conversion: {exc}", flush=True)
                counts[status] += 1
                if completed % 100 == 0 or status == "failed":
                    print(f"Conversion progress {completed}/{len(documents)}: {counts}", flush=True)
                refill()
    return counts


def conversion_gpu_list(convert_gpu: str) -> list[str]:
    gpu_list = [gpu.strip() for gpu in convert_gpu.split(",") if gpu.strip()]
    return gpu_list or ["0"]


def run_conversion_task(document, markdown_dir: Path, force: bool) -> str:
    try:
        result = conversion_task(document, markdown_dir, force)
        return str(result["status"])
    except Exception as exc:
        print(f"Failed conversion for {document.pdf_path}: {exc}", flush=True)
        return "failed"


def embed_markdown_paths(
    markdown_paths: list[Path],
    *,
    persist_dir: Path,
    table_name: str,
    embed_gpu: str,
    embed_batch_size: int,
    chunk_size: int,
    chunk_overlap: int,
    model_embed_batch_size: int,
) -> dict[str, int]:
    if not markdown_paths:
        return {"embedded": 0, "failed": 0}

    os.environ["CUDA_VISIBLE_DEVICES"] = embed_gpu

    import torch
    from llama_index.core import Document
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    embedding_model_name = "Qwen/Qwen3-Embedding-0.6B"
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(
        f"Embedding Tenancy corpus on {device} "
        f"(CUDA_VISIBLE_DEVICES={embed_gpu}, files={len(markdown_paths)})",
        flush=True,
    )
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
    counts = {"embedded": 0, "failed": 0}

    for batch_start in range(0, len(markdown_paths), embed_batch_size):
        batch = markdown_paths[batch_start : batch_start + embed_batch_size]
        try:
            embed_batch(
                batch,
                chunker=chunker,
                document_class=Document,
                embed_model=embed_model,
                writer=writer,
                embedding_model_name=embedding_model_name,
            )
            for path in batch:
                embedded_marker_path(path).touch()
            counts["embedded"] += len(batch)
        except Exception as exc:
            counts["failed"] += len(batch)
            print(f"Embedding failed for batch starting {batch_start}: {exc}", flush=True)
        release_embedding_memory()
        print(
            f"Embedding progress {min(batch_start + len(batch), len(markdown_paths))}/"
            f"{len(markdown_paths)}: {counts}",
            flush=True,
        )
    return counts


def embed_batch(
    markdown_paths: list[Path],
    *,
    chunker,
    document_class,
    embed_model,
    writer: LanceDBChunkWriter,
    embedding_model_name: str,
) -> None:
    documents = []
    for path in markdown_paths:
        metadata, body = parse_tenancy_markdown(path.read_text(encoding="utf-8"))
        metadata["markdown_path"] = str(path)
        for retrieval_doc in build_retrieval_documents(metadata, body):
            documents.append(
                document_class(
                    text=retrieval_doc.text,
                    metadata=retrieval_doc.metadata | {"markdown_path": str(path)},
                )
            )
    nodes = chunker.run(documents=documents)
    texts = [node_text(node) for node in nodes]
    embeddings = embed_model.get_text_embedding_batch(texts, show_progress=True)
    records = build_chunk_records(nodes, markdown_paths, embedding_model_name)
    for record, embedding in zip(records, embeddings, strict=True):
        record["vector"] = embedding
    writer.add_records(records)


def release_embedding_memory() -> None:
    import torch

    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def validate_args(args: argparse.Namespace) -> None:
    if args.limit is not None and args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    for flag in (
        "convert_workers",
        "embed_batch_size",
        "chunk_size",
        "model_embed_batch_size",
        "llm_context_tokens",
        "llm_prompt_token_budget",
        "llm_rpm",
        "llm_batch_size",
        "llm_concurrency",
        "llm_max_chars",
        "llm_timeout",
        "llm_max_tokens",
    ):
        if getattr(args, flag) < 1:
            raise SystemExit(f"--{flag.replace('_', '-')} must be at least 1")
    if not args.pdf_dir.exists():
        raise SystemExit(f"Tenancy PDF directory not found: {args.pdf_dir}")
    if args.include_legacy and not args.legacy_pdf_dir.exists():
        raise SystemExit(f"Legacy Tenancy PDF directory not found: {args.legacy_pdf_dir}")
    args.markdown_dir.mkdir(parents=True, exist_ok=True)
    args.tables_dir.mkdir(parents=True, exist_ok=True)
    args.persist_dir.mkdir(parents=True, exist_ok=True)


def discover_documents(args: argparse.Namespace):
    documents = discover_tenancy_documents(args.pdf_dir)
    legacy_count = 0
    if args.include_legacy:
        legacy_documents = discover_legacy_tenancy_documents(args.legacy_pdf_dir)
        legacy_count = len(legacy_documents)
        documents.extend(legacy_documents)
    if args.limit:
        documents = documents[: args.limit]
    return documents, legacy_count


def discovery_message(document_count: int, legacy_count: int, include_legacy: bool) -> str:
    if include_legacy:
        return (
            f"Discovered {document_count} Tenancy Tribunal PDFs "
            f"({legacy_count} legacy PDFs included)."
        )
    return f"Discovered {document_count} unique Tenancy Tribunal PDFs."


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)
    mp.set_start_method("spawn", force=True)

    documents, legacy_count = discover_documents(args)
    print(discovery_message(len(documents), legacy_count, args.include_legacy), flush=True)

    if not args.skip_convert:
        started = time.time()
        counts = run_conversion(
            documents,
            args.markdown_dir,
            workers=args.convert_workers,
            max_tasks_per_worker=args.max_tasks_per_worker,
            convert_gpu=args.convert_gpu,
            force=args.force_convert,
        )
        print(f"Conversion complete in {time.time() - started:.2f}s: {counts}", flush=True)
        if counts["failed"]:
            raise SystemExit(f"Conversion failed for {counts['failed']} PDF(s)")

    if not args.skip_llm:
        paths = pending_llm_markdown_paths(
            args.markdown_dir,
            limit=args.limit,
            force=args.force_llm,
        )
        print(f"Pending LLM enrichment files: {len(paths)}", flush=True)
        if paths:
            counts = enrich_with_llm(
                paths,
                base_url=args.llm_base_url,
                api_key=args.llm_api_key,
                model=args.llm_model,
                tokenizer_model=args.llm_tokenizer_model,
                context_tokens=args.llm_context_tokens,
                prompt_token_budget=args.llm_prompt_token_budget,
                rpm=args.llm_rpm,
                batch_size=args.llm_batch_size,
                concurrency=args.llm_concurrency,
                max_chars=args.llm_max_chars,
                timeout=args.llm_timeout,
                max_tokens=args.llm_max_tokens,
                api_mode=args.llm_api_mode,
                instructor_mode=args.llm_instructor_mode,
                start_jitter_seconds=(
                    args.llm_start_jitter_min,
                    args.llm_start_jitter_max,
                ),
            )
            print(f"LLM enrichment complete: {counts}", flush=True)
            if counts["failed"]:
                raise SystemExit(f"LLM enrichment failed for {counts['failed']} Markdown file(s)")

    if not args.skip_embed:
        paths = pending_embedding_markdown_paths(
            args.markdown_dir,
            limit=args.limit,
            force=args.force_embed,
        )
        print(f"Pending embedding files: {len(paths)}", flush=True)
        counts = embed_markdown_paths(
            paths,
            persist_dir=args.persist_dir,
            table_name=args.table_name,
            embed_gpu=args.embed_gpu,
            embed_batch_size=args.embed_batch_size,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            model_embed_batch_size=args.model_embed_batch_size,
        )
        print(f"Embedding complete: {counts}", flush=True)
        if counts["failed"]:
            raise SystemExit(f"Embedding failed for {counts['failed']} Markdown file(s)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
