from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

STATIC_DIR = Path(__file__).with_name("static")
RAW_ROOT = Path("data/raw")
WORLD_ROOT_NAME = "\u4e16\u754c\u89c2"
DEFAULT_BRANCH_SPEAKER = "漂泊者"
TEXT_BLOCK_TYPES = {
    "scene_cast",
    "narration",
    "line",
    "summary",
    "chapter_summary",
    "paragraph_summary",
    "text_title",
    "text_body",
    "analysis",
    "chapter_note",
    "note",
}
ANNOTATABLE_BLOCK_TYPES = set(TEXT_BLOCK_TYPES)
NON_DIALOGUE_SPEECH_MODE = "non_dialogue"
REGION_REPORT_FOLDER_NAME = "\u5730\u533a\u63a2\u7d22\u62a5\u544a"
TITLE_PREFIX = "\u3010\u6587\u6863\u6807\u9898\uff1a"
SCENE_PREFIX = "\u3010\u65f6\u95f4&\u5730\u70b9&\u4eba\u7269\uff1a"
LEGACY_SCENE_CAST_PREFIX = "\u3010\u573a\u666f&\u4eba\u7269\uff1a"
LEGACY_SCENE_PREFIX = "\u3010\u573a\u666f\uff06\u4eba\u7269\uff1a"
NARRATION_PREFIX = "\u3010\u65c1\u767d\uff1a"
SUMMARY_PREFIX = "\u3010\u5267\u60c5\u6897\u6982\uff1a"
CHAPTER_SUMMARY_PREFIX = "\u3010\u672c\u7ae0\u6897\u6982\uff1a"
PARAGRAPH_SUMMARY_PREFIX = "\u3010\u6bb5\u843d\u6897\u6982\uff1a"
TEXT_TITLE_PREFIX = "\u3010\u6807\u9898\uff1a"
TEXT_BODY_PREFIX = "\u3010\u6b63\u6587\uff1a"
ANALYSIS_PREFIX = "\u3010\u89e3\u6790\uff1a"
CHAPTER_NOTE_PREFIX = "\u3010\u672c\u7ae0\u6ce8\u91ca\uff1a"
NOTE_PREFIX = "\u3010\u6ce8\u91ca\uff1a"
NON_DIALOGUE_PREFIX = "\u3010\u975e\u5bf9\u8bdd\u683c\u5f0f\u53d1\u8a00\u3011"
OPTION_START = "\u2192"
OPTION_NEXT = "\u2190\u2192"
OPTION_END = "\u2190"
BLOCK_TYPE_LABELS = {
    "scene_cast": "时间&地点&人物",
    "narration": "旁白",
    "line": "台词",
    "branch": "分支选项",
    "summary": "段落梗概",
    "chapter_summary": "本章梗概",
    "paragraph_summary": "段落梗概",
    "text_title": "文本标题",
    "text_body": "文本正文",
    "analysis": "注释",
    "chapter_note": "本章注释",
    "note": "注释",
}
BLOCK_TYPE_ALIASES = {
    "scene_title": "scene_cast",
    "scene_cast": "scene_cast",
    "dialogue": "line",
    "line": "line",
    "branch": "branch",
    "summary": "summary",
    "chapter_summary": "chapter_summary",
    "paragraph_summary": "paragraph_summary",
    "heading": "text_title",
    "narration": "narration",
    "narration_small": "narration",
    "supplement": "analysis",
    "analysis": "analysis",
    "chapter_note": "chapter_note",
    "note": "note",
    "body": "text_body",
    "body_text": "text_body",
    "text_title": "text_title",
    "text_body": "text_body",
}
LEGACY_BLOCK_TYPE_ALIASES = {
    **BLOCK_TYPE_ALIASES,
    "narration": "text_title",
}


def editor_sidecar_path(txt_path: Path) -> Path:
    return txt_path.with_suffix(".editor.json")


def editor_json_to_txt_path(editor_json_path: Path) -> Path:
    if not editor_json_path.name.endswith(".editor.json"):
        raise ValueError("not an editor json path")
    return editor_json_path.with_name(editor_json_path.name[: -len(".editor.json")] + ".txt")


def ensure_within_root(candidate: Path, raw_root: Path) -> Path:
    candidate = candidate.resolve()
    raw_root_resolved = raw_root.resolve()
    if candidate != raw_root_resolved and raw_root_resolved not in candidate.parents:
        raise ValueError("path out of raw root")
    return candidate


