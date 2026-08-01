# 《基于轻量化大语言模型的游戏角色 AI 对话系统设计与实现》论文初稿

> 使用说明：本文是可直接复制到 WPS 的正文初稿。代码块请在 WPS 中设置为浅灰底纹、等宽字体，例如 Consolas 或 Cascadia Mono，字号可比正文小一号。文中所有“图 x-x”位置建议后续补充系统截图、流程图或运行结果截图。本文不设置附录，代码与说明均放在正文对应章节中。

## 序言

本论文初稿是在项目已经完成多轮工程迭代后的基础上整理形成的。项目最初以“让游戏角色能够基于本地大语言模型进行自由对话”为目标，但在实际实现过程中逐渐发现，角色 AI 的难点并不只是调用一个模型接口，而是如何组织剧情资料、限制角色知识边界、控制回答风格，并将结果接入接近真实游戏的交互界面。因此，本文将研究重点放在“轻量化本地模型 + 检索增强生成 + 角色权限控制 + 结构化剧情数据”的完整链路设计上。

在数据准备方面，项目早期曾使用 TXT 文本作为主要资料来源，便于快速整理和导入。但随着剧情文本规模扩大，旁白、台词、本章梗概、段落梗概、本章注释、普通注释、分支选项和分支后续等结构化信息逐渐增多，单纯依靠 TXT 难以稳定表达文本顺序、块类型和人工标注。后续项目转向以游戏解包得到的 XLSX 原始表和人工整理后的 XLSX 标注表作为人工检查入口，再转换为 `.editor.json` 作为程序读取和向量化的中间格式。本文后续章节中的系统设计，均以这一结构化数据链路为当前主线；TXT 相关内容仅作为早期试错和历史兼容背景说明。

在模型部署方面，本文采用 Ollama 调用本地 Qwen3:8B 模型完成回复生成。选择本地模型并不是因为其效果优于云端大模型，而是因为毕业设计更强调可复现、可离线、可解释和可控的系统链路。实际测试中，本地轻量模型在复杂隐喻理解、跨章节伏笔联想和严格指令遵循方面仍存在不足，因此本文并不回避这些问题，而是将其作为系统局限和后续优化方向进行讨论。

本文所实现的系统仍属于原型系统。其价值主要体现在：验证游戏角色 AI 对话不应只依赖模型生成能力，还需要剧情资料结构化、角色权限过滤、检索结果组织、提示词约束和游戏端界面共同配合。后续若进入更接近工业化的流程，还需要进一步引入更强检索模型、重排序器、内容安全过滤、自动评测集和更完整的游戏状态联动。
## 摘要

随着开放世界游戏、角色扮演游戏和服务型游戏内容规模的持续扩大，玩家对游戏角色互动真实性、剧情沉浸感和个性化反馈的要求不断提高。传统游戏中的 NPC 对话多依赖预设脚本、有限分支和固定触发条件，虽然便于控制剧情节奏，却难以覆盖玩家自由输入带来的复杂交互需求。大语言模型具备较强的自然语言理解和生成能力，为游戏角色自由对话提供了新的技术路径。然而，通用大模型直接应用于游戏角色对话时，容易出现角色越界、知识泄露、设定幻觉、剧情剧透和本地部署成本过高等问题。因此，如何在有限硬件资源下构建一个可控、可扩展、具有角色一致性的游戏角色 AI 对话系统，是本文研究的核心问题。

本文围绕“基于轻量化大语言模型的游戏角色 AI 对话系统设计与实现”展开研究，设计并实现了一个面向游戏角色扮演聊天软件对话场景的原型系统。系统以本地轻量化大语言模型为生成核心，结合检索增强生成技术、角色知识权限控制、结构化剧情数据编辑、世界观设定管理和 UE4 聊天界面接入，构建从剧情资料整理、知识向量化、权限过滤、提示词拼接到角色回复生成的完整流程。系统后端采用 Python、FastAPI、FAISS、sentence-transformers 与 Ollama 实现，前端提供权限管理页面、结构化编辑器和游戏内“飞讯”（示例游戏《鸣潮》中的一种通讯软件）式聊天界面，数据层以 XLSX 标注表和 `.editor.json` 结构化格式为主，TXT 仅作为早期试错和历史兼容背景。

在实现过程中，重点关注了三类问题。第一，针对游戏剧情资料结构复杂、文本来源多样的问题，设计了从 XLSX 标注表到 `.editor.json`、metadata 和 vector_db 的数据准备链路，使本章梗概、段落梗概、旁白、台词、文本标题、文本正文、本章注释、注释和分支后续等信息能够被统一建模。第二，针对角色“知道过多”的问题，引入基于角色、地区、势力和剧情路径的权限控制机制，在检索阶段限制角色可访问知识范围，使角色回答更符合自身身份与剧情进度。第三，针对本地模型容易发散和幻觉的问题，在提示词构建阶段加入重点命中文本、设定注释、历史对话与硬约束规则，尽量保证回答以检索证据为依据。

测试与演示结果表明，本系统能够完成基于本地模型的角色问答、权限过滤、剧情资料检索、结构化编辑和 UE4 聊天界面交互，初步验证了轻量化大语言模型在游戏角色 AI 对话场景中的可行性。系统仍存在检索模型语义理解能力有限、提示词约束不稳定、跨章节伏笔关系依赖人工标注等不足，但整体方案为实际工业化流程中接入更强检索模型、引入重排序器、优化角色记忆和扩展游戏引擎集成提供了基础。

关键词：轻量化大语言模型；游戏角色 AI；检索增强生成；知识权限控制；本地部署；UE4

## Abstract

With the continuous expansion of open-world games, role-playing games and live-service game content, players increasingly expect game characters to provide natural, consistent and personalized responses. Traditional NPC dialogue systems usually rely on predefined scripts, limited branches and fixed triggers. Although these methods are easy to control, they cannot effectively handle free-form player input. Large language models provide a promising solution for flexible character dialogue, but direct application of general-purpose models often leads to out-of-character responses, unauthorized knowledge exposure, hallucinated settings, spoilers and high deployment costs. Therefore, this thesis focuses on designing and implementing a controllable game character AI dialogue system based on a lightweight large language model.

This thesis proposes a prototype system that combines local lightweight language model inference, retrieval-augmented generation, role-based knowledge permission control, structured story data editing, world-setting annotation management and UE4 chat UI integration. The backend is implemented with Python, FastAPI, FAISS, sentence-transformers and Ollama. The data pipeline uses structured XLSX annotation sheets and `.editor.json` files as its main formats, while plain TXT is only discussed as an early compatibility stage. The system supports story material preparation, metadata construction, vector indexing, permission-aware retrieval, prompt construction and character response generation.

The system mainly addresses three issues. First, for complex game story data, a structured data pipeline from XLSX annotation sheets to `.editor.json`, metadata and vector databases is designed. Second, for the problem that characters may know information beyond their identities, a permission control mechanism based on roles, regions, organizations and story paths is introduced. Third, for the hallucination and over-expansion problems of local models, the prompt construction process emphasizes highlighted evidence, setting annotations, dialogue history and explicit constraints.

Experiments and demonstrations show that the system can support local model-based character dialogue, permission filtering, story retrieval, structured editing and UE4 chat interaction. Although there are still limitations such as insufficient semantic retrieval accuracy, unstable prompt compliance and manual annotation requirements for cross-chapter foreshadowing, the prototype verifies the feasibility of applying lightweight large language models to game character dialogue systems.

Keywords: Lightweight Large Language Model; Game Character AI; Retrieval-Augmented Generation; Knowledge Permission Control; Local Deployment; UE4

## 第 1 章 绪论

### 1.1 选题背景与意义

近年来，人工智能生成内容技术快速发展，大语言模型在自然语言理解、文本生成、角色扮演和知识问答等任务中表现出较强能力。与此同时，游戏产业也在不断追求更强的沉浸感和更自由的交互方式。对于剧情驱动型游戏而言，角色对话不仅承担信息传递功能，也承担塑造角色人格、推动剧情发展和增强玩家情感投入的作用。一个优秀的角色对话系统，应当能够让玩家感受到角色“知道自己应该知道的事”“以符合自身身份的方式说话”“不会随意泄露剧情或世界观信息”。

传统游戏对话通常采用脚本树、状态机和分支选项实现。其优点是稳定、可控、便于剧情演出，但缺点也十分明显：玩家只能从预设选项中选择，无法真正自由提问；脚本规模随着剧情复杂度快速膨胀，维护成本较高；当游戏世界观和角色设定持续更新时，旧脚本难以自动适配新信息。对于内容量巨大的开放世界游戏而言，大量角色设定、地区设定、剧情对白、支线文本和世界观文档分散在不同文件中，人工维护所有可交互问答几乎不可行。

大语言模型为解决上述问题提供了新的思路。模型可以基于玩家输入生成自然语言回复，使 NPC 具备更接近真实对话的交互能力。但通用大模型并不能直接满足游戏角色对话系统的要求。首先，通用模型训练语料并不包含某个具体游戏项目的全部设定，直接回答容易产生幻觉。其次，模型如果获得完整资料，角色可能会说出自己不应知道的剧情信息，破坏角色知识边界。再次，本地离线游戏或毕业设计原型通常无法长期依赖高成本云端模型，需要考虑轻量化和本地部署。最后，游戏角色回答不仅要“正确”，还要“符合人设”，这对提示词、检索上下文和角色知识组织提出了更高要求。

