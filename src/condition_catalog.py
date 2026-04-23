from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rules_registry import RulesRegistry


class ConditionCatalogError(ValueError):
    pass


@dataclass(slots=True)
class ConditionEffect:
    name: str
    description: str


@dataclass(slots=True)
class ConditionDefinition:
    id: str
    name: str
    source_id: str
    description: str
    effects: list[ConditionEffect]


class ConditionCatalog:
    def __init__(self, by_id: dict[str, ConditionDefinition]) -> None:
        self._by_id = dict(by_id)
        self._by_name = {definition.name.casefold(): definition for definition in by_id.values()}

    def get(self, condition_id: str) -> ConditionDefinition:
        try:
            return self._by_id[condition_id]
        except KeyError as exc:
            raise ConditionCatalogError(f"Unknown condition id: {condition_id}") from exc

    def by_name(self, condition_name: str) -> ConditionDefinition:
        key = condition_name.casefold()
        try:
            return self._by_name[key]
        except KeyError as exc:
            raise ConditionCatalogError(f"Unknown condition name: {condition_name}") from exc

    def has(self, condition_id: str) -> bool:
        return condition_id in self._by_id

    def has_name(self, condition_name: str) -> bool:
        return condition_name.casefold() in self._by_name

    def ids(self) -> list[str]:
        return sorted(self._by_id)


def _coerce_effects(raw_effects: Any) -> list[ConditionEffect]:
    if not isinstance(raw_effects, list):
        return []

    out: list[ConditionEffect] = []
    for effect in raw_effects:
        if isinstance(effect, dict):
            name = str(effect.get("name", "")).strip()
            description = str(effect.get("description", "")).strip()
            if name or description:
                out.append(ConditionEffect(name=name or "(unnamed)", description=description))
        elif isinstance(effect, str) and effect.strip():
            out.append(ConditionEffect(name=effect.strip(), description=""))
    return out


def _coerce_condition(raw: dict[str, Any], fallback_source_id: str, catalog_path: str) -> ConditionDefinition:
    try:
        condition_id = str(raw["id"]).strip()
        name = str(raw["name"]).strip()
    except KeyError as exc:
        raise ConditionCatalogError(f"Condition record missing key in {catalog_path}: {exc}") from exc

    if not condition_id:
        raise ConditionCatalogError(f"Condition in {catalog_path} has empty id")

    source_id = str(raw.get("source_id") or raw.get("source") or fallback_source_id).strip()
    description = str(raw.get("description", "")).strip()

    return ConditionDefinition(
        id=condition_id,
        name=name,
        source_id=source_id,
        description=description,
        effects=_coerce_effects(raw.get("effects")),
    )


def load_condition_catalog(registry: RulesRegistry) -> ConditionCatalog:
    manifests = registry.catalog_manifests("conditions")
    by_id: dict[str, ConditionDefinition] = {}

    for manifest in manifests:
        payload = manifest.payload
        if isinstance(payload, dict):
            raw_conditions = payload.get("conditions", [])
        else:
            raw_conditions = payload

        if not isinstance(raw_conditions, list):
            raise ConditionCatalogError(f"Condition catalog must contain array/list in {manifest.path}")

        for raw in raw_conditions:
            if not isinstance(raw, dict):
                raise ConditionCatalogError(f"Condition entry in {manifest.path} must be object")
            condition = _coerce_condition(raw, manifest.source_id, str(manifest.path))
            if condition.id in by_id:
                raise ConditionCatalogError(f"Duplicate condition id across manifests: {condition.id}")
            by_id[condition.id] = condition

    return ConditionCatalog(by_id)
