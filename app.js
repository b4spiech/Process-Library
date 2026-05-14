// Business Process Repository — frontend
// Talks to the FastAPI backend at the same origin.

const API_BASE = (() => {
  const params = new URLSearchParams(location.search);
  if (params.get("api")) return params.get("api").replace(/\/$/, "");
  return location.origin;
})();

const state = {
  tree: [],
  byId: new Map(),
  // null = root mode (all L1 tiles in grid); otherwise = branch mode focused
  // on this node id (shows header tile + its immediate children stacked).
  currentNodeId: null,
  treeSelectedId: null,
  treeCollapsed: new Set(),     // collapsed nodes in left tree
  docsByNode: new Map(),        // node_id -> LibraryDocument[]  (linked docs only)
  kpisByNode: new Map(),        // node_id -> Kpi[]
  entriesByKpi: new Map(),      // kpi_id  -> KpiEntry[]
  topicsByNode: new Map(),      // node_id -> SustainabilityTopic[]

  viewMode: "tiles",            // "tiles" | "library"
  libraryDocs: [],              // last fetched library result set
  libraryFilter: { doc_type: "", search: "", tags: [] },

  allTopics: null,              // full topic catalog (lazy-loaded once)
};

const LEVEL_NAMES = {
  1: "L1 · Business Domain",
  2: "L2 · Function",
  3: "L3 · Process Group",
  4: "L4 · Terminal Process",
};

const DOC_TYPE_LABELS = {
  procedure: "Procedure",
  work_instruction: "Work Instruction",
  form: "Form",
  certificate: "Certificate",
  policy: "Policy",
  reference: "Reference",
  ci_event: "CI Event",
  audit_report: "Audit Report",
  training_record: "Training Record",
};

const DOC_TYPE_ICON = {
  procedure: "P",
  work_instruction: "WI",
  form: "F",
  certificate: "C",
  policy: "PL",
  reference: "R",
  ci_event: "CI",
  audit_report: "AR",
  training_record: "TR",
};

const PREDEFINED_TAGS = [
  "CI Event", "Certificate", "Audit", "SOP",
  "Training", "Policy", "Work Instruction", "Form",
];

const TYPES_REQUIRING_OWNER_FREQ = new Set(["procedure", "work_instruction"]);

// ---------- API ----------

async function api(path, opts = {}) {
  const headers = opts.body && !(opts.body instanceof FormData)
    ? { "Content-Type": "application/json", ...(opts.headers || {}) }
    : (opts.headers || {});
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = res.statusText; }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

async function checkHealth() {
  const el = $("health-indicator");
  try {
    const r = await api("/health");
    el.textContent = `API ${r.status}`;
    el.className = "health ok";
  } catch (e) {
    el.textContent = "API offline";
    el.className = "health bad";
  }
}

async function loadTree() {
  state.tree = await api("/nodes");
  state.byId.clear();
  const walk = (n) => {
    state.byId.set(n.id, n);
    (n.children || []).forEach(walk);
  };
  state.tree.forEach(walk);

  // If the currently focused branch was deleted, fall back to root.
  if (state.currentNodeId && !state.byId.has(state.currentNodeId)) {
    state.currentNodeId = null;
  }

  renderTree();
  renderRightPane();
}

// ---------- Navigation ----------

function pathTo(nodeId) {
  // Returns ancestors from root → ... → node (inclusive).
  const out = [];
  let n = state.byId.get(nodeId);
  while (n) {
    out.unshift(n);
    n = n.parent_id ? state.byId.get(n.parent_id) : null;
  }
  return out;
}

function navigate(nodeId) {
  state.currentNodeId = nodeId;
  state.treeSelectedId = nodeId;
  renderTree();
  renderRightPane();
}

function navigateToRoot() {
  state.currentNodeId = null;
  renderTree();
  renderRightPane();
}

function navigateUp() {
  if (!state.currentNodeId) return;
  const node = state.byId.get(state.currentNodeId);
  if (!node) return navigateToRoot();
  if (node.parent_id) navigate(node.parent_id);
  else navigateToRoot();
}

function $(id) { return document.getElementById(id); }

// ---------- Left tree rendering ----------

function renderTree() {
  const container = $("tree");
  container.innerHTML = "";
  if (state.tree.length === 0) {
    container.innerHTML = '<p class="muted" style="padding:16px;">No nodes yet. Click "+ L1 Domain" to create your first Business Domain.</p>';
    return;
  }
  state.tree.forEach((n) => container.appendChild(renderTreeNode(n)));
}

function renderTreeNode(node) {
  const wrap = document.createElement("div");
  wrap.className = "tree-node";
  wrap.dataset.id = node.id;

  const row = document.createElement("div");
  row.className = "tree-row";
  if (node.id === state.treeSelectedId) row.classList.add("selected");
  row.style.paddingLeft = `${8 + (node.level - 1) * 4}px`;

  const hasChildren = node.children && node.children.length > 0;
  const isCollapsed = state.treeCollapsed.has(node.id);

  const toggle = document.createElement("span");
  toggle.className = hasChildren ? "toggle" : "toggle placeholder";
  toggle.textContent = hasChildren ? (isCollapsed ? "▶" : "▼") : "·";
  toggle.onclick = (e) => {
    e.stopPropagation();
    if (!hasChildren) return;
    if (isCollapsed) state.treeCollapsed.delete(node.id);
    else state.treeCollapsed.add(node.id);
    renderTree();
  };

  const dot = document.createElement("span");
  dot.className = `status-dot ${node.status}`;
  dot.title = `status: ${node.status}`;

  const code = document.createElement("span");
  code.className = "row-code";
  code.textContent = node.code;

  const name = document.createElement("span");
  name.className = "row-name";
  name.textContent = node.name;

  const addBtn = document.createElement("button");
  addBtn.className = "row-add";
  addBtn.textContent = "+";
  addBtn.title = node.level < 4 ? "Add child node" : "Cannot add — L4 is terminal";
  addBtn.disabled = node.level >= 4;
  if (node.level >= 4) addBtn.style.visibility = "hidden";
  addBtn.onclick = (e) => {
    e.stopPropagation();
    openAddDialog(node);
  };

  row.append(toggle, dot, code, name, addBtn);
  row.onclick = () => selectTreeNode(node.id);

  wrap.appendChild(row);

  if (hasChildren) {
    const childWrap = document.createElement("div");
    childWrap.className = "children" + (isCollapsed ? " collapsed" : "");
    node.children.forEach((c) => childWrap.appendChild(renderTreeNode(c)));
    wrap.appendChild(childWrap);
  }

  return wrap;
}

function selectTreeNode(id) {
  // Tree click navigates to that node's branch view.
  navigate(id);
}

// ---------- Right pane: breadcrumb + mode-based tile rendering ----------

function renderRightPane() {
  if (state.viewMode === "library") return;  // tile pane is hidden
  renderBreadcrumb();
  renderTiles();
  updateSummary();
}

function updateSummary() {
  const total = state.byId.size;
  const l1Count = state.tree.length;
  $("tile-summary").textContent = `${total} nodes · ${l1Count} L1 domain${l1Count === 1 ? "" : "s"}`;
}

function renderBreadcrumb() {
  const bc = $("breadcrumb");
  bc.innerHTML = "";

  const rootCrumb = document.createElement("span");
  rootCrumb.className = "crumb" + (state.currentNodeId === null ? " current" : "");
  rootCrumb.textContent = "Domains";
  if (state.currentNodeId !== null) rootCrumb.onclick = () => navigateToRoot();
  bc.appendChild(rootCrumb);

  if (state.currentNodeId !== null) {
    const path = pathTo(state.currentNodeId);
    path.forEach((n, i) => {
      const sep = document.createElement("span");
      sep.className = "crumb-sep";
      sep.textContent = "›";
      bc.appendChild(sep);

      const crumb = document.createElement("span");
      const isLast = i === path.length - 1;
      crumb.className = "crumb" + (isLast ? " current" : "");
      crumb.textContent = n.name;
      crumb.title = n.code;
      if (!isLast) crumb.onclick = () => navigate(n.id);
      bc.appendChild(crumb);
    });
  }

  // Back button enabled only when not at root
  $("back-btn").disabled = state.currentNodeId === null;
}

function renderTiles() {
  const root = $("tile-grid");
  root.innerHTML = "";
  if (state.tree.length === 0) {
    root.innerHTML = '<p class="muted">No nodes yet.</p>';
    return;
  }
  if (state.currentNodeId === null) {
    renderRootMode(root);
  } else {
    renderBranchMode(root);
  }
}

// Root mode: L1 tiles in a responsive grid.
function renderRootMode(container) {
  const grid = document.createElement("div");
  grid.className = "tile-grid";
  state.tree.forEach((n) => {
    grid.appendChild(renderTile(n, { variant: "grid" }));
    ensureDocsLoaded(n.id);
    ensureKpisLoaded(n.id);
    ensureTopicsLoaded(n.id);
  });
  container.appendChild(grid);
}