基于以上背景，本文设计并实现一个基于轻量化大语言模型的游戏角色 AI 对话系统。系统以本地模型为核心，通过检索增强生成补充游戏专有知识，通过权限过滤限制角色可访问范围，通过结构化编辑器维护剧情和注释数据，通过 UE4 聊天界面展示最终交互效果。本文研究重点不是训练一个全新的大模型，而是在工程层面构建一套可控、可解释、可扩展的角色 AI 对话流程。

本文研究具有以下意义。

第一，将大语言模型从通用问答场景进一步约束到游戏角色扮演场景，强调知识边界、角色身份和剧情进度，这比普通聊天机器人更贴近实际游戏开发需求。游戏角色不能像百科助手一样回答所有问题，也不能在剧情尚未发生时提前透露信息。因此需要在检索层加入角色权限过滤，在提示词层加入角色一致性约束，使系统更符合游戏交互逻辑。

第二，探索了轻量化本地部署方案。相比依赖云端 API，本地模型具有数据可控、成本可控、离线运行和便于游戏内集成的优势。虽然本地模型在推理质量和理解能力上仍不如大型云端模型，但在毕业设计和原型验证阶段更容易复现和展示，也能体现系统工程设计价值。

第三，构建了从资料编辑到游戏界面的完整链路。系统不仅包含模型调用和检索逻辑，还包含 XLSX 标注表、`.editor.json` 结构化数据、权限管理页面、注释系统、FastAPI 服务和 UE4 风格聊天界面。该链路说明游戏角色 AI 并不是单纯调用模型接口，而是需要内容生产、知识管理、权限控制、交互界面和测试评估共同配合。

第四，对当前方案的局限进行了分析。实际测试中，轻量检索模型可能无法准确理解隐晦表达，本地模型也可能出现过度文学化、编造细节或忽视重点证据的问题。这些不足并不否定系统方向，而是说明工业级应用还需要更强检索模型、重排序器、专门微调、自动评测和人工内容规范共同支撑。本文将这些问题作为系统改进方向写入总结，有助于体现毕业设计的客观性。

### 1.3 国内外研究现状

在游戏 AI 领域，传统 NPC 对话系统主要依赖有限状态机、行为树、脚本树和任务系统。此类方法可控性强，能够准确配合剧情演出、镜头调度和任务触发，但自由度有限。随着自然语言处理技术发展，一些游戏开始尝试将聊天机器人或大语言模型接入特定NPC（如国产开放世界RPG《燕云十六声》、韩国《Mecha BREAK》），使玩家能够使用自然语言与角色互动，但实际落地仍面临知识一致性、响应延迟、成本、安全和剧情控制等问题。

检索增强生成是近年来缓解大模型幻觉的重要技术路线。其基本思想是在模型生成前，先从外部知识库检索与问题相关的资料，再将检索结果作为上下文提供给模型。相比单纯依赖模型参数记忆，RAG 更适合需要频繁更新、领域知识明确且要求可追溯的场景。游戏剧情、角色设定和世界观资料具有明显的领域知识特征，因此适合采用 RAG 进行增强。

在权限控制方面，传统知识库问答通常假设用户可以访问完整知识库，而游戏角色对话要求每个角色只能访问自己知道的内容。角色知识权限不仅与角色身份有关，还与出生地、势力、剧情经历和玩家进度有关。因此，本文将权限控制前置到检索阶段，使不可访问资料不进入提示词，从源头降低越权回答概率。

在本地部署方面，Ollama、llama.cpp 等工具降低了本地运行开源模型的门槛。Qwen、Llama、Mistral 等模型的轻量版本为个人电脑和普通显卡环境提供了可用选择。本文采用 Ollama 调用 Qwen3:8B 作为本地推理模型。

### 1.4 研究内容

本文主要研究内容如下。

第一，设计游戏角色 AI 对话系统总体架构。系统包括数据准备层、知识库层、权限控制层、检索层、提示词构建层、模型调用层、Web 管理界面和 UE4 聊天界面。

第二，设计结构化剧情数据格式。系统将解包游戏文件得到的原始XLSX表逐步迁移到 XLSX 标注表和 `.editor.json`，以支持台词、旁白、本章梗概、段落梗概、注释、分支选项和分支后续等结构。

第三，实现基于 FAISS 的向量检索与权限过滤。系统使用 sentence-transformers 生成文本嵌入，使用 FAISS 建立向量索引，并根据角色权限筛选可访问文本。

第四，实现角色权限管理。系统从角色资料中提取基本信息，结合手工配置的”势力-地区“映射和额外授权，生成每个角色的权限 JSON。

第五，实现提示词构建和本地模型调用。系统将角色名、玩家输入、历史对话、检索上下文、重点命中文本和回答约束拼接为提示词，通过 Ollama 调用本地模型生成回复。

第六，实现编辑器和权限管理界面。编辑器用于结构化维护剧情文本和设定标注，权限管理页面用于管理角色权限、文件树和数据入口。

第七，在UE4实现聊天界面。通过 UE4 Slate UI 构建联系人、会话列表、消息气泡和输入框，调用 FastAPI `/chat` 接口完成游戏内对话演示。

### 1.5 论文结构

第一章，绪论。介绍选题背景和意义、国内外学术动态和研究内容。

第二章，介绍系统涉及的关键技术，包括轻量化大语言模型、RAG、FAISS、FastAPI、Ollama、UE4 Slate 等。

第三章，进行系统需求分析，包括功能需求、非功能需求和角色知识边界需求。

第四章，进行系统总体设计，包括系统架构、数据流、权限模型和接口设计。

第五章，详细说明核心模块实现，包括数据准备、向量化、检索、提示词、编辑器、权限页面和 UE4 接入，并给出核心代码及解释。

第六章，进行系统测试与结果分析。

第七章，总结全文并提出后续改进方向。

## 第 2 章 相关技术介绍

### 2.1 大语言模型（LLM）与轻量化部署

大语言模型（Large Language Model）是基于深度学习的自然语言生成模型，通常通过大规模语料预训练获得语言理解和生成能力。相比传统规则系统，大语言模型能够根据上下文动态组织语言，并在对话、摘要、问答、翻译等任务中表现出较高灵活性。对于游戏角色 AI 来说，大语言模型最大的价值在于能够根据玩家输入生成非固定脚本的自然回复。

但是，大语言模型通常参数量较大，对显存、内存和计算资源要求较高。如果直接使用云端大模型，虽然效果较好，但存在调用成本、网络延迟、数据安全和离线不可用等问题。本研究采用轻量化本地模型部署方案，通过 Ollama 调用 Qwen3:8B 模型，使系统能够在本地环境中完成推理。轻量化模型的优势是部署门槛较低、可离线运行、适合概念级方向性演示；不足是对复杂隐喻、长上下文和细粒度指令遵循能力仍有限。因此，本文通过 RAG 和提示词约束弥补模型参数知识不足。

### 2.2 检索增强生成技术（RAG）

检索增强生成技术（Retrieval-Augmented Generation）将外部知识库与大语言模型结合。其流程通常包括文档切分、向量化、索引构建、问题向量化、相似度检索、上下文拼接和模型生成。对于游戏角色 AI，RAG 可以将角色档案、剧情文本、世界观设定等资料动态提供给模型，使模型不必把所有游戏知识记在参数中。

本研究采用两级检索思路：一方面对逻辑链相对完整的文本块建立索引，用于召回较完整的剧情片段；另一方面对单行或细粒度文本建立索引，用于捕捉具体问题中的关键句。检索命中后，系统会回到父级剧情块，尽量保证上下文完整性。

### 2.3 向量表示与 FAISS（Facebook AI Similarity Search）

文本向量化是 RAG 的基础。本实验使用 sentence-transformers 中的中文嵌入模型将文本转换为向量。向量之间的相似度可以反映语义接近程度。sentence-transformers——一个专门处理句子的 Python 工具包，能直接把文字变成电脑能懂的数字向量。它特别适合拿来做语义搜索、判断两句话意思像不像，或者把一堆文章自动分类。

为了提高检索效率，使用 FAISS 建立向量索引。FAISS——由 Meta（原 Facebook）的基础人工智能研究团队开发并开源的专门针对大规模向量集合设计的算法库，核心目的是解决海量数据下的相似性搜索难题，支持高效的向量相似度搜索，适合在本地构建中小规模知识库。

在构建向量库时，对向量进行归一化，并使用内积索引进行相似度计算。对于本项目规模而言，IndexFlatIP 已经能够满足实验需求。如果在知识库规模更大的实际流程中，可考虑 IVF、HNSW 或重排序模型。

### 2.4 FastAPI 后端服务

FastAPI 是基于 Python 的 Web 框架，具有开发效率高、类型标注友好、自动生成接口文档等特点。本文后端使用 FastAPI 提供统一接口，包括健康检查、权限树、编辑器文档读写、设定库查询、搜索接口和聊天接口。UE4 前端并不直接调用模型，而是通过 HTTP 请求访问 FastAPI `/chat` 接口，由后端完成检索、权限过滤、提示词构建和模型调用。

### 2.5 Ollama 本地模型调用

Ollama 是本地运行大语言模型的工具，能够通过 HTTP API 调用本地模型。本文封装 `OllamaClient`，使对话模块不直接依赖具体模型实现。这样在过程中可以根据实际需要更换本地模型名称或调整模型运行参数，而不需要重写上层聊天流程。本文实现阶段以本地 Ollama 服务为主，不再保留非本地模型通道作为正式链路。

### 2.6 虚幻4引擎（Unreal Engine 4）的Slate（Slate UI Framework）界面技术

