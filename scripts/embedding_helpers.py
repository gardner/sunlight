from __future__ import annotations

import hashlib
import importlib.util
import json
import re


def embedding_model_kwargs(torch_module) -> dict[str, object]:
    kwargs: dict[str, object] = {"torch_dtype": torch_module.bfloat16}
    if importlib.util.find_spec("flash_attn") is not None:
        kwargs["attn_implementation"] = "flash_attention_2"
    else:
        kwargs["attn_implementation"] = "sdpa"
    return kwargs


def chunk_id_for_record(
    document_id: str,
    chunk_index: int,
    chunk_text: str,
    retrieval_view: str | None = None,
) -> str:
    text_digest = hashlib.sha1(chunk_text.encode("utf-8")).hexdigest()[:12]
    if retrieval_view and retrieval_view != "source_text":
        safe_view = re.sub(r"[^a-zA-Z0-9_]+", "_", retrieval_view).strip("_")
        return f"chunk_{document_id}_{safe_view}_{chunk_index:04d}_{text_digest}"
    return f"chunk_{document_id}_{chunk_index:04d}_{text_digest}"


def metadata_json(value: object) -> str | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
