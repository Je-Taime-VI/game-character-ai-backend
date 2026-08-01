from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

RAW_DATA_DIR = Path("data/raw")
DEFAULT_OUTPUT_PATH = Path("data/processed/metadata.json")

MAIN_STORY_DIRNAME = "主线"
SIDE_STORY_DIRNAME = "支线"
ROLE_DIRNAME = "角色"
WORLD_DIRNAME = "世界观"
EXPLORATION_REPORT_DIRNAME = "地区探索报告"
ROLE_FILE_CATEGORY = {
    "个性语音": "role_personality_voice",
    "基本信息": "role_basic_info",
    "角色档案": "role_profile",
    "个人档案": "role_profile",
    "角色故事": "role_story",
    "特殊料理": "role_item",
    "珍贵之物": "role_item",
}


@dataclass
class LineChunk:
    line_id: str
    parent_id: str
    text: str
    line_index: int
    retrieval_text: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class BlockChunk:
    chunk_id: str
    text: str
    retrieval_text: str
    metadata: dict = field(default_factory=dict)
    line_chunks: list[LineChunk] = field(default_factory=list)


@dataclass
class KnowledgeDocument:
    doc_id: str
    path: str
    category: str
    title: str
    retrieval_mode: str
    metadata: dict = field(default_factory=dict)
    chunks: list[BlockChunk] = field(default_factory=list)


def normalize_text(text: str) -> str:
    return text.replace("\ufeff", "").replace("\r\n", "\n").strip()


def split_by_blank_lines(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    return [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]


def split_non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in normalize_text(text).split("\n") if line.strip()]


def relative_posix_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def infer_document_category(rel_path: str) -> str:
    path_obj = Path(rel_path)
    parts = path_obj.parts
    stem = path_obj.name[: -len(".editor.json")] if path_obj.name.endswith(".editor.json") else path_obj.stem

    if MAIN_STORY_DIRNAME in parts:
        return "main_story"
    if SIDE_STORY_DIRNAME in parts:
        return "side_story"
    if WORLD_DIRNAME in parts and EXPLORATION_REPORT_DIRNAME in parts:
        return "world_exploration_report"
    if WORLD_DIRNAME in parts:
        return "world"
    if ROLE_DIRNAME in parts:
        if "特殊文本" in parts:
            return "role_special_text"
        return ROLE_FILE_CATEGORY.get(stem, "role_other")
    return "other"


def role_name_from_path(path: Path) -> str | None:
    parts = path.parts
    if ROLE_DIRNAME not in parts:
        return None
    role_index = parts.index(ROLE_DIRNAME) + 1
    if role_index >= len(parts):
        return None
    return parts[role_index]


def infer_retrieval_mode(category: str) -> str:
    if category in {"main_story", "side_story", "role_profile", "role_story", "role_special_text"}:
        return "hierarchical"
    return "flat"


def build_world_region_metadata(path: Path, root: Path) -> dict:
    rel_path = relative_posix_path(path, root)
    path_obj = Path(rel_path)
    parts = path_obj.parts
    if WORLD_DIRNAME not in parts or "地区信息" not in parts:
        return {}

    region_info_index = parts.index("地区信息")
    trailing_parts = list(parts[region_info_index + 1 : -1])
    region_layers: list[str] = []
    current: list[str] = []
    for part in trailing_parts:
        if part == EXPLORATION_REPORT_DIRNAME:
            continue
        current.append(part)
        region_layers.append("/".join(current))

    metadata = {
        "region_layers": region_layers,
        "region_layer": region_layers[-1] if region_layers else None,
        "region_depth": len(region_layers),
    }
    if EXPLORATION_REPORT_DIRNAME in parts:
        metadata["region_subtype"] = "exploration_report"
    return metadata


def parse_scene_metadata(lines: list[str]) -> dict:
    scene_name = None
    scene_roles: list[str] = []
    arrivals: list[str] = []
    departures: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("【场景：") and stripped.endswith("】"):
            scene_name = stripped[4:-1].strip()
        elif stripped.startswith("【角色：") and stripped.endswith("】"):
            raw_roles = stripped[4:-1]
            scene_roles = [role.strip() for role in re.split(r"[，、, ]+", raw_roles) if role.strip()]
        elif stripped.startswith("【") and stripped.endswith("】"):
            event = stripped[1:-1].strip()
            arrivals.extend(extract_named_events(event, arrival=True))
            departures.extend(extract_named_events(event, arrival=False))

    return {
        "scene_name": scene_name,
        "scene_roles": scene_roles,
        "arrivals": dedupe_keep_order(arrivals),
        "departures": dedupe_keep_order(departures),
    }