UE4 提供 UMG 和 Slate 两套 UI 构建方式。UMG 更适合蓝图可视化开发，Slate 更适合 C++ 中精细控制复杂界面。本文为了快速构建风格化聊天界面，采用 Slate 编写“飞讯”风格 UI，包括联系人列表、会话列表、消息气泡、输入框、按钮音效和 HTTP 请求逻辑。该界面模拟游戏内通讯软件的交互方式，展示 AI 对话系统可接入游戏引擎的效果。

## 第 3 章 系统需求分析

### 3.1 功能需求

系统需要实现以下功能。

1. 知识库检索功能。系统能够从角色资料、世界观资料、主线剧情和支线剧情中检索相关文本。

2. 角色权限控制功能。不同角色拥有不同知识范围。

3. 角色自由对话功能。玩家输入自然语言后，系统根据当前角色身份生成回复。回复应尽量符合角色人设，并基于检索上下文给出事实。

4. 结构化剧情编辑功能。系统支持维护台词、旁白、文本标题、文本正文、本章梗概、段落梗概、注释、分支选项和分支后续。

5. 注释管理功能。系统支持基于世界观设定词条自动识别标注，并允许位置级取消注释，避免同一词条在特定位置反复误标。

6. 权限管理功能。系统提供 Web 页面管理角色权限、文件树、新建文件、删除文件、搜索路径和势力地区映射。

7. UE4 聊天演示功能。系统在 UE4 中提供类似游戏内通讯界面的聊天 UI，支持选择角色、创建会话、输入文本、发送请求并显示回复。

### 3.2 非功能需求

系统还需要满足以下非功能需求。

1. 本地运行。系统核心链路尽量在本地运行，避免依赖云端服务。

2. 可扩展。知识库、角色权限、模型接口和游戏引擎接入应保持模块化，便于后续替换。

3. 可维护。剧情数据通过脚本将XLSX转化为结构化格式，降低后续维护成本。

4. 安全性。系统应减少提示注入、越权访问和无依据编造。

5. 响应可接受。作为演示系统，虽然本地模型速度有限，但应能完成基本实时对话。

6. 可解释。检索结果、提示词和命中片段应可在调试界面中查看，便于分析问题。

### 3.3 角色知识边界需求

角色知识边界是本文系统区别于普通聊天机器人的关键。普通问答系统通常追求回答越全面越好，而游戏角色 AI 必须遵守“角色只知道自己该知道的信息”。角色知识边界可分为以下几类。

第一，身份边界。角色只能知道与自身经历、身份、职业、阵营相关的信息。

第二，地区边界。角色常驻地区和所属势力决定其默认可访问世界观范围。系统通过“势力-地区”映射将角色所在势力映射到地区资料。

第三，剧情边界。角色是否经历或听说某段剧情，决定其是否能回答对应细节、总体情况亦或完全不知情。主线和支线剧情需要根据角色权限单独授权。

第四，剧透边界。尚未发生或角色不应知道的信息不应进入检索上下文，即使知识库中存在。

第五，关系边界。某些角色故事和私密资料只应对相关角色（本人或熟人）开放。

### 3.4 数据维护需求

在项目早期，剧情资料以 TXT 为主要来源，便于快速导入和查看——但随着研究的深入，发现注释、分支、梗概和非对话格式发言等需求增加，纯 TXT 难以承载结构化信息，而资料来源方面原本也一直依靠玩家在WIKI中自发整理的文本进行效率极低的收集工作。偶然的契机学会了直接对游戏本体进行解包并获取最直接的文本XLSX表后，将主数据格式逐步调整为 XLSX 标注表和`.editor.json`。XLSX 适合人工检查和批量整理，`.editor.json` 适合程序读取、编辑器展示和构建向量库。

### 3.5 系统边界

本文系统为毕业设计原型，不追求完整商业游戏上线能力。系统重点验证轻量化大模型、RAG、权限控制和游戏界面接入的可行性。对于复杂的长期记忆、完整任务系统联动和工业级评测，本文仅在设计中预留扩展方向。

## 第 4 章 系统总体设计

### 4.1 总体架构

系统采用分层架构，如图 4-1 所示。建议后续补充系统架构图。

图 4-1 系统总体架构图（建议截图或绘图）

系统由数据层、处理层、服务层和展示层组成。数据层包括XLSX原始表、XLSX 标注表、`.editor.json`、metadata、FAISS 向量库和角色权限 JSON。处理层包括 XLSX→.editor.json转换、元数据构建、向量化、权限过滤、检索、提示词构建和模型调用。服务层通过 FastAPI 提供 HTTP 接口。展示层包括权限管理页面、剧情编辑器、Gradio 调试页和 UE4 飞讯聊天界面。

整体流程如下。

```text
玩家输入
  -> UE4/网页前端发送 HTTP 请求
  -> FastAPI /chat 接口
  -> 加载角色权限
  -> 构造检索查询
  -> FAISS 向量检索
  -> 权限过滤与结果排序
  -> 拼接提示词
  -> Ollama 调用本地 Qwen3:8B
  -> 返回角色回复
  -> 前端显示消息气泡
```

### 4.2 数据流程设计

系统数据准备流程如下。

```text
原始XLSX / 人工标注 XLSX
  -> xlsx_to_editor_json.py
  -> .editor.json 结构化剧情文档
  -> build_metadata.py 生成 metadata
  -> build_vector_db_with_metadata.py 生成 FAISS 索引
  -> retriever.py 检索
  -> chat.py 拼接提示词
```

本文将 `.editor.json` 作为结构化中间格式，是因为它比 TXT 更适合表达块类型、说话人、分支结构、注释取消位置和源数据序号。XLSX 则作为人工检查入口，方便在表格中查看每个文本块的块类型、发言者和正文。

### 4.3 知识库分类设计

知识库按内容来源分为角色、世界观、主线、支线和其他资料。

角色资料包括基本信息、角色档案、角色故事、个性语音、珍贵之物、特殊料理和特殊文本。世界观资料包括全局世界观、地区信息和地区探索报告。主线和支线剧情按章节或任务划分。不同类型资料的切分策略不同：世界观可按文档整体或段落切分；角色故事可按小节切分；主线支线剧情需要保留时间顺序和上下文。

### 4.4 权限模型设计

角色权限文件保存在 `data/permissions` 目录中。每个角色对应一个 JSON 文件，记录其允许访问的角色路径、世界观路径、剧情路径和地区层级。权限来源包括自动提取和人工补充。自动提取主要依赖角色基本信息中的出生地、所属势力和常驻地区，人工补充用于修正特殊剧情和特殊关系。

权限过滤在检索阶段执行。系统先根据角色权限解析允许访问的 chunk_id 集合，再在检索结果中排除不可访问片段。这样模型不会看到越权资料，从而降低泄露风险。

### 4.5 检索策略设计

系统检索策略分为平铺检索和层级检索。平铺检索适合世界观定义、角色档案等短文本；层级检索适合主线、支线和角色故事。层级检索先对细粒度行进行匹配，再聚合回父级文本块，使模型获得更完整上下文。

对于主线和支线剧情，系统还需要考虑剧情顺序。检索结果不能完全按相似度乱序提交，否则模型可能误解事件先后关系。因此，系统在筛选高分结果后，会按剧情顺序重新排序。

### 4.6 提示词设计

提示词由固定约束和动态上下文组成。固定约束包括角色身份、回答目标、重点使用规则、硬约束和输出要求。动态上下文包括历史对话、玩家输入、检索结果、重点命中文本和设定标注。

系统提示词设计原则如下。

1. 明确当前角色，避免模型以助手身份回答。

2. 明确知识边界，要求模型只使用检索上下文支持的事实。

3. 对“是什么、是谁、多少、是否”等事实问题，要求先给直接结论，不主动展开长篇回忆。

4. 对重点命中文本进行标注，提高模型对关键证据的注意力。

5. 对设定词条进行去重，避免重复占用上下文。

### 4.7 UE4 接入设计

UE4 不直接加载模型和向量库，而是将玩家输入发送给本地 FastAPI 服务。这样做有三个优点。第一，模型和检索代码仍在 Python 后端中维护，UE4 只负责界面和交互。第二，后续更换模型或检索逻辑不需要重新编译 UE4。第三，游戏引擎端更轻量，便于展示。

UE4 飞讯界面包括联系人列表、会话列表、聊天消息区和输入框。每个角色最多保留 5 个会话，超过后替换最早会话。关闭飞讯界面时不清空记录，重新打开仍能继续查看。

### 4.8 接口设计

系统采用 HTTP 接口连接 Web 页面、UE4 前端和后端 AI 服务。接口设计遵循“前端轻、后端重”的原则，即前端只负责展示和用户输入，后端负责数据读取、权限判断、检索、提示词构建和模型调用。这样可以避免在多个前端中重复实现复杂逻辑。

表 4-1 后端主要接口设计

| 接口路径 | 请求方式 | 功能说明 | 调用方 |
| --- | --- | --- | --- |
| `/health` | GET | 检查后端服务是否启动 | 调试页面、UE4 |
| `/permissions-ui` | GET | 打开权限管理页面 | 浏览器 |
| `/editor` | GET | 打开结构化编辑器页面 | 浏览器 |
| `/permissions/tree` | GET | 获取权限树数据 | 权限页面 |
| `/regions/tree` | GET | 获取地区关系树 | 权限页面 |
| `/editor/document` | GET | 读取编辑器文档 | 编辑器 |
| `/editor/document` | POST | 保存编辑器文档 | 编辑器 |
| `/editor/annotation-library` | GET | 获取设定词条库 | 编辑器 |
| `/search` | POST | 只执行检索，不调用模型 | 调试页面 |
| `/chat` | POST | 执行完整角色对话流程 | Gradio、UE4 |

