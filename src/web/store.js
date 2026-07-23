/* AI Product Finder Store — partner storefronts */

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const fmt = (n) => Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 });

const params = new URLSearchParams(location.search);
const tenantSlug = params.get("tenant") || "demo";

let sessionId = null;
let currentStep = null;
let isQuoting = false;
let tenantData = null;

function applyTheme(branding = {}) {
  const primary = branding.primary_color || "#3b82f6";
  const accent = branding.accent_color || primary;
  document.documentElement.style.setProperty("--store-primary", primary);
  document.documentElement.style.setProperty("--store-accent", accent);
  const logo = $("storeLogo");
  if (logo) logo.style.background = `linear-gradient(135deg, ${primary}, ${accent})`;
  if (branding.logo_text && logo) logo.textContent = branding.logo_text;
}

function renderChips(chips = []) {
  const wrap = $("categoryChips");
  if (!wrap) return;
  wrap.innerHTML = chips.map((chip) =>
    `<button type="button" class="store-chip" data-query="${esc(chip.query)}">${esc(chip.label)}</button>`
  ).join("");
}

function renderProducts(products = []) {
  const grid = $("storeProducts");
  if (!grid) return;
  grid.innerHTML = products.map((p) => `
    <button type="button" class="store-product-card" data-query="${esc(p.query)}">
      <div class="store-product-visual">
        <img
          class="store-product-img"
          src="${esc(p.image_url)}?v=4"
          alt="${esc(p.name)}"
          loading="lazy"
          decoding="async"
        />
      </div>
      <div class="store-product-body">
        <span class="store-product-cat">${esc(p.category)}</span>
        <strong class="store-product-name">${esc(p.name)}</strong>
        <p class="store-product-desc">${esc(p.description)}</p>
        <div class="store-product-meta">
          <span>MOQ ${fmt(p.moq)}</span>
          <span class="store-product-price">From $${fmt(p.from_price_usd)}/unit</span>
        </div>
      </div>
    </button>
  `).join("");
}

function renderTrust(specialties = []) {
  const list = $("storeTrustList");
  const title = $("storeTrustTitle");
  if (!list) return;
  if (title && specialties.length) {
    title.textContent = "Our specialties";
  }
  if (!specialties.length) return;
  const base = [
    "<strong>All-in pricing</strong> — production, QC, and logistics included",
    "<strong>Fast quotes</strong> — typically ready in under 2 minutes",
    "<strong>Order tracking</strong> — portal updates from quote to shipment",
  ];
  const specialtyItems = specialties.map((s) => `<strong>${esc(s)}</strong> — factory-direct programs we run every week`);
  list.innerHTML = [...specialtyItems.slice(0, 2), ...base].map((html) => `<li>${html}</li>`).join("");
}

function bindQuoteTriggers() {
  document.querySelectorAll(".store-chip, .store-product-card").forEach((el) => {
    el.onclick = () => {
      const q = el.dataset.query || "";
      $("productQuery").value = q;
      startSession(q);
    };
  });
}

async function loadTenant() {
  try {
    const res = await fetch(`/api/store/tenant/${encodeURIComponent(tenantSlug)}`);
    if (!res.ok) throw new Error("tenant");
    const t = await res.json();
    tenantData = t;
    $("storeName").textContent = t.name || "AI Product Finder";
    $("storeTagline").textContent = t.tagline || "Custom sourcing in minutes";
    applyTheme(t.branding || {});
    if (t.eyebrow) $("storeEyebrow").textContent = t.eyebrow;
    if (t.hero_title) $("storeHeroTitle").textContent = t.hero_title;
    if (t.hero_subtitle) $("storeHeroSub").textContent = t.hero_subtitle;
    if (t.specialty_lead) $("storeSpecialtyLead").textContent = t.specialty_lead;
    renderChips(t.category_chips || []);
    renderProducts(t.featured_products || []);
    renderTrust(t.specialties || []);
    bindQuoteTriggers();
    document.title = `${t.name || "Store"} — AI Product Finder`;
  } catch {
    $("storeTagline").textContent = "Store not found — using demo";
    bindQuoteTriggers();
  }
}

function addMessage(text, role = "ai") {
  const el = document.createElement("div");
  el.className = `store-msg ${role}`;
  el.innerHTML = esc(text);
  $("chatMessages").appendChild(el);
  el.scrollIntoView({ behavior: "smooth", block: "end" });
}

