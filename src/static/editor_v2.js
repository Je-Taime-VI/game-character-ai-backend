const state = {
  path: "",
  document: null,
  compiledText: "",
  annotationLibrary: [],
  worldTargets: [],
  selectedPath: null,
  editingPath: null,
  selectedAnnotation: null,
  activeSelection: { path: null, text: "" },
  branchSelection: {},
  pendingCreateAnnotationPath: null,
  pendingScrollPath: null,
  savedSnapshot: "",
};

const BLOCK_TYPES = [
  ["scene_cast", "时间&地点&人物"],
  ["narration", "旁白"],
  ["line", "台词"],
  ["branch", "分支选项"],
  ["chapter_summary", "本章梗概"],
  ["paragraph_summary", "段落梗概"],
  ["text_title", "文本标题"],
  ["text_body", "文本正文"],
  ["chapter_note", "本章注释"],
  ["note", "注释"],
];

const TEXT_BLOCK_TYPES = new Set(["scene_cast", "narration", "line", "summary", "chapter_summary", "paragraph_summary", "text_title", "text_body", "analysis", "chapter_note", "note"]);
const ITALIC_TYPES = new Set(["narration", "text_title", "text_body", "analysis", "chapter_note", "note"]);
const NON_DIALOGUE_SPEECH_MODE = "non_dialogue";

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function clonePath(path) {
  return Array.isArray(path) ? path.slice() : null;
}

function pathKey(path) {
  return JSON.stringify(path || []);
}

function pathEquals(a, b) {
  return pathKey(a) === pathKey(b);
}

function setStatus(message) {
  document.getElementById("status").textContent = message;
}

function documentSnapshot() {
  if (!state.document) return "";
  return JSON.stringify({
    path: state.path,
    title: document.getElementById("docTitle")?.value ?? state.document.title ?? "",
    document: state.document,
  });
}

function refreshSavedSnapshot() {
  state.savedSnapshot = documentSnapshot();
}

function hasUnsavedChanges() {
  return Boolean(state.document) && documentSnapshot() !== state.savedSnapshot;
}

function pathParam() {
  return new URLSearchParams(location.search).get("path") || "";
}

function modal(id, open) {
  document.getElementById(id).classList.toggle("open", open);
}

function typeLabel(type) {
  return BLOCK_TYPES.find(([key]) => key === type)?.[1] || type;
}

function emptyAnnotations() {
  return { manual_refs: [], omissions: [], settings: [] };
}

function defaultStyle() {
  return { italic: false, speech_mode: "" };
}

function normalizeClientStyle(value) {
  const style = value && typeof value === "object" ? value : {};
  const italic = Boolean(style.italic);
  return {
    italic,
    speech_mode: italic ? NON_DIALOGUE_SPEECH_MODE : "",
  };
}

function ensureAnnotations(node) {
  if (!node.annotations || typeof node.annotations !== "object") {
    node.annotations = emptyAnnotations();
  }
  if (!Array.isArray(node.annotations.manual_refs)) node.annotations.manual_refs = [];
  if (!Array.isArray(node.annotations.omissions)) node.annotations.omissions = [];
  if (!Array.isArray(node.annotations.settings)) node.annotations.settings = [];
}

