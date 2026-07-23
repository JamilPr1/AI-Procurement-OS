/* AI Procurement CRM — frontend */

function getCrmUser() {
  try {
    return JSON.parse(sessionStorage.getItem("crm_user") || "null");
  } catch {
    return null;
  }
}

const CRM_USER = getCrmUser();
if (!CRM_USER?.token) {
  const next = encodeURIComponent(location.pathname + location.search + location.hash);
  location.replace(`/login?next=${next}`);
  throw new Error("auth_required");
}

let currentRunId = null;
let autoApprove = true;
let allLeads = [];
let allSuppliers = [];
let currentPage = "dashboard";
let lastGateNotifiedKey = null;

const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

const PAGE_META = {
  dashboard: { title: "Dashboard", subtitle: "Overview of your sourcing operation" },
  leads: { title: "Leads", subtitle: "All discovered buyers — persisted and deduplicated" },
  "hot-leads": { title: "Hot Leads", subtitle: "Step-by-step pipeline — review each stage before continuing" },
  tracking: { title: "Deal Tracking", subtitle: "Active deals — production, fulfillment, and client follow-up" },
  "closed-deals": { title: "Closed Deals", subtitle: "Won deals and revenue archive" },
  suppliers: { title: "Suppliers", subtitle: "Verified manufacturers from live search" },
  saas: { title: "SaaS Platform", subtitle: "Multi-tenant stores — provision customers and share AI Product Finder links" },
};

// ── Navigation ──

const VALID_PAGES = Object.keys(PAGE_META);

function pageFromHash() {
  let page = (location.hash || "#dashboard").slice(1).toLowerCase();
  if (page === "deals") page = "hot-leads"; // legacy redirect
  return VALID_PAGES.includes(page) ? page : "dashboard";
}

function navigate(page, { fromHash = false } = {}) {
  if (!VALID_PAGES.includes(page)) page = "dashboard";
  currentPage = page;

  if (!fromHash) {
    const hash = `#${page}`;
    if (location.hash !== hash) location.hash = page;
  }

  $$(".page").forEach((p) => p.classList.remove("active"));
  $$(".nav-item").forEach((n) => n.classList.remove("active"));
  $(`page-${page}`)?.classList.add("active");
  document.querySelector(`[data-page="${page}"]`)?.classList.add("active");
  const meta = PAGE_META[page] || {};
  $("pageTitle").textContent = meta.title || page;
  $("pageSubtitle").textContent = meta.subtitle || "";
  if (page === "leads") loadLeads();
  if (page === "hot-leads") loadHotLeads();
  if (page === "tracking") loadTracking();
  if (page === "closed-deals") loadClosedDeals();
  if (page === "suppliers") loadSuppliers();
  if (page === "saas") loadSaas();
  if (page === "dashboard") loadDashboard();
}

window.addEventListener("hashchange", () => {
  const page = pageFromHash();
  if (page !== currentPage) navigate(page, { fromHash: true });
});

$$(".nav-item").forEach((btn) => {
  btn.onclick = () => navigate(btn.dataset.page);
});

// ── Logging ──

