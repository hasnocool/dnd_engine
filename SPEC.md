Yes — for a **working D&D simulator in 2026**, the best publicly available rules base is **SRD v5.2.1**. Wizards’ official SRD page says SRD 5.2.1 contains D&D rules content that creators can use under **Creative Commons**, which makes it the safest foundation for a simulator you may want to publish or share. ([Dungeons & Dragons][1])

There is also an official free digital rules set called the **D&D Beyond Basic Rules**. D&D Beyond says these were released on **April 22, 2025**, are based on the newer rules, and include the material from the earlier Free Rules (2024), expanded with content from **SRD 5.2**. That makes them great for playtesting and reference, but for a software project, the **SRD is the cleaner legal starting point** because it is explicitly positioned for creators and publishing use. ([Dungeons & Dragons][2])

A useful way to think about it is:

* **SRD 5.2.1** = best for a simulator engine you can build and distribute. ([Dungeons & Dragons][1])
* **D&D Beyond Basic Rules** = best for checking how the current official free rules are presented to players and DMs. ([Dungeons & Dragons][2])
* **Basic Rules (2014)** still exist, but the current official ecosystem has moved to the revised rules family reflected in the 2024 core books and the later SRD 5.2 line. Wizards said in 2024 that SRD 5.2 would incorporate material from the 2024 Player’s Handbook, 2024 Dungeon Master’s Guide, and 2025 Monster Manual. ([Dungeons & Dragons][3])

So the answer is:

**Use SRD 5.2.1 as your simulator’s canonical rules source.**

A good first build target would be this minimal engine surface:

1. dice roller
2. creature stat block schema
3. initiative and turn order
4. actions, bonus actions, reactions
5. attack rolls, damage rolls, saving throws
6. conditions and duration handling
7. spells/effects as structured data
8. combat log + deterministic replay seed

That gives you a real simulator core before you tackle character creation, exploration, or full campaign logic.

For your project, I’d recommend this starting repo shape:

```text
dnd-simulator/
├── docs/
│   ├── rules-source.md
│   ├── engine-architecture.md
│   └── combat-resolution-spec.md
├── data/
│   ├── srd/
│   │   ├── classes.json
│   │   ├── species.json
│   │   ├── equipment.json
│   │   ├── spells.json
│   │   ├── monsters.json
│   │   └── conditions.json
│   └── fixtures/
├── schemas/
│   ├── creature.schema.json
│   ├── action.schema.json
│   ├── spell.schema.json
│   └── encounter.schema.json
├── src/
│   ├── dice/
│   ├── rules/
│   ├── combat/
│   ├── state/
│   └── api/
└── tests/
```

The first concrete deliverables I’d make are:

* `rules-source.md`
* `creature.schema.json`
* `combat-resolution-spec.md`
* `turn-engine.py` or `turn_engine.ts`
* `dice.py` or `dice.ts`
* `conditions-engine.py` or `conditions_engine.ts`

And one important note: even with public rules, you should avoid copying full non-open book text into your app unless it is actually in the SRD/open material. The SRD is the safe subset to model directly. ([Dungeons & Dragons][1])

I can turn this into a **repo-ready D&D simulator starter pack** next, with:
`rules-source.md`, `engine-architecture.md`, `combat-resolution-spec.md`, `schemas/*.json`, and a first `turn_engine.py`.

[1]: https://dnd.wizards.com/resources/systems-reference-document "SRD v5.2.1 - System Reference Document - D&D Beyond "
[2]: https://dnd.wizards.com/news "Changelog -  - D&D Beyond "
[3]: https://dnd.wizards.com/further-resources "How to Play D&D | Dungeons & Dragons | Dungeons & Dragons"

Here’s the repo-ready starter pack.

```text
dnd-simulator/
├── docs/
│   ├── rules-source.md
│   ├── engine-architecture.md
│   └── combat-resolution-spec.md
├── schemas/
│   ├── action.schema.json
│   ├── creature.schema.json
│   ├── spell.schema.json
│   └── encounter.schema.json
├── examples/
│   └── demo_encounter.json
└── src/
    └── turn_engine.py
```

````md
<!-- filename: docs/rules-source.md -->
# Rules Source

## Canonical source

The simulator should use **SRD 5.2.1** as the canonical public rules source.

That gives the project a clean legal boundary for:
- combat procedures
- creatures and stat blocks
- actions
- equipment
- spells that are actually present in the SRD subset
- conditions and other openly reusable mechanics

## Project rule-ingestion policy

The simulator must distinguish between:

1. **Open mechanical content**
   - numeric stats
   - turn structure
   - action economy
   - attack, damage, save, and condition logic
   - openly available monsters, items, spells, and rules text that are part of the SRD subset

2. **Non-open product content**
   - non-SRD story text
   - non-SRD subclasses, monsters, spells, lore, adventures, settings, and book prose
   - copyrighted text copied from non-open books or webpages

## Safe implementation boundary

The codebase should primarily store:
- normalized mechanics
- structured data
- derived machine-readable content
- short field labels
- internal engine comments written by us

The codebase should avoid:
- copying long prose passages from non-open books
- bundling non-open rulebook text into JSON fixtures
- mixing open and non-open data sources without provenance

## Source registry model

Every imported rules dataset should have provenance metadata:

```json
{
  "source_id": "srd-5.2.1",
  "source_type": "official_open_rules",
  "version": "5.2.1",
  "license": "CC",
  "url": "OFFICIAL_SOURCE_URL_HERE",
  "fetched_at_utc": "2026-04-22T00:00:00Z",
  "content_hash": "SHA256_HERE"
}
````

## Initial simulator scope

Phase 1 should implement only:

* deterministic dice rolling
* initiative
* turn order
* attack rolls
* damage rolls
* hit points
* defeat state
* a minimal set of conditions
* deterministic combat logs and replay

## Deferred scope

Do not block Phase 1 on:

* full character creation
* full spellcasting system
* line of sight
* grid movement
* inventory economics
* exploration mode
* social mechanics
* full monster AI
* reactions with full interrupt timing
* legendary actions
* lair actions
* grappling edge cases
* concentration edge cases

## Data normalization policy

Normalize rule content into these core entities:

* Creature
* Action
* Spell
* Condition
* Encounter
* EventLog

Keep raw imports separate from normalized data.

## Versioning policy

All rules-aware engine behavior should be versioned by:

* rules version
* schema version
* engine version

Example:

```text
rules_version=5.2.1
schema_version=0.1.0
engine_version=0.1.0
```

## Practical first milestone

The first milestone is a combat-only engine that can:

1. load an encounter JSON file
2. roll initiative
3. run rounds
4. resolve attacks and damage
5. expire simple timed conditions
6. emit a deterministic combat log
7. declare a winner or a draw

````

```md
<!-- filename: docs/engine-architecture.md -->
# Engine Architecture

## Goals

The engine should be:

- deterministic
- replayable
- data-driven
- testable
- rules-versioned
- easy to extend without rewriting the combat loop

## Core design

Use a layered architecture:

```text
data -> validation -> domain model -> rules engine -> event log -> presentation
````

## Modules

### 1. Data layer

Responsible for:

* loading encounter JSON
* validating against schemas
* version tagging
* source provenance

### 2. Domain model

Structured in-memory objects such as:

* Creature
* Action
* ActiveCondition
* EncounterState
* Event

### 3. Rules engine

Pure mechanics:

* initiative
* target selection
* attack resolution
* damage resolution
* defeat checks
* condition ticking
* end-of-round processing

### 4. Simulation runtime

Controls:

* round loop
* turn order
* stopping conditions
* seeded RNG
* log emission

### 5. Output layer

Responsible for:

* text combat log
* JSON combat log
* replay export
* future API/UI adapters

## Determinism

Every simulation must be reproducible from:

* encounter input
* seed
* engine version
* rules version

The same input and seed must produce the same output.

## State model

State should be explicit and serializable.

Recommended state slices:

* encounter metadata
* combatants
* initiative order
* round number
* active turn index
* active conditions
* event history
* terminal status

## Event sourcing direction

Even if the first version mutates in-memory state directly, the engine should emit events for every important transition:

* encounter_started
* initiative_rolled
* round_started
* turn_started
* attack_declared
* attack_resolved
* damage_applied
* condition_applied
* condition_expired
* creature_defeated
* encounter_ended

This creates a clean future path for:

* replays
* debugging
* frontend visualizations
* audit trails
* branching simulations

## Turn loop

Recommended loop:

```text
load encounter
seed rng
roll initiative
while not terminal:
    start round
    for combatant in initiative order:
        skip if defeated
        start turn
        choose action
        resolve action
        expire timed effects
        check terminal state
