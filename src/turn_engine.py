from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from rules_registry import RulesRegistryError, load_rules_registry
from schema_loader import EncounterSchemaError, validate_encounter_data
from spell_catalog import SpellCatalog, SpellCatalogError, SpellDefinition, load_spell_catalogs


DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$")
ABILITIES = {"str", "dex", "con", "int", "wis", "cha"}
HARD_DISABLE_CONDITIONS = {"unconscious", "paralyzed", "stunned", "incapacitated"}
DISADVANTAGE_CONDITIONS = {"poisoned", "blinded"}


@dataclass(slots=True)
class ActiveCondition:
    name: str
    rounds_remaining: int | None = None


@dataclass(slots=True)
class Action:
    id: str
    name: str
    kind: str
    attack_bonus: int | None = None
    damage: str | None = None
    damage_type: str = "untyped"
    is_melee: bool = True
    range_feet: int = 5
    spell_ref: str | None = None
    attack_bonus_override: int | None = None
    save_dc_override: int | None = None
    damage_override: str | None = None
    half_damage_on_save_override: bool | None = None
    condition_on_failed_save_override: str | None = None
    condition_duration_rounds_override: int | None = None
    notes: str | None = None


@dataclass(slots=True)
class ResolvedAction:
    id: str
    name: str
    kind: str
    attack_bonus: int | None = None
    damage: str | None = None
    damage_type: str = "untyped"
    is_melee: bool = True
    range_feet: int = 5
    resolution_mode: str | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    half_damage_on_save: bool = False
    condition_on_failed_save: str | None = None
    condition_duration_rounds: int | None = None
    spell_level: int | None = None
    school: str | None = None
    spell_ref: str | None = None
    source_id: str | None = None
    notes: str | None = None


@dataclass(slots=True)
class Creature:
    id: str
    name: str
    team: str
    ac: int
    max_hp: int
    current_hp: int
    initiative_bonus: int
    saving_throws: dict[str, int]
    actions: list[Action]
    conditions: list[ActiveCondition] = field(default_factory=list)
    speed_feet: int = 30
    notes: str | None = None
    initiative: int | None = None

    @property
    def alive(self) -> bool:
        return self.current_hp > 0

    def has_condition(self, condition_name: str) -> bool:
        wanted = condition_name.casefold()
        return any(condition.name.casefold() == wanted for condition in self.conditions)

    def has_any_condition(self, names: set[str]) -> bool:
        lowered = {name.casefold() for name in names}
        return any(condition.name.casefold() in lowered for condition in self.conditions)

    def first_combat_action(self) -> Action | None:
        for action in self.actions:
            if action.kind in {"attack", "spell"}:
                return action
        return None

    def saving_throw_bonus(self, ability: str) -> int:
        return int(self.saving_throws.get(ability, 0))


@dataclass(slots=True)
class Encounter:
    name: str
    seed: int
    round_limit: int
    rules_version: str
    engine_version: str
    creatures: list[Creature]