def parse_structured_scene_cast(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.startswith("\u3010") and stripped.endswith("\u3011"):
        stripped = stripped[1:-1].strip()
    for pattern in (
        r"(?:\u5730\u70b9|\u573a\u666f)\s*[:\uff1a]\s*(?P<scene>.*?)(?:\s+|[,，、])(?:\u4eba\u7269|\u89d2\u8272)\s*[:\uff1a]\s*(?P<roles>.+)$",
        r"(?:\u65f6\u95f4&\u5730\u70b9&\u4eba\u7269|\u573a\u666f&\u4eba\u7269)\s*[:\uff1a]\s*(?P<scene>.*?)(?:\s+|[,，、])(?:\u4eba\u7269|\u89d2\u8272)\s*[:\uff1a]\s*(?P<roles>.+)$",
    ):
        match = re.search(pattern, stripped)
        if not match:
            continue
        scene_name = match.group("scene").strip()
        raw_roles = match.group("roles").strip()
        scene_roles = [role.strip() for role in re.split(r"[\uff0c\u3001,;/\s]+", raw_roles) if role.strip()]
        return {"scene_name": scene_name or None, "scene_roles": scene_roles}
    return None


def parse_scene_metadata(lines: list[str]) -> dict:
    scene_name = None
    scene_roles: list[str] = []
    arrivals: list[str] = []
    departures: list[str] = []

    for line in lines:
        stripped = line.strip()
        structured_scene = parse_structured_scene_cast(stripped)
        if structured_scene:
            scene_name = structured_scene.get("scene_name") or scene_name
            scene_roles = structured_scene.get("scene_roles") or scene_roles
            continue
        if stripped.startswith("\u3010\u573a\u666f\uff1a") and stripped.endswith("\u3011"):
            scene_name = stripped[len("\u3010\u573a\u666f\uff1a") : -1].strip()
        elif stripped.startswith("\u3010\u89d2\u8272\uff1a") and stripped.endswith("\u3011"):
            raw_roles = stripped[len("\u3010\u89d2\u8272\uff1a") : -1]
            scene_roles = [role.strip() for role in re.split(r"[\uff0c\u3001, ]+", raw_roles) if role.strip()]
        elif stripped.startswith("\u3010") and stripped.endswith("\u3011"):
            event = stripped[1:-1].strip()
            arrivals.extend(extract_named_events(event, arrival=True))
            departures.extend(extract_named_events(event, arrival=False))

    return {
        "scene_name": scene_name,
        "scene_roles": scene_roles,
        "arrivals": dedupe_keep_order(arrivals),
        "departures": dedupe_keep_order(departures),
    }


def extract_named_events(event: str, arrival: bool) -> list[str]:
    arrival_keywords = ("来到", "到来", "抵达", "进入", "出现", "赶到", "走来")
    departure_keywords = ("离开", "退场", "离去", "离场", "走开", "消失")
    keywords = arrival_keywords if arrival else departure_keywords

    for keyword in keywords:
        if keyword in event:
            name = event.replace(keyword, "").strip(" ：:，,。！？!?,")
            return [name] if name else []
    return []


def dedupe_keep_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def build_document(path: Path, root: Path = RAW_DATA_DIR) -> KnowledgeDocument:
    rel_path = relative_posix_path(path, root)
    category = infer_document_category(rel_path)
    retrieval_mode = infer_retrieval_mode(category)
    text = normalize_text(path.read_text(encoding="utf-8"))
    role_name = role_name_from_path(Path(rel_path))

    metadata = {
        "path": rel_path,
        "knowledge_type": category,
        "source_name": path.name,
    }
    metadata.update(build_world_region_metadata(path, root))
    if role_name and category.startswith("role_"):
        metadata["role_name"] = role_name
    doc = KnowledgeDocument(
        doc_id=rel_path.replace("/", "__"),
        path=rel_path,
        category=category,
        title=path.stem,
        retrieval_mode=retrieval_mode,
        metadata=metadata,
    )
    doc.chunks = build_chunks_for_document(doc, text)
    return doc


def build_document_from_editor_json(path: Path, root: Path = RAW_DATA_DIR) -> KnowledgeDocument:
    rel_path = relative_posix_path(path, root)
    category = infer_document_category(rel_path)
    retrieval_mode = infer_retrieval_mode(category)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    role_name = role_name_from_path(Path(rel_path))
    metadata = {
        "path": rel_path,
        "knowledge_type": category,
        "source_name": path.name,
        "structured_source": path.relative_to(root).as_posix(),
    }
    metadata.update(build_world_region_metadata(path, root))
    if role_name and category.startswith("role_"):
        metadata["role_name"] = role_name
    doc = KnowledgeDocument(
        doc_id=rel_path.replace("/", "__"),
        path=rel_path,
        category=category,
        title=path.name[: -len(".editor.json")] if path.name.endswith(".editor.json") else path.stem,
        retrieval_mode=retrieval_mode,
        metadata=metadata,
    )
    if category in {"main_story", "side_story"}:
        doc.chunks = build_story_chunks_from_editor_document(doc, data)
    else:
        doc.chunks = build_chunks_from_editor_document(doc, data)
    return doc


def build_chunks_for_document(doc: KnowledgeDocument, text: str) -> list[BlockChunk]:
    category = doc.category

    if not text:
        return []

    if category == "world_exploration_report":
        return build_flat_line_chunks(doc, text)
    if category in {"world", "role_other", "other"}:
        return [build_single_chunk(doc, text, 0)]
    if category in {"role_personality_voice", "role_basic_info", "role_item"}:
        return build_flat_blank_line_chunks(doc, text)
    if category in {"main_story", "side_story"}:
        return build_hierarchical_scene_chunks(doc, text, line_mode="all_lines")
    if category == "role_profile":
        return build_hierarchical_blank_line_chunks(doc, text, line_mode="all_lines")
    if category == "role_story":
        return build_hierarchical_blank_line_chunks(doc, text, line_mode="paragraph_lines")
    if category == "role_special_text":
        return build_hierarchical_blank_line_chunks(doc, text, line_mode="all_lines")

    return [build_single_chunk(doc, text, 0)]


def build_chunks_from_editor_document(doc: KnowledgeDocument, document: dict[str, Any]) -> list[BlockChunk]:
    blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
    sections = editor_document_sections(blocks)
    if not sections:
        return []
    if doc.retrieval_mode == "hierarchical":
        return [
            build_hierarchical_editor_section_chunk(doc, section_items, section_number)
            for section_number, section_items in enumerate(sections)
        ]
    return [
        build_flat_editor_section_chunk(doc, section_items, section_number)
        for section_number, section_items in enumerate(sections)
    ]


def editor_document_sections(blocks: list[dict[str, Any]]) -> list[list[tuple[int, dict[str, Any], str]]]:
    has_xlsx_sections = any(
        isinstance(block, dict)
        and isinstance(block.get("meta"), dict)
        and "xlsx_section_index" in block["meta"]
        for block in blocks
    )
    sections: list[list[tuple[int, dict[str, Any], str]]] = []
    current: list[tuple[int, dict[str, Any], str]] = []
    current_key: Any = None
    for block_index, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        text = story_block_text(block)
        if not text:
            continue
        meta = block.get("meta") if isinstance(block.get("meta"), dict) else {}
        key = meta.get("xlsx_section_index") if has_xlsx_sections else 0
        if current and key != current_key:
            sections.append(current)
            current = []
        current_key = key
        current.append((block_index, block, text))
    if current:
        sections.append(current)
    return sections


def editor_section_metadata(
    doc: KnowledgeDocument,
    section_items: list[tuple[int, dict[str, Any], str]],
    section_number: int,
) -> dict[str, Any]:
    metadata = dict(doc.metadata)
    metadata["chunk_index"] = section_number
    metadata["section_index"] = section_number
    first_meta = section_items[0][1].get("meta") if isinstance(section_items[0][1].get("meta"), dict) else {}
    if "xlsx_section_index" in first_meta:
        metadata["xlsx_section_index"] = first_meta["xlsx_section_index"]

    source_ids: list[str] = []
    source_types: list[str] = []
    source_orders: list[int] = []
    keywords: list[str] = []
    for _, block, _ in section_items:
        source_metadata = story_block_source_metadata(block)
        source_id = source_metadata.get("source_id")
        source_type = source_metadata.get("source_type")
        source_order = story_block_source_order(block)
        if source_id:
            source_ids.append(str(source_id))
        if source_type:
            source_types.append(str(source_type))
        if source_order is not None:
            source_orders.append(source_order)
        keywords.extend(story_block_keywords(block))
    if source_ids:
        metadata["source_ids"] = dedupe_keep_order(source_ids)
    if source_types:
        metadata["source_types"] = dedupe_keep_order(source_types)
    if source_orders:
        metadata["source_order_start"] = min(source_orders)
        metadata["source_order_end"] = max(source_orders)
    keywords = dedupe_keep_order(keywords)
    if keywords:
        metadata["keywords"] = keywords
    return metadata


def editor_section_text(section_items: list[tuple[int, dict[str, Any], str]]) -> str:
    return "\n".join(text for _, _, text in section_items if text).strip()


def editor_section_retrieval_text(section_items: list[tuple[int, dict[str, Any], str]]) -> str:
    parts: list[str] = []
    for _, block, text in section_items:
        parts.append(retrieval_text_with_keywords(text, story_block_keywords(block)))
    return "\n".join(part for part in parts if part).strip()


def build_flat_editor_section_chunk(
    doc: KnowledgeDocument,
    section_items: list[tuple[int, dict[str, Any], str]],
    section_number: int,
) -> BlockChunk:
    chunk_id = f"{doc.doc_id}::section::{section_number}"
    return BlockChunk(
        chunk_id=chunk_id,
        text=editor_section_text(section_items),
        retrieval_text=editor_section_retrieval_text(section_items),
        metadata=editor_section_metadata(doc, section_items, section_number),
    )


def build_hierarchical_editor_section_chunk(
    doc: KnowledgeDocument,
    section_items: list[tuple[int, dict[str, Any], str]],
    section_number: int,
) -> BlockChunk:
    chunk_id = f"{doc.doc_id}::section::{section_number}"
    metadata = editor_section_metadata(doc, section_items, section_number)
    metadata["retrieval_mode"] = "hierarchical"
    chunk = BlockChunk(
        chunk_id=chunk_id,
        text=editor_section_text(section_items),
        retrieval_text=editor_section_retrieval_text(section_items),
        metadata=metadata,
    )
    line_chunks: list[LineChunk] = []
    line_index = 0
    for block_index, block, block_text in section_items:
        block_type = str(block.get("type", "")).strip()
        block_keywords = story_block_keywords(block)
        for line in split_non_empty_lines(block_text):
            line_metadata = dict(metadata)
            line_metadata.update(
                {
                    "line_index": line_index,
                    "parent_chunk_id": chunk_id,
                    "block_index": block_index,
                    "block_type": block_type,
                    "line_type": classify_line_type(line),
                }
            )
            line_metadata.update(story_block_source_metadata(block))
            line_chunks.append(
                LineChunk(
                    line_id=f"{chunk_id}::line::{line_index}",
                    parent_id=chunk_id,
                    text=line,
                    line_index=line_index,
                    retrieval_text=retrieval_text_with_keywords(line, block_keywords),
                    metadata=line_metadata,
                )
            )
            line_index += 1
    chunk.line_chunks = line_chunks
    return chunk


def story_block_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type", "")).strip()
    text = str(block.get("text", "")).strip()
    if block_type == "line":
        speaker = str(block.get("speaker", "")).strip()
        return f"{speaker}: {text}" if speaker and text else text
    if block_type == "scene_cast":
        return text
    if block_type == "summary":
        return f"[段落梗概]{text}" if text else ""
    if block_type == "chapter_summary":
        return f"[本章梗概]{text}" if text else ""
    if block_type == "paragraph_summary":
        return f"[段落梗概]{text}" if text else ""
    if block_type == "analysis":
        return f"[注释]{text}" if text else ""
    if block_type == "chapter_note":
        return f"[本章注释]\n{text}" if text else ""
    if block_type == "note":
        return f"[注释]{text}" if text else ""
    if block_type == "text_title":
        return f"[文本标题] {text}" if text else ""
    if block_type == "text_body":
        return text
    if block_type == "narration":
        return f"[旁白]{text}" if text else ""
    if block_type == "branch":
        return story_branch_text(block)
    return text


def story_block_annotation_text(block: dict[str, Any]) -> str:
    block_type = str(block.get("type", "")).strip()
    text = str(block.get("text", "")).strip()
    if block_type == "line":
        speaker = str(block.get("speaker", "")).strip()
        return f"{speaker}: {text}" if speaker and text else text
    if block_type == "branch":
        return story_branch_annotation_text(block)
    return text


def story_branch_text(block: dict[str, Any]) -> str:
    speaker = str(block.get("speaker", "")).strip()
    lines: list[str] = []
    for index, option in enumerate(block.get("options", []) or [], start=1):
        label = str(option.get("label", "")).strip()
        if label:
            prefix = f"{speaker}: " if speaker else ""
            lines.append(f"[分支选项 {index}] {prefix}{label}")
        for child in option.get("children", []) or []:
            child_text = story_block_text(child)
            if child_text:
                lines.append(f"[分支后续]{child_text}")
    return "\n".join(lines).strip()


def story_branch_annotation_text(block: dict[str, Any]) -> str:
    speaker = str(block.get("speaker", "")).strip()
    lines: list[str] = []
    for option in block.get("options", []) or []:
        label = str(option.get("label", "")).strip()
        if label:
            prefix = f"{speaker}: " if speaker else ""
            lines.append(f"{prefix}{label}")
        for child in option.get("children", []) or []:
            child_text = story_block_annotation_text(child)
            if child_text:
                lines.append(child_text)
    return "\n".join(lines).strip()


def story_block_annotations(block: dict[str, Any]) -> dict[str, Any]:
    annotations = block.get("annotations") if isinstance(block.get("annotations"), dict) else {}
    return {
        "manual_refs": annotations.get("manual_refs", []) if isinstance(annotations.get("manual_refs", []), list) else [],
        "omissions": annotations.get("omissions", []) if isinstance(annotations.get("omissions", []), list) else [],
    }


def story_block_keywords(block: dict[str, Any]) -> list[str]:
    meta = block.get("meta") if isinstance(block.get("meta"), dict) else {}
    raw_keywords = meta.get("keywords", [])
    if isinstance(raw_keywords, str):
        candidates = re.split(r"[/\n,，、;；]+", raw_keywords)
    elif isinstance(raw_keywords, list):
        candidates = raw_keywords
    else:
        candidates = []
    return dedupe_keep_order([str(keyword).strip() for keyword in candidates if str(keyword).strip()])


def retrieval_text_with_keywords(text: str, keywords: list[str]) -> str:
    clean_text = text.strip()
    clean_keywords = dedupe_keep_order([keyword.strip() for keyword in keywords if keyword.strip()])
    if not clean_keywords:
        return clean_text
    keyword_text = " / ".join(clean_keywords)
    return f"{clean_text}\n[\u5173\u952e\u8bcd]{keyword_text}" if clean_text else f"[\u5173\u952e\u8bcd]{keyword_text}"


def story_block_source_metadata(block: dict[str, Any]) -> dict[str, Any]:
    meta = block.get("meta") if isinstance(block.get("meta"), dict) else {}
    source: dict[str, Any] = {}
    for key in ("source_id", "source_order", "source_type"):
        if key in meta and meta[key] not in (None, ""):
            source[key] = meta[key]
    return source


def story_block_source_order(block: dict[str, Any]) -> int | None:
    source_order = story_block_source_metadata(block).get("source_order")
    if isinstance(source_order, int):
        return source_order
    if source_order in (None, ""):
        return None
    try:
        return int(source_order)
    except (TypeError, ValueError):
        return None


def _legacy_scene_story_chunks_from_editor_document(doc: KnowledgeDocument, document: dict[str, Any]) -> list[BlockChunk]:
    blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
    chapter_summary = ""
    for block in blocks:
        block_type = str(block.get("type", "")).strip()
        if block_type == "chapter_summary" and not chapter_summary:
            chapter_summary = str(block.get("text", "")).strip()

    annotation_entries = load_annotation_entries()
    chunks: list[BlockChunk] = []
    current_scene: list[tuple[int, dict[str, Any]]] = []
    active_chapter_note: dict[str, Any] | None = None

    def append_premise_chunk(
        *,
        block_index: int,
        block: dict[str, Any],
        premise_type: str,
        text: str,
        label: str,
    ) -> None:
        premise_text = text.strip()
        if not premise_text:
            return
        metadata = dict(doc.metadata)
        metadata.update(story_block_source_metadata(block))
        metadata["chunk_index"] = len(chunks)
        metadata["retrieval_mode"] = "premise"
        metadata["premise_type"] = premise_type
        metadata["block_index"] = block_index
        metadata["chapter_summary"] = chapter_summary
        if active_chapter_note:
            metadata["chapter_note"] = str(active_chapter_note.get("text", "")).strip()
            metadata["chapter_note_context"] = dict(active_chapter_note)
        chunks.append(
            BlockChunk(
                chunk_id=f"{doc.doc_id}::premise::{premise_type}::{block_index}",
                text=f"[{label}]{premise_text}",
                retrieval_text=premise_text,
                metadata=metadata,
            )
        )

    def make_chapter_note_context(block_index: int, block: dict[str, Any]) -> dict[str, Any] | None:
        text = str(block.get("text", "")).strip()
        if not text:
            return None
        context = {
            "text": text,
            "block_index": block_index,
            "source_order": story_block_source_order(block),
        }
        source_metadata = story_block_source_metadata(block)
        if source_metadata.get("source_id"):
            context["source_id"] = source_metadata["source_id"]
        if source_metadata.get("source_type"):
            context["source_type"] = source_metadata["source_type"]
        return context

    def flush_scene() -> None:
        if not current_scene:
            return
        scene_index = len(chunks)
        scene_lines: list[str] = []
        summary_lines: list[str] = []
        scene_annotations: dict[str, dict[str, str]] = {}
        scene_source_ids: list[str] = []
        scene_source_orders: list[int] = []
        scene_source_types: list[str] = []
        metadata = dict(doc.metadata)
        metadata["chunk_index"] = scene_index
        metadata["retrieval_mode"] = "hierarchical"
        metadata["scene_start_line"] = current_scene[0][0]
        metadata["chapter_summary"] = chapter_summary
        chapter_note_context = dict(active_chapter_note or {})
        metadata["chapter_note"] = str(chapter_note_context.get("text", "")).strip()
        if chapter_note_context:
            metadata["chapter_note_context"] = chapter_note_context
        metadata["scene_summaries"] = summary_lines

        line_chunks: list[LineChunk] = []
        for line_index, (block_index, block) in enumerate(current_scene):
            block_type = str(block.get("type", "")).strip()
            block_text = story_block_text(block)
            if not block_text:
                continue
            if block_type in {"summary", "paragraph_summary"}:
                summary_lines.append(str(block.get("text", "")).strip())
            scene_lines.append(block_text)
            source_metadata = story_block_source_metadata(block)
            source_id = source_metadata.get("source_id")
            source_order = source_metadata.get("source_order")
            source_type = source_metadata.get("source_type")
            if source_id:
                scene_source_ids.append(str(source_id))
            if isinstance(source_order, int):
                scene_source_orders.append(source_order)
            elif source_order not in (None, ""):
                try:
                    scene_source_orders.append(int(source_order))
                except (TypeError, ValueError):
                    pass
            if source_type:
                scene_source_types.append(str(source_type))
            annotations = story_block_annotations(block)
            annotation_text = story_block_annotation_text(block)
            for annotation in detect_story_annotation_spans(annotation_text, annotations, annotation_entries):
                scene_annotations.setdefault(annotation["term"], annotation)
            line_metadata = dict(metadata)
            line_metadata.update(
                {
                    "line_index": line_index,
                    "block_index": block_index,
                    "block_type": block_type,
                    "line_type": "dialogue" if block_type == "line" else block_type,
                    "speaker": str(block.get("speaker", "")).strip(),
                }
            )
            line_metadata.update(source_metadata)
            line_id = f"{doc.doc_id}::scene::{scene_index}::line::{line_index}"
            line_chunks.append(
                LineChunk(
                    line_id=line_id,
                    parent_id=f"{doc.doc_id}::scene::{scene_index}",
                    text=block_text,
                    line_index=line_index,
                    metadata=line_metadata,
                )
            )

        metadata["scene_summaries"] = summary_lines
        metadata["source_ids"] = dedupe_keep_order(scene_source_ids)
        metadata["source_types"] = dedupe_keep_order(scene_source_types)
        if scene_source_orders:
            metadata["source_order_start"] = min(scene_source_orders)
            metadata["source_order_end"] = max(scene_source_orders)
        metadata["annotations"] = [scene_annotations[term] for term in sorted(scene_annotations)]
        metadata.update(parse_scene_metadata([story_block_text(current_scene[0][1])]))
        text_parts = []
        if chapter_summary:
            text_parts.extend([f"[本章梗概]{chapter_summary}", ""])
        chapter_note = metadata.get("chapter_note", "")
        if chapter_note:
            text_parts.extend(["[本章注释]", chapter_note, ""])
        text_parts.extend(scene_lines)
        chunk = BlockChunk(
            chunk_id=f"{doc.doc_id}::scene::{scene_index}",
            text="\n".join(part for part in text_parts if part is not None).strip(),
            retrieval_text="\n".join(scene_lines).strip(),
            metadata=metadata,
            line_chunks=line_chunks,
        )
        chunks.append(chunk)

    for block_index, block in enumerate(blocks):
        block_type = str(block.get("type", "")).strip()
        if block_type == "chapter_note":
            flush_scene()
            current_scene = []
            active_chapter_note = make_chapter_note_context(block_index, block)
            append_premise_chunk(
                block_index=block_index,
                block=block,
                premise_type="chapter_note",
                text=str(block.get("text", "")),
                label="本章注释",
            )
            continue
        if block_type == "analysis" and block_index == 0:
            flush_scene()
            current_scene = []
            active_chapter_note = make_chapter_note_context(block_index, block)
            continue
        if block_type == "chapter_summary":
            continue
        if block_type == "scene_cast" and current_scene:
            flush_scene()
            current_scene = []
        current_scene.append((block_index, block))
    flush_scene()
    return chunks


def load_annotation_entries() -> list[dict[str, Any]]:
    try:
        from src.editor_v2 import build_world_annotation_library_v2

        return build_world_annotation_library_v2()
    except Exception:
        return []


def detect_story_annotation_spans(
    text: str,
    annotations: dict[str, Any],
    entries: list[dict[str, Any]],
) -> list[dict[str, str]]:
    definitions = {
        str(item.get("term", "")).strip(): str(item.get("definition", "")).strip()
        for item in entries
        if str(item.get("term", "")).strip()
    }
    output: list[dict[str, str]] = []
    seen: set[str] = set()

    try:
        from src.editor_v2 import detect_annotation_spans

        spans = detect_annotation_spans(
            text,
            entries,
            omissions=annotations.get("omissions", []),
        )
    except Exception:
        spans = []

    for span in spans:
        term = str(span.get("term", "")).strip()
        if not term or term in seen:
            continue
        seen.add(term)
        output.append({"term": term, "definition": definitions.get(term, "")})

    for term in annotations.get("manual_refs", []) or []:
        term = str(term).strip()
        if not term or term in seen:
            continue
        seen.add(term)
        output.append({"term": term, "definition": definitions.get(term, "")})

    return output


def build_story_chunks_from_editor_document(doc: KnowledgeDocument, document: dict[str, Any]) -> list[BlockChunk]:
    blocks = document.get("blocks", []) if isinstance(document.get("blocks"), list) else []
    annotation_entries = load_annotation_entries()
    chunks: list[BlockChunk] = []

    chapter_summary = ""
    for block in blocks:
        if str(block.get("type", "")).strip() == "chapter_summary":
            chapter_summary = str(block.get("text", "")).strip()
            if chapter_summary:
                break

    def make_chapter_note_context(block_index: int, block: dict[str, Any]) -> dict[str, Any] | None:
        text = str(block.get("text", "")).strip()
        if not text:
            return None
        context = {
            "text": text,
            "block_index": block_index,
            "source_order": story_block_source_order(block),
        }
        source_metadata = story_block_source_metadata(block)
        if source_metadata.get("source_id"):
            context["source_id"] = source_metadata["source_id"]
        if source_metadata.get("source_type"):
            context["source_type"] = source_metadata["source_type"]
        return context

    chapter_notes: list[dict[str, Any]] = []
    for block_index, block in enumerate(blocks):
        block_type = str(block.get("type", "")).strip()
        if block_type == "chapter_note" or (block_type == "analysis" and block_index == 0):
            context = make_chapter_note_context(block_index, block)
            if context:
                chapter_notes.append(context)

    def previous_chapter_note(block_index: int) -> dict[str, Any] | None:
        previous = [note for note in chapter_notes if int(note.get("block_index", -1)) < block_index]
        return dict(previous[-1]) if previous else None

    def included_chapter_notes(start: int, end: int) -> list[dict[str, Any]]:
        return [dict(note) for note in chapter_notes if start <= int(note.get("block_index", -1)) <= end]

    def source_order_sort_value(block_index: int) -> int:
        order = story_block_source_order(blocks[block_index])
        return order if order is not None else block_index

    def append_premise_chunk(block_index: int, block: dict[str, Any], premise_type: str, label: str) -> None:
        text = str(block.get("text", "")).strip()
        if not text:
            return
        keywords = story_block_keywords(block)
        metadata = dict(doc.metadata)
        metadata.update(story_block_source_metadata(block))
        if keywords:
            metadata["keywords"] = keywords
        metadata["chunk_index"] = len(chunks)
        metadata["retrieval_mode"] = "premise"
        metadata["premise_type"] = premise_type
        metadata["block_index"] = block_index
        metadata["scene_start_line"] = block_index
        metadata["chapter_summary"] = chapter_summary
        if premise_type != "chapter_note":
            note_context = previous_chapter_note(block_index)
            if note_context:
                metadata["chapter_note"] = str(note_context.get("text", "")).strip()
                metadata["chapter_note_context"] = note_context
        chunks.append(
            BlockChunk(
                chunk_id=f"{doc.doc_id}::premise::{premise_type}::{block_index}",
                text=f"[{label}]{text}",
                retrieval_text=retrieval_text_with_keywords(text, keywords),
                metadata=metadata,
            )
        )

    for block_index, block in enumerate(blocks):
        block_type = str(block.get("type", "")).strip()
        if block_type == "chapter_summary":
            append_premise_chunk(block_index, block, "chapter_summary", "\u672c\u7ae0\u6897\u6982")
        elif block_type == "chapter_note":
            append_premise_chunk(block_index, block, "chapter_note", "\u672c\u7ae0\u6ce8\u91ca")
        elif block_type in {"summary", "paragraph_summary"}:
            append_premise_chunk(block_index, block, "paragraph_summary", "\u6bb5\u843d\u6897\u6982")

    def segment_ranges(marker_types: set[str], *, include_first_prefix: bool) -> list[tuple[int, int]]:
        def excluded_from_boundary(block_index: int, block: dict[str, Any]) -> bool:
            block_type = str(block.get("type", "")).strip()
            return block_type in {"chapter_summary", "chapter_note"} or (block_type == "analysis" and block_index == 0)

        markers = [idx for idx, block in enumerate(blocks) if str(block.get("type", "")).strip() in marker_types]
        non_excluded = [
            idx
            for idx, block in enumerate(blocks)
            if not excluded_from_boundary(idx, block) and story_block_text(block)
        ]
        if not non_excluded:
            return []
        if not markers:
            return [(non_excluded[0], non_excluded[-1])]
        ranges: list[tuple[int, int]] = []
        if include_first_prefix:
            prefix_start_candidates = [idx for idx in non_excluded if idx <= markers[0]]
            if prefix_start_candidates:
                ranges.append((prefix_start_candidates[0], markers[0]))
        for prev, current in zip(markers, markers[1:]):
            if prev + 1 <= current:
                ranges.append((prev + 1, current))
        trailing_candidates = [idx for idx in non_excluded if idx > markers[-1]]
        if trailing_candidates:
            ranges.append((trailing_candidates[0], trailing_candidates[-1]))
        return [(start, end) for start, end in ranges if start <= end]

    def scene_segment_ranges() -> list[tuple[int, int]]:
        markers = [idx for idx, block in enumerate(blocks) if str(block.get("type", "")).strip() == "scene_cast"]
        non_empty = [idx for idx, block in enumerate(blocks) if story_block_text(block)]
        if not markers:
            non_excluded = [
                idx
                for idx in non_empty
                if str(blocks[idx].get("type", "")).strip() not in {"chapter_summary", "chapter_note"}
                and not (str(blocks[idx].get("type", "")).strip() == "analysis" and idx == 0)
            ]
            return [(non_excluded[0], non_excluded[-1])] if non_excluded else []
        ranges: list[tuple[int, int]] = []
        for current, following in zip(markers, markers[1:]):
            if current <= following - 1:
                ranges.append((current, following - 1))
        last = markers[-1]
        trailing = [idx for idx in non_empty if idx >= last]
        if trailing:
            ranges.append((last, trailing[-1]))
        return ranges

    def append_aggregate_chunk(start: int, end: int, aggregate_type: str, aggregate_index: int) -> None:
        items: list[tuple[int, dict[str, Any], str]] = []
        for block_index in range(start, end + 1):
            block = blocks[block_index]
            block_text = story_block_text(block)
            if block_text:
                items.append((block_index, block, block_text))
        if not items:
            return

        source_ids: list[str] = []
        source_orders: list[int] = []
        source_types: list[str] = []
        aggregate_keywords: list[str] = []
        aggregate_blocks: list[dict[str, Any]] = []
        aggregate_annotations: dict[str, dict[str, str]] = {}
        paragraph_summaries: list[str] = []
        line_chunks: list[LineChunk] = []
        note_context = previous_chapter_note(start)
        included_notes = included_chapter_notes(start, end)

        metadata = dict(doc.metadata)
        metadata["chunk_index"] = len(chunks)
        metadata["retrieval_mode"] = "aggregate"
        metadata["aggregate_type"] = aggregate_type
        metadata["aggregate_start"] = start
        metadata["aggregate_end"] = end
        metadata["scene_start_line"] = start
        metadata["chapter_summary"] = chapter_summary
        if note_context:
            metadata["chapter_note"] = str(note_context.get("text", "")).strip()
            metadata["chapter_note_context"] = note_context
        if included_notes:
            metadata["included_chapter_notes"] = included_notes

        for line_index, (block_index, block, block_text) in enumerate(items):
            block_type = str(block.get("type", "")).strip()
            source_metadata = story_block_source_metadata(block)
            source_id = source_metadata.get("source_id")
            source_order = story_block_source_order(block)
            source_type = source_metadata.get("source_type")
            keywords = story_block_keywords(block)
            if source_id:
                source_ids.append(str(source_id))
            if source_order is not None:
                source_orders.append(source_order)
            if source_type:
                source_types.append(str(source_type))
            aggregate_keywords.extend(keywords)
            if block_type in {"summary", "paragraph_summary"}:
                paragraph_summaries.append(str(block.get("text", "")).strip())
            annotations = story_block_annotations(block)
            annotation_text = story_block_annotation_text(block)
            for annotation in detect_story_annotation_spans(annotation_text, annotations, annotation_entries):
                aggregate_annotations.setdefault(annotation["term"], annotation)
            aggregate_blocks.append(
                {
                    "block_index": block_index,
                    "block_type": block_type,
                    "text": block_text,
                    "retrieval_text": retrieval_text_with_keywords(block_text, keywords),
                    "keywords": keywords,
                    "source_order": source_order_sort_value(block_index),
                }
            )
            line_metadata = dict(metadata)
            line_metadata.update(
                {
                    "line_index": line_index,
                    "block_index": block_index,
                    "block_type": block_type,
                    "line_type": "dialogue" if block_type == "line" else block_type,
                    "speaker": str(block.get("speaker", "")).strip(),
                }
            )
            line_metadata.update(source_metadata)
            line_chunks.append(
                LineChunk(
                    line_id=f"{doc.doc_id}::aggregate::{aggregate_type}::{aggregate_index}::line::{line_index}",
                    parent_id=f"{doc.doc_id}::aggregate::{aggregate_type}::{aggregate_index}",
                    text=block_text,
                    line_index=line_index,
                    retrieval_text=retrieval_text_with_keywords(block_text, keywords),
                    metadata=line_metadata,
                )
            )

        metadata["aggregate_blocks"] = aggregate_blocks
        metadata["scene_summaries"] = paragraph_summaries
        metadata["source_ids"] = dedupe_keep_order(source_ids)
        metadata["source_types"] = dedupe_keep_order(source_types)
        aggregate_keywords = dedupe_keep_order(aggregate_keywords)
        if aggregate_keywords:
            metadata["keywords"] = aggregate_keywords
        if source_orders:
            metadata["source_order_start"] = min(source_orders)
            metadata["source_order_end"] = max(source_orders)
        metadata["annotations"] = [aggregate_annotations[term] for term in sorted(aggregate_annotations)]
        first_scene_cast = next((text for _, block, text in items if str(block.get("type", "")).strip() == "scene_cast"), "")
        if first_scene_cast:
            metadata.update(parse_scene_metadata([first_scene_cast]))

        text_parts: list[str] = []
        if chapter_summary:
            text_parts.extend([f"[\u672c\u7ae0\u6897\u6982]{chapter_summary}", ""])
        if note_context:
            text_parts.extend(["[\u672c\u7ae0\u6ce8\u91ca]", str(note_context.get("text", "")).strip(), ""])
        text_parts.extend(item["text"] for item in aggregate_blocks)
        aggregate_text = "\n".join(part for part in text_parts if part is not None).strip()
        retrieval_text = "\n".join(item["retrieval_text"] for item in aggregate_blocks).strip()

        chunks.append(
            BlockChunk(
                chunk_id=f"{doc.doc_id}::aggregate::{aggregate_type}::{aggregate_index}",
                text=aggregate_text,
                retrieval_text=retrieval_text,
                metadata=metadata,
                line_chunks=line_chunks,
            )
        )

    for aggregate_index, (start, end) in enumerate(segment_ranges({"summary", "paragraph_summary"}, include_first_prefix=True)):
        append_aggregate_chunk(start, end, "paragraph", aggregate_index)
    for aggregate_index, (start, end) in enumerate(scene_segment_ranges()):
        append_aggregate_chunk(start, end, "scene", aggregate_index)

    return chunks


def build_single_chunk(doc: KnowledgeDocument, text: str, index: int) -> BlockChunk:
    metadata = dict(doc.metadata)
    metadata["chunk_index"] = index
    chunk_id = f"{doc.doc_id}::chunk::{index}"
    return BlockChunk(chunk_id=chunk_id, text=text, retrieval_text=text, metadata=metadata)


def build_flat_blank_line_chunks(doc: KnowledgeDocument, text: str) -> list[BlockChunk]:
    chunks: list[BlockChunk] = []
    for index, block in enumerate(split_by_blank_lines(text)):
        metadata = dict(doc.metadata)
        metadata["chunk_index"] = index
        chunk_id = f"{doc.doc_id}::chunk::{index}"
        chunks.append(BlockChunk(chunk_id=chunk_id, text=block, retrieval_text=block, metadata=metadata))
    return chunks


def build_flat_line_chunks(doc: KnowledgeDocument, text: str) -> list[BlockChunk]:
    chunks: list[BlockChunk] = []
    for index, line in enumerate(split_non_empty_lines(text)):
        metadata = dict(doc.metadata)
        metadata["chunk_index"] = index
        metadata["line_index"] = index
        chunk_id = f"{doc.doc_id}::chunk::{index}"
        chunks.append(BlockChunk(chunk_id=chunk_id, text=line, retrieval_text=line, metadata=metadata))
    return chunks


def build_hierarchical_scene_chunks(doc: KnowledgeDocument, text: str, line_mode: str) -> list[BlockChunk]:
    return [
        build_hierarchical_block_chunk(doc, block_text, block_index, line_mode)
        for block_index, block_text in enumerate(split_by_blank_lines(text))
    ]


def build_hierarchical_blank_line_chunks(doc: KnowledgeDocument, text: str, line_mode: str) -> list[BlockChunk]:
    return [
        build_hierarchical_block_chunk(doc, block_text, block_index, line_mode)
        for block_index, block_text in enumerate(split_by_blank_lines(text))
    ]


def build_hierarchical_block_chunk(
    doc: KnowledgeDocument,
    block_text: str,
    block_index: int,
    line_mode: str,
) -> BlockChunk:
    block_lines = split_non_empty_lines(block_text)
    chunk_id = f"{doc.doc_id}::block::{block_index}"
    metadata = dict(doc.metadata)
    metadata["chunk_index"] = block_index
    metadata["retrieval_mode"] = "hierarchical"

    if doc.category in {"main_story", "side_story"}:
        metadata.update(parse_scene_metadata(block_lines))
        metadata["scene_start_line"] = block_index * 1000

    block_chunk = BlockChunk(
        chunk_id=chunk_id,
        text=block_text.strip(),
        retrieval_text=block_text.strip(),
        metadata=metadata,
    )
    block_chunk.line_chunks = build_line_chunks(block_chunk, block_lines, line_mode)
    return block_chunk


def build_line_chunks(block_chunk: BlockChunk, block_lines: list[str], line_mode: str) -> list[LineChunk]:
    line_chunks: list[LineChunk] = []
    for line_index, line in enumerate(block_lines):
        if not line.strip():
            continue
        line_metadata = dict(block_chunk.metadata)
        line_metadata["line_index"] = line_index
        line_metadata["parent_chunk_id"] = block_chunk.chunk_id
        line_metadata["line_type"] = classify_line_type(line)
        line_id = f"{block_chunk.chunk_id}::line::{line_index}"
        line_chunks.append(
            LineChunk(
                line_id=line_id,
                parent_id=block_chunk.chunk_id,
                text=line.strip(),
                line_index=line_index,
                metadata=line_metadata,
            )
        )
    return line_chunks


def classify_line_type(line: str) -> str:
    stripped = line.strip()
    if stripped in {"→", "←", "←→"}:
        return "branch_marker"
    if stripped.startswith("【") and stripped.endswith("】"):
        return "narration"
    if "：" in stripped:
        return "dialogue"
    return "paragraph"


def document_to_dict(doc: KnowledgeDocument) -> dict:
    return {
        "doc_id": doc.doc_id,
        "path": doc.path,
        "category": doc.category,
        "title": doc.title,
        "retrieval_mode": doc.retrieval_mode,
        "metadata": doc.metadata,
        "chunks": [
            {
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "retrieval_text": chunk.retrieval_text,
                "metadata": chunk.metadata,
                "line_chunks": [asdict(line_chunk) for line_chunk in chunk.line_chunks],
            }
            for chunk in doc.chunks
        ],
    }


def build_metadata(root: Path = RAW_DATA_DIR) -> list[dict]:
    documents: list[dict] = []
    for path in sorted(root.rglob("*.editor.json")):
        documents.append(document_to_dict(build_document_from_editor_json(path, root=root)))
    return documents


def save_metadata(documents: list[dict], output_path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    documents = build_metadata()
    output_path = save_metadata(documents)
    print(f"metadata saved to {output_path}")


if __name__ == "__main__":
    main()
