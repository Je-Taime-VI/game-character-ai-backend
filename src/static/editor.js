const state = {
  path: "",
  document: { version: 3, path: "", title: "", blocks: [] },
  compiledText: "",
  branchSelection: {},
  selectedPath: null,
  selectedAnnotation: null,
  annotationLibrary: [],
  worldTargets: [],
  activeSelection: { path: null, text: "" },
  pendingAnnotationCreatePath: null
};

const TYPE_LABEL = {
  scene_cast: "\u573a\u666f\uff06\u4eba\u7269",
  line: "\u53f0\u8bcd",
  narration: "\u65c1\u767d\u00b7\u5927",
  narration_small: "\u65c1\u767d\u00b7\u5c0f",
  supplement: "\u65c1\u767d\u00b7\u8865\u5145",
  summary: "\u5267\u60c5\u6897\u6982",
  branch: "\u5206\u652f\u9009\u9879"
};

const BLOCK_TYPE_ALIASES = {
  scene_title: "scene_cast",
  dialogue: "line",
  heading: "narration",
  narration: "narration",
  narration_small: "narration_small",
  body: "narration_small",
  body_text: "narration_small",
  analysis: "supplement",
  supplement: "supplement"
};

const REFERENCEABLE_TYPES = new Set(["scene_cast", "line", "narration", "narration_small", "supplement", "summary"]);
const ADDABLE_BLOCK_TYPES = ["scene_cast", "line", "narration", "narration_small", "supplement", "summary", "branch"];

function normalizeBlockType(type) {
  const value = String(type || "").trim();
  return BLOCK_TYPE_ALIASES[value] || value;
}

function newId() {
  return Math.random().toString(36).slice(2, 10);
}

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setStatus(message) {
  document.getElementById("status").textContent = message;
}

function pathParam() {
  return new URLSearchParams(location.search).get("path") || "";
}

function modal(id, open) {
  document.getElementById(id).classList.toggle("open", open);
}

function normalizeAnnotationRefs(values) {
  const refs = [];
  for (const value of values || []) {
    const term = String(value || "").trim();
    if (term && !refs.includes(term)) refs.push(term);
  }
  return refs;
}

function normalizeAnnotationOmissions(values) {
  const omissions = [];
  const seen = new Set();
  for (const value of values || []) {
    if (!value || typeof value !== "object") continue;
    const term = String(value.term || "").trim();
    const start = Number(value.start);
    const end = Number(value.end);
    if (!term || !Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start) continue;
    const key = `${term}@@${start}@@${end}`;
    if (seen.has(key)) continue;
    seen.add(key);
    omissions.push({ term, start, end });
  }
  return omissions;
}

function normalizeBlocks(blocks) {
  return (blocks || []).map(block => {
    const normalized = { ...block, type: normalizeBlockType(block.type) };
    if (normalized.options) {
      normalized.options = (normalized.options || []).map(option => ({
        ...option,
        response_blocks: normalizeBlocks(option.response_blocks || [])
      }));
    }
    return normalized;
  });
}

function normalizeDocument(document) {
  return {
    ...(document || {}),
    blocks: normalizeBlocks((document || {}).blocks || [])
  };
}

function createBlock(type) {
  if (type === "scene_cast") return { id: newId(), type, text: "", annotation_refs: [], annotation_omissions: [] };
  if (type === "line") return { id: newId(), type, speaker: "", text: "", annotation_refs: [], annotation_omissions: [] };
  if (type === "narration") return { id: newId(), type, text: "", annotation_refs: [], annotation_omissions: [], italic: false };
  if (type === "narration_small") return { id: newId(), type, text: "", annotation_refs: [], annotation_omissions: [], italic: false };
  if (type === "supplement") return { id: newId(), type, text: "", annotation_refs: [], annotation_omissions: [] };
  if (type === "summary") return { id: newId(), type, text: "", annotation_refs: [], annotation_omissions: [] };
  if (type === "branch") {
    return {
      id: newId(),
      type,
      option_speaker: "\u6f02\u6cca\u8005",
      options: [createOption(), createOption()]
    };
  }
  return { id: newId(), type, text: "" };
}

function createOption() {
  return { id: newId(), label: "", annotation_refs: [], annotation_omissions: [], response_blocks: [] };
}

function move(list, index, delta) {
  const target = index + delta;
  if (target < 0 || target >= list.length) return;
  const [item] = list.splice(index, 1);
  list.splice(target, 0, item);
}

function bindInput(el, handler, rerenderEditor = true) {
  el.addEventListener("input", event => {
    handler(event.target.value);
    refreshAnnotationDatalist();
    renderPreview();
    renderSelectedMeta();
    if (rerenderEditor) renderSelectedEditor();
  });
}

function bindSelectionCapture(el, path) {
  const update = () => {
    const value = String(el.value || "");
    const start = typeof el.selectionStart === "number" ? el.selectionStart : 0;
    const end = typeof el.selectionEnd === "number" ? el.selectionEnd : 0;
    const text = end > start ? value.slice(start, end).trim() : "";
    state.activeSelection = { path: clonePath(path), text };
  };
  el.addEventListener("focus", update);
  el.addEventListener("select", update);
  el.addEventListener("keyup", update);
  el.addEventListener("mouseup", update);
}

function clonePath(path) {
  return Array.isArray(path) ? path.slice() : null;
}

function pathEquals(a, b) {
  return JSON.stringify(a || []) === JSON.stringify(b || []);
}

function getRef(path) {
  if (!Array.isArray(path) || !path.length) return null;
  let list = state.document.blocks;
  let block = null;
  let index = null;
  for (let i = 0; i < path.length; i += 1) {
    const step = path[i];
    if (typeof step !== "number") return null;
    index = step;
    block = list?.[index];
    if (!block) return null;
    const next = path[i + 1];
    if (next === "options") {
      const optionIndex = path[i + 2];
      const option = block.options?.[optionIndex];
      if (!option) return null;
      if (path[i + 3] === "response_blocks") {
        list = option.response_blocks || [];
        i += 3;
        continue;
      }
      return { block: option, list: block.options, index: optionIndex, kind: "option", parent: block };
    }
    if (i < path.length - 1) return null;
  }
  return { block, list, index, kind: "block" };
}