function log(msg, cls = "", target = "logFeed") {
  const feed = $(target);
  if (!feed) return;
  const el = document.createElement("div");
  el.className = `entry ${cls}`;
  const ts = new Date().toLocaleTimeString();
  el.innerHTML = `<span class="ts">[${ts}]</span><span class="msg">${esc(msg)}</span>`;
  feed.prepend(el);
  while (feed.children.length > 200) feed.lastChild.remove();
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function fmtDate(iso) {
  if (!iso) return "-";
  try { return new Date(iso).toLocaleString(); } catch { return iso.slice(0, 16); }
}

function scoreClass(s) {
  if (s >= 80) return "score-high";
  if (s >= 60) return "score-mid";
  return "score-low";
}

// ── Data loaders ──

async function loadOverview() {
  const res = await fetch("/api/overview");
  const data = await res.json();
  const s = data.stats || {};
  $("badgeLeads").textContent = s.leads || 0;
  $("badgeSuppliers").textContent = s.suppliers || 0;
  const r = data.revenue || {};
  if ($("badgeTracking")) $("badgeTracking").textContent = r.tracking_count || 0;
  if ($("badgeContacts")) $("badgeContacts").textContent = data.contacts_count ?? 0;
  if ($("badgeClosed")) $("badgeClosed").textContent = r.closed_count || 0;
  if (data.active_run_id && !currentRunId) currentRunId = data.active_run_id;
  return data;
}

async function loadDashboard() {
  const data = await loadOverview();
  const s = data.stats || {};
  const r = data.revenue || {};
  $("kpiRow").innerHTML = [
    { v: s.leads, l: "Leads" },
    { v: r.tracking_count ?? 0, l: "Tracking" },
    { v: `$${(r.pipeline_expected_usd || 0).toLocaleString()}`, l: "Client $" },
    { v: `$${(r.factory_cost_usd || 0).toLocaleString()}`, l: "Factory Cost" },
    { v: `$${(r.margin_usd || 0).toLocaleString()}`, l: "Gross Margin" },
    { v: `${r.margin_percent ?? 0}%`, l: "Margin %" },
    { v: r.closed_count ?? 0, l: "Closed" },
  ].map((k) => `<div class="kpi"><div class="val">${k.v ?? 0}</div><div class="lbl">${k.l}</div></div>`).join("");

  const ar = data.active_run;
  if (ar && ar.status) {
    const lead = ar.summary?.lead || {};
    $("dashPipeline").innerHTML = `
      <div class="kv"><span>Status</span><span class="status-pill status-${ar.status}">${ar.status}</span></div>
      <div class="kv"><span>Stage</span><span>${ar.current_stage || "-"}</span></div>
      <div class="kv"><span>Lead</span><span>${lead.company || "-"}</span></div>
      <div class="kv"><span>Email</span><span>${lead.email || "-"}</span></div>
    `;
    if (ar.stages) renderStages(ar.stages, ar.status);
  } else {
    $("dashPipeline").innerHTML = '<p class="empty">No active run. Click <strong>Discover Leads</strong> to find US buyers.</p>';
  }

  if (typeof loadDashboardAgents === "function") loadDashboardAgents();
}

async function loadLeads() {
  const res = await fetch("/api/leads");
  const { leads } = await res.json();
  allLeads = leads;
  renderLeads(leads);
}

function renderLeads(leads) {
  const tbody = $("tableLeads")?.querySelector("tbody");
  if (!tbody) return;
  if (!leads.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">No leads yet. Run the pipeline to discover buyers.</td></tr>';
    return;
  }
  tbody.innerHTML = leads.map((l) => `
    <tr data-id="${l.id}" class="clickable-row" title="Click to view full lead profile">
      <td><strong>${esc(l.company_name)}</strong> <span class="row-hint">↗</span></td>
      <td>${l.email ? `<a class="link" href="mailto:${esc(l.email)}">${esc(l.email)}</a>` : "-"}</td>
      <td>${l.website ? `<a class="link" href="${esc(l.website)}" target="_blank">${esc(l.domain || l.website)}</a>` : "-"}</td>
      <td><span class="score-pill ${scoreClass(l.lead_score)}">${Math.round(l.lead_score)}</span></td>
      <td><span class="status-pill status-${l.status}">${l.status}</span></td>
      <td>${fmtDate(l.updated_at)}</td>
    </tr>
  `).join("");
  tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.onclick = () => showLeadDetail(tr.dataset.id);
  });
}

async function loadSuppliers() {
  const res = await fetch("/api/suppliers");
  const { suppliers } = await res.json();
  allSuppliers = suppliers;
  renderSuppliers(suppliers);
}

