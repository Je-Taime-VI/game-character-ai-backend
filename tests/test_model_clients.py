from src.chat import CharacterChat
from src.qwen_client import DEFAULT_QWEN_BASE_URL, QwenClient


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def retrieve(self, **kwargs):
        self.queries.append(kwargs.get("query"))
        return []


class FakeModelClient:
    def __init__(self, label):
        self.label = label
        self.calls = []

    def generate_text(self, messages, model=None):
        self.calls.append({"messages": messages, "model": model})
        return f"{self.label}:{model}"


def test_chat_can_route_to_qwen_without_replacing_ollama():
    ollama_client = FakeModelClient("ollama")
    qwen_client = FakeModelClient("qwen")
    chat = CharacterChat(
        retriever=FakeRetriever(),
        ollama_client=ollama_client,
        qwen_client=qwen_client,
        model_name="local-model",
        qwen_model_name="qwen-plus",
    )

    result = chat.chat("role", "hello", model_provider="qwen", model_name="qwen-max")

    assert result.reply == "qwen:qwen-max"
    assert result.model_provider == "qwen"
    assert result.model_name == "qwen-max"
    assert not ollama_client.calls
    assert qwen_client.calls[0]["model"] == "qwen-max"


def test_chat_defaults_to_ollama_channel():
    ollama_client = FakeModelClient("ollama")
    qwen_client = FakeModelClient("qwen")
    chat = CharacterChat(
        retriever=FakeRetriever(),
        ollama_client=ollama_client,
        qwen_client=qwen_client,
        model_name="local-model",
    )

    result = chat.chat("role", "hello")

    assert result.reply == "ollama:local-model"
    assert result.model_provider == "ollama"
    assert not qwen_client.calls


def test_chat_remembers_previous_turns_by_conversation_id():
    retriever = FakeRetriever()
    ollama_client = FakeModelClient("ollama")
    chat = CharacterChat(
        retriever=retriever,
        ollama_client=ollama_client,
        model_name="local-model",
    )

    chat.chat("role", "previous question", conversation_id="demo")
    result = chat.chat("role", "follow up", conversation_id="demo")

    second_call_messages = ollama_client.calls[1]["messages"]
    assert {"role": "user", "content": "previous question"} in second_call_messages
    assert {"role": "assistant", "content": "ollama:local-model"} in second_call_messages
    assert retriever.queries[1] == "previous question\nfollow up"
    assert "previous question" in result.prompt
    assert result.conversation_id == "role::demo"
    assert result.history[-2:] == [
        {"role": "user", "content": "follow up"},
        {"role": "assistant", "content": "ollama:local-model"},
    ]


def test_explicit_history_can_be_used_without_remembering_it():
    retriever = FakeRetriever()
    ollama_client = FakeModelClient("ollama")
    chat = CharacterChat(
        retriever=retriever,
        ollama_client=ollama_client,
        model_name="local-model",
    )

    chat.chat(
        "role",
        "follow up",
        history=[{"role": "user", "content": "external previous"}],
        remember=False,
    )

    assert {"role": "user", "content": "external previous"} in ollama_client.calls[0]["messages"]
    assert chat.conversations == {}


def test_daily_invitation_skips_retrieval_and_uses_plain_chat_rule():
    retriever = FakeRetriever()
    ollama_client = FakeModelClient("ollama")
    chat = CharacterChat(
        retriever=retriever,
        ollama_client=ollama_client,
        model_name="local-model",
    )

    result = chat.chat("爱弥斯", "下午有空吗？")

    assert retriever.queries == []
    assert result.retrieval_results == []
    assert "[日常聊天模式]" in result.prompt
    assert "有空、没空、晚点可以或现在不太方便" in result.prompt
    assert ollama_client.calls[0]["messages"][1]["content"] == result.prompt


def test_casual_follow_up_skips_retrieval_and_ignores_bad_assistant_history():
    retriever = FakeRetriever()
    ollama_client = FakeModelClient("ollama")
    chat = CharacterChat(
        retriever=retriever,
        ollama_client=ollama_client,
        model_name="local-model",
    )

    result = chat.chat(
        "爱弥斯",
        "具体几点有时间呢？",
        history=[
            {"role": "user", "content": "下午有空吗？"},
            {"role": "assistant", "content": "数据流在她周身闪烁。"},
        ],
    )

    assert retriever.queries == []
    assert result.retrieval_results == []
    assert "[日常聊天模式]" in result.prompt
    assert "下午有空吗？" in result.prompt
    assert "数据流在她周身闪烁" not in result.prompt
    assert all(message["role"] != "assistant" for message in ollama_client.calls[0]["messages"])


def test_casual_activity_request_skips_retrieval():
    retriever = FakeRetriever()
    chat = CharacterChat(
        retriever=retriever,
        ollama_client=FakeModelClient("ollama"),
        model_name="local-model",
    )

    result = chat.chat("爱弥斯", "闲下来联系我，我们去飙车")

    assert retriever.queries == []
    assert "[日常聊天模式]" in result.prompt


