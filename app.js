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
  docsByNode: new Map(),        // node_id -> Document[]  (also serves as doc-count cache)
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

  // Compact "+ Doc" button gives users an upload affordance even when the
  // tile currently shows no badges (otherwise uploads would only be reachable
  // by clicking an existing per-type badge, which doesn't exist for the first
  // document of any node).
  const uploadBtn = document.createElement("button");
  uploadBtn.className = "tile-btn";
  uploadBtn.title = "Upload document";
  uploadBtn.innerHTML = `<span class="icon">+</span> Doc`;
  uploadBtn.onclick = (e) => {
    e.stopPropagation();
    openDocDialog(node, null);
  };
  actions.appendChild(uploadBtn);

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

  // Doc-type badges row pinned to the bottom of the tile (via margin-top:auto
  // in CSS). Hidden when the node has no documents.
  const badges = renderDocBadges(node);
  if (badges) wrap.appendChild(badges);

  // Clicking the tile body (but not buttons or badges) drills into the branch
  // — except for the header tile, which is already focused.
  if (variant !== "header") {
    wrap.onclick = (e) => {
      if (e.target.closest("button, .doc-badge")) return;
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
  drawerCtx = { nodeId: node.id, bucket };
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

  renderDrawerBody();
  $("docs-drawer").showModal();
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

$("drawer-upload-btn").addEventListener("click", () => {
  if (drawerCtx.nodeId === null) return;
  const node = state.byId.get(drawerCtx.nodeId);
  // Pre-select the doc type matching this drawer's badge. Misc has no
  // server-side equivalent, so it falls back to the first concrete type.
  const prefill = drawerCtx.bucket === MISC_BUCKET ? null : drawerCtx.bucket;
  openDocDialog(node, null, prefill);
});

function renderDocRow(doc, node) {
  const row = document.createElement("div");
  row.className = "doc-row";

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

  const dl = document.createElement("button");
  dl.textContent = "Download";
  dl.title = "Download";
  dl.onclick = (e) => { e.stopPropagation(); downloadDoc(doc.id); };

  const edit = document.createElement("button");
  edit.textContent = "Edit";
  edit.title = "Edit metadata";
  edit.onclick = (e) => { e.stopPropagation(); openDocDialog(node, doc); };

  const del = document.createElement("button");
  del.className = "danger";
  del.textContent = "Delete";
  del.title = "Delete document";
  del.onclick = (e) => { e.stopPropagation(); deleteDoc(doc); };

  actions.append(dl, edit, del);
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
    const r = await api(`/documents/${docId}/download`);
    window.open(r.url, "_blank", "noopener");
  } catch (err) {
    toast(`Download failed: ${err.message}`, true);
  }
}

async function deleteDoc(doc) {
  if (!confirm(`Delete "${doc.original_filename}"? This removes the file from storage and cannot be undone.`)) return;
  try {
    await api(`/documents/${doc.id}`, { method: "DELETE" });
    state.docsByNode.delete(doc.node_id);
    await ensureDocsLoaded(doc.node_id);
    renderRightPane();
    toast("Document deleted");
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
}

// ---------- Document upload / edit dialog ----------

let docContext = { node: null, doc: null };

function openDocDialog(node, doc, prefillType = null) {
  docContext = { node, doc };
  $("doc-title").textContent = doc
    ? `Edit document — ${doc.original_filename}`
    : `Upload document to ${node.code} — ${node.name}`;

  $("doc-file-wrap").style.display = doc ? "none" : "";
  $("doc-file").value = "";

  // Pre-select doc type: existing doc's type when editing, the badge's type
  // when uploading from a drawer, otherwise the first concrete enum value.
  $("doc-type").value = doc ? doc.doc_type : (prefillType || "procedure");
  $("doc-version").value = doc ? (doc.version || "") : "";
  $("doc-owner").value = doc ? (doc.owner || "") : "";
  $("doc-review-frequency").value = doc ? (doc.review_frequency || "") : "";
  $("doc-last-review-date").value = doc ? (doc.last_review_date || "") : "";
  $("doc-next-review-date").value = doc ? (doc.next_review_date || "") : "";
  $("doc-tags").value = doc ? (doc.tags || "") : "";
  $("doc-notes").value = doc ? (doc.notes || "") : "";

  renderTagChips($("doc-tags").value);
  updateDocFieldRequirements();
  $("doc-dialog").showModal();
}

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
      };
      await api(`/documents/${doc.id}`, { method: "PUT", body: JSON.stringify(payload) });
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

      await api(`/nodes/${node.id}/documents`, { method: "POST", body: fd });
      toast("Document uploaded");
    }
    $("doc-dialog").close();
    state.docsByNode.delete(node.id);
    await ensureDocsLoaded(node.id);
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

// ---------- Toast ----------

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast"; }, 2800);
}

// ---------- Boot ----------

$("back-btn").addEventListener("click", () => navigateUp());

checkHealth();
loadTree().catch((e) => toast(`Failed to load: ${e.message}`, true));
