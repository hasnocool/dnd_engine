from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rules_registry import RulesRegistry, RulesRegistryError


class SpellCatalogError(ValueError):
    pass


_ALLOWED_RESOLUTION_MODES = {"attack", "save", "effect"}
_COMPONENT_SPLIT_RE = re.compile(r"\s*,\s*")
_AOE_RE = re.compile(
    r"(?i)\b(\d+)\s*-?\s*foot(?:-radius)?\s+"
    r"(sphere|cylinder|cone|line|cube|emanation)\b"
)


@dataclass(slots=True)
class SpellDefinition:
    id: str
    name: str
    source_id: str
    level: int
    school: str
    resolution_mode: str
    attack_bonus: int | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    damage: str | None = None
    damage_type: str = "untyped"
    half_damage_on_save: bool = False
    condition_on_failed_save: str | None = None
    condition_duration_rounds: int | None = None
    is_melee: bool = False
    range_feet: int = 60
    notes: str | None = None
    classes: list[str] | None = None
    casting_time: str | None = None
    range_text: str | None = None
    components: list[str] | None = None
    duration: str | None = None
    requires_concentration: bool = False
    higher_level: str | None = None
    aoe_shape: str | None = None
    aoe_size_feet: int | None = None


class SpellCatalog:
    def __init__(self, spells_by_id: dict[str, SpellDefinition]) -> None:
        self._spells_by_id = dict(spells_by_id)

    def get(self, spell_id: str) -> SpellDefinition:
        try:
            return self._spells_by_id[spell_id]
        except KeyError as exc:
            raise SpellCatalogError(f"Unknown spell_ref: {spell_id}") from exc

    def has(self, spell_id: str) -> bool:
        return spell_id in self._spells_by_id

    def ids(self) -> list[str]:
        return sorted(self._spells_by_id)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_note_field(notes: str | None, label: str) -> str | None:
    if not notes:
        return None
    pattern = re.compile(rf"{re.escape(label)}\s*:\s*(.+?)(?=\s+[A-Z][A-Za-z ]+\s*:|\s+Text\s*:|$)")
    match = pattern.search(notes)
    if not match:
        return None
    return match.group(1).strip()


def _extract_higher_level_text(notes: str | None) -> str | None:
    if not notes:
        return None
    match = re.search(r"(?i)Using a Higher-Level Spell Slot\.\s*(.+)$", notes)
    if not match:
        return None
    return match.group(1).strip()


def _parse_components(value: Any, notes: str | None) -> list[str] | None:
    if isinstance(value, list):
        components = [str(item).strip() for item in value if str(item).strip()]
        return components or None

    if isinstance(value, str):
        parts = [part.strip() for part in _COMPONENT_SPLIT_RE.split(value) if part.strip()]
        return parts or None

    inferred = _extract_note_field(notes, "Components") or _extract_note_field(notes, "Component")
    if inferred is None:
        return None
    parts = [part.strip() for part in _COMPONENT_SPLIT_RE.split(inferred) if part.strip()]
    return parts or None


def _parse_aoe(notes: str | None) -> tuple[str | None, int | None]:
    if not notes:
        return None, None

    match = _AOE_RE.search(notes)
    if not match:
        return None, None

    size = int(match.group(1))
    shape = match.group(2).lower()
    return shape, size


