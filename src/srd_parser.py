"""
srd_parser.py – Parse SRD 5.2.1 extracted text into canonical JSON catalogs.

Produces under rules_data/catalogs/:
  conditions.srd-5.2.1.json
  spells.srd-5.2.1.json
  monsters.srd-5.2.1.json
  weapons.srd-5.2.1.json
  armor.srd-5.2.1.json
  magic_items.srd-5.2.1.json
  classes.srd-5.2.1.json
  species.srd-5.2.1.json
  feats.srd-5.2.1.json

Uses srd-5.2.1-raw.txt produced by: pdftotext -raw SRD_CC_v5.2.1.pdf

Run:
  python3 src/srd_parser.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
# Raw text (proper reading order from pdftotext -raw)
SRD_TEXT = ROOT / "rules_data" / "sources" / "srd-5.2.1-raw.txt"
CATALOG_DIR = ROOT / "rules_data" / "catalogs"
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_ID = "srd-5.2.1"

# ── Shared helpers ─────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    """Strip whitespace, collapse runs, and fix soft-hyphen line-break artefacts."""
    s = s.strip()
    # Rejoin hyphenated line breaks: "descrip-\ntion" → "description"
    s = re.sub(r"-\n", "", s)
    s = re.sub(r"\n", " ", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s


def _strip_page_headers(raw: str) -> str:
    """Remove pdftotext page footer/header lines and form-feed characters."""
    # Form-feed (0x0C) page separators
    raw = raw.replace("\x0c", "\n")
    raw = re.sub(r"System Reference Document 5\.2\.1\s*\n\d+\s*\n?", "", raw)
    raw = re.sub(r"\n\d+\n\s*System Reference Document 5\.2\.1\s*\n", "\n", raw)
    # Collapse multiple blank lines introduced by stripping
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw


def _lines_between(lines: list[str], start_re: str, end_re: str, skip_first: bool = True) -> list[str]:
    """Extract lines between two regex anchors (exclusive)."""
    capturing = False
    out: list[str] = []
    for line in lines:
        if not capturing and re.search(start_re, line):
            capturing = True
            if not skip_first:
                out.append(line)
            continue
        if capturing:
            if re.search(end_re, line):
                break
            out.append(line)
    return out


def _text_between(raw: str, start_re: str, end_re: str) -> str:
    """Extract substring of raw text between two regex markers."""
    m_start = re.search(start_re, raw)
    if not m_start:
        return ""
    after_start = raw[m_start.end():]
    m_end = re.search(end_re, after_start)
    return after_start[: m_end.start()] if m_end else after_start


def _write(name: str, obj: Any) -> None:
    path = CATALOG_DIR / f"{name}.{SOURCE_ID}.json"
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    count = len(obj)
    print(f"  ✓ {path.name}  ({count} items)")



# ── 1. Conditions ──────────────────────────────────────────────────────────────

_CONDITION_NAMES = [
    "Blinded", "Charmed", "Deafened", "Exhaustion", "Frightened",
    "Grappled", "Incapacitated", "Invisible", "Paralyzed", "Petrified",
    "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious",
]


def parse_conditions(raw: str) -> list[dict[str, Any]]:
    """Extract condition definitions. Each is under 'Name [Condition]' in the Glossary."""
    glossary = _text_between(raw, r"\nRules Glossary\n", r"\nGameplay Toolbox\n")
    conditions: list[dict[str, Any]] = []

    # Pattern: "Name [Condition]\n<text until next heading>"
    cond_re = re.compile(
        r"([A-Z][A-Za-z ]+) \[Condition\]\n(.*?)(?=\n[A-Z][A-Za-z]+(?: \[|\n)|\Z)",
        re.DOTALL,
    )
    for m in cond_re.finditer(glossary):
        name = m.group(1).strip()
        body = _clean(m.group(2))
        if name not in _CONDITION_NAMES:
            continue
        # Parse bullet effects: "Effect Name. Description text."
        effects: list[dict[str, str]] = []
        effect_re = re.compile(r"([A-Z][A-Za-z ':]+)\.\s+(.+?)(?=(?:[A-Z][A-Za-z ':]+\.\s)|\Z)", re.DOTALL)
        for em in effect_re.finditer(body):
            effects.append({"name": _clean(em.group(1)), "description": _clean(em.group(2))})
        conditions.append({
            "id": name.lower(),
            "name": name,
            "source": SOURCE_ID,
            "description": body,
            "effects": effects,
        })

    # Ensure all 15 conditions are present even if regex misses some
    found_names = {c["name"] for c in conditions}
    for name in _CONDITION_NAMES:
        if name not in found_names:
            # Minimal fallback: search directly
            fallback_m = re.search(
                rf"{re.escape(name)} \[Condition\]\n(.*?)(?=\n[A-Z]|\Z)", glossary, re.DOTALL
            )
            if fallback_m:
                body = _clean(fallback_m.group(1))
                conditions.append({"id": name.lower(), "name": name, "source": SOURCE_ID, "description": body, "effects": []})

    conditions.sort(key=lambda c: _CONDITION_NAMES.index(c["name"]) if c["name"] in _CONDITION_NAMES else 99)
    return conditions


# ── 2. Spells ─────────────────────────────────────────────────────────────────

def parse_spells(raw: str) -> list[dict[str, Any]]:
    """Parse the Spell Descriptions section."""
    section = _text_between(raw, r"\nSpell Descriptions\n", r"\nRules Glossary\n")
    section = _strip_page_headers(section)

    spells: list[dict[str, Any]] = []

    # Spell header patterns (two forms):
    #   "Level N School (Class1, Class2 [,\nClass3])\n"  — levelled spell
    #   "School Cantrip (Class1, Class2 [,\nClass3])\n"  — cantrip
    # The class list sometimes wraps to the next line before the closing ")"
    _HDR_RE = re.compile(
        r"(?:Level (\d+) (\w+)|(\w+) Cantrip)"  # level+school or cantrip marker
        r" \(([^)]*(?:\n[^)]+)?)\)"              # class list (may wrap one line)
    )

    # Split the section into spell blocks by finding each "Name\nHeader\n" boundary
    # Strategy: walk line-by-line; when we see a potential spell header, emit prev block
    lines = section.split("\n")
    blocks: list[list[str]] = []
    current: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if line i+1 looks like a spell header
        if current and i + 1 < len(lines):
            next_line = lines[i + 1]
            # Also allow class list wrapping: "Level N School (Foo,\nBar)"
            if re.match(r"(?:Level \d+ \w+|\w+ Cantrip) \(", next_line):
                # This line is a spell name
                if blocks:
                    pass  # previous block already appended
                blocks.append(current)
                current = [line]
                i += 1
                continue
        current.append(line)
        i += 1
    if current:
        blocks.append(current)

    for block_lines in blocks:
        if len(block_lines) < 5:
            continue
        name = _clean(block_lines[0])
        if not name or len(name) > 60 or not name[0].isupper():
            continue

        # Find header line (could be line 1, accounting for wrapped class lists)
        header_text = ""
        header_end_idx = 1
        for j in range(1, min(4, len(block_lines))):
            if re.match(r"(?:Level \d+ \w+|\w+ Cantrip) \(", block_lines[j]):
                # Build possibly-wrapped header
                raw_hdr = block_lines[j]
                if ")" not in raw_hdr and j + 1 < len(block_lines):
                    raw_hdr = raw_hdr + " " + block_lines[j + 1]
                    header_end_idx = j + 2
                else:
                    header_end_idx = j + 1
                header_text = raw_hdr
                break

        if not header_text:
            continue

        hdr_m = _HDR_RE.search(header_text)
        if not hdr_m:
            continue

        if hdr_m.group(1):  # levelled spell: Level N School (...)
            level = int(hdr_m.group(1))
            school = hdr_m.group(2).capitalize()
        else:               # cantrip: School Cantrip (...)
            level = 0
            school = hdr_m.group(3).capitalize()

        classes_raw = re.sub(r"\s+", " ", hdr_m.group(4))
        classes = [c.strip() for c in classes_raw.split(",") if c.strip()]

        # Remaining lines = Casting Time / Range / Components / Duration / Description
        rest_lines = block_lines[header_end_idx:]
        fields: dict[str, str] = {}
        desc_lines: list[str] = []
        in_desc = False
        for ln in rest_lines:
            if not in_desc:
                for field, pattern in [
                    ("casting_time", r"Casting Time:\s*(.+)"),
                    ("range", r"Range:\s*(.+)"),
                    ("components", r"Components?:\s*(.+)"),
                    ("duration", r"Duration:\s*(.+)"),
                ]:
                    fm = re.match(pattern, ln)
                    if fm:
                        fields[field] = fm.group(1).strip()
                        if field == "duration":
                            in_desc = True
                        break
            else:
                desc_lines.append(ln)

        if "casting_time" not in fields or "duration" not in fields:
            continue

        duration = fields["duration"]
        requires_conc = "concentration" in duration.lower()
        comp_raw = fields.get("components", "")

        # Parse components
        comp_list: list[str] = []
        material: str | None = None
        base_comp = comp_raw.split("(")[0]
        for c in re.split(r",\s*", base_comp):
            c = c.strip().upper()
            if c in ("V", "S", "M"):
                comp_list.append(c)
        mat_m = re.search(r"\(([^)]+)\)", comp_raw)
        if mat_m:
            material = mat_m.group(1)

        desc = _clean("\n".join(desc_lines))

        # Extract upcast text
        upcast: str | None = None
        upcast_m = re.search(r"Using a Higher.Level Spell Slot\.?\s+(.+)", desc, re.DOTALL)
        if upcast_m:
            upcast = _clean(upcast_m.group(1))
            desc = _clean(desc[: upcast_m.start()])

        spell: dict[str, Any] = {
            "id": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "name": name,
            "source": SOURCE_ID,
            "level": level,
            "school": school,
            "classes": classes,
            "casting_time": fields.get("casting_time", ""),
            "range": fields.get("range", ""),
            "components": comp_list,
            "duration": duration,
            "requires_concentration": requires_conc,
        }
        if material:
            spell["material_component"] = material
        if upcast:
            spell["higher_level"] = upcast
        spell["description"] = desc
        spells.append(spell)

    # Deduplicate by id
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for sp in spells:
        if sp["id"] not in seen:
            seen.add(sp["id"])
            unique.append(sp)

    return unique


# ── 3. Monsters ───────────────────────────────────────────────────────────────

_CR_MAP: dict[str, float] = {
    "0": 0.0, "1/8": 0.125, "1/4": 0.25, "1/2": 0.5,
    **{str(n): float(n) for n in range(1, 31)},
}

_SIZE_WORDS = r"Tiny|Small|Medium|Large|Huge|Gargantuan"


def _parse_monster_block(block: str) -> dict[str, Any] | None:
    lines = block.strip().split("\n")
    if len(lines) < 5:
        return None

    # Line 0 = name, line 1 = "Size Type, Alignment"
    name = _clean(lines[0])
    if not name:
        return None

    type_m = re.match(
        rf"({_SIZE_WORDS})\s+([\w ()\-/]+?),\s*(.+)",
        lines[1].strip(),
        re.IGNORECASE,
    )
    if not type_m:
        return None

    monster: dict[str, Any] = {
        "id": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
        "name": name,
        "source": SOURCE_ID,
        "size": type_m.group(1).capitalize(),
        "creature_type": _clean(type_m.group(2)),
        "alignment": _clean(type_m.group(3)),
    }

    # AC
    ac_m = re.search(r"AC\s+(\d+)", block)
    if ac_m:
        monster["ac"] = int(ac_m.group(1))

    # Initiative
    init_m = re.search(r"Initiative\s+([+-]\d+)\s*\((\d+)\)", block)
    if init_m:
        monster["initiative_bonus"] = int(init_m.group(1))

    # HP
    hp_m = re.search(r"HP\s+(\d+)\s*\(([^)]+)\)", block)
    if hp_m:
        monster["hp"] = int(hp_m.group(1))
        monster["hp_formula"] = hp_m.group(2).strip()

    # Speed
    speed_m = re.search(r"Speed\s+([\d][\w .,()]+?)(?:\n)", block)
    if speed_m:
        monster["speed"] = _clean(speed_m.group(1))

    # Ability scores: "Str 14 +2 +2 Dex 11 +0 +0 Con 13 +1 +1"
    ab_re = re.compile(r"(Str|Dex|Con|Int|Wis|Cha)\s+(\d+)\s+([+\-−]\d+)\s+([+\-−]\d+)")
    ability_scores: dict[str, int] = {}
    saving_throws: dict[str, int] = {}
    for ab_m in ab_re.finditer(block):
        ab = ab_m.group(1).lower()
        # Replace unicode minus with ASCII minus
        raw_save = ab_m.group(4).replace("−", "-")
        raw_score = ab_m.group(2)
        ability_scores[ab] = int(raw_score)
        saving_throws[ab] = int(raw_save)
    if ability_scores:
        monster["ability_scores"] = ability_scores
        monster["saving_throws"] = saving_throws

    # CR and XP
    cr_m = re.search(r"CR\s+([\d/]+)\s*\(XP\s+([\d,]+)", block)
    if cr_m:
        cr_str = cr_m.group(1)
        monster["cr"] = _CR_MAP.get(cr_str, cr_str)
        monster["xp"] = int(cr_m.group(2).replace(",", ""))

    # Proficiency bonus
    pb_m = re.search(r"PB\s+\+(\d+)", block)
    if pb_m:
        monster["proficiency_bonus"] = int(pb_m.group(1))

    # Skills
    skills_m = re.search(r"Skills\s+([^\n]+)", block)
    if skills_m:
        monster["skills"] = _clean(skills_m.group(1))

    # Damage fields
    for field, label in [
        ("immunities", r"Immunities"),
        ("resistances", r"Resistances?"),
        ("vulnerabilities", r"Vulnerabilities?"),
    ]:
        fm = re.search(rf"{label}\s+([^\n]+)", block)
        if fm:
            monster[field] = _clean(fm.group(1))

    # Senses / Languages
    for field, label in [("senses", "Senses"), ("languages", "Languages")]:
        fm = re.search(rf"{label}\s+([^\n]+)", block)
        if fm:
            monster[field] = _clean(fm.group(1))

    # Gear
    gear_m = re.search(r"Gear\s+([^\n]+)", block)
    if gear_m:
        monster["gear"] = _clean(gear_m.group(1))

    # Traits, Actions, Bonus Actions, Reactions, Legendary Actions
    def _extract_features(section_label: str) -> list[dict[str, str]]:
        sec_m = re.search(
            rf"\n{re.escape(section_label)}\n(.*?)(?=\n(?:Traits|Actions|Bonus Actions|Reactions|Legendary Actions)\n|\Z)",
            block,
            re.DOTALL,
        )
        if not sec_m:
            return []
        body = sec_m.group(1)
        items: list[dict[str, str]] = []
        # Features: "Feature Name. Description."  or "Feature Name (Recharge N). desc"
        feat_re = re.compile(
            r"([A-Z][^\n.]{0,80}(?:\([^)]*\))?)\.\s+(.+?)(?=(?:[A-Z][^\n.]{0,80}(?:\([^)]*\))?)\.\s|\Z)",
            re.DOTALL,
        )
        for feat_m in feat_re.finditer(body):
            feat_name = _clean(feat_m.group(1))
            feat_desc = _clean(feat_m.group(2))
            if feat_name and feat_desc and len(feat_name) < 80:
                items.append({"name": feat_name, "description": feat_desc})
        return items

    for sec_label in ("Traits", "Actions", "Bonus Actions", "Reactions", "Legendary Actions"):
        key = sec_label.lower().replace(" ", "_")
        feats = _extract_features(sec_label)
        if feats:
            monster[key] = feats

    return monster if "ac" in monster else None


def parse_monsters(raw: str) -> list[dict[str, Any]]:
    """Parse Monsters A–Z and Animals sections."""
    section = _text_between(raw, r"\nMonsters A.Z\n", r"\nIndex of Stat\b|\Z")
    section = _strip_page_headers(section)

    # Split the section into individual monster blocks.
    # A new monster starts with: "Name\n  Size Type, Alignment"
    # Find all positions where "Name\n<Size>" occurs
    block_starts: list[int] = []
    lines = section.split("\n")
    for i in range(len(lines) - 1):
        # The name line is typically short (1–5 words, capitalised)
        name_cand = lines[i].strip()
        next_line = lines[i + 1].strip()
        if (
            name_cand
            and 1 <= len(name_cand.split()) <= 6
            and name_cand[0].isupper()
            and re.match(rf"^({_SIZE_WORDS})\s+", next_line, re.IGNORECASE)
            and not re.search(r"[,;.?!]", name_cand)
        ):
            # Calculate char offset
            offset = sum(len(line_text) + 1 for line_text in lines[:i])
            block_starts.append(offset)

    monsters: list[dict[str, Any]] = []
    for j, start in enumerate(block_starts):
        end = block_starts[j + 1] if j + 1 < len(block_starts) else len(section)
        block = section[start:end]
        parsed = _parse_monster_block(block)
        if parsed:
            monsters.append(parsed)

    # Deduplicate by id (keep first occurrence)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for m in monsters:
        if m["id"] not in seen:
            seen.add(m["id"])
            unique.append(m)

    return unique


# ── 4. Weapons ────────────────────────────────────────────────────────────────

_WEAPON_CATEGORY_HEADERS = [
    ("simple_melee", "Simple Melee Weapons"),
    ("simple_ranged", "Simple Ranged Weapons"),
    ("martial_melee", "Martial Melee Weapons"),
    ("martial_ranged", "Martial Ranged Weapons"),
]


def parse_weapons(raw: str) -> list[dict[str, Any]]:
    """Extract weapon tables from the Equipment section."""
    section = _text_between(raw, r"\nEquipment\n", r"\nSpells\n|\nSpell Descriptions\n")
    section = _strip_page_headers(section)

    # Pre-join wrapped property lines: when a weapon row's properties span two lines,
    # the second line contains only a continuation word before mastery/weight/cost.
    joined_lines: list[str] = []
    raw_lines = section.split("\n")
    idx = 0
    while idx < len(raw_lines):
        line = raw_lines[idx]
        if (
            line.rstrip().endswith(",")
            and idx + 1 < len(raw_lines)
            and re.match(
                r"^\s*(?:Two-Handed|Heavy|Light|Loading|Finesse|Reach)\s*$",
                raw_lines[idx + 1],
            )
        ):
            joined_lines.append(line.rstrip() + " " + raw_lines[idx + 1].strip())
            idx += 2
        else:
            joined_lines.append(line)
            idx += 1
    section = "\n".join(joined_lines)

    weapons: list[dict[str, Any]] = []

    # Table row pattern:
    # "Name  1d8 Slashing  Properties  Mastery  weight  cost"
    row_re = re.compile(
        r"^([\w ,\-]+?)\s+"
        r"(\d+d\d+|\d) "
        r"(Bludgeoning|Piercing|Slashing)\s+"
        r"(.*?)\s+"
        r"(Cleave|Graze|Nick|Push|Sap|Slow|Topple|Vex)\s*"
        r"([^\n]+?)\s+"
        r"([\d,]+\s*(?:GP|SP|CP))",
        re.MULTILINE,
    )

    for cat_id, cat_header in _WEAPON_CATEGORY_HEADERS:
        # Find this category section
        cat_m = re.search(rf"\n{re.escape(cat_header)}\n(.*?)(?=\n(?:Simple|Martial)\s+(?:Melee|Ranged)|\nArmor\n|\Z)", section, re.DOTALL)
        if not cat_m:
            continue
        cat_text = cat_m.group(1)
        is_martial = "martial" in cat_id
        is_ranged = "ranged" in cat_id

        for m in row_re.finditer(cat_text):
            name = _clean(m.group(1))
            if not name or name.lower() in {"weapon", "name"}:
                continue

            damage_dice = m.group(2)
            damage_type = m.group(3).lower()
            props_raw = m.group(4).strip()
            mastery = m.group(5)
            weight_raw = m.group(6).strip()
            cost_raw = m.group(7).strip()

            # Parse properties list
            properties: list[str] = []
            if props_raw and props_raw != "—":
                for prop in re.split(r",\s*", props_raw):
                    prop = prop.strip()
                    if prop:
                        properties.append(prop)

            # Special property flags
            is_finesse = any("Finesse" in p for p in properties)
            is_light = any("Light" in p for p in properties)
            is_heavy = any("Heavy" in p for p in properties)
            is_two_handed = any("Two-Handed" in p for p in properties)
            is_reach = any("Reach" in p for p in properties)
            is_loading = any("Loading" in p for p in properties)

            # Thrown range
            thrown_range: dict[str, int] | None = None
            for p in properties:
                tr_m = re.search(r"Thrown\s*\(Range\s*(\d+)/(\d+)\)", p)
                if tr_m:
                    thrown_range = {"normal": int(tr_m.group(1)), "long": int(tr_m.group(2))}

            # Ammunition range
            ammo: dict[str, Any] | None = None
            for p in properties:
                am_m = re.search(r"Ammunition\s*\(Range\s*(\d+)/(\d+);\s*([^)]+)\)", p)
                if am_m:
                    ammo = {
                        "type": am_m.group(3).strip(),
                        "normal": int(am_m.group(1)),
                        "long": int(am_m.group(2)),
                    }

            # Versatile
            versatile_damage: str | None = None
            for p in properties:
                vd_m = re.search(r"Versatile\s*\((\d+d\d+)\)", p)
                if vd_m:
                    versatile_damage = vd_m.group(1)

            entry: dict[str, Any] = {
                "id": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
                "name": name,
                "source": SOURCE_ID,
                "category": cat_id,
                "is_martial": is_martial,
                "is_ranged": is_ranged,
                "damage_dice": damage_dice,
                "damage_type": damage_type,
                "properties": properties,
                "mastery": mastery,
                "weight_lb": weight_raw.replace("lb.", "").strip() or None,
                "cost": cost_raw,
                "is_finesse": is_finesse,
                "is_light": is_light,
                "is_heavy": is_heavy,
                "is_two_handed": is_two_handed,
                "is_reach": is_reach,
                "is_loading": is_loading,
            }
            if thrown_range:
                entry["thrown_range"] = thrown_range
            if ammo:
                entry["ammunition"] = ammo
            if versatile_damage:
                entry["versatile_damage"] = versatile_damage

            weapons.append(entry)

    return weapons


# ── 5. Armor ──────────────────────────────────────────────────────────────────

def parse_armor(raw: str) -> list[dict[str, Any]]:
    """Extract armor table from Equipment section."""
    section = _text_between(raw, r"\nEquipment\n", r"\nSpells\n|\nSpell Descriptions\n")
    section = _strip_page_headers(section)

    # Locate the armor table - it follows "Armor\n" and precedes "Tools\n"
    armor_section = _text_between(section, r"\nArmor\n", r"\nTools\n")

    armors: list[dict[str, Any]] = []

    # Row format (from raw text - one armor per line):
    # "Padded Armor 11 + Dex modifier — Disadvantage 8 lb. 5 GP"
    # "Chain Mail 16 Str 13 Disadvantage 55 lb. 75 GP"
    row_re = re.compile(
        r"^([\w ]+ Armor|Ring Mail|Splint Armor|Plate Armor|Chain Mail|Chain Shirt|Breastplate|Half Plate Armor|Hide Armor)\s+"
        r"(\d+(?:\s*\+\s*Dex modifier(?:\s*\(max \d+\))?)?)\s+"
        r"(—|Str \d+)\s+"
        r"(—|Disadvantage)\s+"
        r"(\d+(?:\s*lb\.)?)\s+"
        r"([\d,]+\s*GP)",
        re.MULTILINE,
    )

    category = "light"
    for line in armor_section.split("\n"):
        if re.search(r"Light Armor", line):
            category = "light"
        elif re.search(r"Medium Armor", line):
            category = "medium"
        elif re.search(r"Heavy Armor", line):
            category = "heavy"

        m = row_re.match(line)
        if not m:
            continue

        name = _clean(m.group(1))
        ac_formula = _clean(m.group(2))
        str_req_raw = m.group(3)
        stealth_raw = m.group(4)
        weight_raw = m.group(5)
        cost_raw = m.group(6)

        # Parse AC
        if "Dex" in ac_formula:
            base_m = re.match(r"(\d+)", ac_formula)
            base_ac = int(base_m.group(1)) if base_m else 10
            max_dex_m = re.search(r"max (\d+)", ac_formula)
            ac: dict[str, Any] = {"base": base_ac, "add_dex": True}
            if max_dex_m:
                ac["max_dex_bonus"] = int(max_dex_m.group(1))
        else:
            ac = {"base": int(ac_formula), "add_dex": False}

        str_req: int | None = None
        if str_req_raw != "—":
            sm = re.search(r"(\d+)", str_req_raw)
            if sm:
                str_req = int(sm.group(1))

        armors.append({
            "id": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "name": name,
            "source": SOURCE_ID,
            "category": category,
            "ac": ac,
            "strength_requirement": str_req,
            "stealth_disadvantage": stealth_raw == "Disadvantage",
            "weight_lb": weight_raw.replace("lb.", "").strip(),
            "cost": cost_raw,
        })

    # Shield
    armors.append({
        "id": "shield",
        "name": "Shield",
        "source": SOURCE_ID,
        "category": "shield",
        "ac": {"bonus": 2},
        "strength_requirement": None,
        "stealth_disadvantage": False,
        "weight_lb": "6",
        "cost": "10 GP",
    })

    return armors


# ── 6. Magic Items ─────────────────────────────────────────────────────────────

_RARITY_WORDS = r"Common|Uncommon|Rare|Very Rare|Legendary|Artifact"
_TYPE_WORDS = r"Armor|Potion|Ring|Rod|Scroll|Staff|Wand|Weapon|Wondrous Item|Adventuring Gear"


def parse_magic_items(raw: str) -> list[dict[str, Any]]:
    """Parse Magic Items A–Z section."""
    section = _text_between(raw, r"\nMagic Items A.Z\n", r"\nMonsters\n")
    section = _strip_page_headers(section)

    items: list[dict[str, Any]] = []

    # Each magic item block:
    #   Name (possibly multi-line, joined with space)\n
    #   Type [Subtype], Rarity [Requires Attunement]\n
    #     (type/rarity line may wrap to a second line)
    #   Description...\n\n

    _TYPE_RE = re.compile(
        r"^(Armor|Potion|Ring|Rod|Scroll|Staff|Wand|Weapon|Wondrous Item|Adventuring Gear)",
        re.IGNORECASE,
    )
    _RARITY_WORDS_PAT = r"(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact)"

    lines_list = section.split("\n")
    # Find block boundaries: a line that starts with a type word
    # The name is the line(s) immediately before it
    block_starts: list[int] = []  # indices of the type+rarity line
    for idx, line in enumerate(lines_list):
        if _TYPE_RE.match(line.strip()) and idx > 0:
            block_starts.append(idx)

    for j, type_line_idx in enumerate(block_starts):
        end_idx = block_starts[j + 1] - 1 if j + 1 < len(block_starts) else len(lines_list)

        # Name = line(s) before the type line (may be 1 or 2 lines for wrapped names)
        name_lines: list[str] = []
        k = type_line_idx - 1
        while k >= max(0, type_line_idx - 3):
            candidate = lines_list[k].strip()
            if not candidate or _TYPE_RE.match(candidate):
                break
            # Stop at description content (contains digits, periods mid-sentence, etc.)
            if re.search(r"[.!?]\s+[a-z]", candidate) or candidate[0].islower():
                break
            name_lines.insert(0, candidate)
            k -= 1
        if not name_lines:
            continue
        name = _clean(" ".join(name_lines))
        if not name or len(name) > 80:
            continue

        # Type/rarity line — may wrap
        type_rarity_raw = lines_list[type_line_idx].strip()
        # If the closing of a parenthesis or "Requires Attunement" is on the next line, join it
        if (
            type_line_idx + 1 < len(lines_list)
            and not _TYPE_RE.match(lines_list[type_line_idx + 1].strip())
            and lines_list[type_line_idx + 1].strip()
            and not re.search(_RARITY_WORDS_PAT, type_rarity_raw, re.IGNORECASE)
        ):
            type_rarity_raw += " " + lines_list[type_line_idx + 1].strip()

        type_m = _TYPE_RE.match(type_rarity_raw.strip())
        rarity_m = re.search(_RARITY_WORDS_PAT, type_rarity_raw, re.IGNORECASE)
        subtype_m = re.search(r"\(([^)]+)\)", type_rarity_raw)

        item_type = _clean(type_m.group(1)) if type_m else "Wondrous Item"
        rarity = rarity_m.group(0).lower().replace(" ", "_") if rarity_m else "unknown"
        subtype = subtype_m.group(1) if subtype_m else None
        requires_attunement = bool(re.search(r"Requires Attunement", type_rarity_raw, re.IGNORECASE))

        # Description is everything after the type/rarity line
        desc_start = type_line_idx + 1
        if (
            desc_start < len(lines_list)
            and not re.search(_RARITY_WORDS_PAT, lines_list[type_line_idx].strip(), re.IGNORECASE)
            and not re.search(_RARITY_WORDS_PAT, lines_list[type_line_idx + 1].strip() if type_line_idx + 1 < len(lines_list) else "", re.IGNORECASE)
        ):
            pass  # the type line already consumed the rarity via joining
        elif rarity != "unknown" and desc_start < end_idx:
            # Check if we consumed a wrapped second line
            if type_rarity_raw != lines_list[type_line_idx].strip():
                desc_start = type_line_idx + 2

        desc_lines = lines_list[desc_start:end_idx]
        description = _clean("\n".join(desc_lines))

        items.append({
            "id": re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            "name": name,
            "source": SOURCE_ID,
            "item_type": item_type,
            "subtype": subtype,
            "rarity": rarity,
            "requires_attunement": requires_attunement,
            "description": description,
        })

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        if item["id"] not in seen:
            seen.add(item["id"])
            unique.append(item)

    return unique


# ── 7. Classes ────────────────────────────────────────────────────────────────

_CLASS_NAMES = [
    "Barbarian", "Bard", "Cleric", "Druid", "Fighter",
    "Monk", "Paladin", "Ranger", "Rogue", "Sorcerer", "Warlock", "Wizard",
]


def parse_classes(raw: str) -> list[dict[str, Any]]:
    """Parse class entries from the Classes section."""
    section = _text_between(raw, r"\nClasses\n", r"\nCharacter Origins\n")
    section = _strip_page_headers(section)

    classes: list[dict[str, Any]] = []

    for class_name in _CLASS_NAMES:
        # Find "ClassName\nCore ClassName Traits"
        start_m = re.search(
            rf"(?:^|\n){re.escape(class_name)}\nCore {re.escape(class_name)} Traits\n",
            section,
            re.MULTILINE,
        )
        if not start_m:
            # Fallback: just find the class heading
            start_m = re.search(rf"(?:^|\n){re.escape(class_name)}\n", section, re.MULTILINE)
        if not start_m:
            continue

        # End at next class
        later_classes = _CLASS_NAMES[_CLASS_NAMES.index(class_name) + 1:]
        if later_classes:
            end_pattern = rf"(?:^|\n){re.escape(later_classes[0])}\n"
            end_m = re.search(end_pattern, section[start_m.start():], re.MULTILINE)
            end_pos = start_m.start() + end_m.start() if end_m else len(section)
        else:
            end_pos = len(section)

        block = section[start_m.start():end_pos]

        cls: dict[str, Any] = {
            "id": class_name.lower(),
            "name": class_name,
            "source": SOURCE_ID,
        }

        # Primary ability
        pa_m = re.search(r"Primary Ability\s+(.+)", block)
        if pa_m:
            cls["primary_ability"] = _clean(pa_m.group(1))

        # Hit die
        hd_m = re.search(r"Hit Point Die\s+D(\d+)", block, re.IGNORECASE)
        if hd_m:
            cls["hit_die"] = int(hd_m.group(1))

        # Saving throw proficiencies
        st_m = re.search(r"Saving Throw\s*Proficiencies?\s+(.+?)(?=\n\w|\Z)", block, re.DOTALL)
        if st_m:
            st_raw = _clean(st_m.group(1))
            cls["saving_throw_proficiencies"] = [s.strip() for s in re.split(r"\s+and\s+|,\s*", st_raw) if s.strip()]

        # Skill proficiencies
        sk_m = re.search(r"Skill Proficiencies\s+Choose\s+(\d+):\s+(.+?)(?=\n\w|\Z)", block, re.DOTALL)
        if sk_m:
            cls["skill_proficiency_count"] = int(sk_m.group(1))
            skills_raw = _clean(sk_m.group(2))
            cls["skill_proficiency_options"] = [s.strip(" .") for s in re.split(r",\s*|\s+or\s+", skills_raw) if s.strip(" .")]

        # Armor training
        at_m = re.search(r"Armor Training\s+(.+?)(?=\n\w|\Z)", block, re.DOTALL)
        if at_m:
            cls["armor_training"] = _clean(at_m.group(1))

        # Weapon proficiencies
        wp_m = re.search(r"Weapon Proficiencies?\s+(.+?)(?=\n\w|\Z)", block, re.DOTALL)
        if wp_m:
            cls["weapon_proficiencies"] = _clean(wp_m.group(1))

        # Subclass name
        sub_m = re.search(rf"{re.escape(class_name)} Subclass:\s*(.+)", block)
        if sub_m:
            cls["subclass_example"] = _clean(sub_m.group(1))

        # Spellcasting
        cls["has_spellcasting"] = bool(re.search(r"Spellcasting|Spell List|spell slot", block, re.IGNORECASE))

        # Level table: "1 +2 Features... " etc.
        level_re = re.compile(r"^(\d{1,2})\s+\+(\d)\s+(.+)", re.MULTILINE)
        levels: list[dict[str, Any]] = []
        for lm in level_re.finditer(block):
            lvl = int(lm.group(1))
            if lvl > 20:
                continue
            pb = int(lm.group(2))
            feat_raw = _clean(lm.group(3))
            # Strip trailing number columns (e.g., rage counts, spell slots)
            feat_raw = re.sub(r"\s+\d+.*$", "", feat_raw).strip()
            levels.append({"level": lvl, "proficiency_bonus": pb, "features": feat_raw})
        if levels:
            cls["levels"] = levels

        classes.append(cls)

    return classes


# ── 8. Species ────────────────────────────────────────────────────────────────

_SPECIES_NAMES = [
    "Dragonborn", "Dwarf", "Elf", "Gnome", "Goliath",
    "Halfling", "Human", "Orc", "Tiefling",
]


def parse_species(raw: str) -> list[dict[str, Any]]:
    """Parse species (races) from Character Origins section."""
    section = _text_between(raw, r"\nCharacter Origins\n", r"\nFeats\n")
    section = _strip_page_headers(section)

    species_list: list[dict[str, Any]] = []

    for sp_name in _SPECIES_NAMES:
        start_m = re.search(
            rf"(?:^|\n){re.escape(sp_name)}\nCreature Type:",
            section,
            re.MULTILINE,
        )
        if not start_m:
            continue

        later = _SPECIES_NAMES[_SPECIES_NAMES.index(sp_name) + 1:]
        if later:
            end_pattern = rf"(?:^|\n){re.escape(later[0])}\nCreature Type:"
            end_m = re.search(end_pattern, section[start_m.start():], re.MULTILINE)
            end_pos = start_m.start() + end_m.start() if end_m else len(section)
        else:
            end_pos = len(section)

        block = section[start_m.start():end_pos]

        sp: dict[str, Any] = {
            "id": sp_name.lower(),
            "name": sp_name,
            "source": SOURCE_ID,
        }

        ct_m = re.search(r"Creature Type:\s*([^\n]+)", block)
        if ct_m:
            sp["creature_type"] = _clean(ct_m.group(1))

        size_m = re.search(r"Size:\s*([^\n]+)", block)
        if size_m:
            sp["size"] = _clean(size_m.group(1))

        speed_m = re.search(r"Speed:\s*([^\n]+)", block)
        if speed_m:
            sp["speed_feet"] = _clean(speed_m.group(1))

        # Extract traits: "Trait Name.\n Full description."
        traits: list[dict[str, str]] = []
        trait_re = re.compile(
            r"([A-Z][A-Za-z ']+)\.\s*\n(.*?)(?=\n[A-Z][A-Za-z ']+\.\s*\n|\Z)",
            re.DOTALL,
        )
        for tm in trait_re.finditer(block):
            trait_name = _clean(tm.group(1))
            if len(trait_name.split()) > 6 or len(trait_name) < 3:
                continue
            trait_desc = _clean(tm.group(2))
            if trait_desc:
                traits.append({"name": trait_name, "description": trait_desc})
        sp["traits"] = traits

        species_list.append(sp)

    return species_list


# ── 9. Feats ──────────────────────────────────────────────────────────────────

_FEAT_CATEGORIES = {
    "Origin Feats": "origin",
    "General Feats": "general",
    "Fighting Style Feats": "fighting_style",
    "Epic Boon Feats": "epic_boon",
}


def parse_feats(raw: str) -> list[dict[str, Any]]:
    """Parse feat entries from Feats section."""
    section = _text_between(raw, r"\nFeats\n", r"\nEquipment\n")
    section = _strip_page_headers(section)

    feats: list[dict[str, Any]] = []

    # Individual feat format:
    #   FeatName\n
    #   (Origin|General|Fighting Style|Epic Boon) Feat [( Prerequisite: ... )]\n
    #     (the prerequisite may wrap onto the next line before the closing ")")
    #   Description...

    _CAT_BARE_RE = re.compile(
        r"^(Origin|General|Fighting Style|Epic Boon) Feat"
    )

    lines_list = section.split("\n")
    feat_entries: list[tuple[str, str, str | None, int, int]] = []
    # (feat_name, cat_id, prereq, desc_start_line_idx, name_line_idx)

    i = 0
    while i < len(lines_list):
        line = lines_list[i].strip()
        if _CAT_BARE_RE.match(line):
            # Consume possible wrapped prerequisite on next line
            cat_line = line
            consumed = 1  # lines consumed for this entry
            if ")" not in cat_line and i + 1 < len(lines_list):
                # Prerequisite wraps to next line
                cat_line = cat_line + " " + lines_list[i + 1].strip()
                consumed = 2

            cat_m = _CAT_BARE_RE.match(cat_line)
            cat_raw = cat_m.group(1) if cat_m else "General"
            cat_id = cat_raw.lower().replace(" ", "_")

            prereq_m = re.search(r"\(Prerequisite: ([^)]+)\)", cat_line)
            prereq = prereq_m.group(1).strip() if prereq_m else None

            # Name is the previous non-blank line
            name_idx = i - 1
            while name_idx >= 0 and not lines_list[name_idx].strip():
                name_idx -= 1
            if name_idx < 0:
                i += consumed
                continue
            feat_name = _clean(lines_list[name_idx])
            # Reject if name doesn't look like a title (ends with punctuation, or all lower)
            if (
                not feat_name
                or len(feat_name) < 2
                or feat_name.endswith("Feats")
                or feat_name[-1] in ".!?,;:"
                or feat_name[0].islower()
                or len(feat_name.split()) > 6
            ):
                i += consumed
                continue

            desc_start = i + consumed
            feat_entries.append((feat_name, cat_id, prereq, desc_start, name_idx))
        i += 1

    # Extract descriptions
    for j, (feat_name, cat_id, prereq, desc_start, name_idx) in enumerate(feat_entries):
        if j + 1 < len(feat_entries):
            desc_end = feat_entries[j + 1][4]  # next feat's name line
        else:
            desc_end = len(lines_list)

        desc_lines = lines_list[desc_start:desc_end]
        description = _clean("\n".join(desc_lines))

        feats.append({
            "id": re.sub(r"[^a-z0-9]+", "_", feat_name.lower()).strip("_"),
            "name": feat_name,
            "source": SOURCE_ID,
            "category": cat_id,
            "prerequisite": prereq,
            "description": description,
        })

    # Deduplicate
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for f in feats:
        if f["id"] not in seen:
            seen.add(f["id"])
            unique.append(f)

    return unique


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"Loading {SRD_TEXT} ...")
    raw = SRD_TEXT.read_text(encoding="utf-8")

    print("\nParsing sections:")

    print("  conditions ...")
    conditions = parse_conditions(raw)
    _write("conditions", conditions)

    print("  spells ...")
    spells = parse_spells(raw)
    _write("spells", spells)

    print("  monsters ...")
    monsters = parse_monsters(raw)
    _write("monsters", monsters)

    print("  weapons ...")
    weapons = parse_weapons(raw)
    _write("weapons", weapons)

    print("  armor ...")
    armor = parse_armor(raw)
    _write("armor", armor)

    print("  magic_items ...")
    magic_items = parse_magic_items(raw)
    _write("magic_items", magic_items)

    print("  classes ...")
    classes = parse_classes(raw)
    _write("classes", classes)

    print("  species ...")
    species = parse_species(raw)
    _write("species", species)

    print("  feats ...")
    feats = parse_feats(raw)
    _write("feats", feats)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
