from __future__ import annotations


DEFAULT_INSTRUCTOR_MODE = "json_schema"
INSTRUCTOR_MODE_CHOICES = (
    "json_schema",
    "json_mode",
    "md_json",
    "tools",
    "responses_tools",
)


def instructor_client(openai_client, mode_name: str):
    import instructor

    return instructor.from_openai(
        openai_client,
        mode=resolve_instructor_mode(mode_name),
    )


def resolve_instructor_mode(mode_name: str):
    import instructor

    modes = {
        "json_schema": instructor.Mode.JSON_SCHEMA,
        "json_mode": instructor.Mode.JSON,
        "md_json": instructor.Mode.MD_JSON,
        "tools": instructor.Mode.TOOLS,
        "responses_tools": instructor.Mode.RESPONSES_TOOLS,
    }
    try:
        return modes[mode_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported Instructor mode: {mode_name}") from exc