// Branch mode: highlighted parent header tile on its own row, children below in
// the same responsive compact grid as root mode.
function renderBranchMode(container) {
  const node = state.byId.get(state.currentNodeId);
  if (!node) {
    container.innerHTML = '<p class="muted">Node not found.</p>';
    return;
  }
  const view = document.createElement("div");
  view.className = "branch-view";

  const headerRow = document.createElement("div");
  headerRow.className = "branch-header-row";
  headerRow.appendChild(renderTile(node, { variant: "header" }));
  view.appendChild(headerRow);
  ensureDocsLoaded(node.id);
  ensureKpisLoaded(node.id);
  ensureTopicsLoaded(node.id);

  const children = node.children || [];
  if (children.length === 0) {
    const empty = document.createElement("div");
    empty.className = "branch-empty";
    empty.textContent =
      node.level >= 4
        ? "Terminal process (L4) — no further breakdown."
        : "No children yet. Use “+ Add child” in Details to add one.";
    view.appendChild(empty);
  } else {
    const grid = document.createElement("div");
    grid.className = "tile-grid";
    children.forEach((c) => {
      grid.appendChild(renderTile(c, { variant: "grid" }));
      ensureDocsLoaded(c.id);
      ensureKpisLoaded(c.id);
    });
    view.appendChild(grid);
  }

  container.appendChild(view);
}

// `variant` controls minor differences:
//   "grid"   — compact tile in a responsive grid cell (root mode + branch children)
//   "header" — focused parent header tile in branch mode (highlighted, no Expand)
function renderTile(node, { variant }) {
  const wrap = document.createElement("div");
  wrap.className = "tile" + (variant === "header" ? " branch-header-tile" : "");
  wrap.dataset.id = node.id;

  // ---- Top row: status / code / L# / actions ----
  const top = document.createElement("div");
  top.className = "tile-top";

  const dot = document.createElement("span");
  dot.className = `status-dot ${node.status}`;
  dot.title = `status: ${node.status}`;

  const code = document.createElement("span");
  code.className = "row-code";
  code.textContent = node.code;

  const levelMeta = document.createElement("span");
  levelMeta.className = "tile-meta";
  levelMeta.textContent = `L${node.level}`;

  const actions = document.createElement("div");
  actions.className = "tile-actions";

  // "+ Doc" opens a tabbed modal: tab 1 uploads a brand-new file (and
  // auto-links it to this node), tab 2 searches the library and lets the
  // user link an existing document. (The separate Link button is gone.)
  const uploadBtn = document.createElement("button");
  uploadBtn.className = "tile-btn";
  uploadBtn.title = "Upload a new document or link one from the library";
  uploadBtn.innerHTML = `<span class="icon">+</span> Doc`;
  uploadBtn.onclick = (e) => {
    e.stopPropagation();
    openDocDialog(node, null);
  };
  actions.appendChild(uploadBtn);

  // "+ Topic" opens the sustainability-topic link modal for this node.
  const topicBtn = document.createElement("button");
  topicBtn.className = "tile-btn";
  topicBtn.title = "Link an EcoVadis sustainability topic to this node";
  topicBtn.innerHTML = `<span class="icon">🌱</span> Topic`;
  topicBtn.onclick = (e) => {
    e.stopPropagation();
    openTopicDialog(node);
  };
  actions.appendChild(topicBtn);

  if (variant !== "header") {
    const expandBtn = document.createElement("button");
    expandBtn.className = "tile-btn";
    expandBtn.innerHTML = `<span class="icon">▶</span> Expand`;
    expandBtn.title = "Drill into this branch";
    expandBtn.onclick = (e) => {
      e.stopPropagation();
      navigate(node.id);
    };
    actions.appendChild(expandBtn);
  }

  const kpiBtn = document.createElement("button");
  kpiBtn.className = "tile-btn";
  kpiBtn.title = "View / manage KPIs for this node";
  kpiBtn.innerHTML = `<span class="icon">📊</span> KPI`;
  kpiBtn.onclick = (e) => {
    e.stopPropagation();
    openKpiDrawer(node);
  };
  actions.appendChild(kpiBtn);

  const detailsBtn = document.createElement("button");
  detailsBtn.className = "tile-btn";
  detailsBtn.innerHTML = `<span class="icon">i</span> Details`;
  detailsBtn.onclick = (e) => {
    e.stopPropagation();
    openDetailsDialog(node);
  };
  actions.appendChild(detailsBtn);

  top.append(dot, code, levelMeta, actions);
  wrap.appendChild(top);

  const name = document.createElement("div");
  name.className = "tile-name";
  name.textContent = node.name;
  wrap.appendChild(name);

  if (node.owner) {
    const owner = document.createElement("div");
    owner.className = "tile-owner";
    owner.innerHTML = `Owner: <strong></strong>`;
    owner.querySelector("strong").textContent = node.owner;
    wrap.appendChild(owner);
  }

  if (node.kpi_name) {
    const kpi = document.createElement("div");
    kpi.className = "tile-kpi";
    const kname = document.createElement("div");
    kname.className = "kpi-name";
    kname.textContent = `KPI: ${node.kpi_name}`;
    kpi.appendChild(kname);
    if (node.kpi_current || node.kpi_target) {
      const vals = document.createElement("div");
      vals.className = "kpi-vals";
      vals.textContent = `${node.kpi_current || "—"} / ${node.kpi_target || "—"}`;
      kpi.appendChild(vals);
    }
    wrap.appendChild(kpi);
  }

  // Doc-type badges row (hidden when the node has no documents).
  const badges = renderDocBadges(node);
  if (badges) wrap.appendChild(badges);

  // KPI summary indicators (active KPIs only). Hidden when no active KPIs.
  const kpiSummary = renderKpiSummary(node);
  if (kpiSummary) wrap.appendChild(kpiSummary);

  // Sustainability topic pills (theme-colored). Hidden when none linked.
  const topicPills = renderTopicPills(node);
  if (topicPills) wrap.appendChild(topicPills);

  // Clicking the tile body (but not buttons, badges, KPI indicators, or
  // topic pills) drills into the branch — except for the header tile.
  if (variant !== "header") {
    wrap.onclick = (e) => {
      if (e.target.closest("button, .doc-badge, .kpi-indicator, .topic-pill")) return;
      navigate(node.id);
    };
  }

  return wrap;
}

// ---------- Doc-type badges + drawer ----------

const MISC_BUCKET = "_misc";

function groupDocsByType(docs) {
  // Returns Map<type, Document[]> preserving the order in DOC_TYPE_LABELS,
  // with an extra MISC_BUCKET at the end if there are unrecognized types.
  const groups = new Map();
  Object.keys(DOC_TYPE_LABELS).forEach((t) => groups.set(t, []));
  groups.set(MISC_BUCKET, []);

  docs.forEach((d) => {
    const key = DOC_TYPE_LABELS[d.doc_type] ? d.doc_type : MISC_BUCKET;
    groups.get(key).push(d);
  });

  // Drop empty buckets
  for (const [k, arr] of groups) {
    if (arr.length === 0) groups.delete(k);
  }
  return groups;
}

function labelForBucket(bucket) {
  return bucket === MISC_BUCKET ? "Misc" : DOC_TYPE_LABELS[bucket];
}

function renderDocBadges(node) {
  const docs = state.docsByNode.get(node.id);
  // If we haven't loaded docs yet, return null and let ensureDocsLoaded
  // trigger a re-render via renderRightPane when the count is known.
  if (!docs || docs.length === 0) return null;

  const wrap = document.createElement("div");
  wrap.className = "tile-doc-badges";

  const groups = groupDocsByType(docs);
  for (const [bucket, arr] of groups) {
    const badge = document.createElement("span");
    badge.className = `doc-badge dt-${bucket}`;
    badge.title = `Open ${labelForBucket(bucket)} documents`;
    badge.innerHTML = `${labelForBucket(bucket)} <span class="badge-count">${arr.length}</span>`;
    badge.onclick = (e) => {
      e.stopPropagation();
      openDocsDrawer(node, bucket);
    };
    wrap.appendChild(badge);
  }
  return wrap;
}

// ---- Drawer state + rendering ----

let drawerCtx = { nodeId: null, bucket: null };

function openDocsDrawer(node, bucket) {
  // Mutual exclusion: only one side drawer at a time.
  if ($("kpi-drawer").open) closeKpiDrawer();

  drawerCtx = { nodeId: node.id, bucket };
  renderDrawerHeader(node, bucket);
  renderDrawerBody();

  // Non-modal show() so the rest of the page stays interactive — that lets
  // the user click another doc-type badge to update the drawer in place.
  // Calling showModal()/show() on an already-open dialog throws, so we
  // guard on dlg.open and only call once.
  const dlg = $("docs-drawer");
  if (!dlg.open) dlg.show();
}

function renderDrawerHeader(node, bucket) {
  $("drawer-node-name").textContent = `${node.code} — ${node.name}`;

  const headerLabel = $("drawer-doc-type");
  headerLabel.innerHTML = "";
  const chip = document.createElement("span");
  chip.className = `doc-badge dt-${bucket}`;
  chip.style.cursor = "default";
  chip.textContent = labelForBucket(bucket);
  const countEl = document.createElement("span");
  countEl.className = "drawer-count";
  countEl.id = "drawer-count";
  headerLabel.append(chip, countEl);
}

function renderDrawerBody() {
  if (drawerCtx.nodeId === null) return;
  const node = state.byId.get(drawerCtx.nodeId);
  const body = $("drawer-body");
  body.innerHTML = "";

  const docs = state.docsByNode.get(drawerCtx.nodeId) || [];
  const filtered = docs.filter((d) => {
    const key = DOC_TYPE_LABELS[d.doc_type] ? d.doc_type : MISC_BUCKET;
    return key === drawerCtx.bucket;
  });

  $("drawer-count").textContent = `${filtered.length} document${filtered.length === 1 ? "" : "s"}`;

  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "drawer-empty";
    empty.textContent = "No documents of this type remain. Use Upload to add one.";
    body.appendChild(empty);
    return;
  }

  filtered.forEach((d) => body.appendChild(renderDocRow(d, node)));
}

