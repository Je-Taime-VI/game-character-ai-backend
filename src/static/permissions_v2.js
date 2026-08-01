const $ = (selector) => document.querySelector(selector);

const state = {
  roles: [],
  role: "",
  permission: null,
  forest: {},
  storySummaries: new Map(),
  regionTree: null,
  regionPaths: [],
  selectedRegionPath: "",
  mappings: {},
  expanded: new Set(),
  selectedPath: "",
  selectedNodeType: "",
  selectedKind: "",
  selectedSummary: null,
  searchIndex: [],
  rowByPath: new Map(),
};

const sectionNames = {
  role: "角色额外权限",
  world: "世界观额外权限",
  story: "主线 / 支线额外权限",
};

function api(path, options = {}) {
  return fetch(path, {
    cache: "no-store",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  }).then(async (resp) => {
    if (!resp.ok) {
      const text = await resp.text();
      throw new Error(text || `${resp.status} ${resp.statusText}`);
    }
    return resp.json();
  });
}

function setStatus(text) {
  $("#statusText").textContent = text;
}

function normalizePath(path) {
  return String(path || "").replaceAll("\\", "/").replace(/^\/+|\/+$/g, "");
}

function basename(path) {
  const name = normalizePath(path).split("/").pop() || path;
  return name.endsWith(".editor.json") ? name.slice(0, -12) : name.replace(/\.txt$/i, "");
}

function regionName(path) {
  return normalizePath(path).split("/").pop() || path;
}

function txtTwin(path) {
  return path.endsWith(".editor.json") ? `${path.slice(0, -12)}.txt` : "";
}

function editorTwin(path) {
  return path.endsWith(".txt") ? `${path.slice(0, -4)}.editor.json` : "";
}

function equivalentPath(a, b) {
  a = normalizePath(a);
  b = normalizePath(b);
  return a === b || txtTwin(a) === b || txtTwin(b) === a;
}

function openEditor(path = state.selectedPath) {
  if (!path) return setStatus("请先选择一个文件。");
  const target = preferEditorPath(path);
  window.open(`/editor?path=${encodeURIComponent(target)}`, "_blank");
}

function preferEditorPath(path) {
  path = normalizePath(path);
  const twin = editorTwin(path);
  return twin && state.rowByPath.has(twin) ? twin : path;
}

function sectionForPath(path) {
  const first = normalizePath(path).split("/")[0] || "";
  if (first === "角色") return "role";
  if (first === "世界观") return "world";
  if (first === "主线" || first === "支线") return "story";
  return "world";
}

function manualSet(kind) {
  if (!state.permission) return new Set();
  const field = kind === "role" ? "extra_role_paths" : kind === "world" ? "extra_world_paths" : "allowed_story_paths";
  return new Set((state.permission[field] || []).map(normalizePath));
}

function forcedSet(kind) {
  if (!state.permission) return new Set();
  const field = kind === "role" ? "forced_role_paths" : kind === "world" ? "forced_world_paths" : "forced_story_paths";
  return new Set((state.permission[field] || []).map(normalizePath));
}

function storyPremiseKey(item) {
  return `${normalizePath(item?.path)}::${item?.premise_type || ""}::${Number(item?.block_index)}`;
}

function storySegmentKey(item) {
  return `${normalizePath(item?.path)}::${Number(item?.block_index)}::${Number(item?.aggregate_start)}::${Number(item?.aggregate_end)}`;
}

function storyPremiseSet() {
  if (!state.permission) return new Set();
  return new Set((state.permission.allowed_story_premises || []).map(storyPremiseKey));
}

function storySegmentSet() {
  if (!state.permission) return new Set();
  return new Set((state.permission.allowed_story_segments || []).map(storySegmentKey));
}

function setStoryPremiseSet(values) {
  const byKey = new Map();
  for (const story of state.storySummaries.values()) {
    for (const item of story.summaries || []) byKey.set(storyPremiseKey(item), item);
  }
  state.permission.allowed_story_premises = [...values]
    .map((key) => byKey.get(key))
    .filter(Boolean)
    .map((item) => ({ path: normalizePath(item.path), premise_type: item.premise_type, block_index: Number(item.block_index) }))
    .sort((a, b) => storyPremiseKey(a).localeCompare(storyPremiseKey(b), "zh-Hans-CN"));
}

