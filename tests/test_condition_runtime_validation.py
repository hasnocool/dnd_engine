import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from condition_catalog import load_condition_catalog
from rules_registry import load_rules_registry
from spell_catalog import load_spell_catalogs
from turn_engine import CombatEngine, CombatEngineError, load_encounter_from_dict


class ConditionRuntimeValidationTests(unittest.TestCase):
    def test_unknown_initial_condition_raises(self) -> None:
        raw = {
            "name": "Invalid Condition Encounter",
            "seed": 1,
            "round_limit": 1,
            "rules_version": "5.2.1",
            "engine_version": "0.4.0",
            "creatures": [
                {
                    "id": "a",
                    "name": "A",
                    "team": "t1",
                    "ac": 10,
                    "max_hp": 10,
                    "current_hp": 10,
                    "initiative_bonus": 0,
                    "saving_throws": {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
                    "actions": [{"id": "atk", "name": "Atk", "kind": "attack", "attack_bonus": 0, "damage": "1d1"}],
                    "conditions": [{"name": "unknown_condition_name"}],
                },
                {
                    "id": "b",
                    "name": "B",
                    "team": "t2",
                    "ac": 10,
                    "max_hp": 10,
                    "current_hp": 10,
                    "initiative_bonus": 0,
                    "saving_throws": {"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
                    "actions": [{"id": "atk2", "name": "Atk2", "kind": "attack", "attack_bonus": 0, "damage": "1d1"}],
                    "conditions": [],
                },
            ],
        }

        registry = load_rules_registry(ROOT / "rules_data")
        spell_catalog = load_spell_catalogs(registry)
        condition_catalog = load_condition_catalog(registry)

        with self.assertRaises(CombatEngineError):
            CombatEngine(load_encounter_from_dict(raw), spell_catalog, condition_catalog=condition_catalog)


if __name__ == "__main__":
    unittest.main()
