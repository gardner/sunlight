"""Local JSON-schema validation for tribunal extraction outputs."""

from __future__ import annotations

from typing import Any

from vllm.tribunal_eval_extract import build_response_schema


def validate_response_schema_object(value: Any) -> list[str]:
    if not isinstance(value, dict):
        return ["type:root"]
    schema = build_response_schema()
    properties = schema["properties"]
    errors: list[str] = []
    for field in schema["required"]:
        if field not in value:
            errors.append(f"missing_required:{field}")
    if not schema["additionalProperties"]:
        for field in value:
            if field not in properties:
                errors.append(f"extra_property:{field}")
    for field, field_value in value.items():
        property_schema = properties.get(field)
        if property_schema is None:
            continue
        errors.extend(validate_schema_property(field, field_value, property_schema))
    return errors


def validate_schema_property(field: str, value: Any, property_schema: dict[str, Any]) -> list[str]:
    if value is None:
        return []
    option_errors: list[str] = []
    for option in property_schema.get("anyOf", []):
        if option.get("type") == "null":
            continue
        errors = validate_schema_definition(field, value, option)
        if not errors:
            return []
        option_errors = errors
    return option_errors or validate_schema_definition(field, value, property_schema)


def validate_schema_definition(field: str, value: Any, definition: dict[str, Any]) -> list[str]:
    expected_type = definition.get("type")
    if expected_type == "string":
        if not isinstance(value, str):
            return [f"type:{field}"]
        enum_values = definition.get("enum")
        if enum_values and value not in enum_values:
            return [f"enum:{field}"]
        return []
    if expected_type == "number":
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return []
        return [f"type:{field}"]
    if expected_type == "boolean":
        return [] if isinstance(value, bool) else [f"type:{field}"]
    if expected_type == "null":
        return [] if value is None else [f"type:{field}"]
    return []
