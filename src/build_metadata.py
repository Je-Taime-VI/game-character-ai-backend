from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


RAW_DATA_DIR = Path("data/raw")
DEFAULT_OUTPUT_PATH = Path("data/processed/metadata.json")

MAIN_STORY_DIRNAME = "主线"
SIDE_STORY_DIRNAME = "支线"
ROLE_DIRNAME = "角色"
WORLD_DIRNAME = "世界观"
EXPLORATION_REPORT_DIRNAME = "地区探索报告"


@dataclass
class LineChunk:
    line_id: str
    parent_id: str
    text: str
    line_index: int
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
    name = path_obj.name

    if MAIN_STORY_DIRNAME in parts:
        return "main_story"
    if SIDE_STORY_DIRNAME in parts:
        return "side_story"
    if WORLD_DIRNAME in parts and EXPLORATION_REPORT_DIRNAME in parts:
        return "world_exploration_report"
    if WORLD_DIRNAME in parts:
        return "world"
    if ROLE_DIRNAME in parts:
        if name == "个性语音.txt":
            return "role_personality_voice"
        if name == "基本信息.txt":
            return "role_basic_info"
        if name == "角色档案.txt" or name == "个人档案.txt":
            return "role_profile"
        if name == "角色故事.txt":
            return "role_story"
        if name in {"特殊料理.txt", "珍贵之物.txt"}:
            return "role_item"
        if "特殊文本" in parts:
            return "role_special_text"
        return "role_other"
    return "other"


def infer_retrieval_mode(category: str) -> str:
    if category in {"main_story", "side_story", "role_profile", "role_story", "role_special_text"}:
        return "hierarchical"
    return "flat"


def infer_story_document_kind(path: Path) -> str | None:
    if path.name == "简介.txt":
        return "summary"
    if path.name == "全文.txt":
        return "full"
    return None


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
    role_name = path.parts[-2] if ROLE_DIRNAME in path.parts else None

    metadata = {
        "path": rel_path,
        "knowledge_type": category,
        "source_name": path.name,
    }
    metadata.update(build_world_region_metadata(path, root))
    if role_name and category.startswith("role_"):
        metadata["role_name"] = role_name
    story_document_kind = infer_story_document_kind(path)
    if story_document_kind:
        metadata["story_document_kind"] = story_document_kind
        metadata["story_group"] = path.parent.name

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


def build_chunks_for_document(doc: KnowledgeDocument, text: str) -> list[BlockChunk]:
    category = doc.category

    if not text:
        return []

    if category == "world_exploration_report":
        return build_flat_line_chunks(doc, text)
    if category in {"main_story", "side_story"} and doc.metadata.get("story_document_kind") == "summary":
        return build_flat_blank_line_chunks(doc, text)
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
    for path in sorted(root.rglob("*.txt")):
        documents.append(document_to_dict(build_document(path, root=root)))
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
