from __future__ import annotations


HTML_PAGE = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>角色权限管理</title>
  <style>
    :root {
      --bg: #f5efe6;
      --panel: #fffdf8;
      --line: #dccfbc;
      --text: #2d261d;
      --muted: #7a6a58;
      --accent: #9e5334;
      --accent-soft: #f2e3d8;
      --forced: #b3aba1;
      --forced-bg: #f3f0ea;
      --shadow: 0 18px 40px rgba(58, 42, 28, 0.08);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      color: var(--text);
      font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(158, 83, 52, 0.12), transparent 28%),
        linear-gradient(160deg, #f7f1e8 0%, #f0ebe2 46%, #ece7de 100%);
    }

    .layout {
      display: grid;
      grid-template-columns: 320px minmax(720px, 1.3fr) minmax(360px, 0.9fr);
      min-height: 100vh;
    }

    .sidebar, .main, .preview {
      padding: 20px;
    }

    .sidebar {
      border-right: 1px solid var(--line);
      background: rgba(255, 253, 248, 0.92);
      backdrop-filter: blur(6px);
    }

    .preview {
      border-left: 1px solid var(--line);
      background: rgba(255, 253, 248, 0.82);
      backdrop-filter: blur(6px);
    }

    .card {
      margin-bottom: 16px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    h1, h2, h3 {
      margin: 0 0 12px;
    }

    h1 { font-size: 24px; }
    h2 { font-size: 18px; }
    h3 { font-size: 15px; }

    .muted {
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }

    select, input, textarea, button {
      width: 100%;
      padding: 10px 12px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: white;
      color: var(--text);
      font: inherit;
    }

    button {
      border: none;
      cursor: pointer;
      font-weight: 600;
      background: var(--accent);
      color: white;
    }

    button.secondary {
      background: #eadccc;
      color: var(--text);
    }

    button.ghost {
      width: auto;
      padding: 6px 10px;
      background: transparent;
      border: 1px solid var(--line);
      color: var(--muted);
    }

    .button-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .toolbar {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }

    .toolbar button {
      width: auto;
      padding: 8px 12px;
    }

    .toolbar .ghost {
      background: white;
    }

    .status {
      padding: 10px 12px;
      border-radius: 12px;
      background: var(--accent-soft);
      color: var(--text);
      font-size: 13px;
      white-space: pre-wrap;
    }

    .pill {
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      border: 1px solid #ebdecb;
      background: #f5ecdf;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 12px;
    }

    .tree {
      font-size: 14px;
      line-height: 1.45;
    }

    .tree details {
      margin-left: 14px;
      padding-left: 10px;
      border-left: 1px dashed rgba(111, 84, 52, 0.25);
    }

    .tree > details {
      margin-left: 0;
      padding-left: 0;
      border-left: none;
    }

    .tree summary {
      list-style: none;
      cursor: pointer;
      user-select: none;
      margin: 4px 0;
    }

    .tree summary::-webkit-details-marker {
      display: none;
    }

    .row {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 2px 0;
    }

    .file-row {
      padding-left: 23px;
    }

    .expander {
      width: 14px;
      display: inline-flex;
      justify-content: center;
      color: var(--muted);
      font-size: 12px;
    }

    .node-name.folder {
      font-weight: 700;
      color: #6f5434;
    }

    .file-button {
      width: auto;
      padding: 0;
      border: none;
      background: transparent;
      color: #2f5d7a;
      text-align: left;
      cursor: pointer;
      font-weight: 500;
    }

    .file-button:hover {
      text-decoration: underline;
    }

    input[type=checkbox] {
      width: 15px;
      height: 15px;
      accent-color: var(--accent);
    }

    input[type=checkbox][disabled] {
      cursor: not-allowed;
      opacity: 0.55;
      filter: grayscale(1);
    }

    .forced {
      color: var(--forced);
    }

    .forced .node-name,
    .forced .file-button,
    .forced .expander {
      color: var(--forced);
    }

    .forced-badge {
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid #d7d0c6;
      background: var(--forced-bg);
      color: #6d6760;
      font-size: 11px;
      margin-left: 6px;
    }

    .section {
      margin-bottom: 20px;
    }

    .selected-row {
      background: #f7efe2;
      border-radius: 8px;
    }

    .stack {
      display: grid;
      gap: 8px;
    }

    .mini-list {
      display: flex;
      flex-direction: column;
      gap: 8px;
      max-height: 280px;
      overflow: auto;
      padding-right: 4px;
    }

    .mapping-item {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      align-items: start;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fffaf2;
    }

    .mapping-item strong {
      display: block;
      margin-bottom: 2px;
    }

    .mapping-item button {
      width: auto;
      padding: 6px 10px;
      font-size: 12px;
    }

    .preview-pane {
      display: none;
    }

    .preview-pane.open {
      display: block;
    }

    .preview-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }

    .preview-path {
      min-width: 0;
      word-break: break-all;
    }

    .preview-body {
      max-height: 300px;
      overflow: auto;
      border-radius: 12px;
      background: #fbf8f2;
      border: 1px solid #eee1cf;
      padding: 12px;
      font-size: 12px;
      line-height: 1.6;
      white-space: pre-wrap;
      word-break: break-word;
    }

    pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.55;
      overflow: auto;
    }

    @media (max-width: 1200px) {
      .layout {
        grid-template-columns: 1fr;
      }

      .sidebar {
        border-right: none;
        border-bottom: 1px solid var(--line);
      }

      .preview {
        border-left: none;
        border-top: 1px solid var(--line);
      }
    }
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="card">
        <h1>权限管理</h1>
        <p class="muted">角色固有知识会显示为灰色强制勾选。文案只需要维护额外权限，不需要接触代码。</p>
      </div>

      <div class="card">
        <h2>角色</h2>
        <select id="roleSelect"></select>
      </div>

      <div class="card">
        <h2>势力地区映射</h2>
        <p class="muted">维护“所属势力 -> 地区层级”的映射，影响角色默认地区权限。</p>
        <div class="stack">
          <input id="orgNameInput" type="text" placeholder="势力名，例如：星炬学院" />
          <input id="orgRegionInput" type="text" placeholder="地区路径，例如：黎那汐塔/拉古那" />
          <button id="saveOrgMappingBtn" class="secondary">保存映射</button>
        </div>
        <div id="orgMappingList" class="mini-list" style="margin-top: 12px;"></div>
      </div>

      <div class="card">
        <button id="saveBtn">保存权限</button>
      </div>

      <div class="card">
        <div id="status" class="status">准备就绪。</div>
      </div>
    </aside>

    <main class="main">
      <div class="card">
        <h2>权限树</h2>
        <p class="muted">子层部分勾选时父层显示“-”；全部勾选时显示“√”；全未勾选时显示空白。勾选父层会自动勾选所有子层。</p>
        <div id="currentRoleBadge" class="pill">当前显示：未加载</div>
        <div id="selectedPathBadge" class="pill">当前选中：未选择节点</div>
        <div class="toolbar">
          <button id="expandAllBtn" class="secondary">全部展开</button>
          <button id="collapseAllBtn" class="secondary">全部收起</button>
          <button id="newFolderBtn" class="ghost">新建文件夹</button>
          <button id="newFileBtn" class="ghost">新建 TXT</button>
          <button id="openNotepadBtn" class="ghost">编辑器打开</button>
          <button id="deleteNodeBtn" class="ghost">删除</button>
        </div>
        <div id="treeRoot" class="tree"></div>
      </div>

      <div class="card">
        <h2>当前配置预览</h2>
        <pre id="preview"></pre>
      </div>
    </main>

    <aside class="preview">
      <div class="card">
        <div class="preview-head">
          <div>
            <h2 style="margin-bottom: 4px;">TXT 预览</h2>
            <div id="filePath" class="muted">尚未选择文件</div>
          </div>
          <button id="closePreviewBtn" class="ghost">关闭</button>
        </div>
        <div id="filePreviewPane" class="preview-pane">
          <div id="filePreview" class="preview-body"></div>
        </div>
        <div id="emptyPreview" class="muted">点击权限树中的 TXT 文件即可查看原文，只读不可编辑。</div>
      </div>

      <div class="card">
        <h2>地区关系树</h2>
        <p class="muted">这里只展示地区层级本身，不展示地区说明 TXT 或“地区探索报告”等非地区节点。</p>
        <div id="regionTreeRoot" class="tree" style="max-height: 520px; overflow: auto; padding-right: 4px;"></div>
      </div>
    </aside>
  </div>

  <script>
    const state = {
      currentRole: "",
      treeSections: null,
      regionTree: null,
      permission: null,
      manualFiles: { role: new Set(), world: new Set(), story: new Set() },
      forcedFiles: { role: new Set(), world: new Set(), story: new Set() },
      forcedSpecs: { role: [], world: [], story: [] },
      folderNodes: [],
      fileNodes: [],
      roleRequestToken: 0,
      selectedNode: null,
    };

    function setStatus(message) {
      document.getElementById("status").textContent = message;
    }

    function sleep(ms) {
      return new Promise(resolve => window.setTimeout(resolve, ms));
    }

    function setSelectedNode(node) {
      state.selectedNode = node;
      document.getElementById("selectedPathBadge").textContent = node
        ? `当前选中：${node.path}`
        : "当前选中：未选择节点";

      const allRows = document.querySelectorAll("#treeRoot .row");
      allRows.forEach(row => row.classList.remove("selected-row"));
      if (node?.row) {
        node.row.classList.add("selected-row");
      }
    }

    function escapeHtml(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function normalizeSpec(spec) {
      if (typeof spec === "string") {
        if (spec.endsWith("/**")) return { path: spec.slice(0, -3), mode: "recursive" };
        if (spec.endsWith("/*")) return { path: spec.slice(0, -2), mode: "direct_children_txt" };
        if (spec.endsWith(".txt")) return { path: spec, mode: "exact" };
        return { path: spec, mode: "recursive" };
      }
      return { path: spec?.path || "", mode: spec?.mode || "exact" };
    }

    function normalizeSpecs(specs) {
      return (specs || []).map(normalizeSpec).filter(spec => spec.path);
    }

    function findNodeByPath(node, path) {
      if (!node) return null;
      if (node.path === path) return node;
      if (node.node_type === "file") return null;
      for (const child of (node.children || [])) {
        const found = findNodeByPath(child, path);
        if (found) return found;
      }
      return null;
    }

    function gatherFilePaths(node) {
      if (!node) return [];
      if (node.node_type === "file") return [node.path];
      let files = [];
      for (const child of (node.children || [])) {
        files = files.concat(gatherFilePaths(child));
      }
      return files;
    }

    function gatherDirectTxtChildren(node) {
      if (!node || node.node_type === "file") return [];
      return (node.children || [])
        .filter(child => child.node_type === "file" && child.path.endsWith(".txt"))
        .map(child => child.path);
    }

    function fillSetFromSpecs(targetSet, specs, tree) {
      for (const spec of normalizeSpecs(specs)) {
        if (spec.mode === "exact" && spec.path.endsWith(".txt")) {
          targetSet.add(spec.path);
          continue;
        }
        const matchedNode = findNodeByPath(tree, spec.path);
        if (!matchedNode) continue;
        if (spec.mode === "recursive") {
          gatherFilePaths(matchedNode).forEach(path => targetSet.add(path));
        } else if (spec.mode === "direct_children_txt") {
          gatherDirectTxtChildren(matchedNode).forEach(path => targetSet.add(path));
        }
      }
    }

    function isFileForced(scope, path) {
      return state.forcedFiles[scope].has(path);
    }

    function isFileSelected(scope, path) {
      return isFileForced(scope, path) || state.manualFiles[scope].has(path);
    }

    function isFolderForcedBySpec(scope, path) {
      return normalizeSpecs(state.forcedSpecs[scope]).some(spec => {
        return spec.mode !== "exact" && spec.path === path;
      });
    }

    function setFileSelected(scope, path, selected) {
      if (isFileForced(scope, path)) return;
      if (selected) state.manualFiles[scope].add(path);
      else state.manualFiles[scope].delete(path);
    }

    function setSubtreeSelected(scope, node, selected) {
      gatherFilePaths(node).forEach(path => setFileSelected(scope, path, selected));
    }

    function computeNodeState(scope, node) {
      if (node.node_type === "file") {
        const forced = isFileForced(scope, node.path);
        return {
          checked: isFileSelected(scope, node.path),
          indeterminate: false,
          disabled: forced,
          forced,
        };
      }

      const filePaths = gatherFilePaths(node);
      if (!filePaths.length) {
        return { checked: false, indeterminate: false, disabled: false, forced: false };
      }

      const checkedCount = filePaths.filter(path => isFileSelected(scope, path)).length;
      const forcedCount = filePaths.filter(path => isFileForced(scope, path)).length;
      const allChecked = checkedCount === filePaths.length;
      const someChecked = checkedCount > 0;
      const forcedBySpec = isFolderForcedBySpec(scope, node.path);
      const allForced = forcedBySpec || forcedCount === filePaths.length;

      return {
        checked: forcedBySpec || allChecked,
        indeterminate: !forcedBySpec && someChecked && !allChecked,
        disabled: allForced,
        forced: allForced,
      };
    }

    function refreshTreeStates() {
      state.fileNodes.forEach(item => {
        const forced = isFileForced(item.scope, item.path);
        item.checkbox.checked = isFileSelected(item.scope, item.path);
        item.checkbox.disabled = forced;
        item.row.classList.toggle("forced", forced);
      });

      state.folderNodes.forEach(item => {
        const nodeState = computeNodeState(item.scope, item.node);
        item.checkbox.checked = nodeState.checked;
        item.checkbox.indeterminate = nodeState.indeterminate;
        item.checkbox.disabled = nodeState.disabled;
        item.row.classList.toggle("forced", nodeState.forced);
      });
    }

    function serializeSelectedFiles(scope) {
      const rootNode = scope === "role"
        ? state.treeSections.role.tree
        : scope === "world"
          ? state.treeSections.world.tree
          : {
              path: "",
              node_type: "folder",
              children: [state.treeSections.story_main.tree, state.treeSections.story_side.tree],
            };

      const manualSelected = state.manualFiles[scope];
      const specs = [];

      function walk(node) {
        if (node.node_type === "file") {
          return {
            total: 1,
            selected: manualSelected.has(node.path) ? 1 : 0,
          };
        }

        let total = 0;
        let selected = 0;
        for (const child of (node.children || [])) {
          const result = walk(child);
          total += result.total;
          selected += result.selected;
        }

        if (node.path && total > 0 && selected === total) {
          specs.push(`${node.path}/**`);
          return { total, selected: 0 };
        }

        if (node.path) {
          const directTxt = gatherDirectTxtChildren(node);
          if (directTxt.length > 0 && directTxt.every(path => manualSelected.has(path))) {
            specs.push(`${node.path}/*`);
            selected -= directTxt.length;
          }
        }

        return { total, selected };
      }

      walk(rootNode);

      for (const path of manualSelected) {
        const covered = specs.some(specText => {
          const spec = normalizeSpec(specText);
          if (spec.mode === "recursive") return path.startsWith(spec.path + "/");
          if (spec.mode === "direct_children_txt") {
            const parent = path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
            return parent === spec.path;
          }
          return spec.path === path;
        });
        if (!covered) specs.push(path);
      }

      return Array.from(new Set(specs)).sort();
    }

    function updatePreview() {
      const payload = {
        role_name: state.currentRole,
        extra_role_paths: serializeSelectedFiles("role"),
        extra_world_paths: serializeSelectedFiles("world"),
        region_overrides: [],
        allowed_story_paths: serializeSelectedFiles("story"),
        notes: "",
      };
      document.getElementById("preview").textContent = JSON.stringify(payload, null, 2);
    }

    function openPreview(path, content) {
      document.getElementById("filePath").textContent = path;
      document.getElementById("filePreview").textContent = content;
      document.getElementById("filePreviewPane").classList.add("open");
      document.getElementById("emptyPreview").style.display = "none";
    }

    function closePreview() {
      document.getElementById("filePath").textContent = "尚未选择文件";
      document.getElementById("filePreview").textContent = "";
      document.getElementById("filePreviewPane").classList.remove("open");
      document.getElementById("emptyPreview").style.display = "block";
    }

    async function previewFile(path) {
      const resp = await fetch(`/permissions/file?path=${encodeURIComponent(path)}`, { cache: "no-store" });
      if (!resp.ok) {
        setStatus(`打开 TXT 预览失败：${path}`);
        return;
      }
      const payload = await resp.json();
      openPreview(payload.path, payload.content);
    }

    function createFileNode(node, scope) {
      const row = document.createElement("div");
      row.className = "row file-row";
      row.addEventListener("click", () => {
        setSelectedNode({ path: node.path, nodeType: "file", row });
      });

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.addEventListener("click", event => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        setFileSelected(scope, node.path, checkbox.checked);
        refreshTreeStates();
        updatePreview();
      });

      const label = document.createElement("button");
      label.type = "button";
      label.className = "file-button";
      label.textContent = node.name;
      label.addEventListener("click", event => {
        event.stopPropagation();
        setSelectedNode({ path: node.path, nodeType: "file", row });
        previewFile(node.path);
      });

      row.appendChild(checkbox);
      row.appendChild(label);
      state.fileNodes.push({ scope, path: node.path, checkbox, row });
      return row;
    }

    function createFolderNode(node, scope) {
      const details = document.createElement("details");
      details.open = (node.path || "").split("/").length < 2;

      const summary = document.createElement("summary");
      const row = document.createElement("div");
      row.className = "row";
      row.addEventListener("click", event => {
        event.stopPropagation();
        setSelectedNode({ path: node.path, nodeType: "folder", row });
      });

      const expander = document.createElement("span");
      expander.className = "expander";
      expander.textContent = details.open ? "▼" : "▶";
      row.appendChild(expander);

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.addEventListener("click", event => event.stopPropagation());
      checkbox.addEventListener("change", () => {
        const shouldSelect = checkbox.indeterminate ? true : checkbox.checked;
        setSubtreeSelected(scope, node, shouldSelect);
        refreshTreeStates();
        updatePreview();
      });
      row.appendChild(checkbox);

      const title = document.createElement("span");
      title.className = "node-name folder";
      title.textContent = node.name;
      row.appendChild(title);

      summary.appendChild(row);
      details.appendChild(summary);
      for (const child of (node.children || [])) {
        details.appendChild(renderNode(child, scope));
      }

      details.addEventListener("toggle", () => {
        expander.textContent = details.open ? "▼" : "▶";
      });

      state.folderNodes.push({ scope, node, checkbox, row });
      return details;
    }

    function renderNode(node, scope) {
      if (node.node_type === "file") return createFileNode(node, scope);
      return createFolderNode(node, scope);
    }

    function renderRegionNode(node) {
      const details = document.createElement("details");
      details.open = (node.path || "").split("/").length < 3;

      const summary = document.createElement("summary");
      const row = document.createElement("div");
      row.className = "row";

      const expander = document.createElement("span");
      expander.className = "expander";
      expander.textContent = details.open ? "▼" : "▶";
      row.appendChild(expander);

      const title = document.createElement("span");
      title.className = "node-name folder";
      title.textContent = node.name;
      row.appendChild(title);

      summary.appendChild(row);
      details.appendChild(summary);
      for (const child of (node.children || [])) {
        details.appendChild(renderRegionNode(child));
      }

      details.addEventListener("toggle", () => {
        expander.textContent = details.open ? "▼" : "▶";
      });

      return details;
    }

    function renderPermissionTree() {
      const root = document.getElementById("treeRoot");
      root.innerHTML = "";
      state.folderNodes = [];
      state.fileNodes = [];
      setSelectedNode(null);

      const sections = [
        ["角色额外权限", state.treeSections.role.tree, "role"],
        ["世界观额外权限", state.treeSections.world.tree, "world"],
        ["主线权限", state.treeSections.story_main.tree, "story"],
        ["支线权限", state.treeSections.story_side.tree, "story"],
      ];

      for (const [title, tree, scope] of sections) {
        const section = document.createElement("div");
        section.className = "section";

        const header = document.createElement("h3");
        header.textContent = title;
        section.appendChild(header);
        section.appendChild(renderNode(tree, scope));
        root.appendChild(section);
      }

      refreshTreeStates();
    }

    function showLoadingRole(roleName) {
      document.getElementById("currentRoleBadge").textContent = `当前显示：${roleName}`;
      document.getElementById("treeRoot").innerHTML = `<div class="muted">正在加载 ${roleName} 的权限树...</div>`;
      updatePreview();
    }

    async function loadRoles() {
      const resp = await fetch("/permissions/roles", { cache: "no-store" });
      const roles = await resp.json();
      const select = document.getElementById("roleSelect");
      select.innerHTML = "";
      roles.forEach(role => {
        const option = document.createElement("option");
        option.value = role;
        option.textContent = role;
        select.appendChild(option);
      });
      state.currentRole = roles[0] || "";
      select.value = state.currentRole;
    }

    async function loadPermissionForest() {
      const resp = await fetch("/permissions/tree", { cache: "no-store" });
      const tree = await resp.json();
      state.treeSections = {
        role: { title: "角色额外权限", tree: tree["角色"] },
        world: { title: "世界观额外权限", tree: tree["世界观"] },
        story_main: { title: "主线权限", tree: tree["主线"] },
        story_side: { title: "支线权限", tree: tree["支线"] },
      };
    }

    async function loadRegionTree() {
      const resp = await fetch("/regions/tree", { cache: "no-store" });
      const payload = await resp.json();
      state.regionTree = payload.tree;
      const root = document.getElementById("regionTreeRoot");
      root.innerHTML = "";
      root.appendChild(renderRegionNode(state.regionTree));
    }

    async function loadOrgMapping() {
      const resp = await fetch("/org-mapping", { cache: "no-store" });
      const mapping = await resp.json();
      const root = document.getElementById("orgMappingList");
      root.innerHTML = "";
      const entries = Object.entries(mapping).sort((a, b) => a[0].localeCompare(b[0], "zh-CN"));
      if (!entries.length) {
        root.innerHTML = '<div class="muted">当前没有映射。</div>';
        return;
      }

      entries.forEach(([org, region]) => {
        const item = document.createElement("div");
        item.className = "mapping-item";

        const text = document.createElement("div");
        text.innerHTML = `<strong>${escapeHtml(org)}</strong><span class="muted">${escapeHtml(region)}</span>`;

        const removeBtn = document.createElement("button");
        removeBtn.type = "button";
        removeBtn.className = "secondary";
        removeBtn.textContent = "删除";
        removeBtn.addEventListener("click", async () => {
          const resp = await fetch(`/org-mapping/${encodeURIComponent(org)}`, { method: "DELETE" });
          if (!resp.ok) {
            setStatus(`删除映射失败：${org}`);
            return;
          }
          setStatus(`已删除映射：${org}`);
          await loadOrgMapping();
        });

        item.appendChild(text);
        item.appendChild(removeBtn);
        root.appendChild(item);
      });
    }

    async function loadPermission(roleName) {
      if (!state.treeSections) {
        throw new Error("权限树尚未初始化");
      }

      const token = ++state.roleRequestToken;
      state.currentRole = roleName;
      showLoadingRole(roleName);

      const resp = await fetch(`/permissions/${encodeURIComponent(roleName)}?t=${Date.now()}`, { cache: "no-store" });
      if (!resp.ok) {
        throw new Error(`角色权限接口返回 ${resp.status}`);
      }

      const permission = await resp.json();
      if (token !== state.roleRequestToken) return;

      state.permission = permission;
      state.manualFiles = { role: new Set(), world: new Set(), story: new Set() };
      state.forcedFiles = { role: new Set(), world: new Set(), story: new Set() };
      state.forcedSpecs = {
        role: normalizeSpecs(permission.forced_role_paths || []),
        world: normalizeSpecs(permission.forced_world_paths || []),
        story: normalizeSpecs(permission.forced_story_paths || []),
      };

      fillSetFromSpecs(state.forcedFiles.role, permission.forced_role_paths || [], state.treeSections.role.tree);
      fillSetFromSpecs(state.forcedFiles.world, permission.forced_world_paths || [], state.treeSections.world.tree);
      fillSetFromSpecs(state.forcedFiles.story, permission.forced_story_paths || [], state.treeSections.story_main.tree);
      fillSetFromSpecs(state.manualFiles.role, permission.extra_role_paths || [], state.treeSections.role.tree);
      fillSetFromSpecs(state.manualFiles.world, permission.extra_world_paths || [], state.treeSections.world.tree);
      fillSetFromSpecs(state.manualFiles.story, permission.allowed_story_paths || [], state.treeSections.story_main.tree);
      fillSetFromSpecs(state.manualFiles.story, permission.allowed_story_paths || [], state.treeSections.story_side.tree);

      renderPermissionTree();
      updatePreview();
      document.getElementById("currentRoleBadge").textContent = `当前显示：${roleName}`;
      setStatus(`已加载 ${roleName} 的权限配置。`);
    }

    async function handleRoleSelection(roleName) {
      try {
        await loadPermission(roleName);
      } catch (error) {
        setStatus(`切换角色失败：${error.message || error}`);
        console.error(error);
      }
    }

    async function savePermission() {
      const payload = {
        extra_role_paths: serializeSelectedFiles("role"),
        extra_world_paths: serializeSelectedFiles("world"),
        region_overrides: [],
        allowed_story_paths: serializeSelectedFiles("story"),
        notes: "",
      };

      updatePreview();
      setStatus(`正在保存 ${state.currentRole} 的权限...`);

      const resp = await fetch(`/permissions/${encodeURIComponent(state.currentRole)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        setStatus(`保存失败：接口返回 ${resp.status}`);
        return;
      }

      const result = await resp.json();
      setStatus(`保存成功：${result.path}`);
      await loadPermission(state.currentRole);
    }

    async function saveOrgMapping() {
      const organization = document.getElementById("orgNameInput").value.trim();
      const regionPath = document.getElementById("orgRegionInput").value.trim();
      if (!organization || !regionPath) {
        setStatus("请先填写势力名和地区路径。");
        return;
      }

      const resp = await fetch("/org-mapping", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ organization, region_path: regionPath }),
      });

      if (!resp.ok) {
        setStatus(`保存映射失败：${organization}`);
        return;
      }

      document.getElementById("orgNameInput").value = "";
      document.getElementById("orgRegionInput").value = "";
      setStatus(`已保存映射：${organization} -> ${regionPath}`);
      await loadOrgMapping();
    }

    function getSelectedParentPath() {
      if (!state.selectedNode) return null;
      if (state.selectedNode.nodeType === "folder") return state.selectedNode.path;
      const path = state.selectedNode.path;
      return path.includes("/") ? path.slice(0, path.lastIndexOf("/")) : "";
    }

    async function refreshTreesAfterContentChange() {
      let lastError = null;
      for (let attempt = 1; attempt <= 8; attempt += 1) {
        try {
          await loadPermissionForest();
          await loadRegionTree();
          if (state.currentRole) {
            await loadPermission(state.currentRole);
          }
          return;
        } catch (error) {
          lastError = error;
          await sleep(500);
        }
      }
      throw lastError || new Error("刷新权限树失败");
    }

    async function createFolderFromSelection() {
      const parentPath = getSelectedParentPath();
      if (!parentPath) {
        setStatus("请先在权限树中选中一个父文件夹。");
        return;
      }
      const folderName = window.prompt("请输入新文件夹名称：");
      if (!folderName) return;
      const resp = await fetch("/raw/folder", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parent_path: parentPath, folder_name: folderName }),
      });
      if (!resp.ok) {
        setStatus(`新建文件夹失败：${folderName}`);
        return;
      }
      const result = await resp.json();
      setStatus(`已创建文件夹：${result.path}`);
      try {
        await refreshTreesAfterContentChange();
      } catch (error) {
        setStatus(`文件夹已创建，但自动刷新失败，请稍后再试：${error.message || error}`);
      }
    }

    async function createTxtFromSelection() {
      const parentPath = getSelectedParentPath();
      if (!parentPath) {
        setStatus("请先在权限树中选中一个父文件夹。");
        return;
      }
      const fileName = window.prompt("请输入新 TXT 文件名：");
      if (!fileName) return;
      const resp = await fetch("/raw/file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parent_path: parentPath, file_name: fileName, content: "" }),
      });
      if (!resp.ok) {
        setStatus(`新建 TXT 失败：${fileName}`);
        return;
      }
      const result = await resp.json();
      setStatus(`已创建文件：${result.path}`);
      try {
        await refreshTreesAfterContentChange();
      } catch (error) {
        setStatus(`文件已创建，但自动刷新失败，请稍后再试：${error.message || error}`);
      }
    }

    async function deleteSelectedNode() {
      if (!state.selectedNode?.path) {
        setStatus("请先选中要删除的文件或空文件夹。");
        return;
      }
      const targetPath = state.selectedNode.path;
      const confirmed = window.confirm(`确认删除：${targetPath} ？`);
      if (!confirmed) return;
      const resp = await fetch(`/raw/path?path=${encodeURIComponent(targetPath)}`, {
        method: "DELETE",
      });
      if (!resp.ok) {
        setStatus(`删除失败：${targetPath}。目录必须为空。`);
        return;
      }
      setSelectedNode(null);
      closePreview();
      setStatus(`已删除：${targetPath}`);
      try {
        await refreshTreesAfterContentChange();
      } catch (error) {
        setStatus(`已删除，但自动刷新失败，请稍后再试：${error.message || error}`);
      }
    }

    async function openSelectedInNotepad() {
      if (!state.selectedNode?.path || state.selectedNode.nodeType !== "file" || !state.selectedNode.path.endsWith(".txt")) {
        setStatus("请先选中一个 TXT 文件。");
        return;
      }
      window.open(`/editor?path=${encodeURIComponent(state.selectedNode.path)}`, "_blank");
      setStatus(`已用编辑器打开：${state.selectedNode.path}`);
    }

    function setAllFolders(open) {
      document.querySelectorAll("#treeRoot details").forEach(node => {
        node.open = open;
      });
    }

    async function bootstrap() {
      document.getElementById("closePreviewBtn").addEventListener("click", closePreview);
      document.getElementById("saveBtn").addEventListener("click", savePermission);
      document.getElementById("saveOrgMappingBtn").addEventListener("click", saveOrgMapping);
      document.getElementById("expandAllBtn").addEventListener("click", () => setAllFolders(true));
      document.getElementById("collapseAllBtn").addEventListener("click", () => setAllFolders(false));
      document.getElementById("newFolderBtn").addEventListener("click", createFolderFromSelection);
      document.getElementById("newFileBtn").addEventListener("click", createTxtFromSelection);
      document.getElementById("openNotepadBtn").addEventListener("click", openSelectedInNotepad);
      document.getElementById("deleteNodeBtn").addEventListener("click", deleteSelectedNode);

      await loadRoles();
      await loadPermissionForest();
      await loadOrgMapping();
      await loadRegionTree();

      const roleSelect = document.getElementById("roleSelect");
      roleSelect.addEventListener("change", event => {
        handleRoleSelection(event.target.value);
      });

      if (state.currentRole) {
        await handleRoleSelection(state.currentRole);
      } else {
        updatePreview();
      }
    }

    bootstrap().catch(error => {
      setStatus(`页面初始化失败：${error.message || error}`);
      console.error(error);
    });
  </script>
</body>
</html>
"""