def resolve_editor_source_path(relative_path: str, raw_root: Path = RAW_ROOT) -> tuple[Path, str]:
    candidate = ensure_within_root(raw_root / relative_path, raw_root)
    name = candidate.name.lower()
    if name.endswith(".editor.json"):
        return candidate, "editor_json"
    raise ValueError("editor only supports .editor.json files")


def new_id(prefix: str = "blk") -> str:
    return f"{prefix}_{uuid4().hex[:8]}"


def default_annotations() -> dict[str, Any]:
    return {"manual_refs": [], "omissions": [], "settings": []}



def normalize_style(value: Any, *, legacy_italic: Any = False) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    italic = bool(data.get("italic", legacy_italic))
    speech_mode = str(data.get("speech_mode", "")).strip()
    if italic and not speech_mode:
        speech_mode = NON_DIALOGUE_SPEECH_MODE
    return {
        "italic": italic,
        "speech_mode": speech_mode if speech_mode == NON_DIALOGUE_SPEECH_MODE else "",
    }



def normalize_block_type(value: Any, *, legacy: bool = False) -> str:
    key = str(value or "").strip()
    aliases = LEGACY_BLOCK_TYPE_ALIASES if legacy else BLOCK_TYPE_ALIASES
    return aliases.get(key, key)



def is_region_report_path(relative_path: str) -> bool:
    return REGION_REPORT_FOLDER_NAME in str(relative_path or "").replace("\\", "/").split("/")



def normalize_annotation_refs(values: Any) -> list[str]:
    refs: list[str] = []
    for value in values or []:
        term = str(value or "").strip()
        if term and term not in refs:
            refs.append(term)
    return refs



def normalize_annotation_omissions(values: Any) -> list[dict[str, int | str]]:
    normalized: list[dict[str, int | str]] = []
    seen: set[tuple[str, int, int]] = set()
    for value in values or []:
        if not isinstance(value, dict):
            continue
        term = str(value.get("term", "")).strip()
        start = value.get("start")
        end = value.get("end")
        if not term or not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            continue
        key = (term, start, end)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"term": term, "start": start, "end": end})
    return normalized



def normalize_annotations(value: Any, *, legacy_refs: Any = None, legacy_omissions: Any = None) -> dict[str, Any]:
    data = value if isinstance(value, dict) else {}
    refs = normalize_annotation_refs(data.get("manual_refs", legacy_refs or []))
    omissions = normalize_annotation_omissions(data.get("omissions", legacy_omissions or []))
    settings: list[dict[str, Any]] = []
    seen_settings: set[tuple[str, str, int, int]] = set()
    for item in data.get("settings", []) or []:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term", "")).strip()
        source_id = str(item.get("source_id", "")).strip()
        start = item.get("start")
        end = item.get("end")
        if not term or not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
            continue
        key = (term, source_id, start, end)
        if key in seen_settings:
            continue
        seen_settings.add(key)
        settings.append({"term": term, "source_id": source_id, "start": start, "end": end})
    return {"manual_refs": refs, "omissions": omissions, "settings": settings}



def create_block(block_type: str) -> dict[str, Any]:
    block_type = normalize_block_type(block_type)
    if block_type == "line":
        return {
            "id": new_id(),
            "type": "line",
            "speaker": "",
            "text": "",
            "annotations": default_annotations(),
            "style": normalize_style(None),
        }
    if block_type == "branch":
        return {
            "id": new_id(),
            "type": "branch",
            "speaker": DEFAULT_BRANCH_SPEAKER,
            "options": [create_option()],
        }
    return {
        "id": new_id(),
        "type": block_type,
        "text": "",
        "annotations": default_annotations(),
        "style": normalize_style(None),
    }



def create_option() -> dict[str, Any]:
    return {
        "id": new_id("opt"),
        "label": "",
        "annotations": default_annotations(),
        "children": [],
    }


def parse_line_text(line: str) -> tuple[str, str] | None:
    if "\uff1a" in line:
        speaker, content = line.split("\uff1a", 1)
    elif ":" in line:
        speaker, content = line.split(":", 1)
    else:
        return None
    speaker = speaker.strip()
    content = content.strip()
    if not speaker or not content:
        return None
    return speaker, content


