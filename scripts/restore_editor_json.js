const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const ROOT = "F:/GameCharacterAI_Project";

const TITLE_PREFIX = "【文档标题：";
const SCENE_PREFIX = "【场景＆人物：";
const LEGACY_SCENE_PREFIX = "【场景标题：";
const BLOCK_TITLE_PREFIX = "【标题：";
const SUMMARY_PREFIX = "【剧情梗概：";
const ANALYSIS_PREFIX = "【解析：";
const NARRATION_PREFIX = "【旁白：";
const BODY_PREFIX = "【正文：";
const LEGACY_NARRATION_SMALL_PREFIX = "【旁白·小：";
const LEGACY_SUPPLEMENT_PREFIX = "【补充旁白：";
const OPTION_START = "→";
const OPTION_NEXT = "←→";
const OPTION_END = "←";
const DEFAULT_OPTION_SPEAKER = "漂泊者";

const TARGETS = [
  "data/raw/世界观/全局世界观/先天型共鸣者.editor.json",
  "data/raw/世界观/地区信息/罗伊冰原/海维夏.editor.json",
  "data/raw/世界观/地区信息/罗伊冰原/炉芯.editor.json",
  "data/raw/世界观/地区信息/罗伊冰原/炉芯机骸.editor.json",
  "data/raw/世界观/地区信息/罗伊冰原/隧者.editor.json",
  "data/raw/主线/34-第三章-驶向尚未点亮之星-间章-日光落处/全文.editor.json",
  "data/raw/角色/I.R.I.S/占位.editor.json",
  "data/raw/角色/爱弥斯/特殊文本/1.来自准时宝的加急邮件.editor.json",
  "data/raw/角色/爱弥斯/特殊文本/2.来自I.R.I.S.的邮件.editor.json",
  "data/raw/角色/爱弥斯/特殊文本/3.来自不明账号的邮件.editor.json",
];

function newId() {
  return crypto.randomBytes(4).toString("hex");
}

function stripBom(text) {
  return String(text || "").replace(/^\uFEFF/, "");
}

function defaultDocument(relativePath) {
  const name = path.basename(relativePath);
  const title = name.endsWith(".editor.json")
    ? name.slice(0, -".editor.json".length)
    : name.replace(/\.[^.]+$/, "");
  return { version: 3, path: relativePath.replace(/\\/g, "/"), title, blocks: [] };
}

function parseLineText(line) {
  const idx = line.includes("：") ? line.indexOf("：") : line.indexOf(":");
  if (idx < 0) return null;
  const speaker = line.slice(0, idx).trim();
  const text = line.slice(idx + 1).trim();
  if (!speaker || !text) return null;
  return [speaker, text];
}

function textBlock(type, text, extra = {}) {
  return { id: newId(), type, text, annotation_refs: [], annotation_omissions: [], ...extra };
}

function legacyTextToBlocks(text) {
  const blocks = [];
  for (const rawLine of stripBom(text).split(/\r?\n/)) {
    const stripped = rawLine.trim();
    if (!stripped) continue;
    const parsed = parseLineText(stripped);
    if (parsed) {
      const [speaker, content] = parsed;
      blocks.push({ id: newId(), type: "line", speaker, text: content, annotation_refs: [], annotation_omissions: [] });
      continue;
    }
    if (stripped.startsWith(ANALYSIS_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("analysis", stripped.slice(ANALYSIS_PREFIX.length, -1).trim()));
      continue;
    }
    if (stripped.startsWith(LEGACY_SUPPLEMENT_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("analysis", stripped.slice(LEGACY_SUPPLEMENT_PREFIX.length, -1).trim()));
      continue;
    }
    if (stripped.startsWith(BODY_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("body", stripped.slice(BODY_PREFIX.length, -1).trim()));
      continue;
    }
    if (stripped.startsWith(NARRATION_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("narration", stripped.slice(NARRATION_PREFIX.length, -1).trim(), { italic: false }));
      continue;
    }
    if (stripped.startsWith(LEGACY_NARRATION_SMALL_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("narration", stripped.slice(LEGACY_NARRATION_SMALL_PREFIX.length, -1).trim(), { italic: false }));
      continue;
    }
    if (stripped.startsWith(BLOCK_TITLE_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("heading", stripped.slice(BLOCK_TITLE_PREFIX.length, -1).trim(), { italic: false }));
      continue;
    }
    if (stripped.startsWith(SUMMARY_PREFIX) && stripped.endsWith("】")) {
      blocks.push(textBlock("summary", stripped.slice(SUMMARY_PREFIX.length, -1).trim()));
      continue;
    }
    if (stripped.startsWith("【") && stripped.endsWith("】")) {
      blocks.push(textBlock("heading", stripped.slice(1, -1).trim(), { italic: false }));
      continue;
    }
    blocks.push(textBlock("heading", stripped, { italic: false }));
  }
  return blocks;
}

