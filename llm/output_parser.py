from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OutputParserError(ValueError):
    pass


def parse_llm_json(payload: str | dict, schema: type[SchemaT]) -> SchemaT:
    if isinstance(payload, dict):
        return _validate(payload, schema)

    candidates = [_extract_fenced_json(payload), *_extract_json_objects(payload)]
    if payload.strip().startswith("{") and payload.strip().endswith("}"):
        candidates.insert(0, payload.strip())

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            return _validate(json.loads(_repair_json(candidate)), schema)
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as error:
            last_error = error

    preview = payload[:500]
    if not any(candidates):
        raise OutputParserError(f"No JSON object found in LLM output. First 500 characters: {preview}")
    raise OutputParserError(
        f"Invalid LLM JSON output: {last_error}. First 500 characters: {preview}"
    ) from last_error


def _validate(data: dict, schema: type[SchemaT]) -> SchemaT:
    if hasattr(schema, "model_validate"):
        return schema.model_validate(data)
    return schema.parse_obj(data)


def _extract_fenced_json(value: str) -> str:
    match = re.search(r"```json\s*(.*?)\s*```", value, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def _extract_json_objects(value: str) -> list[str]:
    candidates: list[str] = []
    for start in (index for index, character in enumerate(value) if character == "{"):
        candidate = _extract_balanced_object_from(value, start)
        if candidate:
            candidates.append(candidate)
    return candidates


def _extract_balanced_object_from(value: str, start: int) -> str:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(value)):
        character = value[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return value[start : index + 1]
    return ""


def _repair_json(value: str) -> str:
    repaired = value.strip()
    repaired = re.sub(r",(\s*[}\]])", r"\1", repaired)
    return repaired