function newId(prefix = "cli") {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function createBlock(type) {
  if (type === "line") {
    return { id: newId("blk"), type, speaker: "", text: "", annotations: emptyAnnotations(), style: defaultStyle() };
  }
  if (type === "branch") {
    return { id: newId("blk"), type, speaker: "漂泊者", options: [createOption()] };
  }
  return { id: newId("blk"), type, text: "", annotations: emptyAnnotations(), style: defaultStyle() };
}

function createOption() {
  return { id: newId("opt"), label: "", annotations: emptyAnnotations(), children: [] };
}

function getRef(path) {
  if (!Array.isArray(path) || !state.document) return null;
  let list = state.document.blocks;
  let node = null;
  let parent = state.document;
  let kind = "block";
  for (let i = 0; i < path.length; i += 1) {
    const step = path[i];
    if (typeof step === "number") {
      node = list?.[step];
      if (!node) return null;
      parent = list;
      kind = "block";
      if (i === path.length - 1) return { node, list, index: step, kind, parent };
      continue;
    }
    if (step === "options") {
      const optionIndex = path[i + 1];
      const option = node?.options?.[optionIndex];
      if (!option) return null;
      if (i + 1 === path.length - 1) {
        return { node: option, list: node.options, index: optionIndex, kind: "option", parent: node };
      }
      if (path[i + 2] === "children") {
        list = option.children;
        node = option;
        i += 2;
        continue;
      }
      return null;
    }
    return null;
  }
  return null;
}

function getSelectedRef() {
  return getRef(state.selectedPath);
}

function getSelectedTextNode() {
  const ref = getSelectedRef();
  if (!ref) return null;
  if (ref.kind === "option") {
    ensureAnnotations(ref.node);
    return {
      getText: () => ref.node.label || "",
      setText: value => { ref.node.label = value; },
      getAnnotations: () => ref.node.annotations,
      setAnnotations: value => { ref.node.annotations = value; },
      type: "option",
    };
  }
  if (TEXT_BLOCK_TYPES.has(ref.node.type)) {
    ensureAnnotations(ref.node);
    return {
      getText: () => ref.node.text || "",
      setText: value => { ref.node.text = value; },
      getAnnotations: () => ref.node.annotations,
      setAnnotations: value => { ref.node.annotations = value; },
      type: ref.node.type,
    };
  }
  return null;
}

function getTargetListForAppend() {
  const ref = getSelectedRef();
  if (!ref) return { list: state.document.blocks, index: state.document.blocks.length - 1 };
  if (ref.kind === "option") return { list: ref.node.children, index: ref.node.children.length - 1 };
  return { list: ref.list, index: ref.index };
}

function nearestOptionMarker(path) {
  return Array.isArray(path) ? path.lastIndexOf("options") : -1;
}

function selectPath(path, { scroll = false } = {}) {
  state.selectedPath = clonePath(path);
  state.editingPath = null;
  if (scroll) {
    state.pendingScrollPath = clonePath(path);
  }
  if (Array.isArray(path)) {
    const optionMarker = nearestOptionMarker(path);
    if (optionMarker > 0) {
      const branchRef = getRef(path.slice(0, optionMarker));
      const optionRef = getRef(path.slice(0, optionMarker + 2));
      if (branchRef?.node?.id && optionRef?.node?.id) {
        state.branchSelection[branchRef.node.id] = optionRef.node.id;
      }
    }
  }
  if (state.selectedAnnotation && !pathEquals(state.selectedAnnotation.path, path)) {
    state.selectedAnnotation = null;
  }
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
}

function selectAnnotationHit(path, term, start, end) {
  state.selectedPath = clonePath(path);
  state.editingPath = null;
  state.selectedAnnotation = { path: clonePath(path), term, start, end };
  if (Array.isArray(path)) {
    const optionMarker = nearestOptionMarker(path);
    if (optionMarker > 0) {
      const branchRef = getRef(path.slice(0, optionMarker));
      const optionRef = getRef(path.slice(0, optionMarker + 2));
      if (branchRef?.node?.id && optionRef?.node?.id) {
        state.branchSelection[branchRef.node.id] = optionRef.node.id;
      }
    }
  }
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
}

function beginEdit(path) {
  state.selectedPath = clonePath(path);
  state.editingPath = clonePath(path);
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
}

function endEdit({ keepSelection = true } = {}) {
  state.editingPath = null;
  if (!keepSelection) {
    state.selectedPath = null;
    state.selectedAnnotation = null;
  }
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
}

function isEditingPath(path) {
  return pathEquals(state.editingPath, path);
}

function autoResizeTextarea(area) {
  if (!area) return;
  area.style.height = "auto";
  area.style.height = `${area.scrollHeight}px`;
}

function markNodePath(el, path) {
  if (!el) return;
  el.dataset.pathKey = pathKey(path);
}

function flushPendingScroll() {
  if (!state.pendingScrollPath) return;
  const key = pathKey(state.pendingScrollPath);
  state.pendingScrollPath = null;
  requestAnimationFrame(() => {
    const target = document.querySelector(`[data-path-key='${CSS.escape(key)}']`);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });
}

function normalizeAnnotationsForText(text, annotations) {
  const next = annotations && typeof annotations === "object" ? { ...annotations } : emptyAnnotations();
  const value = String(text || "");
  next.manual_refs = Array.isArray(next.manual_refs) ? Array.from(new Set(next.manual_refs.map(item => String(item || "").trim()).filter(Boolean))) : [];
  next.omissions = Array.isArray(next.omissions)
    ? next.omissions.filter(item => {
        if (!item || typeof item !== "object") return false;
        const term = String(item.term || "").trim();
        const start = Number(item.start);
        const end = Number(item.end);
        if (!term || !Number.isInteger(start) || !Number.isInteger(end)) return false;
        if (start < 0 || end <= start || end > value.length) return false;
        return value.slice(start, end) === term;
      })
    : [];
  next.settings = Array.isArray(next.settings)
    ? next.settings.filter(item => {
        if (!item || typeof item !== "object") return false;
        const term = String(item.term || "").trim();
        const start = Number(item.start);
        const end = Number(item.end);
        if (!term || !Number.isInteger(start) || !Number.isInteger(end)) return false;
        if (start < 0 || end <= start || end > value.length) return false;
        return value.slice(start, end) === term;
      })
    : [];
  return next;
}

function syncTextAnnotations(target, text) {
  if (!target) return;
  target.setAnnotations(normalizeAnnotationsForText(text, target.getAnnotations()));
}

function bindInlineEditorInteractions(el) {
  ["click", "mousedown", "dblclick"].forEach(name => {
    el.addEventListener(name, event => {
      event.stopPropagation();
    });
  });
}

function openAnnotationModal(entry, dataset = {}) {
  const term = entry?.term || dataset.term || "";
  if (!term) return;
  document.getElementById("annotationTitle").textContent = term;
  document.getElementById("annotationSource").textContent = entry?.source_path || "";
  document.getElementById("annotationBody").textContent = entry?.definition || "暂无设定正文";
  modal("annotationModal", true);
}

function openSummaryModal(node, path) {
  const body = document.getElementById("summaryBody");
  body.innerHTML = annotateHtml(node.text || "", node.annotations, path) || "暂无梗概";
  bindAnnotationTerms(body, path, node.annotations);
  modal("summaryModal", true);
}
function collectAnnotationEntries() {
  const dedup = new Map();
  for (const item of state.annotationLibrary || []) {
    const term = String(item.term || "").trim();
    if (!term || dedup.has(term)) continue;
    dedup.set(term, item);
  }
  return Array.from(dedup.values()).sort((a, b) => b.term.length - a.term.length || a.term.localeCompare(b.term, "zh-CN"));
}

function findAnnotationEntry(term) {
  return collectAnnotationEntries().find(item => item.term === String(term || "").trim()) || null;
}

function detectSpans(text, annotations, path) {
  const value = String(text || "");
  if (!value) return [];
  const selfTerm = getSelfTermFromPath(state.path);
  const omissions = (annotations?.omissions || []).map(item => `${item.term}@@${item.start}@@${item.end}`);
  const occupied = new Array(value.length).fill(false);
  const spans = [];
  for (const entry of collectAnnotationEntries()) {
    const term = String(entry.term || "").trim();
    if (!term || (selfTerm && term === selfTerm)) continue;
    let start = value.indexOf(term);
    while (start !== -1) {
      const end = start + term.length;
      const key = `${term}@@${start}@@${end}`;
      if (!omissions.includes(key) && !occupied.slice(start, end).some(Boolean)) {
        spans.push({ term, start, end, kind: "setting" });
        for (let i = start; i < end; i += 1) occupied[i] = true;
      }
      start = value.indexOf(term, start + 1);
    }
  }
  for (const term of annotations?.manual_refs || []) {
    const entry = findAnnotationEntry(term);
    if (!entry) continue;
    let start = value.indexOf(entry.term);
    while (start !== -1) {
      const end = start + entry.term.length;
      const key = `${entry.term}@@${start}@@${end}`;
      if (!spans.some(item => item.term === entry.term && item.start === start && item.end === end) && !omissions.includes(key)) {
        spans.push({ term: entry.term, start, end, kind: "setting" });
      }
      start = value.indexOf(entry.term, start + 1);
    }
  }
  spans.sort((a, b) => a.start - b.start || a.end - b.end);
  return spans;
}

function annotateHtml(text, annotations, path) {
  const value = String(text || "");
  const spans = detectSpans(value, annotations, path);
  if (!spans.length) return esc(value).replaceAll("\n", "<br>");
  let cursor = 0;
  let html = "";
  for (const span of spans) {
    if (span.start > cursor) html += esc(value.slice(cursor, span.start)).replaceAll("\n", "<br>");
    html += `<span class="annotation-term" data-term="${esc(span.term)}" data-start="${span.start}" data-end="${span.end}">${esc(value.slice(span.start, span.end))}</span>`;
    cursor = span.end;
  }
  if (cursor < value.length) html += esc(value.slice(cursor)).replaceAll("\n", "<br>");
  return html;
}

function bindAnnotationTerms(container, path, annotations) {
  container.querySelectorAll(".annotation-term").forEach(el => {
    el.addEventListener("click", event => {
      event.stopPropagation();
      const term = el.dataset.term || "";
      const start = Number(el.dataset.start);
      const end = Number(el.dataset.end);
      selectAnnotationHit(path, term, start, end);
      openAnnotationModal(findAnnotationEntry(term), el.dataset);
    });
  });
}

function captureSelection(el, path) {
  const update = () => {
    const value = String(el.value || "");
    const start = typeof el.selectionStart === "number" ? el.selectionStart : 0;
    const end = typeof el.selectionEnd === "number" ? el.selectionEnd : 0;
    state.activeSelection = {
      path: clonePath(path),
      text: end > start ? value.slice(start, end).trim() : "",
    };
  };
  ["focus", "keyup", "mouseup", "select"].forEach(name => el.addEventListener(name, update));
}

function renderTextBlock(node, path, className, placeholder) {
  const wrapper = document.createElement("div");
  wrapper.className = `preview-node ${className}${pathEquals(state.selectedPath, path) ? " selected" : ""}`;
  markNodePath(wrapper, path);
  wrapper.addEventListener("click", () => selectPath(path));
  wrapper.addEventListener("dblclick", event => {
    event.stopPropagation();
    beginEdit(path);
  });
  if (node.style?.italic) { wrapper.style.fontStyle = "italic"; }
  if (isEditingPath(path)) {
    const textTarget = getSelectedTextNode();
    const editor = document.createElement("div");
    editor.className = "inline-editor";
    const area = document.createElement("textarea");
    area.className = `inline-textarea ${className}`;
    area.rows = 1;
    area.value = node.text || "";
    bindInlineEditorInteractions(area);
    area.placeholder = placeholder;
    bindInlineEditorInteractions(editor);
    bindInlineEditorInteractions(area);
    area.addEventListener("input", event => {
      node.text = event.target.value;
      syncTextAnnotations(textTarget, node.text);
      autoResizeTextarea(area);
      renderSelectionTools();
      document.getElementById("previewTitle").textContent = state.document.title || "";
    });
    captureSelection(area, path);
    editor.appendChild(area);
    wrapper.appendChild(editor);
    setTimeout(() => {
      area.focus();
      autoResizeTextarea(area);
    }, 0);
  } else {
    wrapper.innerHTML = annotateHtml(node.text || "", node.annotations, path) || esc(placeholder);
    bindAnnotationTerms(wrapper, path, node.annotations);
  }
  return wrapper;
}

function renderLineBlock(node, path) {
  const wrapper = document.createElement("div");
  wrapper.className = `preview-node ${pathEquals(state.selectedPath, path) ? "selected" : ""}`;
  markNodePath(wrapper, path);
  wrapper.addEventListener("click", () => selectPath(path));
  wrapper.addEventListener("dblclick", event => {
    event.stopPropagation();
    beginEdit(path);
  });
  if (node.style?.italic) { wrapper.style.fontStyle = "italic"; }
  if (isEditingPath(path)) {
    const textTarget = getSelectedTextNode();
    const row = document.createElement("div");
    row.className = "line-row";
    bindInlineEditorInteractions(row);
    const speaker = document.createElement("input");
    speaker.className = "inline-line-speaker";
    speaker.value = node.speaker || "";
    speaker.placeholder = "发言者";
    bindInlineEditorInteractions(speaker);
    speaker.addEventListener("input", event => { node.speaker = event.target.value; renderSelectionTools(); });
    const area = document.createElement("textarea");
    area.className = "inline-textarea line-content-editor";
    area.rows = 1;
    area.value = node.text || "";
    area.placeholder = "输入台词";
    bindInlineEditorInteractions(area);
    area.addEventListener("input", event => {
      node.text = event.target.value;
      syncTextAnnotations(textTarget, node.text);
      autoResizeTextarea(area);
      renderSelectionTools();
    });
    captureSelection(area, path);
    row.appendChild(speaker);
    row.appendChild(area);
    wrapper.appendChild(row);
    setTimeout(() => {
      area.focus();
      autoResizeTextarea(area);
    }, 0);
  } else {
    wrapper.innerHTML = `<div class="line-block"><div class="line-speaker">${esc(node.speaker || "角色")}：</div><div class="line-content">${annotateHtml(node.text || "", node.annotations, path) || "输入台词"}</div></div>`;
    bindAnnotationTerms(wrapper, path, node.annotations);
  }
  return wrapper;
}

function summaryLabel(node) {
  if (node.type === "chapter_summary") return "本章梗概";
  if (node.type === "paragraph_summary") return "段落梗概";
  return "段落梗概";
}

function renderSummaryBlock(node, path) {
  const wrapper = document.createElement("div");
  wrapper.className = `preview-node summary-block${pathEquals(state.selectedPath, path) ? " selected" : ""}`;
  markNodePath(wrapper, path);
  wrapper.addEventListener("click", () => selectPath(path));
  wrapper.addEventListener("dblclick", event => {
    event.stopPropagation();
    beginEdit(path);
  });
  if (node.style?.italic) { wrapper.style.fontStyle = "italic"; }
  if (isEditingPath(path)) {
    const textTarget = getSelectedTextNode();
    const editor = document.createElement("div");
    editor.className = "inline-editor";
    bindInlineEditorInteractions(editor);
    const area = document.createElement("textarea");
    area.className = "inline-textarea summary-block";
    area.rows = 1;
    bindInlineEditorInteractions(area);
    area.value = node.text || "";
    area.placeholder = `输入${summaryLabel(node)}`;
    area.addEventListener("input", event => {
      node.text = event.target.value;
      syncTextAnnotations(textTarget, node.text);
      autoResizeTextarea(area);
      renderSelectionTools();
    });
    captureSelection(area, path);
    editor.appendChild(area);
    wrapper.appendChild(editor);
    setTimeout(() => {
      area.focus();
      autoResizeTextarea(area);
    }, 0);
  } else {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "summary-button";
    button.textContent = summaryLabel(node);
    button.addEventListener("click", event => {
      event.stopPropagation();
      selectPath(path);
      openSummaryModal(node, path);
    });
    wrapper.appendChild(button);
  }
  return wrapper;
}
function selectedOptionIndex(branch) {
  const branchId = branch.id;
  const selectedId = state.branchSelection[branchId] || branch.options?.[0]?.id;
  const index = Math.max(0, branch.options.findIndex(item => item.id === selectedId));
  state.branchSelection[branchId] = branch.options[index]?.id;
  return index;
}

function renderOptionLabel(option, path, active) {
  const node = document.createElement("div");
  node.className = `option-chip${active ? " active" : ""}`;
  markNodePath(node, path);
  node.addEventListener("click", event => {
    event.stopPropagation();
    const branchPath = path.slice(0, nearestOptionMarker(path));
    const branchRef = getRef(branchPath);
    if (branchRef?.node?.id) {
      state.branchSelection[branchRef.node.id] = option.id;
    }
    selectPath(path);
  });
  node.addEventListener("dblclick", event => {
    event.stopPropagation();
    const branchPath = path.slice(0, nearestOptionMarker(path));
    const branchRef = getRef(branchPath);
    if (branchRef?.node?.id) {
      state.branchSelection[branchRef.node.id] = option.id;
    }
    beginEdit(path);
  });
  if (isEditingPath(path)) {
    const area = document.createElement("textarea");
    area.className = "inline-textarea option-chip-editor";
    area.rows = 1;
    bindInlineEditorInteractions(area);
    area.value = option.label || "";
    area.placeholder = "\u9009\u9879\u6587\u672C";
    area.addEventListener("input", event => {
      option.label = event.target.value;
      syncTextAnnotations(getSelectedTextNode(), option.label);
      autoResizeTextarea(area);
      renderSelectionTools();
    });
    captureSelection(area, path);
    node.appendChild(area);
    setTimeout(() => {
      area.focus();
      autoResizeTextarea(area);
    }, 0);
  } else {
    node.innerHTML = annotateHtml(option.label || "", option.annotations, path) || "\u9009\u9879\u6587\u672C";
    bindAnnotationTerms(node, path, option.annotations);
  }
  return node;
}

function renderBranchBlock(node, path) {
  const wrapper = document.createElement("div");
  wrapper.className = "branch-block";
  const shell = document.createElement("div");
  shell.className = `preview-node branch-shell${pathEquals(state.selectedPath, path) ? " selected" : ""}`;
  markNodePath(shell, path);
  shell.addEventListener("click", () => selectPath(path));
  shell.addEventListener("dblclick", event => {
    event.stopPropagation();
    beginEdit(path);
  });
  const speakerLine = document.createElement("div");
  speakerLine.className = "line-block branch-speaker-row";
  const speakerLabel = document.createElement("div");
  speakerLabel.className = "line-speaker";
  if (node.style?.italic) { shell.style.fontStyle = "italic"; }
  if (isEditingPath(path)) {
    const input = document.createElement("input");
    bindInlineEditorInteractions(input);
    input.value = node.speaker || "\u6F02\u6CCA\u8005";
    input.placeholder = "\u5206\u652F\u53D1\u8A00\u4E3B\u4F53";
    input.addEventListener("input", event => { node.speaker = event.target.value; });
    speakerLabel.appendChild(input);
  } else {
    speakerLabel.textContent = `${node.speaker || "\u6F02\u6CCA\u8005"}\uFF1A`;
  }
  speakerLine.appendChild(speakerLabel);
  const speakerSpacer = document.createElement("div");
  speakerSpacer.className = "branch-speaker-spacer";
  speakerLine.appendChild(speakerSpacer);
  shell.appendChild(speakerLine);
  const panel = document.createElement("div");
  panel.className = "branch-panel";
  const list = document.createElement("div");
  list.className = "option-list";
  const activeIndex = selectedOptionIndex(node);
  node.options.forEach((option, index) => {
    const optionPath = path.concat(["options", index]);
    list.appendChild(renderOptionLabel(option, optionPath, index === activeIndex));
  });
  panel.appendChild(list);
  shell.appendChild(panel);
  wrapper.appendChild(shell);
  const childrenRoot = document.createElement("div");
  childrenRoot.className = "option-children branch-children";
  childrenRoot.addEventListener("click", event => event.stopPropagation());
  childrenRoot.addEventListener("dblclick", event => event.stopPropagation());
  const activeOption = node.options[activeIndex];
  (activeOption?.children || []).forEach((child, index) => {
    childrenRoot.appendChild(renderBlock(child, path.concat(["options", activeIndex, "children", index])));
  });
  wrapper.appendChild(childrenRoot);
  return wrapper;
}

function renderBlock(node, path) {
  if (node.type === "scene_cast") return renderTextBlock(node, path, "scene-block", "输入时间&地点&人物");
  if (node.type === "text_title") return renderTextBlock(node, path, "text-title-block", "输入文本标题");
  if (node.type === "narration") return renderTextBlock(node, path, "narration-block", "输入旁白");
  if (node.type === "text_body") return renderTextBlock(node, path, "text-body-block", "输入文本正文");
  if (node.type === "analysis") return renderTextBlock(node, path, "analysis-block", "输入注释");
  if (node.type === "chapter_note") return renderTextBlock(node, path, "analysis-block", "输入本章注释");
  if (node.type === "note") return renderTextBlock(node, path, "analysis-block", "输入注释");
  if (node.type === "summary" || node.type === "chapter_summary" || node.type === "paragraph_summary") return renderSummaryBlock(node, path);
  if (node.type === "line") return renderLineBlock(node, path);
  if (node.type === "branch") return renderBranchBlock(node, path);
  return renderTextBlock(node, path, "narration-block", "输入内容");
}

function renderPreview() {
  document.getElementById("previewTitle").textContent = state.document?.title || "";
  const root = document.getElementById("previewRoot");
  root.innerHTML = "";
  (state.document?.blocks || []).forEach((block, index) => {
    root.appendChild(renderBlock(block, [index]));
  });
  flushPendingScroll();
}

function renderSelectedSummary() {
  const node = document.getElementById("selectedSummary");
  const ref = getSelectedRef();
  if (!ref) {
    node.textContent = "请在中间预览区点击一个块。";
    return;
  }
  if (ref.kind === "option") {
    node.textContent = `分支选项 · 位置 ${ref.index + 1}`;
    return;
  }
  node.textContent = `${typeLabel(ref.node.type)} · 位置 ${ref.index + 1}`;
}

function setInsertButtons(container, onClick) {
  container.innerHTML = "";
  BLOCK_TYPES.forEach(([type, label]) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary";
    button.textContent = label;
    button.addEventListener("click", () => onClick(type));
    container.appendChild(button);
  });
}