function parseTxtToDocument(relativePath, content) {
  const document = defaultDocument(relativePath);
  const lines = stripBom(content).replace(/\r\n/g, "\n").split("\n");
  let index = 0;
  while (index < lines.length) {
    const stripped = lines[index].trim();
    if (!stripped) {
      index += 1;
      continue;
    }
    if (stripped === OPTION_START) {
      const branch = { id: newId(), type: "branch", option_speaker: DEFAULT_OPTION_SPEAKER, options: [] };
      index += 1;
      let currentOption = null;
      let responseLines = [];
      while (index < lines.length) {
        const marker = lines[index].trim();
        if (marker === OPTION_NEXT || marker === OPTION_END) {
          if (currentOption) {
            currentOption.response_blocks = legacyTextToBlocks(responseLines.join("\n").trim());
            branch.options.push(currentOption);
          }
          currentOption = null;
          responseLines = [];
          index += 1;
          if (marker === OPTION_END) break;
          continue;
        }
        if (!currentOption) {
          const parsed = parseLineText(marker);
          if (parsed) {
            const [speaker, label] = parsed;
            branch.option_speaker = speaker;
            currentOption = { id: newId(), label, annotation_refs: [], annotation_omissions: [], response_blocks: [] };
          } else {
            currentOption = { id: newId(), label: marker, annotation_refs: [], annotation_omissions: [], response_blocks: [] };
          }
        } else {
          responseLines.push(lines[index].replace(/\s+$/, ""));
        }
        index += 1;
      }
      document.blocks.push(branch);
      continue;
    }
    if (stripped.startsWith(TITLE_PREFIX) && stripped.endsWith("】")) {
      document.title = stripped.slice(TITLE_PREFIX.length, -1).trim();
    } else if (stripped.startsWith(LEGACY_SCENE_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("scene_cast", stripped.slice(LEGACY_SCENE_PREFIX.length, -1).trim()));
    } else if (stripped.startsWith(SCENE_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("scene_cast", stripped.slice(SCENE_PREFIX.length, -1).trim()));
    } else if (stripped.startsWith(SUMMARY_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("summary", stripped.slice(SUMMARY_PREFIX.length, -1).trim()));
    } else if (stripped.startsWith(BODY_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("body", stripped.slice(BODY_PREFIX.length, -1).trim()));
    } else if (stripped.startsWith(NARRATION_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("narration", stripped.slice(NARRATION_PREFIX.length, -1).trim(), { italic: false }));
    } else if (stripped.startsWith(LEGACY_NARRATION_SMALL_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("narration", stripped.slice(LEGACY_NARRATION_SMALL_PREFIX.length, -1).trim(), { italic: false }));
    } else if (stripped.startsWith(ANALYSIS_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("analysis", stripped.slice(ANALYSIS_PREFIX.length, -1).trim()));
    } else if (stripped.startsWith(LEGACY_SUPPLEMENT_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("analysis", stripped.slice(LEGACY_SUPPLEMENT_PREFIX.length, -1).trim()));
    } else if (stripped.startsWith(BLOCK_TITLE_PREFIX) && stripped.endsWith("】")) {
      document.blocks.push(textBlock("heading", stripped.slice(BLOCK_TITLE_PREFIX.length, -1).trim(), { italic: false }));
    } else if (stripped.startsWith("【") && stripped.endsWith("】")) {
      document.blocks.push(textBlock("heading", stripped.slice(1, -1).trim(), { italic: false }));
    } else {
      const parsed = parseLineText(stripped);
      if (parsed) {
        const [speaker, text] = parsed;
        document.blocks.push({ id: newId(), type: "line", speaker, text, annotation_refs: [], annotation_omissions: [] });
      } else {
        document.blocks.push(textBlock("heading", stripped, { italic: false }));
      }
    }
    index += 1;
  }
  return document;
}

let restored = 0;
for (const relativeEditorJson of TARGETS) {
  const editorPath = path.join(ROOT, relativeEditorJson);
  const txtPath = editorPath.replace(/\.editor\.json$/i, ".txt");
  if (!fs.existsSync(txtPath)) continue;
  const relativeTxt = path.relative(path.join(ROOT, "data/raw"), txtPath).replace(/\\/g, "/");
  const txt = fs.readFileSync(txtPath, "utf8");
  const document = parseTxtToDocument(relativeTxt, txt);
  document.path = relativeEditorJson.replace(/^data\/raw\//, "");
  fs.writeFileSync(editorPath, JSON.stringify(document, null, 2), "utf8");
  restored += 1;
}

console.log(`restored=${restored}`);