function closeDocsDrawer() {
  drawerCtx = { nodeId: null, bucket: null };
  $("docs-drawer").close();
}

$("drawer-close-btn").addEventListener("click", () => closeDocsDrawer());

// Non-modal dialogs don't get ESC-to-close for free; wire it manually.
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && $("docs-drawer").open) {
    e.preventDefault();
    closeDocsDrawer();
  }
});

$("drawer-upload-btn").addEventListener("click", () => {
  if (drawerCtx.nodeId === null) return;
  const node = state.byId.get(drawerCtx.nodeId);
  // Pre-select the doc type matching this drawer's badge. Misc has no
  // server-side equivalent, so it falls back to the first concrete type.
  const prefill = drawerCtx.bucket === MISC_BUCKET ? null : drawerCtx.bucket;
  openDocDialog(node, null, prefill);
});

// renderDocRow is used in the per-node drawer (when `node` is passed) where
// the rightmost action is "Unlink" — i.e., remove the link to this node;
// the file stays in the library. Library-page rows use a separate renderer.
function renderDocRow(doc, node) {
  const row = document.createElement("div");
  row.className = "doc-row is-linked";

  const icon = document.createElement("div");
  icon.className = "doc-icon";
  icon.textContent = DOC_TYPE_ICON[doc.doc_type] || "?";
  icon.title = DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type;

  const info = document.createElement("div");
  info.className = "doc-info";

  const fname = document.createElement("div");
  fname.className = "doc-filename";
  fname.textContent = doc.original_filename;

  const sub = document.createElement("div");
  sub.className = "doc-sub";
  const parts = [];
  parts.push(DOC_TYPE_LABELS[doc.doc_type] || doc.doc_type);
  if (doc.owner) parts.push(`Owner: ${doc.owner}`);
  if (doc.next_review_date) parts.push(`Next review: ${doc.next_review_date}`);
  if (doc.version) parts.push(`v${doc.version}`);
  sub.textContent = parts.join(" · ");

  info.append(fname, sub);

  if (doc.tags) {
    const tagWrap = document.createElement("div");
    tagWrap.className = "doc-sub";
    doc.tags.split(",").map((t) => t.trim()).filter(Boolean).forEach((t) => {
      const chip = document.createElement("span");
      chip.className = "doc-tag";
      chip.textContent = t;
      tagWrap.appendChild(chip);
    });
    info.appendChild(tagWrap);
  }

  const actions = document.createElement("div");
  actions.className = "doc-actions";

  const view = document.createElement("button");
  view.textContent = "View";
  view.title = "Open in a new tab (no download)";
  view.onclick = (e) => { e.stopPropagation(); viewDoc(doc.id); };

  const dl = document.createElement("button");
  dl.textContent = "Download";
  dl.title = "Download";
  dl.onclick = (e) => { e.stopPropagation(); downloadDoc(doc.id); };

  const edit = document.createElement("button");
  edit.textContent = "Edit";
  edit.title = "Edit metadata (library-wide)";
  edit.onclick = (e) => { e.stopPropagation(); openDocDialog(node, doc); };

  const unlink = document.createElement("button");
  unlink.className = "danger";
  unlink.textContent = "Unlink";
  unlink.title = "Remove the link to this node (document stays in the library)";
  unlink.onclick = (e) => { e.stopPropagation(); unlinkDocFromNode(doc, node.id); };

  actions.append(view, dl, edit, unlink);
  row.append(icon, info, actions);
  return row;
}

async function ensureDocsLoaded(nodeId) {
  if (state.docsByNode.has(nodeId)) return;
  try {
    const docs = await api(`/nodes/${nodeId}/documents`);
    state.docsByNode.set(nodeId, docs);

    // Re-render the badges on the affected tile (and, if open, the drawer).
    rerenderTileBadges(nodeId);
    if (drawerCtx.nodeId === nodeId) renderDrawerBody();
  } catch (err) {
    toast(`Failed to load documents: ${err.message}`, true);
  }
}

function rerenderTileBadges(nodeId) {
  const tile = document.querySelector(`.tile[data-id="${nodeId}"]`);
  if (!tile) return;
  const old = tile.querySelector(".tile-doc-badges");
  if (old) old.remove();
  const node = state.byId.get(nodeId);
  if (!node) return;
  const fresh = renderDocBadges(node);
  if (fresh) tile.appendChild(fresh);
}

async function downloadDoc(docId) {
  try {
    const r = await api(`/library/documents/${docId}/download`);
    window.open(r.url, "_blank", "noopener");
  } catch (err) {
    toast(`Download failed: ${err.message}`, true);
  }
}

async function viewDoc(docId) {
  try {
    const r = await api(`/library/documents/${docId}/view`);
    window.open(r.url, "_blank", "noopener");
  } catch (err) {
    toast(`View failed: ${err.message}`, true);
  }
}

// Removing a doc from the drawer = UNLINK (the library doc stays).
// "Delete from Library" (which actually purges the file) is reachable
// only from the Library page.
async function unlinkDocFromNode(doc, nodeId) {
  if (!confirm(`Unlink "${doc.original_filename}" from this node? The document stays in the library.`)) return;
  try {
    await api(`/nodes/${nodeId}/unlink-document/${doc.id}`, { method: "DELETE" });
    state.docsByNode.delete(nodeId);
    await ensureDocsLoaded(nodeId);
    renderRightPane();
    if (drawerCtx.nodeId === nodeId) renderDrawerBody();
    toast("Unlinked");
  } catch (err) {
    toast(`Unlink failed: ${err.message}`, true);
  }
}

// Hard delete from the library (only invoked from the Library page).
async function deleteLibraryDoc(doc) {
  if (!confirm(`Delete "${doc.original_filename}" from the Library? This removes the file from storage and unlinks it from all nodes. Cannot be undone.`)) return;
  try {
    await api(`/library/documents/${doc.id}`, { method: "DELETE" });
    // Any node that had this linked is now stale.
    state.docsByNode.clear();
    await loadLibrary();
    renderRightPane();
    toast("Document deleted from library");
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
}

// ---------- Document upload / edit dialog ----------

let docContext = { node: null, doc: null };

function openDocDialog(node, doc, prefillType = null) {
  // node === null  →  Library upload (no auto-link)
  // node !== null  →  upload + auto-link to that node
  docContext = { node, doc };
  if (doc) {
    $("doc-title").textContent = `Edit document — ${doc.original_filename}`;
  } else if (node) {
    $("doc-title").textContent = `Upload document to ${node.code} — ${node.name}`;
  } else {
    $("doc-title").textContent = "Upload to Library";
  }

  $("doc-file-wrap").style.display = doc ? "none" : "";
  $("doc-file").value = "";

  $("doc-type").value = doc ? doc.doc_type : (prefillType || "procedure");
  $("doc-version").value = doc ? (doc.version || "") : "";
  $("doc-owner").value = doc ? (doc.owner || "") : "";
  $("doc-review-frequency").value = doc ? (doc.review_frequency || "") : "";
  $("doc-last-review-date").value = doc ? (doc.last_review_date || "") : "";
  $("doc-next-review-date").value = doc ? (doc.next_review_date || "") : "";
  $("doc-tags").value = doc ? (doc.tags || "") : "";
  $("doc-notes").value = doc ? (doc.notes || "") : "";
  $("doc-description").value = doc ? (doc.description || "") : "";

  // Tab visibility: only show the "Link from Library" tab when a brand-new
  // doc is being added to a specific node. Edit mode and library uploads
  // get just the Upload tab.
  const showLinkTab = !doc && !!node;
  setDocDialogTabs(showLinkTab);
  // Reset to the Upload tab whenever the dialog opens.
  switchDocDialogTab("upload");
  // Pre-seed the link-tab context so refreshes work if the user switches tabs.
  linkDialogCtx = { node: node || null };

  renderTagChips($("doc-tags").value);
  updateDocFieldRequirements();
  $("doc-dialog").showModal();
}

function setDocDialogTabs(showLinkTab) {
  const tabsBar = $("doc-modal-tabs");
  tabsBar.hidden = !showLinkTab;
  const linkTabBtn = tabsBar.querySelector('[data-doc-tab="link"]');
  if (linkTabBtn) linkTabBtn.hidden = !showLinkTab;
  // Always hide the link panel until the user clicks the tab; the link
  // tab is only reachable when showLinkTab is true.
  document.querySelector('[data-doc-panel="link"]').hidden = true;
}

function switchDocDialogTab(target) {
  document.querySelectorAll("#doc-dialog .modal-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.docTab === target);
  });
  document.querySelectorAll("#doc-dialog .modal-tab-panel").forEach((p) => {
    p.hidden = p.dataset.docPanel !== target;
  });
  if (target === "link") {
    // Reset filters each time the user switches in for a clean slate.
    $("link-search").value = "";
    $("link-type-filter").value = "";
    refreshLinkDialogBody();
  }
}

document.querySelectorAll("#doc-dialog .modal-tab").forEach((btn) => {
  btn.addEventListener("click", () => switchDocDialogTab(btn.dataset.docTab));
});

