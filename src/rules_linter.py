from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from schema_loader import EncounterSchemaError, validate_encounter_data


ALLOWED_RESOLUTION_MODES = {"attack", "save", "effect"}


@dataclass(slots=True)
class LintIssue:
    level: Literal["ERROR", "WARNING"]
    code: str
    message: str
    path: str | None = None

    def render(self) -> str:
        prefix = f"[{self.level}] {self.code}"
        if self.path:
            return f"{prefix} :: {self.path} :: {self.message}"
        return f"{prefix} :: {self.message}"


@dataclass(slots=True)
class CanonicalSpell:
    id: str
    source_id: str
    resolution_mode: str | None
    attack_bonus: int | None
    save_ability: str | None
    save_dc: int | None
    origin_path: Path


def _norm_path(path: Path) -> str:
    return str(path.resolve())


def _read_json_file(path: Path, issues: list[LintIssue], *, code_prefix: str) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        issues.append(
            LintIssue(
                level="ERROR",
                code=f"{code_prefix}_read_failed",
                message=str(exc),
                path=_norm_path(path),
            )
        )
        return None
    except json.JSONDecodeError as exc:
        issues.append(
            LintIssue(
                level="ERROR",
                code=f"{code_prefix}_invalid_json",
                message=f"{exc.msg} at line {exc.lineno}, column {exc.colno}",
                path=_norm_path(path),
            )
        )
        return None

    if not isinstance(raw, dict):
        issues.append(
            LintIssue(
                level="ERROR",
                code=f"{code_prefix}_root_not_object",
                message="Top-level JSON value must be an object.",
                path=_norm_path(path),
            )
        )
        return None

    return raw


