from src.generate_role_permissions import DEFAULT_ORG_REGION_MAPPING, generate_permission_for_role
from src.permission_tree import build_permission_forest, extract_story_summaries_from_document, load_role_permission, normalize_story_premise_specs, normalize_story_segment_specs, save_role_permission
from src.retriever import Retriever


def test_affiliation_region_mapping_is_applied():
    role_info = {
        "role_name": "爱弥斯",
        "birthplace": "拉海洛",
        "affiliation": "星炬学院",
    }
    permission = generate_permission_for_role(role_info, DEFAULT_ORG_REGION_MAPPING, {})

    regions = {entry["region_path"] for entry in permission["allowed_region_layers"]}
    assert "罗伊冰原" in regions


def test_manual_region_overrides_are_preserved():
    role_info = {
        "role_name": "测试角色",
        "birthplace": "今州",
        "affiliation": "瑝珑",
    }
    manual_config = {
        "region_overrides": ["黎那汐塔"],
        "allowed_story_paths": ["主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt"],
    }

    permission = generate_permission_for_role(role_info, DEFAULT_ORG_REGION_MAPPING, manual_config)

    regions = {entry["region_path"] for entry in permission["allowed_region_layers"]}
    assert "黎那汐塔" in regions
    assert permission["allowed_story_paths"] == [
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt"
    ]


def test_manual_story_premises_are_preserved():
    role_info = {
        "role_name": "测试角色",
        "birthplace": "",
        "affiliation": "",
    }
    premise = {"path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt", "premise_type": "chapter_summary", "block_index": 0}

    permission = generate_permission_for_role(
        role_info,
        DEFAULT_ORG_REGION_MAPPING,
        {"allowed_story_premises": [premise]},
    )

    assert permission["allowed_story_premises"] == [premise]


def test_manual_story_segments_are_preserved():
    role_info = {
        "role_name": "测试角色",
        "birthplace": "",
        "affiliation": "",
    }
    segment = {
        "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
        "premise_type": "paragraph_summary",
        "block_index": 61,
        "aggregate_start": 2,
        "aggregate_end": 61,
    }

    permission = generate_permission_for_role(
        role_info,
        DEFAULT_ORG_REGION_MAPPING,
        {"allowed_story_segments": [segment]},
    )

    assert permission["allowed_story_segments"] == [segment]


def test_permission_tree_hides_workbooks_and_excel_temp_files(tmp_path):
    for folder in ("角色", "世界观", "主线", "支线"):
        (tmp_path / folder).mkdir()
    (tmp_path / "主线" / "33-远航星.txt").write_text("txt", encoding="utf-8")
    (tmp_path / "主线" / "33-远航星.editor.json").write_text("{}", encoding="utf-8")
    (tmp_path / "主线" / "33-远航星.xlsx").write_text("xlsx", encoding="utf-8")
    (tmp_path / "主线" / "~$33-远航星.xlsx").write_text("lock", encoding="utf-8")

    forest = build_permission_forest(tmp_path)
    paths = {child["path"] for child in forest["主线"]["children"]}

    assert "主线/33-远航星.txt" in paths
    assert "主线/33-远航星.editor.json" in paths
    assert "主线/33-远航星.xlsx" not in paths
    assert "主线/~$33-远航星.xlsx" not in paths


def test_region_permission_includes_parent_layers():
    role_info = {
        "role_name": "测试角色",
        "birthplace": "",
        "affiliation": "今州",
    }

    permission = generate_permission_for_role(role_info, DEFAULT_ORG_REGION_MAPPING, {})

    regions = {entry["region_path"] for entry in permission["allowed_region_layers"]}
    assert "瑝珑" in regions
    assert "瑝珑/今州" in regions


def test_extra_role_paths_are_merged_into_allowed_role_paths():
    role_info = {
        "role_name": "测试角色",
        "birthplace": "",
        "affiliation": "",
    }

    permission = generate_permission_for_role(
        role_info,
        DEFAULT_ORG_REGION_MAPPING,
        {"extra_role_paths": ["角色/秧秧/角色档案.txt"]},
    )

    assert "角色/测试角色" in permission["allowed_role_paths"]
    assert "角色/秧秧/角色档案.txt" in permission["allowed_role_paths"]


def test_folder_path_spec_matches_descendants():
    assert Retriever._path_matches_spec(
        "世界观/地区信息/瑝珑/今州/地区探索报告/云陵谷.txt",
        "世界观/地区信息/瑝珑",
    )


def test_txt_path_spec_matches_only_exact_file():
    assert Retriever._path_matches_spec(
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
    )
    assert not Retriever._path_matches_spec(
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/??.txt",
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
    )


def test_direct_children_wildcard_matches_only_current_folder_txt():
    assert Retriever._path_matches_spec(
        "世界观/地区信息/瑝珑/今州.txt",
        "世界观/地区信息/瑝珑/*",
    )
    assert not Retriever._path_matches_spec(
        "世界观/地区信息/瑝珑/今州/地区探索报告/云陵谷.txt",
        "世界观/地区信息/瑝珑/*",
    )


def test_recursive_wildcard_matches_descendants():
    assert Retriever._path_matches_spec(
        "世界观/地区信息/瑝珑/今州/地区探索报告/云陵谷.txt",
        "世界观/地区信息/瑝珑/**",
    )


def test_object_spec_supports_frontend_tree_modes():
    assert Retriever._path_matches_spec(
        "世界观/地区信息/瑝珑/今州.txt",
        {"path": "世界观/地区信息/瑝珑", "mode": "direct_children_txt"},
    )
    assert not Retriever._path_matches_spec(
        "世界观/地区信息/瑝珑/今州/地区探索报告/云陵谷.txt",
        {"path": "世界观/地区信息/瑝珑", "mode": "direct_children_txt"},
    )
    assert Retriever._path_matches_spec(
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt",
        {"path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处.txt", "mode": "exact"},
    )


