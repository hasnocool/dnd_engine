import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spell_catalog import SpellCatalog, SpellDefinition
from turn_engine import CombatEngine, Encounter, Action, Creature


class TurnEngineFeatureTests(unittest.TestCase):
    def test_damage_immunity_applies(self) -> None:
        spell_catalog = SpellCatalog({
            "spell.test": SpellDefinition(
                id="spell.test",
                name="Test Spell",
                source_id="test",
                level=0,
                school="evocation",
                resolution_mode="attack",
                attack_bonus=100,
                damage="1d8",
                damage_type="fire",
            )
        })

        attacker = Creature(
            id="attacker",
            name="Attacker",
            team="A",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk", name="Atk", kind="attack", attack_bonus=100, damage="1d6", damage_type="fire")],
        )
        defender = Creature(
            id="defender",
            name="Defender",
            team="B",
            ac=10,
            max_hp=20,
            current_hp=20,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop", name="Noop", kind="attack", attack_bonus=0, damage="1d4")],
            damage_immunities=["fire"],
        )

        encounter = Encounter(
            name="immunity",
            seed=1,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[attacker, defender],
        )

        result = CombatEngine(encounter, spell_catalog).run()
        final = {c["id"]: c for c in result["final_state"]}
        self.assertEqual(final["defender"]["current_hp"], 20)

    def test_dying_creature_rolls_death_saves(self) -> None:
        spell_catalog = SpellCatalog({})
        dying = Creature(
            id="dying",
            name="Dying",
            team="A",
            ac=10,
            max_hp=10,
            current_hp=0,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk", name="Atk", kind="attack", attack_bonus=5, damage="1d4")],
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
            actions=[Action(id="atk2", name="Atk2", kind="attack", attack_bonus=0, damage="1d1")],
        )
        ally = Creature(
            id="ally",
            name="Ally",
            team="A",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk3", name="Atk3", kind="attack", attack_bonus=0, damage="1d1")],
        )

        encounter = Encounter(
            name="death-save",
            seed=2,
            round_limit=2,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[dying, ally, enemy],
        )

        result = CombatEngine(encounter, spell_catalog).run()
        events = [e["event_type"] for e in result["event_log"]]
        self.assertIn("death_save_rolled", events)


if __name__ == "__main__":
    unittest.main()
