from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from condition_catalog import ConditionCatalog, ConditionCatalogError, load_condition_catalog
from policies import (
    ActionPolicy,
    BestDamagePolicy,
    FirstActionPolicy,
    FocusFirePolicy,
    LowestACPolicy,
    LowestHPPolicy,
    RandomPolicy,
    SpellFirstPolicy,
    TargetPolicy,
)
from rules_registry import RulesRegistryError, load_rules_registry
from schema_loader import EncounterSchemaError, validate_encounter_data
from spell_catalog import SpellCatalog, SpellCatalogError, SpellDefinition, load_spell_catalogs


DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$")
ABILITIES = {"str", "dex", "con", "int", "wis", "cha"}
HARD_DISABLE_CONDITIONS = {"unconscious", "paralyzed", "stunned", "incapacitated"}
DISADVANTAGE_CONDITIONS = {"poisoned", "blinded"}
ADVANTAGE_ON_ATTACKS_AGAINST_CONDITIONS = {"restrained", "stunned", "paralyzed", "unconscious"}
AUTO_FAIL_SAVE_CONDITIONS = {"paralyzed", "stunned", "unconscious", "petrified"}


class CombatEngineError(ValueError):
    pass


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
    economy_slot: str = "action"
    sub_actions: list[str] = field(default_factory=list)
    attack_bonus_override: int | None = None
    save_dc_override: int | None = None
    damage_override: str | None = None
    half_damage_on_save_override: bool | None = None
    condition_on_failed_save_override: str | None = None
    condition_duration_rounds_override: int | None = None
    upcast_to_level: int | None = None
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
    economy_slot: str = "action"
    notes: str | None = None
    requires_concentration: bool = False
    aoe_shape: str | None = None
    aoe_size_feet: int | None = None


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
    ability_scores: dict[str, int] = field(default_factory=lambda: {ability: 10 for ability in sorted(ABILITIES)})
    proficiency_bonus: int = 2
    level: int = 0
    spell_slots: dict[int, int] = field(default_factory=dict)
    spell_slot_max: dict[int, int] = field(default_factory=dict)
    concentration_spell: str | None = None
    action_used: bool = False
    bonus_action_used: bool = False
    reaction_used: bool = False
    damage_immunities: list[str] = field(default_factory=list)
    damage_resistances: list[str] = field(default_factory=list)
    damage_vulnerabilities: list[str] = field(default_factory=list)
    hit_dice_remaining: int = 0
    hit_die: int = 0
    death_save_successes: int = 0
    death_save_failures: int = 0
    stable: bool = False
    dead: bool = False
    exhaustion_level: int = 0
    charmed_by: list[str] = field(default_factory=list)
    focused_target_id: str | None = None
    on_take_damage_hooks: list[str] = field(default_factory=list)
    on_creature_attacked_nearby_hooks: list[str] = field(default_factory=list)
    initiative: int | None = None

    @property
    def alive(self) -> bool:
        return self.current_hp > 0 and not self.dead

    @property
    def dying(self) -> bool:
        return self.current_hp <= 0 and not self.dead and not self.stable

    def has_condition(self, condition_name: str) -> bool:
        wanted = condition_name.casefold()
        return any(condition.name.casefold() == wanted for condition in self.conditions)

    def has_any_condition(self, names: set[str]) -> bool:
        lowered = {name.casefold() for name in names}
        return any(condition.name.casefold() in lowered for condition in self.conditions)

    def first_combat_action(self) -> Action | None:
        for action in self.actions:
            if action.kind in {"attack", "spell", "multiattack"}:
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
    def __init__(
        self,
        encounter: Encounter,
        spell_catalog: SpellCatalog,
        condition_catalog: ConditionCatalog | None = None,
        target_policy: TargetPolicy | None = None,
        action_policy: ActionPolicy | None = None,
    ) -> None:
        self.encounter = encounter
        self.spell_catalog = spell_catalog
        self.condition_catalog = condition_catalog
        self.target_policy = target_policy or LowestHPPolicy()
        self.action_policy = action_policy or FirstActionPolicy()
        self.rng = random.Random(encounter.seed)
        self.round_number = 0
        self.event_log: list[dict[str, Any]] = []
        self.initiative_order: list[Creature] = []
        self._initiative_coin_flip: dict[str, float] = {}
        self._validate_initial_conditions()

    def log(self, event_type: str, **payload: Any) -> None:
        self.event_log.append(
            {
                "round": self.round_number,
                "event_type": event_type,
                **payload,
            }
        )

    def _normalize_condition_name(self, condition_name: str) -> str:
        return condition_name.strip().casefold()

    def _validate_condition_name(self, condition_name: str) -> bool:
        if self.condition_catalog is None:
            return True
        return self.condition_catalog.has_name(condition_name)

    def _validate_initial_conditions(self) -> None:
        if self.condition_catalog is None:
            return

        for creature in self.encounter.creatures:
            for condition in creature.conditions:
                if not self._validate_condition_name(condition.name):
                    raise CombatEngineError(
                        f"Unknown condition in encounter creature '{creature.id}': {condition.name}"
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

        if attacker.has_any_condition({"restrained", "frightened", "prone"}):
            disadvantage = True

        if attacker.has_condition("invisible"):
            advantage = True

        if target.has_condition("prone") and action.is_melee:
            advantage = True
        if target.has_condition("prone") and not action.is_melee:
            disadvantage = True

        if target.has_condition("blinded"):
            advantage = True

        if target.has_any_condition(ADVANTAGE_ON_ATTACKS_AGAINST_CONDITIONS):
            advantage = True

        if target.has_condition("invisible"):
            disadvantage = True

        if advantage and disadvantage:
            return "normal"
        if advantage:
            return "advantage"
        if disadvantage:
            return "disadvantage"
        return "normal"

    def _auto_fail_save(self, target: Creature, ability: str) -> bool:
        if ability not in {"str", "dex"}:
            return False
        return target.has_any_condition(AUTO_FAIL_SAVE_CONDITIONS)

    def _can_target(self, actor: Creature, target: Creature) -> bool:
        # If charmed, attacker cannot target creatures it is charmed by.
        if actor.has_condition("charmed") and target.id in {item.strip() for item in actor.charmed_by}:
            return False
        return True

    def choose_target(self, actor: Creature) -> Creature | None:
        enemies = [
            creature
            for creature in self.encounter.creatures
            if creature.alive and creature.team != actor.team and self._can_target(actor, creature)
        ]
        if not enemies:
            return None
        return self.target_policy.select_target(self, actor, enemies)

    def choose_action(self, actor: Creature) -> Action | None:
        return self.action_policy.select_action(self, actor)

    def choose_targets(self, actor: Creature, action: ResolvedAction, primary_target: Creature | None) -> list[Creature]:
        enemies = [
            creature
            for creature in self.encounter.creatures
            if creature.alive and creature.team != actor.team and self._can_target(actor, creature)
        ]
        enemies.sort(key=lambda creature: (creature.current_hp, creature.ac, creature.id))

        if not enemies:
            return []

        if not action.aoe_shape:
            return [primary_target] if primary_target is not None else [enemies[0]]

        shape = action.aoe_shape.casefold()
        if shape in {"sphere", "cylinder", "cube", "emanation"}:
            return enemies
        if shape in {"line", "cone"}:
            return enemies[: min(2, len(enemies))]

        return [primary_target] if primary_target is not None else [enemies[0]]

    def _normalize_damage_terms(self, values: list[str]) -> set[str]:
        return {str(value).strip().casefold() for value in values if str(value).strip()}

    def apply_damage(self, target: Creature, amount: int, damage_type: str | None) -> tuple[int, str | None]:
        if amount <= 0:
            return 0, None

        damage_key = (damage_type or "untyped").strip().casefold()
        immunities = self._normalize_damage_terms(target.damage_immunities)
        resistances = self._normalize_damage_terms(target.damage_resistances)
        vulnerabilities = self._normalize_damage_terms(target.damage_vulnerabilities)

        if damage_key in immunities:
            return 0, "immunity"
        if target.has_condition("petrified"):
            return amount // 2, "petrified_condition"
        if damage_key in resistances:
            return amount // 2, "resistance"
        if damage_key in vulnerabilities:
            return amount * 2, "vulnerability"
        return amount, None

    def _constitution_modifier(self, creature: Creature) -> int:
        con_score = int(creature.ability_scores.get("con", 10))
        return (con_score - 10) // 2

    def roll_concentration_check(self, creature: Creature, damage_taken: int) -> bool:
        if not creature.concentration_spell:
            return True

        dc = max(10, damage_taken // 2)
        roll, detail = self.roll_d20("normal")
        total = roll + creature.saving_throw_bonus("con")
        passed = total >= dc

        self.log(
            "concentration_check_resolved",
            creature_id=creature.id,
            creature_name=creature.name,
            concentration_spell=creature.concentration_spell,
            dc=dc,
            roll_detail=detail,
            total=total,
            success=passed,
        )

        if not passed:
            old_spell = creature.concentration_spell
            creature.concentration_spell = None
            self.log(
                "concentration_broken",
                creature_id=creature.id,
                creature_name=creature.name,
                spell_ref=old_spell,
                reason="failed_concentration_check",
            )

        return passed

    def _mark_zero_hp_state(self, target: Creature, source: Creature, damage_taken: int) -> None:
        if target.current_hp > 0:
            return

        # Massive damage: if a single hit equals/exceeds max HP, creature dies outright.
        if damage_taken >= target.max_hp:
            target.dead = True
            target.stable = False
            self.log(
                "creature_died",
                creature_id=target.id,
                creature_name=target.name,
                reason="massive_damage",
                defeated_by_id=source.id,
                defeated_by_name=source.name,
            )
            return

        target.stable = False
        target.death_save_successes = 0
        target.death_save_failures = 0
        target.current_hp = 0
        self.log(
            "creature_defeated",
            creature_id=target.id,
            creature_name=target.name,
            defeated_by_id=source.id,
            defeated_by_name=source.name,
        )

    def _reset_turn_budget(self, actor: Creature) -> None:
        actor.action_used = False
        actor.bonus_action_used = False

    def _slot_available(self, actor: Creature, economy_slot: str) -> bool:
        if economy_slot == "action":
            return not actor.action_used
        if economy_slot == "bonus_action":
            return not actor.bonus_action_used
        if economy_slot == "reaction":
            return not actor.reaction_used
        return True

    def _consume_slot(self, actor: Creature, economy_slot: str) -> None:
        if economy_slot == "action":
            actor.action_used = True
        elif economy_slot == "bonus_action":
            actor.bonus_action_used = True
        elif economy_slot == "reaction":
            actor.reaction_used = True

    def _resolve_death_save(self, actor: Creature) -> None:
        roll, detail = self.roll_d20("normal")

        if roll == 20:
            actor.current_hp = 1
            actor.death_save_successes = 0
            actor.death_save_failures = 0
            actor.stable = False
            self.log(
                "death_save_rolled",
                creature_id=actor.id,
                creature_name=actor.name,
                roll_detail=detail,
                result="nat20_revive",
            )
            return

        if roll == 1:
            actor.death_save_failures += 2
        elif roll >= 10:
            actor.death_save_successes += 1
        else:
            actor.death_save_failures += 1

        self.log(
            "death_save_rolled",
            creature_id=actor.id,
            creature_name=actor.name,
            roll_detail=detail,
            successes=actor.death_save_successes,
            failures=actor.death_save_failures,
        )

        if actor.death_save_successes >= 3:
            actor.stable = True
            self.log(
                "creature_stabilized",
                creature_id=actor.id,
                creature_name=actor.name,
            )
        elif actor.death_save_failures >= 3:
            actor.dead = True
            self.log(
                "creature_died",
                creature_id=actor.id,
                creature_name=actor.name,
                reason="death_save_failures",
            )

    def _consume_spell_slot(self, caster: Creature, slot_level: int | None) -> bool:
        if slot_level is None or slot_level <= 0:
            return True

        remaining = int(caster.spell_slots.get(slot_level, 0))
        if remaining <= 0:
            return False

        caster.spell_slots[slot_level] = remaining - 1
        self.log(
            "spell_slot_expended",
            creature_id=caster.id,
            creature_name=caster.name,
            slot_level=slot_level,
            remaining=caster.spell_slots[slot_level],
        )
        return True

    def terminal_state(self) -> tuple[bool, str | None]:
        alive_teams = sorted({creature.team for creature in self.encounter.creatures if creature.alive})
        if len(alive_teams) == 1:
            return True, alive_teams[0]
        if len(alive_teams) == 0:
            return True, None
        return False, None

    def roll_initiative(self) -> None:
        self._initiative_coin_flip = {}
        for creature in self.encounter.creatures:
            roll, detail = self.roll_d20("normal")
            creature.initiative = roll + creature.initiative_bonus
            self._initiative_coin_flip[creature.id] = self.rng.random()
            self.log(
                "initiative_rolled",
                creature_id=creature.id,
                creature_name=creature.name,
                roll_detail=detail,
                initiative_bonus=creature.initiative_bonus,
                initiative_total=creature.initiative,
                dex_score=int(creature.ability_scores.get("dex", 10)),
                tie_break_coin=self._initiative_coin_flip[creature.id],
            )

        self.initiative_order = sorted(
            self.encounter.creatures,
            key=lambda creature: (
                -(creature.initiative or 0),
                -creature.initiative_bonus,
                -int(creature.ability_scores.get("dex", 10)),
                self._initiative_coin_flip.get(creature.id, 0.0),
                creature.id,
            ),
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
        if not self._validate_condition_name(name):
            self.log(
                "condition_rejected_unknown",
                creature_id=target.id,
                creature_name=target.name,
                condition_name=name,
            )
            return

        condition_id = None
        condition_source_id = None
        canonical_name = name
        if self.condition_catalog is not None:
            try:
                definition = self.condition_catalog.by_name(name)
            except ConditionCatalogError:
                definition = None
            if definition is not None:
                condition_id = definition.id
                condition_source_id = definition.source_id
                canonical_name = definition.name

        target.conditions.append(ActiveCondition(name=canonical_name, rounds_remaining=rounds_remaining))
        self.log(
            "condition_applied",
            creature_id=target.id,
            creature_name=target.name,
            condition_name=canonical_name,
            condition_id=condition_id,
            condition_source_id=condition_source_id,
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
            economy_slot=action.economy_slot,
            notes=action.notes if action.notes is not None else spell.notes,
            requires_concentration=spell.requires_concentration,
            aoe_shape=spell.aoe_shape,
            aoe_size_feet=spell.aoe_size_feet,
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
            economy_slot=action.economy_slot,
            notes=action.notes,
        )

    def resolve_runtime_action(self, action: Action) -> ResolvedAction:
        if action.kind == "attack":
            return self.resolve_attack_action(action)
        if action.kind == "spell":
            return self.resolve_spell_action(action)
        raise ValueError(f"Unsupported action kind: {action.kind}")

    def _resolve_multiattack(self, actor: Creature, target: Creature, action: Action) -> None:
        if not action.sub_actions:
            self.log(
                "action_failed_invalid",
                attacker_id=actor.id,
                attacker_name=actor.name,
                target_id=target.id,
                target_name=target.name,
                reason="multiattack_missing_sub_actions",
                action=asdict(action),
            )
            return

        by_id = {candidate.id: candidate for candidate in actor.actions}
        for sub_action_id in action.sub_actions:
            sub_action = by_id.get(sub_action_id)
            if sub_action is None:
                self.log(
                    "action_failed_invalid",
                    attacker_id=actor.id,
                    attacker_name=actor.name,
                    target_id=target.id,
                    target_name=target.name,
                    reason=f"unknown_multiattack_sub_action:{sub_action_id}",
                    action=asdict(action),
                )
                continue

            if not target.alive:
                target = self.choose_target(actor) or target
            if not target.alive:
                break

            if sub_action.kind == "multiattack":
                self.log(
                    "action_failed_invalid",
                    attacker_id=actor.id,
                    attacker_name=actor.name,
                    target_id=target.id,
                    target_name=target.name,
                    reason="multiattack_cannot_nest",
                    action=asdict(sub_action),
                )
                continue

            self.resolve_action(actor, target, sub_action)

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

        if hit and action.is_melee and action.range_feet <= 5 and target.has_any_condition({"paralyzed", "unconscious"}):
            crit = True

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
        damage_applied, modifier_reason = self.apply_damage(target, damage_total, action.damage_type)
        old_hp = target.current_hp
        target.current_hp = max(0, target.current_hp - damage_applied)

        if damage_applied > 0:
            self.roll_concentration_check(target, damage_applied)

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
            damage_modifier=modifier_reason,
            damage_applied=damage_applied,
            target_hp_before=old_hp,
            target_hp_after=target.current_hp,
            action_kind=action.kind,
            economy_slot=action.economy_slot,
        )

        self._mark_zero_hp_state(target, attacker, damage_applied)

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

        auto_fail = self._auto_fail_save(target, action.save_ability)
        if auto_fail:
            save_roll = 1
            save_roll_detail = {"mode": "auto_fail", "rolls": [1], "selected": 1}
            save_bonus = target.saving_throw_bonus(action.save_ability)
            save_total = 1 + save_bonus
            save_succeeds = False
        else:
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
            auto_failed=auto_fail,
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

            damage_total, modifier_reason = self.apply_damage(target, damage_total, action.damage_type)
            target.current_hp = max(0, target.current_hp - damage_total)
        else:
            modifier_reason = None

        if damage_total > 0:
            self.roll_concentration_check(target, damage_total)

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
            damage_modifier=modifier_reason,
            damage_detail=damage_detail,
            target_hp_before=old_hp,
            target_hp_after=target.current_hp,
            condition_applied=action.condition_on_failed_save if (not save_succeeds and action.condition_on_failed_save) else None,
            economy_slot=action.economy_slot,
        )

        self._mark_zero_hp_state(target, caster, damage_total)

    def resolve_action(self, actor: Creature, target: Creature, action: Action) -> None:
        if action.kind == "multiattack":
            self._resolve_multiattack(actor, target, action)
            return

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
            if not self._consume_spell_slot(actor, runtime_action.spell_level):
                self.log(
                    "spell_failed_no_slots",
                    creature_id=actor.id,
                    creature_name=actor.name,
                    spell_ref=runtime_action.spell_ref,
                    required_level=runtime_action.spell_level,
                )
                return

            if runtime_action.requires_concentration:
                if actor.concentration_spell and actor.concentration_spell != runtime_action.spell_ref:
                    self.log(
                        "concentration_broken",
                        creature_id=actor.id,
                        creature_name=actor.name,
                        spell_ref=actor.concentration_spell,
                        reason="new_concentration_spell_cast",
                    )
                actor.concentration_spell = runtime_action.spell_ref

            targets = self.choose_targets(actor, runtime_action, target)
            if not targets:
                self.log(
                    "turn_skipped_no_target",
                    creature_id=actor.id,
                    creature_name=actor.name,
                    reason="no_valid_targets_for_action",
                )
                return

            self.log(
                "aoe_targets_selected",
                creature_id=actor.id,
                creature_name=actor.name,
                spell_ref=runtime_action.spell_ref,
                aoe_shape=runtime_action.aoe_shape,
                aoe_size_feet=runtime_action.aoe_size_feet,
                target_ids=[candidate.id for candidate in targets],
            )

            if runtime_action.resolution_mode == "attack":
                for selected_target in targets:
                    if not selected_target.alive:
                        continue
                    self.resolve_attack_like_action(actor, selected_target, runtime_action)
                return

            if runtime_action.resolution_mode == "save":
                for selected_target in targets:
                    if not selected_target.alive:
                        continue
                    self.resolve_save_spell(actor, selected_target, runtime_action)
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
        self._reset_turn_budget(actor)

        if actor.dead:
            self.log(
                "turn_skipped_defeated",
                creature_id=actor.id,
                creature_name=actor.name,
            )
            return

        if actor.dying:
            self.log(
                "turn_started",
                creature_id=actor.id,
                creature_name=actor.name,
                current_hp=actor.current_hp,
                conditions=[asdict(condition) for condition in actor.conditions],
                state="dying",
            )
            self._resolve_death_save(actor)
            self.expire_end_of_turn_conditions(actor)
            return

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

        action = self.choose_action(actor)
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

        if not self._slot_available(actor, action.economy_slot):
            self.log(
                "turn_action_budget_exhausted",
                creature_id=actor.id,
                creature_name=actor.name,
                action_id=action.id,
                action_name=action.name,
                economy_slot=action.economy_slot,
            )
            self.expire_end_of_turn_conditions(actor)
            return

        self.resolve_action(actor, target, action)
        self._consume_slot(actor, action.economy_slot)
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
                    "ability_scores": creature.ability_scores,
                    "proficiency_bonus": creature.proficiency_bonus,
                    "level": creature.level,
                    "spell_slots": creature.spell_slots,
                    "spell_slot_max": creature.spell_slot_max,
                    "concentration_spell": creature.concentration_spell,
                    "action_used": creature.action_used,
                    "bonus_action_used": creature.bonus_action_used,
                    "reaction_used": creature.reaction_used,
                    "damage_immunities": creature.damage_immunities,
                    "damage_resistances": creature.damage_resistances,
                    "damage_vulnerabilities": creature.damage_vulnerabilities,
                    "hit_dice_remaining": creature.hit_dice_remaining,
                    "hit_die": creature.hit_die,
                    "death_save_successes": creature.death_save_successes,
                    "death_save_failures": creature.death_save_failures,
                    "stable": creature.stable,
                    "dead": creature.dead,
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
        economy_slot=str(data.get("economy_slot", "action")),
        sub_actions=[str(value) for value in data.get("sub_actions", []) if str(value).strip()],
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
        upcast_to_level=int(data["upcast_to_level"]) if data.get("upcast_to_level") is not None else None,
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
    ability_scores_raw = dict(data.get("ability_scores", {}))
    ability_scores = {ability: int(ability_scores_raw.get(ability, 10)) for ability in sorted(ABILITIES)}

    def _int_keyed(raw_slots: Any) -> dict[int, int]:
        if not isinstance(raw_slots, dict):
            return {}
        out: dict[int, int] = {}
        for key, value in raw_slots.items():
            try:
                slot_level = int(key)
                out[slot_level] = int(value)
            except (TypeError, ValueError):
                continue
        return out

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
        ability_scores=ability_scores,
        proficiency_bonus=int(data.get("proficiency_bonus", 2)),
        level=int(data.get("level", 0)),
        spell_slots=_int_keyed(data.get("spell_slots", {})),
        spell_slot_max=_int_keyed(data.get("spell_slot_max", {})),
        concentration_spell=(str(data["concentration_spell"]) if data.get("concentration_spell") is not None else None),
        action_used=bool(data.get("action_used", False)),
        bonus_action_used=bool(data.get("bonus_action_used", False)),
        reaction_used=bool(data.get("reaction_used", False)),
        damage_immunities=[str(term) for term in data.get("damage_immunities", [])],
        damage_resistances=[str(term) for term in data.get("damage_resistances", [])],
        damage_vulnerabilities=[str(term) for term in data.get("damage_vulnerabilities", [])],
        hit_dice_remaining=int(data.get("hit_dice_remaining", 0)),
        hit_die=int(data.get("hit_die", 0)),
        death_save_successes=int(data.get("death_save_successes", 0)),
        death_save_failures=int(data.get("death_save_failures", 0)),
        stable=bool(data.get("stable", False)),
        dead=bool(data.get("dead", False)),
        exhaustion_level=int(data.get("exhaustion_level", 0)),
        charmed_by=[str(value) for value in data.get("charmed_by", [])],
        focused_target_id=(str(data["focused_target_id"]) if data.get("focused_target_id") is not None else None),
        on_take_damage_hooks=[str(value) for value in data.get("on_take_damage_hooks", [])],
        on_creature_attacked_nearby_hooks=[str(value) for value in data.get("on_creature_attacked_nearby_hooks", [])],
    )


