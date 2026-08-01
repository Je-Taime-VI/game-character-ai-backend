import json

from src.build_metadata import KnowledgeDocument, build_document_from_editor_json, build_metadata, build_chunks_for_document, build_story_chunks_from_editor_document, story_block_annotation_text
from src.build_vector_db_with_metadata import flatten_documents


def test_story_text_uses_hierarchical_chunks():
    doc = KnowledgeDocument(
        doc_id="test",
        path="main/1-test.txt",
        category="main_story",
        title="1-test",
        retrieval_mode="hierarchical",
        metadata={"path": "main/1-test.txt", "knowledge_type": "main_story"},
    )

    chunks = build_chunks_for_document(
        doc,
        "scene one\nA: first line\n\nscene two\nB: second line",
    )

    assert len(chunks) == 2
    assert len(chunks[0].line_chunks) == 2


def test_structured_story_chunks_build_summary_premises_and_aggregate_lines():
    doc = KnowledgeDocument(
        doc_id="story",
        path="main/1-test.txt",
        category="main_story",
        title="1-test",
        retrieval_mode="hierarchical",
        metadata={"path": "main/1-test.txt", "knowledge_type": "main_story"},
    )
    document = {
        "blocks": [
            {"type": "analysis", "text": "chapter focus"},
            {"type": "scene_cast", "text": "scene one"},
            {"type": "line", "speaker": "A", "text": "first line"},
            {"type": "summary", "text": "summary one"},
            {"type": "scene_cast", "text": "scene two"},
            {"type": "line", "speaker": "B", "text": "second line"},
        ]
    }

    chunks = build_story_chunks_from_editor_document(doc, document)
    scene_chunks = [chunk for chunk in chunks if chunk.metadata.get("aggregate_type") == "scene"]
    paragraph_chunks = [chunk for chunk in chunks if chunk.metadata.get("aggregate_type") == "paragraph"]
    premise_chunks = [chunk for chunk in chunks if chunk.metadata.get("premise_type") == "paragraph_summary"]

    assert len(scene_chunks) == 2
    assert len(paragraph_chunks) == 2
    assert len(premise_chunks) == 1
    assert scene_chunks[0].metadata["chapter_note"] == "chapter focus"
    assert paragraph_chunks[0].metadata["scene_summaries"] == ["summary one"]
    assert [line.text for line in scene_chunks[0].line_chunks] == [
        "scene one",
        "A: first line",
        "[\u6bb5\u843d\u6897\u6982]summary one",
    ]


def test_story_block_text_labels_narration_and_branch_followup():
    doc = KnowledgeDocument(
        doc_id="story",
        path="main/1-test.txt",
        category="main_story",
        title="1-test",
        retrieval_mode="hierarchical",
        metadata={"path": "main/1-test.txt", "knowledge_type": "main_story"},
    )
    document = {
        "blocks": [
            {"type": "scene_cast", "text": "scene"},
            {"type": "narration", "text": "narration text"},
            {"type": "note", "text": "note text"},
            {
                "type": "branch",
                "speaker": "Player",
                "options": [
                    {
                        "label": "choice",
                        "children": [{"type": "line", "speaker": "A", "text": "after choice"}],
                    }
                ],
            },
        ]
    }

    chunks = build_story_chunks_from_editor_document(doc, document)
    scene_chunk = next(chunk for chunk in chunks if chunk.metadata.get("aggregate_type") == "scene")

    assert "[\u65c1\u767d]narration text" in scene_chunk.text
    assert "[\u6ce8\u91ca]note text" in scene_chunk.text
    assert "[\u5206\u652f\u540e\u7eed]A: after choice" in scene_chunk.text


def test_annotation_text_uses_raw_narration_without_display_label():
    block = {
        "type": "narration",
        "text": "《太空战士卡佳Ⅵ》《双星奇旅》都是角色扮演游戏。",
        "annotations": {"omissions": [{"term": "角", "start": 18, "end": 19}]},
    }

    assert story_block_annotation_text(block) == block["text"]
    assert not story_block_annotation_text(block).startswith("[\u65c1\u767d]")


