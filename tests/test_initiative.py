import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spell_catalog import SpellCatalog
from turn_engine import Action, CombatEngine, Creature, Encounter


class InitiativeTests(unittest.TestCase):
    def test_tiebreak_uses_dex_then_seeded_coinflip(self) -> None:
        a = Creature(
            id="a",
            name="A",
            team="T1",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            ability_scores={"str": 10, "dex": 8, "con": 10, "int": 10, "wis": 10, "cha": 10},
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk_a", name="Atk", kind="attack", attack_bonus=0, damage="1d1")],
        )
        b = Creature(
            id="b",
            name="B",
            team="T2",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            ability_scores={"str": 10, "dex": 16, "con": 10, "int": 10, "wis": 10, "cha": 10},
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk_b", name="Atk", kind="attack", attack_bonus=0, damage="1d1")],
        )
        encounter = Encounter(
            name="initiative",
            seed=77,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[a, b],
        )

        engine = CombatEngine(encounter, SpellCatalog({}))
        engine.roll_d20 = lambda mode="normal": (10, {"mode": mode, "rolls": [10], "selected": 10})
        engine.roll_initiative()

        # With tied initiative and bonus, dex should decide before coin flip.
        self.assertEqual(engine.initiative_order[0].id, "b")


if __name__ == "__main__":
    unittest.main()
