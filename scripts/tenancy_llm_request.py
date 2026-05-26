from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


CHAT_RESPONSE_FORMAT_JSON_OBJECT = "json_object"
CHAT_RESPONSE_FORMAT_JSON_SCHEMA = "json_schema"
CHAT_RESPONSE_FORMAT_CHOICES = (
    CHAT_RESPONSE_FORMAT_JSON_OBJECT,
    CHAT_RESPONSE_FORMAT_JSON_SCHEMA,
)
DEFAULT_CHAT_RESPONSE_FORMAT = CHAT_RESPONSE_FORMAT_JSON_OBJECT
DEFAULT_CHAT_EXTRA_BODY = {"chat_template_kwargs": {"enable_thinking": False}}


@dataclass(frozen=True)
class ChatRequestOptions:
    response_format: str = DEFAULT_CHAT_RESPONSE_FORMAT
    extra_body: Mapping[str, object] | None = None


def build_provider_extra_body(provider_ignore: Sequence[str]) -> dict[str, object] | None:
    if not provider_ignore:
        return None
    return {"provider": {"ignore": list(provider_ignore)}}


def build_chat_response_format(
    response_format_type: str,
    response_schema: Mapping[str, Any],
) -> dict[str, Any]:
    if response_format_type == CHAT_RESPONSE_FORMAT_JSON_OBJECT:
        return {"type": "json_object"}
    if response_format_type == CHAT_RESPONSE_FORMAT_JSON_SCHEMA:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "generated_enrichment_batch",
                "strict": True,
                "schema": response_schema,
            },
        }
    raise ValueError(f"Unsupported chat response format: {response_format_type}")


def chat_completion_kwargs(
    *,
    model: str,
    messages: list[dict[str, object]],
    max_tokens: int,
    response_schema: Mapping[str, Any],
    options: ChatRequestOptions | None,
) -> dict[str, Any]:
    options = options or ChatRequestOptions()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "response_format": build_chat_response_format(options.response_format, response_schema),
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    extra_body = DEFAULT_CHAT_EXTRA_BODY if options.extra_body is None else options.extra_body
    if extra_body:
        kwargs["extra_body"] = dict(extra_body)
    return kwargs


def llm_error_summary(exc: Exception, limit: int = 1000) -> str:
    detail: dict[str, Any] = {
        "type": type(exc).__name__,
        "message": str(exc)[:limit],
    }
    status_code = getattr(exc, "status_code", None)
    if status_code is not None:
        detail["status_code"] = status_code
    response = getattr(exc, "response", None)
    if response is not None:
        response_text = getattr(response, "text", "")
        if response_text:
            detail["response_text"] = response_text[:limit]
        try:
            response_json = response.json()
        except Exception:
            response_json = None
        if isinstance(response_json, dict):
            detail["response_json"] = response_json
            detail["response_message"] = response_message(response_json)
    body = getattr(exc, "body", None)
    if body is not None:
        detail["body"] = body
    return json.dumps(detail, ensure_ascii=True, default=str)


def response_message(payload: Mapping[str, Any]) -> object:
    error = payload.get("error")
    if isinstance(error, Mapping):
        return error.get("message") or error.get("detail") or error.get("code")
    return payload.get("message") or payload.get("detail") or payload.get("title")
