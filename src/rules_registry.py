from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RulesRegistryError(ValueError):
    pass


REQUIRED_CATALOG_TYPES = (
    "conditions",
    "spells",
    "monsters",
    "weapons",
    "armor",
    "magic_items",
    "classes",
    "species",
    "feats",
)


@dataclass(slots=True)
class SourceManifest:
    id: str
    path: Path
    payload: dict[str, Any]


@dataclass(slots=True)
class CatalogManifest:
    catalog_type: str
    source_id: str
    path: Path
    count: int | None
    payload: Any


@dataclass(slots=True)
class RulesRegistry:
    root_dir: Path
    version: str
    default_source_id: str
    sources: dict[str, SourceManifest]
    catalogs: dict[str, list[CatalogManifest]]

    def source(self, source_id: str) -> SourceManifest:
        try:
            return self.sources[source_id]
        except KeyError as exc:
            raise RulesRegistryError(f"Unknown source_id: {source_id}") from exc

    def catalog_manifests(self, catalog_type: str) -> list[CatalogManifest]:
        try:
            return self.catalogs[catalog_type]
        except KeyError as exc:
            raise RulesRegistryError(f"Unknown catalog type: {catalog_type}") from exc


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RulesRegistryError(f"Failed to read JSON file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RulesRegistryError(f"Invalid JSON file: {path}: {exc}") from exc


def _expect_object(value: Any, *, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RulesRegistryError(f"Expected JSON object at {where}")
    return value


def _expect_list(value: Any, *, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise RulesRegistryError(f"Expected JSON list at {where}")
    return value


def load_rules_registry(rules_data_dir: Path) -> RulesRegistry:
    rules_data_dir = rules_data_dir.resolve()
    registry_path = rules_data_dir / "registry.json"

    if not registry_path.exists():
        raise RulesRegistryError(f"Missing rules registry file: {registry_path}")

    registry_raw = _expect_object(_read_json_file(registry_path), where=str(registry_path))

    version = str(registry_raw.get("version", "0.0.0"))
    default_source_id = str(registry_raw.get("default_source_id", "")).strip()

    raw_sources = _expect_list(registry_raw.get("sources"), where="registry.sources")
    if not raw_sources:
        raise RulesRegistryError("registry.sources must be non-empty")

    sources: dict[str, SourceManifest] = {}
    for index, source_entry in enumerate(raw_sources):
        source_obj = _expect_object(source_entry, where=f"registry.sources[{index}]")

        source_id = str(source_obj.get("id", "")).strip()
        source_rel_path = str(source_obj.get("path", "")).strip()

        if not source_id:
            raise RulesRegistryError(f"registry.sources[{index}] missing non-empty id")
        if not source_rel_path:
            raise RulesRegistryError(f"registry.sources[{index}] missing non-empty path")
        if source_id in sources:
            raise RulesRegistryError(f"Duplicate source id in registry: {source_id}")

        source_path = (rules_data_dir / source_rel_path).resolve()
        source_payload = _expect_object(_read_json_file(source_path), where=str(source_path))

        payload_source_id = str(source_payload.get("source_id", "")).strip()
        if payload_source_id and payload_source_id != source_id:
            raise RulesRegistryError(
                f"Source id mismatch for {source_path}: registry={source_id!r} file={payload_source_id!r}"
            )

        sources[source_id] = SourceManifest(id=source_id, path=source_path, payload=source_payload)

    if default_source_id and default_source_id not in sources:
        raise RulesRegistryError(f"default_source_id {default_source_id!r} not found in sources")

    catalogs_raw = _expect_object(registry_raw.get("catalogs", {}), where="registry.catalogs")

    missing_catalog_types = [name for name in REQUIRED_CATALOG_TYPES if name not in catalogs_raw]
    if missing_catalog_types:
        missing_text = ", ".join(missing_catalog_types)
        raise RulesRegistryError(f"registry.catalogs missing required keys: {missing_text}")

    catalogs: dict[str, list[CatalogManifest]] = {}

    for catalog_type, raw_entries in catalogs_raw.items():
        entries = _expect_list(raw_entries, where=f"registry.catalogs.{catalog_type}")
        manifests: list[CatalogManifest] = []

        for index, entry in enumerate(entries):
            entry_obj = _expect_object(entry, where=f"registry.catalogs.{catalog_type}[{index}]")

            source_id = str(entry_obj.get("source_id", "")).strip()
            rel_path = str(entry_obj.get("path", "")).strip()
            count_raw = entry_obj.get("count")
            count = int(count_raw) if isinstance(count_raw, int) else None

            if not source_id:
                raise RulesRegistryError(
                    f"registry.catalogs.{catalog_type}[{index}] missing non-empty source_id"
                )
            if source_id not in sources:
                raise RulesRegistryError(
                    f"registry.catalogs.{catalog_type}[{index}] references unknown source_id: {source_id}"
                )
            if not rel_path:
                raise RulesRegistryError(f"registry.catalogs.{catalog_type}[{index}] missing non-empty path")

            manifest_path = (rules_data_dir / rel_path).resolve()
            manifest_payload = _read_json_file(manifest_path)

            # Catalog JSON roots vary by catalog/parser version (array vs object wrapper).
            if isinstance(manifest_payload, dict):
                payload_source_id = str(
                    manifest_payload.get("source_id") or manifest_payload.get("source", "")
                ).strip()
                if payload_source_id and payload_source_id != source_id:
                    raise RulesRegistryError(
                        f"Catalog source mismatch for {manifest_path}: "
                        f"registry={source_id!r} file={payload_source_id!r}"
                    )
            elif not isinstance(manifest_payload, list):
                raise RulesRegistryError(
                    f"Catalog root must be object or array: {manifest_path} (got {type(manifest_payload).__name__})"
                )

            manifests.append(
                CatalogManifest(
                    catalog_type=catalog_type,
                    source_id=source_id,
                    path=manifest_path,
                    count=count,
                    payload=manifest_payload,
                )
            )

        catalogs[catalog_type] = manifests

    return RulesRegistry(
        root_dir=rules_data_dir,
        version=version,
        default_source_id=default_source_id,
        sources=sources,
        catalogs=catalogs,
    )