function addBlockOfType(type) {
  const item = createBlock(type);
  state.document.blocks.push(item);
  selectPath(findPathOfNode(item.id), { scroll: true });
}

function insertBlockOfType(type) {
  const ref = getSelectedRef();
  const item = createBlock(type);
  if (!ref) {
    state.document.blocks.unshift(item);
    selectPath([0], { scroll: true });
    modal("insertModal", false);
    return;
  }
  if (ref.kind === "option") {
    ref.node.children.unshift(item);
    selectPath(state.selectedPath.concat(["children", 0]), { scroll: true });
    modal("insertModal", false);
    return;
  }
  ref.list.splice(ref.index, 0, item);
  selectPath(findPathOfNode(item.id), { scroll: true });
  modal("insertModal", false);
}

function findPathOfNode(id, blocks = state.document?.blocks || [], prefix = []) {
  for (let index = 0; index < blocks.length; index += 1) {
    const block = blocks[index];
    const blockPath = prefix.concat([index]);
    if (block.id === id) return blockPath;
    if (block.type === "branch") {
      for (let optIndex = 0; optIndex < (block.options || []).length; optIndex += 1) {
        const option = block.options[optIndex];
        const optionPath = blockPath.concat(["options", optIndex]);
        if (option.id === id) return optionPath;
        const childPath = findPathOfNode(id, option.children || [], optionPath.concat(["children"]));
        if (childPath) return childPath;
      }
    }
  }
  return null;
}

