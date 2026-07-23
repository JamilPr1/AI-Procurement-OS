/* Detail modal — leads, deals, suppliers */

function esc(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}

function fmtDate(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleString(); } catch { return String(iso).slice(0, 16); }
}

function fmtMoney(n) {
  if (n == null || n === "" || Number.isNaN(Number(n))) return "—";
  const v = Number(n);
  if (v === 0) return "—";
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function gmailComposeUrl(to, subject = "", body = "") {
  const params = new URLSearchParams({ view: "cm", fs: "1" });
  if (to) params.set("to", to);
  if (subject) params.set("su", subject);
  if (body) params.set("body", body);
  return `https://mail.google.com/mail/?${params.toString()}`;
}

function outlookComposeUrl(to, subject = "", body = "") {
  const params = new URLSearchParams();
  if (to) params.set("to", to);
  if (subject) params.set("subject", subject);
  if (body) params.set("body", body);
  return `https://outlook.live.com/mail/0/deeplink/compose?${params.toString()}`;
}

function renderEmailComposeActions(to, subject = "", body = "", { primaryLabel = "Open in Gmail" } = {}) {
  if (!to || to === "—") return "";
  const gmail = gmailComposeUrl(to, subject, body);
  const outlook = outlookComposeUrl(to, subject, body);
  return `<div class="contact-actions email-compose-actions">
    <a class="btn primary" href="${gmail}" target="_blank" rel="noopener">${esc(primaryLabel)}</a>
    <a class="btn ghost" href="${outlook}" target="_blank" rel="noopener">Open in Outlook</a>
    <button type="button" class="btn ghost btn-copy-email-draft">Copy email text</button>
  </div>`;
}

function scoreClass(s) {
  if (s >= 80) return "score-high";
  if (s >= 60) return "score-mid";
  return "score-low";
}

function section(title, desc, bodyHtml) {
  return `<section class="detail-section">
    <div class="detail-section-head">
      <h3>${esc(title)}</h3>
      ${desc ? `<p class="detail-section-desc">${esc(desc)}</p>` : ""}
    </div>
    <div class="detail-section-body">${bodyHtml}</div>
  </section>`;
}

function kvRow(label, value, { raw = false } = {}) {
  const val = raw ? value : esc(value ?? "—");
  return `<div class="detail-kv"><span class="detail-kv-label">${esc(label)}</span><span class="detail-kv-value">${val}</span></div>`;
}

function contactBlock(contacts) {
  if (!contacts) return "<p class='muted'>No contact information extracted yet.</p>";
  const wa = (contacts.whatsapp || []).map((w) =>
    `<a class="contact-chip whatsapp" href="${esc(w.link)}" target="_blank" rel="noopener">
      <span class="chip-icon">WA</span> ${esc(w.number)}
    </a>`
  ).join("");
  const emails = (contacts.emails || []).map((e) =>
    `<a class="contact-chip email" href="mailto:${esc(e)}">${esc(e)}</a>`
  ).join("");
  const phones = (contacts.phones || []).map((p) =>
    `<a class="contact-chip phone" href="tel:${esc(p)}">${esc(p)}</a>`
  ).join("");
  if (!wa && !emails && !phones) {
    return "<p class='muted'>No direct contacts found. Use the platform link below to reach the supplier.</p>";
  }
  return `<div class="contact-grid">${wa}${emails}${phones}</div>`;
}

function mergeProductImages(...sources) {
  const seen = new Set();
  const out = [];
  for (const list of sources) {
    if (!Array.isArray(list)) continue;
    for (const img of list) {
      const key = img?.serve_url || img?.url || img?.filename;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      out.push(img);
    }
  }
  return out;
}

let lightboxGallery = [];
let lightboxIndex = 0;

function openImageLightbox(thumbBtn) {
  const grid = thumbBtn.closest(".product-image-grid");
  if (!grid) return;
  lightboxGallery = [...grid.querySelectorAll(".product-image-thumb")];
  lightboxIndex = lightboxGallery.indexOf(thumbBtn);
  if (lightboxIndex < 0) lightboxIndex = 0;
  showLightboxImage(lightboxIndex);
  const lb = document.getElementById("imageLightbox");
  lb?.classList.remove("hidden");
  document.body.classList.add("lightbox-open");
}

function showLightboxImage(index) {
  if (!lightboxGallery.length) return;
  if (index < 0) index = lightboxGallery.length - 1;
  if (index >= lightboxGallery.length) index = 0;
  lightboxIndex = index;
  const btn = lightboxGallery[index];
  const src = btn.dataset.lightboxSrc;
  const alt = btn.dataset.lightboxAlt || "Product image";
  const img = document.getElementById("imageLightboxImg");
  const cap = document.getElementById("imageLightboxCaption");
  const counter = document.getElementById("imageLightboxCounter");
  if (img) {
    img.src = src;
    img.alt = alt;
  }
  if (cap) cap.textContent = alt;
  if (counter) {
    counter.textContent = lightboxGallery.length > 1 ? `${index + 1} / ${lightboxGallery.length}` : "";
  }
  const prev = document.getElementById("imageLightboxPrev");
  const next = document.getElementById("imageLightboxNext");
  if (prev) prev.style.visibility = lightboxGallery.length > 1 ? "visible" : "hidden";
  if (next) next.style.visibility = lightboxGallery.length > 1 ? "visible" : "hidden";
}

function closeImageLightbox() {
  document.getElementById("imageLightbox")?.classList.add("hidden");
  document.body.classList.remove("lightbox-open");
  const img = document.getElementById("imageLightboxImg");
  if (img) img.src = "";
  lightboxGallery = [];
}

function initProductImageLightbox() {
  document.addEventListener("click", (e) => {
    const thumb = e.target.closest(".product-image-thumb");
    if (thumb) {
      e.preventDefault();
      e.stopPropagation();
      openImageLightbox(thumb);
      return;
    }
  });
  document.getElementById("imageLightboxClose")?.addEventListener("click", closeImageLightbox);
  document.getElementById("imageLightboxBackdrop")?.addEventListener("click", closeImageLightbox);
  document.getElementById("imageLightboxPrev")?.addEventListener("click", (e) => {
    e.stopPropagation();
    showLightboxImage(lightboxIndex - 1);
  });
  document.getElementById("imageLightboxNext")?.addEventListener("click", (e) => {
    e.stopPropagation();
    showLightboxImage(lightboxIndex + 1);
  });
}

function renderProductImages(images, label = "Product images") {
  const list = mergeProductImages(images);
  if (!list.length) return "";
  return `<div class="product-images-block">
    <h4 class="product-images-title">${esc(label)}</h4>
    <div class="product-image-grid">${list.map((img) => {
      const src = img.serve_url || img.url || "";
      const alt = img.alt || "Product";
      if (!src) return "";
      return `<figure class="product-image-card">
        <button type="button" class="product-image-thumb"
          data-lightbox-src="${esc(src)}"
          data-lightbox-alt="${esc(alt)}"
          aria-label="View ${esc(alt)}">
          <img src="${esc(src)}" alt="${esc(alt)}" loading="lazy" />
          <span class="product-image-zoom" aria-hidden="true">&#128269;</span>
        </button>
        <figcaption>${esc(img.alt || "Catalog item")}</figcaption>
      </figure>`;
    }).join("")}</div>
  </div>`;
}

function renderBuyerContactBlock(contacts, fallback = {}) {
  const email = contacts?.primary_email || contacts?.emails?.[0] || fallback?.email || "";
  const phone = contacts?.primary_phone || contacts?.phones?.[0] || fallback?.phone || "";
  const website = contacts?.website || fallback?.website || "";
  const note = contacts?.contact_note || "";
  const actions = [];

  if (email) {
    actions.push(`<a class="btn primary buyer-contact-btn" href="${gmailComposeUrl(email)}" target="_blank" rel="noopener">
      <span class="buyer-contact-label">Email in Gmail</span>
      <span class="buyer-contact-value">${esc(email)}</span>
    </a>`);
  }
  if (phone) {
    actions.push(`<a class="btn ghost buyer-contact-btn" href="tel:${esc(phone)}">
      <span class="buyer-contact-label">Call</span>
      <span class="buyer-contact-value">${esc(phone)}</span>
    </a>`);
  }
  if (website) {
    let host = website;
    try { host = new URL(website).hostname.replace(/^www\./, ""); } catch { /* keep url */ }
    actions.push(`<a class="btn ghost" href="${esc(website)}" target="_blank" rel="noopener">Visit ${esc(host)}</a>`);
  }

  if (!actions.length) {
    return `<p class='muted'>${esc(note || "No buyer contact on file — add details on the Leads page.")}</p>`;
  }
  return `${note ? `<p class="hint buyer-contact-note">${esc(note)}</p>` : ""}<div class="buyer-contact-actions">${actions.join("")}</div>`;
}

function tagList(items) {
  if (!items?.length) return "<span class='muted'>—</span>";
  return items.map((t) => `<span class="tag">${esc(t)}</span>`).join("");
}

function normalizeQuotesList(source) {
  if (!source) return [];
  if (Array.isArray(source)) return source;
  if (typeof source === "object") {
    return source.quotes || source.comparison_table || source.supplier_comparison || [];
  }
  return [];
}

function renderQuoteComparisonTable(quotes, comparison = {}) {
  const list = normalizeQuotesList(quotes);
  const comp = comparison && !Array.isArray(comparison) ? comparison : {};
  const rec = comp.recommended_supplier || comp.recommended_option || "";
  if (!list.length) {
    return "<p class='muted'>No supplier quotes compared yet. Run quote comparison on Hot Leads first.</p>";
  }
  const rows = list.map((q) => {
    const factory = q.factory || q.factory_name || "—";
    const isPick = rec
      && (factory === rec
        || factory.toLowerCase().includes(rec.toLowerCase())
        || rec.toLowerCase().includes(factory.toLowerCase()));
    const hasPrice = q.price_known !== false && q.price_usd != null && Number(q.price_usd) > 0;
    return `<tr class="${isPick ? "best-match" : ""}">
      <td>
        <strong>${esc(factory)}</strong>
        ${isPick ? '<span class="tag tag-accent">Recommended</span>' : ""}
      </td>
      <td>${hasPrice ? fmtMoney(q.price_usd) : "TBD"}</td>
      <td>${q.moq ?? "—"}</td>
      <td>${q.rating ?? "—"}</td>
      <td>${q.url ? `<a class="link" href="${esc(q.url)}" target="_blank" rel="noopener">View</a>` : ""}</td>
    </tr>`;
  }).join("");
  const rationale = comp.reasoning || comp.rationale || "";
  return `<div class="quote-compare-wrap">
    <table class="compare-table">
      <thead><tr>
        <th>Supplier</th><th>Unit price</th><th>MOQ</th><th>Rating</th><th></th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    ${rec ? `<p class="callout"><strong>Recommended:</strong> ${esc(rec)}${rationale ? ` — ${esc(rationale)}` : ""}</p>` : ""}
  </div>`;
}

function renderProposalEmailDraft(draft) {
  if (!draft || typeof draft !== "object") return "";
  const body = draft.body || "";
  return [
    kvRow("To", draft.to || "—"),
    kvRow("Subject", draft.subject || "—"),
    kvRow("Status", draft.status || "draft"),
    draft.sent_at ? kvRow("Sent", fmtDate(draft.sent_at)) : "",
    renderProductImages(draft.product_images, "Images in email"),
    body ? `<pre class="draft-body">${esc(body)}</pre>` : "",
    body && draft.to ? renderEmailComposeActions(draft.to, draft.subject || "", body) : "",
  ].filter(Boolean).join("");
}

function openDetailModal(eyebrow, title, subtitle) {
  const modal = document.getElementById("detailModal");
  document.getElementById("modalEyebrow").textContent = eyebrow;
  document.getElementById("modalTitle").textContent = title;
  document.getElementById("modalSubtitle").textContent = subtitle || "";
  document.getElementById("modalBody").innerHTML = '<div class="modal-loading">Loading details...</div>';
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function closeDetailModal() {
  document.getElementById("detailModal")?.classList.add("hidden");
  document.body.classList.remove("modal-open");
  document.querySelectorAll(".data-table tbody tr.selected").forEach((tr) => tr.classList.remove("selected"));
}

function renderLeadDetail(data) {
  const lead = data.lead || {};
  const d = data.data || {};
  const company = data.company_profile || {};
  const needs = data.sourcing_needs || {};
  const contacts = data.contacts || {};

  const hooks = (company.personalization_hooks || []).filter(Boolean);
  const products = company.products_services || needs.likely_needs || [];

  let dealsHtml = "<p class='muted'>No active deals linked to this lead yet.</p>";
  if (data.deals?.length) {
    dealsHtml = `<div class="mini-table-wrap"><table class="mini-table">
      <thead><tr><th>Stage</th><th>Status</th><th>Product</th><th>Updated</th></tr></thead>
      <tbody>${data.deals.map((deal) => {
        const req = deal.buyer_requirements || {};
        return `<tr class="clickable-deal" data-deal-id="${esc(deal.id)}">
          <td>${esc(deal.stage)}</td>
          <td><span class="status-pill status-${deal.status}">${esc(deal.status)}</span></td>
          <td>${esc(req.product_description || "—")}</td>
          <td>${fmtDate(deal.updated_at)}</td>
        </tr>`;
      }).join("")}</tbody></table></div>`;
  }

  const preview = d.website_text_preview
    ? `<div class="text-preview">${esc(d.website_text_preview.slice(0, 800))}${d.website_text_preview.length > 800 ? "…" : ""}</div>`
    : "<p class='muted'>Website content not yet fetched.</p>";

  return [
    section("Overview", "Core buyer identity and qualification score.", [
      kvRow("Company", lead.company_name),
      kvRow("Lead score", `<span class="score-pill ${scoreClass(lead.lead_score)}">${Math.round(lead.lead_score || 0)}</span>`, { raw: true }),
      kvRow("Status", `<span class="status-pill status-${lead.status || "new"}">${esc(lead.status || "new")}</span>`, { raw: true }),
      kvRow("Industry", d.industry || "—"),
      kvRow("Source", d.source || "web discovery"),
      kvRow("First seen", fmtDate(d.first_seen_at || lead.created_at)),
      kvRow("Last updated", fmtDate(lead.updated_at)),
    ].join("")),
    section("Contact", "Reach the buyer directly.", renderBuyerContactBlock(contacts)),
    section("What they are looking for", "Inferred from website analysis and any linked deal requirements.", [
      kvRow("Primary need", needs.product || products[0] || "—"),
      needs.quantity ? kvRow("Quantity", needs.quantity) : "",
      needs.destination ? kvRow("Ship to", needs.destination) : "",
      kvRow("Products / services", tagList(products), { raw: true }),
      company.company_summary ? `<div class="callout"><strong>Company summary</strong><p>${esc(company.company_summary)}</p></div>` : "",
      renderProductImages(mergeProductImages(company.product_images, d.product_images), "Products from their website"),
    ].join("")),
    hooks.length ? section("Outreach angles", "Personalization hooks for your first message.", hooks.map((h) => `<div class="hook-item">${esc(h)}</div>`).join("")) : "",
    section("Website intelligence", "Content extracted from their public site.", [
      kvRow("Website", d.website ? `<a class="link" href="${esc(d.website)}" target="_blank">${esc(d.domain || d.website)}</a>` : "—", { raw: true }),
      kvRow("Domain", d.domain || "—"),
      preview,
    ].join("")),
    section("Linked deals", "Sourcing opportunities created from this lead.", dealsHtml),
  ].join("");
}

function renderDealDetail(data) {
  const deal = data.deal || {};
  const req = data.requirements || {};
  const spec = data.product_spec || {};
  const proposal = data.proposal || {};
  const quotesData = data.quotes || {};
  const quotes = normalizeQuotesList(quotesData);
  const lead = data.lead || {};
  const company = data.company_profile || {};
  const outreach = data.outreach || {};
  const allImages = mergeProductImages(
    company.product_images,
    spec.reference_images,
    spec.product_images,
    outreach.product_images,
    proposal.reference_images,
    proposal.product_images,
  );

  const pricing = spec.typical_pricing_range || {};
  const proposalItems = Object.entries(proposal).filter(([, v]) => v != null && v !== "");
  const skipProposalKeys = new Set([
    "send_result",
    "requirements_recap",
    "supplier_comparison",
    "client_email_draft",
    "next_steps",
  ]);

  const quotesHtml = renderQuoteComparisonTable(
    quotes.length ? quotes : proposal.supplier_comparison,
    quotesData.comparison || { recommended_supplier: proposal.recommended_option },
  );

  let proposalHtml = "<p class='muted'>Proposal not yet generated. Approve pipeline stages to build a client offer.</p>";
  if (proposalItems.length) {
    proposalHtml = [
      ...proposalItems
        .filter(([k]) => !skipProposalKeys.has(k))
        .map(([k, v]) => {
          const label = k.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
          if (Array.isArray(v)) {
            if (v.length && typeof v[0] === "object") return "";
            return kvRow(label, v.join(" → "));
          }
          if (typeof v === "object") return "";
          return kvRow(label, String(v));
        }),
      proposal.status ? kvRow("Email status", proposal.status) : "",
      proposal.sent_at ? kvRow("Sent at", fmtDate(proposal.sent_at)) : "",
      (proposal.next_steps || []).length ? kvRow("Next steps", proposal.next_steps.join(" → ")) : "",
      proposal.client_email_draft
        ? section("Client email draft", "Email prepared for buyer review.", renderProposalEmailDraft(proposal.client_email_draft))
        : "",
      renderProductImages(mergeProductImages(proposal.reference_images, proposal.product_images, company.product_images), "Images in proposal"),
    ].filter(Boolean).join("");
  }

  const outreachHtml = outreach.body
    ? [
      kvRow("To", outreach.to),
      kvRow("Subject", outreach.subject),
      kvRow("Status", outreach.status),
      renderProductImages(outreach.product_images || company.product_images, "Images in outreach"),
      `<pre class="draft-body">${esc(outreach.body)}</pre>`,
    ].join("")
    : "<p class='muted'>Outreach email not drafted yet.</p>";

  let rfqsHtml = "";
  if (data.rfqs?.length) {
    rfqsHtml = data.rfqs.map((r) => {
      const d = r.data || {};
      const body = typeof d === "object" ? d.rfq_body || JSON.stringify(d) : String(d);
      return `<div class="rfq-review">${kvRow("Status", r.status)}${kvRow("Created", fmtDate(r.created_at))}<pre class="draft-body">${esc(body)}</pre></div>`;
    }).join("");
  }

  return [
    allImages.length ? section("Product catalog", "Images extracted from the buyer's website.", renderProductImages(allImages, "All product references")) : "",
    section("Deal overview", "Current stage and buyer linkage.", [
      kvRow("Buyer", lead.company_name || deal.lead_company || "—"),
      kvRow("Stage", deal.stage),
      kvRow("Status", `<span class="status-pill status-${deal.status}">${esc(deal.status)}</span>`, { raw: true }),
      kvRow("Created", fmtDate(deal.created_at)),
      kvRow("Updated", fmtDate(deal.updated_at)),
      lead.lead_score != null ? kvRow("Lead score", Math.round(lead.lead_score)) : "",
    ].join("")),
    section("Buyer requirements", "What the client needs sourced.", [
      kvRow("Product", req.product_description || "—"),
      kvRow("Quantity", req.quantity || "—"),
      kvRow("Target price", req.target_price_usd ? fmtMoney(req.target_price_usd) : "—"),
      kvRow("Destination", req.shipping_destination || "—"),
      kvRow("Timeline", req.timeline || req.delivery_timeline || "—"),
      req.notes ? `<div class="callout"><strong>Notes</strong><p>${esc(req.notes)}</p></div>` : "",
    ].join("")),
    section("Product specification", "Technical and commercial parameters for sourcing.", [
      kvRow("Category", spec.product_category || "—"),
      kvRow("Materials", tagList(spec.materials), { raw: true }),
      kvRow("Packaging", spec.standard_packaging || "—"),
      pricing.min_usd != null ? kvRow("Price range", `${fmtMoney(pricing.min_usd)} – ${fmtMoney(pricing.max_usd)} ${pricing.unit || ""}`) : "",
      kvRow("Manufacturing regions", tagList(spec.manufacturing_regions), { raw: true }),
      spec.technical_notes ? `<div class="callout"><p>${esc(spec.technical_notes)}</p></div>` : "",
      renderProductImages(mergeProductImages(spec.reference_images, spec.product_images, company.product_images), "Reference product images"),
    ].join("")),
    section("What we can propose", "Client-facing offer built from quotes and margin rules.", proposalHtml),
    section("Supplier comparison", "Factory options discovered via live search — compare price, MOQ, and rating.", quotesHtml),
    section("Outreach email", "First contact email drafted/sent to this buyer.", outreachHtml),
    data.rfqs?.length ? section("RFQ emails", "Formal quote requests sent to manufacturers.", rfqsHtml) : "",
  ].join("");
}

function renderSupplierDetail(data) {
  const supplier = data.supplier || {};
  const d = data.data || {};
  const contacts = data.contacts || {};

  const platform = d.platform_source || "—";
  const url = d.url || "";

  return [
    section("Factory profile", "Manufacturer discovered through live B2B search.", [
      kvRow("Factory", supplier.factory_name),
      kvRow("Platform", platform),
      kvRow("Trust score", `<span class="score-pill ${scoreClass(supplier.trust_score)}">${Math.round(supplier.trust_score || 0)}</span>`, { raw: true }),
      kvRow("Recommendation", d.recommendation || "—"),
      kvRow("Source", d.source || "web search"),
      kvRow("Added", fmtDate(supplier.created_at)),
      kvRow("Updated", fmtDate(supplier.updated_at)),
    ].join("")),
    section("Contact channels", "Direct outreach — WhatsApp preferred for fast factory communication.", [
      contactBlock(contacts),
      url ? `<div class="platform-link"><a class="btn primary" href="${esc(url)}" target="_blank">Open on ${esc(platform)}</a></div>` : "",
      data.alibaba_profile ? `<p class="hint">Alibaba supplier profile available — use platform messaging if no WhatsApp is listed.</p>` : "",
    ].join("")),
    section("Commercial terms", "Pricing and order minimums from search results.", [
      kvRow("Unit price (est.)", fmtMoney(d.unit_price_estimate_usd)),
      kvRow("MOQ", d.moq || "—"),
      kvRow("Lead time", d.lead_time_days ? `${d.lead_time_days} days` : "—"),
      kvRow("Years in business", d.years_in_business || "—"),
      kvRow("Certifications", tagList(d.certifications), { raw: true }),
      kvRow("Export countries", tagList(d.export_countries), { raw: true }),
    ].join("")),
    d.search_snippet ? section("Listing excerpt", "Text captured from the supplier's product page.", `<div class="text-preview">${esc(d.search_snippet)}</div>`) : "",
  ].join("");
}

async function showLeadDetail(id) {
  openDetailModal("Lead", "Loading…", "");
  document.querySelectorAll(`tr[data-id="${id}"]`).forEach((tr) => tr.classList.add("selected"));
  try {
    const res = await fetch(`/api/leads/${id}`);
    if (!res.ok) throw new Error("Lead not found");
    const data = await res.json();
    const lead = data.lead || {};
    document.getElementById("modalTitle").textContent = lead.company_name || "Lead";
    document.getElementById("modalSubtitle").textContent = data.data?.industry
      ? `${data.data.industry} · Score ${Math.round(lead.lead_score || 0)}`
      : `Score ${Math.round(lead.lead_score || 0)}`;
    document.getElementById("modalBody").innerHTML = renderLeadDetail(data);
    document.querySelectorAll(".clickable-deal").forEach((tr) => {
      tr.onclick = (e) => {
        e.stopPropagation();
        showDealDetail(tr.dataset.dealId);
      };
    });
  } catch (err) {
    document.getElementById("modalBody").innerHTML = `<p class="error-msg">${esc(err.message)}</p>`;
  }
}

async function showDealDetail(id) {
  openDetailModal("Deal", "Loading…", "");
  document.querySelectorAll(`tr[data-id="${id}"]`).forEach((tr) => tr.classList.add("selected"));
  try {
    const res = await fetch(`/api/deals/${id}`);
    if (!res.ok) throw new Error("Deal not found");
    const data = await res.json();
    const deal = data.deal || {};
    const req = data.requirements || {};
    document.getElementById("modalTitle").textContent = data.lead?.company_name || deal.lead_company || "Deal";
    document.getElementById("modalSubtitle").textContent = `${deal.stage || "—"} · ${req.product_description || "Sourcing opportunity"}`;
    document.getElementById("modalBody").innerHTML = renderDealDetail(data);
  } catch (err) {
    document.getElementById("modalBody").innerHTML = `<p class="error-msg">${esc(err.message)}</p>`;
  }
}

async function showSupplierDetail(id) {
  openDetailModal("Supplier", "Loading…", "");
  document.querySelectorAll(`tr[data-id="${id}"]`).forEach((tr) => tr.classList.add("selected"));
  try {
    const res = await fetch(`/api/suppliers/${id}`);
    if (!res.ok) throw new Error("Supplier not found");
    const data = await res.json();
    const supplier = data.supplier || {};
    const d = data.data || {};
    document.getElementById("modalTitle").textContent = (supplier.factory_name || "Supplier").slice(0, 80);
    document.getElementById("modalSubtitle").textContent = `${d.platform_source || "B2B"} · Trust ${Math.round(supplier.trust_score || 0)}`;
    document.getElementById("modalBody").innerHTML = renderSupplierDetail(data);
  } catch (err) {
    document.getElementById("modalBody").innerHTML = `<p class="error-msg">${esc(err.message)}</p>`;
  }
}

document.getElementById("modalClose")?.addEventListener("click", closeDetailModal);
document.getElementById("modalBackdrop")?.addEventListener("click", closeDetailModal);
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const lb = document.getElementById("imageLightbox");
  if (lb && !lb.classList.contains("hidden")) {
    closeImageLightbox();
    return;
  }
  closeDetailModal();
});
initProductImageLightbox();

document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".btn-copy-email-draft");
  if (!btn) return;
  e.preventDefault();
  const pre = btn.closest("#modalBody, .detail-section-body, .hot-block")?.querySelector(".draft-body")
    || document.getElementById("modalBody")?.querySelector(".draft-body");
  const text = pre?.textContent?.trim() || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const label = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = label; }, 2000);
  } catch {
    prompt("Copy email text:", text);
  }
});

document.addEventListener("click", async (e) => {
  const btn = e.target.closest(".btn-copy-email-draft");
  if (!btn) return;
  e.preventDefault();
  const pre = btn.closest("#modalBody, .detail-section-body, .hot-block")?.querySelector(".draft-body")
    || document.getElementById("modalBody")?.querySelector(".draft-body");
  const text = pre?.textContent?.trim() || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    const label = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = label; }, 2000);
  } catch {
    prompt("Copy email text:", text);
  }
});
