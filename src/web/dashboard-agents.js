/* Dashboard AI Agent Fleet — human team cards with live task status */

const AGENT_PERSONAS = {
  niche_finder: {
    humanName: "Priya Sharma",
    designation: "Market Research Manager",
    color: "#a78bfa",
    task: "Scanning trends for top niche…",
    avatar: { skin: "#c68642", hair: "#1a1208", shirt: "#6366f1", hairStyle: "bun" },
  },
  lead_discovery: {
    humanName: "Marcus Webb",
    designation: "Lead Generation Specialist",
    color: "#38bdf8",
    task: "Searching web for buyers…",
    avatar: { skin: "#e0ac69", hair: "#3d2314", shirt: "#0ea5e9", hairStyle: "short" },
  },
  company_research: {
    humanName: "Elena Vasquez",
    designation: "Business Research Analyst",
    color: "#34d399",
    task: "Reading company website…",
    avatar: { skin: "#d4a574", hair: "#2d1f14", shirt: "#10b981", hairStyle: "long" },
  },
  personalization: {
    humanName: "James Okonkwo",
    designation: "Content Writer",
    color: "#f472b6",
    task: "Drafting personalization…",
    avatar: { skin: "#6b4423", hair: "#0f0f0f", shirt: "#ec4899", hairStyle: "curly" },
  },
  outreach: {
    humanName: "Sophie Laurent",
    designation: "Outreach Manager",
    color: "#60a5fa",
    task: "Composing outreach email…",
    avatar: { skin: "#f5d0b0", hair: "#8b6914", shirt: "#3b82f6", hairStyle: "bob" },
  },
  qualification: {
    humanName: "David Kim",
    designation: "Sales Qualification Analyst",
    color: "#4ade80",
    task: "Qualifying buyer fit…",
    avatar: { skin: "#f0c8a0", hair: "#1c1c1c", shirt: "#22c55e", hairStyle: "short" },
  },
  product_research: {
    humanName: "Amira Hassan",
    designation: "Product Research Analyst",
    color: "#fbbf24",
    task: "Building product spec…",
    avatar: { skin: "#c68642", hair: "#0a0a0a", shirt: "#f59e0b", hairStyle: "hijab" },
  },
  supplier_discovery: {
    humanName: "Tomás Rivera",
    designation: "Sourcing Manager",
    color: "#fb923c",
    task: "Finding factories…",
    avatar: { skin: "#d4a574", hair: "#2c1810", shirt: "#ea580c", hairStyle: "short" },
  },
  supplier_verification: {
    humanName: "Rachel Foster",
    designation: "Compliance Auditor",
    color: "#2dd4bf",
    task: "Verifying suppliers…",
    avatar: { skin: "#f5d0b0", hair: "#4a3728", shirt: "#14b8a6", hairStyle: "long" },
  },
  rfq: {
    humanName: "Kenji Tanaka",
    designation: "Procurement Coordinator",
    color: "#818cf8",
    task: "Writing RFQ emails…",
    avatar: { skin: "#f0c8a0", hair: "#1a1a1a", shirt: "#6366f1", hairStyle: "short" },
  },
  quote_comparison: {
    humanName: "Olivia Bennett",
    designation: "Pricing Analyst",
    color: "#c084fc",
    task: "Comparing supplier quotes…",
    avatar: { skin: "#e0ac69", hair: "#6b3a2a", shirt: "#a855f7", hairStyle: "bob" },
  },
  proposal: {
    humanName: "Nathan Brooks",
    designation: "Proposal Writer",
    color: "#22d3ee",
    task: "Building client proposal…",
    avatar: { skin: "#f5d0b0", hair: "#3d2817", shirt: "#06b6d4", hairStyle: "short" },
  },
  order_tracking: {
    humanName: "Fatima Al-Rashid",
    designation: "Operations Manager",
    color: "#94a3b8",
    task: "Tracking production…",
    avatar: { skin: "#c68642", hair: "#0f0f0f", shirt: "#64748b", hairStyle: "hijab" },
  },
  finance: {
    humanName: "Michael O'Brien",
    designation: "Finance Manager",
    color: "#facc15",
    task: "Managing invoices…",
    avatar: { skin: "#f5d0b0", hair: "#8b7355", shirt: "#ca8a04", hairStyle: "short" },
  },
  email_drafter: {
    humanName: "Lisa Chen",
    designation: "Communications Specialist",
    color: "#e879f9",
    task: "Preparing email drafts…",
    avatar: { skin: "#f0c8a0", hair: "#1c1c1c", shirt: "#d946ef", hairStyle: "long" },
  },
  customer_support: {
    humanName: "Alex Morgan",
    designation: "Client Support Lead",
    color: "#86efac",
    task: "Handling client queries…",
    avatar: { skin: "#e0ac69", hair: "#2d1f14", shirt: "#4ade80", hairStyle: "curly" },
  },
};

const fleetState = {
  agents: [],
  runningId: null,
  tasks: {},
};

