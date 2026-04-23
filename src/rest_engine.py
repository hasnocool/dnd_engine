from __future__ import annotations

import random
from dataclasses import dataclass

from turn_engine import Creature


@dataclass(slots=True)
class RestResult:
    rest_type: str
    hit_dice_spent: int
    hp_before: int
    hp_after: int
    hp_recovered: int
    hit_dice_before: int
    hit_dice_after: int
    spell_slots_before: dict[int, int]
    spell_slots_after: dict[int, int]
    exhaustion_before: int
    exhaustion_after: int
    events: list[dict[str, object]]


def _con_modifier(creature: Creature) -> int:
    con_score = creature.ability_scores.get("con", 10)
    return (con_score - 10) // 2


def short_rest(
    creature: Creature,
    hit_dice_to_spend: int,
    *,
    rng: random.Random | None = None,
) -> RestResult:
    if rng is None:
        rng = random.Random(0)

    hp_before = creature.current_hp
    hit_dice_before = creature.hit_dice_remaining
    spell_slots_before = dict(creature.spell_slots)
    exhaustion_before = creature.exhaustion_level

    spend_limit = max(0, min(hit_dice_to_spend, creature.hit_dice_remaining))
    spent = 0
    recovered = 0
    events: list[dict[str, object]] = []

    for _ in range(spend_limit):
        if creature.current_hp >= creature.max_hp:
            break

        roll = rng.randint(1, max(1, creature.hit_die))
        heal = max(0, roll + _con_modifier(creature))

        before = creature.current_hp
        creature.current_hp = min(creature.max_hp, creature.current_hp + heal)
        gained = creature.current_hp - before
        creature.hit_dice_remaining = max(0, creature.hit_dice_remaining - 1)
        spent += 1
        recovered += gained

        events.append(
            {
                "event_type": "short_rest_hit_die_spent",
                "roll": roll,
                "heal_raw": heal,
                "heal_applied": gained,
                "hp_before": before,
                "hp_after": creature.current_hp,
            }
        )

    return RestResult(
        rest_type="short_rest",
        hit_dice_spent=spent,
        hp_before=hp_before,
        hp_after=creature.current_hp,
        hp_recovered=recovered,
        hit_dice_before=hit_dice_before,
        hit_dice_after=creature.hit_dice_remaining,
        spell_slots_before=spell_slots_before,
        spell_slots_after=dict(creature.spell_slots),
        exhaustion_before=exhaustion_before,
        exhaustion_after=creature.exhaustion_level,
        events=events,
    )


def long_rest(creature: Creature) -> RestResult:
    hp_before = creature.current_hp
    hit_dice_before = creature.hit_dice_remaining
    spell_slots_before = dict(creature.spell_slots)
    exhaustion_before = creature.exhaustion_level

    creature.current_hp = creature.max_hp

    if creature.spell_slot_max:
        creature.spell_slots = dict(creature.spell_slot_max)

    if creature.level > 0:
        regain = max(1, creature.level // 2)
        creature.hit_dice_remaining = min(creature.level, creature.hit_dice_remaining + regain)

    creature.exhaustion_level = max(0, creature.exhaustion_level - 1)

    events = [
        {
            "event_type": "long_rest_completed",
            "hp_before": hp_before,
            "hp_after": creature.current_hp,
            "spell_slots_restored": creature.spell_slots,
            "hit_dice_before": hit_dice_before,
            "hit_dice_after": creature.hit_dice_remaining,
            "exhaustion_before": exhaustion_before,
            "exhaustion_after": creature.exhaustion_level,
        }
    ]

    return RestResult(
        rest_type="long_rest",
        hit_dice_spent=0,
        hp_before=hp_before,
        hp_after=creature.current_hp,
        hp_recovered=max(0, creature.current_hp - hp_before),
        hit_dice_before=hit_dice_before,
        hit_dice_after=creature.hit_dice_remaining,
        spell_slots_before=spell_slots_before,
        spell_slots_after=dict(creature.spell_slots),
        exhaustion_before=exhaustion_before,
        exhaustion_after=creature.exhaustion_level,
        events=events,
    )
