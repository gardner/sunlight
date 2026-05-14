"""Loads per-request FYI metadata for Vectorize sidecar enrichment.

The on-disk layout is `fyi/data/**/<id>-<slug>.json`, one JSON document per
request. We flatten the parts that are useful for vector filtering into a
narrow dict keyed by integer request id."""

from __future__ import annotations

import json
import re
from pathlib import Path

# `popular_agency` is a UI prominence flag and `not_apply` is a default
# placeholder when the body has no type tag — neither describes the body.
NON_CATEGORICAL_TAGS = frozenset({"popular_agency", "not_apply"})

_FILENAME_RE = re.compile(r"^(\d+)-[^/]+\.json$")


def derive_authority_category(tags: list) -> str | None:
    for tag in tags or []:
        name = tag[0] if isinstance(tag, (list, tuple)) else tag
        if name and name not in NON_CATEGORICAL_TAGS:
            return name
    return None


def _request_year(created_at: str | None) -> int | None:
    if not created_at:
        return None
    return int(created_at[:4])


def _flatten(doc: dict) -> dict:
    pb = doc.get("public_body") or {}
    return {
        "authority_slug": pb.get("url_name"),
        "authority_name": pb.get("name"),
        "authority_category": derive_authority_category(pb.get("tags") or []),
        "law_used": doc.get("law_used"),
        "described_state": doc.get("described_state"),
        "request_year": _request_year(doc.get("created_at")),
        "request_title": doc.get("title"),
        "url_title": doc.get("url_title"),
        "request_created_at": doc.get("created_at"),
    }


def load_request_metadata(data_dir: Path) -> dict[int, dict]:
    """Load every `<id>-<slug>.json` request dump beneath `data_dir`.

    A small fraction of scraped files are HTML error pages rather than
    JSON. Those are skipped at the parse boundary rather than aborting
    the whole join — a missing request id only means that request's
    chunks ship without authority enrichment."""
    index: dict[int, dict] = {}
    for path in data_dir.rglob("*.json"):
        match = _FILENAME_RE.match(path.name)
        if not match:
            continue
        request_id = int(match.group(1))
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(doc, dict) or "id" not in doc:
            continue
        index[request_id] = _flatten(doc)
    return index