end encounter
```

## Extension points

The first engine should be intentionally small but shaped for growth.

Safe extension points:

* target selection policy
* action selection policy
* AI behavior modules
* save/DC resolution
* spell resolution
* reactions
* concentration handling
* battlefield/grid layer
* cover and vision
* advantage/disadvantage modifiers
* analytics hooks

## Recommended near-term roadmap

### Phase 1

* deterministic combat simulator
* one action type: attack
* simple conditions
* CLI runner

### Phase 2

* saves
* spells
* heals
* reactions
* richer conditions

### Phase 3

* grid and movement
* opportunity attacks
* concentration
* area effects

### Phase 4

* full scenario runner
* encounter balance tools
* AI policy modules
* web API
* frontend replay viewer

````

```md
<!-- filename: docs/combat-resolution-spec.md -->
# Combat Resolution Spec

## Scope

This document defines the first-pass combat engine behavior.

This version intentionally supports:
- initiative
- turns
- attacks
- damage
- simple conditions
- win/draw detection

## Encounter input

An encounter contains:
- name
- seed
- round_limit
- combatants

Each combatant contains:
- id
- name
- team
- armor class
- current/max hp
- initiative bonus
- actions
- conditions

## Initiative

Each combatant rolls:

```text
1d20 + initiative_bonus
````

Sorting rules:

1. higher total first
2. higher initiative bonus second
3. stable id/name ordering last

Initiative order remains fixed for the encounter in version 0.1.0.

## Turn eligibility

A creature may take a turn only if:

* current_hp > 0
* it is not blocked by a hard-disable condition

Hard-disable conditions in v0.1.0:

* unconscious
* paralyzed
* stunned
* incapacitated

## Target selection

Default target policy:

* choose an alive enemy
* prefer lowest current HP
* then lower AC
* then lexical id

This is a placeholder AI policy.

## Supported action kinds

Version 0.1.0 supports:

* attack

Other kinds may exist in schemas but are not executed by the engine yet.

## Attack resolution

Attack flow:

1. attacker chooses target
2. engine determines roll mode: normal, advantage, or disadvantage
3. engine rolls d20
4. natural 1 always misses
5. natural 20 always hits and crits
6. otherwise compare:

```text
d20 + attack_bonus >= target.ac
```

## Advantage/disadvantage rules in v0.1.0

Attacker has disadvantage if attacker has:

* poisoned
* blinded

Attacker has advantage against prone targets when:

* the action is melee

If both advantage and disadvantage apply, they cancel.

## Critical hits

On natural 20:

* the attack hits
* damage dice are doubled
* flat modifiers are not doubled

Example:

```text
1d8+3 -> crit becomes 2d8+3
```

## Damage resolution

Damage expression format:

* `XdY`
* `XdY+Z`
* `XdY-Z`

Examples:

* `1d6`
* `1d8+3`
* `2d6+1`

Damage is applied as:

```text
target.current_hp = max(0, target.current_hp - damage)
```

## Defeat state

A creature is defeated when:

* current_hp <= 0

Version 0.1.0 treats defeated creatures as removed from turn participation immediately.

## Condition ticking

At the end of the creature's own turn:

* decrement each timed condition with a numeric duration
* remove conditions that reach 0

Conditions with `rounds_remaining = null` do not expire automatically.

## Terminal state

The encounter ends when:

* only one team has surviving creatures
* or round_limit is reached

Outcomes:

* winning team id/name
* draw
* no_winner_with_survivors
* mutual_elimination

## Event log requirements

Every simulation should emit at least:

* seed
* initiative rolls
* round starts
* turn starts
* attack rolls
* hit/miss result
* damage applied
* defeat notices
* condition expiration
* final outcome

## Non-goals for this version

Not included yet:

* saving throws
* spells
* healing
* movement
* reactions
* readied actions
* multiattack sequencing rules
* resistance/vulnerability/immunity
* concentration
* cover
* line of sight

````

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/action.schema.json",
  "title": "Action",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "kind"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "kind": {
      "type": "string",
      "enum": [
        "attack",
        "heal",
        "spell",
        "dash",
        "dodge",
        "disengage",
        "help",
        "custom"
      ]
    },
    "attack_bonus": {
      "type": "integer",
      "default": 0
    },
    "damage": {
      "type": "string",
      "pattern": "^\\s*\\d*d\\d+\\s*([+-]\\s*\\d+)?\\s*$"
    },
    "damage_type": {
      "type": "string",
      "default": "untyped"
    },
    "is_melee": {
      "type": "boolean",
      "default": true
    },
    "range_feet": {
      "type": "integer",
      "minimum": 0,
      "default": 5
    },
    "notes": {
      "type": "string"
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "attack"
          }
        },
        "required": [
          "kind"
        ]
      },
      "then": {
        "required": [
          "attack_bonus",
          "damage"
        ]
      }
    }
  ]
}
````

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/creature.schema.json",
  "title": "Creature",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "team",
    "ac",
    "max_hp",
    "current_hp",
    "initiative_bonus",
    "actions"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "team": {
      "type": "string",
      "minLength": 1
    },
    "ac": {
      "type": "integer",
      "minimum": 1
    },
    "max_hp": {
      "type": "integer",
      "minimum": 1
    },
    "current_hp": {
      "type": "integer",
      "minimum": 0
    },
    "initiative_bonus": {
      "type": "integer"
    },
    "speed_feet": {
      "type": "integer",
      "minimum": 0,
      "default": 30
    },
    "actions": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "action.schema.json"
      }
    },
    "conditions": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "name"
        ],
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "rounds_remaining": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 1
          }
        }
      }
    },
    "notes": {
      "type": "string"
    }
  }
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/spell.schema.json",
  "title": "Spell",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "level",
    "school"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "level": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9
    },
    "school": {
      "type": "string",
      "minLength": 1
    },
    "casting_time": {
      "type": "string"
    },
    "range": {
      "type": "string"
    },
    "duration": {
      "type": "string"
    },
    "components": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "default": []
    },
    "requires_concentration": {
      "type": "boolean",
      "default": false
    },
    "description_ref": {
      "type": "string"
    },
    "effects": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object"
      }
    }
  }
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/encounter.schema.json",
  "title": "Encounter",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "name",
    "seed",
    "round_limit",
    "creatures"
  ],
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "seed": {
      "type": "integer"
    },
    "round_limit": {
      "type": "integer",
      "minimum": 1
    },
    "rules_version": {
      "type": "string",
      "default": "5.2.1"
    },
    "engine_version": {
      "type": "string",
      "default": "0.1.0"
    },
    "creatures": {
      "type": "array",
      "minItems": 2,
      "items": {
        "$ref": "creature.schema.json"
      }
    }
  }
}
```

```json
{
  "name": "Goblin Ambush Demo",
  "seed": 1337,
  "round_limit": 10,
  "rules_version": "5.2.1",
  "engine_version": "0.1.0",
  "creatures": [
    {
      "id": "fighter_1",
      "name": "Human Fighter",
      "team": "heroes",
      "ac": 16,
      "max_hp": 18,
      "current_hp": 18,
      "initiative_bonus": 2,
      "actions": [
        {
          "id": "longsword",
          "name": "Longsword",
          "kind": "attack",
          "attack_bonus": 5,
          "damage": "1d8+3",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
    },
    {
      "id": "cleric_1",
      "name": "Dwarf Cleric",
      "team": "heroes",
      "ac": 18,
      "max_hp": 16,
      "current_hp": 16,
      "initiative_bonus": 0,
      "actions": [
        {
          "id": "mace",
          "name": "Mace",
          "kind": "attack",
          "attack_bonus": 4,
          "damage": "1d6+2",
          "damage_type": "bludgeoning",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
    },
    {
      "id": "goblin_1",
      "name": "Goblin A",
      "team": "goblins",
      "ac": 15,
      "max_hp": 7,
      "current_hp": 7,
      "initiative_bonus": 2,
      "actions": [
        {
          "id": "scimitar",
          "name": "Scimitar",
          "kind": "attack",
          "attack_bonus": 4,
          "damage": "1d6+2",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
    },
    {
      "id": "goblin_2",
      "name": "Goblin B",
      "team": "goblins",
      "ac": 15,
      "max_hp": 7,
      "current_hp": 7,
      "initiative_bonus": 2,
      "actions": [
        {
          "id": "scimitar",
          "name": "Scimitar",
          "kind": "attack",
          "attack_bonus": 4,
          "damage": "1d6+2",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
    }
  ]
}
```