class CombatEngine:
    def __init__(self, encounter: Encounter, spell_catalog: SpellCatalog) -> None:
        self.encounter = encounter
        self.spell_catalog = spell_catalog
        self.rng = random.Random(encounter.seed)
        self.round_number = 0
        self.event_log: list[dict[str, Any]] = []
        self.initiative_order: list[Creature] = []

    def log(self, event_type: str, **payload: Any) -> None:
        self.event_log.append(
            {
                "round": self.round_number,
                "event_type": event_type,
                **payload,
            }
        )

    def roll_d20(self, mode: Literal["normal", "advantage", "disadvantage"] = "normal") -> tuple[int, dict[str, Any]]:
        if mode == "normal":
            roll = self.rng.randint(1, 20)
            return roll, {"mode": mode, "rolls": [roll], "selected": roll}

        first = self.rng.randint(1, 20)
        second = self.rng.randint(1, 20)
        selected = max(first, second) if mode == "advantage" else min(first, second)
        return selected, {"mode": mode, "rolls": [first, second], "selected": selected}

    def roll_damage(self, expression: str, crit: bool = False) -> tuple[int, dict[str, Any]]:
        match = DICE_RE.fullmatch(expression)
        if not match:
            raise ValueError(f"Unsupported damage expression: {expression!r}")

        dice_count_text, die_size_text, modifier_text = match.groups()
        dice_count = int(dice_count_text) if dice_count_text else 1
        die_size = int(die_size_text)
        modifier = int(modifier_text.replace(" ", "")) if modifier_text else 0

        if crit:
            dice_count *= 2

        rolls = [self.rng.randint(1, die_size) for _ in range(dice_count)]
        total = sum(rolls) + modifier

        return total, {
            "expression": expression,
            "crit": crit,
            "dice_count": dice_count,
            "die_size": die_size,
            "rolls": rolls,
            "modifier": modifier,
            "total": total,
        }

    def determine_attack_roll_mode(
        self,
        attacker: Creature,
        target: Creature,
        action: ResolvedAction,
    ) -> Literal["normal", "advantage", "disadvantage"]:
        advantage = False
        disadvantage = False

        if attacker.has_any_condition(DISADVANTAGE_CONDITIONS):
            disadvantage = True

        if target.has_condition("prone") and action.is_melee:
            advantage = True

        if advantage and disadvantage:
            return "normal"
        if advantage:
            return "advantage"
        if disadvantage:
            return "disadvantage"
        return "normal"

    def choose_target(self, actor: Creature) -> Creature | None:
        enemies = [creature for creature in self.encounter.creatures if creature.alive and creature.team != actor.team]
        if not enemies:
            return None

        enemies.sort(key=lambda creature: (creature.current_hp, creature.ac, creature.id))
        return enemies[0]

    def terminal_state(self) -> tuple[bool, str | None]:
        alive_teams = sorted({creature.team for creature in self.encounter.creatures if creature.alive})
        if len(alive_teams) == 1:
            return True, alive_teams[0]
        if len(alive_teams) == 0:
            return True, None
        return False, None

    def roll_initiative(self) -> None:
        for creature in self.encounter.creatures:
            roll, detail = self.roll_d20("normal")
            creature.initiative = roll + creature.initiative_bonus
            self.log(
                "initiative_rolled",
                creature_id=creature.id,
                creature_name=creature.name,
                roll_detail=detail,
                initiative_bonus=creature.initiative_bonus,
                initiative_total=creature.initiative,
            )

        self.initiative_order = sorted(
            self.encounter.creatures,
            key=lambda creature: (-(creature.initiative or 0), -creature.initiative_bonus, creature.id),
        )

    def expire_end_of_turn_conditions(self, actor: Creature) -> None:
        kept: list[ActiveCondition] = []
        for condition in actor.conditions:
            if condition.rounds_remaining is None:
                kept.append(condition)
                continue

            new_value = condition.rounds_remaining - 1
            if new_value <= 0:
                self.log(
                    "condition_expired",
                    creature_id=actor.id,
                    creature_name=actor.name,
                    condition_name=condition.name,
                )
                continue

            kept.append(ActiveCondition(name=condition.name, rounds_remaining=new_value))

        actor.conditions = kept

    def apply_condition(self, target: Creature, name: str, rounds_remaining: int | None) -> None:
        target.conditions.append(ActiveCondition(name=name, rounds_remaining=rounds_remaining))
        self.log(
            "condition_applied",
            creature_id=target.id,
            creature_name=target.name,
            condition_name=name,
            rounds_remaining=rounds_remaining,
        )

    def resolve_spell_action(self, action: Action) -> ResolvedAction:
        if not action.spell_ref:
            raise SpellCatalogError(f"Spell action missing spell_ref: {action.id}")

        spell: SpellDefinition = self.spell_catalog.get(action.spell_ref)

        return ResolvedAction(
            id=action.id,
            name=action.name or spell.name,
            kind="spell",
            attack_bonus=action.attack_bonus_override if action.attack_bonus_override is not None else spell.attack_bonus,
            damage=action.damage_override if action.damage_override is not None else spell.damage,
            damage_type=spell.damage_type,
            is_melee=spell.is_melee,
            range_feet=spell.range_feet,
            resolution_mode=spell.resolution_mode,
            save_ability=spell.save_ability,
            save_dc=action.save_dc_override if action.save_dc_override is not None else spell.save_dc,
            half_damage_on_save=(
                action.half_damage_on_save_override
                if action.half_damage_on_save_override is not None
                else spell.half_damage_on_save
            ),
            condition_on_failed_save=(
                action.condition_on_failed_save_override
                if action.condition_on_failed_save_override is not None
                else spell.condition_on_failed_save
            ),
            condition_duration_rounds=(
                action.condition_duration_rounds_override
                if action.condition_duration_rounds_override is not None
                else spell.condition_duration_rounds
            ),
            spell_level=spell.level,
            school=spell.school,
            spell_ref=spell.id,
            source_id=spell.source_id,
            notes=action.notes if action.notes is not None else spell.notes,
        )

    def resolve_attack_action(self, action: Action) -> ResolvedAction:
        return ResolvedAction(
            id=action.id,
            name=action.name,
            kind="attack",
            attack_bonus=action.attack_bonus,
            damage=action.damage,
            damage_type=action.damage_type,
            is_melee=action.is_melee,
            range_feet=action.range_feet,
            resolution_mode="attack",
            notes=action.notes,
        )

    def resolve_runtime_action(self, action: Action) -> ResolvedAction:
        if action.kind == "attack":
            return self.resolve_attack_action(action)
        if action.kind == "spell":
            return self.resolve_spell_action(action)
        raise ValueError(f"Unsupported action kind: {action.kind}")

    def resolve_attack_like_action(self, attacker: Creature, target: Creature, action: ResolvedAction) -> None:
        if action.attack_bonus is None:
            self.log(
                "action_failed_invalid",
                attacker_id=attacker.id,
                attacker_name=attacker.name,
                target_id=target.id,
                target_name=target.name,
                reason="missing_attack_bonus",
                action=asdict(action),
            )
            return

        mode = self.determine_attack_roll_mode(attacker, target, action)
        attack_roll, attack_detail = self.roll_d20(mode)
        attack_total = attack_roll + action.attack_bonus

        natural_one = attack_roll == 1
        natural_twenty = attack_roll == 20

        if natural_one:
            hit = False
            crit = False
        elif natural_twenty:
            hit = True
            crit = True
        else:
            hit = attack_total >= target.ac
            crit = False

        self.log(
            "attack_declared",
            attacker_id=attacker.id,
            attacker_name=attacker.name,
            target_id=target.id,
            target_name=target.name,
            action=asdict(action),
        )

        if not hit:
            self.log(
                "attack_resolved",
                attacker_id=attacker.id,
                attacker_name=attacker.name,
                target_id=target.id,
                target_name=target.name,
                result="miss",
                attack_roll_detail=attack_detail,
                attack_bonus=action.attack_bonus,
                attack_total=attack_total,
                target_ac=target.ac,
                action_kind=action.kind,
            )
            return

        if action.damage is None:
            self.log(
                "attack_resolved",
                attacker_id=attacker.id,
                attacker_name=attacker.name,
                target_id=target.id,
                target_name=target.name,
                result="hit_no_damage_expression",
                attack_roll_detail=attack_detail,
                attack_bonus=action.attack_bonus,
                attack_total=attack_total,
                target_ac=target.ac,
                action_kind=action.kind,
            )
            return

        damage_total, damage_detail = self.roll_damage(action.damage, crit=crit)
        old_hp = target.current_hp
        target.current_hp = max(0, target.current_hp - damage_total)

        self.log(
            "attack_resolved",
            attacker_id=attacker.id,
            attacker_name=attacker.name,
            target_id=target.id,
            target_name=target.name,
            result="critical_hit" if crit else "hit",
            attack_roll_detail=attack_detail,
            attack_bonus=action.attack_bonus,
            attack_total=attack_total,
            target_ac=target.ac,
            damage_detail=damage_detail,
            target_hp_before=old_hp,
            target_hp_after=target.current_hp,
            action_kind=action.kind,
        )

        if not target.alive:
            self.log(
                "creature_defeated",
                creature_id=target.id,
                creature_name=target.name,
                defeated_by_id=attacker.id,
                defeated_by_name=attacker.name,
            )

    def resolve_save_spell(self, caster: Creature, target: Creature, action: ResolvedAction) -> None:
        if action.save_ability not in ABILITIES:
            self.log(
                "action_failed_invalid",
                attacker_id=caster.id,
                attacker_name=caster.name,
                target_id=target.id,
                target_name=target.name,
                reason="invalid_or_missing_save_ability",
                action=asdict(action),
            )
            return

        if action.save_dc is None:
            self.log(
                "action_failed_invalid",
                attacker_id=caster.id,
                attacker_name=caster.name,
                target_id=target.id,
                target_name=target.name,
                reason="missing_save_dc",
                action=asdict(action),
            )
            return

        save_roll, save_roll_detail = self.roll_d20("normal")
        save_bonus = target.saving_throw_bonus(action.save_ability)
        save_total = save_roll + save_bonus
        save_succeeds = save_total >= action.save_dc

        self.log(
            "saving_throw_resolved",
            caster_id=caster.id,
            caster_name=caster.name,
            target_id=target.id,
            target_name=target.name,
            save_ability=action.save_ability,
            save_dc=action.save_dc,
            save_roll_detail=save_roll_detail,
            save_bonus=save_bonus,
            save_total=save_total,
            success=save_succeeds,
            action=asdict(action),
        )

        damage_total = 0
        damage_detail: dict[str, Any] | None = None
        old_hp = target.current_hp

        if action.damage:
            rolled_damage, rolled_damage_detail = self.roll_damage(action.damage, crit=False)
            damage_detail = rolled_damage_detail

            if save_succeeds:
                damage_total = rolled_damage // 2 if action.half_damage_on_save else 0
            else:
                damage_total = rolled_damage

            target.current_hp = max(0, target.current_hp - damage_total)

        if not save_succeeds and action.condition_on_failed_save:
            self.apply_condition(target, action.condition_on_failed_save, action.condition_duration_rounds)

        self.log(
            "spell_resolved",
            caster_id=caster.id,
            caster_name=caster.name,
            target_id=target.id,
            target_name=target.name,
            spell_ref=action.spell_ref,
            source_id=action.source_id,
            resolution_mode="save",
            result="save_success" if save_succeeds else "save_failed",
            damage_rolled=damage_detail["total"] if damage_detail else 0,
            damage_applied=damage_total,
            damage_detail=damage_detail,
            target_hp_before=old_hp,
            target_hp_after=target.current_hp,
            condition_applied=action.condition_on_failed_save if (not save_succeeds and action.condition_on_failed_save) else None,
        )

        if not target.alive:
            self.log(
                "creature_defeated",
                creature_id=target.id,
                creature_name=target.name,
                defeated_by_id=caster.id,
                defeated_by_name=caster.name,
            )

    def resolve_action(self, actor: Creature, target: Creature, action: Action) -> None:
        try:
            runtime_action = self.resolve_runtime_action(action)
        except SpellCatalogError as exc:
            self.log(
                "action_failed_invalid",
                attacker_id=actor.id,
                attacker_name=actor.name,
                target_id=target.id,
                target_name=target.name,
                reason=str(exc),
                action=asdict(action),
            )
            return

        if runtime_action.kind == "attack":
            self.resolve_attack_like_action(actor, target, runtime_action)
            return

        if runtime_action.kind == "spell":
            if runtime_action.resolution_mode == "attack":
                self.resolve_attack_like_action(actor, target, runtime_action)
                return

            if runtime_action.resolution_mode == "save":
                self.resolve_save_spell(actor, target, runtime_action)
                return

        self.log(
            "turn_skipped_unsupported_action",
            creature_id=actor.id,
            creature_name=actor.name,
            target_id=target.id,
            target_name=target.name,
            action=asdict(runtime_action),
        )

    def take_turn(self, actor: Creature) -> None:
        if not actor.alive:
            self.log(
                "turn_skipped_defeated",
                creature_id=actor.id,
                creature_name=actor.name,
            )
            return

        if actor.has_any_condition(HARD_DISABLE_CONDITIONS):
            self.log(
                "turn_skipped_disabled",
                creature_id=actor.id,
                creature_name=actor.name,
                active_conditions=[asdict(condition) for condition in actor.conditions],
            )
            self.expire_end_of_turn_conditions(actor)
            return

        self.log(
            "turn_started",
            creature_id=actor.id,
            creature_name=actor.name,
            current_hp=actor.current_hp,
            conditions=[asdict(condition) for condition in actor.conditions],
        )

        action = actor.first_combat_action()
        if action is None:
            self.log(
                "turn_skipped_no_action",
                creature_id=actor.id,
                creature_name=actor.name,
            )
            self.expire_end_of_turn_conditions(actor)
            return

        target = self.choose_target(actor)
        if target is None:
            self.log(
                "turn_skipped_no_target",
                creature_id=actor.id,
                creature_name=actor.name,
            )
            self.expire_end_of_turn_conditions(actor)
            return

        self.resolve_action(actor, target, action)
        self.expire_end_of_turn_conditions(actor)

    def run(self) -> dict[str, Any]:
        self.log(
            "encounter_started",
            encounter_name=self.encounter.name,
            seed=self.encounter.seed,
            rules_version=self.encounter.rules_version,
            engine_version=self.encounter.engine_version,
        )

        self.roll_initiative()

        finished, winner = self.terminal_state()
        if finished:
            self.log("encounter_ended", winner=winner, reason="single_team_after_init")
            return self.build_result(winner=winner, reason="single_team_after_init")

        for round_number in range(1, self.encounter.round_limit + 1):
            self.round_number = round_number
            self.log("round_started", round_number=round_number)

            for actor in self.initiative_order:
                finished, winner = self.terminal_state()
                if finished:
                    reason = "winner_found"
                    self.log("encounter_ended", winner=winner, reason=reason)
                    return self.build_result(winner=winner, reason=reason)

                self.take_turn(actor)

            finished, winner = self.terminal_state()
            if finished:
                reason = "winner_found_end_of_round"
                self.log("encounter_ended", winner=winner, reason=reason)
                return self.build_result(winner=winner, reason=reason)

        alive_teams = sorted({creature.team for creature in self.encounter.creatures if creature.alive})
        reason = "round_limit_reached"
        winner_after_limit = alive_teams[0] if len(alive_teams) == 1 else None
        self.log("encounter_ended", winner=winner_after_limit, reason=reason)
        return self.build_result(winner=winner_after_limit, reason=reason)

    def build_result(self, winner: str | None, reason: str) -> dict[str, Any]:
        return {
            "encounter_name": self.encounter.name,
            "seed": self.encounter.seed,
            "rules_version": self.encounter.rules_version,
            "engine_version": self.encounter.engine_version,
            "winner": winner,
            "reason": reason,
            "final_state": [
                {
                    "id": creature.id,
                    "name": creature.name,
                    "team": creature.team,
                    "ac": creature.ac,
                    "max_hp": creature.max_hp,
                    "current_hp": creature.current_hp,
                    "initiative": creature.initiative,
                    "saving_throws": creature.saving_throws,
                    "conditions": [asdict(condition) for condition in creature.conditions],
                }
                for creature in self.encounter.creatures
            ],
            "event_log": self.event_log,
        }