function renderTagChips(currentTagsCsv) {
  const container = $("doc-tag-chips");
  container.innerHTML = "";
  const current = new Set(
    (currentTagsCsv || "").split(",").map((t) => t.trim()).filter(Boolean)
  );
  PREDEFINED_TAGS.forEach((tag) => {
    const chip = document.createElement("span");
    chip.className = "tag-chip" + (current.has(tag) ? " active" : "");
    chip.textContent = tag;
    chip.onclick = () => {
      if (current.has(tag)) current.delete(tag);
      else current.add(tag);
      $("doc-tags").value = [...current].join(", ");
      renderTagChips($("doc-tags").value);
    };
    container.appendChild(chip);
  });
}

function updateDocFieldRequirements() {
  const t = $("doc-type").value;
  const isRequired = TYPES_REQUIRING_OWNER_FREQ.has(t);
  $("doc-owner-req").style.display = isRequired ? "" : "none";
  $("doc-freq-req").style.display = isRequired ? "" : "none";
  $("doc-owner").required = isRequired;
  $("doc-review-frequency").required = isRequired;
}

$("doc-type").addEventListener("change", updateDocFieldRequirements);
$("doc-tags").addEventListener("input", () => renderTagChips($("doc-tags").value));
$("doc-last-review-date").addEventListener("change", recomputeDocNext);
$("doc-review-frequency").addEventListener("change", recomputeDocNext);

function recomputeDocNext() {
  const last = $("doc-last-review-date").value;
  const freq = $("doc-review-frequency").value;
  if (!last || !freq) return;
  const d = new Date(last + "T00:00:00");
  if (freq === "monthly") d.setMonth(d.getMonth() + 1);
  else if (freq === "quarterly") d.setMonth(d.getMonth() + 3);
  else if (freq === "annually") d.setFullYear(d.getFullYear() + 1);
  $("doc-next-review-date").value = d.toISOString().slice(0, 10);
}

$("doc-cancel").addEventListener("click", () => $("doc-dialog").close());

$("doc-confirm").addEventListener("click", async () => {
  const { node, doc } = docContext;
  const docType = $("doc-type").value;
  const owner = $("doc-owner").value.trim();
  const freq = $("doc-review-frequency").value;

  if (TYPES_REQUIRING_OWNER_FREQ.has(docType)) {
    if (!owner || !freq) {
      toast(`${DOC_TYPE_LABELS[docType]} requires owner and review frequency`, true);
      return;
    }
  }

  try {
    if (doc) {
      const payload = {
        doc_type: docType,
        tags: $("doc-tags").value || null,
        owner: owner || null,
        review_frequency: freq || null,
        last_review_date: $("doc-last-review-date").value || null,
        next_review_date: $("doc-next-review-date").value || null,
        version: $("doc-version").value || null,
        notes: $("doc-notes").value || null,
        description: $("doc-description").value || null,
      };
      await api(`/library/documents/${doc.id}`, { method: "PUT", body: JSON.stringify(payload) });
      toast("Document updated");
    } else {
      const file = $("doc-file").files[0];
      if (!file) { toast("Choose a file to upload", true); return; }

      const fd = new FormData();
      fd.append("file", file);
      fd.append("doc_type", docType);
      if ($("doc-tags").value) fd.append("tags", $("doc-tags").value);
      if (owner) fd.append("owner", owner);
      if (freq) fd.append("review_frequency", freq);
      if ($("doc-last-review-date").value) fd.append("last_review_date", $("doc-last-review-date").value);
      if ($("doc-next-review-date").value) fd.append("next_review_date", $("doc-next-review-date").value);
      if ($("doc-version").value) fd.append("version", $("doc-version").value);
      if ($("doc-notes").value) fd.append("notes", $("doc-notes").value);
      if ($("doc-description").value) fd.append("description", $("doc-description").value);

      // Step 1: upload into the central library.
      const created = await api(`/library/documents`, { method: "POST", body: fd });
      // Step 2: auto-link to the originating node, if one was provided.
      if (node && node.id != null) {
        await api(`/nodes/${node.id}/link-document/${created.id}`, { method: "POST" });
      }
      toast(node ? "Uploaded and linked" : "Uploaded to library");
    }
    $("doc-dialog").close();
    if (node) {
      state.docsByNode.delete(node.id);
      await ensureDocsLoaded(node.id);
    }
    // Refresh library if it's the active view.
    if (state.viewMode === "library") await loadLibrary();
    renderRightPane();
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
  }
});

// ---------- Details dialog (governance metadata) ----------

let detailsContext = null;

function openDetailsDialog(node) {
  detailsContext = node;
  $("d-level").textContent = LEVEL_NAMES[node.level] || `L${node.level}`;
  $("d-code-chip").textContent = node.code;
  $("d-name-chip").textContent = node.name;

  $("f-code").value = node.code || "";
  $("f-name").value = node.name || "";
  $("f-description").value = node.description || "";
  $("f-owner").value = node.owner || "";
  $("f-status").value = node.status || "active";
  $("f-review-frequency").value = node.review_frequency || "";
  $("f-last-review-date").value = node.last_review_date || "";
  $("f-next-review-date").value = node.next_review_date || "";
  $("f-linked-procedure-url").value = node.linked_procedure_url || "";
  $("f-kpi-name").value = node.kpi_name || "";
  $("f-kpi-target").value = node.kpi_target || "";
  $("f-kpi-current").value = node.kpi_current || "";
  $("f-camunda-process-key").value = node.camunda_process_key || "";

  const updated = node.updated_at ? new Date(node.updated_at).toLocaleString() : "";
  $("meta-info").textContent = `id #${node.id} · updated ${updated}`;

  const canAddChild = node.level < 4;
  $("add-child-btn").disabled = !canAddChild;
  $("add-child-btn").style.opacity = canAddChild ? 1 : 0.4;
  $("add-child-btn").title = canAddChild ? "Add child node" : "L4 is terminal — no children allowed";

  $("details-dialog").showModal();
}

$("details-close").addEventListener("click", () => $("details-dialog").close());

$("detail-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!detailsContext) return;
  const payload = {
    code: $("f-code").value.trim(),
    name: $("f-name").value.trim(),
    description: $("f-description").value || null,
    owner: $("f-owner").value || null,
    status: $("f-status").value,
    review_frequency: $("f-review-frequency").value || null,
    last_review_date: $("f-last-review-date").value || null,
    linked_procedure_url: $("f-linked-procedure-url").value || null,
    kpi_name: $("f-kpi-name").value || null,
    kpi_target: $("f-kpi-target").value || null,
    kpi_current: $("f-kpi-current").value || null,
    camunda_process_key: $("f-camunda-process-key").value || null,
  };
  try {
    await api(`/nodes/${detailsContext.id}`, { method: "PUT", body: JSON.stringify(payload) });
    toast("Saved");
    $("details-dialog").close();
    await loadTree();
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
  }
});

