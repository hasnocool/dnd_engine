from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver


class EncounterSchemaError(ValueError):
    pass


def _path_to_text(path_parts: list[Any]) -> str:
    if not path_parts:
        return "$"

    text = "$"
    for part in path_parts:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}"
    return text


def _format_validation_errors(errors: list[Any]) -> str:
    lines: list[str] = []
    for error in errors:
        location = _path_to_text(list(error.path))
        lines.append(f"{location}: {error.message}")
    return "\n".join(lines)


def load_schema_store(schema_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    schema_dir = schema_dir.resolve()
    filenames = [
        "action.schema.json",
        "creature.schema.json",
        "spell.schema.json",
        "encounter.schema.json",
    ]

    schemas_by_name: dict[str, dict[str, Any]] = {}
    store: dict[str, dict[str, Any]] = {}

    for filename in filenames:
        path = schema_dir / filename
        if not path.exists():
            raise EncounterSchemaError(f"Missing schema file: {path}")

        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas_by_name[filename] = schema

        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            store[schema_id] = schema

        store[filename] = schema
        store[path.resolve().as_uri()] = schema

    return schemas_by_name, store


def validate_encounter_data(instance: dict[str, Any], schema_dir: Path) -> None:
    schemas_by_name, store = load_schema_store(schema_dir)
    root_schema = schemas_by_name["encounter.schema.json"]

    Draft202012Validator.check_schema(root_schema)

    base_uri = root_schema.get("$id")
    if not isinstance(base_uri, str) or not base_uri:
        base_uri = (schema_dir / "encounter.schema.json").resolve().as_uri()

    resolver = RefResolver(base_uri=base_uri, referrer=root_schema, store=store)
    validator = Draft202012Validator(root_schema, resolver=resolver)

    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        raise EncounterSchemaError("Encounter schema validation failed:\n" + _format_validation_errors(errors))