def load_action(data: dict[str, Any]) -> Action:
    return Action(
        id=str(data["id"]),
        name=str(data["name"]),
        kind=str(data["kind"]),
        attack_bonus=int(data["attack_bonus"]) if data.get("attack_bonus") is not None else None,
        damage=str(data["damage"]) if data.get("damage") is not None else None,
        damage_type=str(data.get("damage_type", "untyped")),
        is_melee=bool(data.get("is_melee", True)),
        range_feet=int(data.get("range_feet", 5)),
        spell_ref=str(data["spell_ref"]) if data.get("spell_ref") is not None else None,
        attack_bonus_override=int(data["attack_bonus_override"]) if data.get("attack_bonus_override") is not None else None,
        save_dc_override=int(data["save_dc_override"]) if data.get("save_dc_override") is not None else None,
        damage_override=str(data["damage_override"]) if data.get("damage_override") is not None else None,
        half_damage_on_save_override=(
            bool(data["half_damage_on_save_override"])
            if data.get("half_damage_on_save_override") is not None
            else None
        ),
        condition_on_failed_save_override=(
            str(data["condition_on_failed_save_override"])
            if data.get("condition_on_failed_save_override") is not None
            else None
        ),
        condition_duration_rounds_override=(
            int(data["condition_duration_rounds_override"])
            if data.get("condition_duration_rounds_override") is not None
            else None
        ),
        notes=str(data["notes"]) if data.get("notes") is not None else None,
    )


