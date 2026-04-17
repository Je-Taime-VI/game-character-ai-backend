# 编辑器重构方案与 `.editor.json` V4 草案

## 1. 当前问题归纳

现有编辑器的问题不在单点 bug，而在职责边界已经塌掉：

- `src/story_editor.py` 同时承担旧格式兼容、TXT 解析、`.editor.json` 归一化、注释词库构建、世界观注释创建、导出编译。
- `src/static/editor.js` 同时承担状态管理、路径寻址、渲染、分支切换、注释自动识别、位置级取消注释、弹窗交互。
- 旧命名兼容层与新逻辑混杂，导致“看起来能跑，但改一个点会牵出别的链路”。
- 当前保存模型仍然默认联动 `.txt`，这会继续放大 BOM、乱码、磁盘回写和兼容层污染问题。

结论：不应继续修补旧编辑器，应将“文档模型”“注释引擎”“导出编译”“前端视图”拆开，做一个新的最小可用版本。

## 2. 重构目标

这次重构优先满足以下目标：

- 主格式只认 `.editor.json`，`.txt` 退化为导出物。
- 三列布局稳定，选中块、编辑块、预览块之间的一致性可验证。
- 新增、插入、分支内新增共用同一套块工厂和路径操作。
- 注释系统保留核心规则：
  - 世界观 `.editor.json` 是唯一正式来源
  - 默认自动注释
  - 长词优先
  - 禁止自身词条自引用
  - 标题行不参与注释
  - 取消注释精确到 `term + start + end`
- 后续建库可直接消费 `.editor.json`，不再反向依赖原始 `.txt`

## 3. 新架构建议

建议把编辑器相关能力拆成 4 层：

### 3.1 文档模型层

文件建议：

- `src/editor_schema.py`
- `src/editor_document.py`

职责：

- 定义块类型、文档版本、标准字段
- 负责文档 normalize / validate / migrate
- 提供块工厂 `create_block(type)`、选项工厂 `create_option()`、路径读写工具

这一层不做 HTML，不做 FastAPI，不做注释识别。

### 3.2 注释引擎层

文件建议：

- `src/editor_annotations.py`

职责：

- 扫描 `data/raw/世界观/**/*.editor.json`
- 构建注释词库
- 根据文本生成命中 span
- 处理长词优先、重叠消解、自身词条排除、位置级 omission

输入输出应尽量纯函数化，例如：

```python
def detect_annotation_spans(
    text: str,
    entries: list[AnnotationEntry],
    *,
    excluded_terms: set[str],
    omissions: list[AnnotationOmission],
) -> list[AnnotationSpan]:
    ...
```

### 3.3 持久化与导出层

文件建议：

- `src/editor_storage.py`
- `src/editor_export.py`

职责：

- 只负责读写 `.editor.json`
- 导出 `.txt` 时从结构化文档生成文本
- 明确区分“保存文档”和“导出 txt”，不要再隐式混写

建议保存策略：

- 编辑器保存：只写 `.editor.json`
- 手动“保存并编译”：写 `.editor.json`，再额外生成 `.txt`
- 世界观注释新建：直接生成 `词条名.editor.json`

### 3.4 前端编辑器层

文件建议：

- `src/static/editor.html`
- `src/static/editor.css`
- `src/static/editor.js`

但 `editor.js` 内部要再拆模块概念：

- `store`: 当前文档状态、选中路径、分支选中状态
- `ops`: block/path 增删改移
- `annotation`: 注释检测与交互状态
- `render`: 预览渲染、右侧表单渲染、弹窗渲染
- `api`: 加载、保存、导出、世界观注释创建

即使暂时仍放一个 JS 文件，也要按这 5 段组织，不再堆成一个大状态机。

## 4. `.editor.json` V4 设计

### 4.1 文档结构

建议下一版文档结构：

```json
{
  "version": 4,
  "path": "主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.editor.json",
  "title": "日光落处",
  "doc_type": "story",
  "meta": {
    "source": "editor",
    "export_txt": true
  },
  "blocks": []
}
```

字段说明：