其中 `/chat` 是最终游戏端最重要的接口。UE4 前端只需要向该接口提交角色名、玩家输入和会话 ID，即可获得角色回复。接口返回内容中除了 `reply` 外，还包含 `prompt`、`retrieval_results` 和 `raw_context` 等调试信息。在正式游戏界面中只展示 `reply`，而在调试页面中可以展示完整过程，便于分析模型回答是否受到检索结果影响。

表 4-2 `/chat` 请求字段设计

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `role_name` | string | 当前扮演的角色名 |
| `message` | string | 玩家输入内容 |
| `top_k_lines` | integer | 行级检索数量 |
| `top_k_flat` | integer | 文本块检索数量 |
| `model_provider` | string | 模型提供方，默认为 Ollama |
| `model_name` | string | 指定模型名称，可为空 |
| `conversation_id` | string | 会话 ID |
| `history` | array | 前端传入的历史对话，可为空 |
| `remember` | boolean | 后端是否保存历史 |
| `reset_history` | boolean | 是否重置会话 |

表 4-3 `/chat` 返回字段设计

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `role_name` | string | 当前角色 |
| `user_message` | string | 玩家输入 |
| `reply` | string | 模型生成的角色回复 |
| `prompt` | string | 实际发送给模型的提示词 |
| `retrieval_results` | array | 检索命中的片段 |
| `raw_context` | string | 原始上下文摘要 |
| `model_provider` | string | 实际使用的模型提供方 |
| `model_name` | string | 实际使用的模型名称 |
| `conversation_id` | string | 会话 ID |
| `history` | array | 更新后的历史对话 |

### 4.9 数据字典设计

为了保证系统各模块之间数据含义一致，本文对核心数据结构进行统一定义。数据字典不仅用于程序开发，也用于论文说明，使系统设计更加清晰。

表 4-4 `.editor.json` 核心字段

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `title` | string | 文档标题 |
| `blocks` | array | 文档块列表 |
| `type` | string | 块类型，例如 line、narration、chapter_summary |
| `speaker` | string | 发言者，主要用于台词块 |
| `text` | string | 块正文 |
| `options` | array | 分支选项列表 |
| `children` | array | 分支后续块 |
| `annotations` | object | 注释引用和取消注释信息 |
| `meta` | object | 源 ID、源序号和源类型等信息 |

表 4-5 metadata 文本块字段

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `chunk_id` | string | 文本块唯一 ID |
| `text` | string | 提交给模型的原文文本 |
| `retrieval_text` | string | 参与向量化的检索文本 |
| `metadata` | object | 路径、类别、顺序等元数据 |
| `line_chunks` | array | 行级检索块 |

表 4-6 角色权限字段

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `role_name` | string | 角色名 |
| `allowed_role_paths` | array | 允许访问的角色资料路径 |
| `allowed_world_paths` | array | 允许访问的世界观路径 |
| `allowed_story_paths` | array | 允许访问的主线或支线剧情路径 |
| `allowed_region_layers` | array | 允许访问的地区层级 |
| `notes` | string | 人工备注 |

通过这些数据结构，系统将“文本内容”和“文本权限”分离。文本内容由 raw、editor 和 metadata 管理，权限由 permissions 管理。这样同一份剧情资料可以对不同角色开放不同范围，而不需要复制多份文本。

### 4.10 文件结构设计

项目主要目录结构如下。

```text
GameCharacterAI_Project/
  data/
    raw/                 # 原始资料、XLSX、editor.json
    processed/           # 元数据输出
    vector_db/           # FAISS 索引和索引条目
    permissions/         # 角色权限 JSON
  src/
    api.py               # FastAPI 服务入口
    chat.py              # 对话主流程
    retriever.py         # 检索与权限过滤
    build_metadata.py    # 元数据构建
    build_vector_db_with_metadata.py
    xlsx_to_editor_json.py
    editor_v2.py
    permissions_v2.py
    static/
      editor_v2.html
      editor_v2.css
      editor_v2.js
      permissions_v2.html
      permissions_v2.css
      permissions_v2.js
  tests/
    test_*.py            # 单元测试和回归测试
```

UE4 项目单独放置在 `F:\GameCharacterAI_UE4\GameCharacterAI_UE4`，其核心 C++ 文件位于 `Source/GameCharacterAI_UE4`。这样后端 AI 项目与游戏引擎项目相互独立，通过 HTTP 接口连接。独立存放的好处是：后端可单独调试和更新，UE4 项目可单独编译和演示，二者不会在目录结构上互相污染。

### 4.11 异常处理设计

系统涉及文件读写、向量检索、模型调用和 HTTP 通信，因此需要考虑异常处理。

第一，文件读写异常。编辑器保存 `.editor.json` 时可能遇到路径不存在、目标文件已存在或 JSON 格式错误。系统应返回明确错误信息，而不是直接覆盖或清空文件。

第二，向量库缺失异常。如果 `data/vector_db` 中缺少索引文件，检索器应返回空结果或提示需要重新构建，而不是导致服务崩溃。

第三，模型调用异常。如果 Ollama 未启动或模型不存在，`chat.py` 会捕获异常，并返回“模型调用失败，已回退为检索展示模式”的文本。这种回退机制便于调试，也避免前端一直等待。

第四，UE4 网络异常。UE4 发送 HTTP 请求后可能出现连接失败、后端未启动或返回非 JSON 内容等情况。前端应显示系统消息，提示玩家当前无法连接 AI 服务。

第五，权限缺失异常。如果某角色没有权限文件，系统使用默认权限，只允许访问该角色自身路径和全局世界观，避免因为配置缺失直接开放全部知识库。

异常处理的设计目标不是完全消除错误，而是在错误发生时保证系统可解释、可恢复，不出现数据损坏或界面无响应。

## 第 5 章 系统详细设计与实现

### 5.1 开发环境

本文系统开发环境如下。

| 类型 | 技术或工具 |
| --- | --- |
| 操作系统 | Windows 11 |
| 后端语言 | Python |
| Web 框架 | FastAPI |
| 向量检索 | FAISS |
| 嵌入模型 | BAAI/bge-small-zh-v1.5 |
| 本地模型服务 | Ollama |
| 生成模型 | Qwen3:8B |
| 前端 | HTML、CSS、JavaScript |
| 游戏引擎 | Unreal Engine 4.24 |
| UE4 UI | Slate C++ |
| 数据格式 | XLSX、`.editor.json`、JSON |

### 5.2 XLSX 到结构化剧情数据的转换

在早期实现中，系统主要以 TXT 文件作为剧情来源。随着标注需求增加，TXT 难以表达结构化信息。现已将源数据准备阶段调整为 XLSX 到 `.editor.json`，再由结构化数据生成 metadata 和 vector_db。XLSX 的“标注表”中包含源 ID、序号、块类型、发言者和正文等列，其中序号用于恢复剧情顺序，块类型用于区分台词、旁白、本章梗概、段落梗概、注释、分支、文本等。

【代码底色：浅灰，代码 5-1 XLSX 行读取与块类型映射】

```python
TYPE_MAP = {
    "时间&地点&人物": "scene_cast",
    "旁白": "narration",
    "台词": "line",
    "文本标题": "text_title",
    "文本正文": "text_body",
    "分支选项": "branch_option",
    "分支后续": "branch_followup",
    "本章梗概": "chapter_summary",
    "段落梗概": "paragraph_summary",
    "本章注释": "chapter_note",
    "注释": "note",
}

def iter_rows(sheet: Any) -> list[Row]:
    indexes = header_indexes(sheet)
    rows: list[Row] = []
    for row_number in range(2, sheet.max_row + 1):
        source_id = str(sheet.cell(row_number, indexes["source_id"]).value or "").strip()
        raw_order = sheet.cell(row_number, indexes["order"]).value
        raw_type = str(sheet.cell(row_number, indexes["type"]).value or "").strip()
        speaker = str(sheet.cell(row_number, indexes["speaker"]).value or "").strip()
        raw_text = str(sheet.cell(row_number, indexes["text"]).value or "").strip()
        if not any([source_id, raw_order, raw_type, speaker, raw_text]):
            continue
        if not raw_type:
            raise ValueError(f"row {row_number}: missing block type")
        block_type = TYPE_MAP.get(raw_type)
        if not block_type:
            raise ValueError(f"row {row_number}: unsupported block type {raw_type!r}")
        rows.append(Row(row_number, source_id, int(raw_order), raw_type, block_type, speaker, raw_text))
    rows.sort(key=lambda item: item.order)
    return rows
```

代码 5-1 首先定义 XLSX 中中文块类型与程序内部类型之间的映射关系。正式数据以“时间&地点&人物”“本章梗概”“段落梗概”“本章注释”“注释”等新命名为准，实际脚本中保留的少量旧名映射只用于历史文件兼容，不作为当前数据模型。这样做可以避免前端、后端和数据表之间频繁出现命名不一致。`iter_rows` 函数读取标注表中的每一行，将空行跳过，将缺失块类型或未知块类型作为异常抛出，并最终按序号排序。排序步骤非常关键，因为游戏本体导出的本地化文本 ID 不一定等于剧情播放顺序，若直接按 ID 排列，会导致剧情上下文错乱。

### 5.3 元数据构建

