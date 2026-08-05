# 基于轻量化大语言模型的游戏角色AI对话系统

本项目为毕设《基于大语言模型的游戏角色AI对话系统设计与实现》的完整工程实现。

> 环境准备与运行说明见 [SETUP.md](SETUP.md)。

## 项目简介

面向游戏角色扮演场景的本地化 AI 对话原型：玩家通过类游戏内通讯软件（UE4 飞讯界面）与具有稳定人格、知识边界和剧情感知能力的游戏角色进行多轮自由对话。系统以轻量化本地模型为核心，结合 RAG 检索增强、角色知识权限过滤、结构化剧情数据管理与提示词约束，构建可离线运行、可评估、可扩展的完整链路。

## 项目状态

已完成，具备可运行的完整闭环：

- 数据准备：XLSX 剧情标注表 → .editor.json → metadata → FAISS 双索引（flat/line）
- 检索：平铺检索 + 行级层次检索，剧情时序重排，角色权限过滤（检索阶段执行）
- 对话：提示词构建（角色身份 / 历史对话 / 检索上下文 / 硬约束）→ Ollama 本地推理 → 输出后处理
- 界面：权限管理页、结构化剧情编辑器、Gradio 调试页、UE4 仿游戏通讯软件聊天界面
- 测试：pytest 测试套件覆盖检索、权限、转换、时序等核心逻辑

## 技术路线

- 生成模型：`Qwen3:8B`（Ollama 本地部署）
- 嵌入模型：`BAAI/bge-small-zh-v1.5`（sentence-transformers）
- 向量索引：`FAISS`（IndexFlatIP）
- 后端框架：`FastAPI`
- 前端：HTML/CSS/JavaScript（权限页、编辑器）；Gradio（调试）
- 游戏端：Unreal Engine 4（Slate C++）通过 HTTP 调用后端 `/chat`

## 系统模块

1. **结构化剧情数据链路**：XLSX 标注表自动转换 .editor.json，统一表达台词、旁白、章节/段落梗概、注释与分支结构；配套可视化编辑器维护。
2. **RAG 检索增强**：文本块 + 行级双索引，行级命中回卷父级文本块，检索结果按剧情时序重排。
3. **角色知识权限过滤**：按角色/世界观/剧情/地区四级权限，在检索阶段排除未授权内容；剧情支持"不可见 / 仅梗概 / 梗概+正文"三态授权。
4. **提示词与对话流程**：角色名、玩家输入、历史对话、检索上下文与硬约束拼装提示词；区分日常聊天与事实问答；输出后处理去除旁白、说话人标签与超长内容。
5. **服务与界面**：FastAPI 统一接口（/chat、/search、/permissions、/editor 等），权限管理页、剧情编辑器、Gradio 调试页、本地演示启动面板。
6. **UE4 飞讯聊天界面**：联系人/会话/消息气泡/输入框，通过 HTTP 调用后端完成游戏内对话演示。

## 项目结构

```text
src/
  api.py                           # FastAPI 服务入口
  chat.py                          # 对话主流程编排
  retriever.py                     # 检索与权限过滤
  build_metadata.py                # 元数据构建
  build_vector_db_with_metadata.py # FAISS 向量库构建
  extract_role_info.py             # 角色基本信息提取
  generate_role_permissions.py     # 角色权限规则生成
  xlsx_to_editor_json.py           # XLSX 标注表 → .editor.json
  permission_tree.py               # 权限树 / 地区树 / 剧情梗概索引
  editor_v2.py                     # 结构化剧情编辑器
  gradio_app.py                    # Gradio 调试页面
  ollama_client.py / qwen_client.py# 模型调用封装
  static/                          # 权限页与编辑器的前端资源
data/
  raw/                             # 原始资料（XLSX / .editor.json / txt）
  processed/                       # metadata.json / role_infos.json
  vector_db/                       # FAISS 索引与检索入口（构建生成，不入库）
  permissions/                     # 角色权限配置 JSON
tests/                             # pytest 测试套件
scripts/                           # 本地演示启动面板
```

## 测试与验证

- pytest 测试覆盖：权限过滤、剧情时序、XLSX 转换、metadata 规则、模型客户端、编辑器等；
- 功能测试：服务、页面、聊天、转换、权限配置、UE4 会话均通过；
- 权限测试验证"角色检索不到未授权剧情"；本地 8B 模型 + RAG 链路完成 UE4 内中文对话演示。

## 系统不足与扩展方向

- 本地 8B 模型生成质量有限，存在过度发散、忽略重点证据等问题，可引入混合检索、重排序与更强模型；
- 检索对隐晦表达、跨章节伏笔与复杂因果的召回不稳定，需更强的嵌入模型与人工关系标注；
- 对话历史为内存级管理，未实现持久化与复杂长期记忆；
- UE4 界面为演示原型，未达到商业化标准；
- 内容安全为原型级，商业化落地需补充敏感内容拦截与自动评测。