- `version`: 文档版本，V4 作为重构起点
- `path`: 文档相对路径
- `title`: 文档标题
- `doc_type`: 建议至少区分 `story` / `annotation`
- `meta`: 预留扩展位，不把临时 UI 状态塞进根节点
- `blocks`: 结构化内容

### 4.2 块类型

保留并固定以下块类型：

- `scene_cast`
- `line`
- `narration_large`
- `narration_small`
- `narration_supplement`
- `summary`
- `branch`

说明：

- 这里的数据层命名建议显式化，用 `narration_large` 替代现在的 `narration`
- UI 文案仍显示“旁白·大”
- 如果要兼容旧数据，可在迁移层把旧 `narration` 映射为 `narration_large`

### 4.3 文本块统一结构

所有可注释文本节点建议统一带一个 `annotations` 字段，而不是分散成 `annotation_refs` 和 `annotation_omissions` 顶在块根上。

```json
{
  "id": "blk_a1b2c3d4",
  "type": "line",
  "speaker": "卡提希娅",
  "text": "先天型共鸣者并不等同于所有共鸣者。",
  "annotations": {
    "manual_refs": [],
    "omissions": [
      { "term": "共鸣者", "start": 11, "end": 14 }
    ]
  }
}
```

这样做的原因：

- `manual_refs` 与 `omissions` 都属于注释配置，不应散在块根
- 以后若增加 `manual_only`、`disabled`、`resolved_spans_cache` 之类字段，扩展更自然

### 4.4 各块结构

#### `scene_cast`

```json
{
  "id": "blk_x1",
  "type": "scene_cast",
  "text": "港口栈桥，漂泊者与守岸人"
}
```

#### `line`

```json
{
  "id": "blk_x2",
  "type": "line",
  "speaker": "守岸人",
  "text": "你终于来了。"
}
```

#### `narration_large`

```json
{
  "id": "blk_x3",
  "type": "narration_large",
  "text": "夜色像一层缓慢收束的潮。",
  "style": {
    "italic": false
  }
}
```

#### `narration_small`

```json
{
  "id": "blk_x4",
  "type": "narration_small",
  "text": "风里有潮湿的铁味。"
}
```

#### `narration_supplement`

```json
{
  "id": "blk_x5",
  "type": "narration_supplement",
  "text": "这里补充的是设定或舞台提示。"
}
```

#### `summary`

```json
{
  "id": "blk_x6",
  "type": "summary",
  "text": "本段剧情描述角色在港口重逢，并暗示后续分支选择。"
}
```

#### `branch`

```json
{
  "id": "blk_x7",
  "type": "branch",
  "speaker": "漂泊者",
  "options": [
    {
      "id": "opt_01",
      "label": "询问港口最近的异动",
      "annotations": {
        "manual_refs": [],
        "omissions": []
      },
      "children": []
    },
    {
      "id": "opt_02",
      "label": "先谈守岸人的伤势",
      "annotations": {
        "manual_refs": [],
        "omissions": []
      },
      "children": []
    }
  ]
}
```

分支统一规则：

- 分支主体字段统一叫 `speaker`
- 选项内容统一叫 `label`
- 选项后续内容统一叫 `children`
- 不再使用 `response_blocks`

这样新增 / 插入 / 分支内新增能全部抽象为“往某个 block list 里插入 block”。

## 5. 路径与操作模型

旧版最容易出 bug 的点就是“根块”和“分支子块”的寻址不一致。

新版本建议统一使用列表路径：

```json
[
  { "kind": "blocks", "index": 3 },
  { "kind": "options", "index": 1 },
  { "kind": "children", "index": 2 }
]
```

不要再混用数字路径和字符串路径片段。

配套提供统一操作：

- `get_node_by_path(path)`
- `get_list_by_parent_path(path)`
- `insert_block(path, position, block)`
- `update_block(path, patch)`
- `delete_block(path)`
- `move_block(path, delta)`

无论是：

- 右侧新增块
- 左侧插入块
- 分支内部新增块

都调用同一批操作函数。

## 6. 注释系统 V2 设计