function moveSelected(delta) {
  const ref = getSelectedRef();
  if (!ref) return;
  const target = ref.index + delta;
  if (target < 0 || target >= ref.list.length) return;
  const [item] = ref.list.splice(ref.index, 1);
  ref.list.splice(target, 0, item);
  selectPath(findPathOfNode(item.id));
}

function deleteSelected() {
  const ref = getSelectedRef();
  if (!ref) return;
  ref.list.splice(ref.index, 1);
  state.selectedPath = null;
  state.selectedAnnotation = null;
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
}

function addBranchOption() {
  const ref = getSelectedRef();
  if (!ref) return;
  const branch = ref.kind === "option" ? ref.parent : ref.node.type === "branch" ? ref.node : null;
  if (!branch) return;
  const option = createOption();
  branch.options.push(option);
  state.branchSelection[branch.id] = option.id;
  selectPath(findPathOfNode(option.id), { scroll: true });
}

function addChildBlock(type) {
  const ref = getSelectedRef();
  if (!ref || ref.kind !== "option") return;
  const block = createBlock(type);
  ref.node.children.push(block);
  selectPath(findPathOfNode(block.id), { scroll: true });
}

function getSelfTermFromPath(path) {
  const normalized = String(path || "").replaceAll("\\", "/");
  if (!normalized.startsWith("世界观/")) return "";
  const parts = normalized.split("/");
  const fileName = parts[parts.length - 1] || "";
  if (fileName.endsWith(".editor.json")) return fileName.slice(0, -12);
  if (fileName.endsWith(".txt")) return fileName.slice(0, -4);
  return "";
}