```python
# filename: src/turn_engine.py

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal


DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$")
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
    attack_bonus: int = 0
    damage: str | None = None
    damage_type: str = "untyped"
    is_melee: bool = True
    range_feet: int = 5
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
        return any(c.name.casefold() == wanted for c in self.conditions)

    def has_any_condition(self, names: set[str]) -> bool:
        lowered = {name.casefold() for name in names}
        return any(c.name.casefold() in lowered for c in self.conditions)

    def first_attack_action(self) -> Action | None:
        for action in self.actions:
            if action.kind == "attack":
                return action
        return None


@dataclass(slots=True)
class Encounter:
    name: str
    seed: int
    round_limit: int
    rules_version: str
    engine_version: str
    creatures: list[Creature]


class CombatEngine:
    def __init__(self, encounter: Encounter) -> None:
        self.encounter = encounter
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

        roll_a = self.rng.randint(1, 20)
        roll_b = self.rng.randint(1, 20)

        if mode == "advantage":
            selected = max(roll_a, roll_b)
        else:
            selected = min(roll_a, roll_b)

        return selected, {"mode": mode, "rolls": [roll_a, roll_b], "selected": selected}

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

    def determine_roll_mode(self, attacker: Creature, target: Creature, action: Action) -> Literal["normal", "advantage", "disadvantage"]:
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
        enemies = [c for c in self.encounter.creatures if c.alive and c.team != actor.team]
        if not enemies:
            return None
        enemies.sort(key=lambda c: (c.current_hp, c.ac, c.id))
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
            key=lambda c: (
                -(c.initiative or 0),
                -c.initiative_bonus,
                c.id,
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
                active_conditions=[asdict(c) for c in actor.conditions],
            )
            self.expire_end_of_turn_conditions(actor)
            return

        self.log(
            "turn_started",
            creature_id=actor.id,
            creature_name=actor.name,
            current_hp=actor.current_hp,
            conditions=[asdict(c) for c in actor.conditions],
        )

        action = actor.first_attack_action()
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

        mode = self.determine_roll_mode(actor, target, action)
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
            attacker_id=actor.id,
            attacker_name=actor.name,
            target_id=target.id,
            target_name=target.name,
            action=asdict(action),
        )

        if not hit:
            self.log(
                "attack_resolved",
                attacker_id=actor.id,
                attacker_name=actor.name,
                target_id=target.id,
                target_name=target.name,
                result="miss",
                attack_roll_detail=attack_detail,
                attack_bonus=action.attack_bonus,
                attack_total=attack_total,
                target_ac=target.ac,
            )
            self.expire_end_of_turn_conditions(actor)
            return

        if action.damage is None:
            self.log(
                "attack_resolved",
                attacker_id=actor.id,
                attacker_name=actor.name,
                target_id=target.id,
                target_name=target.name,
                result="hit_no_damage_expression",
                attack_roll_detail=attack_detail,
                attack_bonus=action.attack_bonus,
                attack_total=attack_total,
                target_ac=target.ac,
            )
            self.expire_end_of_turn_conditions(actor)
            return

        damage_total, damage_detail = self.roll_damage(action.damage, crit=crit)
        old_hp = target.current_hp
        target.current_hp = max(0, target.current_hp - damage_total)

        self.log(
            "attack_resolved",
            attacker_id=actor.id,
            attacker_name=actor.name,
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
        )

        if not target.alive:
            self.log(
                "creature_defeated",
                creature_id=target.id,
                creature_name=target.name,
                defeated_by_id=actor.id,
                defeated_by_name=actor.name,
            )

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
        attack_bonus=int(data.get("attack_bonus", 0)),
        damage=data.get("damage"),
        damage_type=str(data.get("damage_type", "untyped")),
        is_melee=bool(data.get("is_melee", True)),
        range_feet=int(data.get("range_feet", 5)),
        notes=data.get("notes"),
    )


def load_condition(data: dict[str, Any]) -> ActiveCondition:
    return ActiveCondition(
        name=str(data["name"]),
        rounds_remaining=int(data["rounds_remaining"]) if data.get("rounds_remaining") is not None else None,
    )


def load_creature(data: dict[str, Any]) -> Creature:
    return Creature(
        id=str(data["id"]),
        name=str(data["name"]),
        team=str(data["team"]),
        ac=int(data["ac"]),
        max_hp=int(data["max_hp"]),
        current_hp=int(data["current_hp"]),
        initiative_bonus=int(data["initiative_bonus"]),
        actions=[load_action(action) for action in data["actions"]],
        conditions=[load_condition(condition) for condition in data.get("conditions", [])],
        speed_feet=int(data.get("speed_feet", 30)),
        notes=data.get("notes"),
    )


def load_encounter_from_dict(data: dict[str, Any]) -> Encounter:
    return Encounter(
        name=str(data["name"]),
        seed=int(data["seed"]),
        round_limit=int(data["round_limit"]),
        rules_version=str(data.get("rules_version", "5.2.1")),
        engine_version=str(data.get("engine_version", "0.1.0")),
        creatures=[load_creature(creature) for creature in data["creatures"]],
    )


def demo_encounter_dict() -> dict[str, Any]:
    return {
        "name": "Built-in Demo Encounter",
        "seed": 1337,
        "round_limit": 10,
        "rules_version": "5.2.1",
        "engine_version": "0.1.0",
        "creatures": [
            {
                "id": "fighter_1",
                "name": "Human Fighter",
                "team": "heroes",
                "ac": 16,
                "max_hp": 18,
                "current_hp": 18,
                "initiative_bonus": 2,
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
                "id": "cleric_1",
                "name": "Dwarf Cleric",
                "team": "heroes",
                "ac": 18,
                "max_hp": 16,
                "current_hp": 16,
                "initiative_bonus": 0,
                "actions": [
                    {
                        "id": "mace",
                        "name": "Mace",
                        "kind": "attack",
                        "attack_bonus": 4,
                        "damage": "1d6+2",
                        "damage_type": "bludgeoning",
                        "is_melee": True,
                        "range_feet": 5,
                    }
                ],
                "conditions": [],
            },
            {
                "id": "goblin_1",
                "name": "Goblin A",
                "team": "goblins",
                "ac": 15,
                "max_hp": 7,
                "current_hp": 7,
                "initiative_bonus": 2,
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
                "id": "goblin_2",
                "name": "Goblin B",
                "team": "goblins",
                "ac": 15,
                "max_hp": 7,
                "current_hp": 7,
                "initiative_bonus": 2,
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
        elif event_type == "creature_defeated":
            print(f"[Round {round_number}] {event['creature_name']} is defeated")
        elif event_type == "condition_expired":
            print(f"[Round {round_number}] {event['creature_name']}: {event['condition_name']} expired")
        elif event_type == "encounter_ended":
            print(f"[End] winner={event['winner']} reason={event['reason']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic D&D-style combat simulator starter engine.")
    parser.add_argument(
        "encounter",
        nargs="?",
        help="Path to encounter JSON. If omitted, --demo is used.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the built-in demo encounter.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON result instead of a text summary.",
    )
    parser.add_argument(
        "--write-log",
        type=Path,
        help="Write the full JSON result to a file.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.encounter:
        try:
            data = json.loads(Path(args.encounter).read_text(encoding="utf-8"))
        except OSError as exc:
            print(f"Failed to read encounter file: {exc}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as exc:
            print(f"Invalid JSON: {exc}", file=sys.stderr)
            return 1
    else:
        data = demo_encounter_dict()

    encounter = load_encounter_from_dict(data)
    engine = CombatEngine(encounter)
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
```

```bash
# filename: run_examples.sh
python3 src/turn_engine.py --demo
python3 src/turn_engine.py examples/demo_encounter.json
python3 src/turn_engine.py examples/demo_encounter.json --json
python3 src/turn_engine.py examples/demo_encounter.json --write-log combat_log.json
```

The first real next build step is: add **saving throws, spell actions, and a schema validator loader** so encounters fail fast before simulation starts.

This next pack keeps **SRD 5.2.1** as the project’s open rules foundation, and it switches your data validation to **JSON Schema Draft 2020-12** with Python’s `Draft202012Validator`, which the current `jsonschema` docs still expose for repeated instance validation. ([Dungeons & Dragons][1])

```text
dnd-simulator/
├── schemas/
│   ├── action.schema.json
│   ├── creature.schema.json
│   ├── spell.schema.json
│   └── encounter.schema.json
├── examples/
│   └── demo_encounter.json
├── src/
│   ├── schema_loader.py
│   └── turn_engine.py
└── requirements.txt
```