def test_story_keywords_are_used_for_retrieval_but_not_display_text():
    doc = KnowledgeDocument(
        doc_id="story",
        path="main/1-test.txt",
        category="main_story",
        title="1-test",
        retrieval_mode="hierarchical",
        metadata={"path": "main/1-test.txt", "knowledge_type": "main_story"},
    )
    document = {
        "blocks": [
            {"type": "scene_cast", "text": "scene"},
            {
                "type": "line",
                "speaker": "A",
                "text": "first line",
                "meta": {"keywords": ["陆·赫斯", "星炬学院印象"]},
            },
        ]
    }

    chunks = build_story_chunks_from_editor_document(doc, document)
    scene_chunk = next(chunk for chunk in chunks if chunk.metadata.get("aggregate_type") == "scene")

    assert "陆·赫斯" not in scene_chunk.text
    assert "陆·赫斯" in scene_chunk.retrieval_text
    assert scene_chunk.line_chunks[1].text == "A: first line"
    assert "星炬学院印象" in scene_chunk.line_chunks[1].retrieval_text

    flat_entries, line_entries = flatten_documents(
        [
            {
                "chunks": [
                    {
                        "chunk_id": scene_chunk.chunk_id,
                        "text": scene_chunk.text,
                        "retrieval_text": scene_chunk.retrieval_text,
                        "metadata": scene_chunk.metadata,
                        "line_chunks": [
                            {
                                "line_id": scene_chunk.line_chunks[1].line_id,
                                "parent_id": scene_chunk.line_chunks[1].parent_id,
                                "text": scene_chunk.line_chunks[1].text,
                                "retrieval_text": scene_chunk.line_chunks[1].retrieval_text,
                                "metadata": scene_chunk.line_chunks[1].metadata,
                            }
                        ],
                    }
                ]
            }
        ]
    )
    assert "陆·赫斯" not in flat_entries[0]["text"]
    assert "陆·赫斯" in flat_entries[0]["retrieval_text"]
    assert "星炬学院印象" not in line_entries[0]["text"]
    assert "星炬学院印象" in line_entries[0]["retrieval_text"]


def test_non_story_editor_json_chunks_by_xlsx_blank_sections_without_txt(tmp_path):
    path = tmp_path / "角色" / "爱弥斯" / "角色故事.editor.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "blocks": [
                    {"type": "text_title", "text": "标题一", "meta": {"xlsx_section_index": 0, "source_order": 1}},
                    {"type": "text_body", "text": "正文一", "meta": {"xlsx_section_index": 0, "source_order": 2}},
                    {"type": "text_title", "text": "标题二", "meta": {"xlsx_section_index": 1, "source_order": 4}},
                    {"type": "text_body", "text": "正文二", "meta": {"xlsx_section_index": 1, "source_order": 5}},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    doc = build_document_from_editor_json(path, root=tmp_path)

    assert doc.category == "role_story"
    assert len(doc.chunks) == 2
    assert doc.chunks[0].text == "[文本标题] 标题一\n正文一"
    assert doc.chunks[0].metadata["source_order_start"] == 1
    assert doc.chunks[0].metadata["source_order_end"] == 2
    assert len(doc.chunks[0].line_chunks) == 2


def test_metadata_uses_non_story_editor_json_and_ignores_txt(tmp_path):
    role_dir = tmp_path / "角色" / "爱弥斯"
    role_dir.mkdir(parents=True)
    (role_dir / "个性语音.editor.json").write_text(
        json.dumps(
            {
                "blocks": [
                    {"type": "text_body", "text": "来自 editor json", "meta": {"xlsx_section_index": 0}},
                    {"type": "text_body", "text": "第二段", "meta": {"xlsx_section_index": 1}},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (role_dir / "个性语音.txt").write_text("来自 txt", encoding="utf-8")

    documents = build_metadata(root=tmp_path)
    voice_doc = next(item for item in documents if item["path"] == "角色/爱弥斯/个性语音.editor.json")

    assert all(not item["path"].endswith(".txt") for item in documents)
    assert [chunk["text"] for chunk in voice_doc["chunks"]] == ["来自 editor json", "第二段"]


def test_non_main_side_world_editor_json_also_uses_xlsx_sections(tmp_path):
    world_dir = tmp_path / "世界观"
    world_dir.mkdir()
    (world_dir / "全局世界观.editor.json").write_text(
        json.dumps(
            {
                "blocks": [
                    {"type": "text_title", "text": "设定一", "meta": {"xlsx_section_index": 0, "source_order": 1}},
                    {"type": "text_body", "text": "内容一", "meta": {"xlsx_section_index": 0, "source_order": 2}},
                    {"type": "text_title", "text": "设定二", "meta": {"xlsx_section_index": 1, "source_order": 4}},
                    {"type": "text_body", "text": "内容二", "meta": {"xlsx_section_index": 1, "source_order": 5}},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (world_dir / "全局世界观.txt").write_text("旧 TXT 内容", encoding="utf-8")

    documents = build_metadata(root=tmp_path)
    world_doc = next(item for item in documents if item["path"] == "世界观/全局世界观.editor.json")

    assert all(not item["path"].endswith(".txt") for item in documents)
    assert world_doc["category"] == "world"
    assert [chunk["text"] for chunk in world_doc["chunks"]] == [
        "[文本标题] 设定一\n内容一",
        "[文本标题] 设定二\n内容二",
    ]
