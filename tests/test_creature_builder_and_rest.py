import random
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from creature_builder import build_from_class, build_from_monster
from monster_catalog import load_monster_catalog
from rest_engine import long_rest, short_rest
from rules_registry import load_rules_registry


class CreatureBuilderAndRestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_rules_registry(ROOT / "rules_data")

    def test_build_from_class(self) -> None:
        creature = build_from_class(
            class_id="class.fighter",
            species_id="species.human",
            level=5,
            ability_scores={"str": 16, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
            name="Test Fighter",
            team="heroes",
            registry=self.registry,
        )

        self.assertEqual(creature.level, 5)
        self.assertGreater(creature.max_hp, 10)
        self.assertEqual(creature.current_hp, creature.max_hp)
        self.assertTrue(creature.actions)

    def test_build_from_monster(self) -> None:
        monsters = load_monster_catalog(self.registry)
        monster_id = monsters.ids()[0]
        creature = build_from_monster(monster_id, monsters)

        self.assertEqual(creature.id, monster_id)
        self.assertGreater(creature.max_hp, 0)
        self.assertTrue(creature.actions)

    def test_rest_engines(self) -> None:
        creature = build_from_class(
            class_id="class.fighter",
            species_id="species.human",
            level=4,
            ability_scores={"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
            name="Rest Tester",
            team="heroes",
            registry=self.registry,
        )
        creature.current_hp = max(1, creature.max_hp // 2)
        creature.hit_dice_remaining = creature.level
        creature.exhaustion_level = 1

        short = short_rest(creature, hit_dice_to_spend=2, rng=random.Random(42))
        self.assertGreaterEqual(short.hp_after, short.hp_before)
        self.assertLess(short.hit_dice_after, short.hit_dice_before)

        creature.current_hp = max(1, creature.current_hp - 5)
        creature.spell_slot_max = {1: 2}
        creature.spell_slots = {1: 0}

        long = long_rest(creature)
        self.assertEqual(long.hp_after, creature.max_hp)
        self.assertEqual(creature.spell_slots.get(1), 2)
        self.assertLessEqual(long.exhaustion_after, long.exhaustion_before)


if __name__ == "__main__":
    unittest.main()
