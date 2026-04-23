import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rules_registry import load_rules_registry
from condition_catalog import load_condition_catalog
from spell_catalog import load_spell_catalogs
from turn_engine import CombatEngine, load_encounter_from_dict


class TurnEngineE2ETests(unittest.TestCase):
    def test_demo_encounter_deterministic(self) -> None:
        raw = json.loads((ROOT / "examples" / "demo_encounter.json").read_text(encoding="utf-8"))
        registry = load_rules_registry(ROOT / "rules_data")
        spell_catalog = load_spell_catalogs(registry)
        condition_catalog = load_condition_catalog(registry)

        first = CombatEngine(load_encounter_from_dict(raw), spell_catalog, condition_catalog=condition_catalog).run()
        second = CombatEngine(load_encounter_from_dict(raw), spell_catalog, condition_catalog=condition_catalog).run()

        self.assertEqual(first["winner"], "heroes")
        self.assertEqual(first["reason"], "winner_found")
        self.assertEqual(first["event_log"], second["event_log"])


if __name__ == "__main__":
    unittest.main()
