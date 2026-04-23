import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from spell_catalog import SpellCatalog, SpellDefinition
from turn_engine import Action, CombatEngine, Creature, Encounter


class SpellSystemTests(unittest.TestCase):
    def test_aoe_spell_targets_multiple_enemies(self) -> None:
        aoe_spell = SpellDefinition(
            id="spell.aoe",
            name="AOE",
            source_id="test",
            level=0,
            school="evocation",
            resolution_mode="save",
            save_ability="dex",
            save_dc=10,
            damage="1d1",
            damage_type="fire",
            aoe_shape="sphere",
            aoe_size_feet=20,
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
            actions=[Action(id="cast", name="Cast", kind="spell", spell_ref="spell.aoe")],
        )
        enemy_1 = Creature(
            id="enemy_1",
            name="Enemy1",
            team="B",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop1", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
        )
        enemy_2 = Creature(
            id="enemy_2",
            name="Enemy2",
            team="B",
            ac=10,
            max_hp=10,
            current_hp=10,
            initiative_bonus=0,
            saving_throws={"str": 0, "dex": 0, "con": 0, "int": 0, "wis": 0, "cha": 0},
            actions=[Action(id="noop2", name="Noop", kind="attack", attack_bonus=0, damage="1d1")],
        )

        encounter = Encounter(
            name="aoe",
            seed=11,
            round_limit=1,
            rules_version="5.2.1",
            engine_version="0.4.0",
            creatures=[caster, enemy_1, enemy_2],
        )

        result = CombatEngine(encounter, SpellCatalog({aoe_spell.id: aoe_spell})).run()
        aoe_events = [e for e in result["event_log"] if e["event_type"] == "aoe_targets_selected"]
        self.assertTrue(aoe_events)
        self.assertEqual(set(aoe_events[0]["target_ids"]), {"enemy_1", "enemy_2"})


if __name__ == "__main__":
    unittest.main()