function removeSelectedAnnotationHit() {
  const selectedText = getSelectedTextNode();
  if (!selectedText || !state.selectedAnnotation || !pathEquals(state.selectedAnnotation.path, state.selectedPath)) return;
  const annotations = selectedText.getAnnotations();
  const omissions = Array.isArray(annotations.omissions) ? annotations.omissions.slice() : [];
  omissions.push({ term: state.selectedAnnotation.term, start: state.selectedAnnotation.start, end: state.selectedAnnotation.end });
  selectedText.setAnnotations({ ...annotations, omissions });
  state.selectedAnnotation = null;
  renderPreview();
  renderSelectionTools();
}

function toggleItalic() {
  const ref = getSelectedRef();
  if (!ref || ref.kind !== "block" || !ITALIC_TYPES.has(ref.node.type)) return;
  ref.node.style = normalizeClientStyle(ref.node.style);
  ref.node.style.italic = !ref.node.style.italic;
  ref.node.style.speech_mode = ref.node.style.italic ? NON_DIALOGUE_SPEECH_MODE : "";
  renderPreview();
  renderSelectionTools();
}

function addManualAnnotationRef(term) {
  const selectedText = getSelectedTextNode();
  const entry = findAnnotationEntry(term);
  if (!selectedText || !entry) return false;
  const annotations = selectedText.getAnnotations();
  const refs = Array.isArray(annotations.manual_refs) ? annotations.manual_refs.slice() : [];
  if (!refs.includes(entry.term)) refs.push(entry.term);
  selectedText.setAnnotations({ ...annotations, manual_refs: refs });
  renderPreview();
  renderSelectionTools();
  setStatus(`已引用设定：${entry.term}`);
  return true;
}

