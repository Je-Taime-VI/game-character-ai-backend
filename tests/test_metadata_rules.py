from src.build_metadata import KnowledgeDocument, build_chunks_for_document


def test_story_summary_uses_blank_line_chunks():
    doc = KnowledgeDocument(
        doc_id="test",
        path="主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt",
        category="main_story",
        title="简介",
        retrieval_mode="flat",
        metadata={
            "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/简介.txt",
            "knowledge_type": "main_story",
            "story_document_kind": "summary",
            "story_group": "34-第三章-驶向尚未点亮之星-间章-日光落处",
        },
    )

    chunks = build_chunks_for_document(doc, "第一段\n\n第二段")

    assert len(chunks) == 2
    assert all(not chunk.line_chunks for chunk in chunks)


def test_story_full_uses_hierarchical_chunks():
    doc = KnowledgeDocument(
        doc_id="test",
        path="支线/35-1诸星密语/诸星密语-琳奈/全文.txt",
        category="side_story",
        title="全文",
        retrieval_mode="hierarchical",
        metadata={
            "path": "支线/35-1诸星密语/诸星密语-琳奈/全文.txt",
            "knowledge_type": "side_story",
            "story_document_kind": "full",
            "story_group": "诸星密语-琳奈",
        },
    )

    chunks = build_chunks_for_document(
        doc,
        "【场景：测试场景】【角色：漂泊者】\n漂泊者：你好。\n\n【场景：第二场景】【角色：琳奈】\n琳奈：你好。",
    )

    assert len(chunks) == 2
    assert len(chunks[0].line_chunks) == 2