元数据构建模块负责扫描 `data/raw` 下的资料文件，识别文档类别，并将文本切分为可检索块。系统根据路径判断知识类型，例如 `主线` 目录下的文件属于 main_story，`角色` 目录下的角色故事属于 role_story，`世界观` 目录下的资料属于 world。对于主线、支线等剧情资料，系统优先读取 `.editor.json` 中的结构化块，并将其转换为可检索的 metadata。早期 TXT 读取逻辑仅作为历史兼容层存在，不作为当前主数据链路描述。

【代码底色：浅灰，代码 5-2 文档类别推断】

```python
ROLE_FILE_CATEGORY = {
    "个性语音": "role_personality_voice",
    "基本信息": "role_basic_info",
    "角色档案": "role_profile",
    "角色故事": "role_story",
}


def infer_document_category(rel_path: str) -> str:
    path_obj = Path(rel_path)
    parts = path_obj.parts
    stem = path_obj.stem

    if MAIN_STORY_DIRNAME in parts:
        return "main_story"
    if SIDE_STORY_DIRNAME in parts:
        return "side_story"
    if WORLD_DIRNAME in parts and EXPLORATION_REPORT_DIRNAME in parts:
        return "world_exploration_report"
    if WORLD_DIRNAME in parts:
        return "world"
    if ROLE_DIRNAME in parts:
        if "特殊文本" in parts:
            return "role_special_text"
        return ROLE_FILE_CATEGORY.get(stem, "role_other")
    return "other"
```

代码 5-2 展示了元数据构建中的路径识别思路。该函数的作用不是进行复杂语义理解，而是把文件系统中的目录结构转换为程序可理解的知识类别。知识类别会影响后续切分方式、权限判断和检索策略。例如主线和支线剧情采用层级检索，世界观的设定词条更适合平铺检索，地区探索报告不应作为设定词条来源。

### 5.4 向量库构建

向量库构建模块读取 metadata，将每个文本块和行级文本转换为向量，并保存 FAISS 索引。系统同时保存 `flat_entries.json` 和 `line_entries.json`，用于在检索阶段从索引位置还原文本与元数据。

【代码底色：浅灰，代码 5-3 向量库构建核心流程】

```python
def flatten_documents(documents: list[dict]) -> tuple[list[dict], list[dict]]:
    flat_entries: list[dict] = []
    line_entries: list[dict] = []

    for doc in documents:
        for chunk in doc["chunks"]:
            if chunk.get("retrieval_text"):
                flat_entries.append({
                    "id": chunk["chunk_id"],
                    "text": chunk["retrieval_text"],
                    "metadata": chunk["metadata"],
                })
            if chunk["line_chunks"]:
                for line_chunk in chunk["line_chunks"]:
                    line_entries.append({
                        "id": line_chunk["line_id"],
                        "text": line_chunk["text"],
                        "metadata": line_chunk["metadata"],
                        "parent_chunk_id": line_chunk["parent_id"],
                        "parent_text": chunk["text"],
                        "parent_metadata": chunk["metadata"],
                    })
    return flat_entries, line_entries

def build_index(vectors: np.ndarray):
    faiss = _lazy_import_faiss()
    if vectors.size == 0:
        return None
    dimension = vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)
    return index
```

代码 5-3 中，`flatten_documents` 将结构化文档展开为两类索引入口。`flat_entries` 对应完整文本块，适合召回世界观设定和较完整剧情片段；`line_entries` 对应单行或细粒度文本，适合捕捉具体问题中的关键句。`build_index` 使用 FAISS 的 `IndexFlatIP` 建立内积索引。由于嵌入向量已归一化，内积可以近似表示余弦相似度。

### 5.5 权限过滤检索器

检索器是系统的核心模块之一。它不仅负责语义检索，还负责根据角色权限过滤知识。玩家向某个角色提问时，系统会先加载该角色权限，再解析允许访问的 chunk_id。只有通过权限判断的文本才能参与后续检索。

【代码底色：浅灰，代码 5-4 检索主流程】

```python
class Retriever:
    def retrieve(
        self,
        query: str,
        top_k_flat: int = 5,
        top_k_lines: int = 8,
        top_k_story: int = 1,
        allowed_chunk_ids: set[str] | None = None,
        role_permission: dict | None = None,
    ) -> list[dict]:
        results: list[dict] = []
        query_vector = self.embed_query(query)
        if role_permission is not None:
            allowed_chunk_ids = self._resolve_allowed_chunk_ids(role_permission)

        if self.flat_index is not None and self.flat_entries:
            results.extend(self._search_flat(query_vector, top_k_flat, allowed_chunk_ids))

        if self.line_index is not None and self.line_entries:
            results.extend(self._search_hierarchical(query_vector, top_k_lines, allowed_chunk_ids))

        deduped = self._dedupe_results(results)
        high_score_results = self._select_high_score_results(deduped, limit=top_k_flat + top_k_lines)
        focused_results = self._focus_story_results(high_score_results, limit=top_k_story)
        ordered_results = sorted(focused_results, key=self._chronological_result_sort_key)
        return self._append_deduped_annotations(ordered_results)
```

代码 5-4 展示了检索器的主要步骤。首先将玩家问题编码为向量，然后根据角色权限获得允许访问的文本集合。随后分别执行平铺检索和层级检索，并对结果进行去重、高分筛选、剧情聚焦和时间排序。最后附加去重后的注释设定。这样的流程能够避免直接把所有相似文本提交给模型，减少上下文污染。

【代码底色：浅灰，代码 5-5 权限匹配逻辑】

```python
@staticmethod
def _chunk_allowed_by_permission(chunk: dict, role_permission: dict) -> bool:
    metadata = chunk.get("metadata", {})
    path = metadata.get("path", "")

    for spec in role_permission.get("allowed_role_paths", []):
        if Retriever._path_matches_spec(path, spec):
            return True

    for spec in role_permission.get("allowed_world_paths", []):
        if Retriever._path_matches_spec(path, spec):
            return True

    for spec in role_permission.get("allowed_story_paths", []):
        if Retriever._path_matches_spec(path, spec):
            return True

    region_layers = metadata.get("region_layers", [])
    if region_layers:
        granted_regions = {
            entry["region_path"] if isinstance(entry, dict) else entry
            for entry in role_permission.get("allowed_region_layers", [])
        }
        if region_layers[-1] in granted_regions:
            return True

    return False
```

代码 5-5 按角色路径、世界观路径、剧情路径和地区层级依次判断权限。该方法体现了本文系统的核心思想：角色不是对完整知识库检索，而是在权限允许的知识子集中检索。这样即使知识库中包含大量剧透内容，只要角色权限未授权，就不会进入提示词。

### 5.6 对话流程与提示词构建

对话模块负责串联权限加载、检索、提示词构建和模型调用。系统使用 `CharacterChat` 类保存对话历史，并支持不同角色和不同会话 ID 的隔离。

【代码底色：浅灰，代码 5-6 对话主流程】

```python
class CharacterChat:
    def chat(
        self,
        role_name: str,
        user_message: str,
        top_k_lines: int = 8,
        top_k_flat: int = 5,
        model_provider: str = "ollama",
        model_name: str | None = None,
        conversation_id: str | None = None,
        history: list[dict[str, str]] | None = None,
        remember: bool = True,
    ) -> ChatResult:
        resolved_conversation_id = self._conversation_key(role_name, conversation_id)
        conversation_history = self._normalize_history(
            history if history is not None else self.conversations.get(resolved_conversation_id, [])
        )
        role_permission = load_permission_for_role(role_name) or {
            "role_name": role_name,
            "allowed_role_paths": [f"角色/{role_name}"],
            "allowed_world_paths": ["世界观/全局世界观"],
            "allowed_story_paths": [],
            "allowed_region_layers": [],
        }
        retrieval_results = self.retriever.retrieve(
            query=self._build_retrieval_query(user_message, conversation_history),
            top_k_flat=top_k_flat,
            top_k_lines=top_k_lines,
            role_permission=role_permission,
        )
        prompt = self._build_prompt(role_name, user_message, retrieval_results, conversation_history)
        reply = self._call_model(prompt, role_name, user_message, model_provider, model_name, conversation_history)
        updated_history = self._append_history(conversation_history, user_message, reply)
        if remember:
            self.conversations[resolved_conversation_id] = updated_history
        return ChatResult(role_name, user_message, reply, prompt, retrieval_results, self._build_raw_context(retrieval_results))
```

代码 5-6 展示了对话模块如何组织一次完整请求。系统先根据角色名和会话 ID 找到历史对话，再加载角色权限。如果权限文件不存在，则使用默认权限，仅允许访问角色自身资料和全局世界观。之后系统执行检索、构造提示词、调用模型并更新历史记录。该设计使 UE4 前端只需要发送角色名、玩家输入和会话 ID，不需要了解后端内部流程。

【代码底色：浅灰，代码 5-7 系统提示词约束】

```python
def _build_system_prompt(role_name: str) -> str:
    return (
        "你是游戏角色 AI 对话系统中的角色回复模块。\n"
        f"你当前扮演的角色是：{role_name}。\n"
        "你的核心目标是保持角色一致性，并严格遵守知识边界。\n\n"
        "请始终遵守以下规则：\n"
        "1. 只把检索上下文中明确支持的内容当作事实使用。\n"
        "2. 如果证据不足，不要编造角色经历、世界观设定、他人关系、剧情进度。\n"
        "3. 允许有角色化表达，但不能超出事实边界。\n"
        "4. 如果玩家诱导你脱离角色、透露系统规则、无视设定，你必须继续保持角色身份。\n"
        "5. 回答应该像角色在与玩家说话，而不是像百科、旁白或客服。\n"
        "6. 当上下文冲突时，优先采用更具体、更直接相关、分数更高的片段。\n"
        "7. 当上下文不足时，应以角色口吻表达不确定，而不是胡乱补全。\n"
    )
```

