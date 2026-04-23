import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = "rules_data/sources/srd-5.2.1-public"
DEFAULT_MARKDOWN_INDEX = "rules_data/sources/srd-5.2.1-public-resources.md"
DEFAULT_JSON_MANIFEST = "rules_data/sources/srd-5.2.1-public-resources.json"


CORE_5_2_1_RESOURCES = [
    # Official SRD 5.2.1 docs
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "SRD resource landing page",
        "url": "https://www.dndbeyond.com/resources/1781-systems-reference-document-srd",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "SRD web hub",
        "url": "https://www.dndbeyond.com/srd",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD CC v5.2.1 (English PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.1.pdf",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD 5.1 -> 5.2.1 conversion guide (PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/guide/converting-to-srd-5.2.1.pdf",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD CC v5.2.1 (German PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2/DE_SRD_CC_v5.2.1.pdf",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD CC v5.2.1 (Spanish PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2/SP_SRD_CC_v5.2.1.pdf",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD CC v5.2.1 (French PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2/FR_SRD_CC_v5.2.1.pdf",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD CC v5.2.1 (Italian PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2/IT_SRD_CC_v5.2.1.pdf",
    },
    {
        "category": "official_srd_5_2_1",
        "source": "D&D Beyond media CDN",
        "title": "SRD CC v5.2 (historic PDF)",
        "url": "https://media.dndbeyond.com/compendium-images/srd/5.2/SRD_CC_v5.2.pdf",
    },

    # 2024 basic rules pages (adjacent public rules/lore material)
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "D&D Beyond Basic Rules (2024) index",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "The Basics",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/the-basics",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Playing the Game",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/playing-the-game",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Creating a Character",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/creating-a-character",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Character Classes",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/character-classes",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Character Origins",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/character-origins",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Feats",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/feats",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Equipment",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/equipment",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Spells",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/spells",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Spell Descriptions",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/spell-descriptions",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Rules Glossary",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/rules-glossary",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "DM's Toolbox",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/dms-toolbox",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "How to Use a Monster",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/how-to-use-a-monster",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Creature Stat Blocks",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/creature-stat-blocks",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Magic Items",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/magic-items",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Magic Items A-Z",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/magic-items-a-z",
    },
    {
        "category": "free_rules_2024_pages",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Tracking Sheets",
        "url": "https://www.dndbeyond.com/sources/dnd/br-2024/tracking-sheets",
    },

    # Related assets (images + printable sheets)
    {
        "category": "related_media_assets",
        "source": "D&D Beyond media CDN",
        "title": "Character sheet PDF",
        "url": "https://media.dndbeyond.com/compendium-images/br/ph/character-sheet.pdf",
    },
    {
        "category": "related_media_assets",
        "source": "D&D Beyond media CDN",
        "title": "Free rules TOC image 1k",
        "url": "https://media.dndbeyond.com/compendium-images/phb/ui/free-rules-toc-1k.jpg",
    },
    {
        "category": "related_media_assets",
        "source": "D&D Beyond media CDN",
        "title": "Free rules TOC image 2k",
        "url": "https://media.dndbeyond.com/compendium-images/phb/ui/free-rules-toc-2k.jpg",
    },
    {
        "category": "related_media_assets",
        "source": "D&D Beyond media CDN",
        "title": "Free rules TOC image 4k",
        "url": "https://media.dndbeyond.com/compendium-images/phb/ui/free-rules-toc-4k.jpg",
    },
    {
        "category": "related_media_assets",
        "source": "D&D Beyond media CDN",
        "title": "SRD page download icon (SVG)",
        "url": "https://media.dndbeyond.com/compendium-images/one-dnd/3t4Ut1eEc3GNh103/white-download-icon.svg",
    },

    # Public mirror references
    {
        "category": "public_mirror_reference",
        "source": "Wikimedia Commons",
        "title": "Wikimedia file page for SRD 5.2.1",
        "url": "https://commons.wikimedia.org/wiki/File:Dungeons_%26_Dragons_System_Reference_Document_v5.2.1_(2025).pdf",
    },
    {
        "category": "public_mirror_reference",
        "source": "Wikimedia Commons upload",
        "title": "Wikimedia direct SRD 5.2.1 PDF",
        "url": "https://upload.wikimedia.org/wikipedia/commons/e/e2/Dungeons_%26_Dragons_System_Reference_Document_v5.2.1_%282025%29.pdf",
    },
    {
        "category": "public_mirror_reference",
        "source": "Wikimedia Commons upload",
        "title": "Wikimedia SRD 5.2.1 preview image page 1",
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Dungeons_%26_Dragons_System_Reference_Document_v5.2.1_%282025%29.pdf/page1-960px-Dungeons_%26_Dragons_System_Reference_Document_v5.2.1_%282025%29.pdf.jpg",
    },
]


OPTIONAL_GENERAL_ASSETS_RESOURCES = [
    {
        "category": "general_lore_docs",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "How to Play D&D",
        "url": "https://www.dndbeyond.com/how-to-play-dnd",
    },
    {
        "category": "general_lore_docs",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "What is Dungeons & Dragons?",
        "url": "https://www.dndbeyond.com/posts/1480-what-is-dungeons-dragons",
    },
    {
        "category": "general_lore_docs",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "D&D Character Sheets resource",
        "url": "https://www.dndbeyond.com/resources/1779-d-d-character-sheets",
    },
    {
        "category": "general_rules_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Basic Rules (2014)",
        "url": "https://www.dndbeyond.com/sources/dnd/basic-rules-2014",
    },
    {
        "category": "general_rules_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Unearthed Arcana source index",
        "url": "https://www.dndbeyond.com/sources/dnd/ua",
    },
    {
        "category": "general_rules_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Wayfinder's source index",
        "url": "https://www.dndbeyond.com/sources/dnd/wa",
    },
    {
        "category": "general_rules_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Monstrous Compendium source index",
        "url": "https://www.dndbeyond.com/sources/dnd/mcv1",
    },
    {
        "category": "general_updates",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Community Update",
        "url": "https://www.dndbeyond.com/community-update",
    },
    {
        "category": "general_updates",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Site Changelog",
        "url": "https://www.dndbeyond.com/changelog",
    },
    {
        "category": "general_updates",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Articles index",
        "url": "https://www.dndbeyond.com/articles",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Games index",
        "url": "https://www.dndbeyond.com/games",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Monsters index",
        "url": "https://www.dndbeyond.com/monsters",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Spells index",
        "url": "https://www.dndbeyond.com/spells",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Classes index",
        "url": "https://www.dndbeyond.com/classes",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Species index",
        "url": "https://www.dndbeyond.com/species",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Magic Items index",
        "url": "https://www.dndbeyond.com/magic-items",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Feats index",
        "url": "https://www.dndbeyond.com/feats",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Backgrounds index",
        "url": "https://www.dndbeyond.com/backgrounds",
    },
    {
        "category": "general_game_data_indexes",
        "source": "D&D Beyond (Wizards of the Coast)",
        "title": "Equipment index",
        "url": "https://www.dndbeyond.com/equipment",
    },
]


RESOURCE_GROUPS = {
    "core_5_2_1": CORE_5_2_1_RESOURCES,
    "optional_general_assets": OPTIONAL_GENERAL_ASSETS_RESOURCES,
}

GROUP_DESCRIPTIONS = {
    "core_5_2_1": "Default SRD 5.2.1, 2024 free rules pages, media assets, and mirror references.",
    "optional_general_assets": "Optional non-SRD general docs, lore pages, and expansion/index pages.",
}

DEFAULT_GROUPS = ("core_5_2_1",)
OPTIONAL_GROUPS = frozenset({"optional_general_assets"})


def slugify(text: str) -> str:
    keep = []
    for ch in text.lower():
        if ch.isalnum():
            keep.append(ch)
        else:
            keep.append("-")
    out = "".join(keep)
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-")


def guess_extension(url: str, content_type: str) -> str:
    ctype = (content_type or "").lower()
    if "html" in ctype:
        return ".html"
    if "pdf" in ctype:
        return ".pdf"
    if "json" in ctype:
        return ".json"
    if "jpeg" in ctype or "jpg" in ctype:
        return ".jpg"
    if "png" in ctype:
        return ".png"
    if "svg" in ctype:
        return ".svg"

    path = urlparse(url).path
    leaf = path.split("/")[-1]
    if "." in leaf:
        return "." + leaf.split(".")[-1].lower()
    return ".bin"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch public D&D resources, write local files, and emit markdown/json manifests."
        )
    )
    parser.add_argument(
        "--list-groups",
        action="store_true",
        help="List available resource groups and exit.",
    )
    parser.add_argument(
        "--all-groups",
        action="store_true",
        help="Fetch every available group (default + optional).",
    )
    parser.add_argument(
        "--include-group",
        action="append",
        choices=sorted(OPTIONAL_GROUPS),
        default=[],
        help="Include an optional group in addition to defaults. May be repeated.",
    )
    parser.add_argument(
        "--include-optional-general",
        action="store_true",
        help="Shortcut for --include-group optional_general_assets.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Download output directory (absolute or repo-relative).",
    )
    parser.add_argument(
        "--index-md",
        default=DEFAULT_MARKDOWN_INDEX,
        help="Markdown manifest path (absolute or repo-relative).",
    )
    parser.add_argument(
        "--index-json",
        default=DEFAULT_JSON_MANIFEST,
        help="JSON manifest path (absolute or repo-relative).",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=60,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args()


def resolve_repo_path(path_text: str) -> Path:
    candidate = Path(path_text)
    if candidate.is_absolute():
        return candidate
    return ROOT_DIR / candidate


def display_path(path_obj: Path) -> str:
    try:
        return str(path_obj.relative_to(ROOT_DIR))
    except ValueError:
        return str(path_obj)


def list_groups() -> None:
    print("Available resource groups:")
    for group in RESOURCE_GROUPS:
        marker = " (default)" if group in DEFAULT_GROUPS else ""
        optional = " (optional)" if group in OPTIONAL_GROUPS else ""
        print(f"- {group}{marker}{optional}: {GROUP_DESCRIPTIONS[group]}")


def select_groups(args: argparse.Namespace) -> list[str]:
    if args.all_groups:
        return list(RESOURCE_GROUPS.keys())

    selected = list(DEFAULT_GROUPS)
    requested = set(args.include_group)
    if args.include_optional_general:
        requested.add("optional_general_assets")

    for group in sorted(requested):
        if group not in selected:
            selected.append(group)
    return selected


def collect_resources(groups: list[str]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for item in RESOURCE_GROUPS[group]:
            resource = {**item, "group": group}
            key = (resource["category"], resource["title"], resource["url"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(resource)
    return merged


def fetch_resources(
    resources: list[dict[str, str]],
    out_dir: Path,
    timeout_seconds: int,
) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {"User-Agent": "Mozilla/5.0 (compatible; dnd-engine-source-fetch/1.1)"}
    )

    results: list[dict[str, object]] = []
    for item in resources:
        url = item["url"]
        fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        try:
            resp = session.get(url, timeout=timeout_seconds, allow_redirects=True)
            status = resp.status_code
            ctype = (resp.headers.get("content-type") or "").split(";")[0]
            ext = guess_extension(url, ctype)

            # stable local file name: category + title slug + extension
            fname = f"{item['category']}__{slugify(item['title'])}{ext}"
            fpath = out_dir / fname

            if status == 200:
                fpath.write_bytes(resp.content)
                size = fpath.stat().st_size
                sha256 = hashlib.sha256(resp.content).hexdigest()
                saved_rel = display_path(fpath)
            else:
                size = 0
                sha256 = ""
                saved_rel = ""

            results.append(
                {
                    **item,
                    "status": status,
                    "content_type": ctype,
                    "bytes": size,
                    "sha256": sha256,
                    "saved_file": saved_rel,
                    "final_url": resp.url,
                    "fetched_at_utc": fetched_at,
                }
            )
            print(f"{status}\t{ctype}\t{url}")
        except Exception as exc:
            results.append(
                {
                    **item,
                    "status": "ERROR",
                    "content_type": "",
                    "bytes": 0,
                    "sha256": "",
                    "saved_file": "",
                    "final_url": "",
                    "fetched_at_utc": fetched_at,
                    "error": str(exc),
                }
            )
            print(f"ERROR\t{url}\t{exc}")

    return results


def write_markdown_index(
    md_path: Path,
    results: list[dict[str, object]],
    selected_groups: list[str],
) -> None:
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    optional_groups = [group for group in selected_groups if group in OPTIONAL_GROUPS]

    lines = []
    lines.append("# Public D&D Resource Index")
    lines.append("")
    lines.append(f"Generated at UTC: {generated_at}")
    lines.append(f"Selected groups: {', '.join(selected_groups)}")
    lines.append(
        "Optional groups included: " + (", ".join(optional_groups) if optional_groups else "none")
    )
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- Default run fetches the core SRD 5.2.1 set.")
    lines.append(
        "- Add --include-optional-general to include non-SRD general docs, lore, and expansion/index pages."
    )
    lines.append("- Prefer official URLs where available; mirrors are listed as secondary references.")
    lines.append("")
    lines.append("## Resources")
    lines.append("")
    lines.append(
        "| Group | Category | Source | Title | URL | Status | Type | Bytes | Local File | SHA256 |"
    )
    lines.append("|---|---|---|---|---|---:|---|---:|---|---|")
    for resource in results:
        status = str(resource["status"])
        local_file = resource["saved_file"] if resource["saved_file"] else "-"
        sha = resource["sha256"] if resource["sha256"] else "-"
        lines.append(
            f"| {resource['group']} | {resource['category']} | {resource['source']} | {resource['title']} | {resource['url']} | {status} | {resource['content_type'] or '-'} | {resource['bytes']} | {local_file} | {sha} |"
        )

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json_manifest(json_path: Path, results: list[dict[str, object]]) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(results, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()

    if args.list_groups:
        list_groups()
        return

    selected_groups = select_groups(args)
    resources = collect_resources(selected_groups)

    out_dir = resolve_repo_path(args.output_dir)
    md_path = resolve_repo_path(args.index_md)
    json_path = resolve_repo_path(args.index_json)

    print(f"Selected groups: {', '.join(selected_groups)}")
    print(f"Resources queued: {len(resources)}")

    results = fetch_resources(resources, out_dir, args.timeout_seconds)
    write_markdown_index(md_path, results, selected_groups)
    write_json_manifest(json_path, results)

    ok_count = sum(1 for result in results if result["status"] == 200)
    print(f"\nDownloaded OK: {ok_count}/{len(results)}")
    print(f"Markdown index: {display_path(md_path)}")
    print(f"JSON manifest: {display_path(json_path)}")
    print(f"Download folder: {display_path(out_dir)}")


if __name__ == "__main__":
    main()