$("delete-btn").addEventListener("click", async () => {
  if (!detailsContext) return;
  const node = detailsContext;
  const msg = node.children && node.children.length > 0
    ? `Delete "${node.name}" AND its ${countDescendants(node)} descendant(s)? This cannot be undone.`
    : `Delete "${node.name}"?`;
  if (!confirm(msg)) return;
  try {
    await api(`/nodes/${node.id}`, { method: "DELETE" });
    $("details-dialog").close();
    // If we deleted the focused node, jump up one level (or to root).
    if (state.currentNodeId === node.id) {
      state.currentNodeId = node.parent_id || null;
    }
    state.treeSelectedId = null;
    state.docsByNode.delete(node.id);
    toast("Deleted");
    await loadTree();
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
});

$("add-child-btn").addEventListener("click", () => {
  if (!detailsContext) return;
  openAddDialog(detailsContext);
});

function countDescendants(node) {
  if (!node.children) return 0;
  return node.children.reduce((sum, c) => sum + 1 + countDescendants(c), 0);
}

function recomputeNextReviewDate() {
  const last = $("f-last-review-date").value;
  const freq = $("f-review-frequency").value;
  if (!last || !freq) { $("f-next-review-date").value = ""; return; }
  const d = new Date(last + "T00:00:00");
  if (freq === "monthly") d.setMonth(d.getMonth() + 1);
  else if (freq === "quarterly") d.setMonth(d.getMonth() + 3);
  else if (freq === "annually") d.setFullYear(d.getFullYear() + 1);
  $("f-next-review-date").value = d.toISOString().slice(0, 10);
}
$("f-last-review-date").addEventListener("change", recomputeNextReviewDate);
$("f-review-frequency").addEventListener("change", recomputeNextReviewDate);

// ---------- Add child / add root dialog ----------

let addContext = null;

function openAddDialog(parentNode /* null for root */) {
  addContext = parentNode;
  $("add-title").textContent = parentNode
    ? `Add child under ${parentNode.code} — ${parentNode.name} (will be L${parentNode.level + 1})`
    : "Add new L1 Business Domain";
  $("add-code").value = "";
  $("add-name").value = "";
  $("add-description").value = "";
  $("add-owner").value = "";
  $("add-status").value = "active";
  $("add-dialog").showModal();
  setTimeout(() => $("add-code").focus(), 50);
}

$("add-cancel").addEventListener("click", () => $("add-dialog").close());

$("add-confirm").addEventListener("click", async () => {
  const parent = addContext;
  const level = parent ? parent.level + 1 : 1;
  if (level > 4) { toast("L4 is terminal — cannot add child", true); return; }
  const payload = {
    parent_id: parent ? parent.id : null,
    level,
    code: $("add-code").value.trim(),
    name: $("add-name").value.trim(),
    description: $("add-description").value || null,
    owner: $("add-owner").value || null,
    status: $("add-status").value,
  };
  if (!payload.code || !payload.name) { toast("Code and name are required", true); return; }
  try {
    const created = await api("/nodes", { method: "POST", body: JSON.stringify(payload) });
    $("add-dialog").close();
    toast("Created");
    // After adding, focus the parent's branch (so the new child is visible),
    // or focus the new root domain itself if no parent.
    state.currentNodeId = parent ? parent.id : created.id;
    state.treeSelectedId = created.id;
    await loadTree();
  } catch (err) {
    toast(`Create failed: ${err.message}`, true);
  }
});

$("add-root-btn").addEventListener("click", () => openAddDialog(null));

// ---------- KPIs: drawer, definition form, data entry, tile summary ----------

const FREQ_LABELS = {
  daily: "Daily",
  weekly: "Weekly",
  monthly: "Monthly",
  quarterly: "Quarterly",
  annually: "Annually",
};

function statusForKpi(kpi) {
  // Returns one of: "good", "warn", "bad", "no-data".
  const latest = kpi.latest_entry;
  if (!latest) return "no-data";
  const actual = latest.actual_value;
  const target = kpi.target_value;
  const warn = kpi.warning_threshold;
  if (actual == null || target == null) return "no-data";

  if (kpi.direction === "higher_is_better") {
    if (actual >= target) return "good";
    if (warn != null && actual >= warn) return "warn";
    return "bad";
  }
  // lower_is_better
  if (actual <= target) return "good";
  if (warn != null && actual <= warn) return "warn";
  return "bad";
}

function directionArrow(direction) {
  return direction === "lower_is_better" ? "↓" : "↑";
}

function formatKpiValue(v, unit) {
  if (v == null) return "—";
  const s = Number.isFinite(v) ? String(+v) : String(v);
  return unit ? `${s} ${unit}` : s;
}

async function ensureKpisLoaded(nodeId) {
  if (state.kpisByNode.has(nodeId)) return;
  try {
    const kpis = await api(`/nodes/${nodeId}/kpis`);
    state.kpisByNode.set(nodeId, kpis);
    rerenderTileKpiSummary(nodeId);
    if (kpiDrawerCtx.nodeId === nodeId) renderKpiDrawerBody();
  } catch (err) {
    toast(`Failed to load KPIs: ${err.message}`, true);
  }
}

function rerenderTileKpiSummary(nodeId) {
  const tile = document.querySelector(`.tile[data-id="${nodeId}"]`);
  if (!tile) return;
  const old = tile.querySelector(".tile-kpi-summary");
  if (old) old.remove();
  const node = state.byId.get(nodeId);
  if (!node) return;
  const fresh = renderKpiSummary(node);
  if (fresh) tile.appendChild(fresh);
}

function renderKpiSummary(node) {
  const kpis = state.kpisByNode.get(node.id);
  if (!kpis) return null;
  const active = kpis.filter((k) => k.status === "active");
  if (active.length === 0) return null;

  const wrap = document.createElement("div");
  wrap.className = "tile-kpi-summary";

  active.forEach((k) => {
    const row = document.createElement("div");
    row.className = "kpi-indicator";
    row.title = "Click to enter data / view history";
    row.onclick = (e) => {
      e.stopPropagation();
      openKpiEntryDialog(k);
    };

    const dot = document.createElement("span");
    dot.className = `kpi-dot ${statusForKpi(k)}`;
    const name = document.createElement("span");
    name.className = "kpi-name";
    name.textContent = k.name;
    const vals = document.createElement("span");
    vals.className = "kpi-vals";
    const cur = k.latest_entry ? k.latest_entry.actual_value : null;
    vals.textContent = `${cur == null ? "—" : cur} / ${k.target_value == null ? "—" : k.target_value}${k.unit ? " " + k.unit : ""}`;

    row.append(dot, name, vals);
    wrap.appendChild(row);
  });

  return wrap;
}

// ---- KPI drawer ----

let kpiDrawerCtx = { nodeId: null };

function openKpiDrawer(node) {
  // Mutual exclusion: only one side drawer at a time.
  if ($("docs-drawer").open) closeDocsDrawer();

  kpiDrawerCtx = { nodeId: node.id };
  $("kpi-drawer-node-name").textContent = `${node.code} — ${node.name}`;
  renderKpiDrawerBody();

  const dlg = $("kpi-drawer");
  if (!dlg.open) dlg.show();

  ensureKpisLoaded(node.id);
}

function closeKpiDrawer() {
  kpiDrawerCtx = { nodeId: null };
  $("kpi-drawer").close();
}

function renderKpiDrawerBody() {
  if (kpiDrawerCtx.nodeId === null) return;
  const node = state.byId.get(kpiDrawerCtx.nodeId);
  const kpis = state.kpisByNode.get(kpiDrawerCtx.nodeId);
  const body = $("kpi-drawer-body");
  body.innerHTML = "";

  $("kpi-drawer-count").textContent = kpis
    ? `${kpis.length} KPI${kpis.length === 1 ? "" : "s"}`
    : "loading…";

  if (!kpis) {
    const loading = document.createElement("div");
    loading.className = "drawer-empty";
    loading.textContent = "Loading…";
    body.appendChild(loading);
    return;
  }
  if (kpis.length === 0) {
    const empty = document.createElement("div");
    empty.className = "drawer-empty";
    empty.textContent = "No KPIs defined for this node yet. Use “+ Add KPI” to create one.";
    body.appendChild(empty);
    return;
  }

  kpis.forEach((k) => body.appendChild(renderKpiRow(node, k)));
}

function renderKpiRow(node, kpi) {
  const row = document.createElement("div");
  row.className = "kpi-row";

  const top = document.createElement("div");
  top.className = "kpi-row-top";

  const name = document.createElement("span");
  name.className = "kpi-row-name";
  name.textContent = kpi.name;

  const statusChip = document.createElement("span");
  statusChip.className = `kpi-status-chip ${kpi.status}`;
  statusChip.textContent = (kpi.status || "active").replace("_", " ");

  const actions = document.createElement("div");
  actions.className = "kpi-row-actions";

  const editBtn = document.createElement("button");
  editBtn.textContent = "Edit";
  editBtn.onclick = (e) => { e.stopPropagation(); openKpiDialog(node, kpi); };

  const enterBtn = document.createElement("button");
  enterBtn.textContent = "Enter Data";
  enterBtn.className = "primary";
  enterBtn.onclick = (e) => { e.stopPropagation(); openKpiEntryDialog(kpi); };

  const delBtn = document.createElement("button");
  delBtn.textContent = "Delete";
  delBtn.className = "danger";
  delBtn.onclick = (e) => { e.stopPropagation(); deleteKpi(kpi); };

  actions.append(editBtn, enterBtn, delBtn);
  top.append(name, statusChip, actions);

  const meta = document.createElement("div");
  meta.className = "kpi-row-meta";
  const parts = [];
  if (kpi.target_value != null) {
    parts.push(`Target: <strong>${formatKpiValue(kpi.target_value, kpi.unit)}</strong> <span class="kpi-direction-arrow">${directionArrow(kpi.direction)}</span>`);
  }
  if (kpi.unit) parts.push(`Unit: <strong>${kpi.unit}</strong>`);
  if (kpi.owner) parts.push(`Owner: <strong>${escapeHtml(kpi.owner)}</strong>`);
  if (kpi.reporting_frequency) parts.push(`Freq: <strong>${FREQ_LABELS[kpi.reporting_frequency]}</strong>`);
  if (kpi.data_source) parts.push(`Source: <strong>${escapeHtml(kpi.data_source)}</strong>`);
  if (kpi.latest_entry) {
    parts.push(`Latest: <strong>${formatKpiValue(kpi.latest_entry.actual_value, kpi.unit)}</strong> (${escapeHtml(kpi.latest_entry.period)})`);
  }
  meta.innerHTML = parts.join(" · ");
  row.append(top, meta);

  return row;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

$("kpi-drawer-close-btn").addEventListener("click", () => closeKpiDrawer());
$("kpi-drawer-add-btn").addEventListener("click", () => {
  if (kpiDrawerCtx.nodeId === null) return;
  openKpiDialog(state.byId.get(kpiDrawerCtx.nodeId), null);
});

// ESC closes whichever drawer is open. (Extends the existing docs-drawer handler.)
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if ($("kpi-drawer").open) {
    e.preventDefault();
    closeKpiDrawer();
  }
});

// ---- KPI definition dialog (Create / Edit) ----

let kpiFormCtx = { node: null, kpi: null };

function openKpiDialog(node, kpi) {
  kpiFormCtx = { node, kpi };
  $("kpi-dialog-title").textContent = kpi
    ? `Edit KPI — ${kpi.name}`
    : `Add KPI to ${node.code} — ${node.name}`;

  $("kpi-name").value = kpi ? (kpi.name || "") : "";
  $("kpi-description").value = kpi ? (kpi.description || "") : "";
  $("kpi-calculation-method").value = kpi ? (kpi.calculation_method || "") : "";
  $("kpi-unit").value = kpi ? (kpi.unit || "") : "";
  $("kpi-target-value").value = kpi && kpi.target_value != null ? kpi.target_value : "";
  $("kpi-warning-threshold").value = kpi && kpi.warning_threshold != null ? kpi.warning_threshold : "";
  $("kpi-direction").value = kpi ? (kpi.direction || "higher_is_better") : "higher_is_better";
  $("kpi-owner").value = kpi ? (kpi.owner || "") : "";
  $("kpi-reporting-frequency").value = kpi ? (kpi.reporting_frequency || "") : "";
  $("kpi-data-source").value = kpi ? (kpi.data_source || "") : "";
  $("kpi-status").value = kpi ? (kpi.status || "active") : "active";

  $("kpi-dialog").showModal();
  setTimeout(() => $("kpi-name").focus(), 50);
}

