/* Deal Tracking — list view + detail panel with editable review docs */

const trackingCache = {};
let activeDealId = null;
let activeTrackingRecord = null;
let activeReview = null;
let viewingDocId = null;

function buildFallbackReview(record) {
  if (!record) return null;
  const offer = record.offer || {};
  const contact = record.contact || {};
  const comparison = offer.supplier_comparison || [];
  const recName = offer.recommended_supplier || "";
  let recommended = null;
  for (const q of comparison) {
    const factory = q.factory || q.factory_name || "";
    if (!factory) continue;
    const match = recName && (factory.toLowerCase().includes(recName.toLowerCase()) || recName.toLowerCase().includes(factory.toLowerCase()));
    if (match || !recommended) {
      recommended = { factory_name: factory, url: q.url || "", platform_source: q.platform_source || q.platform || "", unit_price_estimate_usd: q.price_usd ?? q.unit_price_estimate_usd, moq: q.moq, trust_score: q.rating ?? q.trust_score, contacts: { emails: [], phones: [], whatsapp: [] }, is_recommended: !!match };
      if (match) break;
    }
  }
  const product = offer.product || "your order";
  const emailBody = [
    `Dear ${record.company_name || "Client"},`, "", `Thank you for the opportunity to source ${product}.`, "",
    offer.summary || "", "", "PROPOSED SOLUTION", "─────────────────",
    recName ? `Recommended supplier: ${recName}` : "",
    offer.quantity ? `Quantity: ${Number(offer.quantity).toLocaleString()} units` : "",
    offer.client_price_usd ? `All-in price: $${Number(offer.client_price_usd).toLocaleString()} USD` : "",
    "", "Best regards,", "Your Sourcing Team",
  ].filter(Boolean).join("\n");
  return {
    deal_id: record.deal_id,
    company_name: record.company_name,
    artifacts: {
      proposal: { title: offer.title, executive_summary: offer.summary, recommended_option: recName, client_price_usd: offer.client_price_usd, status: record.proposal_status },
      proposal_email: { to: contact.email || "", subject: offer.title || `Proposal for ${record.company_name}`, body: emailBody, status: record.proposal_status || "draft", sent_at: record.proposal_sent_at },
      buyer_contacts: { emails: contact.email && !String(contact.email).includes("@sentry.") ? [contact.email] : [], phones: contact.phone ? [contact.phone] : [], website: contact.website, primary_email: contact.email || "", primary_phone: contact.phone || "" },
      quotes: { quotes: comparison, comparison: { recommended_supplier: recName } },
      recommended_supplier: recommended,
    },
    steps: [],
    documents: [],
  };
}

function mergeReviewWithFallback(review, fallback) {
  if (!fallback) return review;
  if (!review) return fallback;
  const merged = { ...fallback, ...review, artifacts: { ...fallback.artifacts } };
  const apiArt = review.artifacts || {};
  for (const [key, fbVal] of Object.entries(fallback.artifacts)) {
    const apiVal = apiArt[key];
    if (key === "proposal_email") merged.artifacts[key] = apiVal?.body ? apiVal : fbVal;
    else if (key === "quotes") merged.artifacts[key] = (apiVal?.quotes || []).length ? apiVal : fbVal;
    else if (key === "buyer_contacts") merged.artifacts[key] = ((apiVal?.emails || []).length || apiVal?.website) ? { ...fbVal, ...apiVal } : fbVal;
    else if (key === "recommended_supplier") merged.artifacts[key] = apiVal?.factory_name ? apiVal : fbVal;
    else if (apiVal && (typeof apiVal !== "object" || Object.keys(apiVal).length)) merged.artifacts[key] = apiVal;
    else merged.artifacts[key] = fbVal;
  }
  return merged;
}

async function loadTracking() {
  const list = document.getElementById("trackingList");
  const badge = document.getElementById("badgeTracking");
  try {
    const res = await fetch("/api/tracking");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (badge) badge.textContent = data.total || 0;
    if (!list) return;
    if (!data.tracking?.length) {
      document.getElementById("trackingDetailView")?.classList.add("hidden");
      list.classList.remove("hidden");
      list.innerHTML = `<div class="empty-state"><h3>No deals in tracking</h3><p>Deals appear here after a proposal is sent from Hot Leads.</p></div>`;
      return;
    }
    data.tracking.forEach((t) => { trackingCache[t.deal_id] = t; });
    if (activeDealId) {
      activeTrackingRecord = trackingCache[activeDealId] || activeTrackingRecord;
      if (activeTrackingRecord) await renderTrackingDetail(activeTrackingRecord);
      return;
    }
    renderTrackingList(data.tracking);
  } catch (e) {
    if (badge) badge.textContent = "0";
    if (list) list.innerHTML = `<div class="empty-state"><h3>Could not load tracking</h3><p>${esc(e.message)}</p></div>`;
  }
}

