from src.retriever import Retriever


def test_main_and_side_story_prefix_order():
    main_meta = {
        "knowledge_type": "main_story",
        "path": "主线/35-第三章-驶向尚未点亮之星/全文.txt",
        "chunk_index": 0,
    }
    side_meta = {
        "knowledge_type": "side_story",
        "path": "支线/35-1诸星密语/诸星密语-陆·赫斯/全文.txt",
        "chunk_index": 0,
    }

    assert Retriever._story_time_sort_key(main_meta) < Retriever._story_time_sort_key(side_meta)


def test_story_chunks_keep_source_order_inside_same_file():
    earlier_scene = {
        "knowledge_type": "main_story",
        "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.txt",
        "scene_start_line": 10,
        "chunk_index": 0,
    }
    later_scene = {
        "knowledge_type": "main_story",
        "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.txt",
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
            "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.txt",
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
            "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.txt",
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
