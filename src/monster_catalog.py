from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rules_registry import RulesRegistry


class MonsterCatalogError(ValueError):
    pass


@dataclass(slots=True)
class TextFeature:
    name: str
    description: str


@dataclass(slots=True)
class MonsterDefinition:
    id: str
    name: str
    source_id: str
    size: str
    creature_type: str
    alignment: str
    ac: int
    hp: int
    hp_formula: str | None
    speed: str | None
    speed_feet: int
    initiative_bonus: int
    ability_scores: dict[str, int]
    saving_throws: dict[str, int]
    cr: float | None
    xp: int | None
    proficiency_bonus: int | None
    skills: dict[str, int]
    immunities: list[str]
    resistances: list[str]
    vulnerabilities: list[str]
    senses: str | None
    languages: str | None
    traits: list[TextFeature]
    actions: list[TextFeature]
    bonus_actions: list[TextFeature]
    reactions: list[TextFeature]


class MonsterCatalog:
    def __init__(self, monsters_by_id: dict[str, MonsterDefinition]) -> None:
        self._monsters_by_id = dict(monsters_by_id)

    def get(self, monster_id: str) -> MonsterDefinition:
        try:
            return self._monsters_by_id[monster_id]
        except KeyError as exc:
            raise MonsterCatalogError(f"Unknown monster id: {monster_id}") from exc

    def has(self, monster_id: str) -> bool:
        return monster_id in self._monsters_by_id

    def ids(self) -> list[str]:
        return sorted(self._monsters_by_id)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_damage_terms(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip().lower() for item in value if str(item).strip()]

    text = str(value)
    # Data extraction quality varies. Keep conservative normalization.
    text = text.replace(";", ",")
    terms = [part.strip().lower() for part in text.split(",") if part.strip()]
    return terms


def _parse_feature_list(value: Any) -> list[TextFeature]:
    if not isinstance(value, list):
        return []

    features: list[TextFeature] = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            description = str(item.get("description", "")).strip()
            if name or description:
                features.append(TextFeature(name=name or "(unnamed)", description=description))
        elif isinstance(item, str) and item.strip():
            features.append(TextFeature(name=item.strip(), description=""))

    return features


def _parse_skills(value: Any) -> dict[str, int]:
    if isinstance(value, dict):
        out: dict[str, int] = {}
        for key, raw in value.items():
            try:
                out[str(key).strip().lower()] = int(raw)
            except (TypeError, ValueError):
                continue
        return out

    if not isinstance(value, str):
        return {}

    parsed: dict[str, int] = {}
    for chunk in value.split(","):
        piece = chunk.strip()
        if not piece:
            continue
        name, _, bonus_text = piece.partition(" ")
        if not bonus_text:
            continue
        bonus_text = bonus_text.strip().replace("+", "")
        try:
            parsed[name.lower()] = int(bonus_text)
        except ValueError:
            continue
    return parsed


def _coerce_monster(raw: dict[str, Any], fallback_source_id: str, catalog_path: str) -> MonsterDefinition:
    try:
        monster_id = str(raw["id"]).strip()
        name = str(raw["name"]).strip()
        source_id = str(raw.get("source_id") or raw.get("source") or fallback_source_id).strip()
    except KeyError as exc:
        raise MonsterCatalogError(f"Monster record missing key in {catalog_path}: {exc}") from exc

    if not monster_id:
        raise MonsterCatalogError(f"Monster in {catalog_path} has empty id")

    ability_scores_raw = raw.get("ability_scores") or {}
    saving_throws_raw = raw.get("saving_throws") or {}

    ability_scores = {
        ability: _safe_int(ability_scores_raw.get(ability), 10)
        for ability in ("str", "dex", "con", "int", "wis", "cha")
    }
    saving_throws = {
        ability: _safe_int(saving_throws_raw.get(ability), 0)
        for ability in ("str", "dex", "con", "int", "wis", "cha")
    }

    speed_feet = _safe_int(raw.get("speed_feet"), 0)
    if speed_feet <= 0 and isinstance(raw.get("speed"), str):
        import re

        match = re.search(r"(\d+)\s*ft", raw["speed"])
        if match:
            speed_feet = int(match.group(1))

    return MonsterDefinition(
        id=monster_id,
        name=name,
        source_id=source_id,
        size=str(raw.get("size", "")).strip(),
        creature_type=str(raw.get("creature_type", "")).strip(),
        alignment=str(raw.get("alignment", "")).strip(),
        ac=_safe_int(raw.get("ac"), 10),
        hp=_safe_int(raw.get("hp"), 1),
        hp_formula=str(raw["hp_formula"]).strip() if raw.get("hp_formula") is not None else None,
        speed=str(raw["speed"]).strip() if raw.get("speed") is not None else None,
        speed_feet=max(0, speed_feet),
        initiative_bonus=_safe_int(raw.get("initiative_bonus"), 0),
        ability_scores=ability_scores,
        saving_throws=saving_throws,
        cr=_safe_float(raw.get("cr")),
        xp=_safe_int(raw.get("xp"), 0) if raw.get("xp") is not None else None,
        proficiency_bonus=_safe_int(raw.get("proficiency_bonus"), 0)
        if raw.get("proficiency_bonus") is not None
        else None,
        skills=_parse_skills(raw.get("skills")),
        immunities=_parse_damage_terms(raw.get("immunities")),
        resistances=_parse_damage_terms(raw.get("resistances")),
        vulnerabilities=_parse_damage_terms(raw.get("vulnerabilities")),
        senses=str(raw["senses"]).strip() if raw.get("senses") is not None else None,
        languages=str(raw["languages"]).strip() if raw.get("languages") is not None else None,
        traits=_parse_feature_list(raw.get("traits")),
        actions=_parse_feature_list(raw.get("actions")),
        bonus_actions=_parse_feature_list(raw.get("bonus_actions")),
        reactions=_parse_feature_list(raw.get("reactions")),
    )


def load_monster_catalog(registry: RulesRegistry) -> MonsterCatalog:
    manifests = registry.catalog_manifests("monsters")
    monsters_by_id: dict[str, MonsterDefinition] = {}

    for manifest in manifests:
        payload = manifest.payload
        if isinstance(payload, dict):
            raw_monsters = payload.get("monsters", [])
        else:
            raw_monsters = payload

        if not isinstance(raw_monsters, list):
            raise MonsterCatalogError(f"Monster catalog must contain array/list in {manifest.path}")

        for raw in raw_monsters:
            if not isinstance(raw, dict):
                raise MonsterCatalogError(f"Monster entry in {manifest.path} must be object")
            monster = _coerce_monster(raw, manifest.source_id, str(manifest.path))
            if monster.id in monsters_by_id:
                raise MonsterCatalogError(f"Duplicate monster id across manifests: {monster.id}")
            monsters_by_id[monster.id] = monster

    return MonsterCatalog(monsters_by_id)