function renderTrackingList(items) {
  const list = document.getElementById("trackingList");
  document.getElementById("trackingDetailView")?.classList.add("hidden");
  list?.classList.remove("hidden");
  if (!list) return;

  list.innerHTML = `<div class="table-wrap"><table class="data-table hot-leads-table">
    <thead><tr>
      <th>Company</th><th>Product</th><th>Stage</th><th>Proposal</th><th>Client price</th><th></th>
    </tr></thead>
    <tbody>${items.map((t) => {
      const offer = t.offer || {};
      const stage = (t.stage || "").replace(/_/g, " ");
      const sent = t.proposal_status === "sent";
      return `<tr class="clickable-row" data-deal-id="${esc(t.deal_id)}">
        <td><strong>${esc(t.company_name)}</strong></td>
        <td class="cell-truncate">${esc(offer.product || "—")}</td>
        <td><span class="status-pill status-active">${esc(stage)}</span></td>
        <td>${sent ? '<span class="tag tag-sent">Sent</span>' : '<span class="tag tag-warn">Draft</span>'}</td>
        <td>${offer.client_price_usd ? fmtMoney(offer.client_price_usd) : "—"}</td>
        <td><button type="button" class="btn ghost btn-sm btn-open-track" data-id="${esc(t.deal_id)}">Open →</button></td>
      </tr>`;
    }).join("")}</tbody>
  </table></div>`;

  list.querySelectorAll(".clickable-row").forEach((row) => {
    row.addEventListener("click", (e) => { if (!e.target.closest(".btn-open-track")) openTrackingDeal(row.dataset.dealId); });
  });
  list.querySelectorAll(".btn-open-track").forEach((btn) => {
    btn.addEventListener("click", (e) => { e.stopPropagation(); openTrackingDeal(btn.dataset.id); });
  });
}

async function fetchTrackingReview(dealId) {
  const record = trackingCache[dealId];
  const fallback = buildFallbackReview(record);
  let review = null;
  try {
    const res = await fetch(`/api/tracking/${encodeURIComponent(dealId)}/review`);
    if (res.ok) review = await res.json();
  } catch { /* fallback */ }
  review = mergeReviewWithFallback(review, fallback);
  review.deal_id = dealId;
  return review;
}

async function openTrackingDeal(dealId) {
  activeDealId = dealId;
  activeTrackingRecord = trackingCache[dealId];
  viewingDocId = null;
  if (!activeTrackingRecord) return;
  activeReview = await fetchTrackingReview(dealId);
  activeTrackingRecord.review = activeReview;
  if (!viewingDocId && activeReview.documents?.length) viewingDocId = activeReview.documents[0].id;
  await renderTrackingDetail(activeTrackingRecord);
}

function closeTrackingDeal() {
  activeDealId = null;
  activeTrackingRecord = null;
  activeReview = null;
  viewingDocId = null;
  document.getElementById("trackingDetailView")?.classList.add("hidden");
  document.getElementById("trackingList")?.classList.remove("hidden");
}

function renderTrackingSteps(review, dealId) {
  const steps = review?.steps || [];
  if (!steps.length && review?.documents?.length) {
    return `<div class="step-progress">${review.documents.map((d, i) =>
      `<button type="button" class="step-pill ${viewingDocId === d.id ? "current" : "done"}" data-doc-id="${esc(d.id)}">
        <span class="step-pill-dot">${i + 1}</span><span class="step-pill-label">${esc(d.label)}</span>
      </button>`
    ).join("")}</div>`;
  }
  return `<div class="step-progress">${steps.map((s, i) =>
    `<button type="button" class="step-pill ${s.status === "completed" ? "done" : ""} ${viewingDocId === s.artifact ? "current" : ""}"
      data-doc-id="${esc(s.artifact)}" ${s.viewable ? "" : "disabled"}>
      <span class="step-pill-dot">${s.status === "completed" ? "✓" : i + 1}</span>
      <span class="step-pill-label">${esc(s.label)}</span>
    </button>`
  ).join("")}</div>`;
}

