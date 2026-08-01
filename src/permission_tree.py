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
from src.build_metadata import story_block_text


RAW_ROOT = Path("data/raw")
PERMISSION_MANUAL_FIELDS = [
    "extra_role_paths",
    "extra_world_paths",
    "region_overrides",
    "allowed_story_paths",
    "allowed_story_premises",
    "allowed_story_segments",
    "notes",
]
STORY_ROOT_NAMES = {"主线", "支线"}
PERMISSION_TREE_TEXT_SUFFIXES = {".txt"}


def is_permission_tree_file(path: Path) -> bool:
    if not path.is_file() or path.name.startswith("~$"):
        return False
    return path.suffix.lower() in PERMISSION_TREE_TEXT_SUFFIXES or path.name.lower().endswith(".editor.json")


def build_tree(path: Path, root: Path) -> dict[str, Any]:
    relative = path.relative_to(root).as_posix() if path != root else ""
    if path.is_file():
        return {
            "name": path.name,
            "path": relative,
            "node_type": "file",
        }

    children = sorted(
        [
            child
            for child in path.iterdir()
            if child.is_dir() or is_permission_tree_file(child)
        ],
        key=lambda item: (item.is_file(), item.name),
    )
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
            "allowed_story_premises": [],
            "allowed_story_segments": [],
            "notes": "",
        }

    permission = json.loads(path.read_text(encoding="utf-8-sig"))
    permission["role_name"] = permission.get("role_name") or role_name
    permission.setdefault("extra_role_paths", [])
    permission.setdefault("extra_world_paths", [])
    permission.setdefault("region_overrides", [])
    permission.setdefault("allowed_story_paths", [])
    permission.setdefault("allowed_story_premises", [])
    permission.setdefault("allowed_story_segments", [])
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


def normalize_story_premise_specs(values: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    if not isinstance(values, list):
        return normalized
    for item in values:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).replace("\\", "/").strip("/")
        premise_type = str(item.get("premise_type", "")).strip()
        try:
            block_index = int(item.get("block_index"))
        except (TypeError, ValueError):
            continue
        if not path or premise_type not in {"chapter_summary", "paragraph_summary"}:
            continue
        key = (path, premise_type, block_index)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"path": path, "premise_type": premise_type, "block_index": block_index})
    return sorted(normalized, key=lambda spec: (spec["path"], spec["premise_type"], spec["block_index"]))


def normalize_story_segment_specs(values: Any) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, int]] = set()
    if not isinstance(values, list):
        return normalized
    for item in values:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).replace("\\", "/").strip("/")
        premise_type = str(item.get("premise_type", "paragraph_summary")).strip() or "paragraph_summary"
        try:
            block_index = int(item.get("block_index"))
            aggregate_start = int(item.get("aggregate_start"))
            aggregate_end = int(item.get("aggregate_end"))
        except (TypeError, ValueError):
            continue
        if premise_type != "paragraph_summary" or not path or aggregate_start < 0 or aggregate_end < aggregate_start:
            continue
        key = (path, block_index, aggregate_start, aggregate_end)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "path": path,
                "premise_type": "paragraph_summary",
                "block_index": block_index,
                "aggregate_start": aggregate_start,
                "aggregate_end": aggregate_end,
            }
        )
    return sorted(normalized, key=lambda spec: (spec["path"], spec["block_index"], spec["aggregate_start"], spec["aggregate_end"]))


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
    manual["allowed_story_premises"] = normalize_story_premise_specs(manual.get("allowed_story_premises", []))
    manual["allowed_story_segments"] = normalize_story_segment_specs(manual.get("allowed_story_segments", []))
    manual["allowed_story_premises"] = normalize_story_premise_specs(
        [
            *manual["allowed_story_premises"],
            *[
                {
                    "path": segment["path"],
                    "premise_type": "paragraph_summary",
                    "block_index": segment["block_index"],
                }
                for segment in manual["allowed_story_segments"]
            ],
        ]
    )

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


def story_txt_path_for_editor_json(editor_path: Path, raw_root: Path = RAW_ROOT) -> str:
    return editor_path.relative_to(raw_root).as_posix()[: -len(".editor.json")] + ".txt"


def story_summary_title(path: str) -> str:
    return Path(path).name.removesuffix(".txt").removesuffix(".editor.json")