def _as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _iter_json_files(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return sorted(path for path in directory.rglob("*.json") if path.is_file())


def lint_rules_data(rules_data_dir: Path) -> tuple[list[LintIssue], dict[str, CanonicalSpell]]:
    issues: list[LintIssue] = []
    spell_index: dict[str, CanonicalSpell] = {}

    rules_data_dir = rules_data_dir.resolve()
    registry_path = rules_data_dir / "registry.json"

    if not registry_path.exists():
        issues.append(
            LintIssue(
                level="ERROR",
                code="missing_registry",
                message="Missing rules_data/registry.json",
                path=_norm_path(registry_path),
            )
        )
        return issues, spell_index

    registry = _read_json_file(registry_path, issues, code_prefix="registry")
    if registry is None:
        return issues, spell_index

    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_sources_invalid",
                message="'sources' must be a list.",
                path=_norm_path(registry_path),
            )
        )
        raw_sources = []

    source_ids_seen: set[str] = set()
    source_id_to_path: dict[str, Path] = {}

    for index, source_entry in enumerate(raw_sources):
        entry_path = f"{_norm_path(registry_path)}::sources[{index}]"

        if not isinstance(source_entry, dict):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_entry_invalid",
                    message="Source entry must be an object.",
                    path=entry_path,
                )
            )
            continue

        source_id = str(source_entry.get("id", "")).strip()
        source_rel_path = str(source_entry.get("path", "")).strip()

        if not source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_missing_id",
                    message="Source entry is missing a non-empty 'id'.",
                    path=entry_path,
                )
            )
            continue

        if source_id in source_ids_seen:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="duplicate_source_id",
                    message=f"Duplicate source id: {source_id}",
                    path=entry_path,
                )
            )
            continue

        source_ids_seen.add(source_id)

        if not source_rel_path:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_missing_path",
                    message=f"Source '{source_id}' is missing a non-empty 'path'.",
                    path=entry_path,
                )
            )
            continue

        source_path = (rules_data_dir / source_rel_path).resolve()
        source_id_to_path[source_id] = source_path

        if not source_path.exists():
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=f"Source '{source_id}' points to a missing file.",
                    path=_norm_path(source_path),
                )
            )
            continue

        source_payload = _read_json_file(source_path, issues, code_prefix="source")
        if source_payload is None:
            continue

        payload_source_id = str(source_payload.get("source_id", "")).strip()
        if payload_source_id and payload_source_id != source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=(
                        f"Source file source_id mismatch. "
                        f"Registry says '{source_id}', file says '{payload_source_id}'."
                    ),
                    path=_norm_path(source_path),
                )
            )

    raw_catalogs = registry.get("catalogs")
    if raw_catalogs is None:
        raw_catalogs = {}
    if not isinstance(raw_catalogs, dict):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_catalogs_invalid",
                message="'catalogs' must be an object.",
                path=_norm_path(registry_path),
            )
        )
        raw_catalogs = {}

    raw_spell_catalogs = raw_catalogs.get("spells", [])
    if not isinstance(raw_spell_catalogs, list):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_spell_catalogs_invalid",
                message="'catalogs.spells' must be a list.",
                path=_norm_path(registry_path),
            )
        )
        raw_spell_catalogs = []

    referenced_catalog_paths: set[Path] = set()
    duplicate_rule_id_locations: defaultdict[str, list[str]] = defaultdict(list)

    for index, catalog_entry in enumerate(raw_spell_catalogs):
        entry_path = f"{_norm_path(registry_path)}::catalogs.spells[{index}]"

        if not isinstance(catalog_entry, dict):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_entry_invalid",
                    message="Catalog entry must be an object.",
                    path=entry_path,
                )
            )
            continue

        source_id = str(catalog_entry.get("source_id", "")).strip()
        catalog_rel_path = str(catalog_entry.get("path", "")).strip()

        if not source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_missing_source_id",
                    message="Spell catalog entry is missing a non-empty 'source_id'.",
                    path=entry_path,
                )
            )
            continue

        if source_id not in source_id_to_path:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=f"Spell catalog references unknown source_id '{source_id}'.",
                    path=entry_path,
                )
            )

        if not catalog_rel_path:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_missing_path",
                    message="Spell catalog entry is missing a non-empty 'path'.",
                    path=entry_path,
                )
            )
            continue

        catalog_path = (rules_data_dir / catalog_rel_path).resolve()
        referenced_catalog_paths.add(catalog_path)

        if not catalog_path.exists():
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="missing_catalog_file",
                    message="Referenced spell catalog file does not exist.",
                    path=_norm_path(catalog_path),
                )
            )
            continue

        catalog_payload = _read_json_file(catalog_path, issues, code_prefix="catalog")
        if catalog_payload is None:
            continue

        catalog_type = str(catalog_payload.get("catalog_type", "")).strip()
        if catalog_type != "spells":
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_type_invalid",
                    message=f"Expected catalog_type='spells', got {catalog_type!r}.",
                    path=_norm_path(catalog_path),
                )
            )

        payload_source_id = str(catalog_payload.get("source_id", "")).strip()
        if payload_source_id != source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=(
                        f"Catalog source_id mismatch. "
                        f"Registry says '{source_id}', file says '{payload_source_id}'."
                    ),
                    path=_norm_path(catalog_path),
                )
            )

        raw_spells = catalog_payload.get("spells", [])
        if not isinstance(raw_spells, list):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="catalog_spells_invalid",
                    message="'spells' must be a list.",
                    path=_norm_path(catalog_path),
                )
            )
            continue

        for spell_index_in_file, raw_spell in enumerate(raw_spells):
            spell_loc = f"{_norm_path(catalog_path)}::spells[{spell_index_in_file}]"

            if not isinstance(raw_spell, dict):
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_record_invalid",
                        message="Spell entry must be an object.",
                        path=spell_loc,
                    )
                )
                continue

            spell_id = str(raw_spell.get("id", "")).strip()
            if not spell_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_missing_id",
                        message="Spell entry is missing a non-empty 'id'.",
                        path=spell_loc,
                    )
                )
                continue

            duplicate_rule_id_locations[spell_id].append(spell_loc)

            spell_source_id = str(raw_spell.get("source_id", "")).strip()
            if not spell_source_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_missing_source_id",
                        message=f"Spell '{spell_id}' is missing 'source_id'.",
                        path=spell_loc,
                    )
                )
            elif spell_source_id != source_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="bad_source_reference",
                        message=(
                            f"Spell '{spell_id}' source_id mismatch. "
                            f"Catalog uses '{source_id}', spell uses '{spell_source_id}'."
                        ),
                        path=spell_loc,
                    )
                )

            resolution_mode = str(raw_spell.get("resolution_mode", "")).strip() or None
            if resolution_mode not in ALLOWED_RESOLUTION_MODES:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_resolution_mode_invalid",
                        message=(
                            f"Spell '{spell_id}' has invalid resolution_mode {resolution_mode!r}. "
                            f"Allowed: {sorted(ALLOWED_RESOLUTION_MODES)}"
                        ),
                        path=spell_loc,
                    )
                )

            attack_bonus = _as_int_or_none(raw_spell.get("attack_bonus"))
            save_ability = str(raw_spell.get("save_ability", "")).strip() or None
            save_dc = _as_int_or_none(raw_spell.get("save_dc"))

            if resolution_mode == "save" and not save_ability:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="spell_missing_save_ability",
                        message=f"Save-based spell '{spell_id}' is missing 'save_ability'.",
                        path=spell_loc,
                    )
                )

            if resolution_mode == "attack" and attack_bonus is None:
                issues.append(
                    LintIssue(
                        level="WARNING",
                        code="spell_requires_attack_bonus_override",
                        message=(
                            f"Attack-roll spell '{spell_id}' has no canonical attack_bonus. "
                            f"Every encounter action using it must provide attack_bonus_override."
                        ),
                        path=spell_loc,
                    )
                )

            if resolution_mode == "save" and save_dc is None:
                issues.append(
                    LintIssue(
                        level="WARNING",
                        code="spell_requires_save_dc_override",
                        message=(
                            f"Save-based spell '{spell_id}' has no canonical save_dc. "
                            f"Every encounter action using it must provide save_dc_override."
                        ),
                        path=spell_loc,
                    )
                )

            if spell_id not in spell_index:
                spell_index[spell_id] = CanonicalSpell(
                    id=spell_id,
                    source_id=spell_source_id or source_id,
                    resolution_mode=resolution_mode,
                    attack_bonus=attack_bonus,
                    save_ability=save_ability,
                    save_dc=save_dc,
                    origin_path=catalog_path,
                )

    for rule_id, locations in sorted(duplicate_rule_id_locations.items()):
        if len(locations) > 1:
            joined = "; ".join(locations)
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="duplicate_rule_ids",
                    message=f"Rule id '{rule_id}' appears multiple times: {joined}",
                )
            )

    catalogs_dir = (rules_data_dir / "catalogs").resolve()
    for catalog_path in _iter_json_files(catalogs_dir):
        resolved = catalog_path.resolve()
        if resolved not in referenced_catalog_paths:
            issues.append(
                LintIssue(
                    level="WARNING",
                    code="orphaned_catalogs",
                    message="Catalog file exists on disk but is not referenced by rules_data/registry.json.",
                    path=_norm_path(catalog_path),
                )
            )

    return issues, spell_index


