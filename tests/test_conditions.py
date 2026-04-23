import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spell_catalog import SpellCatalog, SpellDefinition
from turn_engine import Action, ActiveCondition, CombatEngine, Creature, Encounter


class ConditionMatrixTests(unittest.TestCase):
    def test_blinded_target_grants_advantage(self) -> None:
        attacker = Creature(
            id="attacker",
            name="Attacker",
            team="A",
            ac=10,
            max_hp=20,
            current_hp=20,
            initiative_bonus=5,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="atk", name="Atk", kind="attack", attack_bonus=5, damage="1d1")],
        )
        target = Creature(
            id="target",
            name="Target",
            team="B",
            ac=10,
            max_hp=20,
            current_hp=20,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
            conditions=[ActiveCondition(name="blinded")],
        )

        encounter = Encounter(
            name="blinded-advantage",
            seed=7,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[attacker, target],
        )

        result = CombatEngine(encounter, SpellCatalog({})).run()
        attack_events = [e for e in result["event_log"] if e["event_type"] == "attack_resolved"]
        self.assertTrue(attack_events)
        self.assertEqual(attack_events[0]["attack_roll_detail"]["mode"], "advantage")

    def test_paralyzed_target_auto_fails_dex_save(self) -> None:
        spell = SpellDefinition(
            id="spell.dex_save",
            name="Dex Save Spell",
            source_id="test",
            level=0,
            school="evocation",
            resolution_mode="save",
            save_ability="dex",
            save_dc=10,
            damage="1d1",
            damage_type="force",
        )
        caster = Creature(
            id="caster",
            name="Caster",
            team="A",
            ac=10,
            max_hp=20,
            current_hp=20,
            initiative_bonus=5,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="cast", name="Cast", kind="spell", spell_ref="spell.dex_save")],
        )
        target = Creature(
            id="target",
            name="Target",
            team="B",
            ac=10,
            max_hp=20,
            current_hp=20,
            initiative_bonus=0,
            saving_throws={"str": 10, "dex": 10, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
            conditions=[ActiveCondition(name="paralyzed")],
        )

        encounter = Encounter(
            name="auto-fail-save",
            seed=9,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[caster, target],
        )

        result = CombatEngine(encounter, SpellCatalog({spell.id: spell})).run()
        save_events = [e for e in result["event_log"] if e["event_type"] == "saving_throw_resolved"]
        self.assertTrue(save_events)
        self.assertTrue(save_events[0]["auto_failed"])
        self.assertFalse(save_events[0]["success"])


if __name__ == "__main__":
    unittest.main()