$("kpi-dialog-cancel").addEventListener("click", () => $("kpi-dialog").close());

$("kpi-dialog-save").addEventListener("click", async () => {
  const { node, kpi } = kpiFormCtx;
  const name = $("kpi-name").value.trim();
  const owner = $("kpi-owner").value.trim();
  if (!name || !owner) {
    toast("Name and Owner are required", true);
    return;
  }
  const payload = {
    name,
    description: $("kpi-description").value || null,
    calculation_method: $("kpi-calculation-method").value || null,
    unit: $("kpi-unit").value || null,
    target_value: $("kpi-target-value").value !== "" ? parseFloat($("kpi-target-value").value) : null,
    warning_threshold: $("kpi-warning-threshold").value !== "" ? parseFloat($("kpi-warning-threshold").value) : null,
    direction: $("kpi-direction").value,
    owner,
    reporting_frequency: $("kpi-reporting-frequency").value || null,
    data_source: $("kpi-data-source").value || null,
    status: $("kpi-status").value,
  };
  try {
    if (kpi) {
      await api(`/kpis/${kpi.id}`, { method: "PUT", body: JSON.stringify(payload) });
      toast("KPI updated");
    } else {
      await api(`/nodes/${node.id}/kpis`, { method: "POST", body: JSON.stringify(payload) });
      toast("KPI created");
    }
    $("kpi-dialog").close();
    state.kpisByNode.delete(node.id);
    await ensureKpisLoaded(node.id);
    rerenderTileKpiSummary(node.id);
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
  }
});