```text
# filename: requirements.txt
jsonschema>=4.26.0,<5
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/action.schema.json",
  "title": "Action",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "kind"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "kind": {
      "type": "string",
      "enum": [
        "attack",
        "spell",
        "heal",
        "dash",
        "dodge",
        "disengage",
        "help",
        "custom"
      ]
    },
    "attack_bonus": {
      "type": "integer"
    },
    "damage": {
      "type": "string",
      "pattern": "^\\s*\\d*d\\d+\\s*([+-]\\s*\\d+)?\\s*$"
    },
    "damage_type": {
      "type": "string",
      "default": "untyped"
    },
    "is_melee": {
      "type": "boolean",
      "default": true
    },
    "range_feet": {
      "type": "integer",
      "minimum": 0,
      "default": 5
    },
    "resolution_mode": {
      "type": "string",
      "enum": [
        "attack",
        "save",
        "effect"
      ]
    },
    "save_ability": {
      "type": "string",
      "enum": [
        "str",
        "dex",
        "con",
        "int",
        "wis",
        "cha"
      ]
    },
    "save_dc": {
      "type": "integer",
      "minimum": 1
    },
    "half_damage_on_save": {
      "type": "boolean",
      "default": false
    },
    "condition_on_failed_save": {
      "type": "string",
      "minLength": 1
    },
    "condition_duration_rounds": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 1
    },
    "spell_level": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9
    },
    "school": {
      "type": "string"
    },
    "notes": {
      "type": "string"
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "attack"
          }
        },
        "required": [
          "kind"
        ]
      },
      "then": {
        "required": [
          "attack_bonus",
          "damage"
        ]
      }
    },
    {
      "if": {
        "properties": {
          "kind": {
            "const": "spell"
          }
        },
        "required": [
          "kind"
        ]
      },
      "then": {
        "required": [
          "resolution_mode"
        ]
      }
    },
    {
      "if": {
        "properties": {
          "kind": {
            "const": "spell"
          },
          "resolution_mode": {
            "const": "attack"
          }
        },
        "required": [
          "kind",
          "resolution_mode"
        ]
      },
      "then": {
        "required": [
          "attack_bonus"
        ]
      }
    },
    {
      "if": {
        "properties": {
          "kind": {
            "const": "spell"
          },
          "resolution_mode": {
            "const": "save"
          }
        },
        "required": [
          "kind",
          "resolution_mode"
        ]
      },
      "then": {
        "required": [
          "save_ability",
          "save_dc"
        ]
      }
    }
  ]
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/creature.schema.json",
  "title": "Creature",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "team",
    "ac",
    "max_hp",
    "current_hp",
    "initiative_bonus",
    "saving_throws",
    "actions"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "team": {
      "type": "string",
      "minLength": 1
    },
    "ac": {
      "type": "integer",
      "minimum": 1
    },
    "max_hp": {
      "type": "integer",
      "minimum": 1
    },
    "current_hp": {
      "type": "integer",
      "minimum": 0
    },
    "initiative_bonus": {
      "type": "integer"
    },
    "speed_feet": {
      "type": "integer",
      "minimum": 0,
      "default": 30
    },
    "saving_throws": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "str",
        "dex",
        "con",
        "int",
        "wis",
        "cha"
      ],
      "properties": {
        "str": {
          "type": "integer",
          "default": 0
        },
        "dex": {
          "type": "integer",
          "default": 0
        },
        "con": {
          "type": "integer",
          "default": 0
        },
        "int": {
          "type": "integer",
          "default": 0
        },
        "wis": {
          "type": "integer",
          "default": 0
        },
        "cha": {
          "type": "integer",
          "default": 0
        }
      }
    },
    "actions": {
      "type": "array",
      "minItems": 1,
      "items": {
        "$ref": "action.schema.json"
      }
    },
    "conditions": {
      "type": "array",
      "default": [],
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "name"
        ],
        "properties": {
          "name": {
            "type": "string",
            "minLength": 1
          },
          "rounds_remaining": {
            "type": [
              "integer",
              "null"
            ],
            "minimum": 1
          }
        }
      }
    },
    "notes": {
      "type": "string"
    }
  }
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/spell.schema.json",
  "title": "Spell",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "level",
    "school",
    "resolution_mode"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "level": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9
    },
    "school": {
      "type": "string",
      "minLength": 1
    },
    "resolution_mode": {
      "type": "string",
      "enum": [
        "attack",
        "save",
        "effect"
      ]
    },
    "attack_bonus": {
      "type": "integer"
    },
    "damage": {
      "type": "string",
      "pattern": "^\\s*\\d*d\\d+\\s*([+-]\\s*\\d+)?\\s*$"
    },
    "damage_type": {
      "type": "string",
      "default": "untyped"
    },
    "save_ability": {
      "type": "string",
      "enum": [
        "str",
        "dex",
        "con",
        "int",
        "wis",
        "cha"
      ]
    },
    "save_dc": {
      "type": "integer",
      "minimum": 1
    },
    "half_damage_on_save": {
      "type": "boolean",
      "default": false
    },
    "condition_on_failed_save": {
      "type": "string"
    },
    "condition_duration_rounds": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 1
    },
    "requires_concentration": {
      "type": "boolean",
      "default": false
    },
    "casting_time": {
      "type": "string"
    },
    "range": {
      "type": "string"
    },
    "duration": {
      "type": "string"
    },
    "notes": {
      "type": "string"
    }
  }
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/encounter.schema.json",
  "title": "Encounter",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "name",
    "seed",
    "round_limit",
    "creatures"
  ],
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "seed": {
      "type": "integer"
    },
    "round_limit": {
      "type": "integer",
      "minimum": 1
    },
    "rules_version": {
      "type": "string",
      "default": "5.2.1"
    },
    "engine_version": {
      "type": "string",
      "default": "0.2.0"
    },
    "creatures": {
      "type": "array",
      "minItems": 2,
      "items": {
        "$ref": "creature.schema.json"
      }
    }
  }
}
```

```json
{
  "name": "Spell and Save Demo",
  "seed": 1337,
  "round_limit": 10,
  "rules_version": "5.2.1",
  "engine_version": "0.2.0",
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
        "cha": 0
      },
      "actions": [
        {
          "id": "longsword",
          "name": "Longsword",
          "kind": "attack",
          "attack_bonus": 5,
          "damage": "1d8+3",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
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
        "cha": 0
      },
      "actions": [
        {
          "id": "fire_bolt",
          "name": "Fire Bolt",
          "kind": "spell",
          "resolution_mode": "attack",
          "attack_bonus": 5,
          "damage": "1d10",
          "damage_type": "fire",
          "is_melee": false,
          "range_feet": 120,
          "spell_level": 0,
          "school": "evocation"
        }
      ],
      "conditions": []
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
        "cha": -1
      },
      "actions": [
        {
          "id": "scimitar",
          "name": "Scimitar",
          "kind": "attack",
          "attack_bonus": 4,
          "damage": "1d6+2",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
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
        "cha": 0
      },
      "actions": [
        {
          "id": "frost_burst",
          "name": "Frost Burst",
          "kind": "spell",
          "resolution_mode": "save",
          "save_ability": "dex",
          "save_dc": 12,
          "damage": "2d6",
          "damage_type": "cold",
          "half_damage_on_save": true,
          "condition_on_failed_save": "prone",
          "condition_duration_rounds": 1,
          "spell_level": 1,
          "school": "evocation"
        }
      ],
      "conditions": []
    }
  ]
}
```

```python
# filename: src/schema_loader.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.validators import RefResolver


class EncounterSchemaError(ValueError):
    pass


def _path_to_text(path_parts: list[Any]) -> str:
    if not path_parts:
        return "$"

    text = "$"
    for part in path_parts:
        if isinstance(part, int):
            text += f"[{part}]"
        else:
            text += f".{part}"
    return text


def _format_validation_errors(errors: list[Any]) -> str:
    lines: list[str] = []
    for error in errors:
        location = _path_to_text(list(error.path))
        lines.append(f"{location}: {error.message}")
    return "\n".join(lines)


def load_schema_store(schema_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    schema_dir = schema_dir.resolve()
    filenames = [
        "action.schema.json",
        "creature.schema.json",
        "spell.schema.json",
        "encounter.schema.json",
    ]

    schemas_by_name: dict[str, dict[str, Any]] = {}
    store: dict[str, dict[str, Any]] = {}

    for filename in filenames:
        path = schema_dir / filename
        if not path.exists():
            raise EncounterSchemaError(f"Missing schema file: {path}")

        schema = json.loads(path.read_text(encoding="utf-8"))
        schemas_by_name[filename] = schema

        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            store[schema_id] = schema

        store[filename] = schema
        store[path.resolve().as_uri()] = schema

    return schemas_by_name, store


def validate_encounter_data(instance: dict[str, Any], schema_dir: Path) -> None:
    schemas_by_name, store = load_schema_store(schema_dir)
    root_schema = schemas_by_name["encounter.schema.json"]

    Draft202012Validator.check_schema(root_schema)

    base_uri = root_schema.get("$id")
    if not isinstance(base_uri, str) or not base_uri:
        base_uri = (schema_dir / "encounter.schema.json").resolve().as_uri()

    resolver = RefResolver(base_uri=base_uri, referrer=root_schema, store=store)
    validator = Draft202012Validator(root_schema, resolver=resolver)

    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.path))
    if errors:
        raise EncounterSchemaError("Encounter schema validation failed:\n" + _format_validation_errors(errors))
```

