"""Shared markdown frontmatter and chunker helpers used by the FYI
ingestion pipeline. Kept separate from parallel_convert_and_embed so the
main pipeline script stays inside the project's per-file line budget."""

from __future__ import annotations

import json


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
        raise ValueError("Markdown is missing opening frontmatter delimiter")

    end_index = text.find("\n---\n", 4)
    if end_index == -1:
        raise ValueError("Markdown frontmatter has no closing delimiter")

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
            raise ValueError(f"Malformed frontmatter line: {line!r}")
        metadata[key.strip()] = json.loads(raw_value.strip())

    return metadata, body


def make_chunker(chunk_size: int, chunk_overlap: int = 128):
    """Compose a header-aware Markdown chunker with a token-budgeted
    splitter so no node exceeds chunk_size tokens. SentenceSplitter
    catches the outlier case where a heading-free section blows past
    the embedder's max_length."""
    from llama_index.core.ingestion import IngestionPipeline
    from llama_index.core.node_parser import MarkdownNodeParser, SentenceSplitter

    return IngestionPipeline(
        transformations=[
            MarkdownNodeParser(),
            SentenceSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap),
        ]
    )