### 6.1 注释来源

唯一正式来源：

- `data/raw/世界观/**/*.editor.json`

注释词条规则：

- 词条名 = 文件名去掉 `.editor.json`
- 注释正文 = 文档内可见正文文本
- 如果正文第一条有效文本和 `title` 相同，应在构建注释词库时自动去重

### 6.2 注释配置

可注释文本节点统一使用：

```json
{
  "annotations": {
    "manual_refs": [],
    "omissions": [
      { "term": "罗伊族", "start": 5, "end": 8 }
    ]
  }
}
```

规则：

- 自动命中是默认行为
- `manual_refs` 用于手工补充
- `omissions` 用于位置级取消

最终渲染命中逻辑：

`effective_spans = auto_detected + manual_refs_expanded - omissions`

### 6.3 长词优先

词库构建完成后按以下顺序排序：

1. 词长降序
2. 同长度按词条字典序

扫描文本时使用占位数组或区间树消解重叠，确保长词先占位。

### 6.4 自身词条排除

当前打开的是世界观词条文档时：

- 从路径推导当前主词条名
- 自动识别时把该词条加入 `excluded_terms`

这样 `炉芯.editor.json` 正文里的“炉芯”不会自引用。

### 6.5 标题不参与注释

标题是文档元数据，不属于正文块，不进入注释检测。

### 6.6 点击行为

点击预览区注释词时应同时做两件事：

- 将当前选中定位到这次命中的 source path
- 在右侧出现“取消注释”操作
- 打开注释详情弹窗

这里“取消注释”针对的是本次命中的 `term + start + end`，不是整词全局禁用。

## 7. MVP 范围

建议新的最小可用版本只做这些：

### 7.1 必做

- 加载 `.editor.json`
- 三列布局
- 预览区稳定选中
- 右侧编辑当前块
- 新增 / 插入 / 上移 / 下移 / 删除
- 分支块新增选项
- 分支选项下新增子块
- 自动注释
- 长词优先
- 自身词条排除
- 位置级取消注释
- 新建注释到世界观文件夹
- 保存 `.editor.json`
- 手动导出 `.txt`

### 7.2 暂缓

- 旧 `.txt` 自动迁移编辑
- 复杂富文本
- 拖拽排序
- 批量替换
- 块级注释列表
- 所有历史兼容别名继续保留

MVP 的原则是先稳定，不追求把旧功能一次性补齐。

## 8. 迁移策略

建议分 3 步做：

### 第一步：先冻结旧编辑器

- 旧接口继续保留，只做只读或最低限度维护
- 不再往旧数据模型上新增能力

### 第二步：建立 V4 文档层

- 新增文档 schema、路径操作、注释引擎
- 先用少量样本文档验证
- 可以先只支持 `.editor.json`

### 第三步：写迁移脚本

建议新增：

- `scripts/migrate_editor_json_v3_to_v4.py`

迁移内容：

- `narration -> narration_large`
- `supplement -> narration_supplement`
- `option_speaker -> speaker`
- `response_blocks -> children`
- `annotation_refs + annotation_omissions -> annotations`

迁移完成后，再考虑删旧兼容层。

## 9. 建议的下一步实现顺序

最推荐的落地顺序：

1. 先实现后端 V4 文档模型与注释引擎
2. 再写新的前端 MVP
3. 再接“保存并导出 txt”
4. 最后做 V3 到 V4 迁移脚本

如果只选一个立刻开工的点，优先级最高的是：

1. `editor_schema.py` + `editor_document.py`
2. `editor_annotations.py`
3. 前端新的块路径与块工厂

## 10. 对当前代码的处理建议

短期内建议保留但逐步边缘化：

- `src/story_editor.py`
- `src/static/editor.js`

不建议继续在这些文件里深挖修补的原因：

- 当前问题不是某几个 if 写错，而是结构已经不适合继续承载重构需求
- 每继续补一个点，未来迁移成本都会更高

更稳妥的做法是：

- 新建 V4 模块
- 新前端先挂到独立入口
- 待 MVP 稳定后再替换旧入口