function selectPath(path) {
  state.selectedPath = clonePath(path);
  if (state.selectedAnnotation && !pathEquals(state.selectedAnnotation.path, path)) {
    state.selectedAnnotation = null;
  }
  renderPreview();
  renderSelectedMeta();
  renderSelectedEditor();
}

function makeNode(className, path) {
  const node = document.createElement("div");
  node.className = className + (pathEquals(state.selectedPath, path) ? " is-selected" : "");
  node.onclick = event => {
    event.stopPropagation();
    state.selectedAnnotation = null;
    selectPath(path);
  };
  return node;
}

function collectAnnotationEntries() {
  const map = new Map();
  for (const entry of state.annotationLibrary || []) {
    if (!map.has(entry.term)) map.set(entry.term, { ...entry, path: null, source_kind: "world" });
  }
  return Array.from(map.values()).sort((a, b) => b.term.length - a.term.length);
}

function refreshAnnotationDatalist() {
  const datalist = document.getElementById("annotationRefOptions");
  if (!datalist) return;
  datalist.innerHTML = "";
  collectAnnotationEntries().forEach(entry => {
    const option = document.createElement("option");
    option.value = entry.term;
    const meta = entry.source_path || entry.source_title || "";
    option.label = meta && meta !== entry.term ? `${entry.term} · ${meta}` : entry.term;
    datalist.appendChild(option);
  });
}

function fillWorldTargetOptions() {
  const select = document.getElementById("createAnnotationTarget");
  if (!select) return;
  select.innerHTML = "";
  if (!(state.worldTargets || []).length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "\u6682\u65e0\u53ef\u7528\u7684\u4e16\u754c\u89c2\u76ee\u6807\u6587\u4ef6\u5939";
    select.appendChild(option);
    return;
  }
  (state.worldTargets || []).forEach(item => {
    const option = document.createElement("option");
    option.value = item.path;
    option.textContent = item.label || item.path;
    select.appendChild(option);
  });
}

function findAnnotationEntry(term) {
  const needle = String(term || "").trim();
  if (!needle) return null;
  return collectAnnotationEntries().find(entry => entry.term === needle) || null;
}

function searchAnnotationEntries(query) {
  const needle = String(query || "").trim().toLowerCase();
  if (!needle) return collectAnnotationEntries().slice(0, 12);
  return collectAnnotationEntries()
    .filter(entry => entry.term.toLowerCase().includes(needle))
    .slice(0, 12);
}

function getCurrentDocumentPrimaryAnnotationTerm() {
  const path = String(state.path || "");
  if (!path.startsWith("\u4e16\u754c\u89c2/")) return "";
  const fileName = path.split("/").pop() || "";
  if (fileName.endsWith(".editor.json")) return fileName.slice(0, -".editor.json".length);
  if (fileName.endsWith(".txt")) return fileName.slice(0, -".txt".length);
  return "";
}

function detectAnnotationRefsInText(text, excludedTerms = []) {
  const value = String(text || "");
  if (!value) return [];
  const excluded = new Set((excludedTerms || []).map(item => String(item || "").trim()).filter(Boolean));
  const detected = [];
  const occupied = new Array(value.length).fill(false);
  for (const entry of collectAnnotationEntries()) {
    const term = String(entry.term || "");
    if (!term || excluded.has(term)) continue;
    let start = value.indexOf(term);
    while (start !== -1) {
      const end = start + term.length;
      const overlaps = occupied.slice(start, end).some(Boolean);
      if (!overlaps) {
        detected.push({ term, start, end });
        for (let i = start; i < end; i += 1) occupied[i] = true;
      }
      start = value.indexOf(term, start + 1);
    }
  }
  return detected.sort((a, b) => {
    if (a.start !== b.start) return a.start - b.start;
    return a.end - b.end;
  });
}

function autoDetectAnnotationSpansForPath(path) {
  const ref = getRef(path);
  if (!ref) return [];
  const selfTerm = getCurrentDocumentPrimaryAnnotationTerm();
  const excludedTerms = selfTerm ? [selfTerm] : [];
  if (ref.kind === "option") return detectAnnotationRefsInText(ref.block.label || "", excludedTerms);
  if (REFERENCEABLE_TYPES.has(ref.block.type)) return detectAnnotationRefsInText(ref.block.text || "", excludedTerms);
  return [];
}

function autoSyncAnnotationRefsForPath(path) {
  const spans = autoDetectAnnotationSpansForPath(path);
  const omissions = getAnnotationOmissionsForPath(path);
  const omissionKeys = new Set(omissions.map(item => `${item.term}@@${item.start}@@${item.end}`));
  const effectiveSpans = spans.filter(item => !omissionKeys.has(`${item.term}@@${item.start}@@${item.end}`));
  setAnnotationRefsForPath(path, effectiveSpans.map(item => item.term));
  setAnnotationOmissionsForPath(
    path,
    omissions.filter(item => spans.some(span => span.term === item.term && span.start === item.start && span.end === item.end))
  );
}

function syncAllAutoAnnotationRefs() {
  const walkBlocks = (blocks, pathPrefix = []) => {
    (blocks || []).forEach((block, index) => {
      const currentPath = pathPrefix.concat(index);
      const blockType = normalizeBlockType(block.type);
      if (REFERENCEABLE_TYPES.has(blockType)) {
        autoSyncAnnotationRefsForPath(currentPath);
      }
      if (blockType === "branch") {
        (block.options || []).forEach((option, optIndex) => {
          const optionPath = currentPath.concat(["options", optIndex]);
          autoSyncAnnotationRefsForPath(optionPath);
          walkBlocks(option.response_blocks || [], optionPath.concat(["response_blocks"]));
        });
      }
    });
  };
  walkBlocks(state.document.blocks || []);
}