def load_encounter_from_dict(data: dict[str, Any]) -> Encounter:
    return Encounter(
        name=str(data["name"]),
        seed=int(data["seed"]),
        round_limit=int(data["round_limit"]),
        rules_version=str(data.get("rules_version", "5.2.1")),
        engine_version=str(data.get("engine_version", "0.4.0")),
        creatures=[load_creature(creature) for creature in data["creatures"]],
    )


TARGET_POLICY_FACTORIES: dict[str, type[TargetPolicy]] = {
    "lowest_hp": LowestHPPolicy,
    "lowest_ac": LowestACPolicy,
    "random": RandomPolicy,
    "focus_fire": FocusFirePolicy,
}

ACTION_POLICY_FACTORIES: dict[str, type[ActionPolicy]] = {
    "first": FirstActionPolicy,
    "best_damage": BestDamagePolicy,
    "spell_first": SpellFirstPolicy,
}


def build_target_policy(name: str) -> TargetPolicy:
    try:
        return TARGET_POLICY_FACTORIES[name]()
    except KeyError as exc:
        raise CombatEngineError(f"Unknown target policy: {name}") from exc


def build_action_policy(name: str) -> ActionPolicy:
    try:
        return ACTION_POLICY_FACTORIES[name]()
    except KeyError as exc:
        raise CombatEngineError(f"Unknown action policy: {name}") from exc