function setStorySegmentSet(values) {
  const byKey = new Map();
  for (const story of state.storySummaries.values()) {
    for (const item of story.summaries || []) {
      if (item.premise_type === "paragraph_summary" && Number.isInteger(Number(item.aggregate_start)) && Number.isInteger(Number(item.aggregate_end))) {
        byKey.set(storySegmentKey(item), item);
      }
    }
  }
  state.permission.allowed_story_segments = [...values]
    .map((key) => byKey.get(key))
    .filter(Boolean)
    .map((item) => ({
      path: normalizePath(item.path),
      premise_type: "paragraph_summary",
      block_index: Number(item.block_index),
      aggregate_start: Number(item.aggregate_start),
      aggregate_end: Number(item.aggregate_end),
    }))
    .sort((a, b) => storySegmentKey(a).localeCompare(storySegmentKey(b), "zh-Hans-CN"));
}

function setManual(kind, values) {
  const field = kind === "role" ? "extra_role_paths" : kind === "world" ? "extra_world_paths" : "allowed_story_paths";
  state.permission[field] = [...values].sort();
}

function isSelected(path, kind) {
  const manual = manualSet(kind);
  const forced = forcedSet(kind);
  return [...manual, ...forced].some((item) => equivalentPath(item, path) || normalizePath(path).startsWith(`${item}/`));
}

function storyPathsForTreeNode(path) {
  const row = state.rowByPath.get(path);
  return row?.node_type === "folder" ? [path] : (row?.paths?.length ? row.paths : [path]);
}

function removeStoryPathSpecs(values, paths) {
  for (const item of paths) {
    for (const existing of [...values]) {
      if (equivalentPath(existing, item)) values.delete(existing);
    }
  }
}

function leafPaths(node) {
  if (!node) return [];
  if (node.node_type === "file") return node.paths || [node.path];
  return (node.children || []).flatMap(leafPaths);
}

function selectionState(node, kind) {
  if (kind === "story" && node.node_type === "file") {
    const story = storySummaryForPath(node.path);
    if (story) return storySelectionState(story);
  }
  const leaves = leafPaths(node).map(normalizePath);
  if (!leaves.length) return { checked: isSelected(node.path, kind), partial: false };
  const selectedCount = leaves.filter((path) => isSelected(path, kind)).length;
  return {
    checked: selectedCount === leaves.length,
    partial: selectedCount > 0 && selectedCount < leaves.length,
  };
}

function setSelected(path, kind, checked) {
  const values = manualSet(kind);
  const row = state.rowByPath.get(path);
  const paths = storyPathsForTreeNode(path);
  if (kind === "story" && row?.node_type !== "folder") {
    removeStoryPathSpecs(values, paths);
    setManual(kind, values);
    const story = storySummaryForPath(path);
    if (story) setWholeStorySummaryState(story, checked);
    return;
  }
  for (const item of paths) {
    if (checked) values.add(normalizePath(item));
    else {
      for (const existing of [...values]) {
        if (equivalentPath(existing, item)) values.delete(existing);
      }
    }
  }
  setManual(kind, values);
}

function storySummaryForPath(path) {
  path = normalizePath(path);
  for (const story of state.storySummaries.values()) {
    if (equivalentPath(story.path, path) || equivalentPath(story.editor_path, path)) return story;
  }
  return null;
}

function storySelectionState(story) {
  const summaries = story.summaries || [];
  if (!summaries.length) return { checked: isSelected(story.path, "story"), partial: false };
  const chapter = summaries.find((item) => item.premise_type === "chapter_summary");
  const paragraphs = summaries.filter((item) => item.premise_type === "paragraph_summary");
  const chapterSelected = chapter ? storyPremiseSet().has(storyPremiseKey(chapter)) || isSelected(story.path, "story") : true;
  const paragraphStates = paragraphs.map(storyParagraphState);
  const allParagraphsFull = paragraphStates.every((state) => state === "full");
  const anyParagraphSelected = paragraphStates.some((state) => state !== "none");
  return {
    checked: chapterSelected && allParagraphsFull,
    partial: (chapterSelected || anyParagraphSelected) && !(chapterSelected && allParagraphsFull),
  };
}