function getAnnotationRefsForPath(path) {
  const ref = getRef(path);
  if (!ref) return [];
  if (ref.kind === "option") return normalizeAnnotationRefs(ref.block.annotation_refs || []);
  if (REFERENCEABLE_TYPES.has(ref.block.type)) {
    return normalizeAnnotationRefs(ref.block.annotation_refs || []);
  }
  return [];
}

function getAnnotationOmissionsForPath(path) {
  const ref = getRef(path);
  if (!ref) return [];
  if (ref.kind === "option") return normalizeAnnotationOmissions(ref.block.annotation_omissions || []);
  if (REFERENCEABLE_TYPES.has(ref.block.type)) {
    return normalizeAnnotationOmissions(ref.block.annotation_omissions || []);
  }
  return [];
}

function setAnnotationRefsForPath(path, refs) {
  const ref = getRef(path);
  if (!ref) return;
  const normalized = normalizeAnnotationRefs(refs);
  if (ref.kind === "option") {
    ref.block.annotation_refs = normalized;
    return;
  }
  if (REFERENCEABLE_TYPES.has(ref.block.type)) {
    ref.block.annotation_refs = normalized;
  }
}

function setAnnotationOmissionsForPath(path, omissions) {
  const ref = getRef(path);
  if (!ref) return;
  const normalized = normalizeAnnotationOmissions(omissions);
  if (ref.kind === "option") {
    ref.block.annotation_omissions = normalized;
    return;
  }
  if (REFERENCEABLE_TYPES.has(ref.block.type)) {
    ref.block.annotation_omissions = normalized;
  }
}

function addAnnotationRef(path, term) {
  const entry = findAnnotationEntry(term);
  if (!entry) return false;
  const omissions = getAnnotationOmissionsForPath(path).filter(item => item.term !== entry.term);
  setAnnotationOmissionsForPath(path, omissions);
  const refs = getAnnotationRefsForPath(path);
  if (!refs.includes(entry.term)) refs.push(entry.term);
  setAnnotationRefsForPath(path, refs);
  autoSyncAnnotationRefsForPath(path);
  refreshAnnotationDatalist();
  renderPreview();
  renderSelectedMeta();
  renderSelectedEditor();
  return true;
}

function openCreateAnnotationModal(path) {
  state.pendingAnnotationCreatePath = clonePath(path);
  const termInput = document.getElementById("createAnnotationTerm");
  const definitionInput = document.getElementById("createAnnotationDefinition");
  termInput.value = state.activeSelection && pathEquals(state.activeSelection.path, path) ? state.activeSelection.text : "";
  definitionInput.value = "";
  fillWorldTargetOptions();
  modal("createAnnotationModal", true);
}

function removeAnnotationRef(path, selectedAnnotation) {
  if (!selectedAnnotation) return;
  const omissions = getAnnotationOmissionsForPath(path);
  omissions.push({
    term: selectedAnnotation.term,
    start: selectedAnnotation.start,
    end: selectedAnnotation.end
  });
  setAnnotationOmissionsForPath(path, omissions);
  autoSyncAnnotationRefsForPath(path);
  if (
    state.selectedAnnotation &&
    pathEquals(state.selectedAnnotation.path, path) &&
    state.selectedAnnotation.term === selectedAnnotation.term &&
    state.selectedAnnotation.start === selectedAnnotation.start &&
    state.selectedAnnotation.end === selectedAnnotation.end
  ) {
    state.selectedAnnotation = null;
  }
  renderPreview();
  renderSelectedMeta();
  renderSelectedEditor();
}

function openAnnotationEntry(entry) {
  if (!entry) return;
  if (entry.path) selectPath(entry.path);
  document.getElementById("annotationTitle").textContent = entry.term || "\u6ce8\u91ca";
  const annotationBody = document.getElementById("annotationBody");
  annotationBody.className = "preview-node";
  annotationBody.innerHTML = annotateText(entry.definition || "", entry.path || null);
  bindAnnotationTerms(annotationBody);
  const sourceNode = document.getElementById("annotationSource");
  if (sourceNode) {
    if (entry.source_path && entry.source_title && entry.source_title !== entry.term) {
      sourceNode.textContent = `${entry.source_title} · ${entry.source_path}`;
    } else {
      sourceNode.textContent = entry.source_path || "";
    }
  }
  modal("annotationModal", true);
}

function getAnnotatableEntries(sourcePath = null) {
  const explicitRefs = sourcePath ? getAnnotationRefsForPath(sourcePath) : [];
  if (!explicitRefs.length) return [];
  const combined = collectAnnotationEntries();
  return explicitRefs
    .map(term => combined.find(entry => entry.term === term))
    .filter(Boolean)
    .sort((a, b) => b.term.length - a.term.length);
}

function getEffectiveAnnotationSpans(sourcePath) {
  if (!sourcePath) return [];
  const refs = new Set(getAnnotationRefsForPath(sourcePath));
  if (!refs.size) return [];
  const omissions = new Set(
    getAnnotationOmissionsForPath(sourcePath).map(item => `${item.term}@@${item.start}@@${item.end}`)
  );
  return autoDetectAnnotationSpansForPath(sourcePath)
    .filter(item => refs.has(item.term))
    .filter(item => !omissions.has(`${item.term}@@${item.start}@@${item.end}`));
}