```python
# filename: src/turn_engine.py

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from schema_loader import EncounterSchemaError, validate_encounter_data


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
    resolution_mode: str | None = None
    save_ability: str | None = None
    save_dc: int | None = None
    half_damage_on_save: bool = False
    condition_on_failed_save: str | None = None
    condition_duration_rounds: int | None = None
    spell_level: int | None = None
    school: str | None = None
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
    def __init__(self, encounter: Encounter) -> None:
        self.encounter = encounter
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
        action: Action,
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

    def resolve_attack_like_action(self, attacker: Creature, target: Creature, action: Action) -> None:
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

    def resolve_save_spell(self, caster: Creature, target: Creature, action: Action) -> None:
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
        if action.kind == "attack":
            self.resolve_attack_like_action(actor, target, action)
            return

        if action.kind == "spell":
            if action.resolution_mode == "save":
                self.resolve_save_spell(actor, target, action)
                return
            if action.resolution_mode == "attack":
                self.resolve_attack_like_action(actor, target, action)
                return

        self.log(
            "turn_skipped_unsupported_action",
            creature_id=actor.id,
            creature_name=actor.name,
            target_id=target.id,
            target_name=target.name,
            action=asdict(action),
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
        damage=data.get("damage"),
        damage_type=str(data.get("damage_type", "untyped")),
        is_melee=bool(data.get("is_melee", True)),
        range_feet=int(data.get("range_feet", 5)),
        resolution_mode=str(data["resolution_mode"]) if data.get("resolution_mode") is not None else None,
        save_ability=str(data["save_ability"]) if data.get("save_ability") is not None else None,
        save_dc=int(data["save_dc"]) if data.get("save_dc") is not None else None,
        half_damage_on_save=bool(data.get("half_damage_on_save", False)),
        condition_on_failed_save=str(data["condition_on_failed_save"]) if data.get("condition_on_failed_save") is not None else None,
        condition_duration_rounds=int(data["condition_duration_rounds"]) if data.get("condition_duration_rounds") is not None else None,
        spell_level=int(data["spell_level"]) if data.get("spell_level") is not None else None,
        school=str(data["school"]) if data.get("school") is not None else None,
        notes=data.get("notes"),
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
        notes=data.get("notes"),
    )


def load_encounter_from_dict(data: dict[str, Any]) -> Encounter:
    return Encounter(
        name=str(data["name"]),
        seed=int(data["seed"]),
        round_limit=int(data["round_limit"]),
        rules_version=str(data.get("rules_version", "5.2.1")),
        engine_version=str(data.get("engine_version", "0.2.0")),
        creatures=[load_creature(creature) for creature in data["creatures"]],
    )


def demo_encounter_dict() -> dict[str, Any]:
    return {
        "name": "Built-in Spell Demo",
        "seed": 1337,
        "round_limit": 10,
        "rules_version": "5.2.1",
        "engine_version": "0.2.0",
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
                        "id": "fire_bolt",
                        "name": "Fire Bolt",
                        "kind": "spell",
                        "resolution_mode": "attack",
                        "attack_bonus": 5,
                        "damage": "1d10",
                        "damage_type": "fire",
                        "is_melee": False,
                        "range_feet": 120,
                        "spell_level": 0,
                        "school": "evocation",
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
                        "id": "frost_burst",
                        "name": "Frost Burst",
                        "kind": "spell",
                        "resolution_mode": "save",
                        "save_ability": "dex",
                        "save_dc": 12,
                        "damage": "2d6",
                        "damage_type": "cold",
                        "half_damage_on_save": True,
                        "condition_on_failed_save": "prone",
                        "condition_duration_rounds": 1,
                        "spell_level": 1,
                        "school": "evocation",
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
                f"[Round {round_number}] {event['caster_name']} resolves spell on {event['target_name']} "
                f"for {event['damage_applied']} damage "
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
    default_schema_dir = (Path(__file__).resolve().parent.parent / "schemas").resolve()

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
        help=f"Directory containing Draft 2020-12 schema files. Default: {default_schema_dir}",
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

    encounter = load_encounter_from_dict(raw_data)
    engine = CombatEngine(encounter)
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
```

```bash
# filename: run_examples.sh
python3 -m pip install -r requirements.txt

python3 src/turn_engine.py --demo
python3 src/turn_engine.py examples/demo_encounter.json
python3 src/turn_engine.py examples/demo_encounter.json --json
python3 src/turn_engine.py examples/demo_encounter.json --write-log combat_log.json
```

The next strong step after this is a **`rules_data/` registry + spell catalog loader** so actions can reference canonical spell definitions instead of duplicating spell fields in encounter JSON.

[1]: https://dnd.wizards.com/resources/systems-reference-document?utm_source=chatgpt.com "SRD v5.2.1 - System Reference Document"

Yes — this is the right next step.

The clean design is:

* `rules_data/` holds canonical, versioned, source-tagged rules content
* encounter files only reference spells by ID
* the engine resolves those IDs through a registry + spell catalog loader
* per-caster runtime values like spell attack bonus or save DC can still be overridden in the encounter action

Use this pack.

```text
dnd-simulator/
├── docs/
│   └── rules-data-architecture.md
├── rules_data/
│   ├── registry.json
│   ├── sources/
│   │   └── srd-5.2.1.source.json
│   └── catalogs/
│       └── spells.srd-5.2.1.json
├── schemas/
│   ├── action.schema.json
│   └── spell.schema.json
├── examples/
│   └── demo_encounter.json
└── src/
    ├── rules_registry.py
    ├── spell_catalog.py
    └── turn_engine.py
```

````md
<!-- filename: docs/rules-data-architecture.md -->
# Rules Data Architecture

## Goal

Move canonical rules content out of encounter files and into a versioned rules registry.

Encounters should describe:
- who is in the fight
- what action they choose
- caster-specific runtime values

Encounters should not duplicate:
- spell school
- spell level
- default damage expressions
- default damage types
- default save ability
- default spell metadata

## Core idea

A spell action in an encounter should look like this:

```json
{
  "id": "cast_fire_bolt",
  "name": "Cast Fire Bolt",
  "kind": "spell",
  "spell_ref": "spell.fire_bolt",
  "attack_bonus_override": 5
}
````

The engine resolves `spell.fire_bolt` from the loaded spell catalogs.

## Why this is better

This gives you:

* one canonical definition per spell
* easier rules upgrades
* less duplication in encounter files
* cleaner provenance and auditing
* safer normalization for future import pipelines
* better support for diffing rule versions

## Separation of responsibility

### rules_data/

Owns:

* source metadata
* catalog metadata
* canonical spell definitions
* version identity
* provenance

### encounter JSON

Owns:

* which creatures are present
* which actions are available
* caster-specific overrides
* scenario-specific tuning

### engine

Owns:

* loading registry
* resolving spell references
* validating required runtime fields
* applying combat mechanics

## Override policy

Some spell values are intrinsic to the spell.
Some are caster-dependent.

### Usually canonical in spell catalog

* id
* name
* level
* school
* resolution_mode
* default damage expression
* default damage type
* save ability
* range
* notes
* source_id

### Usually caster-specific in encounter action

* attack bonus
* save DC
* special local tuning for prototypes
* scenario-specific condition duration overrides

## Registry model

The registry should be explicit and file-based.

It should answer:

* what sources exist
* what catalogs exist
* which file contains each catalog
* which source each catalog belongs to

## Long-term direction

Later you can add:

* monsters catalog
* equipment catalog
* conditions catalog
* actions catalog
* class features catalog
* versioned migration tools
* provenance hashes
* loader benchmarks

````

```json
{
  "version": "0.1.0",
  "default_source_id": "srd-5.2.1",
  "sources": [
    {
      "id": "srd-5.2.1",
      "path": "sources/srd-5.2.1.source.json"
    }
  ],
  "catalogs": {
    "spells": [
      {
        "source_id": "srd-5.2.1",
        "path": "catalogs/spells.srd-5.2.1.json"
      }
    ]
  }
}
````

```json
{
  "source_id": "srd-5.2.1",
  "source_type": "official_open_rules",
  "version": "5.2.1",
  "license": "CC",
  "publisher": "Wizards of the Coast",
  "notes": "Canonical open rules source used by this simulator."
}
```

