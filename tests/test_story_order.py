from src.retriever import Retriever


def test_main_and_side_story_prefix_order():
    main_meta = {
        "knowledge_type": "main_story",
        "path": "主线/35-第三章-驶向尚未点亮之星.txt",
        "chunk_index": 0,
    }
    side_meta = {
        "knowledge_type": "side_story",
        "path": "支线/35-1诸星密语/诸星密语-陆·赫斯.txt",
        "chunk_index": 0,
    }

    assert Retriever._story_time_sort_key(main_meta) < Retriever._story_time_sort_key(side_meta)


def test_story_chunks_keep_source_order_inside_same_file():
    earlier_scene = {
        "knowledge_type": "main_story",
        "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
        "scene_start_line": 10,
        "chunk_index": 0,
    }
    later_scene = {
        "knowledge_type": "main_story",
        "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
        "scene_start_line": 50,
        "chunk_index": 1,
    }

    assert Retriever._story_time_sort_key(earlier_scene) < Retriever._story_time_sort_key(later_scene)


def test_non_story_meta_has_no_story_time_key():
    meta = {
        "knowledge_type": "character",
        "path": "角色/陆·赫斯/角色档案.txt",
        "chunk_index": 0,
    }

    assert Retriever._story_time_sort_key(meta) is None


def test_hierarchical_results_sort_by_score_then_match_count():
    low_score_more_hits = {
        "match_type": "hierarchical",
        "score": 0.80,
        "match_count": 5,
        "metadata": {
            "knowledge_type": "main_story",
            "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
            "chunk_index": 1,
            "scene_start_line": 100,
        },
        "chunk_id": "b",
    }
    high_score_fewer_hits = {
        "match_type": "hierarchical",
        "score": 0.90,
        "match_count": 1,
        "metadata": {
            "knowledge_type": "main_story",
            "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
            "chunk_index": 0,
            "scene_start_line": 0,
        },
        "chunk_id": "a",
    }

    ordered = sorted(
        [low_score_more_hits, high_score_fewer_hits],
        key=Retriever._result_sort_key,
    )

    assert ordered[0]["chunk_id"] == "a"


def test_high_score_results_are_selected_before_chronological_ordering():
    early_low_score = {
        "match_type": "hierarchical",
        "score": 0.70,
        "metadata": {"knowledge_type": "main_story", "path": "主线/1-a.txt", "scene_start_line": 0, "chunk_index": 0},
        "chunk_id": "early_low",
    }
    early_high_score = {
        "match_type": "hierarchical",
        "score": 0.91,
        "metadata": {"knowledge_type": "main_story", "path": "主线/1-a.txt", "scene_start_line": 0, "chunk_index": 0},
        "chunk_id": "early_high",
    }
    later_high_score = {
        "match_type": "hierarchical",
        "score": 0.92,
        "metadata": {"knowledge_type": "main_story", "path": "主线/2-b.txt", "scene_start_line": 0, "chunk_index": 0},
        "chunk_id": "later_high",
    }

    selected = Retriever._select_high_score_results([early_low_score, later_high_score, early_high_score], limit=2)
    ordered = sorted(selected, key=Retriever._chronological_result_sort_key)

    assert [item["chunk_id"] for item in selected] == ["later_high", "early_high"]
    assert [item["chunk_id"] for item in ordered] == ["early_high", "later_high"]


def test_annotation_definitions_are_appended_once_across_results():
    results = [
        {
            "chunk_id": "a",
            "text": "scene a",
            "metadata": {"annotations": [{"term": "Term", "definition": "Definition"}]},
        },
        {
            "chunk_id": "b",
            "text": "scene b",
            "metadata": {"annotations": [{"term": "Term", "definition": "Definition"}]},
        },
    ]

    output = Retriever._append_deduped_annotations(results)

    assert "Term: Definition" in output[0]["text"]
    assert "Term: Definition" not in output[1]["text"]


class FakeIndex:
    def search(self, query_vector, top_k):
        return [[0.95]], [[0]]


def test_line_hit_returns_full_parent_paragraph():
    retriever = Retriever.__new__(Retriever)
    retriever.line_index = FakeIndex()
    retriever.line_entries = [
        {
            "id": "line-1",
            "text": "single high-score sentence",
            "metadata": {"line_index": 1},
            "parent_chunk_id": "scene-1",
            "parent_text": "scene title\nsingle high-score sentence\nnext sentence for context",
            "parent_metadata": {"knowledge_type": "main_story", "path": "main/1.txt"},
        }
    ]
    retriever.block_by_id = {}

    results = retriever._search_hierarchical([[0.0]], top_k=1, allowed_chunk_ids=None)

    assert results[0]["chunk_id"] == "scene-1"
    assert results[0]["matched_lines"] == ["single high-score sentence"]
    assert results[0]["text"] == "scene title\nsingle high-score sentence\nnext sentence for context"


