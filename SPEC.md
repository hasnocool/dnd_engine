# dnd_engine — Master Implementation Specification

**Rules source:** SRD 5.2.1 (Creative Commons)  
**Engine version target:** 0.4.0  
**Last updated:** 2026-04-23

---

## Table of Contents

1. [Project Goals](#1-project-goals)
2. [Current State](#2-current-state)
3. [Architecture Overview](#3-architecture-overview)
4. [Canonical Data Contracts](#4-canonical-data-contracts)
5. [Phased Implementation Plan](#5-phased-implementation-plan)
6. [Module Specifications](#6-module-specifications)
7. [Combat Resolution Rules](#7-combat-resolution-rules)
8. [Rules Data Architecture](#8-rules-data-architecture)
9. [Testing Plan](#9-testing-plan)

---

## 1. Project Goals

Build a **deterministic, data-driven D&D 5.2.1 SRD combat simulator** in Python.

### Core principles

| Principle | Meaning |
|---|---|
| Deterministic | Same seed + same encounter always produces the same log |
| Data-driven | All rules content lives in JSON catalogs, not hardcoded in Python |
| Rules-versioned | Every behavior is tagged to a `rules_version` |
| Testable | Engine logic is pure and unit-testable without side effects |
| Extensible | Adding new action types or rule modules never requires rewriting the combat loop |
| Open | Uses only SRD 5.2.1 (CC-licensed) content — no non-open book text |

### Scope of this simulator

In scope:
- Encounter-based combat (turn order, attacks, spells, conditions, damage, defeat)
- Data-driven creature stat blocks (loaded from encounter JSON or monster catalog)
- Spell resolution (attack-roll spells and saving-throw spells)
- Active conditions with timed expiry
- Structured event log suitable for replay and audit

Out of scope (for now):
- Grid / movement / positioning
- Exploration and social pillars
- Character advancement between encounters
- Full narrative campaign state
- Non-SRD content

---

## 2. Current State

### Status as of 2026-04-23

#### Phase 1 — Data Foundation COMPLETE

| Catalog | Count | File |
|---|---|---|
| conditions | 15 | `rules_data/catalogs/conditions.srd-5.2.1.json` |
| spells | 339 | `rules_data/catalogs/spells.srd-5.2.1.json` |
| monsters | 330 | `rules_data/catalogs/monsters.srd-5.2.1.json` |
| weapons | 38 | `rules_data/catalogs/weapons.srd-5.2.1.json` |
| armor | 12 | `rules_data/catalogs/armor.srd-5.2.1.json` |
| magic_items | 259 | `rules_data/catalogs/magic_items.srd-5.2.1.json` |
| classes | 12 | `rules_data/catalogs/classes.srd-5.2.1.json` |
| species | 9 | `rules_data/catalogs/species.srd-5.2.1.json` |
| feats | 17 | `rules_data/catalogs/feats.srd-5.2.1.json` |

All catalogs produced by `src/srd_parser.py` from `rules_data/sources/srd-5.2.1-raw.txt`.
Registry version: `0.2.0`.

#### Runtime Status Snapshot (v0.4.0 target track)

Implemented and currently exercised:
- Expanded `src/turn_engine.py` runtime with action economy, multiattack expansion, spell slots, concentration checks, AoE multi-targeting, damage resistance/immunity/vulnerability, death saves, and massive-damage death handling
- Initiative tie-breaking upgraded with Dex comparison and deterministic seeded coin-flip fallback
- Runtime condition validation integrated with `src/condition_catalog.py` (unknown encounter conditions fail fast)
- Pluggable target/action policies in `src/policies.py` plus CLI policy flags and A/B simulation mode
- Catalog loaders implemented for spells, monsters, conditions, and weapons
- Creature construction and recovery modules implemented in `src/creature_builder.py` and `src/rest_engine.py`
- CI workflow present and active test suite passing (`python -m unittest discover -s tests -p 'test_*.py'`)

#### Remaining gaps (next implementation track)

- Reaction-time interrupts (opportunity attacks, Shield-style reactions, trigger windows)
- Tactical layer (grid movement, line-of-sight, cover, range/path constraints)
- Condition mechanics that depend on battlefield context (for example frightened movement constraints and visibility checks)
- Robust machine-readable upcast scaling beyond simple dice-based patterns in `higher_level`
- Golden-file replay hash assertions and broader regression fixtures for long encounter traces

---

## 3. Architecture Overview

### Layer diagram

```
+----------------------------------------------------------+
|  Encounter JSON  ->  schema_loader  ->  load_encounter() |  Input layer
+----------------------------------------------------------+
|  rules_registry  ->  catalog loaders  ->  in-memory data |  Rules layer
+----------------------------------------------------------+
|  Creature / Action / ResolvedAction / ActiveCondition    |  Domain model
+----------------------------------------------------------+
|              CombatEngine.run()                          |  Rules engine
|  initiative -> round loop -> take_turn() -> resolve()   |
+----------------------------------------------------------+
|              event_log: list[dict]                       |  Event store
+----------------------------------------------------------+
|         build_result() -> JSON / print_summary()         |  Output layer
+----------------------------------------------------------+
```

### Module map

```
src/
  turn_engine.py       Core combat engine - domain model + CombatEngine loop
   policies.py          Target/action policy modules and expected-damage scoring
  rules_registry.py    Loads registry.json; resolves catalog paths
  spell_catalog.py     Loads + indexes spells catalog; SpellDefinition
   monster_catalog.py   Loads + indexes monsters catalog
   condition_catalog.py Loads + indexes conditions catalog
   weapon_catalog.py    Loads + indexes weapons catalog
   creature_builder.py  Builds Creature from class/species/level or monster data
   rest_engine.py       Short/long rest recovery rules
  schema_loader.py     JSON schema validation for encounter files
  rules_linter.py      Cross-file consistency checks
  srd_parser.py        One-time ETL: raw SRD text -> JSON catalogs
   srd_catalog_builder.py Utility builder for catalog extraction workflows
```

---

## 4. Canonical Data Contracts

### 4.1 registry.json (v0.2.0)

Required top-level keys: `version`, `default_source_id`, `sources[]`, `catalogs{}`.

`catalogs` has one array per catalog type, each entry with:
- `source_id` — must equal `"srd-5.2.1"`
- `path` — relative to `rules_data/`
- `count` — expected entry count (validated by linter)

All nine catalog keys must be present: `conditions`, `spells`, `monsters`, `weapons`,
`armor`, `magic_items`, `classes`, `species`, `feats`.

### 4.2 sources/srd-5.2.1.source.json

Required keys: `source_id`, `source_type`, `version`, `license`, `publisher`, `notes`.
`source_id` must equal `"srd-5.2.1"` everywhere it appears.

### 4.3 Spell catalog entry fields

Identity/provenance: `id`, `name`, `source_id`, `level`, `school`, `classes[]`,
`casting_time`, `range`, `components[]`, `duration`, `requires_concentration`, `description`,
`higher_level`.

Engine resolution fields (added by srd_parser or hand-authored):
- `resolution_mode` — `"attack"` or `"save"`
- `attack_bonus`, `damage`, `damage_type`, `is_melee`, `range_feet` (for attack-mode)
- `save_ability`, `save_dc`, `half_damage_on_save` (for save-mode)
- `condition_on_failed_save`, `condition_duration_rounds` (optional)
- `notes`

### 4.4 Monster catalog entry fields

`id`, `name`, `source_id`, `size`, `creature_type`, `alignment`, `ac`, `hp`,
`hp_formula`, `speed`, `ability_scores{}`, `saving_throws{}`, `cr`, `xp`,
`proficiency_bonus`, `skills{}`, `immunities[]`, `resistances[]`, `senses`,
`languages`, `traits[]`, `actions[]`, `bonus_actions[]`, `reactions[]`.

`traits`, `actions`, `bonus_actions`, `reactions` are each `{name, description}` objects.

### 4.5 Condition catalog entry fields

`id`, `name`, `source_id`, `description`, `effects[]`.

`effects[]` are short mechanical labels used by the engine, e.g.
`"attack_rolls_disadvantage"`, `"auto_fail_str_saves"`.

### 4.6 Encounter format

```json
{
  "name": "string",
  "seed": 1337,
  "round_limit": 20,
  "rules_version": "5.2.1",
  "engine_version": "0.4.0",
  "creatures": [
    {
      "id": "creature_id",
      "name": "Display Name",
      "team": "heroes",
      "ac": 16,
      "max_hp": 30,
      "current_hp": 30,
      "initiative_bonus": 2,
      "speed_feet": 30,
      "saving_throws": { "str": 4, "dex": 1, "con": 3, "int": 0, "wis": 1, "cha": 0 },
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
    }
  ]
}
```

Spell action (overrides from encounter; defaults fetched from catalog):

```json
{
  "id": "cast_fire_bolt",
  "name": "Cast Fire Bolt",
  "kind": "spell",
  "spell_ref": "spell.fire_bolt",
  "attack_bonus_override": 5
}
```

### 4.7 Encounter -> catalog linkage contract

For each action where `kind == "spell"`:
- `spell_ref` must match a `spell.id` in the loaded spell catalog
- If the catalog spell has no `attack_bonus` and `resolution_mode == "attack"`,
  encounter must supply `attack_bonus_override`
- If the catalog spell has no `save_dc` and `resolution_mode == "save"`,
  encounter must supply `save_dc_override`

Optional per-encounter override fields:
`attack_bonus_override`, `save_dc_override`, `damage_override`,
`half_damage_on_save_override`, `condition_on_failed_save_override`,
`condition_duration_rounds_override`

### 4.8 Cross-file consistency rules

- `registry.sources[*].id` must match `source file source_id`
- `registry.catalogs.<type>[*].source_id` must equal `"srd-5.2.1"`
- Every `spell.source_id` must equal `"srd-5.2.1"`
- Every `spell_ref` in any encounter must resolve to a valid spell id
- No duplicate `id` values within any single catalog

Violations are reported by `rules_linter.py` with error type `bad_source_reference`.

---

## 5. Phased Implementation Plan

### Phase 1 — Data Foundation  [COMPLETE]

Goal: Parse SRD 5.2.1 into 9 canonical JSON catalogs.

Deliverables:
- `src/srd_parser.py` — full raw-text parser with `_strip_page_headers()`,
  `_text_between()`, `_lines_between()`, `_clean()`, and 9 `parse_*()` functions
- `rules_data/catalogs/*.srd-5.2.1.json` — all 9 catalogs
- `rules_data/registry.json` v0.2.0

Status: Complete.

---

### Phase 2 — Catalog Loader Upgrade  [COMPLETE]

Goal: Give the engine runtime access to all 9 catalogs, not just spells.

Tasks:

1. Update `spell_catalog.py`
   - Current code expects old `catalog_type`/`spells[]` wrapper format
   - Update `SpellDefinition` and loader to read flat array directly
   - Re-verify `CombatEngine` spell resolution still works

2. Create `src/monster_catalog.py`
   - `MonsterDefinition` dataclass mirroring section 4.4 fields
   - `MonsterCatalog` class with `.get(id)` method
   - `load_monster_catalog(registry) -> MonsterCatalog`

3. Create `src/condition_catalog.py`
   - `ConditionDefinition(id, name, source_id, description, effects)`
   - `ConditionCatalog` with `.get(id)` and `.by_name(name)` methods
   - `load_condition_catalog(registry) -> ConditionCatalog`

4. Create `src/weapon_catalog.py`
   - `WeaponDefinition` dataclass; `load_weapon_catalog(registry)`

5. Update `src/rules_registry.py`
   - `load_rules_registry()` returns typed `RulesRegistry` object
   - Add accessors for all 9 catalog types
   - `registry.catalogs["spells"]` returns `list[CatalogManifest]`

6. Update `src/rules_linter.py`
   - Extend to validate all 9 catalog types against registry v0.2.0
   - Check count fields match actual array lengths

7. Update `src/turn_engine.py`
   - Accept `MonsterCatalog` and `ConditionCatalog` alongside `SpellCatalog`

Acceptance criteria:
- `rules_linter.py` passes cleanly against all 9 catalogs
- `CombatEngine` can look up a monster and a condition by id at runtime

---

### Phase 3 — Creature Builder  [COMPLETE]

Goal: Build full `Creature` stat blocks from catalog data rather than hand-specifying
every field in encounter JSON.

Tasks:

1. Extend `Creature` dataclass (in `turn_engine.py`) with:
   - `ability_scores: dict[str, int]`  (str/dex/con/int/wis/cha raw values)
   - `proficiency_bonus: int`
   - `level: int`  (0 for monsters)
   - `spell_slots: dict[int, int]`  (slot level -> remaining count)
   - `concentration_spell: str | None`
   - `action_used: bool`, `bonus_action_used: bool`, `reaction_used: bool`
   - `damage_immunities: list[str]`, `damage_resistances: list[str]`,
     `damage_vulnerabilities: list[str]`
   - `hit_dice_remaining: int`
   - `death_save_successes: int`, `death_save_failures: int`

2. Create `src/creature_builder.py`:

   `build_from_class(class_id, species_id, level, ability_scores, name, team) -> Creature`
   - Look up `hit_die` from classes catalog
   - Look up speed and traits from species catalog
   - Derive `proficiency_bonus` = ceil(1 + level/4)
   - Compute all 6 ability modifiers = floor((score - 10) / 2)
   - Derive saving throw bonuses: proficient = modifier + proficiency_bonus; else = modifier
   - Compute max HP: level 1 = max hit die + Con mod; levels 2+ += (hit_die/2 + 1) + Con mod each
   - Return populated `Creature`

   `build_from_monster(monster_id, monster_catalog) -> Creature`
   - Look up monster from `MonsterCatalog`
   - Map catalog fields to `Creature` dataclass
   - Copy `damage_immunities`, `damage_resistances`, `damage_vulnerabilities`
   - Attempt to parse `actions[].description` into `Action` objects (best-effort)
   - Fall back to `notes` field for unparsed descriptions

Acceptance criteria:
- `build_from_monster("monster.goblin", catalog)` returns a valid `Creature`
- `build_from_class("class.fighter", "species.human", 5, {...}, ...)` returns a valid `Creature`
- Derived saving throws match SRD-correct values

---

### Phase 4 — Action Economy Enforcement  [COMPLETE]

Goal: Limit each creature to 1 action + 1 bonus action + 1 reaction per turn.

Tasks:

1. Add `economy_slot: Literal["action", "bonus_action", "reaction", "free"]` to `Action`

2. In `take_turn()`:
   - Reset `action_used`, `bonus_action_used`, `reaction_used` to `False` at turn start
   - Before resolving each action: check if the required slot is already used
   - Log `turn_action_budget_exhausted` and skip if slot already used
   - After resolving: mark slot as used

3. Implement `kind="multiattack"` action type:
   - New field: `sub_actions: list[str]` — references other action ids on the same creature
   - `take_turn()` expands multiattack: resolves each sub-action in order
   - Each sub-action resolution does NOT consume an additional action slot
   - The multiattack itself consumes the action slot

4. Add `economy_slot` to all action-resolved log events

Acceptance criteria:
- A creature with two `action`-slot attacks only resolves the first one per turn
- A creature with `kind="multiattack"` with two sub-attacks resolves both

---

### Phase 5 — Full Spellcasting System  [PARTIAL]

Goal: SRD-accurate spellcasting with slots, concentration, upcasting, and AoE.

Tasks:

1. Spell slot tracking
   - `Creature.spell_slots: dict[int, int]` — slot level -> remaining count
   - In `resolve_spell_action()`: if spell level > 0, deduct 1 slot of the required level
   - Log `spell_slot_expended`
   - If no slot remaining: log `spell_failed_no_slots` and skip

2. Concentration tracking
   - `Creature.concentration_spell: str | None`
   - Casting a new concentration spell breaks the existing one (log `concentration_broken`)
   - When a concentrating creature takes damage: Con saving throw
     - DC = max(10, floor(damage / 2))
     - On fail: break concentration (log `concentration_check_failed`)
     - On success: log `concentration_check_passed`
   - Read `requires_concentration` from `SpellDefinition` (already in catalog)

3. Upcast resolution
   - Encounter actions may specify `upcast_to_level: int`
   - `resolve_spell_action()` parses `higher_level` catalog text where possible
   - Apply additional dice per level above base

4. AoE targeting (grid-free first pass)
   - `ResolvedAction` gains `aoe_shape: str | None` and `aoe_size_feet: int | None`
   - When `aoe_shape` is set: `choose_targets()` returns all eligible creatures
     (simplified: all enemies for Sphere/Cylinder, first N enemies for Line/Cone)
   - `take_turn()` calls `resolve_save_spell()` for each target

5. Component enforcement (stub)
   - Parse `components[]` from `SpellDefinition`
   - Log a warning (not a hard error) if `"M"` is required and no material is tracked

Acceptance criteria:
- Casting a concentration spell while one is active breaks the old one
- A wizard with 0 slots cannot cast a leveled spell

Remaining gaps to close this phase:
- Improve `higher_level` parsing into structured upcast scaling for non-dice prose patterns
- Add material component inventory/state so component enforcement can be deterministic (not warning-only)
- Expand AoE selection rules beyond simple shape heuristics when tactical positioning is available

---

### Phase 6 — Combat Resolution Completeness  [COMPLETE]

Goal: Fill the remaining gaps in core SRD combat rules.

Tasks:

1. Death saving throws
   - At 0 HP: creature enters `dying` state (not immediately defeated)
   - At start of a dying creature's turn: roll d20 (no modifier)
     - >= 10: success (accumulate)
     - < 10: failure (accumulate)
     - nat-20: regain 1 HP, remove dying status
     - nat-1: 2 failures
   - 3 successes -> `stable` (unconscious, 0 HP, no longer rolling death saves)
   - 3 failures -> creature dies permanently
   - Log: `death_save_rolled`, `creature_stabilized`, `creature_died`

2. Massive damage instadeath
   - If damage from a single hit >= creature's max_hp: creature dies instantly (skip death saves)

3. Multiattack parsing in creature_builder
   - Parse `actions[*].description` for pattern: "The X makes N Y attacks"
   - Auto-generate `kind="multiattack"` action with `sub_actions` referencing parsed attacks

4. Damage resistance / immunity / vulnerability
   - After rolling damage and before subtracting from HP:
     - Immune: damage = 0
     - Resistant: damage = floor(damage / 2)
     - Vulnerable: damage = damage * 2
   - `build_from_monster()` copies these lists from catalog

5. Prone condition mechanics
   - Ranged attacks against prone targets get disadvantage (already: melee gets advantage)

6. Restrained condition mechanics
   - Speed = 0; disadvantage on own attack rolls; attackers have advantage against them

Acceptance criteria:
- Creature at 0 HP rolls death saves each turn
- Creature immune to fire takes 0 fire damage from fire damage rolls

---

### Phase 7 — Full Condition Wiring  [PARTIAL]

Goal: Wire all 15 SRD conditions from `conditions.srd-5.2.1.json` to engine effects.

Condition engine mapping:

| Condition | Engine effect(s) |
|---|---|
| blinded | Attacker: disadvantage on attacks; attacks against blinded: advantage |
| charmed | Cannot attack charmer (targeting rule) |
| deafened | No combat mechanics in Phase 7 |
| exhaustion | Level 1+: disadvantage on attack rolls and ability checks |
| frightened | Disadvantage on attacks while source visible; cannot move closer to source |
| grappled | Speed = 0 |
| incapacitated | Cannot take actions or bonus actions (already in HARD_DISABLE_CONDITIONS) |
| invisible | Advantage on own attacks; attackers targeting invisible have disadvantage |
| paralyzed | Incapacitated; auto-fail STR/DEX saves; attacks vs have advantage; melee auto-crit |
| petrified | Incapacitated; auto-fail STR/DEX saves; resistant to all damage |
| poisoned | Disadvantage on attack rolls + ability checks (already in DISADVANTAGE_CONDITIONS) |
| prone | Disadvantage on own attacks; melee vs prone: advantage; ranged vs prone: disadvantage |
| restrained | Speed = 0; disadvantage on own attacks; attackers have advantage |
| stunned | Incapacitated; auto-fail STR/DEX saves; attacks vs have advantage |
| unconscious | Incapacitated; prone; auto-fail STR/DEX saves; melee vs auto-crit |

Tasks:
1. Wire each condition name to the relevant engine flags in `determine_attack_roll_mode()`,
   saving throw resolution, and damage application
2. Load condition definitions from `ConditionCatalog` at engine startup
3. Linter validates all condition names used in encounters against the catalog

Remaining gaps to close this phase:
- Frightened movement restrictions and visibility checks require tactical movement/LoS state
- Grappled/restrained speed interactions should be enforced through the movement subsystem rather than metadata only
- Preserve condition source metadata in all condition applications to support source-dependent rules consistently

---

### Phase 8 — Rest and Recovery  [COMPLETE]

Goal: Support short rest and long rest between encounters.

Tasks:

1. Create `src/rest_engine.py`:

   `short_rest(creature, hit_dice_to_spend) -> RestResult`
   - Spend up to `hit_dice_to_spend` hit dice (each: roll hit_die + Con mod, add to current_hp up to max)
   - Log dice spent and HP recovered

   `long_rest(creature) -> RestResult`
   - Set `current_hp = max_hp`
   - Restore all spell slots to max
   - Restore `hit_dice_remaining` up to half of level (min 1)
   - Reduce exhaustion level by 1 (if any)
   - Log full recovery

2. `Creature.hit_dice_remaining` tracks remaining hit dice (starts = level)

---

### Phase 9 — AI and Targeting Improvements  [PARTIAL]

Goal: Pluggable AI policies for more realistic creature behavior.

Tasks:

1. `TargetPolicy` protocol (abc):
   - `LowestHPPolicy` — current default
   - `LowestACPolicy`
   - `RandomPolicy`
   - `FocusFirePolicy` — stay on same target until dead

2. `ActionPolicy` protocol (abc):
   - `FirstActionPolicy` — current default
   - `BestDamagePolicy` — pick action with highest expected damage vs target AC
   - `SpellFirstPolicy` — prefer spell actions when slots remain

3. Initiative tie-breaking improvement:
   - Add Dex score comparison before lexical id fallback
   - Final tiebreak: seeded coin flip

4. Reaction hooks:
   - `on_take_damage` and `on_creature_attacked_nearby` event hooks on `Creature`
   - For future: Shield spell interrupt, opportunity attacks with reaction slot

Remaining gaps to close this phase:
- Hook registration exists, but runtime trigger execution and reaction-slot consumption are not fully wired
- Add policy observability output (policy name, candidate scores) to event logs for A/B analysis audits

---

### Phase 10 — Testing and Validation  [PARTIAL]

Goal: Comprehensive test suite ensuring correctness and determinism.

Current coverage snapshot:
- Active unittest suite includes catalog loading, action economy, condition matrix, spells/AoE,
  initiative tie-breaking, policies, runtime condition validation, creature builder/rest, linter, and deterministic e2e encounter replay
- CLI policy-path tests include positive and negative cases for A/B flags and argparse validation

Remaining tasks:

1. Golden-file and hash-stability checks
   - Add deterministic hash assertions for `combat_log.json` and long-trace fixtures
   - Add snapshot-approval flow for intentional engine behavior changes

2. Focused mechanics unit modules
   - Add dedicated dice, attack-resolution, damage-multiplier, and death-save unit files for isolated regression diagnosis

3. CI hardening
   - Add Python-version matrix and stricter failure gates for lint/test parity
   - Add optional nightly extended simulation runs for flake detection

Acceptance criteria:
- Seed-stable fixture hashes are deterministic across CI reruns
- Core combat mechanics are each covered by isolated unit tests and end-to-end replay tests
- CI blocks merges on linter errors or test failures

---

### Phase 11 — Tactical Combat Layer  [PLANNED]

Goal: Add positional combat state so movement-dependent rules become enforceable.

Tasks:

1. Introduce battlefield state model
   - Add optional gridless coordinate and distance model first, with room for grid adapters later
   - Track per-creature position, reach, and movement budget

2. Implement movement and range legality
   - Enforce movement costs, dash interaction, and engagement/reach checks
   - Validate attack/spell target eligibility by distance and visibility

3. Add visibility and cover resolution
   - Support line-of-sight checks and basic cover modifiers
   - Use this state for frightened/charmed source-dependent behavior

Acceptance criteria:
- Movement can be simulated deterministically from encounter state + seed
- Range/LoS violations are rejected or logged as invalid actions
- Condition mechanics that depend on visibility or proximity become enforceable

---

### Phase 12 — Scenario Runner and Productization  [PLANNED]

Goal: Turn the engine into a repeatable simulation service and replay toolchain.

Tasks:

1. Scenario and batch runner
   - Add multi-encounter runner for policy A/B campaigns and Monte Carlo sweeps
   - Emit aggregate metrics (win rate, rounds, defeat reasons, action usage)

2. Replay and observability outputs
   - Define stable event schema versions for replay compatibility
   - Export compact and full-fidelity logs with deterministic hash signatures

3. Integration surfaces
   - Add CLI/JSON report formats suitable for dashboards
   - Add minimal API contract for downstream UI or automation clients

Acceptance criteria:
- Batch runs are reproducible and configurable from CLI/API input
- Replay consumers can validate deterministic log hashes across reruns
- Policy experiments produce machine-readable summary artifacts

---

## 6. Module Specifications

### src/turn_engine.py  (v0.4.0 track)

Responsibility: Domain model dataclasses + CombatEngine runtime loop.

Dataclasses:
- `ActiveCondition(name, rounds_remaining)`
- `Action(id, name, kind, attack_bonus, damage, damage_type, is_melee, range_feet,
    spell_ref, economy_slot, sub_actions, + override fields)`
- `ResolvedAction(id, name, kind, attack_bonus, damage, damage_type, is_melee, range_feet,
    resolution_mode, save_ability, save_dc, half_damage_on_save,
    condition_on_failed_save, condition_duration_rounds,
    spell_level, school, spell_ref, source_id, notes,
    aoe_shape, aoe_size_feet)`
- `Creature(id, name, team, ac, max_hp, current_hp, initiative_bonus, saving_throws,
    actions, conditions, speed_feet, notes, ability_scores, proficiency_bonus, level,
    spell_slots, concentration_spell, action_used, bonus_action_used, reaction_used,
    damage_immunities, damage_resistances, damage_vulnerabilities,
    hit_dice_remaining, death_save_successes, death_save_failures, initiative)`
- `Encounter(name, seed, round_limit, rules_version, engine_version, creatures)`

CombatEngine methods:
- `run() -> dict`
- `roll_initiative()`
- `take_turn(actor)`
- `resolve_action(actor, target, action)`
- `resolve_attack_like_action(attacker, target, action)`
- `resolve_save_spell(caster, target, action)` 
- `apply_condition(target, name, rounds)`
- `expire_end_of_turn_conditions(actor)`
- `choose_target(actor) -> Creature | None`
- `choose_targets(actor, action) -> list[Creature]`  (Phase 5 — AoE)
- `apply_damage(target, amount, damage_type) -> int`  (applies resist/immune/vuln)
- `roll_death_save(creature)`  (Phase 6)
- `roll_concentration_check(creature, damage) -> bool`  (Phase 5)

### src/rules_registry.py

Responsibility: Load `registry.json`; provide typed access to all catalog manifests.

Target interface:
```python
registry = load_rules_registry(rules_data_dir)
registry.catalogs["spells"]   # list[CatalogManifest]
registry.source("srd-5.2.1")  # SourceManifest
```

### src/spell_catalog.py

Responsibility: Load + index spells catalog. Provide `SpellDefinition` to engine.

Breaking change in Phase 2: flat array format (no wrapper object).

### src/monster_catalog.py  [IMPLEMENTED]

Responsibility: Load + index monsters catalog. `MonsterDefinition` with all fields from 4.4.

### src/condition_catalog.py  [IMPLEMENTED]

Responsibility: Load + index conditions catalog. `.by_name("blinded")` accessor.

### src/weapon_catalog.py  [IMPLEMENTED]

Responsibility: Load + index weapons catalog.

### src/creature_builder.py  [IMPLEMENTED]

Responsibility: Factory functions for constructing `Creature` from catalog data.

Functions:
- `build_from_class(class_id, species_id, level, ability_scores, name, team) -> Creature`
- `build_from_monster(monster_id, monster_catalog) -> Creature`

### src/rest_engine.py  [IMPLEMENTED]

### src/policies.py  [IMPLEMENTED]

Responsibility: Action and target policy interfaces plus concrete policy implementations.

Implemented strategies:
- Target policies: `LowestHPPolicy`, `LowestACPolicy`, `RandomPolicy`, `FocusFirePolicy`
- Action policies: `FirstActionPolicy`, `BestDamagePolicy`, `SpellFirstPolicy`

Notes:
- `BestDamagePolicy` uses expected-value scoring versus target AC/save context.
- CLI policy selection and A/B run wiring live in `src/turn_engine.py`.

Responsibility: Short rest and long rest logic.

### src/schema_loader.py

Responsibility: Validate encounter JSON against schemas. No breaking changes planned.

### src/rules_linter.py

Responsibility: Cross-validate all rules data:
- All 9 catalogs present with correct counts
- No duplicate ids in any catalog
- All source_id values match registry sources
- All encounter spell_refs resolve
- Missing required encounter overrides warned

---

## 7. Combat Resolution Rules

### 7.1 Initiative

Roll: `1d20 + initiative_bonus`

Sort (descending):
1. Total initiative
2. Initiative bonus (tiebreak)
3. Dex score (Phase 9)
4. Lexical creature id (final stable tiebreak)

Initiative order is fixed for the encounter.

### 7.2 Turn structure

Each turn (in order):
1. Reset `action_used`, `bonus_action_used`, `reaction_used` = False
2. Skip if creature is dead (not dying)
3. Skip if hard-disable condition active
4. Emit `turn_started`
5. Select action (action policy)
6. Select target (target policy)
7. Check economy slot; if used, skip with log
8. Resolve action
9. Mark economy slot used
10. Expire timed conditions (-1 rounds; remove at 0)

Hard-disable conditions: `unconscious`, `paralyzed`, `stunned`, `incapacitated`

### 7.3 Attack resolution

```
1. Determine roll mode: normal / advantage / disadvantage
2. Roll d20
3. nat-1  -> miss (always)
   nat-20 -> hit + critical (always)
   else   -> hit if (d20 + attack_bonus) >= target.ac
4. On hit: roll damage dice
   crit: double dice count (not modifier)
5. Apply damage multiplier (immunity=0x, resistance=0.5x round down, vulnerability=2x)
6. target.current_hp = max(0, current_hp - modified_damage)
7. If current_hp == 0: enter dying or dead state
```

### 7.4 Saving throw resolution

```
1. Target rolls d20 + saving_throw_bonus[save_ability]
2. If total >= save_dc: save succeeds
3. Success: apply half damage (if half_damage_on_save=true), no condition applied
4. Failure: apply full damage, apply condition_on_failed_save if set
```

### 7.5 Advantage and disadvantage sources

Attacker disadvantage:
- poisoned, blinded, frightened (source in LoS), restrained, invisible target

Attacker advantage:
- invisible attacker, target is prone + melee, target is paralyzed/stunned/unconscious/restrained

Ranged penalty:
- prone target: ranged attacks at disadvantage

When both advantage and disadvantage apply: normal (they cancel).

### 7.6 Condition tick

At end of each creature's turn:
- Decrement each `ActiveCondition.rounds_remaining` by 1
- Remove and log `condition_expired` for any that reach 0
- Conditions with `rounds_remaining = None` are permanent until dispelled

### 7.7 Death saving throws (Phase 6)

At start of dying creature's turn:
- Roll d20 (no modifier)
- >= 10: accumulate success
- < 10: accumulate failure
- nat-20: regain 1 HP, remove dying
- nat-1: add 2 failures
- 3 successes -> stable
- 3 failures -> dead

Massive damage instadeath: single hit >= creature max_hp -> instant death.

### 7.8 Concentration check (Phase 5)

When concentrating creature takes damage:
- Con saving throw, DC = max(10, floor(damage / 2))
- Fail: concentration broken, spell ends
- Success: concentration maintained

### 7.9 Terminal state

Combat ends when:
- Only one team has creatures with `current_hp > 0` -> that team wins
- All creatures dead -> mutual elimination (draw)
- Round limit reached -> draw (or winner if one team remains)

### 7.10 Required event log entries

Every simulation emits (at minimum):
`encounter_started`, `initiative_rolled`, `round_started`, `turn_started`,
`turn_skipped_*`, `attack_declared`, `attack_resolved`, `saving_throw_resolved`,
`spell_resolved`, `damage_applied` (Phase 6), `condition_applied`, `condition_expired`,
`concentration_broken` (Phase 5), `spell_slot_expended` (Phase 5),
`death_save_rolled` (Phase 6), `creature_stabilized` (Phase 6),
`creature_died` (Phase 6), `creature_defeated`, `encounter_ended`

---

## 8. Rules Data Architecture

### Design principle

Encounter files describe **who** fights and **what they do**.
Catalog files describe **how** those things work mechanically.

Encounters must not duplicate catalog data. Default damage dice, save DCs, damage types,
and spell schools all live in catalogs and are resolved at runtime.

### Source provenance chain

```
srd-5.2.1.source.json  (license, version, url)
        |
  registry.json  (catalog manifest: type -> path + count)
        |
  catalogs/*.srd-5.2.1.json  (structured rules data)
        |
  turn_engine.py / creature_builder.py  (runtime resolution)
        |
  encounter JSON -> combat result
```

### Version policy

Every encounter input and every result output carries:
- `rules_version` — SRD version (e.g. `"5.2.1"`)
- `engine_version` — engine build (e.g. `"0.4.0"`)

Same input + same seed + same rules_version + same engine_version = identical output.

---

## 9. Testing Plan

### Strategy

- Core resolution logic is pure (no I/O inside engine methods)
- Use `unittest` (standard library)
- Tests in `tests/` directory
- Maintain both targeted unit tests and deterministic end-to-end replay checks
- Add golden-file hash regression tests as next-step hardening

### Test matrix

| File | What is tested |
|---|---|
| `tests/test_catalog_loading.py` | registry and catalog loader integrity checks |
| `tests/test_action_economy.py` | action slot limits and multiattack expansion |
| `tests/test_conditions.py` | advantage/disadvantage and save auto-fail condition behavior |
| `tests/test_condition_runtime_validation.py` | encounter condition names validated against condition catalog |
| `tests/test_spells.py` | spell resolution and AoE multi-target behavior |
| `tests/test_policies.py` | target/action policy behavior and selection logic |
| `tests/test_initiative.py` | tie-break ordering with deterministic control |
| `tests/test_turn_engine_features.py` | damage immunities, death saves, and core runtime mechanics |
| `tests/test_turn_engine_e2e.py` | deterministic replay for demo encounter |
| `tests/test_creature_builder_and_rest.py` | class/monster creature construction and rest recovery |
| `tests/test_linter.py` | linter execution and non-error guarantees |
| `tests/test_cli_ab.py` | CLI A/B JSON schema, seed stepping, and argparse negative paths |

Planned additions:
- Golden-file hash stability tests for `combat_log.json`
- Dedicated low-level dice/attack/damage-focused unit modules for faster triage

### CI integration

`run_rules_linter.sh` runs as pre-commit / CI gate:

```sh
python3 src/rules_linter.py --rules-data-dir rules_data --schema-dir schemas --encounter examples
```

---

## Appendix — File Index

```
dnd_engine/
  SPEC.md                         this file (master plan)
  SPEC.original.md                original spec backup
  README.md
  requirements.txt
  run_examples.sh
  run_rules_linter.sh
  combat_log.json                 last generated encounter output
  docs/
    engine-architecture.md
    combat-resolution-spec.md
    rules-data-architecture.md
    rules-source.md
  examples/
    demo_encounter.json
  rules_data/
    registry.json                 v0.2.0, all 9 catalogs
    catalogs/
      conditions.srd-5.2.1.json   (15)
      spells.srd-5.2.1.json       (339)
      monsters.srd-5.2.1.json     (330)
      weapons.srd-5.2.1.json      (38)
      armor.srd-5.2.1.json        (12)
      magic_items.srd-5.2.1.json  (259)
      classes.srd-5.2.1.json      (12)
      species.srd-5.2.1.json      (9)
      feats.srd-5.2.1.json        (17)
    sources/
      srd-5.2.1.source.json
  schemas/
    action.schema.json
    creature.schema.json
    encounter.schema.json
    spell.schema.json
  src/
      turn_engine.py                core runtime loop and CLI entrypoint
      policies.py                   target/action policy implementations
      rules_registry.py             typed registry + source/catalog access
      spell_catalog.py              spell loading and indexing
      monster_catalog.py            monster loading and indexing
      condition_catalog.py          condition loading and name/id lookup
      weapon_catalog.py             weapon loading and indexing
      creature_builder.py           creature factories from classes/species/monsters
      rest_engine.py                short rest and long rest recovery logic
      schema_loader.py              encounter schema validation
      rules_linter.py               cross-file consistency and linkage checks
      srd_parser.py                 SRD extraction/parsing utilities
      srd_catalog_builder.py        catalog build helper scripts
   tests/
      test_catalog_loading.py
      test_cli_ab.py
      test_condition_runtime_validation.py
      test_creature_builder_and_rest.py
    test_initiative.py
      test_policies.py
    test_conditions.py
    test_spells.py
    test_action_economy.py
      test_turn_engine_features.py
      test_turn_engine_e2e.py
    test_linter.py
```
