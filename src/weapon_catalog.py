from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rules_registry import RulesRegistry


class WeaponCatalogError(ValueError):
    pass


@dataclass(slots=True)
class WeaponDefinition:
    id: str
    name: str
    source_id: str
    category: str | None
    is_martial: bool
    is_ranged: bool
    damage_dice: str | None
    damage_type: str | None
    properties: list[str]
    mastery: str | None
    weight_lb: str | None
    cost: str | None
    is_finesse: bool
    is_light: bool
    is_heavy: bool
    is_two_handed: bool
    is_reach: bool
    is_loading: bool
    versatile_damage: str | None
    thrown_range_normal: int | None
    thrown_range_long: int | None


class WeaponCatalog:
    def __init__(self, by_id: dict[str, WeaponDefinition]) -> None:
        self._by_id = dict(by_id)

    def get(self, weapon_id: str) -> WeaponDefinition:
        try:
            return self._by_id[weapon_id]
        except KeyError as exc:
            raise WeaponCatalogError(f"Unknown weapon id: {weapon_id}") from exc

    def has(self, weapon_id: str) -> bool:
        return weapon_id in self._by_id

    def ids(self) -> list[str]:
        return sorted(self._by_id)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_weapon(raw: dict[str, Any], fallback_source_id: str, catalog_path: str) -> WeaponDefinition:
    try:
        weapon_id = str(raw["id"]).strip()
        name = str(raw["name"]).strip()
    except KeyError as exc:
        raise WeaponCatalogError(f"Weapon record missing key in {catalog_path}: {exc}") from exc

    if not weapon_id:
        raise WeaponCatalogError(f"Weapon in {catalog_path} has empty id")

    thrown_range = raw.get("thrown_range")
    thrown_normal = None
    thrown_long = None
    if isinstance(thrown_range, dict):
        thrown_normal = _safe_int(thrown_range.get("normal"))
        thrown_long = _safe_int(thrown_range.get("long"))

    properties_raw = raw.get("properties")
    properties: list[str] = []
    if isinstance(properties_raw, list):
        properties = [str(item).strip() for item in properties_raw if str(item).strip()]

    return WeaponDefinition(
        id=weapon_id,
        name=name,
        source_id=str(raw.get("source_id") or raw.get("source") or fallback_source_id).strip(),
        category=str(raw["category"]).strip() if raw.get("category") is not None else None,
        is_martial=bool(raw.get("is_martial", False)),
        is_ranged=bool(raw.get("is_ranged", False)),
        damage_dice=str(raw["damage_dice"]).strip() if raw.get("damage_dice") is not None else None,
        damage_type=str(raw["damage_type"]).strip() if raw.get("damage_type") is not None else None,
        properties=properties,
        mastery=str(raw["mastery"]).strip() if raw.get("mastery") is not None else None,
        weight_lb=str(raw["weight_lb"]).strip() if raw.get("weight_lb") is not None else None,
        cost=str(raw["cost"]).strip() if raw.get("cost") is not None else None,
        is_finesse=bool(raw.get("is_finesse", False)),
        is_light=bool(raw.get("is_light", False)),
        is_heavy=bool(raw.get("is_heavy", False)),
        is_two_handed=bool(raw.get("is_two_handed", False)),
        is_reach=bool(raw.get("is_reach", False)),
        is_loading=bool(raw.get("is_loading", False)),
        versatile_damage=str(raw["versatile_damage"]).strip() if raw.get("versatile_damage") is not None else None,
        thrown_range_normal=thrown_normal,
        thrown_range_long=thrown_long,
    )


def load_weapon_catalog(registry: RulesRegistry) -> WeaponCatalog:
    manifests = registry.catalog_manifests("weapons")
    by_id: dict[str, WeaponDefinition] = {}

    for manifest in manifests:
        payload = manifest.payload
        if isinstance(payload, dict):
            raw_weapons = payload.get("weapons", [])
        else:
            raw_weapons = payload

        if not isinstance(raw_weapons, list):
            raise WeaponCatalogError(f"Weapon catalog must contain array/list in {manifest.path}")

        for raw in raw_weapons:
            if not isinstance(raw, dict):
                raise WeaponCatalogError(f"Weapon entry in {manifest.path} must be object")
            weapon = _coerce_weapon(raw, manifest.source_id, str(manifest.path))
            if weapon.id in by_id:
                raise WeaponCatalogError(f"Duplicate weapon id across manifests: {weapon.id}")
            by_id[weapon.id] = weapon

    return WeaponCatalog(by_id)