function annotateText(text, sourcePath = null) {
  const value = String(text || "");
  if (!value) return "";
  if (!sourcePath) return esc(value);
  const spans = getEffectiveAnnotationSpans(sourcePath);
  if (!spans.length) return esc(value);
  let i = 0;
  let html = "";
  for (const span of spans) {
    if (span.start > i) html += esc(value.slice(i, span.start));
    html += `<span class="annotation-term" data-annotation-term="${esc(span.term)}" data-annotation-start="${span.start}" data-annotation-end="${span.end}">${esc(value.slice(span.start, span.end))}</span>`;
    i = span.end;
  }
  if (i < value.length) html += esc(value.slice(i));
  return html;
}

function bindAnnotationTerms(container, sourcePath = null) {
  if (!container) return;
  container.querySelectorAll(".annotation-term[data-annotation-term]").forEach(el => {
    el.onclick = event => {
      event.stopPropagation();
      const term = el.getAttribute("data-annotation-term") || "";
      const start = Number(el.getAttribute("data-annotation-start"));
      const end = Number(el.getAttribute("data-annotation-end"));
      if (sourcePath) {
        state.selectedAnnotation = {
          path: clonePath(sourcePath),
          term,
          start: Number.isInteger(start) ? start : -1,
          end: Number.isInteger(end) ? end : -1
        };
        selectPath(sourcePath);
        openAnnotationEntry(findAnnotationEntry(term));
        return;
      }
      openAnnotationEntry(findAnnotationEntry(term));
    };
  });
}

function isEmptyBlock(block) {
  if (!block) return true;
  const blockType = normalizeBlockType(block.type);
  if (blockType === "line") return !(String(block.speaker || "").trim() || String(block.text || "").trim());
  if (blockType === "branch") return !(block.options || []).length || (block.options || []).some(option => !String(option.label || "").trim());
  return !String(block.text || "").trim();
}

function renderPreviewBlock(block, root, path) {
  const blockType = normalizeBlockType(block.type);
  if (blockType === "scene_cast") {
    const firstScene = Array.isArray(path) && path[0] === 0;
    if (!firstScene) {
      const spacer = document.createElement("div");
      spacer.className = "scene-spacer";
      root.appendChild(spacer);
    }
    const node = makeNode(`scene-heading preview-node${firstScene ? " scene-first" : ""}${isEmptyBlock(block) ? " is-empty" : ""}`, path);
    node.innerHTML = annotateText(block.text || "", path) || "\u672a\u547d\u540d\u573a\u666f";
    bindAnnotationTerms(node, path);
    root.appendChild(node);
    return;
  }
  if (blockType === "narration" || blockType === "narration_small" || blockType === "supplement") {
    const cls = blockType === "supplement"
      ? "analysis-block"
      : (blockType === "narration_small" ? "narration-block" : "heading-block");
    const node = makeNode(`preview-node ${cls}${block.italic ? " is-italic" : ""}${isEmptyBlock(block) ? " is-empty" : ""}`, path);
    const text = String(block.text || "");
    const placeholder =
      blockType === "narration" ? "\u8f93\u5165\u65c1\u767d\u00b7\u5927" :
      blockType === "narration_small" ? "\u8f93\u5165\u65c1\u767d\u00b7\u5c0f" :
      "\u8f93\u5165\u65c1\u767d\u00b7\u8865\u5145";
    node.innerHTML = annotateText(text, path) || placeholder;
    bindAnnotationTerms(node, path);
    root.appendChild(node);
    return;
  }
  if (blockType === "line") {
    const node = makeNode(`preview-node line-block${isEmptyBlock(block) ? " is-empty" : ""}`, path);
    const speaker = String(block.speaker || "").trim() || "\u89d2\u8272";
    const text = String(block.text || "");
    node.innerHTML = `<span class="line-speaker">${esc(speaker)}\uff1a</span><span class="line-text">${annotateText(text, path) || "\u8f93\u5165\u53f0\u8bcd"}</span>`;
    bindAnnotationTerms(node, path);
    root.appendChild(node);
    return;
  }
  if (blockType === "summary") {
    const node = makeNode(`preview-node${isEmptyBlock(block) ? " is-empty" : ""}`, path);
    node.innerHTML = `<div class="summary-trigger">\u5267\u60c5\u6897\u6982</div>`;
    node.querySelector(".summary-trigger").onclick = event => {
      event.stopPropagation();
      selectPath(path);
      document.getElementById("summaryBody").innerHTML = annotateText(block.text || "", path);
      bindAnnotationTerms(document.getElementById("summaryBody"));
      modal("summaryModal", true);
    };
    root.appendChild(node);
    return;
  }
  if (blockType === "branch") {
    const optionSpeakerNode = document.createElement("div");
    optionSpeakerNode.className = "branch-option-speaker";
    optionSpeakerNode.textContent = `${block.option_speaker || "\u6f02\u6cca\u8005"}\uff1a`;
    root.appendChild(optionSpeakerNode);
    const panel = makeNode(`choices${isEmptyBlock(block) ? " is-empty" : ""}`, path);
    const key = block.id;
    if (!state.branchSelection[key] && block.options?.[0]) state.branchSelection[key] = block.options[0].id;
    block.options.forEach((option, optIndex) => {
      const choice = document.createElement("div");
      choice.className = "choice" + (state.branchSelection[key] === option.id ? " active" : "");
      const renderedLabel = annotateText(option.label || "", path.concat(["options", optIndex]));
      choice.innerHTML = renderedLabel || "&nbsp;";
      bindAnnotationTerms(choice, path.concat(["options", optIndex]));
      choice.onclick = event => {
        event.stopPropagation();
        state.branchSelection[key] = option.id;
        selectPath(path.concat(["options", optIndex]));
      };
      panel.appendChild(choice);
    });
    root.appendChild(panel);
    const selectedIndex = Math.max(0, block.options.findIndex(option => option.id === state.branchSelection[key]));
    const selected = block.options[selectedIndex] || block.options[0];
    (selected?.response_blocks || []).forEach((sub, subIndex) =>
      renderPreviewBlock(sub, root, path.concat(["options", selectedIndex, "response_blocks", subIndex]))
    );
    return;
  }

  const fallback = makeNode(`preview-node${isEmptyBlock(block) ? " is-empty" : ""}`, path);
  fallback.innerHTML = annotateText(block.text || "", path);
  bindAnnotationTerms(fallback, path);
  root.appendChild(fallback);
}

