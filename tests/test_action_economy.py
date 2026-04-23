import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spell_catalog import SpellCatalog
from turn_engine import Action, CombatEngine, Creature, Encounter


class ActionEconomyTests(unittest.TestCase):
    def test_multiattack_executes_sub_actions(self) -> None:
        actor = Creature(
            id="actor",
            name="Actor",
            team="A",
            ac=10,
            max_hp=20,
            current_hp=20,
            initiative_bonus=5,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[
                Action(
                    id="multiattack",
                    name="Multiattack",
                    kind="multiattack",
                    economy_slot="action",
                    sub_actions=["strike_1", "strike_2"],
                ),
                Action(
                    id="strike_1",
                    name="Strike 1",
                    kind="attack",
                    attack_bonus=100,
                    damage="1d1",
                    damage_type="slashing",
                ),
                Action(
                    id="strike_2",
                    name="Strike 2",
                    kind="attack",
                    attack_bonus=100,
                    damage="1d1",
                    damage_type="slashing",
                ),
            ],
        )

        target = Creature(
            id="target",
            name="Target",
            team="B",
            ac=10,
            max_hp=5,
            current_hp=5,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
        )

        encounter = Encounter(
            name="multiattack",
            seed=123,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[actor, target],
        )

        result = CombatEngine(encounter, SpellCatalog({})).run()
        final = {c["id"]: c for c in result["final_state"]}
        self.assertEqual(final["target"]["current_hp"], 3)


if __name__ == "__main__":
    unittest.main()