function storyParagraphState(item) {
  if (isSelected(item.path, "story")) return "full";
  const hasPremise = storyPremiseSet().has(storyPremiseKey(item));
  const hasSegment = storySegmentSet().has(storySegmentKey(item));
  if (hasSegment) return "full";
  return hasPremise ? "premise" : "none";
}

function isStoryPremiseSelected(item) {
  return isSelected(item.path, "story") || storyPremiseSet().has(storyPremiseKey(item));
}

function setStoryPremiseSelected(item, checked) {
  const storyValues = manualSet("story");
  removeStoryPathSpecs(storyValues, [item.path]);
  setManual("story", storyValues);
  const values = storyPremiseSet();
  const key = storyPremiseKey(item);
  checked ? values.add(key) : values.delete(key);
  setStoryPremiseSet(values);
}

function setStoryParagraphState(item, nextState) {
  const storyValues = manualSet("story");
  removeStoryPathSpecs(storyValues, [item.path]);
  setManual("story", storyValues);
  const premiseValues = storyPremiseSet();
  const segmentValues = storySegmentSet();
  premiseValues.delete(storyPremiseKey(item));
  segmentValues.delete(storySegmentKey(item));
  if (nextState === "premise" || nextState === "full") premiseValues.add(storyPremiseKey(item));
  if (nextState === "full") segmentValues.add(storySegmentKey(item));
  setStoryPremiseSet(premiseValues);
  setStorySegmentSet(segmentValues);
}

function setWholeStorySummaryState(story, checked) {
  const premiseValues = storyPremiseSet();
  const segmentValues = storySegmentSet();
  for (const item of story.summaries || []) {
    premiseValues.delete(storyPremiseKey(item));
    segmentValues.delete(storySegmentKey(item));
    if (checked) {
      premiseValues.add(storyPremiseKey(item));
      if (item.premise_type === "paragraph_summary") segmentValues.add(storySegmentKey(item));
    }
  }
  setStoryPremiseSet(premiseValues);
  setStorySegmentSet(segmentValues);
}

function mergeTwinFiles(node) {
  if (!node || node.node_type !== "folder") return node;
  const merged = [];
  const byStem = new Map();
  for (const child of node.children || []) {
    if (child.node_type === "folder") {
      merged.push(mergeTwinFiles(child));
      continue;
    }
    const path = normalizePath(child.path);
    const stem = path.replace(/\.editor\.json$/i, "").replace(/\.txt$/i, "");
    const current = byStem.get(stem);
    if (current) {
      current.paths.push(path);
      current.path = current.paths.find((item) => item.endsWith(".editor.json")) || current.path;
    } else {
      const item = { ...child, path, paths: [path], name: basename(path), node_type: "file" };
      byStem.set(stem, item);
      merged.push(item);
    }
  }
  return { ...node, children: merged };
}

function indexRows(node) {
  const path = normalizePath(node.path);
  if (path) {
    for (const item of node.paths || [path]) state.rowByPath.set(item, node);
    state.searchIndex.push({ name: basename(path), path, node });
  }
  for (const child of node.children || []) indexRows(child);
}

function renderTreeNode(node, kind, container) {
  const path = normalizePath(node.path);
  const isFolder = node.node_type === "folder";
  const story = kind === "story" && !isFolder ? storySummaryForPath(path) : null;
  const hasExpandableChildren = isFolder || !!story;
  const row = document.createElement("div");
  row.className = `tree-node ${isFolder ? "folder" : "file"}`;
  row.dataset.path = path;
  row.dataset.kind = kind;
  row.dataset.type = node.node_type;

  const toggle = document.createElement("span");
  toggle.className = hasExpandableChildren ? "toggle" : "toggle placeholder";
  toggle.textContent = state.expanded.has(path) ? "▼" : "▶";
  row.append(toggle);

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  const currentState = selectionState(node, kind);
  checkbox.checked = currentState.checked;
  checkbox.indeterminate = currentState.partial;
  checkbox.disabled = [...forcedSet(kind)].some((item) => equivalentPath(item, path) || path.startsWith(`${item}/`));
  checkbox.addEventListener("click", (event) => event.stopPropagation());
  checkbox.addEventListener("change", () => {
    setSelected(path, kind, checkbox.checked);
    renderAll();
  });
  row.append(checkbox);

  const label = document.createElement("span");
  label.className = "node-name";
  label.textContent = isFolder ? node.name : basename(path);
  row.append(label);

  row.addEventListener("click", (event) => {
    event.stopPropagation();
    selectPath(path, node.node_type, kind);
    if (event.target === toggle && hasExpandableChildren) {
      state.expanded.has(path) ? state.expanded.delete(path) : state.expanded.add(path);
      renderAll();
    }
  });
  row.addEventListener("dblclick", (event) => {
    event.stopPropagation();
    if (!isFolder) openEditor(path);
  });
  container.append(row);

  if (state.expanded.has(path)) {
    const children = document.createElement("div");
    children.className = "tree-children";
    if (isFolder) {
      for (const child of node.children || []) renderTreeNode(child, kind, children);
    } else if (story) {
      renderStorySummaryControls(story, children);
    }
    container.append(children);
  }
}

