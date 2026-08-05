# 基于轻量化大语言模型的游戏角色 AI 对话系统

本项目为本科毕业设计《基于大语言模型的游戏角色AI对话系统设计与实现》，已完成并可本地运行演示。

> 下载后如何准备环境并运行测试，请看 [SETUP.md](SETUP.md)。

系统目标是让玩家通过文本聊天界面，与具有稳定人格、知识边界和剧情感知能力的游戏角色进行多轮自由对话。整体方案以轻量化本地模型为核心，结合 RAG、角色权限过滤、结构化剧情数据与提示词约束，构建可离线运行、可评估、可扩展的角色 AI 对话原型。

## 项目状态

毕业设计已完成，实现了一条可运行的完整链路：

- 数据准备：XLSX 剧情标注表 → `.editor.json` 结构化文档 → metadata → FAISS 向量库（文本块级 + 行级双索引）。
- 检索：平铺检索 + 层次检索，检索阶段按角色权限过滤，结果按剧情时间顺序重排。
- 对话：Ollama + Qwen3-8B 本地推理，提示词约束 + 日常聊天模式识别 + 输出后处理。
- 展示：FastAPI 服务、权限管理页、结构化剧情编辑器、Gradio 调试页、UE4 仿游戏通讯软件聊天界面。

## 技术路线

- 生成模型：`Qwen3:8B`（Ollama 本地推理）
- 嵌入模型：`BAAI/bge-small-zh-v1.5`
- 向量索引：`FAISS`
- 后端框架：`FastAPI`
- 前端：HTML / CSS / JavaScript（权限页、编辑器）
- 调试界面：`Gradio`
- 游戏引擎：Unreal Engine 4（Slate C++ 聊天界面，通过 HTTP 调用后端接口）

## 项目结构

```text
src/
  api.py                        # FastAPI 服务入口（/chat /search /permissions /editor 等）
  chat.py                       # 对话主流程编排（提示词构建、模型调用、历史管理）
  retriever.py                  # 双索引检索 + 角色权限过滤 + 剧情时序重排
  build_metadata.py             # metadata 构建与文本切块
  build_vector_db_with_metadata.py  # FAISS 向量库构建
  extract_role_info.py          # 角色基本信息提取
  generate_role_permissions.py  # 角色权限规则生成（自动提取 + 手工配置）
  xlsx_to_editor_json.py        # XLSX 标注表 → .editor.json 转换
  permission_tree.py            # 权限树 / 地区树 / 剧情梗概索引
  editor_v2.py                  # 结构化剧情编辑器后端
  gradio_app.py                 # Gradio 调试页面
  ollama_client.py / qwen_client.py  # 模型调用封装
  static/                       # 编辑器与权限管理页面前端
data/
  raw/                          # 原始资料（世界观 / 角色 / 主线 / 支线）
  processed/                    # metadata.json、role_infos.json
  vector_db/                    # FAISS 索引与检索入口（构建生成，不入库）
  permissions/                  # 角色权限配置（JSON）
tests/                          # pytest 测试套件
scripts/                        # 本地演示启动面板
```

## 已实现功能

- 知识库检索：角色 / 世界观 / 主线 / 支线资料统一分块向量化，双索引召回并保持剧情上下文完整。
- 角色权限控制：角色 / 世界观 / 剧情 / 地区四级权限，剧情支持"不可见 / 仅梗概 / 梗概+正文"三态授权，未授权内容在模型调用前即被过滤。
- 角色自由对话：本地 Qwen3-8B 生成，系统提示词硬约束 + 日常聊天模式 + 输出后处理，回复贴近聊天软件风格。
- 结构化剧情编辑：XLSX 标注表转换、`.editor.json` 维护、世界观词条自动识别与位置级取消注释。
- 调试与管理：Gradio 检索/对话调试、权限管理页面、本地演示启动面板（Tkinter）。
- UE4 聊天演示：仿游戏内通讯软件的聊天界面（联系人、会话、消息气泡），通过 HTTP 调用 `/chat` 接口。

## 测试与验证

`tests/` 提供 pytest 测试套件，覆盖权限过滤、剧情时序、XLSX 转换、metadata 规则、模型客户端与编辑器。系统完成功能测试、检索测试、权限控制测试、编辑器测试与 UE4 界面测试，详见毕业设计论文第 6 章。

## 运行环境

依赖与模型不随仓库分发，首次运行前请按 [SETUP.md](SETUP.md) 准备：

- Python 3.10 ~ 3.12 与 `requirements.txt` 依赖
- 嵌入模型 `BAAI/bge-small-zh-v1.5`（Hugging Face 缓存）
- Ollama 与 `qwen3:8b`
- FAISS 向量库需执行 `python -m src.build_vector_db_with_metadata` 重建
- UE4 4.24（仅前端演示需要）

## 扩展方向

- 混合检索与重排序（关键词召回 + 向量召回），提升隐晦表达下的召回率。
- 更强的本地模型或角色专属数据微调、指令模板强化。
- 长期记忆、任务系统联动、内容安全过滤与自动评测集。