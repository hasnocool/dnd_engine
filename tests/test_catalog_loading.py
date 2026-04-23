import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from condition_catalog import load_condition_catalog
from monster_catalog import load_monster_catalog
from rules_registry import load_rules_registry
from spell_catalog import load_spell_catalogs
from weapon_catalog import load_weapon_catalog


class CatalogLoadingTests(unittest.TestCase):
    def test_load_all_catalogs(self) -> None:
        registry = load_rules_registry(ROOT / "rules_data")
        self.assertEqual(registry.version, "0.2.0")

        spell_catalog = load_spell_catalogs(registry)
        monster_catalog = load_monster_catalog(registry)
        condition_catalog = load_condition_catalog(registry)
        weapon_catalog = load_weapon_catalog(registry)

        self.assertGreaterEqual(len(spell_catalog.ids()), 300)
        self.assertGreaterEqual(len(monster_catalog.ids()), 300)
        self.assertGreaterEqual(len(condition_catalog.ids()), 10)
        self.assertGreaterEqual(len(weapon_catalog.ids()), 30)

        self.assertTrue(spell_catalog.has("spell.fire_bolt"))
        self.assertTrue(condition_catalog.has_name("blinded"))


if __name__ == "__main__":
    unittest.main()