```json
{
  "catalog_type": "spells",
  "source_id": "srd-5.2.1",
  "version": "5.2.1",
  "spells": [
    {
      "id": "spell.fire_bolt",
      "name": "Fire Bolt",
      "source_id": "srd-5.2.1",
      "level": 0,
      "school": "evocation",
      "resolution_mode": "attack",
      "damage": "1d10",
      "damage_type": "fire",
      "is_melee": false,
      "range_feet": 120,
      "notes": "Canonical attack-roll cantrip example."
    },
    {
      "id": "spell.acid_splash",
      "name": "Acid Splash",
      "source_id": "srd-5.2.1",
      "level": 0,
      "school": "conjuration",
      "resolution_mode": "save",
      "save_ability": "dex",
      "damage": "1d6",
      "damage_type": "acid",
      "half_damage_on_save": false,
      "is_melee": false,
      "range_feet": 60,
      "notes": "Canonical save-based cantrip example."
    }
  ]
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/action.schema.json",
  "title": "Action",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "kind"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "kind": {
      "type": "string",
      "enum": [
        "attack",
        "spell",
        "heal",
        "dash",
        "dodge",
        "disengage",
        "help",
        "custom"
      ]
    },
    "attack_bonus": {
      "type": "integer"
    },
    "damage": {
      "type": "string",
      "pattern": "^\\s*\\d*d\\d+\\s*([+-]\\s*\\d+)?\\s*$"
    },
    "damage_type": {
      "type": "string",
      "default": "untyped"
    },
    "is_melee": {
      "type": "boolean",
      "default": true
    },
    "range_feet": {
      "type": "integer",
      "minimum": 0,
      "default": 5
    },
    "spell_ref": {
      "type": "string",
      "minLength": 1
    },
    "attack_bonus_override": {
      "type": "integer"
    },
    "save_dc_override": {
      "type": "integer",
      "minimum": 1
    },
    "damage_override": {
      "type": "string",
      "pattern": "^\\s*\\d*d\\d+\\s*([+-]\\s*\\d+)?\\s*$"
    },
    "half_damage_on_save_override": {
      "type": "boolean"
    },
    "condition_on_failed_save_override": {
      "type": "string",
      "minLength": 1
    },
    "condition_duration_rounds_override": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 1
    },
    "notes": {
      "type": "string"
    }
  },
  "allOf": [
    {
      "if": {
        "properties": {
          "kind": {
            "const": "attack"
          }
        },
        "required": [
          "kind"
        ]
      },
      "then": {
        "required": [
          "attack_bonus",
          "damage"
        ]
      }
    },
    {
      "if": {
        "properties": {
          "kind": {
            "const": "spell"
          }
        },
        "required": [
          "kind"
        ]
      },
      "then": {
        "required": [
          "spell_ref"
        ]
      }
    }
  ]
}
```

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/schemas/spell.schema.json",
  "title": "Spell",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "id",
    "name",
    "source_id",
    "level",
    "school",
    "resolution_mode"
  ],
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "source_id": {
      "type": "string",
      "minLength": 1
    },
    "level": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9
    },
    "school": {
      "type": "string",
      "minLength": 1
    },
    "resolution_mode": {
      "type": "string",
      "enum": [
        "attack",
        "save",
        "effect"
      ]
    },
    "attack_bonus": {
      "type": "integer"
    },
    "save_ability": {
      "type": "string",
      "enum": [
        "str",
        "dex",
        "con",
        "int",
        "wis",
        "cha"
      ]
    },
    "save_dc": {
      "type": "integer",
      "minimum": 1
    },
    "damage": {
      "type": "string",
      "pattern": "^\\s*\\d*d\\d+\\s*([+-]\\s*\\d+)?\\s*$"
    },
    "damage_type": {
      "type": "string",
      "default": "untyped"
    },
    "half_damage_on_save": {
      "type": "boolean",
      "default": false
    },
    "condition_on_failed_save": {
      "type": "string"
    },
    "condition_duration_rounds": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 1
    },
    "is_melee": {
      "type": "boolean",
      "default": false
    },
    "range_feet": {
      "type": "integer",
      "minimum": 0,
      "default": 60
    },
    "notes": {
      "type": "string"
    }
  }
}
```

```json
{
  "name": "Spell Catalog Demo",
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
        "cha": 0
      },
      "actions": [
        {
          "id": "longsword",
          "name": "Longsword",
          "kind": "attack",
          "attack_bonus": 5,
          "damage": "1d8+3",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
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
        "cha": 0
      },
      "actions": [
        {
          "id": "cast_fire_bolt",
          "name": "Cast Fire Bolt",
          "kind": "spell",
          "spell_ref": "spell.fire_bolt",
          "attack_bonus_override": 5
        }
      ],
      "conditions": []
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
        "cha": -1
      },
      "actions": [
        {
          "id": "scimitar",
          "name": "Scimitar",
          "kind": "attack",
          "attack_bonus": 4,
          "damage": "1d6+2",
          "damage_type": "slashing",
          "is_melee": true,
          "range_feet": 5
        }
      ],
      "conditions": []
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
        "cha": 0
      },
      "actions": [
        {
          "id": "cast_acid_splash",
          "name": "Cast Acid Splash",
          "kind": "spell",
          "spell_ref": "spell.acid_splash",
          "save_dc_override": 12
        }
      ],
      "conditions": []
    }
  ]
}
```

```python
# filename: src/rules_registry.py

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RulesRegistryError(ValueError):
    pass


@dataclass(slots=True)
class SourceRecord:
    id: str
    path: Path
    payload: dict[str, Any]


@dataclass(slots=True)
class CatalogRecord:
    source_id: str
    path: Path
    payload: dict[str, Any]


