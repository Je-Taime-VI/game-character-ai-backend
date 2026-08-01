from src.editor_v2 import compile_document_to_txt, normalize_document


def test_v4_narration_block_stays_narration():
    document = {
        "version": 4,
        "title": "Doc",
        "meta": {"source": "editor_v2"},
        "blocks": [{"id": "a", "type": "narration", "text": "plain narration"}],
    }

    normalized = normalize_document(document, "story.txt")

    assert normalized["blocks"][0]["type"] == "narration"


def test_legacy_narration_block_maps_to_text_title():
    document = {
        "version": 3,
        "title": "Doc",
        "blocks": [{"id": "a", "type": "narration", "text": "legacy title"}],
    }

    normalized = normalize_document(document, "story.txt")

    assert normalized["blocks"][0]["type"] == "text_title"


def test_compile_txt_uses_inline_story_labels():
    text = compile_document_to_txt(
        {
            "title": "Doc",
            "blocks": [
                {"type": "chapter_summary", "text": "chapter summary"},
                {"type": "paragraph_summary", "text": "paragraph summary"},
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
            ],
        }
    )

    assert "[\u672c\u7ae0\u6897\u6982]chapter summary" in text
    assert "[\u6bb5\u843d\u6897\u6982]paragraph summary" in text
    assert "[\u65c1\u767d]narration text" in text
    assert "[\u6ce8\u91ca]note text" in text
    assert "[\u5206\u652f\u540e\u7eed]A" in text
