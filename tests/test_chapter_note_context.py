from src.build_metadata import KnowledgeDocument, build_story_chunks_from_editor_document
from src.chat import CharacterChat
from src.retriever import Retriever


def test_repeated_chapter_notes_apply_to_following_story_regions():
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
            {"type": "chapter_note", "text": "first premise", "meta": {"source_order": 2}},
            {"type": "scene_cast", "text": "scene one", "meta": {"source_order": 400}},
            {"type": "line", "speaker": "A", "text": "middle line", "meta": {"source_order": 600}},
            {"type": "chapter_note", "text": "second premise", "meta": {"source_order": 1000}},
            {"type": "scene_cast", "text": "scene two", "meta": {"source_order": 1040}},
            {"type": "line", "speaker": "B", "text": "later line", "meta": {"source_order": 1050}},
        ]
    }

    chunks = build_story_chunks_from_editor_document(doc, document)

    scene_chunks = [chunk for chunk in chunks if chunk.metadata.get("aggregate_type") == "scene"]
    premise_chunks = [chunk for chunk in chunks if chunk.metadata.get("retrieval_mode") == "premise"]

    assert len(scene_chunks) == 2
    assert len(premise_chunks) == 2
    assert premise_chunks[0].metadata["premise_type"] == "chapter_note"
    assert premise_chunks[0].retrieval_text == "first premise"
    assert scene_chunks[0].metadata["chapter_note"] == "first premise"
    assert scene_chunks[0].metadata["chapter_note_context"]["source_order"] == 2
    assert scene_chunks[1].metadata["chapter_note"] == "second premise"
    assert scene_chunks[1].metadata["chapter_note_context"]["source_order"] == 1000
    assert "first premise" in scene_chunks[0].text
    assert "second premise" in scene_chunks[0].text
    assert scene_chunks[0].metadata["included_chapter_notes"][0]["text"] == "second premise"
    assert "second premise" in scene_chunks[1].text


def test_prompt_keeps_each_result_chapter_note_as_premise():
    chat = CharacterChat.__new__(CharacterChat)
    prompt = chat._build_prompt(
        "Role",
        "question",
        [
            {
                "chunk_id": "scene-a",
                "text": "[\u672c\u7ae0\u6ce8\u91ca]\nfirst premise\nscene one\nA: middle",
                "metadata": {"path": "main/a.txt", "chapter_note": "first premise"},
                "score": 0.9,
                "match_type": "hierarchical",
            },
            {
                "chunk_id": "scene-b",
                "text": "[\u672c\u7ae0\u6ce8\u91ca]\nsecond premise\nscene two\nB: later",
                "metadata": {"path": "main/a.txt", "chapter_note": "second premise"},
                "score": 0.8,
                "match_type": "hierarchical",
            },
        ],
    )

    assert "[\u672c\u7ae0\u6ce8\u91ca]\nfirst premise" in prompt
    assert "[\u672c\u7ae0\u6ce8\u91ca]\nsecond premise" in prompt


def test_chapter_summary_is_included_for_premise_result():
    chat = CharacterChat.__new__(CharacterChat)
    prompt = chat._build_prompt(
        "Role",
        "question",
        [
            {
                "chunk_id": "note-a",
                "text": "[\u672c\u7ae0\u6ce8\u91ca]\nfirst premise",
                "metadata": {
                    "path": "main/a.txt",
                    "retrieval_mode": "premise",
                    "premise_type": "chapter_note",
                    "chapter_summary": "whole chapter summary",
                    "chapter_note": "first premise",
                },
                "score": 0.9,
                "match_type": "flat",
            },
        ],
    )

    assert "[\u672c\u7ae0\u6897\u6982]whole chapter summary" in prompt
    assert "[\u672c\u7ae0\u6ce8\u91ca]\nfirst premise" in prompt


def test_premise_results_do_not_consume_story_scene_limit():
    scene = {
        "chunk_id": "scene",
        "score": 0.9,
        "metadata": {"knowledge_type": "main_story", "path": "main/a.txt"},
    }
    premise = {
        "chunk_id": "premise",
        "score": 0.95,
        "metadata": {
            "knowledge_type": "main_story",
            "path": "main/a.txt",
            "retrieval_mode": "premise",
            "premise_type": "chapter_note",
        },
    }
    world = {
        "chunk_id": "world",
        "score": 0.8,
        "metadata": {"knowledge_type": "world", "path": "world/a.txt"},
    }

    focused = Retriever._limit_story_results([premise, scene, world], limit=1)

    assert focused == [scene, premise, world]


def test_story_builds_summary_premises_and_complementary_aggregates():
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
            {"type": "chapter_summary", "text": "chapter summary"},
            {"type": "chapter_note", "text": "chapter note"},
            {"type": "scene_cast", "text": "place one"},
            {"type": "line", "speaker": "A", "text": "line one"},
            {"type": "paragraph_summary", "text": "paragraph one"},
            {"type": "scene_cast", "text": "place two"},
            {"type": "line", "speaker": "B", "text": "line two"},
        ]
    }

    chunks = build_story_chunks_from_editor_document(doc, document)
    premise_types = [chunk.metadata.get("premise_type") for chunk in chunks if chunk.metadata.get("retrieval_mode") == "premise"]
    paragraph_ranges = [
        (chunk.metadata["aggregate_start"], chunk.metadata["aggregate_end"])
        for chunk in chunks
        if chunk.metadata.get("aggregate_type") == "paragraph"
    ]
    scene_ranges = [
        (chunk.metadata["aggregate_start"], chunk.metadata["aggregate_end"])
        for chunk in chunks
        if chunk.metadata.get("aggregate_type") == "scene"
    ]

    assert premise_types == ["chapter_summary", "chapter_note", "paragraph_summary"]
    assert paragraph_ranges == [(2, 4), (5, 6)]
    assert scene_ranges == [(2, 4), (5, 6)]