def load_condition(data: dict[str, Any]) -> ActiveCondition:
    return ActiveCondition(
        name=str(data["name"]),
        rounds_remaining=int(data["rounds_remaining"]) if data.get("rounds_remaining") is not None else None,
    )


def load_creature(data: dict[str, Any]) -> Creature:
    saving_throws_raw = dict(data.get("saving_throws", {}))
    saving_throws = {ability: int(saving_throws_raw.get(ability, 0)) for ability in sorted(ABILITIES)}

    return Creature(
        id=str(data["id"]),
        name=str(data["name"]),
        team=str(data["team"]),
        ac=int(data["ac"]),
        max_hp=int(data["max_hp"]),
        current_hp=int(data["current_hp"]),
        initiative_bonus=int(data["initiative_bonus"]),
        saving_throws=saving_throws,
        actions=[load_action(action) for action in data["actions"]],
        conditions=[load_condition(condition) for condition in data.get("conditions", [])],
        speed_feet=int(data.get("speed_feet", 30)),
        notes=str(data["notes"]) if data.get("notes") is not None else None,
    )


def load_encounter_from_dict(data: dict[str, Any]) -> Encounter:
    return Encounter(
        name=str(data["name"]),
        seed=int(data["seed"]),
        round_limit=int(data["round_limit"]),
        rules_version=str(data.get("rules_version", "5.2.1")),
        engine_version=str(data.get("engine_version", "0.3.0")),
        creatures=[load_creature(creature) for creature in data["creatures"]],
    )