function removeManualAnnotationRef(term) {
  const selectedText = getSelectedTextNode();
  if (!selectedText) return;
  const annotations = selectedText.getAnnotations();
  selectedText.setAnnotations({
    ...annotations,
    manual_refs: (annotations.manual_refs || []).filter(item => item !== term),
  });
  renderPreview();
  renderSelectionTools();
}


function renderSelectionTools() {
  const container = document.getElementById("selectionTools");
  const ref = getSelectedRef();
  if (!ref) {
    container.className = "tools-empty muted";
    container.textContent = "选择块后，这里会出现倾斜、分支、设定等操作。";
    return;
  }
  container.className = "";
  container.innerHTML = "";

  const title = document.createElement("div");
  title.className = "helper-text";
  title.textContent = ref.kind === "option" ? "当前为分支选项" : `当前块：${typeLabel(ref.node.type)}`;
  container.appendChild(title);

  if (ref.kind === "block" && ITALIC_TYPES.has(ref.node.type)) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "secondary";
    btn.textContent = ref.node.style?.italic ? "取消倾斜" : "字体倾斜";
    btn.textContent = ref.node.style?.italic ? "取消非对话格式发言" : "标为非对话格式发言";
    btn.title = "用于书、信件、转述话语等不是角色现场对话的发言；保存后会在编译文本中标注给 AI。";
    btn.addEventListener("click", toggleItalic);
    container.appendChild(btn);
  }

  if ((ref.kind === "block" && ref.node.type === "branch") || ref.kind === "option") {
    const branchBtn = document.createElement("button");
    branchBtn.type = "button";
    branchBtn.className = "secondary";
    branchBtn.textContent = "为分支选项新增选项";
    branchBtn.addEventListener("click", addBranchOption);
    container.appendChild(branchBtn);
  }

  if (ref.kind === "option") {
    const childWrap = document.createElement("div");
    childWrap.className = "field-list";
    const helper = document.createElement("div");
    helper.className = "helper-text";
    helper.textContent = "为当前分支选项新增新后续块";
    childWrap.appendChild(helper);
    const grid = document.createElement("div");
    grid.className = "button-grid compact";
    ["line", "narration", "text_title", "text_body", "note", "paragraph_summary", "branch"].forEach(type => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "secondary";
      button.textContent = `新增${typeLabel(type)}`;
      button.addEventListener("click", () => addChildBlock(type));
      grid.appendChild(button);
    });
    childWrap.appendChild(grid);
    container.appendChild(childWrap);
  }

  const selectedText = getSelectedTextNode();
  if (selectedText) {
    const annotationPanel = document.createElement("div");
    annotationPanel.className = "field-list";

    const createBtn = document.createElement("button");
    createBtn.type = "button";
    createBtn.className = "secondary small";
    createBtn.textContent = "新建设定";
    createBtn.addEventListener("click", () => openCreateAnnotationModal(state.selectedPath));
    annotationPanel.appendChild(createBtn);

    if (state.selectedAnnotation && pathEquals(state.selectedAnnotation.path, state.selectedPath)) {
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "danger";
      removeBtn.textContent = `取消设定：${state.selectedAnnotation.term}`;
      removeBtn.addEventListener("click", removeSelectedAnnotationHit);
      annotationPanel.appendChild(removeBtn);
    }

    container.appendChild(annotationPanel);
  }
}