function personaFor(agent) {
  return AGENT_PERSONAS[agent.id] || {
    humanName: "AI Team Member",
    designation: "Specialist",
    color: "#60a5fa",
    task: "Processing…",
    avatar: { skin: "#e0ac69", hair: "#2c1810", shirt: "#3b82f6", hairStyle: "short" },
  };
}

function humanAvatarSvg(persona, agentId) {
  const a = persona.avatar || {};
  const skin = a.skin || "#e0ac69";
  const hair = a.hair || "#2c1810";
  const shirt = a.shirt || persona.color || "#3b82f6";
  const style = a.hairStyle || "short";
  const gradId = `bg-${(agentId || "agent").replace(/[^a-z0-9]/gi, "")}`;

  let hairPaths = "";
  if (style === "long") {
    hairPaths = `<ellipse cx="50" cy="38" rx="34" ry="30" fill="${hair}"/>
      <path d="M18 42 Q16 70 22 88 L78 88 Q84 70 82 42" fill="${hair}"/>`;
  } else if (style === "bob") {
    hairPaths = `<ellipse cx="50" cy="40" rx="32" ry="28" fill="${hair}"/>
      <rect x="20" y="48" width="60" height="22" rx="10" fill="${hair}"/>`;
  } else if (style === "curly") {
    hairPaths = `<circle cx="30" cy="32" r="14" fill="${hair}"/><circle cx="50" cy="26" r="16" fill="${hair}"/>
      <circle cx="70" cy="32" r="14" fill="${hair}"/><circle cx="38" cy="48" r="12" fill="${hair}"/>
      <circle cx="62" cy="48" r="12" fill="${hair}"/>`;
  } else if (style === "bun") {
    hairPaths = `<ellipse cx="50" cy="40" rx="30" ry="26" fill="${hair}"/>
      <circle cx="50" cy="18" r="12" fill="${hair}"/>`;
  } else if (style === "hijab") {
    hairPaths = `<path d="M16 55 Q50 10 84 55 L84 95 Q50 80 16 95 Z" fill="${shirt}" opacity="0.9"/>
      <ellipse cx="50" cy="42" rx="28" ry="24" fill="${hair}" opacity="0.3"/>`;
  } else {
    hairPaths = `<ellipse cx="50" cy="38" rx="30" ry="26" fill="${hair}"/>`;
  }

  return `<svg class="crew-avatar-svg" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
    <defs>
      <linearGradient id="${gradId}" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="${shirt}" stop-opacity="0.35"/>
        <stop offset="100%" stop-color="${persona.color}" stop-opacity="0.15"/>
      </linearGradient>
    </defs>
    <rect width="100" height="100" fill="url(#${gradId})"/>
    <ellipse cx="50" cy="92" rx="38" ry="18" fill="${shirt}" opacity="0.85"/>
    <path d="M28 92 Q50 72 72 92 L72 100 L28 100 Z" fill="${shirt}"/>
    ${hairPaths}
    <ellipse cx="50" cy="52" rx="24" ry="28" fill="${skin}"/>
    <ellipse cx="40" cy="50" rx="3" ry="3.5" fill="#2d2d2d"/>
    <ellipse cx="60" cy="50" rx="3" ry="3.5" fill="#2d2d2d"/>
    <path d="M44 62 Q50 67 56 62" stroke="#c4756a" stroke-width="2" fill="none" stroke-linecap="round"/>
    <ellipse cx="36" cy="58" rx="5" ry="3" fill="#e8a090" opacity="0.35"/>
    <ellipse cx="64" cy="58" rx="5" ry="3" fill="#e8a090" opacity="0.35"/>
  </svg>`;
}

function taskText(agent, persona, state) {
  const text = fleetState.tasks[agent.id] || persona.task;
  const cursor = state === "running" ? '<span class="crew-cursor">▌</span>' : "";
  return `${esc(text)}${cursor}`;
}

function renderCrewCard(agent) {
  const persona = personaFor(agent);
  const apiState = agent.status || "idle";
  let state = "idle";
  if (apiState === "running" || fleetState.runningId === agent.id) state = "running";
  else if (agent.last_status === "success" || agent.last_status === "ok") state = "done";
  else if (agent.last_status === "error") state = "error";

  const statusLabel = state === "running"
    ? "Working now"
    : state === "done"
      ? "Task complete"
      : state === "error"
        ? "Needs attention"
        : "On standby";

  const stageLabel = agent.stage_num ? `Stage ${agent.stage_num}` : "Support";

  return `<article class="crew-card ${state}" data-agent-id="${esc(agent.id)}" style="--crew-accent:${persona.color}">
    <div class="crew-card-accent"></div>
    ${state === "running" ? '<div class="crew-glow-aura" aria-hidden="true"></div>' : ""}
    <header class="crew-header">
      <div class="crew-identity">
        ${state === "running" ? '<span class="crew-live-badge crew-live-inline" title="Active">LIVE</span>' : ""}
        ${state === "done" ? '<span class="crew-done-badge crew-done-inline" title="Complete">✓</span>' : ""}
        <span class="crew-designation">${esc(persona.designation)}</span>
        <h3 class="crew-agent-name">${esc(agent.name)}</h3>
        <div class="crew-meta">
          <span class="crew-human-name">${esc(persona.humanName)}</span>
          <span class="crew-stage">${esc(stageLabel)}</span>
          ${agent.has_gate ? '<span class="crew-gate-tag">Review gate</span>' : ""}
        </div>
      </div>
    </header>
    <div class="crew-task-panel">
      <span class="crew-task-label">${state === "running" ? "Currently working on" : "Ready to"}</span>
      <p class="crew-task-text">${taskText(agent, persona, state)}</p>
      ${state === "running" ? '<div class="crew-activity-bar"><div class="crew-activity-fill"></div></div>' : ""}
    </div>
    <footer class="crew-footer">
      <span class="crew-status-dot ${state}"></span>
      <span class="crew-status-label">${statusLabel}</span>
    </footer>
  </article>`;
}