def strip_wrapped(prefix: str, text: str) -> str | None:
    if text.startswith(prefix) and text.endswith("\u3011"):
        return text[len(prefix) : -1].strip()
    return None


def legacy_text_to_blocks_v2(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped:
            blocks.append(parse_txt_line_to_block(stripped))
    return blocks


def parse_txt_line_to_block(stripped: str) -> dict[str, Any]:
    style = normalize_style(None)
    if stripped.startswith(NON_DIALOGUE_PREFIX):
        stripped = stripped[len(NON_DIALOGUE_PREFIX) :].strip()
        style = normalize_style({"italic": True, "speech_mode": NON_DIALOGUE_SPEECH_MODE})

    for prefix, block_type in (
        (SCENE_PREFIX, "scene_cast"),
        (LEGACY_SCENE_CAST_PREFIX, "scene_cast"),
        (LEGACY_SCENE_PREFIX, "scene_cast"),
        (NARRATION_PREFIX, "narration"),
        (SUMMARY_PREFIX, "summary"),
        (CHAPTER_SUMMARY_PREFIX, "chapter_summary"),
        (PARAGRAPH_SUMMARY_PREFIX, "paragraph_summary"),
        (TEXT_TITLE_PREFIX, "text_title"),
        (TEXT_BODY_PREFIX, "text_body"),
        (ANALYSIS_PREFIX, "analysis"),
        (CHAPTER_NOTE_PREFIX, "chapter_note"),
        (NOTE_PREFIX, "note"),
    ):
        text = strip_wrapped(prefix, stripped)
        if text is not None:
            item = create_block(block_type)
            item["text"] = text
            item["style"] = style
            return item

    if stripped.startswith("\u3010") and stripped.endswith("\u3011"):
        item = create_block("narration")
        item["text"] = stripped[1:-1].strip()
        item["style"] = style
        return item

    parsed = parse_line_text(stripped)
    if parsed:
        speaker, text = parsed
        item = create_block("line")
        item["speaker"] = speaker
        item["text"] = text
        item["style"] = style
        return item

    item = create_block("text_title")
    item["text"] = stripped
    item["style"] = style
    return item


def parse_txt_to_document(relative_path: str, content: str) -> dict[str, Any]:
    document = default_document(relative_path)
    lines = content.replace("\r\n", "\n").split("\n")
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        title = strip_wrapped(TITLE_PREFIX, stripped)
        if title is not None:
            document["title"] = title
            index += 1
            continue
        if stripped == OPTION_START:
            branch = create_block("branch")
            branch["options"] = []
            index += 1
            current_option: dict[str, Any] | None = None
            response_lines: list[str] = []
            while index < len(lines):
                marker = lines[index].strip()
                if marker in {OPTION_NEXT, OPTION_END}:
                    if current_option is not None:
                        current_option["children"] = legacy_text_to_blocks_v2("\n".join(response_lines))
                        branch["options"].append(current_option)
                    current_option = None
                    response_lines = []
                    index += 1
                    if marker == OPTION_END:
                        break
                    continue
                if current_option is None:
                    current_option = create_option()
                    parsed = parse_line_text(marker)
                    if parsed:
                        speaker, label = parsed
                        branch["speaker"] = speaker
                        current_option["label"] = label
                    else:
                        current_option["label"] = marker
                else:
                    response_lines.append(lines[index].rstrip())
                index += 1
            branch["options"] = branch["options"] or [create_option()]
            document["blocks"].append(branch)
            continue
        document["blocks"].append(parse_txt_line_to_block(stripped))
        index += 1
    return document



def default_document(relative_path: str) -> dict[str, Any]:
    name = Path(relative_path).name
    if name.endswith(".editor.json"):
        title = name[:-len(".editor.json")]
    else:
        title = Path(relative_path).stem
    doc_type = "annotation" if str(relative_path).replace("\\", "/").startswith(f"{WORLD_ROOT_NAME}/") else "story"
    return {
        "version": 4,
        "path": relative_path,
        "title": title,
        "doc_type": doc_type,
        "meta": {"source": "editor_v2", "export_txt": False},
        "blocks": [],
    }



def normalize_option(option: Any, *, legacy: bool = False) -> dict[str, Any]:
    data = option if isinstance(option, dict) else {}
    children = [normalize_block(item, legacy=legacy) for item in (data.get("children") or data.get("response_blocks") or [])]
    return {
        "id": str(data.get("id") or new_id("opt")),
        "label": str(data.get("label", "")),
        "annotations": normalize_annotations(
            data.get("annotations"),
            legacy_refs=data.get("annotation_refs"),
            legacy_omissions=data.get("annotation_omissions"),
        ),
        "children": [item for item in children if item],
    }



def normalize_block(block: Any, *, legacy: bool = False) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        return None
    block_type = normalize_block_type(block.get("type"), legacy=legacy)
    if not block_type:
        return None
    if block_type == "branch":
        options = [normalize_option(item, legacy=legacy) for item in block.get("options", [])]
        return {
            "id": str(block.get("id") or new_id()),
            "type": "branch",
            "speaker": str(block.get("speaker") or block.get("option_speaker") or DEFAULT_BRANCH_SPEAKER),
            "options": options or [create_option()],
        }

    normalized = {
        "id": str(block.get("id") or new_id()),
        "type": block_type,
        "annotations": normalize_annotations(
            block.get("annotations"),
            legacy_refs=block.get("annotation_refs"),
            legacy_omissions=block.get("annotation_omissions"),
        ),
        "style": normalize_style(block.get("style"), legacy_italic=block.get("italic", False)),
    }
    if block_type == "line":
        normalized["speaker"] = str(block.get("speaker", ""))
        normalized["text"] = str(block.get("text", ""))
        return normalized

    normalized["text"] = str(block.get("text", ""))
    return normalized



def normalize_document(document: Any, relative_path: str) -> dict[str, Any]:
    default = default_document(relative_path)
    data = document if isinstance(document, dict) else {}
    try:
        version = int(data.get("version") or 0)
    except (TypeError, ValueError):
        version = 0
    meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
    legacy = version < 4 and meta.get("source") != "editor_v2"
    blocks = [normalize_block(item, legacy=legacy) for item in data.get("blocks", [])]
    result = {
        "version": 4,
        "path": relative_path,
        "title": str(data.get("title", default["title"])).strip() or default["title"],
        "doc_type": str(data.get("doc_type", default["doc_type"])).strip() or default["doc_type"],
        "meta": data.get("meta") if isinstance(data.get("meta"), dict) else default["meta"],
        "blocks": [item for item in blocks if item],
    }
    return result



def safe_document_basename(title: str, fallback: str) -> str:
    """Convert a document title into one safe Windows filename stem."""
    replacements = {
        "<": "\uff1c",
        ">": "\uff1e",
        ":": "\uff1a",
        '"': "\uff02",
        "/": "\uff0f",
        "\\": "\uff3c",
        "|": "\uff5c",
        "?": "\uff1f",
        "*": "\uff0a",
    }
    value = "".join(replacements.get(char, char) for char in str(title or ""))
    value = "".join(" " if ord(char) < 32 else char for char in value).strip(" .")
    if not value:
        value = str(fallback or "untitled").strip(" .") or "untitled"
    if value.upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"}:
        value = f"{value}_"
    return value



def document_target_paths(source_path: Path, source_kind: str, document: dict[str, Any], raw_root: Path) -> tuple[Path, Path, str]:
    fallback = source_path.name[:-len(".editor.json")] if source_path.name.endswith(".editor.json") else source_path.stem
    basename = safe_document_basename(str(document.get("title", "")).strip(), fallback)
    if source_kind == "editor_json":
        editor_json_path = ensure_within_root(source_path.with_name(f"{basename}.editor.json"), raw_root)
        txt_path = editor_json_to_txt_path(editor_json_path)
        relative_path = editor_json_path.relative_to(raw_root.resolve()).as_posix()
    else:
        txt_path = ensure_within_root(source_path.with_name(f"{basename}.txt"), raw_root)
        editor_json_path = editor_sidecar_path(txt_path)
        relative_path = txt_path.relative_to(raw_root.resolve()).as_posix()
    return editor_json_path, txt_path, relative_path



def assert_can_write_editor_targets(targets: list[Path], owned_paths: list[Path]) -> None:
    owned = {path.resolve() for path in owned_paths if path.exists()}
    for target in targets:
        resolved = target.resolve()
        if target.exists() and resolved not in owned:
            raise FileExistsError(str(target))



def remove_old_editor_files(paths: list[Path], keep_paths: list[Path]) -> None:
    keep = {path.resolve() for path in keep_paths}
    for path in paths:
        if path.exists() and path.resolve() not in keep:
            path.unlink()



def _block_to_txt_lines_plain(block: dict[str, Any]) -> list[str]:
    block_type = normalize_block_type(block.get("type"))
    text = str(block.get("text", "")).strip()
    if block_type == "scene_cast":
        return [f"【时间&地点&人物：{text}】", ""] if text else []
    if block_type == "narration":
        return [f"[旁白]{text}"] if text else []
    if block_type == "summary":
        return [f"[段落梗概]{text}"] if text else []
    if block_type == "chapter_summary":
        return [f"[本章梗概]{text}"] if text else []
    if block_type == "paragraph_summary":
        return [f"[段落梗概]{text}"] if text else []
    if block_type == "text_title":
        return [f"【标题：{text}】"] if text else []
    if block_type == "text_body":
        return [f"【正文：{text}】"] if text else []
    if block_type == "analysis":
        return [f"[注释]{text}"] if text else []
    if block_type == "chapter_note":
        return [f"【本章注释：{text}】"] if text else []
    if block_type == "note":
        return [f"[注释]{text}"] if text else []
    if block_type == "line":
        speaker = str(block.get("speaker", "")).strip()
        if speaker and text:
            return [f"{speaker}：{text}"]
        return [text] if text else []
    if block_type == "branch":
        lines: list[str] = []
        speaker = str(block.get("speaker") or DEFAULT_BRANCH_SPEAKER).strip() or DEFAULT_BRANCH_SPEAKER
        options = block.get("options", [])
        if not options:
            return []
        for index, option in enumerate(options):
            lines.append("→" if index == 0 else "←→")
            label = str(option.get("label", "")).strip()
            if label:
                lines.append(f"{speaker}：{label}")
            for child in option.get("children", []):
                child_lines = block_to_txt_lines(child)
                if child_lines:
                    lines.append(f"[分支后续]{child_lines[0]}")
                    lines.extend(child_lines[1:])
        lines.append("←")
        return lines
    return []



def block_to_txt_lines(block: dict[str, Any]) -> list[str]:
    lines = _block_to_txt_lines_plain(block)
    block_type = normalize_block_type(block.get("type"))
    if block_type not in {"narration", "text_title", "text_body", "analysis", "chapter_note", "note"}:
        return lines
    style = normalize_style(block.get("style"), legacy_italic=block.get("italic", False))
    if style.get("speech_mode") != NON_DIALOGUE_SPEECH_MODE or not lines:
        return lines
    return [f"【非对话格式发言】{lines[0]}", *lines[1:]]



def compile_document_to_txt(document: dict[str, Any]) -> str:
    lines: list[str] = []
    title = str(document.get("title", "")).strip()
    if title:
        lines.extend([f"【文档标题：{title}】", ""])
    for block in document.get("blocks", []):
        chunk = block_to_txt_lines(block)
        lines.extend(chunk)
        if chunk and lines[-1] != "":
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")



def _legacy_document_from_txt(relative_path: str, source_path: Path) -> dict[str, Any]:
    return parse_txt_to_document(relative_path, source_path.read_text(encoding="utf-8"))



def load_editor_document_v2(relative_path: str, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    source_path, source_kind = resolve_editor_source_path(relative_path, raw_root=raw_root)
    if not source_path.exists():
        raise FileNotFoundError(relative_path)

    if source_kind == "editor_json":
        document = json.loads(source_path.read_text(encoding="utf-8-sig"))
        normalized = normalize_document(document, relative_path)
        return {"path": relative_path, "document": normalized, "compiled_text": compile_document_to_txt(normalized), "source": "editor_json"}

    sidecar = editor_sidecar_path(source_path)
    if sidecar.exists():
        document = json.loads(sidecar.read_text(encoding="utf-8-sig"))
        normalized = normalize_document(document, relative_path)
        return {"path": relative_path, "document": normalized, "compiled_text": compile_document_to_txt(normalized), "source": "sidecar"}

    legacy = _legacy_document_from_txt(relative_path, source_path)
    normalized = normalize_document(legacy, relative_path)
    return {"path": relative_path, "document": normalized, "compiled_text": compile_document_to_txt(normalized), "source": "txt"}



def save_editor_document_v2(relative_path: str, document: dict[str, Any], raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    source_path, source_kind = resolve_editor_source_path(relative_path, raw_root=raw_root)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    target_editor_json_path, target_txt_path, target_relative_path = document_target_paths(source_path, source_kind, document, raw_root)
    old_editor_json_path = source_path if source_kind == "editor_json" else editor_sidecar_path(source_path)
    old_txt_path = editor_json_to_txt_path(source_path) if source_kind == "editor_json" else source_path
    assert_can_write_editor_targets(
        [target_editor_json_path],
        [old_editor_json_path, old_txt_path],
    )

    normalized = normalize_document(document, target_relative_path)
    compiled_text = compile_document_to_txt(normalized)
    payload = json.dumps(normalized, ensure_ascii=False, indent=2)

    target_editor_json_path.write_text(payload, encoding="utf-8")
    remove_old_editor_files([old_editor_json_path, old_txt_path], [target_editor_json_path, target_txt_path])
    return {"path": target_relative_path, "document": normalized, "compiled_text": compiled_text}



def iter_world_documents_v2(raw_root: Path = RAW_ROOT) -> Iterator[tuple[str, dict[str, Any]]]:
    world_root = raw_root / WORLD_ROOT_NAME
    if not world_root.exists():
        return
    seen: set[Path] = set()
    for editor_json_path in world_root.rglob("*.editor.json"):
        relative_path = editor_json_path.relative_to(raw_root).as_posix()
        if is_region_report_path(relative_path):
            continue
        try:
            document = json.loads(editor_json_path.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        seen.add(editor_json_path.with_suffix("").with_suffix(""))
        yield relative_path, normalize_document(document, relative_path)



def _block_text_for_annotation(block: dict[str, Any]) -> str:
    block_type = normalize_block_type(block.get("type"))
    if block_type == "line":
        speaker = str(block.get("speaker", "")).strip()
        text = str(block.get("text", "")).strip()
        return f"{speaker}：{text}" if speaker and text else text
    return str(block.get("text", "")).strip()



def build_world_annotation_library_v2(raw_root: Path = RAW_ROOT) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for relative_path, document in iter_world_documents_v2(raw_root=raw_root):
        file_name = Path(relative_path).name
        term = file_name[:-len(".editor.json")] if file_name.endswith(".editor.json") else Path(relative_path).stem
        title = str(document.get("title", "")).strip() or term
        parts: list[str] = []
        first_meaningful = True
        for block in document.get("blocks", []):
            block_type = normalize_block_type(block.get("type"))
            if block_type == "branch":
                branch_lines: list[str] = []
                speaker = str(block.get("speaker") or DEFAULT_BRANCH_SPEAKER).strip() or DEFAULT_BRANCH_SPEAKER
                for option in block.get("options", []):
                    label = str(option.get("label", "")).strip()
                    if label:
                        branch_lines.append(f"{speaker}：{label}")
                    for child in option.get("children", []):
                        content = _block_text_for_annotation(child)
                        if content:
                            branch_lines.append(content)
                text = "\n".join(branch_lines).strip()
            else:
                text = _block_text_for_annotation(block)
            if not text:
                continue
            if first_meaningful and text == title:
                first_meaningful = False
                continue
            first_meaningful = False
            parts.append(text)
        definition = "\n".join(parts).strip()
        if not term or not definition:
            continue
        key = (term, relative_path)
        if key in seen:
            continue
        seen.add(key)
        entries.append({"term": term, "definition": definition, "source_path": relative_path, "source_title": title})
    entries.sort(key=lambda item: (-len(item["term"]), item["term"], item["source_path"]))
    return entries


def find_world_annotation_entry_v2(term: str, raw_root: Path = RAW_ROOT) -> dict[str, Any] | None:
    target = str(term or "").strip()
    if not target:
        return None
    for entry in build_world_annotation_library_v2(raw_root=raw_root):
        if str(entry.get("term", "")).strip() == target:
            return entry
    return None



def list_world_editor_targets_v2(raw_root: Path = RAW_ROOT) -> list[dict[str, str]]:
    world_root = raw_root / WORLD_ROOT_NAME
    if not world_root.exists():
        return []
    skip_region_report = "地区探索报告"
    region_info_root = f"{WORLD_ROOT_NAME}/地区信息"
    targets: dict[str, dict[str, str]] = {}
    for folder in sorted(path for path in world_root.rglob("*") if path.is_dir()):
        relative_path = folder.relative_to(raw_root).as_posix()
        parts = relative_path.split("/")
        if skip_region_report in parts:
            continue
        if relative_path in {WORLD_ROOT_NAME, region_info_root}:
            continue
        if relative_path.startswith(f"{region_info_root}/"):
            label = relative_path[len(f"{region_info_root}/"):]
        elif relative_path.startswith(f"{WORLD_ROOT_NAME}/"):
            label = relative_path[len(f"{WORLD_ROOT_NAME}/"):]
        else:
            label = relative_path
        if not label:
            continue
        targets[relative_path] = {"path": relative_path, "label": label.replace("/", "——")}
    return [targets[key] for key in sorted(targets.keys())]



def save_world_annotation_entry_v2(
    target_relative_path: str,
    term: str,
    definition: str,
    raw_root: Path = RAW_ROOT,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    target_relative_path = str(target_relative_path).strip().replace("\\", "/")
    term = str(term).strip()
    definition = str(definition).strip()
    if not target_relative_path:
        raise ValueError("target path is required")
    if not term:
        raise ValueError("term is required")
    if not definition:
        raise ValueError("definition is required")
    if target_relative_path == WORLD_ROOT_NAME or not target_relative_path.startswith(f"{WORLD_ROOT_NAME}/"):
        raise ValueError(f"target path must be inside {WORLD_ROOT_NAME}")

    existing_entry = find_world_annotation_entry_v2(term, raw_root=raw_root)
    if existing_entry and not overwrite:
        raise FileExistsError(str(existing_entry.get("source_path", "")))

    if existing_entry and overwrite:
        existing_path = str(existing_entry.get("source_path", "")).strip().replace("\\", "/")
        if existing_path:
            target_relative_path = str(Path(existing_path).parent).replace("\\", "/")

    target_dir = ensure_within_root(raw_root / target_relative_path, raw_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / f"{term}.editor.json"
    target_relative_file = target_file.relative_to(raw_root.resolve()).as_posix()
    document = default_document(target_relative_file)
    document["title"] = term
    document["doc_type"] = "annotation"
    document["blocks"] = []
    for raw_line in definition.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        block = create_block("text_body")
        block["text"] = line
        document["blocks"].append(block)
    result = save_editor_document_v2(target_relative_file, document, raw_root=raw_root)
    return {
        "status": "ok",
        "target_path": target_relative_file,
        "target_folder": target_relative_path,
        "term": term,
        "definition": definition,
        "document": result["document"],
    }



def get_primary_annotation_term(relative_path: str) -> str:
    normalized = str(relative_path or "").replace("\\", "/")
    if not normalized.startswith(f"{WORLD_ROOT_NAME}/"):
        return ""
    name = Path(normalized).name
    if name.endswith(".editor.json"):
        return name[:-len(".editor.json")]
    if name.endswith(".txt"):
        return Path(name).stem
    return ""



def detect_annotation_spans(text: str, entries: list[dict[str, Any]], *, excluded_terms: set[str] | None = None, omissions: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    value = str(text or "")
    if not value:
        return []
    excluded = {str(item).strip() for item in (excluded_terms or set()) if str(item).strip()}
    omission_keys = {
        (str(item.get("term", "")).strip(), item.get("start"), item.get("end"))
        for item in (omissions or [])
        if isinstance(item, dict)
    }
    ordered = sorted(
        [item for item in entries if str(item.get("term", "")).strip() and str(item.get("term", "")).strip() not in excluded],
        key=lambda item: (-len(str(item.get("term", ""))), str(item.get("term", ""))),
    )
    occupied = [False] * len(value)
    spans: list[dict[str, Any]] = []
    for entry in ordered:
        term = str(entry.get("term", "")).strip()
        start = value.find(term)
        while start != -1:
            end = start + len(term)
            if not any(occupied[start:end]) and (term, start, end) not in omission_keys:
                spans.append({"term": term, "start": start, "end": end})
                for index in range(start, end):
                    occupied[index] = True
            start = value.find(term, start + 1)
    spans.sort(key=lambda item: (item["start"], item["end"]))
    return spans


@lru_cache(maxsize=1)
def get_editor_page_v2() -> str:
    return (STATIC_DIR / "editor_v2.html").read_text(encoding="utf-8")