function renderPreview() {
  document.getElementById("previewTitle").textContent = state.document.title || "";
  const root = document.getElementById("previewRoot");
  root.innerHTML = "";
  state.document.blocks.forEach((block, index) => {
    try {
      renderPreviewBlock(block, root, [index]);
    } catch (error) {
      console.error("renderPreviewBlock failed", block, error);
      const fallback = document.createElement("div");
      fallback.className = "preview-node is-empty";
      fallback.textContent = String(block?.text || "");
      root.appendChild(fallback);
    }
  });
}

function scrollSelectedPreviewIntoView() {
  requestAnimationFrame(() => {
    const selected = document.querySelector("#previewRoot .is-selected");
    if (selected && typeof selected.scrollIntoView === "function") {
      selected.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }
  });
}

function renderSelectedMeta() {
  const meta = document.getElementById("selectedMeta");
  const ref = getRef(state.selectedPath);
  if (!ref) {
    meta.textContent = "\u8bf7\u5728\u4e2d\u95f4\u9884\u89c8\u533a\u70b9\u51fb\u4e00\u4e2a\u5757\u3002";
    return;
  }
  const blockType = normalizeBlockType(ref.block.type);
  const label = ref.kind === "option" ? "\u5206\u652f\u9009\u9879" : (TYPE_LABEL[blockType] || blockType);
  const selected = state.selectedAnnotation;
  if (selected && pathEquals(selected.path, state.selectedPath)) {
    meta.textContent = `${label} \u00b7 \u4f4d\u7f6e ${ref.index + 1} \u00b7 \u6ce8\u91ca ${selected.term}`;
    return;
  }
  meta.textContent = `${label} \u00b7 \u4f4d\u7f6e ${ref.index + 1}`;
}

function buildAnnotationRefEditor(path) {
  const wrapper = document.createElement("div");
  wrapper.className = "field annotation-ref-panel";
  wrapper.innerHTML = `
    <div class="muted">\u6ce8\u91ca\u5f15\u7528</div>
    <div class="inline annotation-ref-row">
      <input type="text" data-role="annotation-ref-input" placeholder="\u8f93\u5165\u6ce8\u91ca\uff0c\u4e0b\u65b9\u4f1a\u51fa\u73b0\u53ef\u9009\u5019\u9009\u9879" autocomplete="off" />
      <button type="button" class="ghost" data-role="annotation-ref-create">\u65b0\u5efa\u6ce8\u91ca</button>
    </div>
    <div class="annotation-suggest-list" data-role="annotation-suggest-list"></div>
    <div data-role="annotation-selected-action"></div>
  `;

  const input = wrapper.querySelector('[data-role="annotation-ref-input"]');
  const createButton = wrapper.querySelector('[data-role="annotation-ref-create"]');
  const suggestList = wrapper.querySelector('[data-role="annotation-suggest-list"]');
  const selectedAction = wrapper.querySelector('[data-role="annotation-selected-action"]');

  const renderSelectedAction = () => {
    selectedAction.innerHTML = "";
    const selected = state.selectedAnnotation;
    const spans = getEffectiveAnnotationSpans(path);
    const exists = spans.some(item => item.term === selected?.term && item.start === selected?.start && item.end === selected?.end);
    if (!selected || !pathEquals(selected.path, path) || !exists) return;
    const row = document.createElement("div");
    row.className = "inline";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "danger";
    button.textContent = `\u53d6\u6d88\u6ce8\u91ca\uff1a${selected.term}`;
    button.onclick = event => {
      event.stopPropagation();
      removeAnnotationRef(path, selected);
    };
    row.appendChild(button);
    selectedAction.appendChild(row);
  };

  const renderSuggestions = () => {
    const query = input.value.trim();
    const refs = new Set(getAnnotationRefsForPath(path));
    const items = searchAnnotationEntries(query).filter(entry => !refs.has(entry.term));
    suggestList.innerHTML = "";
    if (!query || !items.length) return;
    items.forEach(entry => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "annotation-suggest-item";
      const meta = entry.source_title && entry.source_title !== entry.term
        ? entry.source_title
        : (entry.source_path || "");
      item.innerHTML = `<span class="annotation-suggest-term">${esc(entry.term)}</span><span class="annotation-suggest-source">${esc(meta)}</span>`;
      item.onclick = event => {
        event.stopPropagation();
        addAnnotationRef(path, entry.term);
        input.value = "";
        renderSuggestions();
      };
      suggestList.appendChild(item);
    });
  };

  input.addEventListener("input", renderSuggestions);
  input.addEventListener("focus", renderSuggestions);
  createButton.onclick = () => openCreateAnnotationModal(path);

  renderSelectedAction();
  renderSuggestions();
  return wrapper;
}