@dataclass(slots=True)
class RulesRegistry:
    root_dir: Path
    version: str
    default_source_id: str
    sources: dict[str, SourceRecord]
    spell_catalogs: list[CatalogRecord]


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RulesRegistryError(f"Failed to read JSON file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RulesRegistryError(f"Invalid JSON file: {path}: {exc}") from exc


def load_rules_registry(rules_data_dir: Path) -> RulesRegistry:
    rules_data_dir = rules_data_dir.resolve()
    registry_path = rules_data_dir / "registry.json"

    if not registry_path.exists():
        raise RulesRegistryError(f"Missing rules registry file: {registry_path}")

    registry_raw = _read_json_file(registry_path)

    version = str(registry_raw.get("version", "0.0.0"))
    default_source_id = str(registry_raw.get("default_source_id", ""))

    raw_sources = registry_raw.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise RulesRegistryError("rules_data/registry.json must contain a non-empty 'sources' list")

    sources: dict[str, SourceRecord] = {}
    for source_entry in raw_sources:
        if not isinstance(source_entry, dict):
            raise RulesRegistryError("Each source entry must be an object")

        source_id = str(source_entry.get("id", "")).strip()
        rel_path = str(source_entry.get("path", "")).strip()

        if not source_id or not rel_path:
            raise RulesRegistryError("Each source entry must contain non-empty 'id' and 'path'")

        source_path = (rules_data_dir / rel_path).resolve()
        payload = _read_json_file(source_path)
        sources[source_id] = SourceRecord(id=source_id, path=source_path, payload=payload)

    raw_catalogs = registry_raw.get("catalogs", {})
    if not isinstance(raw_catalogs, dict):
        raise RulesRegistryError("'catalogs' must be an object")

    raw_spell_catalogs = raw_catalogs.get("spells", [])
    if not isinstance(raw_spell_catalogs, list):
        raise RulesRegistryError("'catalogs.spells' must be a list")

    spell_catalogs: list[CatalogRecord] = []
    for catalog_entry in raw_spell_catalogs:
        if not isinstance(catalog_entry, dict):
            raise RulesRegistryError("Each spell catalog entry must be an object")

        source_id = str(catalog_entry.get("source_id", "")).strip()
        rel_path = str(catalog_entry.get("path", "")).strip()

        if not source_id or not rel_path:
            raise RulesRegistryError("Each spell catalog entry must contain non-empty 'source_id' and 'path'")

        if source_id not in sources:
            raise RulesRegistryError(f"Spell catalog references unknown source_id: {source_id}")

        catalog_path = (rules_data_dir / rel_path).resolve()
        payload = _read_json_file(catalog_path)
        spell_catalogs.append(CatalogRecord(source_id=source_id, path=catalog_path, payload=payload))

    return RulesRegistry(
        root_dir=rules_data_dir,
        version=version,
        default_source_id=default_source_id,
        sources=sources,
        spell_catalogs=spell_catalogs,
    )
```

```python
# filename: src/spell_catalog.py

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
```

```python
# filename: src/turn_engine.py

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
```

This gives you the real foundation you want:

* canonical spell definitions live in one place
* encounters stay small
* spell refs are versioned and source-tagged
* the engine resolves spell behavior at runtime

The strongest next file after this is `src/rules_linter.py` to catch:

* missing `spell_ref`
* duplicate rule IDs
* orphaned catalogs
* bad source references
* encounter actions that require `attack_bonus_override` or `save_dc_override` but forgot them

```python
# filename: src/rules_linter.py

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from schema_loader import EncounterSchemaError, validate_encounter_data


ALLOWED_RESOLUTION_MODES = {"attack", "save", "effect"}


@dataclass(slots=True)
class LintIssue:
    level: Literal["ERROR", "WARNING"]
    code: str
    message: str
    path: str | None = None

    def render(self) -> str:
        prefix = f"[{self.level}] {self.code}"
        if self.path:
            return f"{prefix} :: {self.path} :: {self.message}"
        return f"{prefix} :: {self.message}"


@dataclass(slots=True)
class CanonicalSpell:
    id: str
    source_id: str
    resolution_mode: str | None
    attack_bonus: int | None
    save_ability: str | None
    save_dc: int | None
    origin_path: Path


def _norm_path(path: Path) -> str:
    return str(path.resolve())


def _read_json_file(path: Path, issues: list[LintIssue], *, code_prefix: str) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        issues.append(
            LintIssue(
                level="ERROR",
                code=f"{code_prefix}_read_failed",
                message=str(exc),
                path=_norm_path(path),
            )
        )
        return None
    except json.JSONDecodeError as exc:
        issues.append(
            LintIssue(
                level="ERROR",
                code=f"{code_prefix}_invalid_json",
                message=f"{exc.msg} at line {exc.lineno}, column {exc.colno}",
                path=_norm_path(path),
            )
        )
        return None

    if not isinstance(raw, dict):
        issues.append(
            LintIssue(
                level="ERROR",
                code=f"{code_prefix}_root_not_object",
                message="Top-level JSON value must be an object.",
                path=_norm_path(path),
            )
        )
        return None

    return raw


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iter_json_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.json") if path.is_file())


def lint_rules_data(rules_data_dir: Path) -> tuple[list[LintIssue], dict[str, CanonicalSpell]]:
    issues: list[LintIssue] = []
    spell_index: dict[str, CanonicalSpell] = {}

    rules_data_dir = rules_data_dir.resolve()
    registry_path = rules_data_dir / "registry.json"

    if not registry_path.exists():
        issues.append(
            LintIssue(
                level="ERROR",
                code="missing_registry",
                message="Missing rules_data/registry.json",
                path=_norm_path(registry_path),
            )
        )
        return issues, spell_index

    registry = _read_json_file(registry_path, issues, code_prefix="registry")
    if registry is None:
        return issues, spell_index

    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_sources_invalid",
                message="'sources' must be a list.",
                path=_norm_path(registry_path),
            )
        )
        raw_sources = []

    source_ids_seen: set[str] = set()
    source_id_to_path: dict[str, Path] = {}

    for index, source_entry in enumerate(raw_sources):
        entry_path = f"{_norm_path(registry_path)}::sources[{index}]"

        if not isinstance(source_entry, dict):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_entry_invalid",
                    message="Source entry must be an object.",
                    path=entry_path,
                )
            )
            continue

        source_id = str(source_entry.get("id", "")).strip()
        source_rel_path = str(source_entry.get("path", "")).strip()

        if not source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_missing_id",
                    message="Source entry is missing a non-empty 'id'.",
                    path=entry_path,
                )
            )
            continue

        if source_id in source_ids_seen:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="duplicate_source_id",
                    message=f"Duplicate source id: {source_id}",
                    path=entry_path,
                )
            )
            continue

        source_ids_seen.add(source_id)

        if not source_rel_path:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_missing_path",
                    message=f"Source '{source_id}' is missing a non-empty 'path'.",
                    path=entry_path,
                )
            )
            continue

        source_path = (rules_data_dir / source_rel_path).resolve()
        source_id_to_path[source_id] = source_path

        if not source_path.exists():
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=f"Source '{source_id}' points to a missing file.",
                    path=_norm_path(source_path),
                )
            )
            continue

        source_payload = _read_json_file(source_path, issues, code_prefix="source")
        if source_payload is None:
            continue

        payload_source_id = str(source_payload.get("source_id", "")).strip()
        if payload_source_id and payload_source_id != source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=(
                        f"Source file source_id mismatch. "
                        f"Registry says '{source_id}', file says '{payload_source_id}'."
                    ),
                    path=_norm_path(source_path),
                )
            )

    raw_catalogs = registry.get("catalogs")
    if raw_catalogs is None:
        raw_catalogs = {}
    if not isinstance(raw_catalogs, dict):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_catalogs_invalid",
                message="'catalogs' must be an object.",
                path=_norm_path(registry_path),
            )
        )
        raw_catalogs = {}

    raw_spell_catalogs = raw_catalogs.get("spells", [])
    if not isinstance(raw_spell_catalogs, list):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_spell_catalogs_invalid",
                message="'catalogs.spells' must be a list.",
                path=_norm_path(registry_path),
            )
        )
        raw_spell_catalogs = []

    referenced_catalog_paths: set[Path] = set()
    duplicate_rule_id_locations: defaultdict[str, list[str]] = defaultdict(list)

    for index, catalog_entry in enumerate(raw_spell_catalogs):
        entry_path = f"{_norm_path(registry_path)}::catalogs.spells[{index}]"

        if not isinstance(catalog_entry, dict):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_entry_invalid",
                    message="Catalog entry must be an object.",
                    path=entry_path,
                )
            )
            continue

        source_id = str(catalog_entry.get("source_id", "")).strip()
        catalog_rel_path = str(catalog_entry.get("path", "")).strip()

        if not source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_missing_source_id",
                    message="Spell catalog entry is missing a non-empty 'source_id'.",
                    path=entry_path,
                )
            )
            continue

        if source_id not in source_id_to_path:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=f"Spell catalog references unknown source_id '{source_id}'.",
                    path=entry_path,
                )
            )

        if not catalog_rel_path:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_missing_path",
                    message="Spell catalog entry is missing a non-empty 'path'.",
                    path=entry_path,
                )
            )
            continue

        catalog_path = (rules_data_dir / catalog_rel_path).resolve()
        referenced_catalog_paths.add(catalog_path)

        if not catalog_path.exists():
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="missing_catalog_file",
                    message="Referenced spell catalog file does not exist.",
                    path=_norm_path(catalog_path),
                )
            )
            continue

        catalog_payload = _read_json_file(catalog_path, issues, code_prefix="catalog")
        if catalog_payload is None:
            continue

        catalog_type = str(catalog_payload.get("catalog_type", "")).strip()
        if catalog_type != "spells":
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_type_invalid",
                    message=f"Expected catalog_type='spells', got {catalog_type!r}.",
                    path=_norm_path(catalog_path),
                )
            )

        payload_source_id = str(catalog_payload.get("source_id", "")).strip()
        if payload_source_id != source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=(
                        f"Catalog source_id mismatch. "
                        f"Registry says '{source_id}', file says '{payload_source_id}'."
                    ),
                    path=_norm_path(catalog_path),
                )
            )

        raw_spells = catalog_payload.get("spells", [])
        if not isinstance(raw_spells, list):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_spells_invalid",
                    message="'spells' must be a list.",
                    path=_norm_path(catalog_path),
                )
            )
            continue

        for spell_index_in_file, raw_spell in enumerate(raw_spells):
            spell_loc = f"{_norm_path(catalog_path)}::spells[{spell_index_in_file}]"

            if not isinstance(raw_spell, dict):
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_record_invalid",
                        message="Spell entry must be an object.",
                        path=spell_loc,
                    )
                )
                continue

            spell_id = str(raw_spell.get("id", "")).strip()
            if not spell_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_missing_id",
                        message="Spell entry is missing a non-empty 'id'.",
                        path=spell_loc,
                    )
                )
                continue

            duplicate_rule_id_locations[spell_id].append(spell_loc)

            spell_source_id = str(raw_spell.get("source_id", "")).strip()
            if not spell_source_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_missing_source_id",
                        message=f"Spell '{spell_id}' is missing 'source_id'.",
                        path=spell_loc,
                    )
                )
            elif spell_source_id != source_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="bad_source_reference",
                        message=(
                            f"Spell '{spell_id}' source_id mismatch. "
                            f"Catalog uses '{source_id}', spell uses '{spell_source_id}'."
                        ),
                        path=spell_loc,
                    )
                )

            resolution_mode = str(raw_spell.get("resolution_mode", "")).strip() or None
            if resolution_mode not in ALLOWED_RESOLUTION_MODES:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_resolution_mode_invalid",
                        message=(
                            f"Spell '{spell_id}' has invalid resolution_mode {resolution_mode!r}. "
                            f"Allowed: {sorted(ALLOWED_RESOLUTION_MODES)}"
                        ),
                        path=spell_loc,
                    )
                )

            attack_bonus = _as_int_or_none(raw_spell.get("attack_bonus"))
            save_ability = str(raw_spell.get("save_ability", "")).strip() or None
            save_dc = _as_int_or_none(raw_spell.get("save_dc"))

            if resolution_mode == "save" and not save_ability:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_missing_save_ability",
                        message=f"Save-based spell '{spell_id}' is missing 'save_ability'.",
                        path=spell_loc,
                    )
                )

            if resolution_mode == "attack" and attack_bonus is None:
                issues.append(
                    LintIssue(
                        level="WARNING",
                        code="spell_requires_attack_bonus_override",
                        message=(
                            f"Attack-roll spell '{spell_id}' has no canonical attack_bonus. "
                            f"Every encounter action using it must provide attack_bonus_override."
                        ),
                        path=spell_loc,
                    )
                )

            if resolution_mode == "save" and save_dc is None:
                issues.append(
                    LintIssue(
                        level="WARNING",
                        code="spell_requires_save_dc_override",
                        message=(
                            f"Save-based spell '{spell_id}' has no canonical save_dc. "
                            f"Every encounter action using it must provide save_dc_override."
                        ),
                        path=spell_loc,
                    )
                )

            if spell_id not in spell_index:
                spell_index[spell_id] = CanonicalSpell(
                    id=spell_id,
                    source_id=spell_source_id or source_id,
                    resolution_mode=resolution_mode,
                    attack_bonus=attack_bonus,
                    save_ability=save_ability,
                    save_dc=save_dc,
                    origin_path=catalog_path,
                )

    for rule_id, locations in sorted(duplicate_rule_id_locations.items()):
        if len(locations) > 1:
            joined = "; ".join(locations)
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="duplicate_rule_ids",
                    message=f"Rule id '{rule_id}' appears multiple times: {joined}",
                )
            )

    catalogs_dir = (rules_data_dir / "catalogs").resolve()
    for catalog_path in _iter_json_files(catalogs_dir):
        resolved = catalog_path.resolve()
        if resolved not in referenced_catalog_paths:
            issues.append(
                LintIssue(
                    level="WARNING",
                    code="orphaned_catalogs",
                    message="Catalog file exists on disk but is not referenced by rules_data/registry.json.",
                    path=_norm_path(catalog_path),
                )
            )

    return issues, spell_index


