from __future__ import annotations

from dataclasses import dataclass

from rules_registry import RulesRegistry, RulesRegistryError


class SpellCatalogError(ValueError):
    pass


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


def _coerce_spell(raw: dict) -> SpellDefinition:
    try:
        return SpellDefinition(
            id=str(raw["id"]),
            name=str(raw["name"]),
            source_id=str(raw["source_id"]),
            level=int(raw["level"]),
            school=str(raw["school"]),
            resolution_mode=str(raw["resolution_mode"]),
            attack_bonus=int(raw["attack_bonus"]) if raw.get("attack_bonus") is not None else None,
            save_ability=str(raw["save_ability"]) if raw.get("save_ability") is not None else None,
            save_dc=int(raw["save_dc"]) if raw.get("save_dc") is not None else None,
            damage=str(raw["damage"]) if raw.get("damage") is not None else None,
            damage_type=str(raw.get("damage_type", "untyped")),
            half_damage_on_save=bool(raw.get("half_damage_on_save", False)),
            condition_on_failed_save=str(raw["condition_on_failed_save"]) if raw.get("condition_on_failed_save") is not None else None,
            condition_duration_rounds=int(raw["condition_duration_rounds"]) if raw.get("condition_duration_rounds") is not None else None,
            is_melee=bool(raw.get("is_melee", False)),
            range_feet=int(raw.get("range_feet", 60)),
            notes=str(raw["notes"]) if raw.get("notes") is not None else None,
        )
    except KeyError as exc:
        raise SpellCatalogError(f"Invalid spell record missing key: {exc}") from exc
    except (TypeError, ValueError) as exc:
        raise SpellCatalogError(f"Invalid spell record: {raw}") from exc


def load_spell_catalogs(registry: RulesRegistry) -> SpellCatalog:
    spells_by_id: dict[str, SpellDefinition] = {}

    for catalog_record in registry.spell_catalogs:
        payload = catalog_record.payload
        catalog_type = str(payload.get("catalog_type", ""))
        if catalog_type != "spells":
            raise RulesRegistryError(
                f"Catalog file is not a spell catalog: {catalog_record.path} (catalog_type={catalog_type!r})"
            )

        source_id = str(payload.get("source_id", ""))
        if source_id != catalog_record.source_id:
            raise RulesRegistryError(
                f"Catalog source_id mismatch in {catalog_record.path}: "
                f"registry={catalog_record.source_id!r} file={source_id!r}"
            )

        raw_spells = payload.get("spells", [])
        if not isinstance(raw_spells, list):
            raise SpellCatalogError(f"Spell catalog must contain a 'spells' list: {catalog_record.path}")

        for raw_spell in raw_spells:
            if not isinstance(raw_spell, dict):
                raise SpellCatalogError(f"Invalid spell entry in {catalog_record.path}: expected object")

            spell = _coerce_spell(raw_spell)
            if spell.id in spells_by_id:
                raise SpellCatalogError(f"Duplicate spell id found across catalogs: {spell.id}")

            spells_by_id[spell.id] = spell

    return SpellCatalog(spells_by_id)
