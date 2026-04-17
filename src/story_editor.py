from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

RAW_ROOT = Path("data/raw")
WORLD_ROOT_NAME = "\u4e16\u754c\u89c2"

TITLE_PREFIX = "\u3010\u6587\u6863\u6807\u9898\uff1a"
SCENE_PREFIX = "\u3010\u573a\u666f\uff06\u4eba\u7269\uff1a"
BLOCK_TITLE_PREFIX = "\u3010\u6807\u9898\uff1a"
SUMMARY_PREFIX = "\u3010\u5267\u60c5\u6897\u6982\uff1a"
ANALYSIS_PREFIX = "\u3010\u89e3\u6790\uff1a"
NARRATION_PREFIX = "\u3010\u65c1\u767d\uff1a"
BODY_PREFIX = "\u3010\u6b63\u6587\uff1a"
LEGACY_NARRATION_SMALL_PREFIX = "\u3010\u65c1\u767d\u00b7\u5c0f\uff1a"
LEGACY_SUPPLEMENT_PREFIX = "\u3010\u8865\u5145\u65c1\u767d\uff1a"
SMALL_NARRATION_PREFIX = "\u3010\u65c1\u767d\u00b7\u5c0f\uff1a"
SUPPLEMENT_PREFIX = "\u3010\u65c1\u767d\u00b7\u8865\u5145\uff1a"
OPTION_START = "\u2192"
OPTION_NEXT = "\u2190\u2192"
OPTION_END = "\u2190"
DEFAULT_OPTION_SPEAKER = "\u6f02\u6cca\u8005"

BLOCK_TYPE_ALIASES = {
    "scene_title": "scene_cast",
    "dialogue": "line",
    "heading": "narration",
    "narration": "narration",
    "narration_small": "narration_small",
    "body": "narration_small",
    "body_text": "narration_small",
    "analysis": "supplement",
    "supplement": "supplement",
    "scene_cast": "scene_cast",
    "line": "line",
    "narration": "narration",
    "narration_small": "narration_small",
    "supplement": "supplement",
}

TEXT_BLOCK_TYPES = {"scene_cast", "narration", "narration_small", "supplement", "summary"}
REFERENCEABLE_BLOCK_TYPES = {"scene_cast", "line", "narration", "narration_small", "supplement", "summary"}


def normalize_block_type(value: Any) -> str:
    block_type = str(value or "").strip()
    return BLOCK_TYPE_ALIASES.get(block_type, block_type)


def new_id() -> str:
    return uuid4().hex[:8]


def editor_sidecar_path(txt_path: Path) -> Path:
    return txt_path.with_suffix(".editor.json")