def _collect_encounter_files(paths: list[Path]) -> list[Path]:
    found: set[Path] = set()

    for path in paths:
        path = path.resolve()
        if path.is_file() and path.suffix.lower() == ".json":
            found.add(path)
            continue

        if path.is_dir():
            for child in path.rglob("*.json"):
                if child.is_file():
                    found.add(child.resolve())

    return sorted(found)


def lint_encounters(
    encounter_paths: list[Path],
    schema_dir: Path,
    spell_index: dict[str, CanonicalSpell],
) -> list[LintIssue]:
    issues: list[LintIssue] = []

    for encounter_path in _collect_encounter_files(encounter_paths):
        raw_data = _read_json_file(encounter_path, issues, code_prefix="encounter")
        if raw_data is None:
            continue

        try:
            validate_encounter_data(raw_data, schema_dir)
        except EncounterSchemaError as exc:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="encounter_schema_invalid",
                    message=str(exc),
                    path=_norm_path(encounter_path),
                )
            )
            continue

        creatures = raw_data.get("creatures", [])
        if not isinstance(creatures, list):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="encounter_creatures_invalid",
                    message="'creatures' must be a list.",
                    path=_norm_path(encounter_path),
                )
            )
            continue

        for creature_index, creature in enumerate(creatures):
            if not isinstance(creature, dict):
                continue

            creature_name = str(creature.get("name", creature.get("id", f"creature[{creature_index}]")))
            actions = creature.get("actions", [])
            if not isinstance(actions, list):
                continue

            for action_index, action in enumerate(actions):
                if not isinstance(action, dict):
                    continue

                kind = str(action.get("kind", "")).strip()
                action_name = str(action.get("name", action.get("id", f"action[{action_index}]")))
                action_loc = (
                    f"{_norm_path(encounter_path)}"
                    f"::creatures[{creature_index}]({creature_name})"
                    f"::actions[{action_index}]({action_name})"
                )

                if kind != "spell":
                    continue

                spell_ref = str(action.get("spell_ref", "")).strip()
                if not spell_ref:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="missing_spell_ref",
                            message="Spell action is missing a non-empty 'spell_ref'.",
                            path=action_loc,
                        )
                    )
                    continue

                spell = spell_index.get(spell_ref)
                if spell is None:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="unknown_spell_ref",
                            message=f"spell_ref '{spell_ref}' does not exist in loaded rules catalogs.",
                            path=action_loc,
                        )
                    )
                    continue

                if spell.resolution_mode == "attack":
                    if spell.attack_bonus is None and action.get("attack_bonus_override") is None:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="missing_attack_bonus_override",
                                message=(
                                    f"Spell action references attack-roll spell '{spell_ref}' "
                                    f"with no canonical attack_bonus, but forgot attack_bonus_override."
                                ),
                                path=action_loc,
                            )
                        )

                if spell.resolution_mode == "save":
                    if spell.save_dc is None and action.get("save_dc_override") is None:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="missing_save_dc_override",
                                message=(
                                    f"Spell action references save-based spell '{spell_ref}' "
                                    f"with no canonical save_dc, but forgot save_dc_override."
                                ),
                                path=action_loc,
                            )
                        )

                    if not spell.save_ability:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="bad_source_reference",
                                message=(
                                    f"Spell action references save-based spell '{spell_ref}' "
                                    f"whose canonical definition is missing save_ability."
                                ),
                                path=action_loc,
                            )
                        )

    return issues


def print_issues(issues: list[LintIssue]) -> None:
    if not issues:
        print("rules_linter: no issues found")
        return

    severity_order = {"ERROR": 0, "WARNING": 1}
    for issue in sorted(issues, key=lambda item: (severity_order[item.level], item.code, item.path or "")):
        print(issue.render())


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    default_rules_data_dir = (project_root / "rules_data").resolve()
    default_schema_dir = (project_root / "schemas").resolve()
    default_examples_dir = (project_root / "examples").resolve()

    parser = argparse.ArgumentParser(
        description="Lint rules_data catalogs and encounter files for D&D simulator consistency problems."
    )
    parser.add_argument(
        "--rules-data-dir",
        type=Path,
        default=default_rules_data_dir,
        help=f"Path to rules_data directory. Default: {default_rules_data_dir}",
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=default_schema_dir,
        help=f"Path to schema directory. Default: {default_schema_dir}",
    )
    parser.add_argument(
        "--encounter",
        dest="encounters",
        type=Path,
        action="append",
        default=[],
        help="Encounter JSON file or directory to lint. May be specified multiple times.",
    )
    parser.add_argument(
        "--skip-encounters",
        action="store_true",
        help="Only lint rules_data/ and skip encounter linting.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures too.",
    )

    args = parser.parse_args()

    if not args.encounters and not args.skip_encounters and default_examples_dir.exists():
        args.encounters = [default_examples_dir]

    return args


def main() -> int:
    args = parse_args()

    rules_issues, spell_index = lint_rules_data(args.rules_data_dir)
    encounter_issues: list[LintIssue] = []

    if not args.skip_encounters:
        encounter_issues = lint_encounters(args.encounters, args.schema_dir, spell_index)

    all_issues = rules_issues + encounter_issues
    print_issues(all_issues)

    error_count = sum(1 for issue in all_issues if issue.level == "ERROR")
    warning_count = sum(1 for issue in all_issues if issue.level == "WARNING")

    print()
    print(
        f"rules_linter summary: errors={error_count} warnings={warning_count} "
        f"spells_loaded={len(spell_index)}"
    )

    if error_count > 0:
        return 1
    if args.strict and warning_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

```bash
# filename: run_rules_linter.sh

python3 src/rules_linter.py
python3 src/rules_linter.py --rules-data-dir rules_data --schema-dir schemas --encounter examples
python3 src/rules_linter.py --skip-encounters
python3 src/rules_linter.py --strict
```

This catches the five cases you called out and also warns when canonical attack/save values are missing and therefore must be supplied by encounter overrides. The next best place to wire it is CI so bad rule data never lands.
