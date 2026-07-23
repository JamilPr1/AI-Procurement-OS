/* Contacts — fast list view with per-item modal actions */

let contactsCache = [];

const VIEW_BTN_CLASS = {
  outreach: "btn primary",
  proposal_email: "btn primary",
  proposal: "btn ghost",
  company: "btn ghost",
  personalization: "btn ghost",
  quotes: "btn ghost",
  rfq: "btn ghost",
  requirements: "btn ghost",
  product_spec: "btn ghost",
};

async function loadContacts() {
  const wrap = document.getElementById("contactsTableWrap");
  if (!wrap) return;
  wrap.innerHTML = '<p class="muted" style="padding:1rem">Loading clients…</p>';
  try {
    const res = await fetch("/api/contacts");
    const data = await res.json();
    contactsCache = data.clients || [];
    renderContactsTable();
  } catch (err) {
    wrap.innerHTML = `<p class="error-msg" style="padding:1rem">${esc(err.message)}</p>`;
  }
}

function renderContactsTable() {
  const wrap = document.getElementById("contactsTableWrap");
  const q = (document.getElementById("searchContacts")?.value || "").toLowerCase();
  const filtered = contactsCache.filter((c) =>
    !q
    || (c.company_name || "").toLowerCase().includes(q)
    || (c.email || "").toLowerCase().includes(q)
    || (c.domain || "").toLowerCase().includes(q)
  );

  if (!filtered.length) {
    wrap.innerHTML = '<p class="empty" style="padding:1rem">No clients found. Run the pipeline on Hot Leads first.</p>';
    return;
  }

  wrap.innerHTML = `<table class="data-table contacts-table">
    <thead><tr>
      <th>Company</th>
      <th>Email</th>
      <th>Stage</th>
      <th>Sent</th>
      <th>Actions</th>
    </tr></thead>
    <tbody>${filtered.map(renderContactRow).join("")}</tbody>
  </table>`;
}

function renderContactRow(c) {
  const stage = (c.deal_stage || "engaged").replace(/_/g, " ");
  const views = c.views || [];
  const actions = views.map((v) => {
    const cls = VIEW_BTN_CLASS[v.id] || "btn ghost";
    const sent = v.status === "sent" ? " ✓" : "";
    return `<button type="button" class="${cls} btn-contact-view" data-lead-id="${esc(c.lead_id)}" data-view-id="${esc(v.id)}" data-company="${esc(c.company_name)}">${esc(v.label)}${sent}</button>`;
  }).join("");
  const demoBtn = `<button type="button" class="btn ghost btn-contact-demo" data-lead-id="${esc(c.lead_id)}">Demo flow</button>`;
  const trackBtn = c.deal_id
    ? `<button type="button" class="btn ghost btn-contact-tracking" data-deal-id="${esc(c.deal_id)}">Tracking</button>`
    : "";

  return `<tr data-lead-id="${esc(c.lead_id)}">
    <td><strong>${esc(c.company_name)}</strong>${c.website ? `<div class="row-hint"><a class="link" href="${esc(c.website)}" target="_blank" rel="noopener">${esc(c.domain || "website")}</a></div>` : ""}</td>
    <td>${c.email ? `<a class="link" href="${gmailComposeUrl(c.email)}" target="_blank" rel="noopener">${esc(c.email)}</a>` : "—"}</td>
    <td><span class="status-pill status-active">${esc(stage)}</span></td>
    <td>${c.emails_sent || 0}</td>
    <td><div class="contact-row-actions">${actions}${demoBtn}${trackBtn}</div></td>
  </tr>`;
}

async function openContactView(leadId, viewId, companyName) {
  if (typeof openDetailModal !== "function") {
    alert("Please refresh the page.");
    return;
  }
  openDetailModal("Client document", companyName || "Loading…", viewId.replace(/_/g, " "));
  const body = document.getElementById("modalBody");
  body.innerHTML = '<div class="modal-loading">Loading…</div>';
  try {
    const res = await fetch(`/api/contacts/${encodeURIComponent(leadId)}/view/${encodeURIComponent(viewId)}`);
    if (!res.ok) throw new Error("Document not found");
    const payload = await res.json();
    document.getElementById("modalTitle").textContent = payload.title || companyName;
    body.innerHTML = renderContactViewPayload(payload);
  } catch (err) {
    body.innerHTML = `<p class="error-msg">${esc(err.message)}</p>`;
  }
}

function renderContactViewPayload(payload) {
  const type = payload.type;
  const data = payload.data || {};
  if (type === "email") return renderContactEmailView(data);
  if (type === "proposal") return renderContactProposalView(data);
  if (type === "quotes") return renderContactQuotesView(data);
  if (type === "company") return renderContactCompanyView(data);
  if (type === "rfq") return renderContactRfqView(data);
  if (type === "text") return renderContactPersonalizationView(data);
  if (type === "kv") return renderContactKvView(data);
  return `<pre class="draft-body">${esc(JSON.stringify(data, null, 2))}</pre>`;
}