def paragraph_summary_ranges(blocks: list[dict[str, Any]]) -> dict[int, tuple[int, int]]:
    def excluded_from_boundary(block_index: int, block: dict[str, Any]) -> bool:
        block_type = str(block.get("type", "")).strip()
        return block_type in {"chapter_summary", "chapter_note"} or (block_type == "analysis" and block_index == 0)

    markers = [
        index
        for index, block in enumerate(blocks)
        if str(block.get("type", "")).strip() in {"summary", "paragraph_summary"}
    ]
    non_excluded = [
        index
        for index, block in enumerate(blocks)
        if not excluded_from_boundary(index, block) and story_block_text(block)
    ]
    if not markers or not non_excluded:
        return {}

    ranges: dict[int, tuple[int, int]] = {}
    prefix_start_candidates = [index for index in non_excluded if index <= markers[0]]
    if prefix_start_candidates:
        ranges[markers[0]] = (prefix_start_candidates[0], markers[0])
    for previous, current in zip(markers, markers[1:]):
        if previous + 1 <= current:
            ranges[current] = (previous + 1, current)
    return ranges


def source_order_range(blocks: list[dict[str, Any]], start: int, end: int) -> tuple[int | None, int | None]:
    source_orders: list[int] = []
    for block in blocks[start : end + 1]:
        block_type = str(block.get("type", "")).strip()
        if block_type in {"summary", "paragraph_summary"}:
            continue
        meta = block.get("meta") if isinstance(block.get("meta"), dict) else {}
        source_order = meta.get("source_order")
        try:
            source_orders.append(int(source_order))
        except (TypeError, ValueError):
            continue
    if not source_orders:
        return None, None
    return min(source_orders), max(source_orders)


def extract_story_summaries_from_document(relative_txt_path: str, document: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    paragraph_index = 0
    blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
    summary_ranges = paragraph_summary_ranges(blocks)
    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type", "")).strip()
        if block_type not in {"chapter_summary", "paragraph_summary"}:
            continue
        text = str(block.get("text", "")).strip()
        if not text:
            continue
        label = "本章梗概" if block_type == "chapter_summary" else f"段落梗概{paragraph_index + 1}"
        if block_type == "paragraph_summary":
            paragraph_index += 1
        source_order = (block.get("meta") or {}).get("source_order") if isinstance(block.get("meta"), dict) else None
        item = {
            "id": f"{relative_txt_path}::{block_type}::{block_index}",
            "path": relative_txt_path,
            "premise_type": block_type,
            "block_index": block_index,
            "source_order": source_order,
            "label": label,
            "text": text,
        }
        if block_type == "paragraph_summary" and block_index in summary_ranges:
            aggregate_start, aggregate_end = summary_ranges[block_index]
            item["aggregate_start"] = aggregate_start
            item["aggregate_end"] = aggregate_end
            source_order_start, source_order_end = source_order_range(blocks, aggregate_start, aggregate_end)
            item["source_order_start"] = source_order_start
            item["source_order_end"] = source_order_end
        items.append(item)
    return items


def build_story_summary_index(raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    stories: list[dict[str, Any]] = []
    for editor_path in sorted(raw_root.rglob("*.editor.json")):
        relative_parts = editor_path.relative_to(raw_root).parts
        if not relative_parts or relative_parts[0] not in STORY_ROOT_NAMES:
            continue
        try:
            document = json.loads(editor_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        relative_txt_path = story_txt_path_for_editor_json(editor_path, raw_root=raw_root)
        summaries = extract_story_summaries_from_document(relative_txt_path, document)
        if summaries:
            stories.append(
                {
                    "path": relative_txt_path,
                    "editor_path": editor_path.relative_to(raw_root).as_posix(),
                    "title": story_summary_title(relative_txt_path),
                    "summaries": summaries,
                }
            )
    return {"stories": stories}


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
    raw_root_resolved = raw_root.resolve()
    clean_name = folder_name.strip()
    if not clean_name:
        raise ValueError("folder name is empty")
    target = parent / clean_name
    if target.exists():
        raise FileExistsError(target.name)
    target.mkdir(parents=False, exist_ok=False)
    return {
        "path": target.relative_to(raw_root_resolved).as_posix(),
        "name": target.name,
        "node_type": "folder",
    }


def create_raw_txt_file(
    parent_path: str,
    file_name: str,
    content: str = "",
    raw_root: Path = RAW_ROOT,
) -> dict[str, Any]:
    parent = ensure_manageable_parent(parent_path, raw_root=raw_root)
    raw_root_resolved = raw_root.resolve()
    clean_name = file_name.strip()
    if not clean_name:
        raise ValueError("file name is empty")
    if not clean_name.lower().endswith(".txt"):
        clean_name = f"{clean_name}.txt"
    target = parent / clean_name
    if target.exists():
        if target.is_file():
            return {
                "path": target.relative_to(raw_root_resolved).as_posix(),
                "name": target.name,
                "node_type": "file",
                "existed": True,
            }
        raise FileExistsError(target.name)
    target.write_text(content, encoding="utf-8")
    return {
        "path": target.relative_to(raw_root_resolved).as_posix(),
        "name": target.name,
        "node_type": "file",
        "existed": False,
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