def _collect_encounter_files(paths: list[Path]) -> list[Path]:
    found: set[Path] = set()

    for path in paths:
        path = path.resolve()
        if path.is_file() and path.suffix.lower() == ".json":
            found.add(path)
            continue

        if path.is_dir():
            for child in path.rglob("*.json"):
                if child.is_file():
                    found.add(child.resolve())

    return sorted(found)


def lint_encounters(
    encounter_paths: list[Path],
    schema_dir: Path,
    spell_index: dict[str, CanonicalSpell],
) -> list[LintIssue]:
    issues: list[LintIssue] = []

    for encounter_path in _collect_encounter_files(encounter_paths):
        raw_data = _read_json_file(encounter_path, issues, code_prefix="encounter")
        if raw_data is None:
            continue

        try:
            validate_encounter_data(raw_data, schema_dir)
        except EncounterSchemaError as exc:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="encounter_schema_invalid",
                    message=str(exc),
                    path=_norm_path(encounter_path),
                )
            )
            continue

        creatures = raw_data.get("creatures", [])
        if not isinstance(creatures, list):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="encounter_creatures_invalid",
                    message="'creatures' must be a list.",
                    path=_norm_path(encounter_path),
                )
            )
            continue

        for creature_index, creature in enumerate(creatures):
            if not isinstance(creature, dict):
                continue

            creature_name = str(creature.get("name", creature.get("id", f"creature[{creature_index}]")))
            actions = creature.get("actions", [])
            if not isinstance(actions, list):
                continue

            for action_index, action in enumerate(actions):
                if not isinstance(action, dict):
                    continue

                kind = str(action.get("kind", "")).strip()
                action_name = str(action.get("name", action.get("id", f"action[{action_index}]")))
                action_loc = (
                    f"{_norm_path(encounter_path)}"
                    f"::creatures[{creature_index}]({creature_name})"
                    f"::actions[{action_index}]({action_name})"
                )

                if kind != "spell":
                    continue

                spell_ref = str(action.get("spell_ref", "")).strip()
                if not spell_ref:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="missing_spell_ref",
                            message="Spell action is missing a non-empty 'spell_ref'.",
                            path=action_loc,
                        )
                    )
                    continue

                spell = spell_index.get(spell_ref)
                if spell is None:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="unknown_spell_ref",
                            message=f"spell_ref '{spell_ref}' does not exist in loaded rules catalogs.",
                            path=action_loc,
                        )
                    )
                    continue

                if spell.resolution_mode == "attack":
                    if spell.attack_bonus is None and action.get("attack_bonus_override") is None:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="missing_attack_bonus_override",
                                message=(
                                    f"Spell action references attack-roll spell '{spell_ref}' "
                                    f"with no canonical attack_bonus, but forgot attack_bonus_override."
                                ),
                                path=action_loc,
                            )
                        )

                if spell.resolution_mode == "save":
                    if spell.save_dc is None and action.get("save_dc_override") is None:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="missing_save_dc_override",
                                message=(
                                    f"Spell action references save-based spell '{spell_ref}' "
                                    f"with no canonical save_dc, but forgot save_dc_override."
                                ),
                                path=action_loc,
                            )
                        )

                    if not spell.save_ability:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="bad_source_reference",
                                message=(
                                    f"Spell action references save-based spell '{spell_ref}' "
                                    f"whose canonical definition is missing save_ability."
                                ),
                                path=action_loc,
                            )
                        )

    return issues