function renderSuppliers(suppliers) {
  const tbody = $("tableSuppliers")?.querySelector("tbody");
  if (!tbody) return;
  if (!suppliers.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">No suppliers yet.</td></tr>';
    return;
  }
  tbody.innerHTML = suppliers.map((s) => `
    <tr data-id="${s.id}" class="clickable-row" title="Click to view supplier profile">
      <td><strong>${esc(s.factory_name?.slice(0, 60))}</strong> <span class="row-hint">↗</span></td>
      <td>${esc(s.platform || "-")}</td>
      <td>${s.price ? `$${s.price}` : "-"}</td>
      <td>${s.moq || "-"}</td>
      <td><span class="score-pill ${scoreClass(s.trust_score)}">${Math.round(s.trust_score)}</span></td>
      <td>${fmtDate(s.updated_at)}</td>
    </tr>
  `).join("");
  tbody.querySelectorAll("tr[data-id]").forEach((tr) => {
    tr.onclick = () => showSupplierDetail(tr.dataset.id);
  });
}

async function loadAgents() {
  const res = await fetch("/api/agents");
  const { agents } = await res.json();
  $("agentGrid").innerHTML = agents.map((a) => {
    const st = a.status || "idle";
    const dotCls = st === "running" ? "running" : (a.last_status === "error" ? "error" : (a.last_status === "success" ? "success" : "idle"));
    const mode = a.model === "fallback" ? "rule-based" : (a.model || "");
    return `<div class="agent-card ${st === "running" ? "running" : ""} ${a.last_status === "success" ? "agent-ok" : ""}">
      <div class="agent-num">Stage ${a.stage_num}</div>
      <div class="agent-name">${esc(a.name)}</div>
      <div style="font-size:0.7rem;color:var(--muted)">${esc(a.id)}</div>
      <div class="agent-status">
        <span class="agent-dot ${dotCls}"></span>
        ${st === "running" ? "Running now" : (a.last_run ? `Last: ${a.last_status || "ok"}` : "Ready")}
      </div>
      ${mode ? `<div style="font-size:0.65rem;color:var(--muted);margin-top:0.25rem">${esc(mode)}${a.duration_ms ? ` · ${a.duration_ms}ms` : ""}</div>` : ""}
      ${a.has_gate ? `<div style="font-size:0.65rem;color:var(--orange);margin-top:0.3rem">Human gate</div>` : ""}
    </div>`;
  }).join("");
}

$("btnTestAgents")?.addEventListener("click", async () => {
  const btn = $("btnTestAgents");
  const status = $("agentTestStatus");
  btn.disabled = true;
  status.textContent = "Testing all 13 agents...";
  try {
    const res = await fetch("/api/agents/test-all", { method: "POST" });
    const data = await res.json();
    status.textContent = `${data.passed}/${data.total} agents passed`;
    status.style.color = data.passed === data.total ? "var(--green)" : "var(--orange)";
    await loadAgents();
  } catch (e) {
    status.textContent = "Test failed";
    status.style.color = "var(--red)";
  }
  btn.disabled = false;
});

async function loadActivity() {
  const res = await fetch("/api/activity?limit=150");
  const { logs, live_events } = await res.json();
  const feed = $("activityLog");
  feed.innerHTML = "";
  const combined = [
    ...live_events.map((e) => ({
      timestamp: e.timestamp,
      message: `[${e.type}] ${JSON.stringify(e.data || {}).slice(0, 120)}`,
      cls: e.type === "human_gate" ? "gate" : (e.type === "run_failed" ? "error" : ""),
    })),
    ...logs.map((l) => ({
      timestamp: l.timestamp,
      message: l.message || l.data?.message || JSON.stringify(l).slice(0, 100),
      cls: l.level === "ERROR" ? "error" : "",
    })),
  ].sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""));

  if (!combined.length) {
    feed.innerHTML = '<div class="empty">No activity yet.</div>';
    return;
  }
  combined.slice(0, 150).forEach((e) => {
    const el = document.createElement("div");
    el.className = `entry ${e.cls}`;
    el.innerHTML = `<span class="ts">${e.timestamp ? fmtDate(e.timestamp) : ""}</span><span class="msg">${esc(e.message)}</span>`;
    feed.appendChild(el);
  });
}