function renderStorySummaryControls(story, container) {
  const chapter = (story.summaries || []).find((item) => item.premise_type === "chapter_summary");
  const paragraphs = (story.summaries || []).filter((item) => item.premise_type === "paragraph_summary");
  const wrapper = document.createElement("div");
  wrapper.className = "story-summary-grid";

  const chapterColumn = document.createElement("div");
  chapterColumn.className = "story-summary-column chapter";
  if (chapter) chapterColumn.append(renderStorySummaryItem(chapter, "本章梗概"));

  const paragraphColumn = document.createElement("div");
  paragraphColumn.className = "story-summary-column paragraphs";
  const title = document.createElement("div");
  title.className = "story-summary-title";
  title.textContent = "段落梗概";
  paragraphColumn.append(title);
  for (const item of paragraphs) paragraphColumn.append(renderStorySummaryItem(item, item.label));

  wrapper.append(chapterColumn, paragraphColumn);
  container.append(wrapper);
}

function renderStorySummaryItem(item, labelText) {
  const row = document.createElement("div");
  row.className = `story-summary-item ${item.premise_type === "paragraph_summary" ? "paragraph" : "chapter"}`;
  row.dataset.summaryKey = storyPremiseKey(item);

  const label = document.createElement("span");
  label.textContent = labelText;
  label.className = "story-summary-label";

  if (item.premise_type !== "paragraph_summary") {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = isStoryPremiseSelected(item);
    checkbox.addEventListener("click", (event) => event.stopPropagation());
    checkbox.addEventListener("change", () => {
      setStoryPremiseSelected(item, checkbox.checked);
      state.selectedSummary = item;
      renderAll();
    });
    row.append(checkbox, label);
  } else {
    row.append(label, renderParagraphStateButtons(item));
  }

  row.addEventListener("click", (event) => {
    event.stopPropagation();
    state.selectedSummary = item;
    renderSummaryPreview();
  });
  return row;
}

function renderParagraphStateButtons(item) {
  const control = document.createElement("div");
  control.className = "paragraph-state-control";
  const currentState = storyParagraphState(item);
  for (const [value, text] of [["none", "无"], ["premise", "仅梗概"], ["full", "梗概+正文"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `paragraph-state-btn ${currentState === value ? "active" : ""}`;
    button.textContent = text;
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      setStoryParagraphState(item, value);
      state.selectedSummary = item;
      renderAll();
    });
    control.append(button);
  }
  return control;
}

function renderTrees() {
  const root = $("#treeRoot");
  root.innerHTML = "";
  state.searchIndex = [];
  state.rowByPath.clear();

  const sections = [];
  for (const [key, rawNode] of Object.entries(state.forest)) {
    const node = mergeTwinFiles(rawNode);
    const kind = sectionForPath(node.path || node.name);
    sections.push([kind, node]);
  }
  for (const [kind, node] of sections) {
    const title = document.createElement("h3");
    title.className = "tree-section-title";
    title.textContent = sectionNames[kind] || node.name;
    root.append(title);
    indexRows(node);
    renderTreeNode(node, kind, root);
  }

  buildSearchSuggestions();
}