function renderEditableTrackingDoc(docId, review) {
  const art = review.artifacts || {};
  if (docId === "proposal_email") {
    const e = art.proposal_email || {};
    return `<form class="draft-edit-form" id="trackEditForm">
      <label class="draft-field"><span class="draft-field-label">To</span><input type="email" name="to" value="${escAttr(e.to || "")}" class="draft-input" /></label>
      <label class="draft-field"><span class="draft-field-label">Subject</span><input type="text" name="subject" value="${escAttr(e.subject || "")}" class="draft-input" /></label>
      <label class="draft-field"><span class="draft-field-label">Body</span><textarea name="body" class="draft-textarea" rows="14">${esc(e.body || "")}</textarea></label>
    </form>`;
  }
  if (docId === "outreach") {
    const o = art.outreach || {};
    return `<form class="draft-edit-form" id="trackEditForm">
      <label class="draft-field"><span class="draft-field-label">Subject</span><input type="text" name="subject" value="${escAttr(o.subject || "")}" class="draft-input" /></label>
      <label class="draft-field"><span class="draft-field-label">Body</span><textarea name="body" class="draft-textarea" rows="12">${esc(o.body || "")}</textarea></label>
    </form>`;
  }
  if (docId === "proposal") {
    const p = art.proposal || {};
    return `<form class="draft-edit-form" id="trackEditForm">
      <label class="draft-field"><span class="draft-field-label">Title</span><input type="text" name="title" value="${escAttr(p.title || "")}" class="draft-input" /></label>
      <label class="draft-field"><span class="draft-field-label">Summary</span><textarea name="executive_summary" class="draft-textarea" rows="8">${esc(p.executive_summary || "")}</textarea></label>
    </form>`;
  }
  return renderReviewDocument(docId, review);
}

function escAttr(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

async function renderTrackingDetail(t) {
  const container = document.getElementById("trackingDetailView");
  if (!container) return;
  const review = activeReview || t.review || await fetchTrackingReview(t.deal_id);
  activeReview = review;
  const offer = t.offer || {};
  const docId = viewingDocId || review.documents?.[0]?.id || "proposal_email";
  viewingDocId = docId;
  const stageLabel = (t.stage || "").replace(/_/g, " ");

  container.innerHTML = `
    <div class="step-view-header">
      <button type="button" class="btn ghost" id="btnBackTrackList">← Back to list</button>
      <div class="step-view-title"><h2>${esc(t.company_name)}</h2><span class="status-pill status-active">${esc(stageLabel)}</span></div>
    </div>
    <div class="tracking-summary-bar">
      <span>${esc(offer.product || "—")}</span>
      <span>Qty ${esc(offer.quantity || "—")}</span>
      <span>${offer.client_price_usd ? fmtMoney(offer.client_price_usd) : ""}</span>
    </div>
    ${renderTrackingSteps(review, t.deal_id)}
    <article class="step-card">
      <header class="step-card-head">
        <h3>${esc((review.documents || []).find((d) => d.id === docId)?.label || docId.replace(/_/g, " "))}</h3>
      </header>
      <div class="step-context" id="trackDocBody">${renderEditableTrackingDoc(docId, review)}</div>
      <footer class="step-card-actions">
        ${t.stage === "proposal_sent" ? `<button class="btn primary btn-track-advance" data-id="${esc(t.deal_id)}" data-action="start_production">Client Approved → Production</button>` : ""}
        ${t.stage === "order_tracking" ? `<button class="btn primary btn-track-advance" data-id="${esc(t.deal_id)}" data-action="finance">Record Invoice</button>` : ""}
        <button type="button" class="btn ghost btn-portal-link" data-id="${esc(t.deal_id)}">Copy Portal Link</button>
        <button type="button" class="btn ghost btn-view-deal" data-id="${esc(t.deal_id)}">Full deal detail</button>
        <button type="button" class="btn ghost btn-close-deal" data-id="${esc(t.deal_id)}">Close Deal</button>
      </footer>
    </article>`;

  document.getElementById("trackingList")?.classList.add("hidden");
  container.classList.remove("hidden");

  document.getElementById("btnBackTrackList")?.addEventListener("click", closeTrackingDeal);
  container.querySelectorAll(".step-pill[data-doc-id]").forEach((btn) => {
    btn.addEventListener("click", () => { viewingDocId = btn.dataset.docId; renderTrackingDetail(t); });
  });
  bindTrackingDetailActions(container);
}

function bindTrackingDetailActions(root) {
  root.querySelector(".btn-track-advance")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true;
    await fetch(`/api/tracking/${btn.dataset.id}/advance?action=${btn.dataset.action}`, { method: "POST" });
    await loadTracking();
    loadOverview?.();
  });
  root.querySelector(".btn-close-deal")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    if (!confirm("Close this deal?")) return;
    await fetch(`/api/tracking/${btn.dataset.id}/close`, { method: "POST" });
    closeTrackingDeal();
    loadTracking();
    loadClosedDeals?.();
    loadOverview?.();
  });
  root.querySelector(".btn-view-deal")?.addEventListener("click", (e) => showDealDetail(e.currentTarget.dataset.id));
  root.querySelector(".btn-portal-link")?.addEventListener("click", async (e) => {
    const url = `${location.origin}/portal/${e.currentTarget.dataset.id}`;
    try { await navigator.clipboard.writeText(url); e.currentTarget.textContent = "Copied!"; }
    catch { prompt("Copy:", url); }
  });
}

