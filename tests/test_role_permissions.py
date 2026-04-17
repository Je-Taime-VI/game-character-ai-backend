from src.generate_role_permissions import DEFAULT_ORG_REGION_MAPPING, generate_permission_for_role
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
        "allowed_story_paths": ["主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt"],
    }

    permission = generate_permission_for_role(role_info, DEFAULT_ORG_REGION_MAPPING, manual_config)

    regions = {entry["region_path"] for entry in permission["allowed_region_layers"]}
    assert "黎那汐塔" in regions
    assert permission["allowed_story_paths"] == [
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt"
    ]


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
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt",
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt",
    )
    assert not Retriever._path_matches_spec(
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.txt",
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt",
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
        "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt",
        {"path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt", "mode": "exact"},
    )