def test_story_premise_permission_matches_only_requested_summary():
    permission = {
        "allowed_role_paths": [],
        "allowed_world_paths": [],
        "allowed_story_paths": [],
        "allowed_region_layers": [],
        "allowed_story_premises": [
            {"path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt", "premise_type": "chapter_summary", "block_index": 1}
        ],
    }
    allowed_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "premise",
            "premise_type": "chapter_summary",
            "block_index": 1,
        }
    }
    blocked_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "aggregate",
            "premise_type": "chapter_summary",
            "block_index": 1,
        }
    }

    assert Retriever._chunk_allowed_by_permission(allowed_chunk, permission)
    assert not Retriever._chunk_allowed_by_permission(blocked_chunk, permission)


def test_story_segment_permission_matches_contained_aggregate_only():
    permission = {
        "allowed_role_paths": [],
        "allowed_world_paths": [],
        "allowed_story_paths": [],
        "allowed_region_layers": [],
        "allowed_story_premises": [],
        "allowed_story_segments": [
            {
                "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
                "premise_type": "paragraph_summary",
                "block_index": 61,
                "aggregate_start": 2,
                "aggregate_end": 61,
            }
        ],
    }
    allowed_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "aggregate",
            "aggregate_type": "paragraph",
            "aggregate_start": 2,
            "aggregate_end": 61,
        }
    }
    too_wide_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "aggregate",
            "aggregate_type": "paragraph",
            "aggregate_start": 2,
            "aggregate_end": 125,
        }
    }
    overlapping_scene_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "aggregate",
            "aggregate_type": "scene",
            "aggregate_start": 9,
            "aggregate_end": 62,
        }
    }
    unrelated_scene_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "aggregate",
            "aggregate_type": "scene",
            "aggregate_start": 126,
            "aggregate_end": 180,
        }
    }
    premise_chunk = {
        "metadata": {
            "path": "主线/33-第三章-驶向尚未点亮之星-第三幕-远航星.txt",
            "retrieval_mode": "premise",
            "premise_type": "paragraph_summary",
            "block_index": 61,
        }
    }

    assert Retriever._chunk_allowed_by_permission(allowed_chunk, permission)
    assert not Retriever._chunk_allowed_by_permission(too_wide_chunk, permission)
    assert Retriever._chunk_allowed_by_permission(overlapping_scene_chunk, permission)
    assert not Retriever._chunk_allowed_by_permission(unrelated_scene_chunk, permission)
    assert not Retriever._chunk_allowed_by_permission(premise_chunk, permission)


def test_extract_story_summaries_labels_chapter_and_paragraphs():
    document = {
        "blocks": [
            {"type": "chapter_summary", "text": "whole"},
            {"type": "scene_cast", "text": "scene"},
            {"type": "line", "speaker": "A", "text": "before one"},
            {"type": "paragraph_summary", "text": "one"},
            {"type": "line", "speaker": "A", "text": "before two"},
            {"type": "paragraph_summary", "text": "two"},
        ]
    }

    summaries = extract_story_summaries_from_document("主线/a.txt", document)

    assert [item["label"] for item in summaries] == ["本章梗概", "段落梗概1", "段落梗概2"]
    assert [item["text"] for item in summaries] == ["whole", "one", "two"]
    assert [(item.get("aggregate_start"), item.get("aggregate_end")) for item in summaries[1:]] == [(1, 3), (4, 5)]


def test_normalize_story_premise_specs_drops_invalid_and_dedupes():
    specs = normalize_story_premise_specs(
        [
            {"path": "主线/a.txt", "premise_type": "chapter_summary", "block_index": "1"},
            {"path": "主线/a.txt", "premise_type": "chapter_summary", "block_index": 1},
            {"path": "主线/a.txt", "premise_type": "line", "block_index": 2},
        ]
    )

    assert specs == [{"path": "主线/a.txt", "premise_type": "chapter_summary", "block_index": 1}]


def test_normalize_story_segment_specs_drops_invalid_and_dedupes():
    specs = normalize_story_segment_specs(
        [
            {"path": "主线/a.txt", "premise_type": "paragraph_summary", "block_index": "4", "aggregate_start": "2", "aggregate_end": "4"},
            {"path": "主线/a.txt", "premise_type": "paragraph_summary", "block_index": 4, "aggregate_start": 2, "aggregate_end": 4},
            {"path": "主线/a.txt", "premise_type": "paragraph_summary", "block_index": 5, "aggregate_start": 8, "aggregate_end": 4},
        ]
    )

    assert specs == [
        {
            "path": "主线/a.txt",
            "premise_type": "paragraph_summary",
            "block_index": 4,
            "aggregate_start": 2,
            "aggregate_end": 4,
        }
    ]


def test_saving_story_segments_also_saves_matching_premises(tmp_path):
    segment = {
        "path": "主线/a.txt",
        "premise_type": "paragraph_summary",
        "block_index": 4,
        "aggregate_start": 2,
        "aggregate_end": 4,
    }

    save_role_permission("RoleA", {"allowed_story_segments": [segment]}, permissions_dir=tmp_path)
    permission = load_role_permission("RoleA", permissions_dir=tmp_path)

    assert permission["allowed_story_segments"] == [segment]
    assert permission["allowed_story_premises"] == [
        {"path": "主线/a.txt", "premise_type": "paragraph_summary", "block_index": 4}
    ]