def demo_encounter_dict() -> dict[str, Any]:
    return {
        "name": "Built-in Spell Catalog Demo",
        "seed": 1337,
        "round_limit": 10,
        "rules_version": "5.2.1",
        "engine_version": "0.3.0",
        "creatures": [
            {
                "id": "fighter_1",
                "name": "Human Fighter",
                "team": "heroes",
                "ac": 16,
                "max_hp": 20,
                "current_hp": 20,
                "initiative_bonus": 2,
                "saving_throws": {
                    "str": 4,
                    "dex": 1,
                    "con": 3,
                    "int": 0,
                    "wis": 1,
                    "cha": 0,
                },
                "actions": [
                    {
                        "id": "longsword",
                        "name": "Longsword",
                        "kind": "attack",
                        "attack_bonus": 5,
                        "damage": "1d8+3",
                        "damage_type": "slashing",
                        "is_melee": True,
                        "range_feet": 5,
                    }
                ],
                "conditions": [],
            },
            {
                "id": "wizard_1",
                "name": "Elf Wizard",
                "team": "heroes",
                "ac": 12,
                "max_hp": 14,
                "current_hp": 14,
                "initiative_bonus": 3,
                "saving_throws": {
                    "str": -1,
                    "dex": 3,
                    "con": 1,
                    "int": 5,
                    "wis": 2,
                    "cha": 0,
                },
                "actions": [
                    {
                        "id": "cast_fire_bolt",
                        "name": "Cast Fire Bolt",
                        "kind": "spell",
                        "spell_ref": "spell.fire_bolt",
                        "attack_bonus_override": 5,
                    }
                ],
                "conditions": [],
            },
            {
                "id": "goblin_1",
                "name": "Goblin Raider",
                "team": "goblins",
                "ac": 15,
                "max_hp": 7,
                "current_hp": 7,
                "initiative_bonus": 2,
                "saving_throws": {
                    "str": -1,
                    "dex": 2,
                    "con": 0,
                    "int": -1,
                    "wis": 0,
                    "cha": -1,
                },
                "actions": [
                    {
                        "id": "scimitar",
                        "name": "Scimitar",
                        "kind": "attack",
                        "attack_bonus": 4,
                        "damage": "1d6+2",
                        "damage_type": "slashing",
                        "is_melee": True,
                        "range_feet": 5,
                    }
                ],
                "conditions": [],
            },
            {
                "id": "shaman_1",
                "name": "Goblin Shaman",
                "team": "goblins",
                "ac": 13,
                "max_hp": 10,
                "current_hp": 10,
                "initiative_bonus": 1,
                "saving_throws": {
                    "str": -1,
                    "dex": 1,
                    "con": 0,
                    "int": 1,
                    "wis": 2,
                    "cha": 0,
                },
                "actions": [
                    {
                        "id": "cast_acid_splash",
                        "name": "Cast Acid Splash",
                        "kind": "spell",
                        "spell_ref": "spell.acid_splash",
                        "save_dc_override": 12,
                    }
                ],
                "conditions": [],
            },
        ],
    }