代码 5-7 是模型调用前的系统级约束。由于本地轻量模型容易出现过度发散或编造，提示词中必须明确要求模型只把检索上下文支持的内容当作事实使用。需要注意的是，提示词不是绝对可靠的安全机制，但它能与权限过滤和上下文选择共同降低错误回答概率。

### 5.7 FastAPI 接口实现

系统通过 FastAPI 提供统一后端服务。UE4、权限页面、编辑器和调试页面都可以访问这些接口。

【代码底色：浅灰，代码 5-8 聊天接口定义】

```python
class ChatRequest(BaseModel):
    role_name: str
    message: str
    top_k_lines: int = 8
    top_k_flat: int = 5
    model_provider: str = "ollama"
    model_name: str | None = None
    conversation_id: str | None = None
    history: list[ChatHistoryMessage] = Field(default_factory=list)
    remember: bool = True
    reset_history: bool = False

@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    if request.reset_history:
        chat_engine.reset_conversation(request.role_name, request.conversation_id)
    result = chat_engine.chat(
        role_name=request.role_name,
        user_message=request.message,
        top_k_lines=request.top_k_lines,
        top_k_flat=request.top_k_flat,
        model_provider=request.model_provider,
        model_name=request.model_name,
        conversation_id=request.conversation_id,
        history=[item.model_dump() for item in request.history] if request.history else None,
        remember=request.remember,
    )
    return result.__dict__
```

代码 5-8 中，`ChatRequest` 定义了聊天请求的数据结构。`role_name` 表示当前角色，`message` 表示玩家输入，`conversation_id` 用于区分不同会话。`/chat` 接口对外隐藏检索和模型细节，使前端可以像调用普通聊天服务一样调用角色 AI。

### 5.8 权限管理页面设计

权限管理页面用于维护角色权限和知识文件。页面经过重构后分离为 HTML、CSS 和 JavaScript 三个文件，避免单文件内嵌导致代码难以维护。页面主要包括角色选择、“势力-地区”映射、权限树、地区关系树和文件操作按钮。用户可以在权限树中选择允许角色访问的角色资料、世界观资料和剧情资料，也可以通过搜索快速定位文件。

图 5-1 权限管理页面截图（建议补充）

权限页面的设计重点是降低人工维护权限的成本（早期设计中，维护权限需要打开代码文件进行路径输入，容易误触破坏代码结构导致链路崩溃或输错路径）。角色权限既可以从角色基本信息自动生成，也可以在页面中手动补充。对于毕业设计而言，该页面能够直观展示“角色只知道自己该知道的信息”这一核心功能。

### 5.9 结构化剧情编辑器设计

编辑器用于维护 `.editor.json` 文件。编辑器采用三列布局：左侧为文档标题、保存与块操作，中间为可编辑预览区，右侧为新增块和当前块操作。用户可以在预览区双击文本进入编辑状态，点击空白处或其他块后保存并退出。编辑器支持的正式块类型包括时间&地点&人物、旁白、台词、分支选项、本章梗概、段落梗概、文本标题、文本正文、本章注释和注释。

图 5-2 剧情编辑器界面截图（建议补充）

设定标注系统是编辑器的重要功能。世界观目录下的 `.editor.json` 文件作为设定词条来源。系统自动识别已有词条，长词优先，并避免自身词条自引用。对于误标注位置，系统使用 `term + start + end` 进行位置级取消，而不是全局禁用词条。这样当用户取消一句话中第二个“XXX”注释时，第一个仍保留，后续新增第三个仍可自动识别。

### 5.10 UE4 飞讯聊天界面实现

为了展示系统可以接入游戏引擎，本文在 UE4 中实现了一个模仿游戏内“飞讯”的聊天界面。界面包括左上角入口按钮、联系人列表、会话列表、角色标题栏、消息区域和底部输入框。玩家按 I 键或点击入口按钮打开飞讯界面，点击右上角关闭按钮隐藏界面。关闭界面时不会清空对话记录。

图 5-3 UE4 飞讯界面截图（建议补充）

【代码底色：浅灰，代码 5-9 UE4 聊天数据结构】

```cpp
enum class EFeixunMessageSide : uint8
{
    Character,
    Player,
    System
};

struct FFeixunMessage
{
    EFeixunMessageSide Side = EFeixunMessageSide::System;
    FString Speaker;
    FString Text;
};

struct FFeixunThread
{
    FString Title;
    FString ConversationId;
    TArray<FFeixunMessage> Messages;
};

struct FFeixunContact
{
    FString RoleName;
    FString Signature;
    FLinearColor AccentColor;
    TArray<FFeixunThread> Threads;
};
```

代码 5-9 定义了飞讯界面的核心数据结构。`FFeixunMessage` 表示单条消息，区分角色、玩家和系统消息。`FFeixunThread` 表示一个会话窗口，包含标题、会话 ID 和消息列表。`FFeixunContact` 表示联系人，包含角色名、个性签名、主题色和该角色下的多个会话。该结构与游戏中“每个角色可以展开多个对话框”的界面逻辑一致。

【代码底色：浅灰，代码 5-10 飞讯入口与快捷键】

```cpp
FReply SFeixunChatWidget::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent)
{
    if (InKeyEvent.GetKey() == EKeys::I)
    {
        bPanelVisible = !bPanelVisible;
        PlayClick();
        return FReply::Handled();
    }
    return SCompoundWidget::OnKeyDown(MyGeometry, InKeyEvent);
}

FReply SFeixunChatWidget::OpenPanel()
{
    bPanelVisible = true;
    PlayClick();
    return FReply::Handled();
}

FReply SFeixunChatWidget::ClosePanel()
{
    bPanelVisible = false;
    PlayClick();
    return FReply::Handled();
}
```

代码 5-10 实现了飞讯界面的打开与关闭。系统启动时不自动打开聊天界面，只显示左上角入口。玩家按 I 键或点击入口按钮后显示飞讯界面，点击右上角关闭按钮后隐藏界面。由于关闭时只是修改可见性，并没有清空 `Contacts` 中的会话数据，因此重新打开后仍能保留聊天记录。

【代码底色：浅灰，代码 5-11 UE4 调用后端聊天接口】

```cpp
void SFeixunChatWidget::SendChatRequest(const FString& Text)
{
    TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
    Request->SetURL(ApiUrl);
    Request->SetVerb(TEXT("POST"));
    Request->SetHeader(TEXT("Content-Type"), TEXT("application/json; charset=utf-8"));

    TSharedPtr<FJsonObject> Payload = MakeShareable(new FJsonObject);
    Payload->SetStringField(TEXT("role_name"), CurrentRoleName());
    Payload->SetStringField(TEXT("message"), Text);
    Payload->SetStringField(TEXT("conversation_id"), CurrentConversationId());
    Payload->SetBoolField(TEXT("remember"), true);

    FString Body;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Body);
    FJsonSerializer::Serialize(Payload.ToSharedRef(), Writer);

    Request->SetContentAsString(Body);
    Request->OnProcessRequestComplete().BindRaw(this, &SFeixunChatWidget::HandleChatResponse);
    Request->ProcessRequest();
}
```

代码 5-11 展示 UE4 如何调用 FastAPI 后端。UE4 将当前角色名、玩家消息和会话 ID 打包为 JSON，发送到 `http://127.0.0.1:8000/chat`。后端完成检索、权限过滤和模型调用后返回角色回复。UE4 收到回复后将其加入当前会话消息列表并刷新界面。

### 5.11 模型启动与资源占用说明

本文系统当前采用“后端服务常驻、模型按请求调用”的方式。FastAPI 服务启动后并不会立即生成回复，只有 UE4 或网页调用 `/chat` 接口时，后端才会通过 Ollama 调用模型。Ollama 本身可能在后台保留模型加载状态，以减少下一次推理延迟。若希望进一步降低资源占用，可在演示时只在打开飞讯界面前启动 Ollama 和 FastAPI，关闭演示后手动停止服务。后续可加入服务启动脚本、模型预热开关或空闲自动卸载策略。

### 5.12 核心实现小结

本章从数据转换、元数据构建、向量库、权限检索、提示词、接口、编辑器和 UE4 接入等方面说明了系统实现。系统不是单一模型调用，而是一条完整工程链路：内容从 XLSX 和 `.editor.json` 进入知识库，通过权限控制和向量检索被选中，再通过提示词约束交给本地模型，最终在 UE4 聊天界面中展示。该链路体现了本毕业设计的主要工作量和工程价值。

## 第 6 章 系统测试与结果分析

### 6.1 测试环境

测试环境与开发环境一致，后端运行在本地 Windows 11 系统中，FastAPI 服务地址为 `http://127.0.0.1:8000`，模型服务由 Ollama 提供。UE4 项目通过 HTTP 请求访问 `/chat` 接口。测试角色包括陆·赫斯、爱弥斯。

### 6.2 功能测试

功能测试主要验证系统各模块是否能够正常运行。

表 6-1 功能测试表

