from src.chat import CharacterChat


def test_scene_cleanup_keeps_facts_and_dialogue():
    scene_text = """【场景：办公室内】【角色：陆·赫斯，西格莉卡】
【回忆开始】
【娜波摩背后向陆·赫斯开枪，陆·赫斯躲开，昏迷的魏尔伦被枪杀】
陆·赫斯（拿出糖果）：来，吃颗糖？
【娜波摩离开】
"""

    cleaned = CharacterChat._summarize_scene_for_prompt(scene_text)

    assert "场景：" not in cleaned
    assert "事实摘要：" in cleaned
    assert "时间标记：回忆开始" in cleaned
    assert "事实：娜波摩背后向陆·赫斯开枪，陆·赫斯躲开，昏迷的魏尔伦被枪杀" in cleaned
    assert "相关对白：" in cleaned
    assert "陆·赫斯：来，吃颗糖？" in cleaned
    assert "拿出糖果" not in cleaned


def test_scene_cleanup_drops_empty_stage_noise():
    scene_text = """【问候娜波摩】
【角色：漂泊者，娜波摩】
漂泊者：你好。
"""

    cleaned = CharacterChat._summarize_scene_for_prompt(scene_text)

    assert "问候娜波摩" not in cleaned
    assert "角色：" not in cleaned
    assert "漂泊者：你好。" in cleaned
