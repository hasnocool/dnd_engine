from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Literal

from schema_loader import EncounterSchemaError, validate_encounter_data


ALLOWED_RESOLUTION_MODES = {"attack", "save", "effect"}
REQUIRED_CATALOG_TYPES = (
    "conditions",
    "spells",
    "monsters",
    "weapons",
    "armor",
    "magic_items",
    "classes",
    "species",
    "feats",
)


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


@dataclass(slots=True)
class LintState:
    spell_index: dict[str, CanonicalSpell]
    condition_ids: set[str]
    condition_names: set[str]
    catalog_counts: dict[str, int]


def _norm_path(path: Path) -> str:
    return str(path.resolve())


def _read_json_file(path: Path, issues: list[LintIssue], *, code_prefix: str) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
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


def _extract_catalog_rows(catalog_type: str, payload: Any) -> list[dict[str, Any]] | None:
    if isinstance(payload, list):
        raw_rows = payload
    elif isinstance(payload, dict):
        if catalog_type == "spells":
            raw_rows = payload.get("spells", [])
        else:
            raw_rows = payload.get(catalog_type, payload.get("items", payload.get("entries", [])))
            if raw_rows == [] and all(isinstance(v, list) for v in payload.values()):
                # Heuristic: pick single list value if parser used nonstandard key.
                list_values = [v for v in payload.values() if isinstance(v, list)]
                if len(list_values) == 1:
                    raw_rows = list_values[0]
    else:
        return None

    if not isinstance(raw_rows, list):
        return None

    rows: list[dict[str, Any]] = []
    for row in raw_rows:
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _build_spell_index(
    rows: list[dict[str, Any]],
    source_id: str,
    catalog_path: Path,
    issues: list[LintIssue],
) -> dict[str, CanonicalSpell]:
    spell_index: dict[str, CanonicalSpell] = {}

    for idx, raw_spell in enumerate(rows):
        spell_loc = f"{_norm_path(catalog_path)}::spells[{idx}]"

        spell_id = str(raw_spell.get("id", "")).strip()
        if not spell_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="spell_missing_id",
                    message="Spell entry is missing non-empty id.",
                    path=spell_loc,
                )
            )
            continue

        spell_source_id = str(raw_spell.get("source_id") or raw_spell.get("source") or "").strip()
        if not spell_source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="spell_missing_source_id",
                    message=f"Spell '{spell_id}' is missing source_id/source.",
                    path=spell_loc,
                )
            )
        elif spell_source_id != source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=(
                        f"Spell '{spell_id}' source mismatch: catalog source_id='{source_id}' "
                        f"spell source_id='{spell_source_id}'."
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
                        f"Allowed={sorted(ALLOWED_RESOLUTION_MODES)}"
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
                    message=f"Save spell '{spell_id}' missing save_ability.",
                    path=spell_loc,
                )
            )

        if resolution_mode == "attack" and attack_bonus is None:
            issues.append(
                LintIssue(
                    level="WARNING",
                    code="spell_requires_attack_bonus_override",
                    message=(
                        f"Attack-roll spell '{spell_id}' has no canonical attack_bonus; "
                        "encounters must set attack_bonus_override."
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
                        f"Save-based spell '{spell_id}' has no canonical save_dc; "
                        "encounters must set save_dc_override."
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

    return spell_index


def lint_rules_data(rules_data_dir: Path) -> tuple[list[LintIssue], LintState]:
    issues: list[LintIssue] = []

    rules_data_dir = rules_data_dir.resolve()
    registry_path = rules_data_dir / "registry.json"

    empty_state = LintState(spell_index={}, condition_ids=set(), condition_names=set(), catalog_counts={})

    if not registry_path.exists():
        issues.append(
            LintIssue(
                level="ERROR",
                code="missing_registry",
                message="Missing rules_data/registry.json",
                path=_norm_path(registry_path),
            )
        )
        return issues, empty_state

    registry = _read_json_file(registry_path, issues, code_prefix="registry")
    if not isinstance(registry, dict):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_root_not_object",
                message="registry.json root must be object.",
                path=_norm_path(registry_path),
            )
        )
        return issues, empty_state

    raw_sources = registry.get("sources")
    if not isinstance(raw_sources, list):
        issues.append(
            LintIssue(
                level="ERROR",
                code="registry_sources_invalid",
                message="'sources' must be list.",
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
                    message="Source entry must be object.",
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
                    message="Source entry missing non-empty id.",
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
                    message=f"Source '{source_id}' missing non-empty path.",
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
                    message=f"Source '{source_id}' points to missing file.",
                    path=_norm_path(source_path),
                )
            )
            continue

        source_payload = _read_json_file(source_path, issues, code_prefix="source")
        if not isinstance(source_payload, dict):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="source_root_not_object",
                    message="Source file root must be object.",
                    path=_norm_path(source_path),
                )
            )
            continue

        payload_source_id = str(source_payload.get("source_id", "")).strip()
        if payload_source_id and payload_source_id != source_id:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="bad_source_reference",
                    message=(
                        f"Source file source_id mismatch. registry='{source_id}' file='{payload_source_id}'."
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
                message="'catalogs' must be object.",
                path=_norm_path(registry_path),
            )
        )
        raw_catalogs = {}

    for required in REQUIRED_CATALOG_TYPES:
        if required not in raw_catalogs:
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="missing_catalog_type",
                    message=f"registry.catalogs missing key '{required}'.",
                    path=_norm_path(registry_path),
                )
            )

    referenced_catalog_paths: set[Path] = set()
    duplicate_ids_by_catalog: dict[str, defaultdict[str, list[str]]] = {
        catalog_type: defaultdict(list) for catalog_type in REQUIRED_CATALOG_TYPES
    }

    spell_index: dict[str, CanonicalSpell] = {}
    condition_ids: set[str] = set()
    condition_names: set[str] = set()
    catalog_counts: dict[str, int] = defaultdict(int)

    for catalog_type, raw_entries in raw_catalogs.items():
        if not isinstance(raw_entries, list):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="registry_catalog_entry_list_invalid",
                    message=f"registry.catalogs.{catalog_type} must be list.",
                    path=_norm_path(registry_path),
                )
            )
            continue

        for index, catalog_entry in enumerate(raw_entries):
            entry_path = f"{_norm_path(registry_path)}::catalogs.{catalog_type}[{index}]"

            if not isinstance(catalog_entry, dict):
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="catalog_entry_invalid",
                        message="Catalog entry must be object.",
                        path=entry_path,
                    )
                )
                continue

            source_id = str(catalog_entry.get("source_id", "")).strip()
            catalog_rel_path = str(catalog_entry.get("path", "")).strip()
            expected_count = _as_int_or_none(catalog_entry.get("count"))

            if not source_id:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="catalog_missing_source_id",
                        message=f"Catalog '{catalog_type}' entry missing source_id.",
                        path=entry_path,
                    )
                )
                continue

            if source_id not in source_id_to_path:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="bad_source_reference",
                        message=(
                            f"Catalog '{catalog_type}' references unknown source_id '{source_id}'."
                        ),
                        path=entry_path,
                    )
                )

            if not catalog_rel_path:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="catalog_missing_path",
                        message=f"Catalog '{catalog_type}' entry missing path.",
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
                        message="Referenced catalog file does not exist.",
                        path=_norm_path(catalog_path),
                    )
                )
                continue

            payload = _read_json_file(catalog_path, issues, code_prefix="catalog")
            if payload is None:
                continue

            rows = _extract_catalog_rows(catalog_type, payload)
            if rows is None:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="catalog_rows_invalid",
                        message=f"Could not extract rows for catalog type '{catalog_type}'.",
                        path=_norm_path(catalog_path),
                    )
                )
                continue

            catalog_counts[catalog_type] += len(rows)

            if expected_count is not None and expected_count != len(rows):
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="catalog_count_mismatch",
                        message=(
                            f"Catalog '{catalog_type}' expected count={expected_count} "
                            f"but file has count={len(rows)}."
                        ),
                        path=_norm_path(catalog_path),
                    )
                )

            for row_idx, row in enumerate(rows):
                item_loc = f"{_norm_path(catalog_path)}::{catalog_type}[{row_idx}]"

                row_id = str(row.get("id", "")).strip()
                if not row_id:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="catalog_item_missing_id",
                            message=f"Catalog '{catalog_type}' item missing non-empty id.",
                            path=item_loc,
                        )
                    )
                    continue

                duplicate_ids_by_catalog.setdefault(catalog_type, defaultdict(list))[row_id].append(item_loc)

                row_source = str(row.get("source_id") or row.get("source") or "").strip()
                if row_source and row_source != source_id:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="bad_source_reference",
                            message=(
                                f"Catalog '{catalog_type}' id='{row_id}' source mismatch: "
                                f"entry source_id='{source_id}', item source='{row_source}'."
                            ),
                            path=item_loc,
                        )
                    )

                if catalog_type == "conditions":
                    condition_ids.add(row_id.casefold())
                    condition_name = str(row.get("name", "")).strip()
                    if condition_name:
                        condition_names.add(condition_name.casefold())

            if catalog_type == "spells":
                new_spells = _build_spell_index(rows, source_id, catalog_path, issues)
                for spell_id, spell in new_spells.items():
                    if spell_id in spell_index:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="duplicate_rule_ids",
                                message=(
                                    f"Rule id '{spell_id}' duplicated across spell catalogs: "
                                    f"{spell_index[spell_id].origin_path} ; {catalog_path}"
                                ),
                            )
                        )
                    else:
                        spell_index[spell_id] = spell

    for catalog_type, mapping in sorted(duplicate_ids_by_catalog.items()):
        for rule_id, locations in sorted(mapping.items()):
            if len(locations) > 1:
                issues.append(
                    LintIssue(
                        level="ERROR",
                        code="duplicate_rule_ids",
                        message=(
                            f"Catalog '{catalog_type}' has duplicate id '{rule_id}': "
                            + "; ".join(locations)
                        ),
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
                    message="Catalog file exists on disk but is not referenced by registry.json.",
                    path=_norm_path(catalog_path),
                )
            )

    state = LintState(
        spell_index=spell_index,
        condition_ids=condition_ids,
        condition_names=condition_names,
        catalog_counts=dict(catalog_counts),
    )

    return issues, state


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
    condition_ids: set[str],
    condition_names: set[str],
) -> list[LintIssue]:
    issues: list[LintIssue] = []

    for encounter_path in _collect_encounter_files(encounter_paths):
        raw_data = _read_json_file(encounter_path, issues, code_prefix="encounter")
        if not isinstance(raw_data, dict):
            issues.append(
                LintIssue(
                    level="ERROR",
                    code="encounter_root_not_object",
                    message="Encounter root must be object.",
                    path=_norm_path(encounter_path),
                )
            )
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
                    message="'creatures' must be list.",
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

            action_id_set = {
                str(action.get("id", "")).strip()
                for action in actions
                if isinstance(action, dict) and str(action.get("id", "")).strip()
            }

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

                if kind == "multiattack":
                    sub_actions = action.get("sub_actions")
                    if not isinstance(sub_actions, list) or not sub_actions:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="multiattack_sub_actions_invalid",
                                message="multiattack action requires non-empty sub_actions list.",
                                path=action_loc,
                            )
                        )
                    else:
                        for sub_action_id in sub_actions:
                            if not isinstance(sub_action_id, str) or not sub_action_id.strip():
                                issues.append(
                                    LintIssue(
                                        level="ERROR",
                                        code="multiattack_sub_action_id_invalid",
                                        message="sub_actions entries must be non-empty strings.",
                                        path=action_loc,
                                    )
                                )
                                continue
                            if sub_action_id not in action_id_set:
                                issues.append(
                                    LintIssue(
                                        level="ERROR",
                                        code="multiattack_sub_action_missing",
                                        message=f"sub_action '{sub_action_id}' not found on creature.",
                                        path=action_loc,
                                    )
                                )
                    continue

                if kind != "spell":
                    continue

                spell_ref = str(action.get("spell_ref", "")).strip()
                if not spell_ref:
                    issues.append(
                        LintIssue(
                            level="ERROR",
                            code="missing_spell_ref",
                            message="Spell action missing non-empty spell_ref.",
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
                            message=f"spell_ref '{spell_ref}' not found in loaded spell catalogs.",
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
                                    f"Spell action uses attack-roll spell '{spell_ref}' with no canonical "
                                    "attack_bonus; attack_bonus_override required."
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
                                    f"Spell action uses save spell '{spell_ref}' with no canonical save_dc; "
                                    "save_dc_override required."
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
                                    f"Spell action references save spell '{spell_ref}' whose canonical "
                                    "definition is missing save_ability."
                                ),
                                path=action_loc,
                            )
                        )

            conditions = creature.get("conditions", [])
            if isinstance(conditions, list):
                for condition_index, condition in enumerate(conditions):
                    if not isinstance(condition, dict):
                        continue
                    condition_name = str(condition.get("name", "")).strip()
                    if not condition_name:
                        continue
                    key = condition_name.casefold()
                    if key not in condition_ids and key not in condition_names:
                        issues.append(
                            LintIssue(
                                level="ERROR",
                                code="unknown_condition_name",
                                message=f"Condition '{condition_name}' is not in condition catalog.",
                                path=(
                                    f"{_norm_path(encounter_path)}"
                                    f"::creatures[{creature_index}]({creature_name})"
                                    f"::conditions[{condition_index}]"
                                ),
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
        help="Only lint rules_data and skip encounter linting.",
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

    rules_issues, state = lint_rules_data(args.rules_data_dir)
    encounter_issues: list[LintIssue] = []

    if not args.skip_encounters:
        encounter_issues = lint_encounters(
            args.encounters,
            args.schema_dir,
            state.spell_index,
            state.condition_ids,
            state.condition_names,
        )

    all_issues = rules_issues + encounter_issues
    print_issues(all_issues)

    error_count = sum(1 for issue in all_issues if issue.level == "ERROR")
    warning_count = sum(1 for issue in all_issues if issue.level == "WARNING")

    print()
    print(
        "rules_linter summary: "
        f"errors={error_count} warnings={warning_count} "
        f"spells_loaded={len(state.spell_index)} "
        f"catalog_counts={state.catalog_counts}"
    )

    if error_count > 0:
        return 1
    if args.strict and warning_count > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