def test_story_aggregate_merge_uses_paragraph_center_with_scene_supplements():
    def result(chunk_id, start, end, score, aggregate_type):
        return {
            "chunk_id": chunk_id,
            "text": f"{start}-{end}",
            "score": score,
            "match_type": "hierarchical",
            "metadata": {
                "knowledge_type": "main_story",
                "path": "main/a.txt",
                "retrieval_mode": "aggregate",
                "aggregate_type": aggregate_type,
                "aggregate_start": start,
                "aggregate_end": end,
                "chapter_summary": "summary",
                "aggregate_blocks": [
                    {"block_index": index, "text": f"block {index}"}
                    for index in range(start, end + 1)
                ],
            },
        }

    focused = Retriever._focus_story_results(
        [
            result("c-e", 3, 5, 0.80, "paragraph"),
            result("d-h", 4, 8, 0.82, "scene"),
            result("f-j", 6, 10, 0.99, "paragraph"),
            result("i-k", 9, 11, 0.83, "scene"),
        ],
        limit=1,
    )

    assert len(focused) == 1
    assert focused[0]["metadata"]["aggregate_start"] == 4
    assert focused[0]["metadata"]["aggregate_end"] == 11
    assert "block 4" in focused[0]["text"]
    assert "block 11" in focused[0]["text"]
    assert "block 3" not in focused[0]["text"]


def test_scene_hit_prefers_paragraph_containing_matched_block():
    def result(chunk_id, start, end, score, aggregate_type, matched_block_indices=None):
        return {
            "chunk_id": chunk_id,
            "text": f"{start}-{end}",
            "score": score,
            "match_type": "hierarchical",
            "matched_block_indices": matched_block_indices or [],
            "metadata": {
                "knowledge_type": "main_story",
                "path": "main/a.txt",
                "retrieval_mode": "aggregate",
                "aggregate_type": aggregate_type,
                "aggregate_start": start,
                "aggregate_end": end,
                "chapter_summary": "summary",
                "aggregate_blocks": [
                    {"block_index": index, "text": f"block {index}"}
                    for index in range(start, end + 1)
                ],
            },
        }

    focused = Retriever._focus_story_results(
        [
            result("c-e", 3, 5, 0.80, "paragraph"),
            result("d-h", 4, 8, 0.99, "scene", matched_block_indices=[7]),
            result("f-j", 6, 10, 0.80, "paragraph"),
            result("i-k", 9, 11, 0.70, "scene"),
        ],
        limit=1,
    )

    assert focused[0]["metadata"]["aggregate_start"] == 4
    assert focused[0]["metadata"]["aggregate_end"] == 11
    assert "block 3" not in focused[0]["text"]
    assert "block 10" in focused[0]["text"]


def test_scene_hit_falls_back_to_largest_overlap_before_score():
    def result(chunk_id, start, end, score, aggregate_type):
        return {
            "chunk_id": chunk_id,
            "text": f"{start}-{end}",
            "score": score,
            "match_type": "hierarchical",
            "metadata": {
                "knowledge_type": "main_story",
                "path": "main/a.txt",
                "retrieval_mode": "aggregate",
                "aggregate_type": aggregate_type,
                "aggregate_start": start,
                "aggregate_end": end,
                "chapter_summary": "summary",
                "aggregate_blocks": [
                    {"block_index": index, "text": f"block {index}"}
                    for index in range(start, end + 1)
                ],
            },
        }

    focused = Retriever._focus_story_results(
        [
            result("a-b", 1, 2, 0.80, "paragraph"),
            result("c-h", 3, 8, 0.70, "paragraph"),
            result("b-g", 2, 7, 0.99, "scene"),
        ],
        limit=1,
    )

    assert focused[0]["metadata"]["aggregate_start"] == 2
    assert focused[0]["metadata"]["aggregate_end"] == 8
    assert "block 8" in focused[0]["text"]


def test_summary_premise_is_dropped_when_same_story_aggregate_is_selected():
    aggregate = {
        "chunk_id": "story-aggregate",
        "text": "story text",
        "score": 0.90,
        "metadata": {
            "knowledge_type": "main_story",
            "path": "main/a.txt",
            "retrieval_mode": "aggregate",
            "aggregate_start": 1,
            "aggregate_end": 3,
            "aggregate_blocks": [{"block_index": 1, "text": "story text"}],
        },
    }
    paragraph_summary = {
        "chunk_id": "paragraph-summary",
        "text": "summary text",
        "score": 0.95,
        "metadata": {
            "knowledge_type": "main_story",
            "path": "main/a.txt",
            "retrieval_mode": "premise",
            "premise_type": "paragraph_summary",
        },
    }
    chapter_note = {
        "chunk_id": "chapter-note",
        "text": "note text",
        "score": 0.80,
        "metadata": {
            "knowledge_type": "main_story",
            "path": "main/a.txt",
            "retrieval_mode": "premise",
            "premise_type": "chapter_note",
        },
    }

    focused = Retriever._focus_story_results([paragraph_summary, chapter_note, aggregate], limit=1)

    assert paragraph_summary not in focused
    assert chapter_note in focused
    assert focused[0]["chunk_id"] == "story-aggregate"