async function loadRoadmap() {
  const res = await fetch("/api/roadmap");
  const { phases, crm_pages } = await res.json();

  const pagesEl = $("roadmapPages");
  if (pagesEl && crm_pages) {
    pagesEl.innerHTML = `<h3 class="roadmap-section-title">CRM Pages (no duplicates)</h3><div class="crm-page-grid">${
      crm_pages.map((p) => `<div class="crm-page-card">
        <strong>${esc(p.label)}</strong>
        <span class="hint">${esc(p.purpose)}</span>
      </div>`).join("")
    }</div>`;
  }

  $("roadmap").innerHTML = phases.map((p) => {
    const done = p.items.filter((i) => i.status === "completed").length;
    const total = p.items.length;
    return `<div class="phase ${p.status}">
      <div class="phase-head">
        <h3>${esc(p.name)}</h3>
        <span class="phase-progress">${done}/${total} done</span>
      </div>
      <div class="phase-status">${p.status.replace("_", " ")}</div>
      <ul class="roadmap-items">${p.items.map((i) => {
        const icon = i.status === "completed" ? "✓" : i.status === "in_progress" ? "◐" : "○";
        const page = i.ui_page ? `<a class="link" href="#${esc(i.ui_page)}">${esc(i.ui_page)}</a>` : "—";
        return `<li class="roadmap-item ${i.status}">
          <span class="ri-icon">${icon}</span>
          <span class="ri-name">${esc(i.name)}</span>
          <span class="ri-page">${page}</span>
          <span class="ri-note">${esc(i.note || "")}</span>
        </li>`;
      }).join("")}</ul>
    </div>`;
  }).join("");

  loadIntegrationList();
}

async function loadIntegrationList() {
  const el = $("integrationList");
  if (!el) return;
  const res = await fetch("/api/roadmap/integrations");
  const { integrations } = await res.json();
  const byPhase = {};
  for (const item of integrations) {
    const p = item.phase || "Other";
    if (!byPhase[p]) byPhase[p] = [];
    byPhase[p].push(item);
  }
  el.innerHTML = Object.entries(byPhase).map(([phase, items]) => `
    <div class="integration-phase">
      <h4>${esc(phase)}</h4>
      <ul>${items.map((i) => `<li class="int-${i.priority}">
        <strong>${esc(i.name)}</strong> — ${esc(i.description)}
        ${i.blocker ? `<span class="tag">${esc(i.blocker)}</span>` : ""}
      </li>`).join("")}</ul>
    </div>
  `).join("");
}

// ── Pipeline ──