def demo_encounter_dict() -> dict[str, Any]:
    return {
        "name": "Built-in Spell Catalog Demo",
        "seed": 1337,
        "round_limit": 10,
        "rules_version": "5.2.1",
        "engine_version": "0.4.0",
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
    parser.add_argument(
        "--target-policy",
        choices=sorted(TARGET_POLICY_FACTORIES.keys()),
        default="lowest_hp",
        help="Target selection policy for normal runs.",
    )
    parser.add_argument(
        "--action-policy",
        choices=sorted(ACTION_POLICY_FACTORIES.keys()),
        default="first",
        help="Action selection policy for normal runs.",
    )
    parser.add_argument(
        "--ab-target-policy",
        choices=sorted(TARGET_POLICY_FACTORIES.keys()),
        help="Variant target policy for A/B simulations.",
    )
    parser.add_argument(
        "--ab-action-policy",
        choices=sorted(ACTION_POLICY_FACTORIES.keys()),
        help="Variant action policy for A/B simulations.",
    )
    parser.add_argument(
        "--ab-runs",
        type=int,
        default=1,
        help="Number of deterministic A/B runs using seed stepping.",
    )
    parser.add_argument(
        "--ab-seed-step",
        type=int,
        default=1,
        help="Seed increment applied between A/B runs.",
    )
    return parser.parse_args()


def _run_with_policies(
    raw_data: dict[str, Any],
    *,
    spell_catalog: SpellCatalog,
    condition_catalog: ConditionCatalog,
    target_policy_name: str,
    action_policy_name: str,
    seed_override: int | None = None,
) -> dict[str, Any]:
    data = json.loads(json.dumps(raw_data))
    if seed_override is not None:
        data["seed"] = int(seed_override)
    encounter = load_encounter_from_dict(data)
    engine = CombatEngine(
        encounter,
        spell_catalog,
        condition_catalog=condition_catalog,
        target_policy=build_target_policy(target_policy_name),
        action_policy=build_action_policy(action_policy_name),
    )
    return engine.run()


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
        condition_catalog = load_condition_catalog(registry)
    except (RulesRegistryError, SpellCatalogError, ConditionCatalogError, CombatEngineError) as exc:
        print(f"Rules data load failed: {exc}", file=sys.stderr)
        return 3

    ab_enabled = bool(args.ab_action_policy or args.ab_target_policy)

    if ab_enabled:
        baseline_target = args.target_policy
        baseline_action = args.action_policy
        variant_target = args.ab_target_policy or baseline_target
        variant_action = args.ab_action_policy or baseline_action

        base_seed = int(raw_data.get("seed", 0))
        runs: list[dict[str, Any]] = []
        baseline_wins: dict[str, int] = {}
        variant_wins: dict[str, int] = {}

        for index in range(max(1, args.ab_runs)):
            run_seed = base_seed + index * int(args.ab_seed_step)
            baseline = _run_with_policies(
                raw_data,
                spell_catalog=spell_catalog,
                condition_catalog=condition_catalog,
                target_policy_name=baseline_target,
                action_policy_name=baseline_action,
                seed_override=run_seed,
            )
            variant = _run_with_policies(
                raw_data,
                spell_catalog=spell_catalog,
                condition_catalog=condition_catalog,
                target_policy_name=variant_target,
                action_policy_name=variant_action,
                seed_override=run_seed,
            )

            baseline_key = str(baseline.get("winner"))
            variant_key = str(variant.get("winner"))
            baseline_wins[baseline_key] = baseline_wins.get(baseline_key, 0) + 1
            variant_wins[variant_key] = variant_wins.get(variant_key, 0) + 1

            runs.append(
                {
                    "seed": run_seed,
                    "baseline": {
                        "target_policy": baseline_target,
                        "action_policy": baseline_action,
                        "winner": baseline.get("winner"),
                        "reason": baseline.get("reason"),
                        "events": len(baseline.get("event_log", [])),
                    },
                    "variant": {
                        "target_policy": variant_target,
                        "action_policy": variant_action,
                        "winner": variant.get("winner"),
                        "reason": variant.get("reason"),
                        "events": len(variant.get("event_log", [])),
                    },
                }
            )

        summary = {
            "ab_runs": len(runs),
            "baseline": {
                "target_policy": baseline_target,
                "action_policy": baseline_action,
                "wins": baseline_wins,
            },
            "variant": {
                "target_policy": variant_target,
                "action_policy": variant_action,
                "wins": variant_wins,
            },
            "runs": runs,
        }

        if args.json:
            print(json.dumps(summary, indent=2))
        else:
            print("A/B Summary:")
            print(f"  baseline={baseline_action}/{baseline_target} wins={baseline_wins}")
            print(f"  variant={variant_action}/{variant_target} wins={variant_wins}")
            for run in runs:
                print(
                    f"  seed={run['seed']} baseline={run['baseline']['winner']}({run['baseline']['events']} events) "
                    f"variant={run['variant']['winner']}({run['variant']['events']} events)"
                )
        return 0

    try:
        result = _run_with_policies(
            raw_data,
            spell_catalog=spell_catalog,
            condition_catalog=condition_catalog,
            target_policy_name=args.target_policy,
            action_policy_name=args.action_policy,
        )
    except CombatEngineError as exc:
        print(f"Engine initialization failed: {exc}", file=sys.stderr)
        return 4

    if args.write_log:
        args.write_log.write_text(json.dumps(result, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_summary(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
