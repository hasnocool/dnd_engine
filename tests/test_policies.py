import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from policies import BestDamagePolicy, FocusFirePolicy, SpellFirstPolicy
from spell_catalog import SpellCatalog
from turn_engine import Action, CombatEngine, Creature, Encounter


class PolicyTests(unittest.TestCase):
    def test_spell_first_action_policy(self) -> None:
        actor = Creature(
            id="actor",
            name="Actor",
            team="A",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[
                Action(id="atk", name="Attack", kind="attack", attack_bonus=1, damage="1d4"),
                Action(id="sp", name="Spell", kind="spell", spell_ref="spell.none"),
            ],
        )
        enemy = Creature(
            id="enemy",
            name="Enemy",
            team="B",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
        )
        encounter = Encounter(
            name="policy",
            seed=1,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[actor, enemy],
        )
        engine = CombatEngine(encounter, SpellCatalog({}), action_policy=SpellFirstPolicy())
        chosen = engine.choose_action(actor)
        self.assertIsNotNone(chosen)
        self.assertEqual(chosen.kind, "spell")

    def test_best_damage_policy(self) -> None:
        actor = Creature(
            id="actor",
            name="Actor",
            team="A",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[
                Action(id="low", name="Low", kind="attack", attack_bonus=1, damage="1d4"),
                Action(id="high", name="High", kind="attack", attack_bonus=1, damage="2d10"),
            ],
        )
        encounter = Encounter(
            name="best-dmg",
            seed=1,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[actor],
        )
        engine = CombatEngine(encounter, SpellCatalog({}), action_policy=BestDamagePolicy())
        self.assertEqual(engine.choose_action(actor).id, "high")

    def test_focus_fire_target_policy(self) -> None:
        actor = Creature(
            id="actor",
            name="Actor",
            team="A",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk", name="Attack", kind="attack", attack_bonus=5, damage="1d1")],
        )
        e1 = Creature(
            id="e1",
            name="E1",
            team="B",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop1", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
        )
        e2 = Creature(
            id="e2",
            name="E2",
            team="B",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop2", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
        )
        encounter = Encounter(
            name="focus",
            seed=1,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[actor, e1, e2],
        )
        engine = CombatEngine(encounter, SpellCatalog({}), target_policy=FocusFirePolicy())
        first = engine.choose_target(actor)
        second = engine.choose_target(actor)
        self.assertIsNotNone(first)
        self.assertEqual(first.id, second.id)


if __name__ == "__main__":
    unittest.main()