function renderStages(stages, runStatus) {
  const list = $("stageList");
  if (!list) return;
  list.innerHTML = "";
  let done = 0;
  stages.forEach((s) => {
    if (s.status === "completed") done++;
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="dot ${s.status}"></div>
      <span class="stage-label">${s.num}. ${esc(s.label)}</span>
      ${s.gate_label ? `<span class="stage-gate">gate</span>` : ""}
    `;
    list.appendChild(li);
  });
  const fill = $("progressFill");
  if (fill) fill.style.width = `${stages.length ? (done / stages.length) * 100 : 0}%`;
}

function renderSummary(data) {
  const box = $("runSummary");
  if (!box) return;
  if (!data || !data.summary) {
    box.innerHTML = `<div class="kv"><span>Status</span><span>${data?.status || "idle"}</span></div>
      ${data?.current_stage ? `<div class="kv"><span>Stage</span><span>${data.current_stage}</span></div>` : ""}`;
    return;
  }
  const s = data.summary;
  const lead = s.lead || {};
  box.innerHTML = `
    <div class="kv"><span>Status</span><span class="status-pill status-${data.status}">${data.status}</span></div>
    <div class="kv"><span>Lead</span><span>${esc(lead.company || "-")}</span></div>
    <div class="kv"><span>Email</span><span>${esc(lead.email || "-")}</span></div>
    <div class="kv"><span>Website</span><span>${esc(lead.website || "-")}</span></div>
    <div class="kv"><span>Score</span><span>${lead.score ?? "-"}</span></div>
    <div class="kv"><span>Supplier</span><span>${esc(s.recommended_supplier || "-")}</span></div>
    <div class="kv"><span>Client price</span><span>$${(s.client_price_usd || 0).toLocaleString()}</span></div>
    <div class="kv"><span>Elapsed</span><span>${s.elapsed_seconds || "-"}s</span></div>
  `;
}

function notifyGateOnce(gateKey, label) {
  if (!gateKey || lastGateNotifiedKey === gateKey) return;
  lastGateNotifiedKey = gateKey;
  if (typeof Notification !== "undefined" && Notification.permission === "granted") {
    new Notification("Approval Required", { body: label || "Review required in dashboard" });
  }
}

function showGate(data, { notify = false } = {}) {
  const banner = $("gateBanner");
  if (!banner) return;
  if (data?.status === "paused" && data.pending_gate) {
    banner.classList.remove("hidden");
    const label = data.pending_gate_label || data.pending_gate;
    $("gateLabel").textContent = label;
    if (notify) {
      notifyGateOnce(`${data.pending_gate}:${currentRunId || ""}`, label);
    }
  } else {
    banner.classList.add("hidden");
    if (!data?.pending_gate) lastGateNotifiedKey = null;
  }
}

async function refreshRun() {
  if (!currentRunId) {
    const res = await fetch("/api/runs/active");
    const data = await res.json();
    if (data.active) currentRunId = data.run_id;
  }
  if (!currentRunId) return;
  const res = await fetch(`/api/runs/${currentRunId}`);
  const data = await res.json();
  renderStages(data.stages || [], data.status);
  renderSummary(data);
  showGate(data);
  return data;
}

// ── SSE ──

function connectSSE() {
  const es = new EventSource("/api/events");
  es.onopen = () => {
    $("connStatus").textContent = "Live";
    $("connStatus").classList.add("ok");
  };
  es.onerror = () => {
    $("connStatus").textContent = "Reconnecting";
    $("connStatus").classList.remove("ok");
  };
  es.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === "ping") return;

    if (ev.type === "log") {
      log(ev.data.message);
      if (currentPage === "dashboard") log(ev.data.message, "", "dashActivity");
    }
    if (ev.type === "stage_started") {
      log(`Stage started: ${ev.data.label}`, "", "logFeed");
      if (currentPage === "dashboard") log(`Stage started: ${ev.data.label}`, "", "dashActivity");
      loadAgents();
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
    }
    if (ev.type === "stage_completed") {
      log(`Stage done: ${ev.data.stage}`, "done", "logFeed");
      if (currentPage === "dashboard") log(`Stage done: ${ev.data.stage}`, "done", "dashActivity");
      loadAgents();
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
    }
    if (ev.type === "lead_stage_started" || ev.type === "lead_stage_completed") {
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
    }
    if (ev.type === "human_gate") {
      log(`APPROVAL NEEDED: ${ev.data.label}`, "gate", "logFeed");
      log(`APPROVAL NEEDED: ${ev.data.label}`, "gate", "dashActivity");
      notifyGateOnce(`${ev.data.gate || ev.data.label}:${ev.data.run_id || currentRunId || ""}`, ev.data.label);
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
      refreshRun();
    }
    if (ev.type === "gate_approved") {
      lastGateNotifiedKey = null;
      log("Gate approved — resuming", "done");
    }
    if (ev.type === "run_completed") {
      log(`Pipeline complete in ${ev.data.elapsed_sec}s`, "done");
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
      refreshRun();
      loadOverview();
      loadLeads();
      loadSuppliers();
      if (currentPage === "dashboard") loadDashboard();
      if (typeof loadHotLeads === "function") loadHotLeads();
    }
    if (ev.type === "run_failed") {
      log(`FAILED: ${ev.data.error}`, "error");
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
    }
    if (ev.type === "run_started") {
      log(`Run started: ${ev.data.run_id}`);
      if (typeof onFleetEvent === "function") onFleetEvent(ev);
      if (currentPage === "dashboard" && typeof loadDashboardAgents === "function") loadDashboardAgents();
    }

    if (["stage_started", "stage_completed", "human_gate", "run_completed", "lead_stage_completed"].includes(ev.type)) {
      refreshRun();
    }
    if (ev.type === "lead_stage_completed" && typeof loadHotLeads === "function") {
      if (typeof onHotLeadPipelineEvent === "function") onHotLeadPipelineEvent(ev);
      loadHotLeads();
    }
    if (ev.type === "lead_stage_started" && typeof onHotLeadPipelineEvent === "function") {
      onHotLeadPipelineEvent(ev);
    }
  };
}

// ── SaaS Platform ──

async function loadSaas() {
  const [summaryRes, tenantsRes] = await Promise.all([
    fetch("/api/saas/summary"),
    fetch("/api/saas/tenants"),
  ]);
  const summary = await summaryRes.json();
  const data = await tenantsRes.json();
  const plans = data.plans || summary.plans || {};
  const tenants = data.tenants || [];

  $("saasKpis").innerHTML = `
    <div class="kpi"><div class="kpi-label">Status</div><div class="kpi-value">${esc(summary.status || "—")}</div></div>
    <div class="kpi"><div class="kpi-label">Tenants</div><div class="kpi-value">${summary.tenant_count ?? tenants.length}</div></div>
    <div class="kpi"><div class="kpi-label">Plans</div><div class="kpi-value">${Object.keys(plans).length}</div></div>
  `;

  $("saasPlans").innerHTML = Object.entries(plans).map(([id, p]) => `
    <div class="detail-kv"><span class="detail-kv-label">${esc(id)}</span>
    <span class="detail-kv-value">${p.max_active_deals || "—"} deals · ${p.max_users || "—"} users</span></div>
  `).join("");

  const origin = location.origin;
  $("saasTenantBody").innerHTML = tenants.length ? tenants.map((t) => `
    <tr>
      <td><strong>${esc(t.name)}</strong></td>
      <td><code>${esc(t.slug || "—")}</code></td>
      <td>${esc(t.plan || "starter")}</td>
      <td>${t.active_deals ?? 0} / ${t.plan_limits?.max_active_deals ?? "—"}</td>
      <td>${t.margin_percent ?? 15}%</td>
      <td><a href="${origin}/store?tenant=${encodeURIComponent(t.slug || "")}" target="_blank" rel="noopener">Open store ↗</a></td>
    </tr>
  `).join("") : `<tr><td colspan="6" class="empty">No tenants yet — create one above</td></tr>`;
}

$("btnCreateTenant")?.addEventListener("click", async () => {
  const name = $("saasTenantName")?.value?.trim();
  if (!name) return alert("Company name required");
  const body = {
    name,
    slug: $("saasTenantSlug")?.value?.trim() || undefined,
    plan: $("saasTenantPlan")?.value || "starter",
    margin_percent: Number($("saasTenantMargin")?.value || 15),
    tagline: $("saasTenantTagline")?.value?.trim() || "",
  };
  const res = await fetch("/api/saas/tenants", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) return alert(data.detail || "Failed to create tenant");
  $("saasTenantName").value = "";
  $("saasTenantSlug").value = "";
  $("saasTenantTagline").value = "";
  loadSaas();
  const url = `${location.origin}${data.store_url || `/store?tenant=${data.slug}`}`;
  if (confirm(`Tenant created!\n\nStore URL:\n${url}\n\nOpen in new tab?`)) window.open(url, "_blank");
});

$("btnSeedDemo")?.addEventListener("click", async () => {
  if (!confirm("Seed demo tenants, users, and sample store orders?")) return;
  const res = await fetch("/api/admin/seed-demo", { method: "POST" });
  const data = await res.json();
  if (!res.ok) return alert(data.detail || "Seed failed");
  alert(`Seeded: ${data.tenants_seeded} tenants, ${data.orders_created} orders created`);
  loadSaas();
});

$("btnGenCreds")?.addEventListener("click", async () => {
  const res = await fetch("/api/admin/generate-credentials", { method: "POST" });
  const data = await res.json();
  if (!res.ok) return alert(data.detail || "Failed");
  alert(`Credentials document saved to:\n${data.path}\n\n(${data.users} users, ${data.tenants} tenants)`);
});

// ── Actions ──

$("btnStart").onclick = async () => {
  $("btnStart").disabled = true;
  log("Discovering leads...");
  if (currentPage !== "dashboard") navigate("dashboard");
  const res = await fetch(`/api/runs/start?auto_approve=true`, { method: "POST" });
  const data = await res.json();
  currentRunId = data.run_id;
  log(`Run ID: ${currentRunId}`, "", "dashActivity");
  await loadDashboard();
  loadHotLeads?.();
  $("btnStart").disabled = false;
};

const btnReset = $("btnReset");
if (btnReset) {
  btnReset.onclick = async () => {
    if (!confirm("Delete ALL leads, deals, and suppliers? This cannot be undone.")) return;
    btnReset.disabled = true;
    const res = await fetch("/api/admin/reset?include_suppliers=true", { method: "POST" });
    const data = await res.json();
    log(`Reset complete: ${data.leads_deleted || 0} leads, ${data.deals_deleted || 0} deals removed`);
    loadOverview?.();
    loadLeads?.();
    loadHotLeads?.();
    loadTracking?.();
    loadClosedDeals?.();
    btnReset.disabled = false;
  };
}

$("searchLeads")?.addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  renderLeads(allLeads.filter((l) =>
    l.company_name.toLowerCase().includes(q) ||
    (l.email || "").toLowerCase().includes(q) ||
    (l.domain || "").toLowerCase().includes(q)
  ));
});

$("searchSuppliers")?.addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  renderSuppliers(allSuppliers.filter((s) =>
    (s.factory_name || "").toLowerCase().includes(q) ||
    (s.platform || "").toLowerCase().includes(q)
  ));
});

// Notification permission — only when user enables browser notifications (no auto-prompt spam)
// Users can enable in browser site settings if desired.

// Init — auth UI + restore page from URL hash
(function initAuthUi() {
  const badge = $("userBadge");
  if (badge && CRM_USER) {
    const role = CRM_USER.role === "superadmin" ? "Super Admin" : "Tenant";
    badge.innerHTML = `<strong>${esc(CRM_USER.name || CRM_USER.email)}</strong><br><span class="muted">${role} · ${esc(CRM_USER.tenant_name || "")}</span>`;
  }
  if (CRM_USER.role !== "superadmin") {
    document.querySelector('[data-page="saas"]')?.remove();
    if (pageFromHash() === "saas") navigate("dashboard", { fromHash: true });
  }
  $("btnLogout")?.addEventListener("click", () => {
    sessionStorage.removeItem("crm_user");
    location.href = "/login?logout=1";
  });

  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("sidebarOverlay");
  const toggle = document.getElementById("sidebarToggle");
  const closeSidebar = () => {
    sidebar?.classList.remove("open");
    overlay?.classList.remove("open");
  };
  toggle?.addEventListener("click", () => {
    sidebar?.classList.toggle("open");
    overlay?.classList.toggle("open");
  });
  overlay?.addEventListener("click", closeSidebar);
  document.querySelectorAll(".sidebar-nav .nav-item").forEach((btn) => {
    btn.addEventListener("click", closeSidebar);
  });
})();

if (!location.hash) history.replaceState(null, "", "#dashboard");
navigate(pageFromHash(), { fromHash: true });
connectSSE();
setInterval(() => {
  loadOverview();
  if (currentRunId) refreshRun();
  if (currentPage === "dashboard" && typeof loadDashboardAgents === "function") loadDashboardAgents();
}, 5000);