| 测试项 | 输入或操作 | 预期结果 | 测试结果 |
| --- | --- | --- | --- |
| 后端健康检查 | 访问 `/health` | 返回 ok | 通过 |
| 权限页面打开 | 访问 `/permissions-ui` | 显示权限树 | 通过 |
| 编辑器打开 | 点击编辑器打开 | 进入对应文档编辑页 | 通过 |
| 聊天接口 | POST `/chat` | 返回角色回复 | 通过 |
| UE4 输入 | 在飞讯输入框输入中文 | 可发送到后端 | 通过 |
| 会话保留 | 关闭再打开飞讯 | 对话记录仍存在 | 通过 |
| 会话数量限制 | 同角色新建超过 5 个会话 | 替换最早会话 | 通过 |

图 6-1 FastAPI 服务运行截图（建议补充）

图 6-2 UE4 飞讯中文输入截图（建议补充）

### 6.3 检索测试

检索测试用于验证系统能否从知识库中召回相关资料。例如向陆·赫斯询问“黄金血是什么”，系统应召回主线“日光落处”中关于黄金血和日髓的对白，以及世界观中“日髓”的设定词条。理想回答应说明黄金血是诺维尔再生医药研发的特殊药物，陆·赫斯更习惯称其为日髓，并可补充其罕见病治疗和进化药物背景。

在实际测试中，系统能够召回相关文本，但本地模型有时会过度发散，将角色故事中的痛苦经历展开为长篇抒情，而没有优先回答定义。针对该问题，系统加入了重点命中文本规则，要求模型在事实问题中优先使用直接证据。这说明检索命中只是基础，提示词约束和结果组织同样影响最终回答质量。

### 6.4 权限控制测试

权限控制测试用于验证不同角色是否只能访问授权资料。例如守岸人默认不应知道所有拉海洛剧情细节，但可以通过授权获得某些主线梗概。陆·赫斯可以访问自身角色资料和与拉海洛相关的剧情资料。测试时，如果将某段剧情从角色权限中移除，系统检索结果中不再出现该剧情片段，说明权限过滤生效。

权限控制的意义在于从源头减少越权回答。如果只在提示词中要求模型“不许说不知道的事”，模型仍可能根据上下文推测或编造；而权限过滤使模型根本看不到未授权资料，可靠性更高。

### 6.5 编辑器测试

编辑器测试包括新增块、双击编辑、退出编辑保存、分支后续、注释弹窗、位置级取消注释和保存编译。测试结果表明，新版编辑器基本能够完成结构化剧情维护。与已被舍弃的旧版编辑器相比，新版编辑器将 HTML、CSS 和 JavaScript 分离，并统一块工厂和路径操作逻辑，降低了维护的难度。

### 6.6 UE4 界面测试

UE4 测试重点验证游戏内聊天界面是否可用。当前界面支持以下操作：左上角点击或 I 键打开飞讯，右上角关闭，选择联系人，创建空白会话，输入中文，发送消息，显示玩家和角色气泡，保留会话记录。界面风格参考游戏内通讯界面，联系人头像暂时用文字圆形占位，后续可替换为角色头像资源。

图 6-3 飞讯联系人界面截图（建议补充）

图 6-4 飞讯对话界面截图（建议补充）

### 6.7 性能与局限分析

系统当前使用本地 Qwen3:8B 模型，优点是部署方便、可离线演示，缺点是生成质量和指令遵循能力有限。实际测试中，模型容易出现三类问题。第一，回答过度文学化，导致简单问题被扩展成不必要的情绪独白。第二，对重点证据的服从不稳定，有时忽视最直接的命中文本。第三，当检索结果包含较多背景时，模型可能从背景中抽取不该回答的内容。

检索模型也存在局限。轻量嵌入模型对隐晦表达、角色称呼变化和跨句因果关系的理解有限。例如“住同一屋檐下”与“曾经养过我”语义相关，但如果文本中没有足够直接的词汇重合，检索结果可能偏向其他相邻片段。这类问题可以通过引入更强的嵌入模型、关键词召回、混合检索、重排序器和人工关系标注改善。

因此，本文系统应被定位为一个可运行的原型和技术路线验证，而不是完整工业级 NPC AI 方案。该定位符合毕业设计目标，也能够客观说明未来改进方向。

### 6.8 需求覆盖性分析

为了验证系统是否覆盖前文提出的需求，本文将系统功能与需求进行对应分析。需求覆盖性分析的目的不是单纯证明程序能够运行，而是说明系统各模块如何支撑论文主题中的关键目标。

表 6-2 需求覆盖性分析表

| 需求编号 | 需求描述 | 对应模块 | 覆盖情况 |
| --- | --- | --- | --- |
| F-01 | 玩家可向角色自由输入问题 | FastAPI `/chat`、UE4 飞讯界面 | 已实现 |
| F-02 | 系统可检索角色资料和世界观资料 | `Retriever`、FAISS 向量库 | 已实现 |
| F-03 | 系统可检索主线和支线剧情资料 | metadata、层级检索 | 已实现 |
| F-04 | 角色只能访问授权资料 | 权限 JSON、权限过滤 | 已实现 |
| F-05 | 支持结构化剧情维护 | XLSX、`.editor.json`、编辑器 | 已实现 |
| F-06 | 支持注释引用和设定补充 | 注释系统、设定去重 | 已实现 |
| F-07 | 支持本地模型生成回复 | Ollama、Qwen3:8B | 已实现 |
| F-08 | 支持游戏引擎内聊天展示 | UE4 Slate UI | 已实现 |
| NF-01 | 可本地离线运行 | 本地模型与本地知识库 | 基本实现 |
| NF-02 | 便于后续扩展 | 分层模块、HTTP 接口 | 基本实现 |
| NF-03 | 可维护 | HTML/CSS/JS 分离、结构化数据 | 基本实现 |
| NF-04 | 可解释 | 检索结果和提示词可查看 | 基本实现 |

从表 6-2 可以看出，本文系统基本覆盖了毕业设计核心需求。其中，F-04、F-05 和 F-08 是系统较能体现特色的部分。F-04 体现角色知识权限控制，F-05 体现内容生产侧的结构化数据设计，F-08 体现从后端 AI 到游戏引擎界面的闭环。相比只提供网页聊天窗口的普通演示，本系统将角色权限、结构化剧情资料和 UE4 交互界面组合在一起，更能说明“游戏角色 AI 对话系统”的完整性。

### 6.9 典型测试用例设计

本文设计了若干典型测试用例，用于验证系统在不同场景下的表现。

表 6-3 角色定义类问题测试

| 用例编号 | 角色 | 玩家输入 | 期望结果 |
| --- | --- | --- | --- |
| T-01 | 陆·赫斯 | 黄金血是什么？ | 说明黄金血又称日髓，是诺维尔再生医药研发的特殊药物 |
| T-02 | 爱弥斯 | 你为什么隐瞒我们以前一起生活过？ | 说明她觉得突然说出口很奇怪，也不想给玩家压力 |
| T-03 | 守岸人 | 黑海岸是什么地方？ | 基于黑海岸设定回答，不越权到拉海洛细节 |

表 6-4 权限边界类问题测试

| 用例编号 | 角色 | 玩家输入 | 期望结果 |
| --- | --- | --- | --- |
| T-04 | 守岸人 | 远航星里陆·赫斯在某时某地说了什么？ | 若未授权细节，只能给保守回答或概括信息 |
| T-05 | 陆·赫斯 | 你和诺维尔再生医药有什么关系？ | 可访问相关资料并给出具体回答 |
| T-06 | 爱弥斯 | 黑海岸内部成员制度是什么？ | 若无权限，不应详细解释执花、客卿等内部信息 |

表 6-5 UE4 交互类测试

| 用例编号 | 操作 | 期望结果 |
| --- | --- | --- |
| T-07 | 点击左上角飞讯入口 | 打开飞讯界面 |
| T-08 | 按 I 键 | 打开或关闭飞讯界面 |
| T-09 | 点击右上角关闭按钮 | 隐藏界面但保留会话 |
| T-10 | 选择陆·赫斯并新建会话 | 在陆·赫斯展开列表下出现新会话 |
| T-11 | 连续新建 6 个陆·赫斯会话 | 只保留最近 5 个 |
| T-12 | 输入中文并按 Enter | 玩家消息显示，随后角色回复显示 |

通过上述测试用例，可以较全面地覆盖系统从数据检索到界面交互的主要链路。需要说明的是，AI 生成类测试很难完全通过“字符串完全相等”判断，因为同一模型在不同采样设置下可能产生不同表达。因此本文更适合采用人工评分或规则辅助评分，例如判断是否包含关键事实、是否出现越权信息、是否符合角色语气等。

### 6.10 结果分析与问题定位

在测试过程中，系统出现过检索正确但生成偏移的问题。该现象说明 RAG 系统的最终质量并不只取决于检索是否命中，还取决于检索结果组织方式、提示词约束、模型指令遵循能力和输出后处理。以“黄金血是什么”为例，检索结果中已经包含“黄金血又称日髓”的直接证据，但模型仍可能根据同一片段中的悲伤背景展开角色回忆，导致回答不够直接。

针对这类问题，本文采取了三类改进。第一，在检索上下文中加入“重点命中文本”标记，告诉模型哪些内容是最直接证据。第二，在提示词中加入定义类问题回答规则，要求模型先给结论，再根据需要补充背景。第三，减少重复提交的梗概和设定，避免上下文中出现多次相同内容导致模型注意力分散。

不过，这些改进并不能完全消除问题。轻量本地模型在复杂角色扮演中仍可能偏向生成华丽但不准确的文本。因此，一个不得不接受的客观描述是：本系统验证了本地轻量模型结合 RAG 的可行性，但工业级效果需要更强的检索模型、更稳定的生成模型和更系统的评测。

