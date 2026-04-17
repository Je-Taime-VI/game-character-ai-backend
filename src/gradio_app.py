from __future__ import annotations

import threading
from pathlib import Path

import gradio as gr

from src.build_vector_db_with_metadata import build_vector_db
from src.chat import CharacterChat


PERMISSIONS_DIR = Path("data/permissions")
CHAT_ENGINE = CharacterChat()


def list_roles() -> list[str]:
    return sorted(
        path.stem
        for path in PERMISSIONS_DIR.glob("*.json")
        if path.name != "org_region_mapping.json"
    )


def format_retrieval_table(results: list[dict]) -> list[list[str]]:
    table: list[list[str]] = []
    for index, result in enumerate(results, start=1):
        table.append(
            [
                str(index),
                result["metadata"].get("path", ""),
                result.get("match_type", ""),
                f"{result.get('score', 0.0):.4f}",
                str(result.get("match_count", len(result.get("matched_lines", [])))),
            ]
        )
    return table


def on_build_index() -> str:
    try:
        paths = build_vector_db()
        return "\n".join(f"{name}: {path}" for name, path in paths.items())
    except Exception as exc:
        return f"[构建索引失败]\n{exc}"


def on_search(role_name: str, query: str) -> tuple[list[list[str]], str]:
    try:
        payload = CHAT_ENGINE.search_only(role_name=role_name, query=query)
        return format_retrieval_table(payload["results"]), payload["raw_context"]
    except Exception as exc:
        return [], f"[检索失败]\n{exc}"


def on_chat(role_name: str, query: str) -> tuple[str, list[list[str]], str, str]:
    try:
        result = CHAT_ENGINE.chat(role_name=role_name, user_message=query)
        return (
            result.reply,
            format_retrieval_table(result.retrieval_results),
            result.raw_context,
            result.prompt,
        )
    except Exception as exc:
        return f"[对话失败]\n{exc}", [], f"[对话失败]\n{exc}", ""


def build_demo() -> gr.Blocks:
    with gr.Blocks(title="游戏角色AI对话系统演示") as demo:
        gr.Markdown("# 游戏角色AI对话系统演示")
        gr.Markdown(
            "支持角色权限过滤检索、原文展示、命中行展示，以及基于 Ollama 的本地对话调用。"
        )

        with gr.Row():
            role_name = gr.Dropdown(label="角色", choices=list_roles(), value=(list_roles()[0] if list_roles() else None))
            query = gr.Textbox(label="玩家输入", lines=4, placeholder="输入想对角色说的话...")

        with gr.Row():
            build_btn = gr.Button("构建/刷新索引", variant="secondary")
            search_btn = gr.Button("只看检索", variant="secondary")
            chat_btn = gr.Button("执行对话", variant="primary")

        build_output = gr.Textbox(label="索引构建日志", lines=6)
        retrieval_table = gr.Dataframe(
            headers=["序号", "来源", "类型", "最高分", "命中行数"],
            datatype=["str", "str", "str", "str", "str"],
            row_count=(0, "dynamic"),
            column_count=(5, "fixed"),
            label="检索结果概览",
        )
        reply = gr.Textbox(label="角色回复", lines=10)
        raw_context = gr.Textbox(label="命中原文与命中行", lines=25)
        prompt = gr.Textbox(label="发送给模型的提示词", lines=20)

        build_btn.click(on_build_index, outputs=build_output)
        search_btn.click(on_search, inputs=[role_name, query], outputs=[retrieval_table, raw_context])
        chat_btn.click(
            on_chat,
            inputs=[role_name, query],
            outputs=[reply, retrieval_table, raw_context, prompt],
        )

    return demo


def main() -> None:
    demo = build_demo()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        prevent_thread_lock=True,
    )
    threading.Event().wait()


if __name__ == "__main__":
    main()