function renderContactEmailView(data) {
  const isDemo = data.send_result?.status === "dry_run" || data.send_result?.demo;
  const body = data.body || "";
  return [
    kvRow("To", data.to || "—"),
    kvRow("Subject", data.subject || "—"),
    kvRow("Status", data.status || "draft"),
    data.sent_at ? kvRow("Sent", fmtDate(data.sent_at)) : "",
    isDemo ? '<span class="tag tag-demo">Demo email</span>' : (data.status === "sent" ? '<span class="tag tag-sent">Sent</span>' : ""),
    data.send_result?.message ? `<p class="hint">${esc(data.send_result.message)}</p>` : "",
    typeof renderProductImages === "function" ? renderProductImages(data.product_images, "Images in email") : "",
    body ? `<pre class="draft-body">${esc(body)}</pre>` : "",
    body && data.to ? renderEmailComposeActions(data.to, data.subject || "", body) : "",
  ].filter(Boolean).join("");
}

function renderContactProposalView(data) {
  const parts = [
    kvRow("Title", data.title),
    kvRow("Status", data.status || "draft"),
    kvRow("Client price", fmtMoney(data.client_price_usd)),
    data.factory_cost_usd ? kvRow("Factory cost", fmtMoney(data.factory_cost_usd)) : "",
    data.margin_usd ? kvRow("Margin", `${fmtMoney(data.margin_usd)} (${data.margin_percent || 15}%)`) : "",
    kvRow("Supplier", data.recommended_option),
    kvRow("Timeline", data.timeline),
    kvRow("Payment", data.payment_terms),
    data.executive_summary ? `<p class="callout">${esc(data.executive_summary)}</p>` : "",
    typeof renderProductImages === "function"
      ? renderProductImages(data.reference_images || data.product_images, "Proposal images")
      : "",
  ];
  const email = data.client_email_draft;
  if (email?.body) {
    parts.push('<h4 class="contact-view-sub">Client email preview</h4>');
    parts.push(renderContactEmailView({ ...email, status: data.status, sent_at: data.sent_at, send_result: data.send_result }));
  }
  return parts.filter(Boolean).join("");
}

function renderContactQuotesView(data) {
  const quotes = data.quotes || [];
  if (typeof renderQuoteComparisonTable === "function" && quotes.length) {
    return renderQuoteComparisonTable(quotes, data.comparison || {});
  }
  return quotes.length
    ? `<ul>${quotes.map((q) => `<li>${esc(q.factory)} — ${fmtMoney(q.price_usd)} MOQ ${esc(q.moq ?? "—")}</li>`).join("")}</ul>`
    : "<p class='muted'>No quotes yet.</p>";
}

function renderContactCompanyView(data) {
  return [
    kvRow("Summary", data.company_summary),
    data.products_services?.length ? kvRow("Products", data.products_services.join(", ")) : "",
    typeof renderProductImages === "function"
      ? renderProductImages(data.product_images, "Product catalog")
      : "",
  ].filter(Boolean).join("");
}

function renderContactRfqView(data) {
  return [
    kvRow("Subject", data.subject),
    kvRow("Product", data.product),
    data.rfq_body ? `<pre class="draft-body">${esc(data.rfq_body)}</pre>` : "",
  ].filter(Boolean).join("");
}

function renderContactPersonalizationView(data) {
  return [
    kvRow("Subject", data.subject_line),
    data.email_body ? `<pre class="draft-body">${esc(data.email_body)}</pre>` : "",
    data.linkedin_message ? `<p class="hint"><strong>LinkedIn:</strong> ${esc(data.linkedin_message)}</p>` : "",
  ].filter(Boolean).join("");
}

function renderContactKvView(data) {
  return Object.entries(data)
    .filter(([, v]) => v != null && v !== "")
    .map(([k, v]) => kvRow(k.replace(/_/g, " "), Array.isArray(v) ? v.join(", ") : String(v)))
    .join("");
}

function bindContactsPage() {
  const wrap = document.getElementById("contactsTableWrap");
  if (!wrap || wrap._bound) return;
  wrap._bound = true;

  wrap.addEventListener("click", async (e) => {
    const viewBtn = e.target.closest(".btn-contact-view");
    if (viewBtn) {
      e.preventDefault();
      openContactView(viewBtn.dataset.leadId, viewBtn.dataset.viewId, viewBtn.dataset.company);
      return;
    }
    const demoBtn = e.target.closest(".btn-contact-demo");
    if (demoBtn) {
      demoBtn.disabled = true;
      try {
        await fetch(`/api/contacts/${demoBtn.dataset.leadId}/demo-complete`, { method: "POST" });
        await loadContacts();
        loadOverview?.();
      } finally {
        demoBtn.disabled = false;
      }
      return;
    }
    const trackBtn = e.target.closest(".btn-contact-tracking");
    if (trackBtn && typeof navigate === "function") {
      navigate("tracking");
    }
  });

  document.getElementById("searchContacts")?.addEventListener("input", renderContactsTable);

  document.getElementById("btnDemoAllContacts")?.addEventListener("click", async () => {
    const btn = document.getElementById("btnDemoAllContacts");
    if (!confirm("Record demo emails for all clients?")) return;
    btn.disabled = true;
    try {
      const res = await fetch("/api/contacts/demo-complete-all", { method: "POST" });
      const data = await res.json();
      await loadContacts();
      loadOverview?.();
      alert(`Demo flow completed for ${data.processed || 0} client(s).`);
    } finally {
      btn.disabled = false;
    }
  });
}

bindContactsPage();