function renderOptionEditor(option, container) {
  if (!Array.isArray(option.response_blocks)) option.response_blocks = [];
  const selectedOptionPath = clonePath(state.selectedPath);
  const wrapper = document.createElement("div");
  wrapper.className = "field";
  wrapper.innerHTML = `<input id="selectedOptionText" placeholder="\u9009\u9879\u6587\u672c" value="${esc(option.label || "")}" />`;
  bindInput(wrapper.querySelector("#selectedOptionText"), value => {
    option.label = value;
    autoSyncAnnotationRefsForPath(selectedOptionPath);
  }, false);
  wrapper.appendChild(buildAnnotationRefEditor(selectedOptionPath));
  const addBar = document.createElement("div");
  addBar.className = "button-grid compact";
    ADDABLE_BLOCK_TYPES.filter(type => type !== "scene_cast").forEach(type => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = `\u65b0\u589e${TYPE_LABEL[type] || type}`;
    button.onclick = () => {
      option.response_blocks.push(createBlock(type));
      state.selectedPath = clonePath(state.selectedPath).concat(["response_blocks", option.response_blocks.length - 1]);
      refreshAnnotationDatalist();
      renderPreview();
      renderSelectedMeta();
      renderSelectedEditor();
      scrollSelectedPreviewIntoView();
    };
    addBar.appendChild(button);
  });
  wrapper.appendChild(addBar);
  const subList = document.createElement("div");
  subList.className = "sub-list";
  if (!option.response_blocks.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "\u5f53\u524d\u9009\u9879\u8fd8\u6ca1\u6709\u540e\u7eed\u6587\u672c\uff0c\u8bf7\u5148\u65b0\u589e\u5bf9\u767d\u6216\u65c1\u767d\u3002";
    subList.appendChild(empty);
  }
  option.response_blocks.forEach((sub, subIndex) => {
    const item = document.createElement("div");
    item.className = "sub-item";
    const subType = normalizeBlockType(sub.type);
    item.innerHTML = `<div class="muted">${TYPE_LABEL[subType] || subType} ${subIndex + 1}</div>`;
        renderFieldEditor(sub, item, selectedOptionPath.concat(["response_blocks", subIndex]));
    subList.appendChild(item);
  });
  wrapper.appendChild(subList);
  container.innerHTML = "";
  container.appendChild(wrapper);
}

function renderFieldEditor(block, container, currentPath = state.selectedPath) {
  const blockType = normalizeBlockType(block.type);
  if (blockType === "line") {
    container.innerHTML = `<div class="field"><input id="selectedLineSpeaker" placeholder="\u8bf4\u8bdd\u89d2\u8272" value="${esc(block.speaker || "")}" /><textarea id="selectedLineText" placeholder="\u5bf9\u767d\u5185\u5bb9">${esc(block.text || "")}</textarea></div>`;
    bindInput(container.querySelector("#selectedLineSpeaker"), value => block.speaker = value, false);
    bindInput(container.querySelector("#selectedLineText"), value => {
      block.text = value;
      autoSyncAnnotationRefsForPath(currentPath);
    }, false);
    bindSelectionCapture(container.querySelector("#selectedLineSpeaker"), currentPath);
    bindSelectionCapture(container.querySelector("#selectedLineText"), currentPath);
    container.appendChild(buildAnnotationRefEditor(currentPath));
    return;
  }
  if (blockType === "branch") {
    const wrapper = document.createElement("div");
    wrapper.className = "field";
    wrapper.innerHTML = `<input id="selectedBranchSpeaker" placeholder="\u9009\u9879\u53d1\u8d77\u8005\uff0c\u9ed8\u8ba4\u6f02\u6cca\u8005" value="${esc(block.option_speaker || "\u6f02\u6cca\u8005")}" />`;
    bindInput(wrapper.querySelector("#selectedBranchSpeaker"), value => block.option_speaker = value || "\u6f02\u6cca\u8005", false);
    bindSelectionCapture(wrapper.querySelector("#selectedBranchSpeaker"), currentPath);
    const optionAddBar = document.createElement("div");
    optionAddBar.className = "inline";
    const addOptionBtn = document.createElement("button");
    addOptionBtn.type = "button";
    addOptionBtn.className = "secondary";
    addOptionBtn.textContent = "\u65b0\u589e\u9009\u9879";
    addOptionBtn.onclick = () => {
      block.options = Array.isArray(block.options) ? block.options : [];
      block.options.push(createOption());
      state.selectedPath = currentPath.concat(["options", block.options.length - 1]);
      renderPreview();
      renderSelectedMeta();
      renderSelectedEditor();
    };
    optionAddBar.appendChild(addOptionBtn);
    wrapper.appendChild(optionAddBar);
    block.options.forEach((option, optIndex) => {
      const card = document.createElement("div");
      card.className = "option-card";
      card.innerHTML = `<div class="muted">\u9009\u9879 ${optIndex + 1}</div><input data-role="label" placeholder="\u9009\u9879\u6587\u672c" value="${esc(option.label || "")}" />`;
      bindInput(card.querySelector('[data-role="label"]'), value => {
        option.label = value;
        autoSyncAnnotationRefsForPath(currentPath.concat(["options", optIndex]));
      }, false);
      bindSelectionCapture(card.querySelector('[data-role="label"]'), currentPath.concat(["options", optIndex]));
      card.appendChild(buildAnnotationRefEditor(currentPath.concat(["options", optIndex])));
      const subList = document.createElement("div");
      subList.className = "sub-list";
      (option.response_blocks || []).forEach((sub, subIndex) => {
        const item = document.createElement("div");
        item.className = "sub-item";
        const subType = normalizeBlockType(sub.type);
        item.innerHTML = `<div class="muted">${TYPE_LABEL[subType] || subType} ${subIndex + 1}</div>`;
        renderFieldEditor(sub, item, currentPath.concat(["options", optIndex, "response_blocks", subIndex]));
        subList.appendChild(item);
      });
      card.appendChild(subList);
      wrapper.appendChild(card);
    });
    container.innerHTML = "";
    container.appendChild(wrapper);
    return;
  }
  if (blockType === "scene_cast") {
    container.innerHTML = `<div class="field"><textarea id="selectedText" placeholder="\u8f93\u5165\u6587\u672c">${esc(block.text || "")}</textarea></div>`;
    bindInput(container.querySelector("#selectedText"), value => {
      block.text = value;
      autoSyncAnnotationRefsForPath(currentPath);
    }, false);
    bindSelectionCapture(container.querySelector("#selectedText"), currentPath);
    container.appendChild(buildAnnotationRefEditor(currentPath));
    return;
  }
  if (blockType === "supplement") {
    container.innerHTML = `<div class="field"><textarea id="selectedText" placeholder="\u8f93\u5165\u6587\u672c">${esc(block.text || "")}</textarea></div>`;
    bindInput(container.querySelector("#selectedText"), value => {
      block.text = value;
      autoSyncAnnotationRefsForPath(currentPath);
    }, false);
    bindSelectionCapture(container.querySelector("#selectedText"), currentPath);
    container.appendChild(buildAnnotationRefEditor(currentPath));
    return;
  }
  if (blockType === "narration" || blockType === "narration_small") {
    container.innerHTML = `
      <div class="field">
        <textarea id="selectedText" placeholder="\u8f93\u5165\u6587\u672c">${esc(block.text || "")}</textarea>
        <label class="muted"><input id="selectedItalic" type="checkbox" ${block.italic ? "checked" : ""} style="width:auto;margin-right:8px;" />\u5b57\u4f53\u503e\u659c</label>
      </div>
    `;
    bindInput(container.querySelector("#selectedText"), value => {
      block.text = value;
      autoSyncAnnotationRefsForPath(currentPath);
    }, false);
    container.querySelector("#selectedItalic").addEventListener("change", event => {
      block.italic = !!event.target.checked;
      renderPreview();
      renderSelectedMeta();
    });
    bindSelectionCapture(container.querySelector("#selectedText"), currentPath);
    container.appendChild(buildAnnotationRefEditor(currentPath));
    return;
  }
  container.innerHTML = `<div class="field"><textarea id="selectedText" placeholder="\u8f93\u5165\u6587\u672c">${esc(block.text || "")}</textarea></div>`;
  bindInput(container.querySelector("#selectedText"), value => {
    block.text = value;
    autoSyncAnnotationRefsForPath(currentPath);
  }, false);
  bindSelectionCapture(container.querySelector("#selectedText"), currentPath);
  container.appendChild(buildAnnotationRefEditor(currentPath));
}

