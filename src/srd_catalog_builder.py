"""Build comprehensive SRD 5.2.1 catalogs from the local raw text source."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from srd_parser import parse_armor, parse_conditions, parse_monsters, parse_weapons

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "rules_data" / "sources" / "srd-5.2.1-raw.txt"
CATALOG_DIR = ROOT / "rules_data" / "catalogs"
SOURCE_ID = "srd-5.2.1"
SOURCE_VERSION = "5.2.1"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def _normalize_text(value: str) -> str:
    # Rejoin hard-wrapped hyphenations from pdftotext output.
    value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
    value = value.replace("\u00ad", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _clean_section_lines(section: str) -> list[str]:
    section = section.replace("\f", "\n")
    out: list[str] = []
    for raw_line in section.splitlines():
        line = raw_line.rstrip()
        if re.fullmatch(r"\s*System Reference Document 5\.2\.1\s*", line):
            continue
        if re.fullmatch(r"\s*\d+\s*", line):
            continue
        out.append(line)
    return out


def _section_between(raw: str, start_heading: str, end_heading: str) -> str:
    start = re.search(rf"(?m)^{re.escape(start_heading)}$", raw)
    if not start:
        return ""
    end = re.search(rf"(?m)^{re.escape(end_heading)}$", raw[start.end() :])
    if not end:
        return raw[start.end() :]
    return raw[start.end() : start.end() + end.start()]


def _next_heading_after(raw: str, heading: str, *, after: int) -> int:
    match = re.search(rf"(?m)^{re.escape(heading)}$", raw[after:])
    if not match:
        return len(raw)
    return after + match.start()


def _write_json(name: str, payload: Any) -> None:
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    path = CATALOG_DIR / f"{name}.{SOURCE_ID}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if isinstance(payload, list):
        count = len(payload)
    elif isinstance(payload, dict) and isinstance(payload.get("spells"), list):
        count = len(payload["spells"])
    else:
        count = 1
    print(f"  ✓ {path.name} ({count} entries)")


# ---- Spells -----------------------------------------------------------------

_SPELL_HEADER_RE = re.compile(
    r"^(?:Level\s+(\d+)\s+([A-Za-z]+)|([A-Za-z]+)\s+Cantrip)\s*\((.+)\)$"
)
_SPELL_NAME_RE = re.compile(r"^[A-Z][A-Za-z0-9'’,+/\- ]{1,80}$")
_FIELD_LABELS = ("Casting Time:", "Range:", "Components:", "Component:", "Duration:")
_DAMAGE_TYPES = [
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
]
_ABILITY_MAP = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
}


def _next_nonempty(lines: list[str], idx: int) -> int:
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    return idx


def _parse_spell_header(lines: list[str], idx: int) -> dict[str, Any] | None:
    start = _next_nonempty(lines, idx)
    if start >= len(lines):
        return None

    parts: list[str] = []
    cursor = start
    for _ in range(6):
        if cursor >= len(lines):
            break
        line = lines[cursor].strip()
        if not line:
            cursor = _next_nonempty(lines, cursor + 1)
            continue
        parts.append(line)
        header_text = " ".join(parts)
        header_match = _SPELL_HEADER_RE.match(header_text)
        if header_match:
            after = _next_nonempty(lines, cursor + 1)
            if after < len(lines) and lines[after].strip().startswith("Casting Time:"):
                return {
                    "text": header_text,
                    "match": header_match,
                    "after": after,
                }
        if line.startswith("Casting Time:"):
            break
        cursor += 1

    return None


def _looks_like_spell_start(lines: list[str], idx: int) -> bool:
    idx = _next_nonempty(lines, idx)
    if idx >= len(lines):
        return False

    name = lines[idx].strip()
    if name == "Spell Descriptions":
        return False
    if ":" in name or not _SPELL_NAME_RE.match(name):
        return False

    return _parse_spell_header(lines, idx + 1) is not None


def _consume_field(lines: list[str], idx: int, label: str) -> tuple[str, int]:
    if idx >= len(lines) or not lines[idx].strip().startswith(label):
        return "", idx

    values = [lines[idx].strip()[len(label) :].strip()]
    idx += 1

    while idx < len(lines):
        candidate = lines[idx].strip()
        if not candidate:
            idx += 1
            continue
        if any(candidate.startswith(prefix) for prefix in _FIELD_LABELS):
            break
        if _looks_like_spell_start(lines, idx):
            break
        values.append(candidate)
        idx += 1

    return _normalize_text(" ".join(v for v in values if v)), idx


def _parse_range_feet(range_text: str) -> int:
    lowered = range_text.lower()
    if "self" in lowered:
        return 0
    if "touch" in lowered:
        return 5

    feet_match = re.search(r"(\d+)\s*(?:foot|feet|ft\.)", lowered)
    if feet_match:
        return int(feet_match.group(1))

    mile_match = re.search(r"(\d+)\s*mile", lowered)
    if mile_match:
        return int(mile_match.group(1)) * 5280

    return 0


def _infer_resolution_mode(description: str) -> tuple[str, str | None]:
    lowered = description.lower()

    save_match = re.search(
        r"\b(strength|dexterity|constitution|intelligence|wisdom|charisma)\s+saving throw\b",
        lowered,
    )
    save_ability = _ABILITY_MAP.get(save_match.group(1)) if save_match else None

    has_attack = bool(
        re.search(r"\b(?:melee|ranged)?\s*spell attack\b", lowered)
        or re.search(r"\bmake\s+(?:a\s+)?(?:melee|ranged)\s+attack\b", lowered)
    )

    if has_attack:
        return "attack", save_ability
    if save_ability:
        return "save", save_ability
    return "effect", save_ability


def _extract_damage(description: str) -> tuple[str | None, str]:
    dice_match = re.search(r"(\d+d\d+(?:\s*[+\-]\s*\d+)?)\s+(?:[A-Za-z]+\s+)?damage", description, re.IGNORECASE)
    damage = _normalize_text(dice_match.group(1)) if dice_match else None

    dtype_match = re.search(
        r"\b(" + "|".join(dt.capitalize() for dt in _DAMAGE_TYPES) + r")\s+damage\b",
        description,
    )
    damage_type = dtype_match.group(1).lower() if dtype_match else "untyped"
    return damage, damage_type


def _extract_condition(description: str) -> tuple[str | None, int | None]:
    cond_match = re.search(r"\bhave the\s+([A-Za-z]+)\s+condition\b", description, re.IGNORECASE)
    if not cond_match:
        return None, None

    condition = cond_match.group(1).lower()

    # Best-effort duration extraction for explicit round/minute/hour statements.
    dur_match = re.search(
        rf"\b{re.escape(cond_match.group(1))}\s+condition\s+for\s+(\d+)\s+(round|minute|hour)s?\b",
        description,
        re.IGNORECASE,
    )
    if not dur_match:
        return condition, None

    amount = int(dur_match.group(1))
    unit = dur_match.group(2).lower()
    if unit == "round":
        return condition, amount
    if unit == "minute":
        return condition, amount * 10
    if unit == "hour":
        return condition, amount * 600
    return condition, None


def parse_spells(raw: str) -> list[dict[str, Any]]:
    section = _section_between(raw, "Spell Descriptions", "Rules Glossary")
    lines = _clean_section_lines(section)

    spells: list[dict[str, Any]] = []
    id_counts: dict[str, int] = {}

    idx = 0
    while idx < len(lines):
        idx = _next_nonempty(lines, idx)
        if idx >= len(lines):
            break

        spell_name = lines[idx].strip()
        if spell_name == "Spell Descriptions" or ":" in spell_name or not _SPELL_NAME_RE.match(spell_name):
            idx += 1
            continue

        header = _parse_spell_header(lines, idx + 1)
        if not header:
            idx += 1
            continue

        header_match = header["match"]
        header_text = header["text"]
        cursor = header["after"]

        casting_time, cursor = _consume_field(lines, cursor, "Casting Time:")
        range_text, cursor = _consume_field(lines, cursor, "Range:")
        if cursor < len(lines) and lines[cursor].strip().startswith("Components:"):
            components_text, cursor = _consume_field(lines, cursor, "Components:")
        elif cursor < len(lines) and lines[cursor].strip().startswith("Component:"):
            components_text, cursor = _consume_field(lines, cursor, "Component:")
        else:
            components_text = ""

        duration = ""
        if cursor < len(lines) and lines[cursor].strip().startswith("Duration:"):
            duration = _normalize_text(lines[cursor].strip()[len("Duration:") :].strip())
            cursor += 1

        body_lines: list[str] = []
        while cursor < len(lines) and not _looks_like_spell_start(lines, cursor):
            line = lines[cursor].strip()
            if line:
                body_lines.append(line)
            cursor += 1

        description = _normalize_text(" ".join(body_lines))

        level = 0
        school = ""
        classes_raw = ""
        if header_match.group(1) and header_match.group(2):
            level = int(header_match.group(1))
            school = header_match.group(2).lower()
            classes_raw = header_match.group(4)
        else:
            level = 0
            school = (header_match.group(3) or "").lower()
            classes_raw = header_match.group(4)
        classes = [part.strip() for part in classes_raw.split(",") if part.strip()]

        spell_id = f"spell.{_slugify(spell_name)}"
        if spell_id in id_counts:
            id_counts[spell_id] += 1
            spell_id = f"{spell_id}_{id_counts[spell_id]}"
        else:
            id_counts[spell_id] = 1

        resolution_mode, save_ability = _infer_resolution_mode(description)
        damage, damage_type = _extract_damage(description)
        condition_name, condition_rounds = _extract_condition(description)

        spell_record: dict[str, Any] = {
            "id": spell_id,
            "name": spell_name,
            "source_id": SOURCE_ID,
            "level": level,
            "school": school,
            "resolution_mode": resolution_mode,
            "damage_type": damage_type,
            "half_damage_on_save": bool("half as much" in description.lower() and resolution_mode == "save"),
            "is_melee": bool("melee spell attack" in description.lower() or range_text.lower() == "touch"),
            "range_feet": _parse_range_feet(range_text),
            "notes": _normalize_text(
                " ".join(
                    [
                        f"Header: {header_text}",
                        f"Casting Time: {casting_time}",
                        f"Range: {range_text}",
                        f"Components: {components_text or 'None'}",
                        f"Duration: {duration}",
                        f"Classes: {', '.join(classes)}",
                        f"Text: {description}",
                    ]
                )
            ),
        }

        if damage:
            spell_record["damage"] = damage
        if save_ability and resolution_mode == "save":
            spell_record["save_ability"] = save_ability
        if condition_name and resolution_mode == "save":
            spell_record["condition_on_failed_save"] = condition_name
        if condition_rounds and resolution_mode == "save":
            spell_record["condition_duration_rounds"] = condition_rounds

        spells.append(spell_record)
        idx = cursor

    spells.sort(key=lambda item: (item["level"], item["name"]))
    return spells


# ---- Magic Items -------------------------------------------------------------

_RARITY_WORDS = ["Common", "Uncommon", "Rare", "Very Rare", "Legendary", "Artifact", "Rarity Varies"]
_ITEM_TYPE_PREFIXES = [
    "Armor",
    "Potion",
    "Ring",
    "Rod",
    "Scroll",
    "Staff",
    "Wand",
    "Weapon",
    "Wondrous Item",
    "Adventuring Gear",
]


def _starts_with_item_type(value: str) -> bool:
    return any(value.startswith(prefix) for prefix in _ITEM_TYPE_PREFIXES)


def _looks_like_item_name_line(value: str) -> bool:
    value = value.strip()
    if not value:
        return False
    if value in {"Magic Items A–Z", "Magic items are presented in alphabetical order."}:
        return False
    if ":" in value or value.endswith("."):
        return False
    if re.search(r"\b(?:Common|Uncommon|Rare|Very Rare|Legendary|Artifact)\b", value) and re.search(r"\d", value):
        return False
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9'’,+\-()/ ]{0,120}$", value))


def _looks_like_item_name_continuation(value: str) -> bool:
    value = value.strip()
    if not value or ":" in value or value.endswith("."):
        return False
    if len(value) > 50:
        return False
    if re.search(r"\d\s+\w+\s+\d\s+\w+", value):
        return False
    # Multi-line item names in SRD are connective tails like "and Location".
    return bool(re.match(r"^[a-z(].*$", value))


def _infer_item_rarity(meta: str) -> tuple[str, list[str]]:
    matched = [word for word in _RARITY_WORDS if word in meta]
    if not matched:
        return "unknown", []
    if len(matched) == 1 and matched[0] != "Rarity Varies":
        return _slugify(matched[0]), [matched[0]]
    return "varies", matched


def parse_magic_items(raw: str) -> list[dict[str, Any]]:
    start_heading = "Magic Items A\u2013Z"
    end_heading = "Monsters A\u2013Z"
    section = _section_between(raw, start_heading, end_heading)
    lines = _clean_section_lines(section)

    entries: list[dict[str, Any]] = []
    found: list[dict[str, Any]] = []

    idx = 0
    while idx < len(lines):
        if not _looks_like_item_name_line(lines[idx]):
            idx += 1
            continue

        name_parts = [lines[idx].strip()]
        cursor = idx + 1
        while cursor < len(lines) and not _starts_with_item_type(lines[cursor].strip()):
            if not _looks_like_item_name_continuation(lines[cursor]):
                break
            name_parts.append(lines[cursor].strip())
            cursor += 1
            if len(name_parts) >= 3:
                break

        if cursor >= len(lines) or not _starts_with_item_type(lines[cursor].strip()):
            idx += 1
            continue

        meta_parts = [lines[cursor].strip()]
        meta_end = cursor
        while (
            meta_end + 1 < len(lines)
            and not any(word in " ".join(meta_parts) for word in _RARITY_WORDS)
            and len(meta_parts) < 4
        ):
            nxt = lines[meta_end + 1].strip()
            if not nxt or _starts_with_item_type(nxt):
                break
            meta_parts.append(nxt)
            meta_end += 1

        meta_text = " ".join(meta_parts)
        if not any(word in meta_text for word in _RARITY_WORDS):
            idx += 1
            continue

        found.append(
            {
                "name": _normalize_text(" ".join(name_parts)),
                "meta": _normalize_text(meta_text),
                "start": idx,
                "meta_end": meta_end,
            }
        )
        idx = meta_end + 1

    for i, item in enumerate(found):
        desc_start = item["meta_end"] + 1
        desc_end = found[i + 1]["start"] if i + 1 < len(found) else len(lines)
        description_lines = [line.strip() for line in lines[desc_start:desc_end] if line.strip()]
        description = _normalize_text(" ".join(description_lines))

        meta = item["meta"]
        item_type = _normalize_text(meta.split(",", 1)[0])
        rarity, rarity_list = _infer_item_rarity(meta)

        entry: dict[str, Any] = {
            "id": _slugify(item["name"]),
            "name": item["name"],
            "source": SOURCE_ID,
            "item_type": item_type,
            "rarity": rarity,
            "rarity_text": meta,
            "requires_attunement": "requires attunement" in meta.lower(),
            "description": description,
        }
        if rarity_list:
            entry["rarity_values"] = rarity_list

        entries.append(entry)

    # Deduplicate while preserving first occurrence.
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        if entry["id"] in seen:
            continue
        seen.add(entry["id"])
        deduped.append(entry)

    return deduped


# ---- Classes -----------------------------------------------------------------

_CLASS_NAMES = [
    "Barbarian",
    "Bard",
    "Cleric",
    "Druid",
    "Fighter",
    "Monk",
    "Paladin",
    "Ranger",
    "Rogue",
    "Sorcerer",
    "Warlock",
    "Wizard",
]

_CLASS_CORE_LABELS = [
    "Primary Ability",
    "Hit Point Die",
    "Saving Throw Proficiencies",
    "Skill Proficiencies",
    "Weapon Proficiencies",
    "Tool Proficiencies",
    "Armor Training",
    "Starting Equipment",
]


def _extract_class_core_traits(block: str, class_name: str) -> dict[str, str]:
    core_match = re.search(
        rf"Core {re.escape(class_name)} Traits\n(.*?)(?:\nBecoming [^\n]*{re.escape(class_name)}|\n{re.escape(class_name)} Class Features)",
        block,
        re.DOTALL,
    )
    if not core_match:
        return {}

    compact = _normalize_text(core_match.group(1).replace("\n", " "))
    out: dict[str, str] = {}

    for idx, label in enumerate(_CLASS_CORE_LABELS):
        next_labels = _CLASS_CORE_LABELS[idx + 1 :]
        if next_labels:
            boundary = "|".join(re.escape(item) for item in next_labels)
            pattern = rf"{re.escape(label)}\s+(.*?)(?=\s+(?:{boundary})\s+|$)"
        else:
            pattern = rf"{re.escape(label)}\s+(.*)$"

        match = re.search(pattern, compact)
        if match:
            out[label] = _normalize_text(match.group(1))

    return out


def _extract_level_features(block: str) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    matches = list(re.finditer(r"(?m)^Level\s+(\d+):\s+([^\n]+)$", block))

    for idx, match in enumerate(matches):
        level = int(match.group(1))
        feature_name = _normalize_text(match.group(2))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(block)
        description = _normalize_text(block[start:end])
        features.append(
            {
                "level": level,
                "name": feature_name,
                "description": description,
            }
        )

    return features


def _extract_subclass_name(block: str, class_name: str) -> str | None:
    match = re.search(rf"{re.escape(class_name)} Subclass:\s*([^\n]+)", block)
    if not match:
        return None

    base = _normalize_text(match.group(1))

    # Some subclass names wrap to the next line (for example, "Warrior of the Elements").
    tail_start = block.find("\n", match.end())
    if tail_start == -1:
        return base
    tail_line_match = re.search(r"\n([^\n]+)", block[tail_start:])
    if not tail_line_match:
        return base
    tail_line = tail_line_match.group(1).strip()

    if (
        tail_line
        and not tail_line.startswith("Level ")
        and ":" not in tail_line
        and len(tail_line.split()) <= 4
        and base.split()[-1].lower() in {"the", "draconic", "warrior", "college", "circle", "life", "fiend"}
    ):
        return _normalize_text(f"{base} {tail_line}")

    return base


def parse_classes(raw: str) -> list[dict[str, Any]]:
    section = _section_between(raw, "Classes", "Character Origins")
    lines = _clean_section_lines(section)
    text = "\n".join(lines)

    positions: list[tuple[int, str]] = []
    for class_name in _CLASS_NAMES:
        match = re.search(rf"(?m)^{re.escape(class_name)}$", text)
        if match:
            positions.append((match.start(), class_name))
    positions.sort()

    classes: list[dict[str, Any]] = []
    for idx, (start, class_name) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
        block = text[start:end]

        core_traits = _extract_class_core_traits(block, class_name)
        level_features = _extract_level_features(block)

        record: dict[str, Any] = {
            "id": _slugify(class_name),
            "name": class_name,
            "source": SOURCE_ID,
            "core_traits": core_traits,
            "features": level_features,
            "description": _normalize_text(block),
        }

        primary = core_traits.get("Primary Ability")
        if primary:
            record["primary_ability"] = primary

        hit_die = core_traits.get("Hit Point Die")
        if hit_die:
            die_match = re.search(r"D(\d+)", hit_die, re.IGNORECASE)
            if die_match:
                record["hit_die"] = int(die_match.group(1))

        saves = core_traits.get("Saving Throw Proficiencies")
        if saves:
            save_tokens = [token.strip() for token in re.split(r",|\band\b", saves) if token.strip()]
            record["saving_throw_proficiencies"] = save_tokens

        subclass_name = _extract_subclass_name(block, class_name)
        if subclass_name:
            record["subclass"] = subclass_name

        classes.append(record)

    return classes


# ---- Species -----------------------------------------------------------------

_SPECIES_NAMES = [
    "Dragonborn",
    "Dwarf",
    "Elf",
    "Gnome",
    "Goliath",
    "Halfling",
    "Human",
    "Orc",
    "Tiefling",
]

_SPECIES_TRAITS = {
    "Dragonborn": ["Draconic Ancestry", "Breath Weapon", "Damage Resistance", "Darkvision", "Draconic Flight"],
    "Dwarf": ["Darkvision", "Dwarven Resilience", "Dwarven Toughness", "Stonecunning"],
    "Elf": ["Darkvision", "Elven Lineage", "Fey Ancestry", "Keen Senses", "Trance"],
    "Gnome": ["Darkvision", "Gnomish Cunning", "Gnomish Lineage"],
    "Goliath": ["Giant Ancestry", "Large Form", "Powerful Build"],
    "Halfling": ["Brave", "Halfling Nimbleness", "Luck", "Naturally Stealthy"],
    "Human": ["Resourceful", "Skillful", "Versatile"],
    "Orc": ["Adrenaline Rush", "Darkvision", "Relentless Endurance"],
    "Tiefling": ["Darkvision", "Fiendish Legacy", "Otherworldly Presence"],
}


def _extract_species_field(block: str, label: str, stop_labels: list[str]) -> str | None:
    stopper = "|".join(re.escape(item) for item in stop_labels)
    match = re.search(rf"{re.escape(label)}:\s*(.*?)(?=\n(?:{stopper})|\Z)", block, re.DOTALL)
    if not match:
        return None
    return _normalize_text(match.group(1))


def _extract_named_traits(block: str, names: list[str]) -> list[dict[str, str]]:
    positions: list[tuple[int, int, str]] = []
    for name in names:
        match = re.search(rf"{re.escape(name)}\.\s*", block)
        if match:
            positions.append((match.start(), match.end(), name))
    positions.sort()

    traits: list[dict[str, str]] = []
    for idx, (start, end, name) in enumerate(positions):
        finish = positions[idx + 1][0] if idx + 1 < len(positions) else len(block)
        desc = _normalize_text(block[end:finish])
        traits.append({"name": name, "description": desc})

    return traits


def parse_species(raw: str) -> list[dict[str, Any]]:
    section = _section_between(raw, "Character Origins", "Feats")
    lines = _clean_section_lines(section)
    text = "\n".join(lines)

    positions: list[tuple[int, str]] = []
    for species_name in _SPECIES_NAMES:
        match = re.search(rf"(?m)^{re.escape(species_name)}$", text)
        if match:
            positions.append((match.start(), species_name))
    positions.sort()

    records: list[dict[str, Any]] = []
    for idx, (start, species_name) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
        block = text[start:end]

        creature_type = _extract_species_field(block, "Creature Type", ["Size:", "Speed:", "As a "])
        size = _extract_species_field(block, "Size", ["Speed:", "As a "])
        speed = _extract_species_field(block, "Speed", ["As a "])
        speed_match = re.search(r"(\d+)\s*feet", speed or "", re.IGNORECASE)

        traits = _extract_named_traits(block, _SPECIES_TRAITS[species_name])

        records.append(
            {
                "id": _slugify(species_name),
                "name": species_name,
                "source": SOURCE_ID,
                "creature_type": creature_type,
                "size": size,
                "speed": speed,
                "speed_feet": int(speed_match.group(1)) if speed_match else None,
                "traits": traits,
                "description": _normalize_text(block),
            }
        )

    return records


# ---- Feats -------------------------------------------------------------------

_FEAT_CATEGORIES = {
    "Origin Feats": "origin",
    "General Feats": "general",
    "Fighting Style Feats": "fighting_style",
    "Epic Boon Feats": "epic_boon",
}


def _is_feat_meta_line(value: str) -> bool:
    return bool(re.search(r"(?:Origin|General|Fighting Style|Epic Boon) Feat", value))


def parse_feats(raw: str) -> list[dict[str, Any]]:
    start_match = re.search(r"(?m)^Feats$", raw)
    if not start_match:
        return []
    start = start_match.start()
    end = _next_heading_after(raw, "Equipment", after=start)
    section = raw[start:end]

    lines = _clean_section_lines(section)

    feats: list[dict[str, Any]] = []
    current_category = ""

    idx = 0
    while idx < len(lines):
        idx = _next_nonempty(lines, idx)
        if idx >= len(lines):
            break

        line = lines[idx].strip()
        if line in _FEAT_CATEGORIES:
            current_category = _FEAT_CATEGORIES[line]
            idx += 1
            continue

        if line in {"Feats", "Feat Descriptions", "Parts of a Feat"}:
            idx += 1
            continue

        if not current_category:
            idx += 1
            continue

        if ":" in line or not re.match(r"^[A-Z][A-Za-z0-9'’,+\-()/ ]{1,100}$", line):
            idx += 1
            continue

        meta_idx = _next_nonempty(lines, idx + 1)
        if meta_idx >= len(lines):
            break

        meta_parts = [lines[meta_idx].strip()]
        cursor = meta_idx
        while (
            cursor + 1 < len(lines)
            and "(" in " ".join(meta_parts)
            and ")" not in " ".join(meta_parts)
        ):
            nxt = lines[cursor + 1].strip()
            if not nxt:
                cursor += 1
                continue
            meta_parts.append(nxt)
            cursor += 1

        meta_line = _normalize_text(" ".join(meta_parts))
        if not _is_feat_meta_line(meta_line):
            idx += 1
            continue

        cursor += 1
        body_lines: list[str] = []
        while cursor < len(lines):
            candidate = lines[cursor].strip()
            if candidate in _FEAT_CATEGORIES:
                break
            if re.match(r"^[A-Z][A-Za-z0-9'’,+\-()/ ]{1,100}$", candidate) and ":" not in candidate:
                next_line_idx = _next_nonempty(lines, cursor + 1)
                if next_line_idx < len(lines) and _is_feat_meta_line(lines[next_line_idx].strip()):
                    break
            if candidate:
                body_lines.append(candidate)
            cursor += 1

        prerequisite: str | None = None
        prereq_match = re.search(r"Prerequisite:\s*([^\)]+)", meta_line)
        if prereq_match:
            prerequisite = _normalize_text(prereq_match.group(1))

        feats.append(
            {
                "id": _slugify(line),
                "name": line,
                "source": SOURCE_ID,
                "category": current_category,
                "header": _normalize_text(meta_line),
                "prerequisite": prerequisite,
                "description": _normalize_text(" ".join(body_lines)),
            }
        )

        idx = cursor

    return feats


def main() -> int:
    raw = RAW_PATH.read_text(encoding="utf-8")

    print(f"Loading {RAW_PATH} ...")
    print("\nRebuilding catalogs:")

    conditions = parse_conditions(raw)
    _write_json("conditions", conditions)

    spells = parse_spells(raw)
    spell_payload = {
        "catalog_type": "spells",
        "source_id": SOURCE_ID,
        "version": SOURCE_VERSION,
        "spells": spells,
    }
    _write_json("spells", spell_payload)

    monsters = parse_monsters(raw)
    _write_json("monsters", monsters)

    weapons = parse_weapons(raw)
    _write_json("weapons", weapons)

    armor = parse_armor(raw)
    _write_json("armor", armor)

    magic_items = parse_magic_items(raw)
    _write_json("magic_items", magic_items)

    classes = parse_classes(raw)
    _write_json("classes", classes)

    species = parse_species(raw)
    _write_json("species", species)

    feats = parse_feats(raw)
    _write_json("feats", feats)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