def print_summary(result: dict[str, Any]) -> None:
    print(f"Encounter: {result['encounter_name']}")
    print(f"Seed: {result['seed']}")
    print(f"Winner: {result['winner']}")
    print(f"Reason: {result['reason']}")
    print()
    print("Final State:")
    for creature in result["final_state"]:
        print(
            f"  - {creature['name']} [{creature['team']}] "
            f"HP={creature['current_hp']}/{creature['max_hp']} "
            f"AC={creature['ac']} INIT={creature['initiative']}"
        )
    print()
    print("Event Log:")
    for event in result["event_log"]:
        event_type = event["event_type"]
        round_number = event["round"]

        if event_type == "round_started":
            print(f"[Round {round_number}] --- round started ---")
        elif event_type == "initiative_rolled":
            print(
                f"[Init] {event['creature_name']} rolled "
                f"{event['roll_detail']['selected']} + {event['initiative_bonus']} = {event['initiative_total']}"
            )
        elif event_type == "turn_started":
            print(f"[Round {round_number}] {event['creature_name']} starts turn at {event['current_hp']} HP")
        elif event_type == "attack_resolved":
            if event["result"] == "miss":
                print(
                    f"[Round {round_number}] {event['attacker_name']} misses {event['target_name']} "
                    f"({event['attack_total']} vs AC {event['target_ac']})"
                )
            else:
                print(
                    f"[Round {round_number}] {event['attacker_name']} {event['result'].replace('_', ' ')} "
                    f"{event['target_name']} for {event['damage_detail']['total']} damage "
                    f"({event['target_hp_before']} -> {event['target_hp_after']})"
                )
        elif event_type == "saving_throw_resolved":
            outcome = "succeeds" if event["success"] else "fails"
            print(
                f"[Round {round_number}] {event['target_name']} {outcome} "
                f"{event['save_ability'].upper()} save "
                f"({event['save_total']} vs DC {event['save_dc']})"
            )
        elif event_type == "spell_resolved":
            print(
                f"[Round {round_number}] {event['caster_name']} resolves {event['spell_ref']} on "
                f"{event['target_name']} for {event['damage_applied']} damage "
                f"({event['target_hp_before']} -> {event['target_hp_after']})"
            )
        elif event_type == "condition_applied":
            print(
                f"[Round {round_number}] {event['creature_name']} gains {event['condition_name']} "
                f"for {event['rounds_remaining']} round(s)"
            )
        elif event_type == "creature_defeated":
            print(f"[Round {round_number}] {event['creature_name']} is defeated")
        elif event_type == "condition_expired":
            print(f"[Round {round_number}] {event['creature_name']}: {event['condition_name']} expired")
        elif event_type == "encounter_ended":
            print(f"[End] winner={event['winner']} reason={event['reason']}")


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    default_schema_dir = (project_root / "schemas").resolve()
    default_rules_data_dir = (project_root / "rules_data").resolve()

    parser = argparse.ArgumentParser(description="Deterministic D&D-style combat simulator starter engine.")
    parser.add_argument(
        "encounter",
        nargs="?",
        help="Path to encounter JSON. If omitted, the built-in demo encounter is used.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Explicitly use the built-in demo encounter.",
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=default_schema_dir,
        help=f"Directory containing schema files. Default: {default_schema_dir}",
    )
    parser.add_argument(
        "--rules-data-dir",
        type=Path,
        default=default_rules_data_dir,
        help=f"Directory containing rules registry and catalogs. Default: {default_rules_data_dir}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON result instead of a text summary.",
    )
    parser.add_argument(
        "--write-log",
        type=Path,
        help="Write the full JSON result to a file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.encounter and not args.demo:
        try:
            raw_data = json.loads(Path(args.encounter).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"Failed to read encounter file: {exc}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}", file=sys.stderr)
            return 1
    else:
        raw_data = demo_encounter_dict()

    try:
        validate_encounter_data(raw_data, args.schema_dir)
    except EncounterSchemaError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        registry = load_rules_registry(args.rules_data_dir)
        spell_catalog = load_spell_catalogs(registry)
    except (RulesRegistryError, SpellCatalogError) as exc:
        print(f"Rules data load failed: {exc}", file=sys.stderr)
        return 3

    encounter = load_encounter_from_dict(raw_data)
    engine = CombatEngine(encounter, spell_catalog)
    result = engine.run()

    if args.write_log:
        args.write_log.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_summary(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