function renderAgentFleet(agents) {
  fleetState.agents = agents || [];
  const el = document.getElementById("dashAgentFleet");
  const statusEl = document.getElementById("fleetStatus");
  if (!el) return;

  if (!agents?.length) {
    el.innerHTML = '<p class="empty">Loading team…</p>';
    return;
  }

  el.innerHTML = agents.map(renderCrewCard).join("");

  const running = agents.find((a) => a.status === "running") || agents.find((a) => a.id === fleetState.runningId);
  if (statusEl) {
    if (running) {
      const p = personaFor(running);
      statusEl.innerHTML = `<span class="fleet-pulse"></span> <strong>${esc(p.humanName)}</strong> (${esc(p.designation)}) is working`;
      statusEl.classList.add("active");
    } else {
      statusEl.textContent = `${agents.length} team members ready — click Discover Leads`;
      statusEl.classList.remove("active");
    }
  }
}

async function loadDashboardAgents() {
  try {
    const res = await fetch("/api/agents");
    const { agents } = await res.json();
    renderAgentFleet(agents);
  } catch {
    const el = document.getElementById("dashAgentFleet");
    if (el) el.innerHTML = '<p class="empty">Could not load team.</p>';
  }
}

function setAgentTask(agentId, message) {
  if (!agentId || !message) return;
  fleetState.tasks[agentId] = message.slice(0, 100);
  fleetState.runningId = agentId;

  const card = document.querySelector(`.crew-card[data-agent-id="${agentId}"]`);
  if (card) {
    const line = card.querySelector(".crew-task-text");
    if (line) line.innerHTML = `${esc(fleetState.tasks[agentId])}<span class="crew-cursor">▌</span>`;
    const label = card.querySelector(".crew-task-label");
    if (label) label.textContent = "Currently working on";
    const panel = card.querySelector(".crew-task-panel");
    if (panel && !card.querySelector(".crew-activity-bar")) {
      panel.insertAdjacentHTML("beforeend", '<div class="crew-activity-bar"><div class="crew-activity-fill"></div></div>');
    }
    const wrap = card.querySelector(".crew-identity");
    if (wrap && !wrap.querySelector(".crew-live-badge")) {
      wrap.insertAdjacentHTML("afterbegin", '<span class="crew-live-badge crew-live-inline" title="Active">LIVE</span>');
    }
    card.classList.remove("idle", "done", "error");
    card.classList.add("running");
    if (!card.querySelector(".crew-glow-aura")) {
      card.insertAdjacentHTML("afterbegin", '<div class="crew-glow-aura" aria-hidden="true"></div>');
    }
    card.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  const statusEl = document.getElementById("fleetStatus");
  const agent = fleetState.agents.find((a) => a.id === agentId);
  if (statusEl && agent) {
    const p = personaFor(agent);
    statusEl.innerHTML = `<span class="fleet-pulse"></span> <strong>${esc(p.humanName)}</strong> — ${esc(message.slice(0, 55))}`;
    statusEl.classList.add("active");
  }
}

function onFleetEvent(ev) {
  if (!ev?.type) return;

  if (ev.type === "stage_started") {
    const stage = ev.data?.stage;
    setAgentTask(stage, ev.data?.label ? `Running: ${ev.data.label}` : "Stage started…");
    loadDashboardAgents();
  }
  if (ev.type === "lead_stage_started") {
    setAgentTask(ev.data?.agent || ev.data?.stage, ev.data?.stage ? `Lead stage: ${ev.data.stage}` : "Working on lead…");
    loadDashboardAgents();
  }
  if (ev.type === "log" && fleetState.runningId && ev.data?.message) {
    setAgentTask(fleetState.runningId, ev.data.message);
  }
  if (ev.type === "stage_completed" || ev.type === "lead_stage_completed") {
    const id = ev.data?.stage || ev.data?.agent || fleetState.runningId;
    if (id) fleetState.tasks[id] = personaFor({ id }).task + " — Done ✓";
    fleetState.runningId = null;
    loadDashboardAgents();
  }
  if (ev.type === "run_completed" || ev.type === "run_failed") {
    fleetState.runningId = null;
    loadDashboardAgents();
  }
  if (ev.type === "human_gate") {
    const agentId = ev.data?.stage;
    if (agentId) setAgentTask(agentId, ev.data?.label || "Processing…");
  }
}