function renderSelectedEditor() {
  const root = document.getElementById("selectedEditor");
  const ref = getRef(state.selectedPath);
  if (!ref) {
    root.className = "muted";
    root.textContent = "\u8bf7\u5728\u4e2d\u95f4\u9884\u89c8\u533a\u70b9\u51fb\u4e00\u4e2a\u5757\u5f00\u59cb\u7f16\u8f91\u3002";
    return;
  }
  root.className = "";
  const blockType = normalizeBlockType(ref.block.type);
  const label = ref.kind === "option" ? "\u5206\u652f\u9009\u9879" : (TYPE_LABEL[blockType] || blockType);
  root.innerHTML = `<div class="muted">${label}</div>`;
  if (ref.kind === "option") {
    renderOptionEditor(ref.block, root);
  } else {
    renderFieldEditor(ref.block, root, state.selectedPath);
  }
}

function applySelectionAction(action, insertType) {
  const ref = getRef(state.selectedPath);
  if (!ref) return;
  if (action === "insert") {
    const chosenType = insertType || "line";
    if (ref.kind === "option") {
      ref.parent.options[ref.index].response_blocks = ref.parent.options[ref.index].response_blocks || [];
      ref.parent.options[ref.index].response_blocks.unshift(createBlock(chosenType));
      state.selectedPath = clonePath(state.selectedPath).concat(["response_blocks", 0]);
    } else {
      ref.list.splice(ref.index, 0, createBlock(chosenType));
      const path = clonePath(state.selectedPath);
      path[path.length - 1] = ref.index;
      state.selectedPath = path;
    }
  } else if (action === "delete") {
    ref.list.splice(ref.index, 1);
    state.selectedPath = null;
  } else if (action === "up") {
    move(ref.list, ref.index, -1);
    if (ref.index > 0) {
      const path = clonePath(state.selectedPath);
      path[path.length - 1] = ref.index - 1;
      state.selectedPath = path;
    }
  } else if (action === "down") {
    move(ref.list, ref.index, 1);
    if (ref.index < ref.list.length - 1) {
      const path = clonePath(state.selectedPath);
      path[path.length - 1] = ref.index + 1;
      state.selectedPath = path;
    }
  }
  refreshAnnotationDatalist();
  renderPreview();
  renderSelectedMeta();
  renderSelectedEditor();
  scrollSelectedPreviewIntoView();
}

function showInsertPicker() {
  const ref = getRef(state.selectedPath);
  if (!ref) return;
  const holder = document.getElementById("insertTypeButtons");
  holder.innerHTML = "";
  ADDABLE_BLOCK_TYPES.forEach(type => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "secondary";
    btn.textContent = TYPE_LABEL[type] || type;
    btn.onclick = () => {
      modal("insertModal", false);
      applySelectionAction("insert", type);
    };
    holder.appendChild(btn);
  });
  modal("insertModal", true);
}

async function loadAnnotationLibrary() {
  const resp = await fetch("/editor/annotation-library?limit=1000", { cache: "no-store" });
  if (!resp.ok) throw new Error(`\u52a0\u8f7d\u6ce8\u91ca\u5e93\u5931\u8d25\uff1a${resp.status}`);
  const payload = await resp.json();
  state.annotationLibrary = payload.items || [];
  syncAllAutoAnnotationRefs();
  refreshAnnotationDatalist();
}

async function loadWorldTargets() {
  const resp = await fetch("/editor/world-targets", { cache: "no-store" });
  if (!resp.ok) throw new Error(`\u52a0\u8f7d\u4e16\u754c\u89c2\u76ee\u6807\u6587\u4ef6\u5939\u5931\u8d25\uff1a${resp.status}`);
  const payload = await resp.json();
  state.worldTargets = payload.items || [];
  fillWorldTargetOptions();
}