async function deleteKpi(kpi) {
  if (!confirm(`Delete KPI "${kpi.name}" and all its entries? This cannot be undone.`)) return;
  try {
    await api(`/kpis/${kpi.id}`, { method: "DELETE" });
    state.kpisByNode.delete(kpi.node_id);
    state.entriesByKpi.delete(kpi.id);
    await ensureKpisLoaded(kpi.node_id);
    rerenderTileKpiSummary(kpi.node_id);
    toast("KPI deleted");
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
}

// ---- Enter Data dialog ----

let kpiEntryCtx = { kpi: null };

async function openKpiEntryDialog(kpi) {
  kpiEntryCtx = { kpi };
  $("kpi-entry-title").textContent = "Enter Data";
  $("kpi-entry-name").textContent = kpi.name;
  $("kpi-entry-target").textContent = kpi.target_value != null
    ? `${formatKpiValue(kpi.target_value, kpi.unit)} ${directionArrow(kpi.direction)}`
    : "—";

  $("kpi-entry-period").value = "";
  $("kpi-entry-actual").value = "";
  $("kpi-entry-entered-by").value = "";
  $("kpi-entry-notes").value = "";

  $("kpi-entry-dialog").showModal();
  await loadKpiEntries(kpi.id);
  renderKpiHistory(kpi);
}

async function loadKpiEntries(kpiId) {
  try {
    const entries = await api(`/kpis/${kpiId}/entries`);
    state.entriesByKpi.set(kpiId, entries);
  } catch (err) {
    toast(`Failed to load entries: ${err.message}`, true);
  }
}

function renderKpiHistory(kpi) {
  const tbody = $("kpi-history-body");
  tbody.innerHTML = "";
  const entries = (state.entriesByKpi.get(kpi.id) || []).slice(0, 10);
  if (entries.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="7" class="muted" style="text-align:center;padding:12px;">No entries yet.</td>`;
    tbody.appendChild(tr);
    return;
  }
  entries.forEach((entry) => {
    const tr = document.createElement("tr");

    const target = kpi.target_value;
    let deltaClass = "neutral";
    let deltaText = "—";
    if (target != null) {
      const diff = entry.actual_value - target;
      const isGood =
        kpi.direction === "higher_is_better" ? entry.actual_value >= target : entry.actual_value <= target;
      deltaClass = isGood ? "good" : "bad";
      const sign = diff > 0 ? "+" : "";
      deltaText = `${sign}${diff.toFixed(2)}`;
    }

    const date = entry.entered_at ? new Date(entry.entered_at).toLocaleDateString() : "";

    tr.innerHTML = `
      <td>${escapeHtml(entry.period)}</td>
      <td>${formatKpiValue(entry.actual_value, kpi.unit)}</td>
      <td class="delta ${deltaClass}">${deltaText}</td>
      <td>${escapeHtml(entry.notes || "")}</td>
      <td>${escapeHtml(entry.entered_by || "")}</td>
      <td>${date}</td>
      <td></td>
    `;

    const delBtn = document.createElement("button");
    delBtn.className = "danger";
    delBtn.textContent = "Delete";
    delBtn.onclick = (e) => { e.stopPropagation(); deleteKpiEntry(entry, kpi); };
    tr.lastElementChild.appendChild(delBtn);

    tbody.appendChild(tr);
  });
}

$("kpi-entry-cancel").addEventListener("click", () => $("kpi-entry-dialog").close());

$("kpi-entry-save").addEventListener("click", async () => {
  const kpi = kpiEntryCtx.kpi;
  if (!kpi) return;
  const period = $("kpi-entry-period").value.trim();
  const actualRaw = $("kpi-entry-actual").value;
  if (!period || actualRaw === "") {
    toast("Period and Actual Value are required", true);
    return;
  }
  const payload = {
    period,
    actual_value: parseFloat(actualRaw),
    entered_by: $("kpi-entry-entered-by").value || null,
    notes: $("kpi-entry-notes").value || null,
  };
  try {
    await api(`/kpis/${kpi.id}/entries`, { method: "POST", body: JSON.stringify(payload) });
    toast("Entry added");
    $("kpi-entry-period").value = "";
    $("kpi-entry-actual").value = "";
    $("kpi-entry-notes").value = "";
    // Refresh entries + KPIs (latest_entry may have changed).
    await loadKpiEntries(kpi.id);
    state.kpisByNode.delete(kpi.node_id);
    await ensureKpisLoaded(kpi.node_id);
    renderKpiHistory(kpi);
    rerenderTileKpiSummary(kpi.node_id);
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
  }
});

async function deleteKpiEntry(entry, kpi) {
  if (!confirm(`Delete entry for "${entry.period}"?`)) return;
  try {
    await api(`/kpi-entries/${entry.id}`, { method: "DELETE" });
    await loadKpiEntries(kpi.id);
    state.kpisByNode.delete(kpi.node_id);
    await ensureKpisLoaded(kpi.node_id);
    renderKpiHistory(kpi);
    rerenderTileKpiSummary(kpi.node_id);
    toast("Entry deleted");
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
}

// ---------- Toast ----------

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast"; }, 2800);
}

// ---------- Document Library (full-page view) ----------

function setViewMode(mode) {
  // "library" shows the overlay; "tiles" hides it. The tile layout
  // stays mounted underneath the overlay — we never hide it.
  state.viewMode = mode;
  const isLibrary = mode === "library";
  // Mutual exclusion with the sustainability overlay.
  if (isLibrary && document.getElementById("sustainability-view") &&
      !document.getElementById("sustainability-view").hidden) {
    setSustainabilityOpen(false);
  }
  $("library-view").hidden = !isLibrary;
  $("view-toggle-btn").innerHTML = isLibrary ? "✕ Library" : "📚 Library";
  if (isLibrary) loadLibrary();
}

$("view-toggle-btn").addEventListener("click", () => {
  setViewMode(state.viewMode === "library" ? "tiles" : "library");
});

$("library-close-btn").addEventListener("click", () => setViewMode("tiles"));

// ESC closes the library overlay (in addition to the existing drawer ESC).
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && state.viewMode === "library") {
    e.preventDefault();
    setViewMode("tiles");
  }
});

async function loadLibrary() {
  try {
    const qs = new URLSearchParams();
    if (state.libraryFilter.doc_type) qs.set("doc_type", state.libraryFilter.doc_type);
    if (state.libraryFilter.search) qs.set("search", state.libraryFilter.search);
    if (state.libraryFilter.tags.length > 0) qs.set("tags", state.libraryFilter.tags.join(","));
    const path = "/library/documents" + (qs.toString() ? `?${qs}` : "");
    state.libraryDocs = await api(path);
    renderLibraryTable();
  } catch (err) {
    toast(`Failed to load library: ${err.message}`, true);
  }
}

function renderLibraryTable() {
  const tbody = $("library-table-body");
  tbody.innerHTML = "";

  // Apply the "Misc" doc-type filter client-side (the server only knows
  // about real enum values, so this catches NULL/unknown types).
  let docs = state.libraryDocs;
  if (state.libraryFilter.doc_type === "_misc") {
    const known = new Set(Object.keys(DOC_TYPE_LABELS));
    docs = docs.filter((d) => !known.has(d.doc_type));
  }

  if (docs.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="7" class="muted" style="text-align:center;padding:24px;">No documents match.</td>`;
    tbody.appendChild(tr);
    return;
  }

  docs.forEach((doc) => {
    const tr = document.createElement("tr");

    const typeCell = document.createElement("td");
    typeCell.innerHTML = `<span class="doc-badge dt-${doc.doc_type}" style="cursor:default;">${DOC_TYPE_LABELS[doc.doc_type] || "Misc"}</span>`;

    const fileCell = document.createElement("td");
    fileCell.innerHTML = `<div class="lib-filename"><span>${escapeHtml(doc.original_filename)}</span>${doc.description ? `<span class="lib-desc">${escapeHtml(doc.description)}</span>` : ""}</div>`;

    const ownerCell = document.createElement("td");
    ownerCell.textContent = doc.owner || "—";

    const verCell = document.createElement("td");
    verCell.textContent = doc.version || "—";

    const reviewCell = document.createElement("td");
    reviewCell.textContent = doc.next_review_date || "—";

    const linkedCell = document.createElement("td");
    const pill = document.createElement("span");
    pill.className = "linked-pill";
    pill.innerHTML = `<strong>${doc.linked_nodes_count || 0}</strong> nodes`;
    pill.onclick = async () => showLinkedNodesTooltip(doc, pill);
    pill.title = "Click to see which nodes this document is linked to";
    linkedCell.appendChild(pill);

    const actionsCell = document.createElement("td");
    actionsCell.className = "lib-actions";
    const mkBtn = (label, fn, danger = false) => {
      const b = document.createElement("button");
      b.textContent = label;
      if (danger) b.className = "danger";
      b.onclick = (e) => { e.stopPropagation(); fn(); };
      return b;
    };
    actionsCell.append(
      mkBtn("View", () => viewDoc(doc.id)),
      mkBtn("Download", () => downloadDoc(doc.id)),
      mkBtn("Edit", () => openDocDialog(null, doc)),
      mkBtn("Delete", () => deleteLibraryDoc(doc), true),
    );

    tr.append(typeCell, fileCell, ownerCell, verCell, reviewCell, linkedCell, actionsCell);
    tbody.appendChild(tr);
  });
}

async function showLinkedNodesTooltip(doc, anchor) {
  try {
    const full = await api(`/library/documents/${doc.id}`);
    const names = (full.linked_nodes || []).map((n) => `${n.code} ${n.name}`).join("\n");
    anchor.title = names || "Not linked to any node yet.";
  } catch (err) {
    anchor.title = "Failed to load linked nodes.";
  }
}

// Library filter input wiring
$("library-search").addEventListener("input", (e) => {
  state.libraryFilter.search = e.target.value;
  // Debounce-lite: only fire after a short pause
  clearTimeout(loadLibrary._t);
  loadLibrary._t = setTimeout(loadLibrary, 200);
});
$("library-type-filter").addEventListener("change", (e) => {
  state.libraryFilter.doc_type = e.target.value;
  loadLibrary();
});
$("library-upload-btn").addEventListener("click", () => openDocDialog(null, null));

// Library tag-chip filter — mirrors the predefined-tag list from the upload dialog.
(function buildLibraryTagFilter() {
  const c = $("library-tag-filter");
  PREDEFINED_TAGS.forEach((tag) => {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.textContent = tag;
    chip.onclick = () => {
      const i = state.libraryFilter.tags.indexOf(tag);
      if (i >= 0) state.libraryFilter.tags.splice(i, 1);
      else state.libraryFilter.tags.push(tag);
      chip.classList.toggle("active");
      loadLibrary();
    };
    c.appendChild(chip);
  });
})();

// ---------- Link from Library (embedded as the second tab of #doc-dialog) ----------

let linkDialogCtx = { node: null };

async function refreshLinkDialogBody() {
  const { node } = linkDialogCtx;
  if (!node) return;
  try {
    const qs = new URLSearchParams();
    if ($("link-type-filter").value) qs.set("doc_type", $("link-type-filter").value);
    if ($("link-search").value) qs.set("search", $("link-search").value);
    const docs = await api(`/library/documents${qs.toString() ? `?${qs}` : ""}`);
    const linked = state.docsByNode.get(node.id) || await api(`/nodes/${node.id}/documents`);
    state.docsByNode.set(node.id, linked);

    const linkedIds = new Set(linked.map((d) => d.id));
    renderLinkDialogBody(docs, linkedIds);
  } catch (err) {
    toast(`Search failed: ${err.message}`, true);
  }
}

function renderLinkDialogBody(allDocs, linkedIds) {
  const body = $("link-dialog-body");
  body.innerHTML = "";

  const linked = allDocs.filter((d) => linkedIds.has(d.id));
  const unlinked = allDocs.filter((d) => !linkedIds.has(d.id));

  if (linked.length > 0) {
    const title = document.createElement("div");
    title.className = "link-section-title";
    title.textContent = `Already linked (${linked.length})`;
    body.appendChild(title);
    linked.forEach((d) => body.appendChild(renderLinkRow(d, true)));
    const sep = document.createElement("div");
    sep.className = "link-section-divider";
    body.appendChild(sep);
  }

  const title2 = document.createElement("div");
  title2.className = "link-section-title";
  title2.textContent = `Available in library (${unlinked.length})`;
  body.appendChild(title2);

  if (unlinked.length === 0) {
    const empty = document.createElement("div");
    empty.className = "drawer-empty";
    empty.textContent = "No matching documents.";
    body.appendChild(empty);
  } else {
    unlinked.forEach((d) => body.appendChild(renderLinkRow(d, false)));
  }
}

function renderLinkRow(doc, isLinked) {
  const row = document.createElement("div");
  row.className = "link-row" + (isLinked ? " is-linked" : "");

  const icon = document.createElement("div");
  icon.className = "doc-icon";
  icon.textContent = DOC_TYPE_ICON[doc.doc_type] || "?";

  const info = document.createElement("div");
  info.className = "link-info";
  const fn = document.createElement("div");
  fn.className = "link-filename";
  fn.textContent = doc.original_filename;
  const sub = document.createElement("div");
  sub.className = "link-sub";
  const parts = [DOC_TYPE_LABELS[doc.doc_type] || "Misc"];
  if (doc.owner) parts.push(`Owner: ${doc.owner}`);
  if (doc.version) parts.push(`v${doc.version}`);
  parts.push(`Linked to ${doc.linked_nodes_count || 0} node${doc.linked_nodes_count === 1 ? "" : "s"}`);
  sub.textContent = parts.join(" · ");
  info.append(fn, sub);

  const action = document.createElement("button");
  action.className = "link-action " + (isLinked ? "is-unlink" : "is-link");
  action.textContent = isLinked ? "Unlink" : "Link";
  action.onclick = async (e) => {
    e.stopPropagation();
    const { node } = linkDialogCtx;
    try {
      if (isLinked) {
        await api(`/nodes/${node.id}/unlink-document/${doc.id}`, { method: "DELETE" });
      } else {
        await api(`/nodes/${node.id}/link-document/${doc.id}`, { method: "POST" });
      }
      state.docsByNode.delete(node.id);
      await ensureDocsLoaded(node.id);
      await refreshLinkDialogBody();
      renderRightPane();
    } catch (err) {
      toast(`${isLinked ? "Unlink" : "Link"} failed: ${err.message}`, true);
    }
  };

  row.append(icon, info, action);
  return row;
}

$("link-dialog-close").addEventListener("click", () => $("doc-dialog").close());
$("link-search").addEventListener("input", () => {
  clearTimeout(refreshLinkDialogBody._t);
  refreshLinkDialogBody._t = setTimeout(refreshLinkDialogBody, 200);
});
$("link-type-filter").addEventListener("change", () => refreshLinkDialogBody());


// ---------- Sustainability: overlay, topic pills, topic-link modal ----------

const SUSTAINABILITY_THEMES = [
  { key: "environment",             label: "Environment" },
  { key: "labor_human_rights",      label: "Labor & Human Rights" },
  { key: "ethics",                  label: "Ethics" },
  { key: "sustainable_procurement", label: "Sustainable Procurement" },
];

// Short labels used inside the tile pills so the names don't overflow.
const TOPIC_SHORT_LABEL = {
  "Energy & GHG Emissions": "Energy/GHG",
  "Water": "Water",
  "Biodiversity": "Biodiversity",
  "Pollution & Waste": "Pollution",
  "Hazardous Materials": "Hazardous",
  "Product Use Impact": "Use Impact",
  "Product End-of-Life": "End-of-Life",
  "Health & Safety": "H&S",
  "Working Conditions": "Working Cond.",
  "Social Dialogue": "Social Dialogue",
  "Diversity & Inclusion": "D&I",
  "Training & Development": "Training",
  "Human Rights": "Human Rights",
  "Anti-Corruption & Bribery": "Anti-Corruption",
  "Anti-Competitive Practices": "Anti-Competitive",
  "Responsible Information Management": "Info Mgmt",
  "Whistleblower Protection": "Whistleblower",
  "Supplier Environmental Practices": "Sup. Env.",
  "Supplier Social Practices": "Sup. Social",
  "Supplier Code of Conduct": "Sup. CoC",
  "Supplier Assessment & Monitoring": "Sup. Audit",
};

async function ensureAllTopicsLoaded() {
  if (state.allTopics) return state.allTopics;
  try {
    state.allTopics = await api("/sustainability/topics");
  } catch (err) {
    toast(`Failed to load topics: ${err.message}`, true);
    state.allTopics = [];
  }
  return state.allTopics;
}

async function ensureTopicsLoaded(nodeId) {
  if (state.topicsByNode.has(nodeId)) return;
  try {
    const topics = await api(`/nodes/${nodeId}/sustainability-topics`);
    state.topicsByNode.set(nodeId, topics);
    rerenderTileTopicPills(nodeId);
  } catch (err) {
    toast(`Failed to load topics: ${err.message}`, true);
  }
}

function rerenderTileTopicPills(nodeId) {
  const tile = document.querySelector(`.tile[data-id="${nodeId}"]`);
  if (!tile) return;
  const old = tile.querySelector(".tile-topic-pills");
  if (old) old.remove();
  const node = state.byId.get(nodeId);
  if (!node) return;
  const fresh = renderTopicPills(node);
  if (fresh) tile.appendChild(fresh);
}

function renderTopicPills(node) {
  const topics = state.topicsByNode.get(node.id);
  if (!topics || topics.length === 0) return null;
  const wrap = document.createElement("div");
  wrap.className = "tile-topic-pills";
  topics.forEach((t) => {
    const pill = document.createElement("span");
    pill.className = `topic-pill theme-${t.theme}`;
    pill.textContent = TOPIC_SHORT_LABEL[t.name] || t.name;
    pill.title = `${t.name} — click "🌱 Topic" on the tile to manage`;
    wrap.appendChild(pill);
  });
  return wrap;
}

// ---- Sustainability overlay (full-page panel) ----

function setSustainabilityOpen(open) {
  $("sustainability-view").hidden = !open;
  $("sustainability-toggle-btn").innerHTML = open ? "✕ Sustainability" : "🌱 Sustainability";
  if (open) {
    // Make sure the docs library overlay isn't also open.
    if (state.viewMode === "library") setViewMode("tiles");
    renderSustainabilityPanel();
  }
}

$("sustainability-toggle-btn").addEventListener("click", () => {
  setSustainabilityOpen($("sustainability-view").hidden);
});
$("sustainability-close-btn").addEventListener("click", () => setSustainabilityOpen(false));

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !$("sustainability-view").hidden) {
    e.preventDefault();
    setSustainabilityOpen(false);
  }
});