function renderRegionNode(node, container) {
  const path = normalizePath(node.path);
  const row = document.createElement("div");
  row.className = "tree-node folder";
  const toggle = document.createElement("span");
  toggle.className = "toggle";
  toggle.textContent = state.expanded.has(`region:${path}`) ? "▼" : "▶";
  row.append(toggle);
  const label = document.createElement("span");
  label.className = "node-name";
  label.textContent = node.name;
  row.append(label);
  row.addEventListener("click", () => {
    const key = `region:${path}`;
    state.expanded.has(key) ? state.expanded.delete(key) : state.expanded.add(key);
    const mappingPath = normalizeRegionMappingPath(path);
    if (mappingPath) {
      setRegionInput(mappingPath);
    }
    renderRegionTree();
  });
  container.append(row);
  if (state.expanded.has(`region:${path}`)) {
    const children = document.createElement("div");
    children.className = "tree-children";
    for (const child of node.children || []) renderRegionNode(child, children);
    container.append(children);
  }
}

function renderRegionTree() {
  const root = $("#regionTree");
  root.innerHTML = "";
  if (state.regionTree) renderRegionNode(state.regionTree, root);
}

function renderSummaryPreview() {
  const root = $("#summaryPreview");
  if (!root) return;
  const item = state.selectedSummary;
  if (!item) {
    root.innerHTML = `<p class="muted">在左侧展开剧情后，点击“本章梗概”或“段落梗概”可在这里预览文本。</p>`;
    return;
  }
  const title = item.premise_type === "chapter_summary" ? "本章梗概" : item.label;
  root.innerHTML = `
    <div class="summary-preview-title">${escapeHtml(title)}</div>
    <div class="summary-preview-path">${escapeHtml(item.path)}</div>
    <div class="summary-preview-text">${escapeHtml(item.text)}</div>
  `;
}

function normalizeRegionMappingPath(path) {
  const normalized = normalizePath(path);
  const rootPath = normalizePath(state.regionTree?.path || "");
  if (!normalized || normalized === rootPath) return "";
  if (rootPath && normalized.startsWith(`${rootPath}/`)) {
    return normalized.slice(rootPath.length + 1);
  }
  return normalized;
}

function collectRegionPaths(node, results = []) {
  const path = normalizeRegionMappingPath(node?.path || "");
  if (path) results.push(path);
  for (const child of node?.children || []) collectRegionPaths(child, results);
  return results;
}

function buildRegionSuggestions() {
  const paths = [...new Set(state.regionPaths.map(normalizeRegionMappingPath).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b, "zh-Hans-CN"));
  state.regionPaths = paths;
  renderRegionSuggestions();
}

function setRegionInput(path) {
  const normalized = normalizeRegionMappingPath(path);
  state.selectedRegionPath = normalized;
  $("#regionInput").value = regionName(normalized);
  hideRegionSuggestions();
}

function resolveRegionInputPath() {
  const value = $("#regionInput").value.trim();
  if (!value) return "";
  if (state.regionPaths.includes(state.selectedRegionPath) && regionName(state.selectedRegionPath) === value) {
    return state.selectedRegionPath;
  }
  if (state.regionPaths.includes(value)) return value;
  const matches = state.regionPaths.filter((path) => regionName(path) === value);
  return matches.length === 1 ? matches[0] : "";
}

function renderRegionSuggestions() {
  const list = $("#regionSuggestions");
  const input = $("#regionInput");
  if (!list || !input) return;
  if (document.activeElement !== input) {
    list.hidden = true;
    return;
  }
  const query = input.value.trim().toLowerCase();
  const hits = state.regionPaths
    .filter((path) => !query || regionName(path).toLowerCase().includes(query) || path.toLowerCase().includes(query))
    .slice(0, 40);
  list.innerHTML = "";
  for (const path of hits) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "region-suggestion";
    button.innerHTML = `<span class="region-suggestion-title">${escapeHtml(regionName(path))}</span><span class="region-suggestion-path">${escapeHtml(path.split("/").join(" / "))}</span>`;
    button.addEventListener("mousedown", (event) => {
      event.preventDefault();
      setRegionInput(path);
    });
    list.append(button);
  }
  list.hidden = hits.length === 0;
}

function hideRegionSuggestions() {
  const list = $("#regionSuggestions");
  if (list) list.hidden = true;
}