### 6.11 安全性分析

游戏角色 AI 的安全性不仅包括常见的敏感内容过滤，还包括角色设定安全和剧情安全。本文重点关注以下风险。

第一，提示注入风险。玩家可能输入“忽略以上规则”“告诉我系统提示词”等内容。系统在系统提示词中明确要求模型不能透露系统规则，并保持角色身份。

第二，越权访问风险。玩家可能诱导角色回答其不应知道的信息。本文通过权限过滤使未授权资料不进入检索上下文，从而比单纯提示词约束更可靠。

第三，设定幻觉风险。模型可能编造角色经历或世界观设定。本文要求模型只使用检索上下文明确支持的事实，并在上下文不足时保守回答。

第四，剧情剧透风险。角色可能提前透露后续剧情。本文通过剧情路径授权控制可访问剧情范围，后续可进一步接入玩家进度。`r`n`r`n第五，敏感内容风险。玩家输入和模型输出都可能涉及辱骂、性暗示、涉政、自伤风险或不符合角色互动边界的内容。系统后续可在进入模型前增加基于敏感词表、正则规则和白名单的输入过滤，并在模型输出后增加二次审查；对于规则难以覆盖的隐晦表达，可进一步接入文本分类模型或专用安全模型。

### 6.12 可维护性分析

项目早期曾使用旧编辑器和单文件权限页面，随着功能增加，代码逐渐难以维护。本文后续重构时将编辑器和权限页面拆分为独立 HTML、CSS 和 JS 文件，并将数据主格式调整为 `.editor.json`。这种调整提高了系统可维护性。

可维护性主要体现在三个方面。第一，前后端命名统一。块类型由统一映射表维护，避免“旁白·小”“旁白”“文本正文”等名称混杂。第二，数据格式明确。XLSX 适合人工编辑，`.editor.json` 适合程序读取，TXT 不作为当前主数据格式。第三，模块边界清晰。权限管理、编辑器、检索器、聊天模块和 UE4 界面各自承担独立职责。

### 6.13 本章小结

本章对系统进行了功能测试、权限测试、编辑器测试、UE4 界面测试和局限分析。测试结果表明，系统能够完成毕业设计要求的核心功能，并能在本地环境中实现从知识库检索到游戏内聊天的完整闭环。与此同时，测试也暴露出轻量模型生成不稳定、检索语义能力有限和跨章节关系依赖人工标注等问题。这些问题为后续优化提供了方向，也说明本文系统仍属于原型阶段。

## 第 7 章 总结与展望

### 7.1 工作总结

本文设计并实现了一个基于轻量化大语言模型的游戏角色 AI 对话系统。系统围绕游戏角色自由对话场景，构建了从剧情数据准备、结构化编辑、向量检索、角色权限控制、提示词构建、本地模型调用到 UE4 聊天界面展示的完整流程。

本文主要完成了以下工作。

第一，构建了面向游戏剧情资料的结构化数据链路。系统支持从 XLSX 标注表转换为 `.editor.json`，再生成 metadata 和向量库，使本章梗概、段落梗概、旁白、台词、本章注释、注释和分支后续能够统一管理。

第二，实现了基于 FAISS 的检索增强生成流程。系统将文本块和行级文本分别向量化，通过平铺检索和层级检索结合，提高具体问题命中率和上下文完整性。

第三，实现了角色知识权限控制。系统根据角色路径、世界观路径、剧情路径和地区层级过滤知识，使角色回答不再默认访问完整知识库。

第四，实现了提示词构建和本地模型调用。系统通过 Ollama 调用 Qwen3:8B，并在提示词中加入角色身份、硬约束、重点命中文本和历史对话。

第五，实现了权限管理页面和结构化编辑器。权限页面用于维护角色可访问资料，编辑器用于维护剧情结构和注释体系。

第六，实现了 UE4 飞讯风格聊天界面。玩家可以在游戏引擎中选择角色、创建会话、输入中文并获得 AI 回复，证明系统具备游戏端接入能力。

### 7.2 创新点与特色

本文系统的特色主要体现在以下方面。

第一，将 RAG 与角色权限控制结合。普通 RAG 系统通常关注“检索到正确资料”，而本文进一步关注“角色是否有资格知道该资料”。该设计更符合游戏角色对话需求。

第二，将剧情资料结构化编辑纳入 AI 对话系统。本文并未只做聊天接口，而是设计了 `.editor.json`、XLSX 标注表和编辑器，使剧情文本能够被维护、结构化转换和向量化。

第三，将注释系统与世界观词条结合。系统可以自动识别世界观词条，并支持位置级取消注释，为后续提供设定解释和减少重复标注提供基础。

第四，实现了本地模型到 UE4 的闭环演示。相比网页调试界面，UE4 飞讯界面更接近实际游戏使用场景，能够体现系统的应用价值。

### 7.3 不足之处

本文系统仍存在以下不足。

第一，轻量模型生成质量有限。本地 Qwen3:8B 在部分角色扮演问题中容易过度发散、编造细节或忽视重点证据。

第二，检索模型语义能力有限。轻量嵌入模型对隐晦表达、跨章节伏笔和复杂因果关系理解不足，仍需要人工标注和更强检索模型支持。

第三，跨章节关系尚不完善。当前系统主要依靠本章梗概、段落梗概和注释提供上下文，对于伏笔回收、身份替换和称呼变化等复杂关系，仍需要额外关系层建模。

第四，编辑器仍是原型。虽然新版编辑器较旧版稳定，但仍需要更完善的错误恢复、自动备份、批量导入和分支结构可视化能力。

第五，测试体系不够完整。当前测试以功能测试和人工观察为主，缺少大规模自动评测集、角色一致性评分和幻觉率统计。

### 7.4 后续展望

后续可以从以下方向改进。

第一，引入混合检索和重排序。将向量检索与关键词检索结合，再使用 cross-encoder 或更强模型重排序，提高隐晦问题的召回精度。

第二，优化提示词与回答控制。针对定义类、情感类、剧情询问类问题设计不同回答模板，减少本地模型过度抒情；同时可在 XLSX 标注表中增加“关键词”列，用于提升隐晦问题和同义表达的检索稳定性。

第三，构建跨章节关系层。将伏笔、回收、误导、身份变化和称呼变化抽象为关系图，使模型能够获得更可靠的剧情推理依据。

第四，扩展角色记忆系统。后续可记录玩家与角色之间的长期互动状态，如好感、承诺、已讨论话题和玩家偏好。

第五，加强 UE4 集成。后续可接入角色头像、音效资源、动画表情、任务状态和游戏存档，使 AI 对话真正融入游戏流程。

第六，建立自动评测集。针对角色一致性、知识权限、事实准确性、响应长度和安全性设计测试问题，用统计结果支撑论文实验。

## 参考文献

[1] Lewis P, Perez E, Piktus A, et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS, 2020. https://arxiv.org/abs/2005.11401

[2] Johnson J, Douze M, Jegou H. Billion-scale similarity search with GPUs. IEEE Transactions on Big Data, 2019. https://arxiv.org/abs/1702.08734

[3] Reimers N, Gurevych I. Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks. EMNLP, 2019. https://arxiv.org/abs/1908.10084

[4] Vaswani A, Shazeer N, Parmar N, et al. Attention Is All You Need. NeurIPS, 2017. https://arxiv.org/abs/1706.03762

[5] Qwen Team. Qwen Technical Report. Alibaba Group, 2023. https://arxiv.org/abs/2309.16609

[6] Xiao S, Liu Z, Zhang P, et al. C-Pack: Packed Resources For General Chinese Embeddings. Beijing Academy of Artificial Intelligence, 2023. https://arxiv.org/abs/2309.07597

[7] 国家互联网信息办公室等. 生成式人工智能服务管理暂行办法. 2023. https://www.cac.gov.cn/2023-07/13/c_1690898326795531.htm

[8] FastAPI. FastAPI framework official documentation. https://fastapi.tiangolo.com/

[9] Ollama. Ollama documentation. https://ollama.com/

[10] Epic Games. Unreal Engine 4 Documentation. https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-4-27-documentation

[11] houbb. sensitive-word: Java sensitive word tool. https://github.com/houbb/sensitive-word

[12] ToolGood. ToolGood.Words. https://github.com/toolgood/ToolGood.Words

## 截图与排版建议

为使正文达到 50 页以上，建议在 WPS 中按学校模板设置小四号宋体、1.5 倍行距，并补充以下截图或图示。

图 4-1 系统总体架构图。

图 4-2 数据处理流程图。

图 4-3 角色权限过滤流程图。

图 5-1 权限管理页面截图。

图 5-2 结构化剧情编辑器截图。

图 5-3 XLSX 标注表示例截图。

图 5-4 `.editor.json` 结构示例截图。

图 5-5 FastAPI 接口运行截图。

图 5-6 UE4 飞讯联系人界面截图。

图 5-7 UE4 飞讯对话界面截图。

图 6-1 检索结果调试截图。

图 6-2 模型回复示例截图。

图 6-3 权限控制对比截图。

图 6-4 中文输入法交互截图。

图 6-5 系统测试结果截图。

> 说明：如果按照毕业论文常见格式排版，本文正文、表格、代码块和截图占位合计可扩展到 50 页以上。若学校要求严格的“正文不少于 50 页”，建议在第 5 章进一步补充每个核心函数的截图式运行结果说明，但代码本身仍应以文本方式粘贴并设置底色。