async function createWorldAnnotationFromSelection() {
  const term = document.getElementById("createAnnotationTerm").value.trim();
  const definition = document.getElementById("createAnnotationDefinition").value.trim();
  const targetPath = document.getElementById("createAnnotationTarget").value.trim();
  if (!term) {
      setStatus("\u8bf7\u5148\u586b\u5199\u6ce8\u91ca\u540d\u79f0\u3002");
    return;
  }
  if (!definition) {
      setStatus("\u8bf7\u5148\u586b\u5199\u6ce8\u91ca\u5185\u5bb9\u3002");
    return;
  }
  if (!targetPath) {
    setStatus("\u8bf7\u5148\u9009\u62e9\u4e00\u4e2a\u4e16\u754c\u89c2\u76ee\u6807\u6587\u4ef6\u5939\u3002");
    return;
  }
  const resp = await fetch("/editor/world-annotation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ target_path: targetPath, term, definition })
  });
  if (!resp.ok) {
    const text = await resp.text();
      throw new Error(text || `\u65b0\u5efa\u6ce8\u91ca\u5931\u8d25\uff1a${resp.status}`);
  }
  await loadAnnotationLibrary();
  if (state.pendingAnnotationCreatePath) addAnnotationRef(state.pendingAnnotationCreatePath, term);
  modal("createAnnotationModal", false);
  setStatus(`\u5df2\u521b\u5efa\u6ce8\u91ca\uff1a${term}`);
}

async function loadDocument() {
  const resp = await fetch(`/editor/document?path=${encodeURIComponent(state.path)}`, { cache: "no-store" });
  if (!resp.ok) throw new Error(`\u52a0\u8f7d\u5931\u8d25\uff1a${resp.status}`);
  const payload = await resp.json();
  state.document = normalizeDocument(payload.document);
  state.compiledText = payload.compiled_text || "";
  document.getElementById("docTitle").value = state.document.title || "";
  document.getElementById("editorPath").textContent = state.path;
  state.selectedPath = state.document.blocks.length ? [0] : null;
  syncAllAutoAnnotationRefs();
  refreshAnnotationDatalist();
  renderPreview();
  renderSelectedMeta();
  renderSelectedEditor();
  setStatus(`\u5df2\u52a0\u8f7d ${state.path}\uff08\u6765\u6e90\uff1a${payload.source}\uff09`);
}

async function saveDocument() {
  state.document.title = document.getElementById("docTitle").value.trim();
  const resp = await fetch("/editor/document", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: state.path, document: state.document })
  });
  if (!resp.ok) {
    const text = await resp.text();
    throw new Error(text || `\u4fdd\u5b58\u5931\u8d25\uff1a${resp.status}`);
  }
  const payload = await resp.json();
  state.document = normalizeDocument(payload.document);
  state.compiledText = payload.compiled_text || "";
  refreshAnnotationDatalist();
  renderPreview();
  renderSelectedMeta();
  renderSelectedEditor();
  setStatus(`\u5df2\u4fdd\u5b58 ${state.path}`);
}

async function bootstrap() {
  state.path = pathParam();
  if (!state.path) {
    setStatus("\u7f3a\u5c11 path \u53c2\u6570\uff0c\u8bf7\u4ece\u6743\u9650\u9875\u9009\u62e9 TXT \u540e\u6253\u5f00\u7f16\u8f91\u5668\u3002");
    return;
  }

  document.querySelectorAll("[data-add]").forEach(button => {
    button.onclick = () => {
      const type = String(button.dataset.add || "").trim();
      if (!ADDABLE_BLOCK_TYPES.includes(type)) {
        setStatus(`无法新增未知块类型：${type}`);
        return;
      }
      state.document.blocks.push(createBlock(type));
      state.selectedPath = [state.document.blocks.length - 1];
      refreshAnnotationDatalist();
      renderPreview();
      renderSelectedMeta();
      renderSelectedEditor();
      scrollSelectedPreviewIntoView();
    };
  });

  document.getElementById("docTitle").addEventListener("input", event => {
    state.document.title = event.target.value;
    renderPreview();
  });

  document.getElementById("saveBtn").onclick = async () => {
    try {
      await saveDocument();
    } catch (error) {
      setStatus(`\u4fdd\u5b58\u5931\u8d25\uff1a${error.message || error}`);
      console.error(error);
    }
  };

  document.getElementById("showTxtBtn").onclick = () => {
    document.getElementById("compiledText").textContent = state.compiledText || "";
    modal("txtModal", true);
  };

  const insertBtn = document.getElementById("insertBtn");
  if (insertBtn) insertBtn.onclick = () => showInsertPicker();
  const moveUpBtn = document.getElementById("moveUpBtn");
  if (moveUpBtn) moveUpBtn.onclick = () => applySelectionAction("up");
  const moveDownBtn = document.getElementById("moveDownBtn");
  if (moveDownBtn) moveDownBtn.onclick = () => applySelectionAction("down");
  const deleteBtn = document.getElementById("deleteBtn");
  if (deleteBtn) deleteBtn.onclick = () => applySelectionAction("delete");

  document.getElementById("closeTxtBtn").onclick = () => modal("txtModal", false);
  document.getElementById("closeInsertBtn").onclick = () => modal("insertModal", false);
  document.getElementById("closeSummaryBtn").onclick = () => modal("summaryModal", false);
  document.getElementById("closeAnnotationBtn").onclick = () => modal("annotationModal", false);
  document.getElementById("closeCreateAnnotationBtn").onclick = () => modal("createAnnotationModal", false);
  document.getElementById("submitCreateAnnotationBtn").onclick = async () => {
    try {
      await createWorldAnnotationFromSelection();
    } catch (error) {
      setStatus(`\u521b\u5efa\u6ce8\u91ca\u5931\u8d25\uff1a${error.message || error}`);
      console.error(error);
    }
  };

  await loadWorldTargets();
  await loadAnnotationLibrary();
  await loadDocument();
}

bootstrap().catch(error => {
  setStatus(`\u52a0\u8f7d\u5931\u8d25\uff1a${error.message || error}`);
  console.error(error);
});

