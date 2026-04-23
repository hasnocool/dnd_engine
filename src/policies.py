from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from turn_engine import Action, CombatEngine, Creature


DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$")


class TargetPolicy(Protocol):
    def select_target(self, engine: CombatEngine, actor: Creature, candidates: list[Creature]) -> Creature | None:
        ...


class ActionPolicy(Protocol):
    def select_action(self, engine: CombatEngine, actor: Creature) -> Action | None:
        ...


@dataclass(slots=True)
class LowestHPPolicy:
    def select_target(self, engine: CombatEngine, actor: Creature, candidates: list[Creature]) -> Creature | None:
        if not candidates:
            return None
        return sorted(candidates, key=lambda creature: (creature.current_hp, creature.ac, creature.id))[0]


@dataclass(slots=True)
class LowestACPolicy:
    def select_target(self, engine: CombatEngine, actor: Creature, candidates: list[Creature]) -> Creature | None:
        if not candidates:
            return None
        return sorted(candidates, key=lambda creature: (creature.ac, creature.current_hp, creature.id))[0]


@dataclass(slots=True)
class RandomPolicy:
    def select_target(self, engine: CombatEngine, actor: Creature, candidates: list[Creature]) -> Creature | None:
        if not candidates:
            return None
        return engine.rng.choice(candidates)


@dataclass(slots=True)
class FocusFirePolicy:
    def select_target(self, engine: CombatEngine, actor: Creature, candidates: list[Creature]) -> Creature | None:
        if not candidates:
            actor.focused_target_id = None
            return None

        if actor.focused_target_id:
            for candidate in candidates:
                if candidate.id == actor.focused_target_id:
                    return candidate

        chosen = sorted(candidates, key=lambda creature: (creature.current_hp, creature.ac, creature.id))[0]
        actor.focused_target_id = chosen.id
        return chosen


@dataclass(slots=True)
class FirstActionPolicy:
    def select_action(self, engine: CombatEngine, actor: Creature) -> Action | None:
        return actor.first_combat_action()


def _expected_damage(expression: str | None) -> float:
    if not expression:
        return 0.0

    match = DICE_RE.fullmatch(expression)
    if not match:
        return 0.0

    dice_count_text, die_size_text, modifier_text = match.groups()
    dice_count = int(dice_count_text) if dice_count_text else 1
    die_size = int(die_size_text)
    modifier = int(modifier_text.replace(" ", "")) if modifier_text else 0
    return dice_count * (die_size + 1) / 2.0 + modifier


@dataclass(slots=True)
class BestDamagePolicy:
    def _expected_attack_damage(self, attack_bonus: int, target_ac: int, damage: str | None) -> float:
        if not damage:
            return 0.0

        normal_damage = _expected_damage(damage)
        if normal_damage <= 0:
            return 0.0

        crit_damage = _expected_damage(_crit_expression(damage))

        noncrit_hits = 0
        crit_hits = 0
        for roll in range(1, 21):
            if roll == 1:
                continue
            if roll == 20:
                crit_hits += 1
                continue
            if roll + attack_bonus >= target_ac:
                noncrit_hits += 1

        return (noncrit_hits / 20.0) * normal_damage + (crit_hits / 20.0) * crit_damage

    def _save_success_probability(self, save_dc: int, save_bonus: int) -> float:
        success = 0
        for roll in range(1, 21):
            if roll + save_bonus >= save_dc:
                success += 1
        return success / 20.0

    def _expected_spell_damage(self, resolved_action, target: Creature) -> float:
        if not resolved_action.damage:
            return 0.0

        base = _expected_damage(resolved_action.damage)
        if resolved_action.resolution_mode == "attack" and resolved_action.attack_bonus is not None:
            return self._expected_attack_damage(resolved_action.attack_bonus, target.ac, resolved_action.damage)

        if (
            resolved_action.resolution_mode == "save"
            and resolved_action.save_dc is not None
            and resolved_action.save_ability in {"str", "dex", "con", "int", "wis", "cha"}
        ):
            bonus = target.saving_throw_bonus(resolved_action.save_ability)
            save_success_prob = self._save_success_probability(resolved_action.save_dc, bonus)
            save_fail_prob = 1.0 - save_success_prob
            save_success_damage = base / 2.0 if resolved_action.half_damage_on_save else 0.0
            return save_fail_prob * base + save_success_prob * save_success_damage

        return base

    def _expected_action_damage(
        self,
        engine: CombatEngine,
        actor: Creature,
        action: Action,
        primary_target: Creature | None,
        depth: int = 0,
    ) -> float:
        if depth > 2:
            return 0.0

        target = primary_target
        if target is None:
            enemies = [candidate for candidate in engine.encounter.creatures if candidate.alive and candidate.team != actor.team]
            target = engine.target_policy.select_target(engine, actor, enemies) if enemies else None

        if action.kind == "attack":
            if target is None or action.attack_bonus is None:
                return _expected_damage(action.damage)
            return self._expected_attack_damage(action.attack_bonus, target.ac, action.damage)

        if action.kind == "spell":
            try:
                resolved = engine.resolve_spell_action(action)
            except Exception:
                return _expected_damage(action.damage)
            if target is None:
                return _expected_damage(resolved.damage)
            return self._expected_spell_damage(resolved, target)

        if action.kind == "multiattack":
            total = 0.0
            by_id = {candidate.id: candidate for candidate in actor.actions}
            for sub_id in action.sub_actions:
                sub_action = by_id.get(sub_id)
                if sub_action is None:
                    continue
                total += self._expected_action_damage(engine, actor, sub_action, target, depth + 1)
            return total

        return _expected_damage(action.damage)

    def select_action(self, engine: CombatEngine, actor: Creature) -> Action | None:
        candidates = [action for action in actor.actions if action.kind in {"attack", "spell", "multiattack"}]
        if not candidates:
            return None

        enemies = [candidate for candidate in engine.encounter.creatures if candidate.alive and candidate.team != actor.team]
        target = engine.target_policy.select_target(engine, actor, enemies) if enemies else None

        return sorted(
            candidates,
            key=lambda action: (self._expected_action_damage(engine, actor, action, target), action.id),
            reverse=True,
        )[0]


@dataclass(slots=True)
class SpellFirstPolicy:
    def select_action(self, engine: CombatEngine, actor: Creature) -> Action | None:
        spell_actions = [action for action in actor.actions if action.kind == "spell"]
        for action in spell_actions:
            return action
        return actor.first_combat_action()


def _crit_expression(expression: str) -> str:
    match = DICE_RE.fullmatch(expression)
    if not match:
        return expression

    dice_count_text, die_size_text, modifier_text = match.groups()
    dice_count = int(dice_count_text) if dice_count_text else 1
    crit_count = max(1, dice_count * 2)
    modifier = modifier_text.replace(" ", "") if modifier_text else ""
    return f"{crit_count}d{die_size_text}{modifier}"