def test_casual_hurry_follow_up_gets_specific_time():
    reply = CharacterChat._postprocess_casual_reply(
        "行，到时候在联运椎骨碰头，我们去研究院一趟，莫宁要见你。越快越好",
        "下午有空，不过得先处理点事，大概三点能到联运椎骨。",
    )

    assert reply == "那我现在就收拾一下，十几分钟后见。"


def test_prompt_marks_high_similarity_lines_as_priority_evidence():
    chat = CharacterChat.__new__(CharacterChat)

    prompt = chat._build_prompt(
        "陆·赫斯",
        "黄金血是什么？",
        [
            {
                "chunk_id": "story",
                "text": "陆·赫斯: 诺维尔再生医药研发的“黄金血”，但我更习惯喊它的另一个名字——日髓。\n陆·赫斯: 之后发生了很多事。",
                "metadata": {"path": "主线/34.txt", "knowledge_type": "main_story"},
                "score": 0.9,
                "match_type": "hierarchical",
                "matched_lines": [
                    "陆·赫斯: 诺维尔再生医药研发的“黄金血”，但我更习惯喊它的另一个名字——日髓。"
                ],
                "match_count": 1,
            }
        ],
    )

    assert "【重点命中文本】" in prompt
    assert "黄金血" in prompt
    assert "优先级高于同片段里的其他背景文本" in prompt
    assert "不要主动展开成长篇回忆或剧情独白" in prompt


def test_prompt_can_highlight_summary_lines_inside_story_aggregate():
    chat = CharacterChat.__new__(CharacterChat)

    prompt = chat._build_prompt(
        "Role",
        "黄金血是什么？",
        [
            {
                "chunk_id": "story",
                "text": "[段落梗概]summary\nRole: direct answer",
                "metadata": {"path": "main/a.txt", "knowledge_type": "main_story"},
                "score": 0.9,
                "match_type": "hierarchical",
                "matched_lines": ["[段落梗概]summary", "Role: direct answer"],
                "match_count": 2,
            }
        ],
    )

    highlighted = prompt.split("Role: direct answer", 1)[0]
    assert ">> Role: direct answer" in prompt
    assert ">> [段落梗概]" in highlighted
    assert "[定义/事实题额外规则]" in prompt


def test_definition_prompt_omits_character_story_when_story_fact_is_available():
    chat = CharacterChat.__new__(CharacterChat)

    prompt = chat._build_prompt(
        "Role",
        "黄金血是什么？",
        [
            {
                "chunk_id": "main-story",
                "text": "Role: direct fact",
                "metadata": {"path": "main/a.txt", "knowledge_type": "main_story"},
                "score": 0.9,
                "match_type": "hierarchical",
                "matched_lines": ["Role: direct fact"],
            },
            {
                "chunk_id": "character-story",
                "text": "long painful memory",
                "metadata": {"path": "角色/Role/story.txt", "knowledge_type": "character"},
                "score": 0.85,
                "match_type": "hierarchical",
                "matched_lines": ["long painful memory"],
            },
        ],
    )

    assert "Role: direct fact" in prompt
    assert "long painful memory" not in prompt


def test_reply_postprocess_removes_script_labels_and_stage_directions():
    raw = (
        "**漂泊者**：（轻抬额头，声音微颤）爱弥斯，你知道什么是炉芯机骸吗？\n\n"
        "**爱弥斯**：（将发丝别至耳后）那是罗伊冰原上的机骸，和炉芯有关。"
    )

    reply = CharacterChat._postprocess_reply("爱弥斯", raw)

    assert "漂泊者" not in reply
    assert "爱弥斯" not in reply
    assert "（" not in reply
    assert "炉芯" in reply


def test_reply_postprocess_limits_long_story_like_output():
    raw = (
        "爱弥斯：第一句事实。第二句补充。第三句收束。"
        "第四句开始变成长篇剧情。第五句继续扩写许多没有必要的背景。"
    )

    reply = CharacterChat._postprocess_reply("爱弥斯", raw)

    assert reply == "第一句事实。第二句补充。第三句收束。"


def test_qwen_client_uses_openai_compatible_chat_completions(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "online reply"}}]}

    def fake_post(url, headers, json, timeout):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr("src.qwen_client.requests.post", fake_post)
    client = QwenClient(api_key="test-key", model="qwen-plus", timeout=30)

    reply = client.generate_text([{"role": "user", "content": "hi"}])

    assert reply == "online reply"
    assert calls[0]["url"] == f"{DEFAULT_QWEN_BASE_URL}/chat/completions"
    assert calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert calls[0]["json"]["model"] == "qwen-plus"
    assert calls[0]["json"]["messages"] == [{"role": "user", "content": "hi"}]