async function renderSustainabilityPanel() {
  const body = $("sustainability-body");
  body.innerHTML = '<div class="drawer-empty">Loading…</div>';
  const topics = await ensureAllTopicsLoaded();
  // Force a refresh each open so counts stay current.
  state.allTopics = null;
  const fresh = await ensureAllTopicsLoaded();
  body.innerHTML = "";

  SUSTAINABILITY_THEMES.forEach(({ key, label }) => {
    const inTheme = (fresh || []).filter((t) => t.theme === key);
    const section = document.createElement("section");
    section.className = `theme-section theme-${key}`;

    const header = document.createElement("div");
    header.className = "theme-section-header";
    const chev = document.createElement("span");
    chev.className = "theme-chevron";
    chev.textContent = "▾";
    const title = document.createElement("span");
    title.textContent = label;
    const count = document.createElement("span");
    count.className = "theme-count";
    count.textContent = `${inTheme.length} criteria`;
    header.append(chev, title, count);
    header.onclick = () => section.classList.toggle("collapsed");

    const bodyEl = document.createElement("div");
    bodyEl.className = "theme-section-body";
    inTheme.forEach((t) => bodyEl.appendChild(renderTopicCard(t)));

    section.append(header, bodyEl);
    body.appendChild(section);
  });
}

function renderTopicCard(topic) {
  const card = document.createElement("div");
  card.className = "topic-card";

  const top = document.createElement("div");
  top.className = "topic-card-top";
  const name = document.createElement("span");
  name.className = "topic-card-name";
  name.textContent = topic.name;
  top.appendChild(name);

  const statusChip = document.createElement("span");
  statusChip.className = `kpi-status-chip status-chip-${topic.status} ${topic.status}`;
  statusChip.textContent = (topic.status || "active").replace("_", " ");
  top.appendChild(statusChip);

  card.appendChild(top);

  if (topic.description) {
    const d = document.createElement("div");
    d.className = "topic-card-desc";
    d.textContent = topic.description;
    card.appendChild(d);
  }
  if (topic.why_it_matters) {
    const w = document.createElement("div");
    w.className = "topic-card-why";
    w.innerHTML = `<span class="topic-card-why-label">Why it matters</span>${escapeHtml(topic.why_it_matters)}`;
    card.appendChild(w);
  }

  const meta = document.createElement("div");
  meta.className = "topic-card-meta";

  // Owner — inline-editable via prompt for now.
  const ownerSpan = document.createElement("span");
  ownerSpan.innerHTML = topic.owner
    ? `Owner: <strong>${escapeHtml(topic.owner)}</strong>`
    : `<em>No owner</em>`;
  const setOwnerBtn = document.createElement("button");
  setOwnerBtn.className = "tile-btn";
  setOwnerBtn.style.padding = "2px 6px";
  setOwnerBtn.textContent = topic.owner ? "Change" : "Set owner";
  setOwnerBtn.onclick = async () => {
    const v = prompt("Owner:", topic.owner || "");
    if (v === null) return;
    await updateTopic(topic.id, { owner: v });
  };
  meta.append(ownerSpan, setOwnerBtn);

  // Linked-nodes count
  const linkedCount = document.createElement("span");
  linkedCount.innerHTML = `Linked to <strong>${topic.linked_nodes_count || 0}</strong> nodes`;
  meta.appendChild(linkedCount);

  // Activation toggle
  const toggleLabel = document.createElement("label");
  toggleLabel.className = "activated-toggle";
  toggleLabel.innerHTML = `<input type="checkbox" ${topic.is_activated ? "checked" : ""}/> Activated`;
  toggleLabel.querySelector("input").onchange = async (e) => {
    await updateTopic(topic.id, { is_activated: e.target.checked });
  };
  meta.appendChild(toggleLabel);

  card.appendChild(meta);
  return card;
}

async function updateTopic(topicId, fields) {
  try {
    await api(`/sustainability/topics/${topicId}`, {
      method: "PUT",
      body: JSON.stringify(fields),
    });
    // Invalidate caches and re-render
    state.allTopics = null;
    state.topicsByNode.clear();
    renderSustainabilityPanel();
    renderRightPane();
    toast("Saved");
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
  }
}

// ---- Per-tile Topic Link modal (4 theme tabs) ----

let topicDialogCtx = { node: null, theme: "environment" };

async function openTopicDialog(node) {
  topicDialogCtx = { node, theme: "environment" };
  $("topic-dialog-title").textContent = `Link Sustainability Topic to ${node.code} — ${node.name}`;
  // Reset tab UI to Environment
  document.querySelectorAll("#topic-dialog .modal-tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.theme === "environment");
  });
  await ensureAllTopicsLoaded();
  await ensureTopicsLoaded(node.id);
  renderTopicDialogBody();
  $("topic-dialog").showModal();
}

function renderTopicDialogBody() {
  const { node, theme } = topicDialogCtx;
  const body = $("topic-dialog-body");
  body.innerHTML = "";
  const topics = (state.allTopics || []).filter((t) => t.theme === theme);
  const linked = new Set((state.topicsByNode.get(node.id) || []).map((t) => t.id));

  if (topics.length === 0) {
    const empty = document.createElement("div");
    empty.className = "drawer-empty";
    empty.textContent = "No topics in this theme.";
    body.appendChild(empty);
    return;
  }

  topics.forEach((t) => {
    const row = document.createElement("div");
    row.className = "topic-row" + (linked.has(t.id) ? " is-linked" : "");

    const info = document.createElement("div");
    info.className = "topic-info";
    const name = document.createElement("div");
    name.className = "topic-name";
    name.textContent = t.name;
    const sub = document.createElement("div");
    sub.className = "topic-sub";
    sub.textContent = t.description || "";
    info.append(name, sub);

    const isLinked = linked.has(t.id);
    const btn = document.createElement("button");
    btn.className = "topic-action " + (isLinked ? "is-unlink" : "is-link");
    btn.textContent = isLinked ? "Unlink" : "Link";
    btn.onclick = async (e) => {
      e.stopPropagation();
      try {
        if (isLinked) {
          await api(`/nodes/${node.id}/sustainability-topics/${t.id}`, { method: "DELETE" });
        } else {
          await api(`/nodes/${node.id}/sustainability-topics/${t.id}`, { method: "POST" });
        }
        state.topicsByNode.delete(node.id);
        state.allTopics = null;
        await ensureTopicsLoaded(node.id);
        await ensureAllTopicsLoaded();
        renderTopicDialogBody();
        renderRightPane();
      } catch (err) {
        toast(`${isLinked ? "Unlink" : "Link"} failed: ${err.message}`, true);
      }
    };

    row.append(info, btn);
    body.appendChild(row);
  });
}

document.querySelectorAll("#topic-dialog .modal-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    topicDialogCtx.theme = btn.dataset.theme;
    document.querySelectorAll("#topic-dialog .modal-tab").forEach((b) => {
      b.classList.toggle("active", b === btn);
    });
    renderTopicDialogBody();
  });
});

$("topic-dialog-close").addEventListener("click", () => $("topic-dialog").close());


// ---------- Boot ----------

$("back-btn").addEventListener("click", () => navigateUp());

checkHealth();
loadTree().catch((e) => toast(`Failed to load: ${e.message}`, true));