def default_document(relative_path: str) -> dict[str, Any]:
    title_source = Path(relative_path)
    if title_source.name.endswith(".editor.json"):
        title = title_source.name[: -len(".editor.json")]
    else:
        title = title_source.stem
    return {
        "version": 3,
        "path": relative_path,
        "title": title,
        "blocks": [],
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


def normalize_annotation_refs(values: Any) -> list[str]:
    refs: list[str] = []
    for value in values or []:
        term = str(value).strip()
        if term and term not in refs:
            refs.append(term)
    return refs


def normalize_annotation_omissions(values: Any) -> list[dict[str, int | str]]:
    omissions: list[dict[str, int | str]] = []
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
        omissions.append({"term": term, "start": start, "end": end})
    return omissions


def normalize_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for block in blocks:
        block_type = normalize_block_type(block.get("type", ""))
        item = {"id": str(block.get("id") or new_id()), "type": block_type}

        if block_type in TEXT_BLOCK_TYPES:
            item["text"] = str(block.get("text", ""))
            item["annotation_refs"] = normalize_annotation_refs(block.get("annotation_refs", []))
            item["annotation_omissions"] = normalize_annotation_omissions(block.get("annotation_omissions", []))
            if block_type in {"narration", "narration_small"}:
                item["italic"] = bool(block.get("italic", False))
        elif block_type == "line":
            item["speaker"] = str(block.get("speaker", ""))
            item["text"] = str(block.get("text", ""))
            item["annotation_refs"] = normalize_annotation_refs(block.get("annotation_refs", []))
            item["annotation_omissions"] = normalize_annotation_omissions(block.get("annotation_omissions", []))
        elif block_type == "branch":
            item["option_speaker"] = str(block.get("option_speaker", "")).strip() or DEFAULT_OPTION_SPEAKER
            options: list[dict[str, Any]] = []
            for option in block.get("options", []):
                response_blocks = option.get("response_blocks")
                if not response_blocks and option.get("response_text"):
                    response_blocks = legacy_text_to_blocks(str(option.get("response_text", "")))
                options.append(
                    {
                        "id": str(option.get("id") or new_id()),
                        "label": str(option.get("label", "")),
                        "annotation_refs": normalize_annotation_refs(option.get("annotation_refs", [])),
                        "annotation_omissions": normalize_annotation_omissions(option.get("annotation_omissions", [])),
                        "response_blocks": normalize_blocks(response_blocks or []),
                    }
                )
            item["options"] = options
        else:
            continue

        normalized.append(item)
    return normalized


def block_to_txt_lines(block: dict[str, Any]) -> list[str]:
    block_type = normalize_block_type(block.get("type", ""))
    if block_type == "scene_cast":
        text = str(block.get("text", "")).strip()
        return [f"{SCENE_PREFIX}{text}\u3011", ""] if text else []
    if block_type == "heading":
        text = str(block.get("text", "")).strip()
        return [f"{BLOCK_TITLE_PREFIX}{text}\u3011"] if text else []
    if block_type == "narration":
        text = str(block.get("text", "")).strip()
        return [f"\u3010{text}\u3011"] if text else []
    if block_type == "narration_small":
        text = str(block.get("text", "")).strip()
        return [f"{SMALL_NARRATION_PREFIX}{text}\u3011"] if text else []
    if block_type == "supplement":
        text = str(block.get("text", "")).strip()
        return [f"{SUPPLEMENT_PREFIX}{text}\u3011"] if text else []
    if block_type == "line":
        speaker = str(block.get("speaker", "")).strip()
        text = str(block.get("text", "")).strip()
        if speaker and text:
            return [f"{speaker}\uff1a{text}"]
        if text:
            return [text]
        return []
    if block_type == "summary":
        text = str(block.get("text", "")).strip()
        return [f"{SUMMARY_PREFIX}{text}\u3011"] if text else []
    if block_type == "branch":
        options = block.get("options", [])
        if not options:
            return []
        option_speaker = str(block.get("option_speaker", "")).strip() or DEFAULT_OPTION_SPEAKER
        lines: list[str] = []
        for index, option in enumerate(options):
            lines.append(OPTION_START if index == 0 else OPTION_NEXT)
            label = str(option.get("label", "")).strip()
            if label:
                lines.append(f"{option_speaker}\uff1a{label}")
            for response_block in option.get("response_blocks", []):
                lines.extend(block_to_txt_lines(response_block))
        lines.append(OPTION_END)
        return lines
    return []


def compile_document_to_txt(document: dict[str, Any]) -> str:
    lines: list[str] = []
    title = str(document.get("title", "")).strip()
    if title:
        lines.extend([f"{TITLE_PREFIX}{title}\u3011", ""])
    for block in document.get("blocks", []):
        chunk = block_to_txt_lines(block)
        lines.extend(chunk)
        if chunk and lines[-1] != "":
            lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + ("\n" if lines else "")


def legacy_text_to_blocks(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        parsed_line = parse_line_text(stripped)
        if parsed_line:
            speaker, content = parsed_line
            blocks.append({"id": new_id(), "type": "line", "speaker": speaker, "text": content, "annotation_refs": []})
            continue
        if stripped.startswith(ANALYSIS_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "supplement", "text": stripped[len(ANALYSIS_PREFIX) : -1].strip(), "annotation_refs": []})
            continue
        if stripped.startswith(SUPPLEMENT_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "supplement", "text": stripped[len(SUPPLEMENT_PREFIX) : -1].strip(), "annotation_refs": []})
            continue
        if stripped.startswith(LEGACY_SUPPLEMENT_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "supplement", "text": stripped[len(LEGACY_SUPPLEMENT_PREFIX) : -1].strip(), "annotation_refs": []})
            continue
        if stripped.startswith(BODY_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "narration_small", "text": stripped[len(BODY_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
            continue
        if stripped.startswith(NARRATION_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "narration_small", "text": stripped[len(NARRATION_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
            continue
        if stripped.startswith(SMALL_NARRATION_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "narration_small", "text": stripped[len(SMALL_NARRATION_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
            continue
        if stripped.startswith(LEGACY_NARRATION_SMALL_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "narration_small", "text": stripped[len(LEGACY_NARRATION_SMALL_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
            continue
        if stripped.startswith(BLOCK_TITLE_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "narration", "text": stripped[len(BLOCK_TITLE_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
            continue
        if stripped.startswith(SUMMARY_PREFIX) and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "summary", "text": stripped[len(SUMMARY_PREFIX) : -1].strip(), "annotation_refs": []})
            continue
        if stripped.startswith("\u3010") and stripped.endswith("\u3011"):
            blocks.append({"id": new_id(), "type": "narration", "text": stripped[1:-1].strip(), "annotation_refs": [], "italic": False})
            continue
        blocks.append({"id": new_id(), "type": "narration", "text": stripped, "annotation_refs": [], "italic": False})
    return blocks


def parse_txt_to_document(relative_path: str, content: str) -> dict[str, Any]:
    document = default_document(relative_path)
    lines = content.replace("\r\n", "\n").split("\n")
    index = 0
    while index < len(lines):
        stripped = lines[index].strip()
        if not stripped:
            index += 1
            continue
        if stripped == OPTION_START:
            branch_block = {"id": new_id(), "type": "branch", "option_speaker": DEFAULT_OPTION_SPEAKER, "options": []}
            index += 1
            current_option: dict[str, Any] | None = None
            response_lines: list[str] = []
            while index < len(lines):
                marker = lines[index].strip()
                if marker in {OPTION_NEXT, OPTION_END}:
                    if current_option is not None:
                        current_option["response_blocks"] = legacy_text_to_blocks("\n".join(response_lines).strip())
                        branch_block["options"].append(current_option)
                    current_option = None
                    response_lines = []
                    index += 1
                    if marker == OPTION_END:
                        break
                    continue
                if current_option is None:
                    parsed = parse_line_text(marker)
                    if parsed:
                        speaker, label = parsed
                        branch_block["option_speaker"] = speaker
                        current_option = {"id": new_id(), "label": label, "annotation_refs": [], "response_blocks": []}
                    else:
                        current_option = {"id": new_id(), "label": marker, "annotation_refs": [], "response_blocks": []}
                else:
                    response_lines.append(lines[index].rstrip())
                index += 1
            document["blocks"].append(branch_block)
            continue
        if stripped.startswith(TITLE_PREFIX) and stripped.endswith("\u3011"):
            document["title"] = stripped[len(TITLE_PREFIX) : -1].strip()
        elif stripped.startswith("\u3010\u573a\u666f\u6807\u9898\uff1a") and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "scene_cast", "text": stripped[len("\u3010\u573a\u666f\u6807\u9898\uff1a") : -1].strip(), "annotation_refs": []})
        elif stripped.startswith(SCENE_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "scene_cast", "text": stripped[len(SCENE_PREFIX) : -1].strip(), "annotation_refs": []})
        elif stripped.startswith(SUMMARY_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "summary", "text": stripped[len(SUMMARY_PREFIX) : -1].strip(), "annotation_refs": []})
        elif stripped.startswith(BODY_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "narration_small", "text": stripped[len(BODY_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
        elif stripped.startswith(NARRATION_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "narration_small", "text": stripped[len(NARRATION_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
        elif stripped.startswith(SMALL_NARRATION_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "narration_small", "text": stripped[len(SMALL_NARRATION_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
        elif stripped.startswith(LEGACY_NARRATION_SMALL_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "narration_small", "text": stripped[len(LEGACY_NARRATION_SMALL_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
        elif stripped.startswith(ANALYSIS_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "supplement", "text": stripped[len(ANALYSIS_PREFIX) : -1].strip(), "annotation_refs": []})
        elif stripped.startswith(SUPPLEMENT_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "supplement", "text": stripped[len(SUPPLEMENT_PREFIX) : -1].strip(), "annotation_refs": []})
        elif stripped.startswith("\u3010\u8865\u5145\u65c1\u767d\uff1a") and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "supplement", "text": stripped[len("\u3010\u8865\u5145\u65c1\u767d\uff1a") : -1].strip(), "annotation_refs": []})
        elif stripped.startswith(LEGACY_SUPPLEMENT_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "supplement", "text": stripped[len(LEGACY_SUPPLEMENT_PREFIX) : -1].strip(), "annotation_refs": []})
        elif stripped.startswith(BLOCK_TITLE_PREFIX) and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "narration", "text": stripped[len(BLOCK_TITLE_PREFIX) : -1].strip(), "annotation_refs": [], "italic": False})
        elif stripped.startswith("\u3010") and stripped.endswith("\u3011"):
            document["blocks"].append({"id": new_id(), "type": "narration", "text": stripped[1:-1].strip(), "annotation_refs": [], "italic": False})
        else:
            parsed = parse_line_text(stripped)
            if parsed:
                speaker, text = parsed
                document["blocks"].append({"id": new_id(), "type": "line", "speaker": speaker, "text": text, "annotation_refs": []})
            else:
                document["blocks"].append({"id": new_id(), "type": "narration", "text": stripped, "annotation_refs": [], "italic": False})
        index += 1
    return document


def ensure_within_root(candidate: Path, raw_root: Path) -> Path:
    candidate = candidate.resolve()
    raw_root_resolved = raw_root.resolve()
    if raw_root_resolved not in candidate.parents and candidate != raw_root_resolved:
        raise ValueError("path out of raw root")
    return candidate


def resolve_editor_source_path(relative_path: str, raw_root: Path = RAW_ROOT) -> tuple[Path, str]:
    candidate = ensure_within_root(raw_root / relative_path, raw_root)
    name = candidate.name.lower()
    if name.endswith('.editor.json'):
        return candidate, 'editor_json'
    if candidate.suffix.lower() == '.txt':
        return candidate, 'txt'
    raise ValueError('editor only supports txt files or .editor.json files')


def editor_json_to_txt_path(editor_json_path: Path) -> Path:
    if not editor_json_path.name.endswith('.editor.json'):
        raise ValueError('not an editor json path')
    return editor_json_path.with_name(editor_json_path.name[:-len('.editor.json')] + '.txt')


def load_document_from_editor_json(editor_json_path: Path, relative_path: str) -> dict[str, Any]:
    document = json.loads(editor_json_path.read_text(encoding='utf-8-sig'))
    document['path'] = relative_path
    document['blocks'] = normalize_blocks(document.get('blocks', []))
    return document


def load_document_from_editor_json_safe(editor_json_path: Path, relative_path: str) -> dict[str, Any]:
    try:
        document = load_document_from_editor_json(editor_json_path, relative_path)
    except Exception:
        return default_document(relative_path)
    if not isinstance(document, dict):
        return default_document(relative_path)
    if not isinstance(document.get("blocks", []), list):
        document["blocks"] = []
    document["path"] = relative_path
    document["title"] = str(document.get("title", "")).strip() or default_document(relative_path)["title"]
    document["blocks"] = normalize_blocks(document.get("blocks", []))
    return document


def load_editor_document(relative_path: str, raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    source_path, source_kind = resolve_editor_source_path(relative_path, raw_root=raw_root)
    if not source_path.exists():
        raise FileNotFoundError(relative_path)

    if source_kind == 'editor_json':
        document = load_document_from_editor_json_safe(source_path, relative_path)
        return {
            'path': relative_path,
            'document': document,
            'compiled_text': compile_document_to_txt(document),
            'source': 'editor_json',
        }

    sidecar = editor_sidecar_path(source_path)
    if sidecar.exists():
        document = load_document_from_editor_json_safe(sidecar, str(Path(relative_path).with_suffix('.editor.json')))
        document['path'] = relative_path
        return {
            'path': relative_path,
            'document': document,
            'compiled_text': compile_document_to_txt(document),
            'source': 'sidecar',
        }

    text = source_path.read_text(encoding='utf-8')
    document = parse_txt_to_document(relative_path, text)
    return {'path': relative_path, 'document': document, 'compiled_text': compile_document_to_txt(document), 'source': 'txt'}


def save_editor_document(relative_path: str, document: dict[str, Any], raw_root: Path = RAW_ROOT) -> dict[str, Any]:
    source_path, source_kind = resolve_editor_source_path(relative_path, raw_root=raw_root)
    source_path.parent.mkdir(parents=True, exist_ok=True)

    normalized = default_document(relative_path)
    normalized['title'] = str(document.get('title', '')).strip()
    normalized['blocks'] = normalize_blocks(document.get('blocks', []))
    compiled_text = compile_document_to_txt(normalized)

    if source_kind == 'editor_json':
        source_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')
        txt_path = editor_json_to_txt_path(source_path)
        txt_path.write_text(compiled_text, encoding='utf-8')
    else:
        source_path.write_text(compiled_text, encoding='utf-8')
        editor_sidecar_path(source_path).write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding='utf-8')

    return {'path': relative_path, 'compiled_text': compiled_text, 'document': normalized}


def iter_world_editor_documents(raw_root: Path = RAW_ROOT) -> Iterator[tuple[str, dict[str, Any]]]:
    world_root = raw_root / WORLD_ROOT_NAME
    if not world_root.exists():
        return

    seen_bases: set[Path] = set()
    for editor_json_path in world_root.rglob('*.editor.json'):
        relative_path = editor_json_path.relative_to(raw_root).as_posix()
        try:
            document = load_document_from_editor_json_safe(editor_json_path, relative_path)
        except Exception:
            continue
        seen_bases.add(editor_json_path.with_suffix('').with_suffix(''))
        yield relative_path, document

    for txt_path in world_root.rglob('*.txt'):
        if txt_path in seen_bases:
            continue
        sidecar = editor_sidecar_path(txt_path)
        relative_txt_path = txt_path.relative_to(raw_root).as_posix()
        try:
            if sidecar.exists():
                document = load_document_from_editor_json_safe(sidecar, sidecar.relative_to(raw_root).as_posix())
            else:
                document = parse_txt_to_document(relative_txt_path, txt_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        yield relative_txt_path, document


def build_world_annotation_library(raw_root: Path = RAW_ROOT) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_terms: set[tuple[str, str]] = set()
    for relative_path, document in iter_world_editor_documents(raw_root=raw_root):
        file_name = Path(relative_path).name
        if file_name.endswith(".editor.json"):
            term = file_name[: -len(".editor.json")]
        else:
            term = Path(relative_path).stem
        title = str(document.get("title", "")).strip() or term
        blocks = normalize_blocks(document.get("blocks", []))
        definition_parts: list[str] = []
        first_meaningful_text = True
        for block in blocks:
            block_type = normalize_block_type(block.get("type", ""))
            if block_type == "scene_cast":
                text = str(block.get("text", "")).strip()
            elif block_type in {"narration", "narration_small", "supplement", "summary"}:
                text = str(block.get("text", "")).strip()
            elif block_type == "line":
                speaker = str(block.get("speaker", "")).strip()
                content = str(block.get("text", "")).strip()
                text = f"{speaker}\uff1a{content}" if speaker and content else content
            elif block_type == "branch":
                option_speaker = str(block.get("option_speaker", "")).strip() or DEFAULT_OPTION_SPEAKER
                branch_lines: list[str] = []
                for option in block.get("options", []):
                    label = str(option.get("label", "")).strip()
                    if label:
                        branch_lines.append(f"{option_speaker}\uff1a{label}")
                    for response_block in option.get("response_blocks", []):
                        response_type = normalize_block_type(response_block.get("type", ""))
                        if response_type == "line":
                            speaker = str(response_block.get("speaker", "")).strip()
                            content = str(response_block.get("text", "")).strip()
                            if speaker and content:
                                branch_lines.append(f"{speaker}\uff1a{content}")
                            elif content:
                                branch_lines.append(content)
                        else:
                            content = str(response_block.get("text", "")).strip()
                            if content:
                                branch_lines.append(content)
                text = "\n".join(branch_lines).strip()
            else:
                text = ""

            if not text:
                continue
            if first_meaningful_text and text == title:
                first_meaningful_text = False
                continue
            first_meaningful_text = False
            definition_parts.append(text)

        definition = "\n".join(part for part in definition_parts if part).strip()
        if not term or not definition:
            continue
        key = (term, relative_path)
        if key in seen_terms:
            continue
        seen_terms.add(key)
        entries.append({
            "term": term,
            "definition": definition,
            "source_path": relative_path,
            "source_title": title,
        })
    entries.sort(key=lambda item: (item["term"], item["source_path"]))
    return entries


def list_world_editor_targets(raw_root: Path = RAW_ROOT) -> list[dict[str, str]]:
    world_root = raw_root / WORLD_ROOT_NAME
    if not world_root.exists():
        return []

    targets: dict[str, dict[str, str]] = {}
    skip_region_report = "\u5730\u533a\u63a2\u7d22\u62a5\u544a"
    region_info_root = f"{WORLD_ROOT_NAME}/\u5730\u533a\u4fe1\u606f"

    for folder in sorted(path for path in world_root.rglob("*") if path.is_dir()):
        relative_path = folder.relative_to(raw_root).as_posix()
        parts = relative_path.split("/")
        if skip_region_report in parts:
            continue
        if relative_path == region_info_root:
            continue

        if relative_path.startswith(f"{region_info_root}/"):
            label = relative_path[len(f"{region_info_root}/") :]
        elif relative_path.startswith(f"{WORLD_ROOT_NAME}/"):
            label = relative_path[len(f"{WORLD_ROOT_NAME}/") :]
        else:
            label = relative_path

        if not label:
            continue

        label = label.replace("/", "\u2014\u2014")
        targets[relative_path] = {"path": relative_path, "label": label}

    return [targets[key] for key in sorted(targets.keys())]


def save_world_annotation_entry(
    target_relative_path: str,
    term: str,
    definition: str,
    raw_root: Path = RAW_ROOT,
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

    if target_relative_path != WORLD_ROOT_NAME and not target_relative_path.startswith(f"{WORLD_ROOT_NAME}/"):
        raise ValueError(f"target path must be inside {WORLD_ROOT_NAME}")

    target_dir = ensure_within_root(raw_root / target_relative_path, raw_root)
    raw_root_resolved = raw_root.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / f"{term}.editor.json"
    target_relative_file = target_file.relative_to(raw_root_resolved).as_posix()

    if target_file.exists():
        document = load_document_from_editor_json_safe(target_file, target_relative_file)
    else:
        txt_path = editor_json_to_txt_path(target_file)
        if txt_path.exists():
            document = parse_txt_to_document(
                txt_path.relative_to(raw_root_resolved).as_posix(),
                txt_path.read_text(encoding="utf-8"),
            )
            document["path"] = target_relative_file
        else:
            document = default_document(target_relative_file)

    content_blocks: list[dict[str, Any]] = []
    for raw_line in definition.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        content_blocks.append({"id": new_id(), "type": "narration_small", "text": line, "annotation_refs": [], "italic": False})

    document["title"] = term
    document["blocks"] = content_blocks
    result = save_editor_document(target_relative_file, document, raw_root=raw_root)
    return {
        "status": "ok",
        "target_path": target_relative_file,
        "target_folder": target_relative_path,
        "term": term,
        "definition": definition,
        "document": result["document"],
    }


STATIC_DIR = Path(__file__).with_name('static')


@lru_cache(maxsize=1)
def get_editor_page() -> str:
    return (STATIC_DIR / 'editor.html').read_text(encoding='utf-8')




