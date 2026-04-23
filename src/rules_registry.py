from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RulesRegistryError(ValueError):
    pass


@dataclass(slots=True)
class SourceRecord:
    id: str
    path: Path
    payload: dict[str, Any]


@dataclass(slots=True)
class CatalogRecord:
    source_id: str
    path: Path
    payload: dict[str, Any]


@dataclass(slots=True)
class RulesRegistry:
    root_dir: Path
    version: str
    default_source_id: str
    sources: dict[str, SourceRecord]
    spell_catalogs: list[CatalogRecord]


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RulesRegistryError(f"Failed to read JSON file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RulesRegistryError(f"Invalid JSON file: {path}: {exc}") from exc


def load_rules_registry(rules_data_dir: Path) -> RulesRegistry:
    rules_data_dir = rules_data_dir.resolve()
    registry_path = rules_data_dir / "registry.json"

    if not registry_path.exists():
        raise RulesRegistryError(f"Missing rules registry file: {registry_path}")

    registry_raw = _read_json_file(registry_path)

    version = str(registry_raw.get("version", "0.0.0"))
    default_source_id = str(registry_raw.get("default_source_id", ""))

    raw_sources = registry_raw.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise RulesRegistryError("rules_data/registry.json must contain a non-empty 'sources' list")

    sources: dict[str, SourceRecord] = {}
    for source_entry in raw_sources:
        if not isinstance(source_entry, dict):
            raise RulesRegistryError("Each source entry must be an object")

        source_id = str(source_entry.get("id", "")).strip()
        rel_path = str(source_entry.get("path", "")).strip()

        if not source_id or not rel_path:
            raise RulesRegistryError("Each source entry must contain non-empty 'id' and 'path'")

        source_path = (rules_data_dir / rel_path).resolve()
        payload = _read_json_file(source_path)
        sources[source_id] = SourceRecord(id=source_id, path=source_path, payload=payload)

    raw_catalogs = registry_raw.get("catalogs", {})
    if not isinstance(raw_catalogs, dict):
        raise RulesRegistryError("'catalogs' must be an object")

    raw_spell_catalogs = raw_catalogs.get("spells", [])
    if not isinstance(raw_spell_catalogs, list):
        raise RulesRegistryError("'catalogs.spells' must be a list")

    spell_catalogs: list[CatalogRecord] = []
    for catalog_entry in raw_spell_catalogs:
        if not isinstance(catalog_entry, dict):
            raise RulesRegistryError("Each spell catalog entry must be an object")

        source_id = str(catalog_entry.get("source_id", "")).strip()
        rel_path = str(catalog_entry.get("path", "")).strip()

        if not source_id or not rel_path:
            raise RulesRegistryError("Each spell catalog entry must contain non-empty 'source_id' and 'path'")

        if source_id not in sources:
            raise RulesRegistryError(f"Spell catalog references unknown source_id: {source_id}")

        catalog_path = (rules_data_dir / rel_path).resolve()
        payload = _read_json_file(catalog_path)
        spell_catalogs.append(CatalogRecord(source_id=source_id, path=catalog_path, payload=payload))

    return RulesRegistry(
        root_dir=rules_data_dir,
        version=version,
        default_source_id=default_source_id,
        sources=sources,
        spell_catalogs=spell_catalogs,
    )