function showChat() {
  $("storeHero").classList.add("hidden");
  document.querySelector(".store-section#how-store-works")?.classList.add("hidden");
  $("storeCatalog")?.classList.add("hidden");
  $("storeChat").classList.remove("hidden");
  $("storeChat").scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetStore() {
  sessionId = null;
  currentStep = null;
  isQuoting = false;
  $("chatMessages").innerHTML = "";
  $("quotePanel").classList.add("hidden");
  $("orderDone").classList.add("hidden");
  $("chatInputArea").classList.remove("hidden");
  $("storeChat").classList.add("hidden");
  $("storeHero").classList.remove("hidden");
  document.querySelector(".store-section#how-store-works")?.classList.remove("hidden");
  $("storeCatalog")?.classList.remove("hidden");
  $("productQuery").value = "";
  $("productQuery").focus();
}

async function startSession(query) {
  if (!query) return;
  showChat();
  addMessage(query, "user");
  addMessage("Great — I'll ask a few quick questions to find the right suppliers and build your quote.");
  try {
    const res = await fetch("/api/store/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tenant: tenantSlug, query }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to start");
    sessionId = data.session_id;
    const answers = data.answers || {};
    for (const [k, v] of Object.entries(answers)) {
      if (k === "product" || k === "quantity") {
        addMessage(String(v), "user");
      }
    }
    renderStep(data);
  } catch (err) {
    addMessage(`Error: ${err.message}`, "ai");
  }
}

function renderStep(session) {
  currentStep = session.next_step;
  $("chatInputArea").classList.toggle("hidden", !currentStep);
  $("quotePanel").classList.add("hidden");
  if (currentStep) {
    const input = $("answerInput");
    input.placeholder = currentStep.placeholder || "Type your answer…";
    input.type = currentStep.type === "number" ? "number" : currentStep.type === "email" ? "email" : "text";
    addMessage(currentStep.question);
    input.focus();
  } else if (session.status === "ready_to_quote" || session.status === "intake") {
    requestQuote();
  } else if (session.quote && session.status === "quoted") {
    renderQuote(session);
  } else if (session.status === "ordered") {
    renderOrderDone(session);
  }
}

async function requestQuote() {
  if (isQuoting || !sessionId) return;
  isQuoting = true;
  $("chatInputArea").classList.add("hidden");
  addMessage("Searching suppliers and building your quotation…", "ai thinking");
  try {
    const res = await fetch(`/api/store/sessions/${sessionId}/quote`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Quote failed");
    const thinking = document.querySelector(".store-msg.thinking");
    if (thinking) thinking.remove();
    addMessage("Here's your quotation based on live supplier research:");
    renderQuote(data);
  } catch (e) {
    addMessage(`Sorry, we couldn't build a quote: ${e.message}`, "ai");
    $("chatInputArea").classList.remove("hidden");
  } finally {
    isQuoting = false;
  }
}

function renderQuote(session) {
  const q = session.quote || {};
  $("quotePanel").classList.remove("hidden");
  $("quotePanel").innerHTML = `
    <h3>Your quotation</h3>
    <div class="store-quote-price">$${fmt(q.client_price_usd)} <span style="font-size:0.5em;color:#94a3b8">all-in</span></div>
    <div class="store-quote-grid">
      <div class="store-quote-stat"><label>Product</label><strong>${esc(q.product)}</strong></div>
      <div class="store-quote-stat"><label>Quantity</label><strong>${fmt(q.quantity)}</strong></div>
      <div class="store-quote-stat"><label>Unit price</label><strong>$${fmt(q.unit_price_usd)}</strong></div>
      <div class="store-quote-stat"><label>Delivery</label><strong>${esc(q.timeline)}</strong></div>
      <div class="store-quote-stat"><label>Supplier</label><strong>${esc(q.supplier)}</strong></div>
    </div>
    ${(q.suppliers || []).length ? `
      <p style="font-size:0.8rem;color:#94a3b8;margin:0 0 0.5rem">Compared suppliers:</p>
      <ul class="store-suppliers">${q.suppliers.map((s) =>
        `<li>${esc(s.supplier)} — ${s.unit_price_usd ? `$${fmt(s.unit_price_usd)}/unit` : "quote on request"}${s.moq ? ` · MOQ ${s.moq}` : ""}</li>`
      ).join("")}</ul>
    ` : ""}
    <button type="button" class="btn primary" id="btnPlaceOrder">Place order — 30% deposit</button>
  `;
  $("btnPlaceOrder").onclick = placeOrder;
}

async function placeOrder() {
  const btn = $("btnPlaceOrder");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Placing order…";
  }
  try {
    const res = await fetch(`/api/store/sessions/${sessionId}/order`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Order failed");
    renderOrderDone(data);
  } catch (e) {
    addMessage(`Order failed: ${e.message}`, "ai");
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Place order — 30% deposit";
    }
  }
}

function renderOrderDone(session) {
  $("quotePanel").classList.add("hidden");
  $("orderDone").classList.remove("hidden");
  const q = session.quote || {};
  const deposit = (q.client_price_usd || 0) * 0.3;
  const ref = (session.deal_id || "").slice(0, 8).toUpperCase();
  $("orderDone").innerHTML = `
    <div class="store-order-icon">✓</div>
    <h3>Order confirmed</h3>
    <p class="store-order-sub">Your order has been placed and our team is on it.</p>
    <div class="store-order-grid">
      <div class="store-order-stat"><label>Product</label><span>${esc(q.product)}</span></div>
      <div class="store-order-stat"><label>Quantity</label><span>${fmt(q.quantity)} units</span></div>
      <div class="store-order-stat"><label>Order ref</label><span>#${esc(ref)}</span></div>
      <div class="store-order-stat"><label>Delivery</label><span>${esc(q.timeline || "TBD")}</span></div>
    </div>
    <div class="store-order-totals">
      <div class="store-order-total-row"><span>Total</span><span class="store-order-total-price">$${fmt(q.client_price_usd)}</span></div>
      <div class="store-order-total-row deposit"><span>30% deposit due</span><span class="store-order-deposit">$${fmt(deposit)}</span></div>
    </div>
    ${session.portal_url ? `<a href="${esc(session.portal_url)}" class="btn primary store-order-track">Track your order</a>` : ""}
  `;
}

$("startForm").onsubmit = async (e) => {
  e.preventDefault();
  await startSession($("productQuery").value.trim());
};

$("btnNewQuote")?.addEventListener("click", resetStore);

$("answerForm").onsubmit = async (e) => {
  e.preventDefault();
  if (!currentStep || !sessionId) return;
  const value = $("answerInput").value.trim();
  if (!value) return;
  addMessage(value, "user");
  $("answerInput").value = "";
  $("answerInput").disabled = true;
  try {
    const res = await fetch(`/api/store/sessions/${sessionId}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ field: currentStep.id, value: currentStep.type === "number" ? Number(value) : value }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed");
    renderStep(data);
  } catch (err) {
    addMessage(`Error: ${err.message}`, "ai");
  } finally {
    $("answerInput").disabled = false;
    $("answerInput").focus();
  }
};

loadTenant();