function openCreateAnnotationModal(path) {
  state.pendingCreateAnnotationPath = clonePath(path);
  document.getElementById("createAnnotationTerm").value = pathEquals(state.activeSelection.path, path) ? state.activeSelection.text : "";
  document.getElementById("createAnnotationDefinition").value = "";
  const select = document.getElementById("createAnnotationTarget");
  select.innerHTML = "";
  for (const item of state.worldTargets || []) {
    const option = document.createElement("option");
    option.value = item.path;
    option.textContent = item.label;
    select.appendChild(option);
  }
  modal("createAnnotationModal", true);
}

async function submitCreateAnnotation() {
  const targetPath = document.getElementById("createAnnotationTarget").value;
  const term = document.getElementById("createAnnotationTerm").value.trim();
  const definition = document.getElementById("createAnnotationDefinition").value.trim();
  if (!targetPath || !term || !definition) {
    setStatus("请完整填写新建设定信息。");
    return;
  }
  const submit = overwrite => fetch("/editor/world-annotation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_path: targetPath, term, definition, overwrite }),
  });
  let resp = await submit(false);
  if (resp.status === 409) {
    let detail = {};
    try {
      detail = await resp.json();
    } catch {
      detail = {};
    }
    const sourcePath = detail?.detail?.source_path || "";
    const confirmed = window.confirm(sourcePath
      ? `设定库中已存在同名设定“${term}”。\n是否替换现有设定？\n\n现有位置：${sourcePath}`
      : `设定库中已存在同名设定“${term}”。\n是否替换现有设定？`);
    if (!confirmed) {
      setStatus(`已取消替换设定：${term}`);
      return;
    }
    resp = await submit(true);
  }
  if (!resp.ok) {
    setStatus(`新建设定失败：${await resp.text()}`);
    return;
  }
  await loadAnnotationLibrary();
  addManualAnnotationRef(term);
  modal("createAnnotationModal", false);
  setStatus(`已创建设定：${term}`);
}

