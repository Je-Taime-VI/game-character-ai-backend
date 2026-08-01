from __future__ import annotations

import json
from pathlib import Path

from src.extract_role_info import OUTPUT_PATH as ROLE_INFO_OUTPUT, extract_all_role_infos, save_role_infos


PERMISSIONS_DIR = Path("data/permissions")
ORG_REGION_MAPPING_PATH = PERMISSIONS_DIR / "org_region_mapping.json"

ROLE_ROOT = "角色"
WORLD_GLOBAL_ROOT = "世界观/全局世界观"
WORLD_REGION_ROOT = "世界观/地区信息"


DEFAULT_ORG_REGION_MAPPING = {
    "拉海洛": "罗伊冰原",
    "星炬学院": "罗伊冰原",
    "隐海修会": "黎那汐塔/拉古那",
    "翡萨烈家族": "黎那汐塔/拉古那",
    "莫塔里家族": "黎那汐塔/拉古那",
    "愚人剧团": "黎那汐塔/拉古那",
    "拉古那": "黎那汐塔/拉古那",
    "七丘": "黎那汐塔/七丘",
    "明庭": "瑝珑/明庭",
    "今州": "瑝珑/今州",
    "梦州": "瑝珑/梦州",
    "瑝珑": "瑝珑",
    "苇原": "苇原",
    "新联邦": "新联邦",
    "黑海岸": "黑海岸",
    "残星会": "残星会",
}

def ensure_default_files() -> None:
    PERMISSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if not ORG_REGION_MAPPING_PATH.exists():
        ORG_REGION_MAPPING_PATH.write_text(
            json.dumps(DEFAULT_ORG_REGION_MAPPING, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def load_org_region_mapping() -> dict[str, str]:
    ensure_default_files()
    return load_json(ORG_REGION_MAPPING_PATH, DEFAULT_ORG_REGION_MAPPING)


def save_org_region_mapping(mapping: dict[str, str]) -> Path:
    ensure_default_files()
    ORG_REGION_MAPPING_PATH.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return ORG_REGION_MAPPING_PATH


def load_json(path: Path, default):
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def normalize_region_name(raw_value: str | None, org_region_mapping: dict[str, str]) -> str | None:
    if not raw_value:
        return None
    value = raw_value.strip()
    if not value:
        return None
    return org_region_mapping.get(value, value)


def build_region_permission_entry(region_path: str) -> dict:
    return {
        "region_path": region_path,
        "world_prefix": f"{WORLD_REGION_ROOT}/{region_path}",
        "match_mode": "layer",
    }


def expand_region_with_ancestors(region_path: str | None) -> list[str]:
    if not region_path:
        return []
    parts = [part for part in region_path.split("/") if part]
    expanded: list[str] = []
    for index in range(1, len(parts) + 1):
        expanded.append("/".join(parts[:index]))
    return expanded


def permission_file_path(role_name: str, permissions_dir: Path = PERMISSIONS_DIR) -> Path:
    return permissions_dir / f"{role_name}.json"


def default_role_permission_template(role_name: str) -> dict:
    return {
        "role_name": role_name,
        "extra_role_paths": [],
        "extra_world_paths": [],
        "region_overrides": [],
        "allowed_story_paths": [],
        "allowed_story_premises": [],
        "allowed_story_segments": [],
        "notes": "",
    }


def load_role_permission_config(role_name: str, permissions_dir: Path = PERMISSIONS_DIR) -> dict:
    path = permission_file_path(role_name, permissions_dir)
    config = default_role_permission_template(role_name)
    existing = load_json(path, {})
    if isinstance(existing, dict):
        config.update(existing)
    config["role_name"] = role_name
    return config


def load_permission_for_role(role_name: str, permissions_dir: Path = PERMISSIONS_DIR) -> dict | None:
    path = permission_file_path(role_name, permissions_dir)
    if not path.exists():
        return None
    return load_json(path, None)


def generate_permission_for_role(
    role_info: dict,
    org_region_mapping: dict[str, str],
    manual_config: dict | None = None,
) -> dict:
    role_name = role_info["role_name"]
    manual = default_role_permission_template(role_name)
    if manual_config:
        manual.update(manual_config)

    region_values = set()
    birth_region = normalize_region_name(role_info.get("birthplace"), org_region_mapping)
    affiliation_region = normalize_region_name(role_info.get("affiliation"), org_region_mapping)
    for region in expand_region_with_ancestors(birth_region):
        region_values.add(region)
    for region in expand_region_with_ancestors(affiliation_region):
        region_values.add(region)
    for extra_region in manual.get("region_overrides", []):
        for region in expand_region_with_ancestors(extra_region):
            region_values.add(region)

    forced_role_paths = [f"{ROLE_ROOT}/{role_name}"]
    forced_world_paths = [WORLD_GLOBAL_ROOT]
    forced_region_layers = [
        build_region_permission_entry(region_path)
        for region_path in sorted(region_values)
    ]

    final_role_paths = [
        *forced_role_paths,
        *manual.get("extra_role_paths", []),
    ]
    final_world_paths = [
        *forced_world_paths,
        *manual.get("extra_world_paths", []),
    ]

    return {
        "role_name": role_name,
        "extra_role_paths": manual.get("extra_role_paths", []),
        "extra_world_paths": manual.get("extra_world_paths", []),
        "region_overrides": manual.get("region_overrides", []),
        "allowed_story_paths": manual.get("allowed_story_paths", []),
        "allowed_story_premises": manual.get("allowed_story_premises", []),
        "allowed_story_segments": manual.get("allowed_story_segments", []),
        "notes": manual.get("notes", ""),
        "role_info": role_info,
        "forced_role_paths": forced_role_paths,
        "forced_world_paths": forced_world_paths,
        "forced_region_layers": forced_region_layers,
        "allowed_role_paths": final_role_paths,
        "allowed_world_paths": final_world_paths,
        "allowed_story_paths": manual.get("allowed_story_paths", []),
        "allowed_region_layers": forced_region_layers,
    }


def generate_all_role_permissions(
    role_infos: list[dict] | None = None,
    permissions_dir: Path = PERMISSIONS_DIR,
) -> list[dict]:
    ensure_default_files()
    if role_infos is None:
        if ROLE_INFO_OUTPUT.exists():
            role_infos = load_json(ROLE_INFO_OUTPUT, [])
        else:
            role_infos = extract_all_role_infos()
            save_role_infos(role_infos)

    org_region_mapping = load_json(ORG_REGION_MAPPING_PATH, DEFAULT_ORG_REGION_MAPPING)

    permissions_dir.mkdir(parents=True, exist_ok=True)
    permissions: list[dict] = []
    for role_info in role_infos:
        manual_config = load_role_permission_config(role_info["role_name"], permissions_dir=permissions_dir)
        permission = generate_permission_for_role(role_info, org_region_mapping, manual_config)
        permissions.append(permission)
        permission_file_path(role_info["role_name"], permissions_dir=permissions_dir).write_text(
            json.dumps(permission, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return permissions


def main() -> None:
    permissions = generate_all_role_permissions()
    print(f"generated permissions for {len(permissions)} roles into {PERMISSIONS_DIR}")


if __name__ == "__main__":
    main()