def _normalize_spell_records(payload: Any, catalog_path: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        raw_spells = payload
    elif isinstance(payload, dict):
        if payload.get("catalog_type") and str(payload.get("catalog_type")) != "spells":
            raise SpellCatalogError(
                f"Catalog file is not a spell catalog: {catalog_path} (catalog_type={payload.get('catalog_type')!r})"
            )
        raw_spells = payload.get("spells", [])
    else:
        raise SpellCatalogError(
            f"Spell catalog root must be object or array: {catalog_path} (got {type(payload).__name__})"
        )

    if not isinstance(raw_spells, list):
        raise SpellCatalogError(f"Spell catalog must contain a spell list: {catalog_path}")

    normalized: list[dict[str, Any]] = []
    for index, raw_spell in enumerate(raw_spells):
        if not isinstance(raw_spell, dict):
            raise SpellCatalogError(
                f"Invalid spell entry in {catalog_path} at index {index}: expected object"
            )
        normalized.append(raw_spell)
    return normalized


def _coerce_spell(raw: dict[str, Any], fallback_source_id: str, catalog_path: str) -> SpellDefinition:
    try:
        spell_id = str(raw["id"])
        name = str(raw["name"])
        source_id = str(raw.get("source_id") or raw.get("source") or fallback_source_id)
        level = int(raw["level"])
        school = str(raw["school"])
        resolution_mode = str(raw["resolution_mode"])
    except KeyError as exc:
        raise SpellCatalogError(f"Invalid spell record missing key in {catalog_path}: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise SpellCatalogError(f"Invalid spell record in {catalog_path}: {raw}") from exc

    if resolution_mode not in _ALLOWED_RESOLUTION_MODES:
        raise SpellCatalogError(
            f"Spell {spell_id} in {catalog_path} has invalid resolution_mode: {resolution_mode!r}"
        )

    notes = str(raw["notes"]) if raw.get("notes") is not None else None

    casting_time = (
        str(raw["casting_time"]).strip()
        if raw.get("casting_time") is not None
        else _extract_note_field(notes, "Casting Time")
    )
    range_text = (
        str(raw["range"]).strip() if raw.get("range") is not None else _extract_note_field(notes, "Range")
    )
    duration = (
        str(raw["duration"]).strip()
        if raw.get("duration") is not None
        else _extract_note_field(notes, "Duration")
    )

    classes_value = raw.get("classes")
    if isinstance(classes_value, list):
        classes = [str(item).strip() for item in classes_value if str(item).strip()]
    elif isinstance(classes_value, str):
        classes = [item.strip() for item in _COMPONENT_SPLIT_RE.split(classes_value) if item.strip()]
    else:
        inferred_classes = _extract_note_field(notes, "Classes")
        classes = [item.strip() for item in _COMPONENT_SPLIT_RE.split(inferred_classes)] if inferred_classes else []

    components = _parse_components(raw.get("components"), notes)

    requires_concentration = bool(raw.get("requires_concentration", False))
    if not requires_concentration and duration:
        requires_concentration = "concentration" in duration.lower()

    higher_level = str(raw["higher_level"]).strip() if raw.get("higher_level") else None
    if not higher_level:
        higher_level = _extract_higher_level_text(notes)

    aoe_shape = str(raw["aoe_shape"]).strip().lower() if raw.get("aoe_shape") else None
    aoe_size_feet = _safe_int(raw.get("aoe_size_feet"))
    if not aoe_shape or aoe_size_feet is None:
        inferred_shape, inferred_size = _parse_aoe(notes)
        aoe_shape = aoe_shape or inferred_shape
        aoe_size_feet = aoe_size_feet if aoe_size_feet is not None else inferred_size

    return SpellDefinition(
        id=spell_id,
        name=name,
        source_id=source_id,
        level=level,
        school=school,
        resolution_mode=resolution_mode,
        attack_bonus=_safe_int(raw.get("attack_bonus")),
        save_ability=str(raw["save_ability"]).strip() if raw.get("save_ability") is not None else None,
        save_dc=_safe_int(raw.get("save_dc")),
        damage=str(raw["damage"]).strip() if raw.get("damage") is not None else None,
        damage_type=str(raw.get("damage_type", "untyped")),
        half_damage_on_save=bool(raw.get("half_damage_on_save", False)),
        condition_on_failed_save=(
            str(raw["condition_on_failed_save"]).strip()
            if raw.get("condition_on_failed_save") is not None
            else None
        ),
        condition_duration_rounds=_safe_int(raw.get("condition_duration_rounds")),
        is_melee=bool(raw.get("is_melee", False)),
        range_feet=int(raw.get("range_feet", 60)),
        notes=notes,
        classes=classes or None,
        casting_time=casting_time,
        range_text=range_text,
        components=components,
        duration=duration,
        requires_concentration=requires_concentration,
        higher_level=higher_level,
        aoe_shape=aoe_shape,
        aoe_size_feet=aoe_size_feet,
    )


def load_spell_catalogs(registry: RulesRegistry) -> SpellCatalog:
    manifests = registry.catalog_manifests("spells")
    spells_by_id: dict[str, SpellDefinition] = {}

    for manifest in manifests:
        spell_records = _normalize_spell_records(manifest.payload, str(manifest.path))
        for raw_spell in spell_records:
            spell = _coerce_spell(raw_spell, manifest.source_id, str(manifest.path))
            if spell.id in spells_by_id:
                raise SpellCatalogError(f"Duplicate spell id found across catalogs: {spell.id}")
            spells_by_id[spell.id] = spell

    if not spells_by_id:
        raise RulesRegistryError("No spells loaded from rules registry")

    return SpellCatalog(spells_by_id)
