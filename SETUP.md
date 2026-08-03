# 环境准备与运行说明

本文档面向需要下载本仓库并实际运行测试的同学/公司。本系统是本地大语言模型原型，
模型、索引和引擎资源体积较大，**不会全部包含在 Git 仓库中**，运行前必须按以下步骤准备环境。

## 一、需要准备的环境清单

| 项目 | 用途 | 是否在 Git 仓库中 | 获取方式 |
| --- | --- | --- | --- |
| Windows 10/11 | 操作系统 | - | - |
| Python 3.10 ~ 3.12 | 运行后端 | 否 | python.org |
| Python 依赖（requirements.txt） | FastAPI/FAISS/嵌入模型等 | 仅依赖清单 | `pip install -r requirements.txt` |
| 嵌入模型 BAAI/bge-small-zh-v1.5 | 文本向量化（RAG 检索） | 否 | 首次向量化时自动下载 |
| Ollama | 本地模型服务 | 否 | https://ollama.com/download |
| 对话模型 qwen3:8b | 角色回复生成 | 否（约 4~5GB） | `ollama pull qwen3:8b` |
| FAISS 向量库 data/vector_db | 检索索引 | 否（约 200MB，被 .gitignore 排除） | 运行第 5 步重建 |
| Unreal Engine 4.24 | UE4 飞讯前端 | 否（引擎本体） | Epic Games Launcher 安装 |

## 二、详细步骤

以下命令默认在项目根目录（含 `src/`、`data/` 的目录）执行，Windows PowerShell 或 cmd 均可。

### 1. 获取代码

```powershell
git clone https://gitee.com/GrayRaveN-Q312O6/game-character-ai-backend.git
cd game-character-ai-backend
```

### 2. 安装 Python 依赖

```powershell
python -m pip install -r requirements.txt
```

> 依赖包含 torch、sentence-transformers、faiss-cpu、fastapi、uvicorn、gradio、requests、numpy，
> 体积较大，首次安装需要几分钟。

### 3. 准备嵌入模型（bge-small-zh-v1.5）

首次执行向量化或检索时，sentence-transformers 会自动从 Hugging Face 下载模型。
建议先显式设置缓存目录并预下载：

```powershell
set HF_HOME=%USERPROFILE%\.cache\huggingface
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-zh-v1.5')"
```

离线环境：将已下载的模型缓存目录（`hub/models--BAAI--bge-small-zh-v1.5`）整体拷贝到目标电脑，
并把 `HF_HOME` 指向它的上级目录。

### 4. 安装 Ollama 并下载对话模型

```powershell
# 安装后确认
ollama --version
# 下载 qwen3:8b（约 4~5GB，需联网）
ollama pull qwen3:8b
# 确认模型存在
ollama list
```

### 5. 重建 FAISS 向量库（必做）

`data/vector_db/` 不在 Git 仓库中，克隆后必须执行一次重建：

```powershell
python -m src.build_vector_db_with_metadata
```

成功后会在 `data/vector_db/` 下生成 `flat.index`、`line.index`、`flat_entries.json`、`line_entries.json`。
也可以在本地演示启动面板中点击“刷新 metadata + vector_db”完成。

### 6. 启动后端服务

```powershell
set HF_HOME=%USERPROFILE%\.cache\huggingface
python -m uvicorn src.api:app --host 127.0.0.1 --port 8000
```

验证：

- 健康检查：http://127.0.0.1:8000/health （返回 `{"status":"ok"}`）
- 接口文档：http://127.0.0.1:8000/docs
- 权限管理页：http://127.0.0.1:8000/permissions-ui
- 结构化编辑器：http://127.0.0.1:8000/editor

### 7. （可选）Gradio 调试页面

```powershell
python -m src.gradio_app
```

### 8. （可选）本地演示启动面板

双击 `scripts/start_dashboard.bat`，可一键启停 Ollama / FastAPI / Gradio，并执行 XLSX 转换与向量库刷新。

### 9. UE4 飞讯前端（仅演示界面需要）

1. 安装 Unreal Engine 4.24（Epic Games Launcher 中获取，引擎本体不随仓库分发）；
2. 克隆/下载 [game-character-ai-ue4-client](https://gitee.com/GrayRaveN-Q312O6/game-character-ai-ue4-client)；
3. 用 UE4 打开 `GameCharacterAI_UE4.uproject`，点击运行；
4. 进入场景后按 `I` 键打开飞讯界面，选择角色并发送消息；
5. UE4 通过 HTTP 调用 `http://127.0.0.1:8000/chat`，请先确保后端已启动。

## 三、不在 Git 仓库中的内容汇总

- `data/vector_db/`：FAISS 索引与检索入口文件（约 200MB），克隆后需按第 5 步重建；
- 嵌入模型缓存（`BAAI/bge-small-zh-v1.5`）；
- Ollama 及 `qwen3:8b` 模型；
- UE4 引擎本体；
- Python 依赖。

## 四、常见问题

| 现象 | 排查方向 |
| --- | --- |
| `/health` 无法访问 | 后端是否启动、8000 端口是否被占用 |
| 聊天返回“模型调用失败” | Ollama 是否启动、`qwen3:8b` 是否已 `ollama pull` |
| 检索/向量化报找不到模型 | `HF_HOME` 是否设置、模型缓存目录是否存在 |
| UE4 飞讯无回复 | 先直接调用 `/chat` 接口验证，再检查 UE4 中 API 地址是否为 `http://127.0.0.1:8000/chat` |
| 生成回复质量差 | 本地 8B 模型能力有限，属已知局限，可调大 `top_k_lines`/`top_k_flat` 或换更强模型 |

## 五、注意事项

- 首次运行需要联网下载依赖与模型，总体积约 8~10GB；全部就绪后可完全离线运行。
- 本系统未使用数据库，数据保存在 `.editor.json`、`metadata.json` 与 FAISS 索引文件中。
- 角色权限、剧情资料位于 `data/permissions/` 与 `data/raw/`，均为项目自身数据，随仓库分发。