/* ── Review document renderers (read-only views) ── */

function kvRow(label, value) {
  return `<div class="detail-kv"><span class="detail-kv-label">${esc(label)}</span><span class="detail-kv-value">${esc(value ?? "—")}</span></div>`;
}

function section(title, desc, html) {
  return `<div class="hot-block full"><h4>${esc(title)}</h4>${desc ? `<p class="block-desc">${esc(desc)}</p>` : ""}${html}</div>`;
}

function renderSupplierContacts(s) {
  if (!s) return "<p class='muted'>No supplier selected.</p>";
  const c = s.contacts || {};
  const chips = [];
  (c.whatsapp || []).forEach((w) => chips.push(`<a class="btn primary" href="${esc(w.link)}" target="_blank">WhatsApp</a>`));
  (c.emails || []).forEach((e) => chips.push(`<a class="btn ghost" href="${gmailComposeUrl(e)}" target="_blank">Email</a>`));
  if (s.url) chips.push(`<a class="btn ghost" href="${esc(s.url)}" target="_blank">Open listing</a>`);
  return `${kvRow("Factory", s.factory_name)}${kvRow("Price est.", fmtMoney(s.unit_price_estimate_usd))}${kvRow("MOQ", s.moq)}<div class="contact-actions">${chips.join("")}</div>`;
}

function renderBuyerContacts(contacts, fallbackContact) {
  if (typeof renderBuyerContactBlock === "function") return renderBuyerContactBlock(contacts, fallbackContact);
  const email = contacts?.primary_email || contacts?.emails?.[0] || fallbackContact?.email;
  return email ? `<a class="btn primary" href="${gmailComposeUrl(email)}" target="_blank">Email in Gmail</a>` : "<p class='muted'>No buyer email on file.</p>";
}

function renderReviewDocument(docId, review) {
  const art = review.artifacts || {};
  const titleMap = { company: "Company profile", personalization: "Personalization", outreach: "Outreach email", requirements: "Buyer requirements", product_spec: "Product spec", suppliers: "All suppliers", recommended_supplier: "Recommended supplier", supplier_approval: "Supplier approval", rfqs: "RFQ email", quotes: "Quote comparison", proposal: "Proposal", proposal_email: "Client email", buyer_contacts: "Contact buyer" };
  let html = "";
  try {
    switch (docId) {
      case "company": {
        const c = art.company || {};
        html = [kvRow("Summary", c.company_summary), kvRow("Products", (c.products_services || []).join(", ")), typeof renderProductImages === "function" ? renderProductImages(c.product_images, "Product images") : ""].join("");
        break;
      }
      case "quotes": {
        const quotesData = art.quotes || {};
        html = typeof renderQuoteComparisonTable === "function" ? renderQuoteComparisonTable(normalizeQuotesList(quotesData), quotesData.comparison || {}) : "<p class='muted'>No quotes.</p>";
        break;
      }
      case "recommended_supplier": html = renderSupplierContacts(art.recommended_supplier); break;
      case "buyer_contacts": html = renderBuyerContacts(art.buyer_contacts, trackingCache[review.deal_id]?.contact); break;
      case "suppliers": {
        const list = art.suppliers || [];
        html = list.map((s) => `<div class="supplier-review-card"><h4>${esc(s.factory_name)}</h4>${renderSupplierContacts(s)}</div>`).join("") || "<p class='muted'>No suppliers.</p>";
        break;
      }
      case "rfqs": {
        html = (art.rfqs || []).map((r) => `<pre class="draft-body">${esc(r.rfq_body || "")}</pre>`).join("") || "<p class='muted'>No RFQ.</p>";
        break;
      }
      default: html = "<p class='muted'>Select a document above to review.</p>";
    }
  } catch (err) {
    html = `<p class="error-msg">${esc(err.message)}</p>`;
  }
  return html || `<p class="muted">${esc(titleMap[docId] || docId)} — no content yet.</p>`;
}

async function openTrackingDocument(dealId, docId) {
  viewingDocId = docId;
  activeDealId = dealId;
  activeTrackingRecord = trackingCache[dealId];
  if (activeTrackingRecord) await renderTrackingDetail(activeTrackingRecord);
}

function bindTrackingActions() {
  /* legacy hook — detail view handles actions */
}