def test_dedupe_prefers_full_parent_result_with_matched_lines_on_tie():
    retriever = Retriever.__new__(Retriever)
    flat_parent = {
        "chunk_id": "scene-1",
        "text": "single high-score sentence",
        "score": 0.95,
        "match_type": "flat",
    }
    hierarchical_parent = {
        "chunk_id": "scene-1",
        "text": "scene title\nsingle high-score sentence\nnext sentence for context",
        "score": 0.95,
        "match_type": "hierarchical",
        "matched_lines": ["single high-score sentence"],
        "match_count": 1,
    }

    deduped = retriever._dedupe_results([flat_parent, hierarchical_parent])

    assert deduped == [hierarchical_parent]


def test_matched_lines_expand_to_neighbor_blocks_without_chaining():
    metadata = {
        "aggregate_blocks": [
            {"block_index": index, "block_type": "line", "text": f"block {index}"}
            for index in range(1, 9)
        ]
    }
    matched_entries = [
        {"text": "block 4", "metadata": {"block_index": 4}},
        {"text": "block 5", "metadata": {"block_index": 5}},
    ]

    expanded = Retriever._expand_matched_lines(metadata, matched_entries, radius=2)

    assert expanded == ["block 2", "block 3", "block 4", "block 5", "block 6", "block 7"]


def test_matched_branch_expansion_keeps_branch_as_single_block():
    metadata = {
        "aggregate_blocks": [
            {"block_index": 1, "block_type": "line", "text": "before"},
            {"block_index": 2, "block_type": "branch", "text": "whole branch"},
            {"block_index": 3, "block_type": "line", "text": "after"},
        ]
    }

    expanded = Retriever._expand_matched_lines(
        metadata,
        [{"text": "whole branch", "metadata": {"block_index": 2}}],
        radius=2,
    )

    assert expanded == ["whole branch"]


def test_merged_story_result_dedupes_repeated_matched_lines():
    def result(chunk_id, start, end, matched_lines):
        return {
            "chunk_id": chunk_id,
            "text": chunk_id,
            "score": 0.9,
            "match_type": "hierarchical",
            "matched_lines": matched_lines,
            "match_count": len(matched_lines),
            "metadata": {
                "knowledge_type": "main_story",
                "path": "main/a.txt",
                "retrieval_mode": "aggregate",
                "aggregate_start": start,
                "aggregate_end": end,
                "aggregate_blocks": [
                    {"block_index": index, "text": f"block {index}"}
                    for index in range(start, end + 1)
                ],
            },
        }

    merged = Retriever._compose_merged_story_result(
        result("best", 2, 4, ["same line"]),
        [
            result("best", 2, 4, ["same line"]),
            result("overlap", 3, 5, ["same line", "other line"]),
        ],
    )

    assert merged["matched_lines"] == ["same line", "other line"]
    assert merged["match_count"] == 2


def test_story_results_are_limited_to_most_relevant_scene():
    top_story = {
        "chunk_id": "story-top",
        "score": 0.95,
        "metadata": {"knowledge_type": "main_story", "path": "main/2.txt"},
    }
    lower_story = {
        "chunk_id": "story-lower",
        "score": 0.90,
        "metadata": {"knowledge_type": "main_story", "path": "main/1.txt"},
    }
    world_fact = {
        "chunk_id": "world-fact",
        "score": 0.93,
        "metadata": {"knowledge_type": "world", "path": "world/fact.txt"},
    }

    focused = Retriever._limit_story_results([lower_story, world_fact, top_story], limit=1)

    assert focused == [top_story, world_fact]


def test_chronological_sort_key_can_mix_story_and_non_story_results():
    story = {
        "chunk_id": "story",
        "score": 0.95,
        "match_type": "hierarchical",
        "metadata": {"knowledge_type": "main_story", "path": "main/1.txt", "scene_start_line": 0},
    }
    world = {
        "chunk_id": "world",
        "score": 0.97,
        "match_type": "hierarchical",
        "metadata": {"knowledge_type": "world", "path": "world/fact.txt"},
    }

    ordered = sorted([world, story], key=Retriever._chronological_result_sort_key)

    assert ordered == [story, world]
