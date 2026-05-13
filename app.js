// Business Process Repository — frontend
// Talks to the FastAPI backend at the same origin.

const API_BASE = (() => {
  // Allow overriding via ?api=http://... for dev, otherwise same origin.
  const params = new URLSearchParams(location.search);
  if (params.get("api")) return params.get("api").replace(/\/$/, "");
  return location.origin;
})();

const state = {
  tree: [],
  byId: new Map(),
  selectedId: null,
  collapsed: new Set(),
};

const LEVEL_NAMES = {
  1: "L1 · Business Domain",
  2: "L2 · Function",
  3: "L3 · Process Group",
  4: "L4 · Terminal Process",
};

// ---------- API ----------

async function api(path, opts = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { detail = res.statusText; }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return null;
  return res.json();
}

async function checkHealth() {
  const el = document.getElementById("health-indicator");
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
  renderTree();
  if (state.selectedId && state.byId.has(state.selectedId)) {
    renderDetail(state.byId.get(state.selectedId));
  }
}

// ---------- Tree rendering ----------

function renderTree() {
  const container = document.getElementById("tree");
  container.innerHTML = "";
  if (state.tree.length === 0) {
    container.innerHTML = '<p class="muted" style="padding:16px;">No nodes yet. Click "+ L1 Domain" to create your first Business Domain.</p>';
    return;
  }
  state.tree.forEach((n) => container.appendChild(renderNode(n)));
}

function renderNode(node) {
  const wrap = document.createElement("div");
  wrap.className = "tree-node";
  wrap.dataset.id = node.id;

  const row = document.createElement("div");
  row.className = "tree-row";
  if (node.id === state.selectedId) row.classList.add("selected");
  row.style.paddingLeft = `${8 + (node.level - 1) * 4}px`;

  const hasChildren = node.children && node.children.length > 0;
  const isCollapsed = state.collapsed.has(node.id);

  const toggle = document.createElement("span");
  toggle.className = hasChildren ? "toggle" : "toggle placeholder";
  toggle.textContent = hasChildren ? (isCollapsed ? "▶" : "▼") : "·";
  toggle.onclick = (e) => {
    e.stopPropagation();
    if (!hasChildren) return;
    if (isCollapsed) state.collapsed.delete(node.id);
    else state.collapsed.add(node.id);
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
  row.onclick = () => selectNode(node.id);

  wrap.appendChild(row);

  if (hasChildren) {
    const childWrap = document.createElement("div");
    childWrap.className = "children" + (isCollapsed ? " collapsed" : "");
    node.children.forEach((c) => childWrap.appendChild(renderNode(c)));
    wrap.appendChild(childWrap);
  }

  return wrap;
}

function selectNode(id) {
  state.selectedId = id;
  renderTree();
  const node = state.byId.get(id);
  if (node) renderDetail(node);
}

// ---------- Detail panel ----------

function $(id) { return document.getElementById(id); }

function renderDetail(node) {
  $("empty-state").style.display = "none";
  $("detail-form").style.display = "flex";

  $("d-level").textContent = LEVEL_NAMES[node.level] || `L${node.level}`;
  $("d-code-chip").textContent = node.code;

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
}

function clearDetail() {
  state.selectedId = null;
  $("detail-form").style.display = "none";
  $("empty-state").style.display = "flex";
}

$("detail-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (!state.selectedId) return;
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
    await api(`/nodes/${state.selectedId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
    toast("Saved");
    await loadTree();
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
  }
});

$("delete-btn").addEventListener("click", async () => {
  if (!state.selectedId) return;
  const node = state.byId.get(state.selectedId);
  const msg = node.children && node.children.length > 0
    ? `Delete "${node.name}" AND its ${countDescendants(node)} descendant(s)? This cannot be undone.`
    : `Delete "${node.name}"?`;
  if (!confirm(msg)) return;
  try {
    await api(`/nodes/${state.selectedId}`, { method: "DELETE" });
    clearDetail();
    toast("Deleted");
    await loadTree();
  } catch (err) {
    toast(`Delete failed: ${err.message}`, true);
  }
});

function countDescendants(node) {
  if (!node.children) return 0;
  return node.children.reduce((sum, c) => sum + 1 + countDescendants(c), 0);
}

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
  if (level > 4) {
    toast("L4 is terminal — cannot add child", true);
    return;
  }
  const payload = {
    parent_id: parent ? parent.id : null,
    level,
    code: $("add-code").value.trim(),
    name: $("add-name").value.trim(),
    description: $("add-description").value || null,
    owner: $("add-owner").value || null,
    status: $("add-status").value,
  };
  if (!payload.code || !payload.name) {
    toast("Code and name are required", true);
    return;
  }
  try {
    const created = await api("/nodes", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("add-dialog").close();
    toast("Created");
    if (parent) state.collapsed.delete(parent.id); // expand parent so new node shows
    await loadTree();
    selectNode(created.id);
  } catch (err) {
    toast(`Create failed: ${err.message}`, true);
  }
});

$("add-root-btn").addEventListener("click", () => openAddDialog(null));
$("add-child-btn").addEventListener("click", () => {
  if (!state.selectedId) return;
  openAddDialog(state.byId.get(state.selectedId));
});

// ---------- Auto-compute next review date in the form ----------

function recomputeNextReviewDate() {
  const last = $("f-last-review-date").value;
  const freq = $("f-review-frequency").value;
  if (!last || !freq) {
    $("f-next-review-date").value = "";
    return;
  }
  const d = new Date(last + "T00:00:00");
  if (freq === "monthly") d.setMonth(d.getMonth() + 1);
  else if (freq === "quarterly") d.setMonth(d.getMonth() + 3);
  else if (freq === "annually") d.setFullYear(d.getFullYear() + 1);
  $("f-next-review-date").value = d.toISOString().slice(0, 10);
}
$("f-last-review-date").addEventListener("change", recomputeNextReviewDate);
$("f-review-frequency").addEventListener("change", recomputeNextReviewDate);

// ---------- Toast ----------

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.className = "toast"; }, 2500);
}

// ---------- Boot ----------

checkHealth();
loadTree().catch((e) => toast(`Failed to load: ${e.message}`, true));