async function loadAnnotationLibrary() {
  const resp = await fetch("/editor/annotation-library?limit=1000", { cache: "no-store" });
  const payload = await resp.json();
  state.annotationLibrary = payload.items || [];
}

async function loadWorldTargets() {
  const resp = await fetch("/editor/world-targets", { cache: "no-store" });
  const payload = await resp.json();
  state.worldTargets = payload.items || [];
}

async function loadDocument() {
  if (!state.path) {
    setStatus("缺少 path 参数。");
    return;
  }
  const resp = await fetch(`/editor/document?path=${encodeURIComponent(state.path)}`, { cache: "no-store" });
  if (!resp.ok) {
    setStatus(`加载失败：${await resp.text()}`);
    return;
  }
  const payload = await resp.json();
  state.document = payload.document;
  state.compiledText = payload.compiled_text || "";
  document.getElementById("editorPath").textContent = state.path;
  document.getElementById("docTitle").value = state.document.title || "";
  state.selectedPath = state.document.blocks?.length ? [0] : null;
  refreshSavedSnapshot();
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
  setStatus(`已加载 ${state.path}`);
}

async function saveDocument() {
  state.document.title = document.getElementById("docTitle").value.trim();
  const resp = await fetch("/editor/document", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: state.path, document: state.document }),
  });
  if (!resp.ok) {
    setStatus(`保存失败：${await resp.text()}`);
    return;
  }
  const payload = await resp.json();
  const oldPath = state.path;
  state.path = payload.path || state.path;
  state.document = payload.document;
  state.compiledText = payload.compiled_text || "";
  document.getElementById("editorPath").textContent = state.path;
  if (state.path !== oldPath) {
    const url = new URL(window.location.href);
    url.searchParams.set("path", state.path);
    window.history.replaceState(null, "", url.toString());
  }
  refreshSavedSnapshot();
  renderPreview();
  renderSelectionTools();
  renderSelectedSummary();
  setStatus(`已保存并编译：${state.path}`);
}

function bindGlobalActions() {
  document.getElementById("saveBtn").addEventListener("click", saveDocument);
  document.getElementById("showTxtBtn").addEventListener("click", () => {
    document.getElementById("compiledText").textContent = state.compiledText || "";
    modal("txtModal", true);
  });
  document.getElementById("docTitle").addEventListener("input", event => {
    if (state.document) {
      state.document.title = event.target.value;
      document.getElementById("previewTitle").textContent = event.target.value;
    }
  });
  document.getElementById("insertBtn").addEventListener("click", () => modal("insertModal", true));
  document.getElementById("moveUpBtn").addEventListener("click", () => moveSelected(-1));
  document.getElementById("moveDownBtn").addEventListener("click", () => moveSelected(1));
  document.getElementById("deleteBtn").addEventListener("click", deleteSelected);
  document.getElementById("submitCreateAnnotationBtn").addEventListener("click", submitCreateAnnotation);
  document.querySelectorAll("[data-close]").forEach(button => {
    button.addEventListener("click", () => modal(button.dataset.close, false));
  });
  const centerScroll = document.querySelector(".center-scroll");
  if (centerScroll) {
    centerScroll.addEventListener("click", event => {
      if (event.target === centerScroll && state.editingPath) {
        endEdit({ keepSelection: true });
      }
    });
  }
  const previewRoot = document.getElementById("previewRoot");
  if (previewRoot) {
    previewRoot.addEventListener("click", event => {
      if (event.target === previewRoot && state.editingPath) {
        endEdit({ keepSelection: true });
      }
    });
  }
  setInsertButtons(document.getElementById("insertTypeGrid"), insertBlockOfType);
  setInsertButtons(document.getElementById("addBlockGrid"), addBlockOfType);
  window.addEventListener("beforeunload", event => {
    if (!hasUnsavedChanges()) return;
    event.preventDefault();
    event.returnValue = "";
  });
}

async function bootstrap() {
  state.path = pathParam();
  bindGlobalActions();
  await Promise.all([loadAnnotationLibrary(), loadWorldTargets()]);
  await loadDocument();
}

bootstrap().catch(error => {
  console.error(error);
  setStatus(`初始化失败：${error.message || error}`);
});