def print_issues(issues: list[LintIssue]) -> None:
    if not issues:
        print("rules_linter: no issues found")
        return

    severity_order = {"ERROR": 0, "WARNING": 1}
    for issue in sorted(issues, key=lambda item: (severity_order[item.level], item.code, item.path or "")):
        print(issue.render())


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parent.parent
    default_rules_data_dir = (project_root / "rules_data").resolve()
    default_schema_dir = (project_root / "schemas").resolve()
    default_examples_dir = (project_root / "examples").resolve()

    parser = argparse.ArgumentParser(
        description="Lint rules_data catalogs and encounter files for D&D simulator consistency problems."
    )
    parser.add_argument(
        "--rules-data-dir",
        type=Path,
        default=default_rules_data_dir,
        help=f"Path to rules_data directory. Default: {default_rules_data_dir}",
    )
    parser.add_argument(
        "--schema-dir",
        type=Path,
        default=default_schema_dir,
        help=f"Path to schema directory. Default: {default_schema_dir}",
    )
    parser.add_argument(
        "--encounter",
        dest="encounters",
        type=Path,
        action="append",
        default=[],
        help="Encounter JSON file or directory to lint. May be specified multiple times.",
    )
    parser.add_argument(
        "--skip-encounters",
        action="store_true",
        help="Only lint rules_data/ and skip encounter linting.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as failures too.",
    )

    args = parser.parse_args()

    if not args.encounters and not args.skip_encounters and default_examples_dir.exists():
        args.encounters = [default_examples_dir]

    return args


def main() -> int:
    args = parse_args()

    rules_issues, spell_index = lint_rules_data(args.rules_data_dir)
    encounter_issues: list[LintIssue] = []

    if not args.skip_encounters:
        encounter_issues = lint_encounters(args.encounters, args.schema_dir, spell_index)

    all_issues = rules_issues + encounter_issues
    print_issues(all_issues)

    error_count = sum(1 for issue in all_issues if issue.level == "ERROR")
    warning_count = sum(1 for issue in all_issues if issue.level == "WARNING")

    print()
    print(
        f"rules_linter summary: errors={error_count} warnings={warning_count} "
        f"spells_loaded={len(spell_index)}"
    )

    if error_count > 0:
        return 1
    if args.strict and warning_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
