from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from src.generate_role_permissions import (
    PERMISSIONS_DIR,
    ROLE_ROOT,
    WORLD_GLOBAL_ROOT,
    default_role_permission_template,
    generate_permission_for_role,
    load_org_region_mapping,
    permission_file_path,
)


RAW_ROOT = Path("data/raw")
PERMISSION_MANUAL_FIELDS = [
    "extra_role_paths",
    "extra_world_paths",
    "region_overrides",
    "allowed_story_paths",
    "notes",
]


def build_tree(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix() if path != root else ""
    if path.is_file():
        return {
            "name": path.name,
            "path": relative,
            "node_type": "file",
        }

    children = sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name))
    return {
        "name": path.name if relative else root.name,
        "path": relative,
        "node_type": "folder",
        "children": [build_tree(child, root) for child in children],
    }


def build_folder_only_tree(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix() if path != root else ""
    children = sorted(
        [
            child
            for child in path.iterdir()
            if child.is_dir() and child.name != "地区探索报告"
        ],
        key=lambda item: item.name,
    )
    return {
        "name": path.name if relative else root.name,
        "path": relative,
        "node_type": "folder",
        "children": [build_folder_only_tree(child, root) for child in children],
    }


def build_permission_forest(raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    return {
        "角色": build_tree(raw_root / "角色", raw_root),
        "世界观": build_tree(raw_root / "世界观", raw_root),
        "主线": build_tree(raw_root / "主线", raw_root),
        "支线": build_tree(raw_root / "支线", raw_root),
    }


def build_region_tree(raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    return build_folder_only_tree(raw_root / "世界观" / "地区信息", raw_root)


def flatten_folder_paths(node: dict[str, Any]) -> list[str]:
    results: list[str] = []
    if node.get("node_type") == "folder" and node.get("path"):
        results.append(node["path"].replace("世界观/地区信息/", "", 1))
    for child in node.get("children", []):
        results.extend(flatten_folder_paths(child))
    return results


def list_permission_roles(permissions_dir: Path = PERMISSIONS_DIR) -> list[str]:
    return sorted(
        path.stem for path in permissions_dir.glob("*.json") if path.name != "org_region_mapping.json"
    )


def load_role_permission(role_name: str, permissions_dir: Path = PERMISSIONS_DIR) -> dict[str, Any]:
    path = permission_file_path(role_name, permissions_dir)
    if not path.exists():
        return {
            "role_name": role_name,
            "extra_role_paths": [],
            "extra_world_paths": [],
            "region_overrides": [],
            "allowed_story_paths": [],
            "notes": "",
        }

    permission = json.loads(path.read_text(encoding="utf-8-sig"))
    permission["role_name"] = permission.get("role_name") or role_name
    permission.setdefault("extra_role_paths", [])
    permission.setdefault("extra_world_paths", [])
    permission.setdefault("region_overrides", [])
    permission.setdefault("allowed_story_paths", [])
    permission.setdefault("notes", "")
    permission.setdefault("forced_role_paths", [f"{ROLE_ROOT}/{role_name}"])
    permission.setdefault("forced_world_paths", [WORLD_GLOBAL_ROOT])
    permission.setdefault("forced_region_layers", [])
    permission.setdefault(
        "allowed_role_paths",
        [*permission["forced_role_paths"], *permission["extra_role_paths"]],
    )
    permission.setdefault(
        "allowed_world_paths",
        [*permission["forced_world_paths"], *permission["extra_world_paths"]],
    )
    permission.setdefault("allowed_region_layers", permission["forced_region_layers"])
    return permission


def save_role_permission(
    role_name: str,
    payload: dict[str, Any],
    permissions_dir: Path = PERMISSIONS_DIR,
) -> Path:
    existing = load_role_permission(role_name, permissions_dir)
    manual = default_role_permission_template(role_name)
    manual.update(existing)
    manual["role_name"] = role_name
    for field in PERMISSION_MANUAL_FIELDS:
        if field in payload:
            manual[field] = payload[field]

    role_info = existing.get("role_info")
    if role_info:
        updated = generate_permission_for_role(
            role_info=role_info,
            org_region_mapping=load_org_region_mapping(),
            manual_config=manual,
        )
    else:
        updated = dict(existing)
        updated.update(manual)
        forced_role_paths = updated.get("forced_role_paths") or [f"{ROLE_ROOT}/{role_name}"]
        forced_world_paths = updated.get("forced_world_paths") or [WORLD_GLOBAL_ROOT]
        updated["forced_role_paths"] = forced_role_paths
        updated["forced_world_paths"] = forced_world_paths
        updated["allowed_role_paths"] = [*forced_role_paths, *updated.get("extra_role_paths", [])]
        updated["allowed_world_paths"] = [*forced_world_paths, *updated.get("extra_world_paths", [])]
        updated["allowed_region_layers"] = updated.get("forced_region_layers", [])

    path = permission_file_path(role_name, permissions_dir)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def extract_forced_specs(permission: dict[str, Any]) -> dict[str, list[str]]:
    return {
        "role": permission.get("forced_role_paths", []),
        "world": permission.get("forced_world_paths", []),
        "story": permission.get("forced_story_paths", []),
    }


def resolve_raw_txt_path(relative_path: str, raw_root: Path = RAW_ROOT) -> Path:
    candidate = (raw_root / relative_path).resolve()
    raw_root_resolved = raw_root.resolve()
    if raw_root_resolved not in candidate.parents and candidate != raw_root_resolved:
        raise ValueError("path out of raw root")
    if candidate.suffix.lower() != ".txt":
        raise ValueError("only txt preview is supported")
    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def read_raw_txt_preview(relative_path: str, raw_root: Path = RAW_ROOT) -> dict[str, str]:
    path = resolve_raw_txt_path(relative_path, raw_root=raw_root)
    return {
        "path": relative_path,
        "content": path.read_text(encoding="utf-8"),
    }


def resolve_raw_path(relative_path: str, raw_root: Path = RAW_ROOT) -> Path:
    candidate = (raw_root / relative_path).resolve()
    raw_root_resolved = raw_root.resolve()
    if raw_root_resolved not in candidate.parents and candidate != raw_root_resolved:
        raise ValueError("path out of raw root")
    return candidate


def ensure_manageable_parent(parent_path: str, raw_root: Path = RAW_ROOT) -> Path:
    parent = resolve_raw_path(parent_path, raw_root=raw_root)
    if not parent.exists() or not parent.is_dir():
        raise FileNotFoundError(parent_path)
    return parent


def create_raw_folder(parent_path: str, folder_name: str, raw_root: Path = RAW_ROOT) -> dict[str, str]:
    parent = ensure_manageable_parent(parent_path, raw_root=raw_root)
    clean_name = folder_name.strip()
    if not clean_name:
        raise ValueError("folder name is empty")
    target = parent / clean_name
    if target.exists():
        raise FileExistsError(target.name)
    target.mkdir(parents=False, exist_ok=False)
    return {
        "path": target.relative_to(raw_root).as_posix(),
        "name": target.name,
        "node_type": "folder",
    }


def create_raw_txt_file(
    parent_path: str,
    file_name: str,
    content: str = "",
    raw_root: Path = RAW_ROOT,
) -> dict[str, str]:
    parent = ensure_manageable_parent(parent_path, raw_root=raw_root)
    clean_name = file_name.strip()
    if not clean_name:
        raise ValueError("file name is empty")
    if not clean_name.lower().endswith(".txt"):
        clean_name = f"{clean_name}.txt"
    target = parent / clean_name
    if target.exists():
        raise FileExistsError(target.name)
    target.write_text(content, encoding="utf-8")
    return {
        "path": target.relative_to(raw_root).as_posix(),
        "name": target.name,
        "node_type": "file",
    }


def delete_raw_path(relative_path: str, raw_root: Path = RAW_ROOT) -> dict[str, str]:
    target = resolve_raw_path(relative_path, raw_root=raw_root)
    if target == raw_root.resolve():
        raise ValueError("cannot delete raw root")
    if not target.exists():
        raise FileNotFoundError(relative_path)
    node_type = "folder" if target.is_dir() else "file"
    if target.is_dir():
        if any(target.iterdir()):
            raise ValueError("folder is not empty")
        target.rmdir()
    else:
        target.unlink()
    return {
        "path": relative_path,
        "node_type": node_type,
    }


def open_raw_txt_in_notepad(relative_path: str, raw_root: Path = RAW_ROOT) -> dict[str, str]:
    path = resolve_raw_txt_path(relative_path, raw_root=raw_root)
    subprocess.Popen(["notepad.exe", str(path)])
    return {
        "path": relative_path,
        "status": "opened",
    }