function buildSearchSuggestions() {
  const list = $("#searchSuggestions");
  list.innerHTML = "";
  const seen = new Set();
  for (const item of state.searchIndex) {
    const key = `${item.name}|${item.path}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const option = document.createElement("option");
    option.value = item.name;
    option.label = item.path;
    list.append(option);
  }
}

function searchCurrent() {
  const query = $("#searchInput").value.trim().toLowerCase();
  if (!query) return;
  const hit = state.searchIndex.find((item) => item.name.toLowerCase() === query)
    || state.searchIndex.find((item) => item.name.toLowerCase().includes(query) || item.path.toLowerCase().includes(query));
  if (!hit) return setStatus("没有找到匹配项。");
  revealPath(hit.path);
  selectPath(hit.path, hit.node.node_type, sectionForPath(hit.path));
}

function revealPath(path) {
  const parts = normalizePath(path).split("/");
  for (let i = 1; i < parts.length; i += 1) state.expanded.add(parts.slice(0, i).join("/"));
  renderAll();
  requestAnimationFrame(() => {
    const row = document.querySelector(`.tree-node[data-path="${CSS.escape(path)}"]`);
    row?.scrollIntoView({ block: "center", behavior: "smooth" });
  });
}

async function selectPath(path, nodeType = "file", kind = "") {
  state.selectedPath = normalizePath(path);
  state.selectedNodeType = nodeType;
  state.selectedKind = kind || sectionForPath(path);
  renderSelection();
}

function renderSelection() {
  document.querySelectorAll(".tree-node.selected").forEach((item) => item.classList.remove("selected"));
  const row = document.querySelector(`.tree-node[data-path="${CSS.escape(state.selectedPath)}"]`);
  row?.classList.add("selected");
}

function renderMappings() {
  const list = $("#mappingList");
  list.innerHTML = "";
  for (const [org, region] of Object.entries(state.mappings).sort()) {
    const item = document.createElement("div");
    item.className = "mapping-item";
    item.innerHTML = `<div><strong>${escapeHtml(org)}</strong><span>${escapeHtml(region)}</span></div>`;
    const del = document.createElement("button");
    del.className = "danger";
    del.textContent = "删除";
    del.addEventListener("click", async () => {
      await api(`/org-mapping/${encodeURIComponent(org)}`, { method: "DELETE" });
      await loadMappings();
    });
    item.append(del);
    list.append(item);
  }
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

async function saveMapping() {
  const organization = $("#orgInput").value.trim();
  const region_path = resolveRegionInputPath();
  if (!organization || !region_path) return setStatus("请填写势力和地区路径。");
  if (!state.regionPaths.includes(region_path)) return setStatus("请从地区关系树补全列表中选择地区路径。");
  await api("/org-mapping", { method: "POST", body: JSON.stringify({ organization, region_path }) });
  $("#orgInput").value = "";
  $("#regionInput").value = "";
  state.selectedRegionPath = "";
  await loadMappings();
  setStatus("势力地区映射已保存。");
}

function selectedParentPath() {
  if (!state.selectedPath) return "";
  if (state.selectedNodeType === "folder") return state.selectedPath;
  const parts = state.selectedPath.split("/");
  parts.pop();
  return parts.join("/");
}

async function newFolder() {
  const parent_path = selectedParentPath();
  const folder_name = prompt("新文件夹名称");
  if (!folder_name) return;
  const created = await api("/raw/folder", { method: "POST", body: JSON.stringify({ parent_path, folder_name }) });
  await loadTree();
  revealPath(created.path);
  selectPath(created.path, "folder", sectionForPath(created.path));
}

async function newTxt() {
  const parent_path = selectedParentPath();
  const file_name = prompt("新 TXT 文件名");
  if (!file_name) return;
  const created = await api("/raw/file", { method: "POST", body: JSON.stringify({ parent_path, file_name, content: "" }) });
  await loadTree();
  revealPath(created.path);
  selectPath(created.path, "file", sectionForPath(created.path));
  openEditor(created.path);
}

async function deleteSelected() {
  if (!state.selectedPath) return setStatus("请先选择要删除的节点。");
  if (!confirm(`确认删除：${state.selectedPath}？`)) return;
  const deletedPath = state.selectedPath;
  await api(`/raw/path?path=${encodeURIComponent(state.selectedPath)}`, { method: "DELETE" });
  state.selectedPath = "";
  state.selectedNodeType = "";
  state.selectedKind = "";
  for (const path of [...state.expanded]) {
    if (path === deletedPath || path.startsWith(`${deletedPath}/`)) {
      state.expanded.delete(path);
    }
  }
  await loadTree();
  renderAll();
  setStatus("已删除。");
}

function expandAll() {
  for (const item of state.searchIndex) {
    const parts = item.path.split("/");
    for (let i = 1; i < parts.length; i += 1) state.expanded.add(parts.slice(0, i).join("/"));
  }
  renderAll();
}

function collapseAll() {
  state.expanded.clear();
  renderAll();
}

async function savePermission() {
  if (!state.role || !state.permission) return;
  const payload = {
    extra_role_paths: state.permission.extra_role_paths || [],
    extra_world_paths: state.permission.extra_world_paths || [],
    region_overrides: state.permission.region_overrides || [],
    allowed_story_paths: state.permission.allowed_story_paths || [],
    allowed_story_premises: state.permission.allowed_story_premises || [],
    allowed_story_segments: state.permission.allowed_story_segments || [],
    notes: state.permission.notes || "",
  };
  await api(`/permissions/${encodeURIComponent(state.role)}`, { method: "POST", body: JSON.stringify(payload) });
  await loadRolePermission();
  setStatus("权限已保存。");
}

async function loadRolePermission() {
  if (!state.role) return;
  state.permission = await api(`/permissions/${encodeURIComponent(state.role)}`);
  renderAll();
}

async function loadRoles() {
  state.roles = await api("/permissions/roles");
  const select = $("#roleSelect");
  select.innerHTML = "";
  for (const role of state.roles) {
    const option = document.createElement("option");
    option.value = role;
    option.textContent = role;
    select.append(option);
  }
  state.role = state.roles[0] || "";
  select.value = state.role;
}

async function loadTree() {
  state.forest = await api("/permissions/tree");
}

async function loadStorySummaries() {
  const data = await api("/permissions/story-summaries");
  state.storySummaries.clear();
  for (const story of data.stories || []) {
    state.storySummaries.set(normalizePath(story.path), story);
    if (story.editor_path) state.storySummaries.set(normalizePath(story.editor_path), story);
  }
}

async function loadRegions() {
  const data = await api("/regions/tree");
  state.regionTree = data.tree;
  state.regionPaths = (data.paths && data.paths.length ? data.paths : collectRegionPaths(data.tree))
    .map(normalizeRegionMappingPath)
    .filter(Boolean);
  buildRegionSuggestions();
}

async function loadMappings() {
  state.mappings = await api("/org-mapping");
  renderMappings();
}

function renderAll() {
  renderTrees();
  renderSummaryPreview();
  renderRegionTree();
  renderSelection();
}

function bindEvents() {
  $("#roleSelect").addEventListener("change", async (event) => {
    state.role = event.target.value;
    await loadRolePermission();
  });
  $("#saveBtn").addEventListener("click", savePermission);
  $("#saveMappingBtn").addEventListener("click", saveMapping);
  $("#regionInput").addEventListener("input", () => {
    state.selectedRegionPath = "";
    renderRegionSuggestions();
  });
  $("#regionInput").addEventListener("focus", renderRegionSuggestions);
  document.addEventListener("mousedown", (event) => {
    if (!event.target.closest(".region-autocomplete")) hideRegionSuggestions();
  });
  $("#expandAllBtn").addEventListener("click", expandAll);
  $("#collapseAllBtn").addEventListener("click", collapseAll);
  $("#newFolderBtn").addEventListener("click", newFolder);
  $("#newTxtBtn").addEventListener("click", newTxt);
  $("#openEditorBtn").addEventListener("click", () => openEditor());
  $("#deleteBtn").addEventListener("click", deleteSelected);
  $("#searchBtn").addEventListener("click", searchCurrent);
  $("#searchInput").addEventListener("keydown", (event) => { if (event.key === "Enter") searchCurrent(); });
}

async function boot() {
  try {
    bindEvents();
    await Promise.all([loadRoles(), loadTree(), loadStorySummaries(), loadRegions(), loadMappings()]);
    await loadRolePermission();
    renderAll();
    setStatus(`已加载：${state.role || "未选择角色"}`);
  } catch (error) {
    console.error(error);
    setStatus(`加载失败：${error.message}`);
  }
}

boot();

