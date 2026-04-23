from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from monster_catalog import MonsterCatalog, MonsterDefinition, load_monster_catalog
from rules_registry import RulesRegistry, RulesRegistryError, load_rules_registry
from turn_engine import Action, Creature


class CreatureBuilderError(ValueError):
    pass


ABILITY_KEYS = ("str", "dex", "con", "int", "wis", "cha")
_WORD_TO_INT = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}
_ABILITY_NAME_TO_KEY = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
}
_DAMAGE_TYPE_WORDS = {
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
}


@dataclass(slots=True)
class ClassDefinition:
    id: str
    name: str
    hit_die: int
    saving_throw_proficiencies: set[str]


@dataclass(slots=True)
class SpeciesDefinition:
    id: str
    name: str
    speed_feet: int


def _default_rules_data_dir() -> Path:
    return (Path(__file__).resolve().parent.parent / "rules_data").resolve()


def _ability_modifier(score: int) -> int:
    return math.floor((score - 10) / 2)


def _norm_lookup_id(raw_id: str) -> str:
    text = raw_id.strip().casefold()
    for prefix in ("class.", "species.", "monster."):
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def _extract_hit_die(raw: dict[str, Any]) -> int:
    value = raw.get("hit_die")
    if isinstance(value, int) and value > 0:
        return value

    core_traits = raw.get("core_traits")
    if isinstance(core_traits, dict):
        hit_die_text = str(core_traits.get("Hit Point Die", ""))
        match = re.search(r"D(\d+)", hit_die_text, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    description = str(raw.get("description", ""))
    match = re.search(r"Hit Point Die\s+D(\d+)", description, flags=re.IGNORECASE)
    if match:
        return int(match.group(1))

    raise CreatureBuilderError(f"Could not determine hit die for class {raw.get('id')!r}")


def _extract_class_save_proficiencies(raw: dict[str, Any]) -> set[str]:
    values: list[str] = []

    direct = raw.get("saving_throw_proficiencies")
    if isinstance(direct, list):
        values.extend(str(item) for item in direct)
    elif isinstance(direct, str):
        values.extend(re.split(r"[,;/]", direct))

    core_traits = raw.get("core_traits")
    if isinstance(core_traits, dict):
        core = core_traits.get("Saving Throw Proficiencies")
        if isinstance(core, str):
            values.extend(re.split(r"[,;/]|\band\b", core))

    profs: set[str] = set()
    for value in values:
        key = _ABILITY_NAME_TO_KEY.get(value.strip().casefold())
        if key:
            profs.add(key)

    return profs


def _load_class_index(registry: RulesRegistry) -> dict[str, ClassDefinition]:
    manifests = registry.catalog_manifests("classes")
    index: dict[str, ClassDefinition] = {}

    for manifest in manifests:
        payload = manifest.payload
        rows = payload if isinstance(payload, list) else payload.get("classes", [])
        if not isinstance(rows, list):
            raise CreatureBuilderError(f"Class catalog malformed: {manifest.path}")

        for row in rows:
            if not isinstance(row, dict):
                continue
            class_id = _norm_lookup_id(str(row.get("id", "")))
            if not class_id:
                continue
            class_def = ClassDefinition(
                id=class_id,
                name=str(row.get("name", class_id)).strip(),
                hit_die=_extract_hit_die(row),
                saving_throw_proficiencies=_extract_class_save_proficiencies(row),
            )
            index[class_id] = class_def

    if not index:
        raise CreatureBuilderError("No classes found in class catalogs")

    return index


def _load_species_index(registry: RulesRegistry) -> dict[str, SpeciesDefinition]:
    manifests = registry.catalog_manifests("species")
    index: dict[str, SpeciesDefinition] = {}

    for manifest in manifests:
        payload = manifest.payload
        rows = payload if isinstance(payload, list) else payload.get("species", [])
        if not isinstance(rows, list):
            raise CreatureBuilderError(f"Species catalog malformed: {manifest.path}")

        for row in rows:
            if not isinstance(row, dict):
                continue
            species_id = _norm_lookup_id(str(row.get("id", "")))
            if not species_id:
                continue
            speed_feet = int(row.get("speed_feet", 30)) if str(row.get("speed_feet", "")).strip() else 30
            index[species_id] = SpeciesDefinition(
                id=species_id,
                name=str(row.get("name", species_id)).strip(),
                speed_feet=speed_feet,
            )

    if not index:
        raise CreatureBuilderError("No species found in species catalogs")

    return index


def _infer_damage_terms(text: str) -> list[str]:
    lowered = text.casefold().replace(";", ",")
    terms: list[str] = []
    for chunk in lowered.split(","):
        token = chunk.strip().split(" ")[0]
        if token in _DAMAGE_TYPE_WORDS:
            terms.append(token)
    return terms


def _to_key_ability_scores(values: dict[str, int]) -> dict[str, int]:
    out = {ability: 10 for ability in ABILITY_KEYS}
    for ability in ABILITY_KEYS:
        if ability in values:
            out[ability] = int(values[ability])
    return out


def _parse_multiattack_action(actions: list[Action], raw_text: str) -> Action | None:
    lowered = raw_text.casefold()
    match = re.search(r"makes?\s+(one|two|three|four|five|six|\d+)\s+([a-z][a-z\s]+?)\s+attacks?", lowered)
    if not match:
        return None

    count_text, attack_name_fragment = match.groups()
    count = _WORD_TO_INT.get(count_text, int(count_text) if count_text.isdigit() else 0)
    if count <= 0:
        return None

    fragment = attack_name_fragment.strip()
    sub_action_ids: list[str] = []

    for action in actions:
        if action.kind != "attack":
            continue
        if fragment in action.name.casefold() or action.name.casefold() in fragment:
            sub_action_ids.append(action.id)

    if not sub_action_ids:
        return None

    expanded: list[str] = []
    for _ in range(count):
        expanded.append(sub_action_ids[min(len(expanded), len(sub_action_ids) - 1)])

    return Action(
        id="multiattack",
        name="Multiattack",
        kind="multiattack",
        economy_slot="action",
        sub_actions=expanded,
        notes=raw_text,
    )


def _parse_attack_action(monster_id: str, action_name: str, raw_text: str) -> Action | None:
    text = f"{action_name}. {raw_text}".strip()

    bonus_match = re.search(r"Attack Roll:\s*([+\-]?\d+)", text, flags=re.IGNORECASE)
    damage_match = re.search(r"(\d+d\d+(?:\s*[+\-]\s*\d+)?)", text)
    damage_type_match = re.search(
        r"\b(acid|bludgeoning|cold|fire|force|lightning|necrotic|piercing|poison|psychic|radiant|slashing|thunder)\s+damage\b",
        text,
        flags=re.IGNORECASE,
    )

    if not bonus_match or not damage_match:
        return None

    is_melee = bool(re.search(r"\bMelee\b", text, flags=re.IGNORECASE))
    range_feet = 5

    reach_match = re.search(r"reach\s*(\d+)\s*ft", text, flags=re.IGNORECASE)
    if reach_match:
        range_feet = int(reach_match.group(1))

    range_match = re.search(r"range\s*(\d+)(?:\/(\d+))?\s*ft", text, flags=re.IGNORECASE)
    if range_match:
        range_feet = int(range_match.group(1))
        if not is_melee:
            is_melee = False

    action_id_base = re.sub(r"[^a-z0-9]+", "_", action_name.casefold()).strip("_") or "attack"
    action_id = f"{monster_id}_{action_id_base}"

    return Action(
        id=action_id,
        name=action_name,
        kind="attack",
        attack_bonus=int(bonus_match.group(1)),
        damage=damage_match.group(1).replace(" ", ""),
        damage_type=(damage_type_match.group(1).lower() if damage_type_match else "untyped"),
        is_melee=is_melee,
        range_feet=range_feet,
        economy_slot="action",
        notes=raw_text,
    )


def _parse_monster_actions(monster: MonsterDefinition) -> tuple[list[Action], list[str]]:
    actions: list[Action] = []
    unparsed: list[str] = []

    for feature in monster.actions:
        raw_text = f"{feature.name}. {feature.description}".strip()
        if feature.name.casefold().startswith("multiattack"):
            continue

        parsed = _parse_attack_action(monster.id, feature.name, raw_text)
        if parsed is not None:
            actions.append(parsed)
        else:
            unparsed.append(raw_text)

    for feature in monster.actions:
        if not feature.name.casefold().startswith("multiattack"):
            continue
        raw_text = f"{feature.name}. {feature.description}".strip()
        multiattack = _parse_multiattack_action(actions, raw_text)
        if multiattack is not None:
            actions.insert(0, multiattack)
        else:
            unparsed.append(raw_text)

    return actions, unparsed


def _load_registry_or_raise(registry: RulesRegistry | None) -> RulesRegistry:
    if registry is not None:
        return registry
    try:
        return load_rules_registry(_default_rules_data_dir())
    except RulesRegistryError as exc:
        raise CreatureBuilderError(str(exc)) from exc


def _compute_proficiency_bonus(level: int) -> int:
    return int(math.ceil(1 + (level / 4)))


def _derive_saving_throws(ability_scores: dict[str, int], proficiency_bonus: int, proficient: set[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for ability in ABILITY_KEYS:
        modifier = _ability_modifier(ability_scores[ability])
        out[ability] = modifier + (proficiency_bonus if ability in proficient else 0)
    return out


def _class_hit_points(level: int, hit_die: int, con_mod: int) -> int:
    if level <= 0:
        raise CreatureBuilderError("level must be >= 1 for class-based creatures")

    level_one = hit_die + con_mod
    if level == 1:
        return max(1, level_one)

    per_level = (hit_die // 2 + 1) + con_mod
    return max(1, level_one + max(0, level - 1) * per_level)


def build_from_class(
    class_id: str,
    species_id: str,
    level: int,
    ability_scores: dict[str, int],
    name: str,
    team: str,
    *,
    registry: RulesRegistry | None = None,
) -> Creature:
    registry = _load_registry_or_raise(registry)

    class_index = _load_class_index(registry)
    species_index = _load_species_index(registry)

    class_key = _norm_lookup_id(class_id)
    species_key = _norm_lookup_id(species_id)

    if class_key not in class_index:
        raise CreatureBuilderError(f"Unknown class id: {class_id}")
    if species_key not in species_index:
        raise CreatureBuilderError(f"Unknown species id: {species_id}")

    class_def = class_index[class_key]
    species_def = species_index[species_key]

    scores = _to_key_ability_scores(ability_scores)
    proficiency_bonus = _compute_proficiency_bonus(level)
    saving_throws = _derive_saving_throws(scores, proficiency_bonus, class_def.saving_throw_proficiencies)

    con_mod = _ability_modifier(scores["con"])
    max_hp = _class_hit_points(level, class_def.hit_die, con_mod)

    unarmed_attack_bonus = proficiency_bonus + _ability_modifier(scores["str"])
    unarmed_damage = f"1d4+{_ability_modifier(scores['str'])}" if _ability_modifier(scores["str"]) >= 0 else "1d4"

    creature_id = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_") or f"{species_key}_{class_key}"

    return Creature(
        id=creature_id,
        name=name,
        team=team,
        ac=max(1, 10 + _ability_modifier(scores["dex"])),
        max_hp=max_hp,
        current_hp=max_hp,
        initiative_bonus=_ability_modifier(scores["dex"]),
        saving_throws=saving_throws,
        actions=[
            Action(
                id=f"{creature_id}_unarmed",
                name="Unarmed Strike",
                kind="attack",
                attack_bonus=unarmed_attack_bonus,
                damage=unarmed_damage,
                damage_type="bludgeoning",
                is_melee=True,
                range_feet=5,
                economy_slot="action",
            )
        ],
        conditions=[],
        speed_feet=species_def.speed_feet,
        notes=f"Built from class={class_def.id} species={species_def.id}",
        ability_scores=scores,
        proficiency_bonus=proficiency_bonus,
        level=level,
        spell_slots={},
        spell_slot_max={},
        concentration_spell=None,
        action_used=False,
        bonus_action_used=False,
        reaction_used=False,
        damage_immunities=[],
        damage_resistances=[],
        damage_vulnerabilities=[],
        hit_dice_remaining=level,
        hit_die=class_def.hit_die,
        death_save_successes=0,
        death_save_failures=0,
        stable=False,
        dead=False,
        charmed_by=[],
        focused_target_id=None,
        on_take_damage_hooks=[],
        on_creature_attacked_nearby_hooks=[],
    )


def build_from_monster(
    monster_id: str,
    monster_catalog: MonsterCatalog,
    *,
    team: str = "monsters",
) -> Creature:
    lookup_id = _norm_lookup_id(monster_id)

    monster: MonsterDefinition
    if monster_catalog.has(monster_id):
        monster = monster_catalog.get(monster_id)
    elif monster_catalog.has(lookup_id):
        monster = monster_catalog.get(lookup_id)
    else:
        raise CreatureBuilderError(f"Unknown monster id: {monster_id}")

    actions, unparsed_actions = _parse_monster_actions(monster)
    if not actions:
        fallback_attack_bonus = _ability_modifier(monster.ability_scores.get("str", 10)) + (
            monster.proficiency_bonus or 2
        )
        actions = [
            Action(
                id=f"{monster.id}_improvised_attack",
                name="Improvised Attack",
                kind="attack",
                attack_bonus=fallback_attack_bonus,
                damage="1d4",
                damage_type="bludgeoning",
                is_melee=True,
                range_feet=5,
                economy_slot="action",
                notes="Fallback action generated by creature_builder",
            )
        ]

    hit_die_count = 0
    hit_die = 8
    if monster.hp_formula:
        match = re.search(r"(\d+)d(\d+)", monster.hp_formula)
        if match:
            hit_die_count = int(match.group(1))
            hit_die = int(match.group(2))

    notes = []
    if unparsed_actions:
        notes.append("Unparsed monster actions: " + " | ".join(unparsed_actions[:8]))

    return Creature(
        id=monster.id,
        name=monster.name,
        team=team,
        ac=max(1, monster.ac),
        max_hp=max(1, monster.hp),
        current_hp=max(1, monster.hp),
        initiative_bonus=monster.initiative_bonus,
        saving_throws=monster.saving_throws,
        actions=actions,
        conditions=[],
        speed_feet=max(0, monster.speed_feet),
        notes="; ".join(notes) if notes else None,
        ability_scores=monster.ability_scores,
        proficiency_bonus=monster.proficiency_bonus or 2,
        level=0,
        spell_slots={},
        spell_slot_max={},
        concentration_spell=None,
        action_used=False,
        bonus_action_used=False,
        reaction_used=False,
        damage_immunities=_infer_damage_terms(", ".join(monster.immunities)),
        damage_resistances=_infer_damage_terms(", ".join(monster.resistances)),
        damage_vulnerabilities=_infer_damage_terms(", ".join(monster.vulnerabilities)),
        hit_dice_remaining=hit_die_count,
        hit_die=hit_die,
        death_save_successes=0,
        death_save_failures=0,
        stable=False,
        dead=False,
        charmed_by=[],
        focused_target_id=None,
        on_take_damage_hooks=[],
        on_creature_attacked_nearby_hooks=[],
    )


def build_monster_catalog_from_registry(
    registry: RulesRegistry | None = None,
) -> MonsterCatalog:
    registry = _load_registry_or_raise(registry)
    return load_monster_catalog(registry)


def roll_short_rest_heal(
    creature: Creature,
    hit_dice_to_spend: int,
    *,
    rng: random.Random,
) -> tuple[int, int]:
    if hit_dice_to_spend <= 0 or creature.hit_die <= 0:
        return 0, 0

    con_mod = _ability_modifier(creature.ability_scores.get("con", 10))

    spent = 0
    healed = 0
    spend_limit = min(hit_dice_to_spend, creature.hit_dice_remaining)
    for _ in range(spend_limit):
        if creature.current_hp >= creature.max_hp:
            break
        spent += 1
        roll = rng.randint(1, creature.hit_die)
        healed += max(0, roll + con_mod)

    healed_effective = min(healed, max(0, creature.max_hp - creature.current_hp))
    return spent, healed_effective
