/* Hot Leads — list view + step wizard with editable drafts & step navigation */

let hotLeadsData = [];
let hotFilter = "hot";
let activeLeadId = null;
let activeBrief = null;
let viewingStepId = null;
let stepRunning = false;
let activityTimer = null;

const PIPELINE_STEPS = [
  { id: "company_research", label: "Research", artifact: "company" },
  { id: "personalization", label: "Personalize", artifact: "personalization" },
  { id: "outreach", label: "Outreach", artifact: "outreach" },
  { id: "qualification", label: "Open Deal", artifact: "requirements" },
  { id: "product_research", label: "Product", artifact: "product_spec" },
  { id: "supplier_discovery", label: "Find Suppliers", artifact: "suppliers" },
  { id: "supplier_verification", label: "Verify", artifact: "supplier_approval" },
  { id: "rfq", label: "RFQ", artifact: "rfqs" },
  { id: "quote_comparison", label: "Quotes", artifact: "quotes" },
  { id: "proposal", label: "Proposal", artifact: "proposal" },
  { id: "tracking", label: "Tracking", artifact: null },
];

const STEP_ACTIVITY = {
  company_research: ["Fetching company website…", "Analyzing products…", "Extracting buying signals…"],
  personalization: ["Reading company profile…", "Drafting personalized outreach…", "Tailoring message…"],
  outreach: ["Composing outreach email…", "Adding product references…", "Preparing preview…"],
  qualification: ["Qualifying buyer fit…", "Creating sourcing deal…", "Capturing requirements…"],
  product_research: ["Defining specifications…", "Checking certifications…", "Estimating price range…"],
  supplier_discovery: ["Searching manufacturers…", "Matching factories…", "Ranking candidates…"],
  supplier_verification: ["Scoring trust profiles…", "Verifying certifications…", "Building shortlist…"],
  rfq: ["Drafting formal RFQ…", "Selecting suppliers…", "Preparing quote request…"],
  quote_comparison: ["Collecting quotes…", "Comparing price and MOQ…", "Ranking options…"],
  proposal: ["Building proposal…", "Summarizing option…", "Preparing client email…"],
};

function heatBadge(heat, score) {
  const labels = { on_fire: "On Fire", hot: "Hot", warm: "Warm", cool: "Cool" };
  return `<span class="heat-badge heat-${heat || "cool"}">${labels[heat] || "Cool"} ${Math.round(score)}</span>`;
}

function currentStepId(brief) {
  return brief?.next_step?.stage || "company_research";
}

function stepIndex(stepId) {
  const idx = PIPELINE_STEPS.findIndex((s) => s.id === stepId);
  return idx >= 0 ? idx : 0;
}

function pipelineStepStatus(brief, stepId) {
  const steps = brief?.pipeline?.steps || [];
  const found = steps.find((s) => s.id === stepId);
  if (found) return found.status;
  const cur = stepIndex(currentStepId(brief));
  const idx = stepIndex(stepId);
  if (idx < cur) return "completed";
  if (idx === cur) return "current";
  return "pending";
}

function displayStepId(brief) {
  return viewingStepId || currentStepId(brief);
}

function renderProgressBar(brief) {
  const current = stepIndex(currentStepId(brief));
  const terminal = brief?.next_step?.terminal;
  const active = displayStepId(brief);

  return `<div class="step-progress" role="tablist" aria-label="Pipeline progress">
    ${PIPELINE_STEPS.map((s, i) => {
      const status = pipelineStepStatus(brief, s.id);
      const isDone = terminal && s.id === "tracking" ? true : status === "completed" || i < current;
      const isCurrent = s.id === active;
      const isFuture = !isDone && !isCurrent && s.id !== active;
      let cls = "step-pill";
      if (isDone) cls += " done";
      if (isCurrent) cls += " current";
      const clickable = isDone || isCurrent || status === "completed";
      const tag = clickable ? "button" : "div";
      const attrs = clickable
        ? `type="button" class="${cls}" data-step-id="${esc(s.id)}" role="tab" aria-selected="${isCurrent}"`
        : `class="${cls} disabled" role="tab" aria-disabled="true"`;
      return `<${tag} ${attrs} title="${esc(s.label)}">
        <span class="step-pill-dot">${isDone ? "✓" : i + 1}</span>
        <span class="step-pill-label">${esc(s.label)}</span>
      </${tag}>`;
    }).join("")}
  </div>`;
}

function fieldRow(label, html) {
  return `<label class="draft-field"><span class="draft-field-label">${esc(label)}</span>${html}</label>`;
}

function renderRfqEditor(rfq) {
  const d = rfq || {};
  const suppliers = d.suppliers || [];
  return `<form class="draft-edit-form" id="draftEditForm">
    ${fieldRow("Subject", `<input type="text" name="subject" value="${escAttr(d.subject || "")}" class="draft-input" />`)}
    ${fieldRow("RFQ body", `<textarea name="rfq_body" class="draft-textarea" rows="14">${esc(d.rfq_body || "")}</textarea>`)}
    <div class="rfq-supplier-list">
      <p class="block-desc">Recipients — ${suppliers.length} supplier${suppliers.length === 1 ? "" : "s"}</p>
      ${suppliers.length
        ? `<ul class="supplier-approve-list">${suppliers.map((s) =>
            `<li><strong>${esc(s.factory_name || "Supplier")}</strong>${
              s.url ? ` · <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer" class="link">Visit store ↗</a>` : ""
            }</li>`
          ).join("")}</ul>`
        : `<p class="muted">No suppliers linked — run supplier discovery first.</p>`}
    </div>
  </form>`;
}

function renderEditableDraft(pending, brief, stageId) {
  const artifacts = brief.pipeline?.artifacts || {};
  const pendingGate = pending?.status === "pending" ? pending : null;

  if (pendingGate) {
    const draft = pendingGate.draft || {};
    const dtype = draft.type || "";
    const d = draft.draft || draft;

    if (dtype === "outreach" || pendingGate.gate === "outreach_first_batch") {
      return `<form class="draft-edit-form" id="draftEditForm">
        ${fieldRow("To", `<input type="email" name="to" value="${escAttr(d.to || "")}" class="draft-input" />`)}
        ${fieldRow("Subject", `<input type="text" name="subject" value="${escAttr(d.subject || "")}" class="draft-input" />`)}
        ${typeof renderProductImages === "function" ? renderProductImages(d.product_images || [], "Factory products we can source") : ""}
        ${fieldRow("Body", `<textarea name="body" class="draft-textarea" rows="12">${esc(d.body || "")}</textarea>`)}
      </form>`;
    }
    if (dtype === "rfq" || pendingGate.gate === "rfq_send") {
      return renderRfqEditor(d);
    }
    if (dtype === "suppliers" || pendingGate.gate === "supplier_final_approval") {
      const suppliers = draft.suppliers || d.suppliers || [];
      return `<div class="draft-readonly">
        <ul class="supplier-approve-list">${suppliers.map((s) =>
          `<li><strong>${esc(s.factory_name)}</strong> — trust ${Math.round(s.trust_score || 0)} · ${esc(s.recommendation || "")}</li>`
        ).join("")}</ul>
        <p class="hint">Supplier list is generated by AI. Re-run verification to refresh.</p>
      </div>`;
    }
    if (dtype === "proposal" || pendingGate.gate === "proposal_send") {
      return `<form class="draft-edit-form" id="draftEditForm">
        ${fieldRow("To", `<input type="email" name="to" value="${escAttr(d.to || "")}" class="draft-input" />`)}
        ${fieldRow("Subject", `<input type="text" name="subject" value="${escAttr(d.subject || "")}" class="draft-input" />`)}
        ${typeof renderProductImages === "function" ? renderProductImages(d.product_images || d.proposal?.reference_images || [], "Product images") : ""}
        ${fieldRow("Email body", `<textarea name="body" class="draft-textarea proposal-email-body" rows="20">${esc(d.body || "")}</textarea>`)}
      </form>`;
    }
    if (dtype === "personalization") {
      return `<form class="draft-edit-form" id="draftEditForm">
        ${fieldRow("Email body", `<textarea name="email_body" class="draft-textarea" rows="12">${esc(d.email_body || "")}</textarea>`)}
      </form>`;
    }
    return `<form class="draft-edit-form" id="draftEditForm">
      ${fieldRow("Content", `<textarea name="body" class="draft-textarea" rows="10">${esc(JSON.stringify(draft, null, 2))}</textarea>`)}
    </form>`;
  }

  return renderArtifactEditor(stageId, artifacts, brief);
}

function escAttr(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

function stepHasContent(brief, stageId) {
  const artKey = PIPELINE_STEPS.find((s) => s.id === stageId)?.artifact;
  const artifacts = brief.pipeline?.artifacts || {};
  const art = artKey ? artifacts[artKey] : null;

  if (stageId === "company_research") {
    const c = art || {};
    return !!(c.company_summary || brief.intent?.summary);
  }
  if (stageId === "personalization") {
    const p = art || {};
    return !!(p.email_body || p.subject_line || p.linkedin_message);
  }
  if (stageId === "outreach") {
    const o = art || {};
    return !!(o.body || o.subject);
  }
  if (stageId === "qualification") {
    const r = art || brief.deal?.buyer_requirements || {};
    return !!(r.product_description || brief.deal?.id);
  }
  if (stageId === "product_research") {
    const s = art || {};
    return !!(s.product_category || s.materials?.length);
  }
  if (stageId === "supplier_discovery" || stageId === "supplier_verification") {
    return !!(brief.supplier_matches?.length);
  }
  if (stageId === "rfq") {
    const rfqs = art || [];
    return !!(Array.isArray(rfqs) ? rfqs[0]?.rfq_body : null);
  }
  if (stageId === "quote_comparison") {
    return !!((art || {}).quotes || []).length;
  }
  if (stageId === "proposal") {
    const p = art || {};
    return !!(p.title || p.executive_summary);
  }
  return !!art;
}

function renderStepPreview(stageId, brief) {
  const intent = brief.intent || {};
  const previews = {
    company_research: `
      <div class="step-preview">
        <p>AI will scan the buyer's website and build a company profile with products, signals, and images.</p>
        ${brief.contact?.website ? `<p class="hint"><a class="link" href="${esc(brief.contact.website)}" target="_blank">Visit website</a></p>` : ""}
      </div>`,
    personalization: `
      <div class="step-preview">
        <p>AI will draft a <strong>subject line</strong>, <strong>email body</strong>, and <strong>LinkedIn message</strong> using research from Step 1.</p>
        ${intent.summary ? `<div class="preview-context"><strong>Company insight (from research)</strong><p>${esc(intent.summary)}</p></div>` : ""}
        <p class="hint">Click <strong>Start this step</strong> to generate the draft — fields will appear here for you to review and edit.</p>
      </div>`,
    outreach: `
      <div class="step-preview">
        <p>AI will compose the first outreach email to introduce your agency to this buyer.</p>
        ${brief.personalization_draft?.subject_line ? `<p class="hint">Using personalization: "${esc(brief.personalization_draft.subject_line)}"</p>` : ""}
        <p class="hint">Click <strong>Start this step</strong> to generate the email draft.</p>
      </div>`,
    qualification: `
      <div class="step-preview">
        <p>AI will qualify this buyer and open a sourcing deal with their product requirements.</p>
        <p class="hint">Click <strong>Start this step</strong> to create the deal.</p>
      </div>`,
    product_research: `
      <div class="step-preview">
        <p>AI will define materials, certifications, and price range for <strong>${esc(intent.primary_need || "this product")}</strong>.</p>
        <p class="hint">Click <strong>Start this step</strong> to run product research.</p>
      </div>`,
    supplier_discovery: `
      <div class="step-preview">
        <p>Search manufacturers for <strong>${esc(intent.primary_need || "this product")}</strong>.</p>
        ${brief.supplier_matches?.length
          ? renderSupplierTable(brief.supplier_matches, brief)
          : `<p class="hint">Click <strong>Start this step</strong> to find suppliers.</p>`}
      </div>`,
    supplier_verification: `
      <div class="step-preview">
        <p>AI will score and vet factory options, then prepare a shortlist for your approval.</p>
        <p class="hint">Click <strong>Start this step</strong> to verify suppliers.</p>
      </div>`,
    rfq: `
      <div class="step-preview">
        <p>AI will draft a formal RFQ email to send to the top suppliers.</p>
        <p class="hint">Click <strong>Start this step</strong> to generate the RFQ.</p>
      </div>`,
    quote_comparison: `
      <div class="step-preview">
        <p>AI will compare supplier quotes by price, MOQ, and lead time.</p>
        <p class="hint">Click <strong>Start this step</strong> to compare quotes.</p>
      </div>`,
    proposal: `
      <div class="step-preview">
        <p>AI will build a client-facing proposal with recommended supplier and pricing.</p>
        <p class="hint">Click <strong>Start this step</strong> to generate the proposal.</p>
      </div>`,
  };
  return previews[stageId] || `<div class="step-preview"><p class="hint">Click <strong>Start this step</strong> to run this stage.</p></div>`;
}

function renderArtifactEditor(stageId, artifacts, brief) {
  const artKey = PIPELINE_STEPS.find((s) => s.id === stageId)?.artifact;
  if (!artKey) return `<p class="muted">No editable content for this step.</p>`;
  const art = artifacts[artKey];

  if (stageId === "company_research") {
    const c = art || {};
    return `<form class="draft-edit-form" id="draftEditForm">
      ${fieldRow("Company summary", `<textarea name="company_summary" class="draft-textarea" rows="8">${esc(c.company_summary || brief.intent?.summary || "")}</textarea>`)}
      ${brief.contact?.website ? `<p class="hint"><a class="link" href="${esc(brief.contact.website)}" target="_blank">Visit website</a></p>` : ""}
    </form>`;
  }
  if (stageId === "personalization") {
    const p = art || {};
    return `<form class="draft-edit-form" id="draftEditForm">
      ${fieldRow("Subject line", `<input type="text" name="subject_line" value="${escAttr(p.subject_line || "")}" class="draft-input" />`)}
      ${fieldRow("Email body", `<textarea name="email_body" class="draft-textarea" rows="10">${esc(p.email_body || "")}</textarea>`)}
      ${fieldRow("LinkedIn message", `<textarea name="linkedin_message" class="draft-textarea" rows="5">${esc(p.linkedin_message || "")}</textarea>`)}
    </form>`;
  }
  if (stageId === "outreach") {
    const o = art || {};
    return `<form class="draft-edit-form" id="draftEditForm">
      ${fieldRow("To", `<input type="email" name="to" value="${escAttr(o.to || brief.contact?.email || "")}" class="draft-input" />`)}
      ${fieldRow("Subject", `<input type="text" name="subject" value="${escAttr(o.subject || "")}" class="draft-input" />`)}
      ${fieldRow("Body", `<textarea name="body" class="draft-textarea" rows="12">${esc(o.body || "")}</textarea>`)}
      ${o.status === "sent" ? `<p class="hint">Already sent${o.sent_at ? ` · ${esc(o.sent_at)}` : ""}. Edits update the stored draft.</p>` : ""}
    </form>`;
  }
  if (stageId === "qualification") {
    const r = art || brief.deal?.buyer_requirements || {};
    return `<div class="draft-readonly">
      <div class="detail-kv"><span class="detail-kv-label">Product</span><span class="detail-kv-value">${esc(r.product_description || brief.intent?.primary_need || "—")}</span></div>
      <div class="detail-kv"><span class="detail-kv-label">Quantity</span><span class="detail-kv-value">${esc(r.quantity || "—")}</span></div>
      <div class="detail-kv"><span class="detail-kv-label">Destination</span><span class="detail-kv-value">${esc(r.shipping_destination || "—")}</span></div>
    </div>`;
  }
  if (stageId === "product_research") {
    const s = art || {};
    return `<form class="draft-edit-form" id="draftEditForm">
      ${fieldRow("Category", `<input type="text" name="title" value="${escAttr(s.product_category || brief.intent?.primary_need || "")}" class="draft-input" readonly />`)}
      ${fieldRow("Materials", `<input type="text" value="${escAttr((s.materials || []).join(", "))}" class="draft-input" readonly />`)}
      ${fieldRow("Notes", `<textarea name="executive_summary" class="draft-textarea" rows="6" readonly>${esc(s.standard_packaging || s.notes || "")}</textarea>`)}
    </form>`;
  }
  if (stageId === "supplier_discovery" || stageId === "supplier_verification") {
    return `<div class="step-detail-block">
      <p class="block-desc">Matched manufacturers for <strong>${esc(brief.intent?.primary_need || "this product")}</strong></p>
      ${renderSupplierTable(brief.supplier_matches, brief)}
    </div>`;
  }
  if (stageId === "rfq") {
    const rfqs = art || [];
    const r = Array.isArray(rfqs) ? rfqs[0] : null;
    return renderRfqEditor(r);
  }
  if (stageId === "quote_comparison") {
    const quotes = art?.quotes || [];
    if (!quotes.length) return `<p class="muted">No quotes yet. Run quote comparison first.</p>`;
    return typeof renderQuoteComparisonTable === "function"
      ? renderQuoteComparisonTable(quotes, art?.comparison || {})
      : `<p class="muted">${quotes.length} quote(s) on file.</p>`;
  }
  if (stageId === "proposal") {
    const p = art || {};
    return `<form class="draft-edit-form" id="draftEditForm">
      ${fieldRow("Title", `<input type="text" name="title" value="${escAttr(p.title || "")}" class="draft-input" />`)}
      ${fieldRow("Executive summary", `<textarea name="executive_summary" class="draft-textarea" rows="8">${esc(p.executive_summary || "")}</textarea>`)}
      <div class="detail-kv"><span class="detail-kv-label">Client price</span><span class="detail-kv-value">${p.client_price_usd ? fmtMoney(p.client_price_usd) : "—"}</span></div>
    </form>`;
  }
  return `<p class="muted">No content saved for this step yet.</p>`;
}

function supplierMatchId(m, i) {
  return m.supplier_id || m.url || `idx-${i}`;
}

function renderSupplierTable(matches, brief) {
  if (!matches?.length) return `<p class="muted">Suppliers will appear after discovery.</p>`;
  const selectedId = brief?.selected_supplier_id || "";
  const savedName = brief?.selected_supplier?.factory_name;
  return `
    <p class="hint supplier-picker-hint">Visit each factory store, then select your preferred supplier for this program.</p>
    ${savedName ? `<p class="supplier-selected-banner">Selected: <strong>${esc(savedName)}</strong></p>` : ""}
    <div class="table-wrap">
      <table class="compare-table supplier-picker-table">
        <thead><tr>
          <th class="col-pick"></th>
          <th>Supplier</th>
          <th>Match</th>
          <th>Price</th>
          <th>MOQ</th>
          <th>Trust</th>
          <th>Actions</th>
        </tr></thead>
        <tbody>${matches.map((m, i) => {
          const sid = supplierMatchId(m, i);
          const isSelected = selectedId ? selectedId === sid : i === 0;
          const isTop = i === 0 && !selectedId;
          return `
          <tr class="supplier-row ${isSelected ? "selected" : ""} ${isTop ? "best-match" : ""}" data-supplier-id="${escAttr(sid)}">
            <td class="col-pick"><input type="radio" name="supplierPick" value="${escAttr(sid)}" class="supplier-radio" ${isSelected ? "checked" : ""} aria-label="Select ${escAttr(m.factory_name || "supplier")}" /></td>
            <td>
              <strong>${esc(m.factory_name?.slice(0, 45) || "—")}</strong>
              ${isTop ? '<span class="tag tag-accent">Top match</span>' : ""}
              ${isSelected && selectedId ? '<span class="tag tag-success">Your pick</span>' : ""}
              ${m.match_reason ? `<div class="match-reason muted">${esc(m.match_reason)}</div>` : ""}
            </td>
            <td>${m.match_score ?? "—"}%</td>
            <td>${m.price_usd ? fmtMoney(m.price_usd) : "TBD"}</td>
            <td>${m.moq || "—"}</td>
            <td>${Math.round(m.trust_score || 0)}</td>
            <td class="supplier-actions">
              ${m.url
                ? `<a href="${esc(m.url)}" target="_blank" rel="noopener noreferrer" class="btn ghost btn-sm supplier-visit-btn">Visit store ↗</a>`
                : '<span class="muted">No URL</span>'}
            </td>
          </tr>`;
        }).join("")}
        </tbody>
      </table>
    </div>
    <div class="supplier-picker-footer">
      <button type="button" class="btn primary" id="btnSaveSupplier">Save selection</button>
      <span id="supplierSaveStatus" class="hint" role="status"></span>
    </div>`;
}

function bindSupplierPicker(leadId) {
  const table = document.querySelector(".supplier-picker-table");
  if (!table) return;

  const saveBtn = document.getElementById("btnSaveSupplier");
  const statusEl = document.getElementById("supplierSaveStatus");

  const updateRowHighlight = () => {
    const checked = table.querySelector('input[name="supplierPick"]:checked');
    table.querySelectorAll(".supplier-row").forEach((row) => {
      row.classList.toggle("selected", !!(checked && row.contains(checked)));
    });
  };

  table.querySelectorAll(".supplier-radio").forEach((radio) => {
    radio.addEventListener("change", updateRowHighlight);
  });

  table.querySelectorAll(".supplier-row").forEach((row) => {
    row.addEventListener("click", (e) => {
      if (e.target.closest("a, button, input")) return;
      const radio = row.querySelector(".supplier-radio");
      if (radio) {
        radio.checked = true;
        updateRowHighlight();
      }
    });
  });

  saveBtn?.addEventListener("click", async () => {
    const checked = table.querySelector('input[name="supplierPick"]:checked');
    if (!checked) {
      if (statusEl) statusEl.textContent = "Select a supplier first.";
      return;
    }
    if (saveBtn) {
      saveBtn.disabled = true;
      saveBtn.textContent = "Saving…";
    }
    if (statusEl) statusEl.textContent = "";
    try {
      const res = await fetch(`/api/hot-leads/${leadId}/supplier-selection`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ supplier_id: checked.value }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Could not save selection");
      if (data.brief) {
        activeBrief = data.brief;
        renderStepView(activeBrief);
      }
      if (statusEl) statusEl.textContent = "Selection saved.";
    } catch (e) {
      if (statusEl) statusEl.textContent = e.message;
    } finally {
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.textContent = "Save selection";
      }
    }
  });
}

function stepContextHtml(brief) {
  const next = brief.next_step || {};
  const stage = displayStepId(brief);
  const pending = brief.pending_review;
  const isViewingPast = viewingStepId && viewingStepId !== currentStepId(brief);
  const showReview = !isViewingPast && pending?.status === "pending";

  if (next.terminal && !viewingStepId) {
    return `<div class="step-context terminal"><p class="step-context-lead">Pipeline complete — manage this deal on Tracking.</p></div>`;
  }

  const stepDef = PIPELINE_STEPS.find((s) => s.id === stage) || {};
  const stepLabel = stepDef.label || next.label;

  let intro = "";
  if (isViewingPast) {
    intro = `<div class="viewing-banner">Viewing step: <strong>${esc(stepLabel)}</strong> — edit below or return to the current step.</div>`;
  } else if (showReview) {
    intro = `<p class="step-context-lead">Review and edit the content below, then approve to continue.</p>`;
  } else if (stage === "company_research") {
    intro = `<p class="step-context-lead">The AI agent will analyze this buyer's website and catalog.</p>`;
  } else if (stage === "supplier_discovery" || stage === "supplier_verification") {
    intro = `<p class="step-context-lead">Review matched factories below — open each store, pick your favorite, then save your selection.</p>`;
  } else {
    intro = `<p class="step-context-lead">${esc(next.description || "Run this step to generate content for review.")}</p>`;
  }

  const stepStatus = pipelineStepStatus(brief, stage);
  const hasContent = stepHasContent(brief, stage);
  const isCurrentUnrun = !isViewingPast && !showReview && stage === currentStepId(brief) && !hasContent;

  let content;
  if (showReview) {
    content = renderEditableDraft(pending, brief, stage);
  } else if (isCurrentUnrun) {
    content = renderStepPreview(stage, brief);
  } else if (hasContent || isViewingPast || stepStatus === "completed") {
    content = renderEditableDraft(null, brief, stage);
  } else {
    content = renderStepPreview(stage, brief);
  }

  return `<div class="step-context">${intro}${content}</div>`;
}

function collectDraftFields() {
  const form = document.getElementById("draftEditForm");
  if (!form) return {};
  const data = {};
  form.querySelectorAll("input, textarea, select").forEach((el) => {
    if (!el.name || el.readOnly || el.disabled) return;
    data[el.name] = el.value;
  });
  return data;
}

function renderStepView(brief) {
  const container = document.getElementById("hotLeadStepView");
  if (!container) return;

  const next = brief.next_step || {};
  const pending = brief.pending_review;
  const stage = displayStepId(brief);
  const curStage = currentStepId(brief);
  const idx = stepIndex(stage);
  const stepNum = idx + 1;
  const isViewingPast = viewingStepId && viewingStepId !== curStage;
  const isReview = !isViewingPast && (pending?.status === "pending" || next.review);
  const isTerminal = next.terminal && !viewingStepId;
  const stepDef = PIPELINE_STEPS.find((s) => s.id === stage);
  const stepTitle = isViewingPast ? (stepDef?.label || stage) : (next.label || "Next step");

  let cta = "";
  if (stepRunning) {
    cta = `<button class="btn primary" disabled><span class="spinner inline"></span> Running…</button>`;
  } else if (isViewingPast) {
    cta = `
      <button type="button" class="btn ghost" id="btnBackToCurrent">← Current step</button>
      <button type="button" class="btn ghost" id="btnSaveDraft">Save changes</button>`;
  } else if (isTerminal) {
    cta = `<a href="#tracking" class="btn primary">Open Tracking</a>`;
  } else if (isReview && pending?.status === "pending") {
    const label = pending.gate === "supplier_final_approval" ? "Approve & Continue" : "Approve & Send";
    cta = `
      <button type="button" class="btn ghost" id="btnSaveDraft">Save changes</button>
      <button type="button" class="btn primary" id="btnStepApprove">${label}</button>`;
  } else if (isReview) {
    cta = `<button type="button" class="btn primary" id="btnStepRun">Prepare for review</button>`;
  } else {
    cta = `<button type="button" class="btn primary" id="btnStepRun">Start this step</button>`;
  }

  if (!isViewingPast && idx > 0 && !stepRunning && !isTerminal) {
    const prev = PIPELINE_STEPS[idx - 1];
    if (pipelineStepStatus(brief, prev.id) === "completed") {
      cta = `<button type="button" class="btn ghost" id="btnPrevStep">← ${esc(prev.label)}</button>` + cta;
    }
  }

  container.innerHTML = `
    <div class="step-view-header">
      <button type="button" class="btn ghost btn-back-list" id="btnBackHotList">← Back to list</button>
      <div class="step-view-title">
        <h2>${esc(brief.company_name)}</h2>
        ${heatBadge(brief.heat, brief.hot_score)}
      </div>
    </div>
    ${renderProgressBar(brief)}
    <article class="step-card">
      <header class="step-card-head">
        <span class="step-number">Step ${stepNum} of ${PIPELINE_STEPS.length}${isViewingPast ? " · reviewing" : ""}</span>
        <h3>${esc(stepTitle)}</h3>
        <p class="step-agent">${esc(next.agent_label || next.agent || "")}</p>
      </header>
      <div class="step-activity ${stepRunning ? "running" : ""}" id="stepActivity">
        ${stepRunning ? `<div class="activity-live"><span class="spinner"></span><span id="activityMsg">Working…</span></div>` : ""}
      </div>
      ${stepRunning ? "" : stepContextHtml(brief)}
      <footer class="step-card-actions">${cta}</footer>
    </article>`;

  document.getElementById("hotLeadsList")?.classList.add("hidden");
  container.classList.remove("hidden");

  document.getElementById("btnBackHotList")?.addEventListener("click", closeHotLead);
  document.getElementById("btnStepRun")?.addEventListener("click", () => runCurrentStep(brief.lead_id));
  document.getElementById("btnStepApprove")?.addEventListener("click", () => approveCurrentStep(brief.lead_id));
  document.getElementById("btnSaveDraft")?.addEventListener("click", () => saveDraftEdits(brief.lead_id));
  document.getElementById("btnBackToCurrent")?.addEventListener("click", () => { viewingStepId = null; renderStepView(activeBrief); });
  document.getElementById("btnPrevStep")?.addEventListener("click", () => {
    const prev = PIPELINE_STEPS[stepIndex(curStage) - 1];
    if (prev) { viewingStepId = prev.id; renderStepView(activeBrief); }
  });

  container.querySelectorAll(".step-pill[data-step-id]").forEach((btn) => {
    btn.addEventListener("click", () => {
      viewingStepId = btn.dataset.stepId;
      renderStepView(activeBrief);
    });
  });

  bindSupplierPicker(brief.lead_id);
}

function renderHotLeadsList(list) {
  const container = document.getElementById("hotLeadsList");
  if (!container) return;
  document.getElementById("hotLeadStepView")?.classList.add("hidden");
  container.classList.remove("hidden");

  if (!list.length) {
    container.innerHTML = `<div class="empty-state"><h3>No hot leads yet</h3><p>Run the pipeline or click <strong>Re-analyze All</strong> to score leads.</p></div>`;
    return;
  }

  container.innerHTML = `<div class="table-wrap"><table class="data-table hot-leads-table">
    <thead><tr><th>Company</th><th>Score</th><th>Need</th><th>Stage</th><th>Next step</th><th></th></tr></thead>
    <tbody>${list.map((b) => {
      const next = b.next_step || {};
      const intent = b.intent || {};
      const deal = b.deal || {};
      const review = b.pending_review?.status === "pending";
      return `<tr class="clickable-row" data-lead-id="${esc(b.lead_id)}">
        <td><strong>${esc(b.company_name)}</strong>${review ? ' <span class="review-dot" title="Awaiting review">●</span>' : ""}</td>
        <td>${heatBadge(b.heat, b.hot_score)}</td>
        <td class="cell-truncate">${esc(intent.primary_need || "—")}</td>
        <td>${deal.stage ? `<span class="status-pill status-active">${esc(deal.stage)}</span>` : "<span class='muted'>—</span>"}</td>
        <td class="cell-truncate">${esc(next.label || "—")}</td>
        <td><button type="button" class="btn ghost btn-sm btn-open-lead" data-id="${esc(b.lead_id)}">Open →</button></td>
      </tr>`;
    }).join("")}</tbody>
  </table></div>`;

  container.querySelectorAll(".clickable-row").forEach((row) => {
    row.addEventListener("click", (e) => { if (!e.target.closest(".btn-open-lead")) openHotLead(row.dataset.leadId); });
  });
  container.querySelectorAll(".btn-open-lead").forEach((btn) => {
    btn.addEventListener("click", (e) => { e.stopPropagation(); openHotLead(btn.dataset.id); });
  });
}

function startActivityMessages(stage) {
  stopActivityMessages();
  const msgs = STEP_ACTIVITY[stage] || ["AI agent is working…"];
  let i = 0;
  const el = document.getElementById("activityMsg");
  if (el) el.textContent = msgs[0];
  activityTimer = setInterval(() => {
    i = (i + 1) % msgs.length;
    const node = document.getElementById("activityMsg");
    if (node) node.textContent = msgs[i];
  }, 2200);
}

function stopActivityMessages() {
  if (activityTimer) { clearInterval(activityTimer); activityTimer = null; }
}

async function fetchBrief(leadId) {
  const res = await fetch(`/api/hot-leads/${leadId}`);
  if (!res.ok) throw new Error("Lead not found");
  return res.json();
}

async function openHotLead(leadId) {
  activeLeadId = leadId;
  viewingStepId = null;
  stepRunning = false;
  stopActivityMessages();
  try {
    activeBrief = await fetchBrief(leadId);
    renderStepView(activeBrief);
  } catch (e) {
    activeLeadId = null;
    activeBrief = null;
    alert(e.message);
  }
}

function closeHotLead() {
  activeLeadId = null;
  activeBrief = null;
  viewingStepId = null;
  stepRunning = false;
  stopActivityMessages();
  document.getElementById("hotLeadStepView")?.classList.add("hidden");
  document.getElementById("hotLeadsList")?.classList.remove("hidden");
}

async function saveDraftEdits(leadId) {
  const fields = collectDraftFields();
  if (!Object.keys(fields).length) return;
  const btn = document.getElementById("btnSaveDraft");
  if (btn) { btn.disabled = true; btn.textContent = "Saving…"; }
  try {
    const res = await fetch(`/api/hot-leads/${leadId}/draft`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Save failed");
    activeBrief = data.brief || await fetchBrief(leadId);
    renderStepView(activeBrief);
  } catch (e) {
    alert(e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "Save changes"; }
  }
}

async function runCurrentStep(leadId) {
  if (stepRunning) return;
  stepRunning = true;
  viewingStepId = null;
  const stage = activeBrief?.next_step?.stage || "company_research";
  renderStepView(activeBrief);
  startActivityMessages(stage);
  try {
    const res = await fetch(`/api/hot-leads/${leadId}/advance?auto_approve=false`, { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Step failed");
    activeBrief = data.brief || await fetchBrief(leadId);
    stepRunning = false;
    stopActivityMessages();
    renderStepView(activeBrief);
    loadOverview?.();
  } catch (e) {
    stepRunning = false;
    stopActivityMessages();
    document.getElementById("stepActivity").innerHTML = `<div class="activity-error"><span class="error-msg">${esc(e.message)}</span></div>`;
  }
}

async function approveCurrentStep(leadId) {
  if (stepRunning) return;
  const fields = collectDraftFields();
  stepRunning = true;
  renderStepView(activeBrief);
  startActivityMessages(activeBrief?.next_step?.stage);
  try {
    const res = await fetch(`/api/hot-leads/${leadId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(fields),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Approve failed");
    activeBrief = data.brief || await fetchBrief(leadId);
    viewingStepId = null;
    stepRunning = false;
    stopActivityMessages();
    renderStepView(activeBrief);
    loadOverview?.();
  } catch (e) {
    stepRunning = false;
    stopActivityMessages();
    document.getElementById("stepActivity").innerHTML = `<div class="activity-error"><span class="error-msg">${esc(e.message)}</span></div>`;
  }
}

async function loadHotLeads() {
  const hotOnly = hotFilter === "hot";
  const minScore = hotFilter === "warm" ? 50 : 0;
  const res = await fetch(`/api/hot-leads?hot_only=${hotOnly}&min_score=${minScore}`);
  const data = await res.json();
  hotLeadsData = data.hot_leads || [];

  const badge = document.getElementById("badgeHotLeads");
  if (badge) badge.textContent = data.hot_count || 0;

  const summary = document.getElementById("hotLeadsSummary");
  if (summary) {
    summary.innerHTML = `
      <div class="kpi"><div class="val">${data.hot_count || 0}</div><div class="lbl">Hot Leads</div></div>
      <div class="kpi"><div class="val">${data.total || 0}</div><div class="lbl">Analyzed</div></div>
      <div class="kpi"><div class="val">${hotLeadsData.filter((b) => b.deal).length}</div><div class="lbl">With Deals</div></div>
      <div class="kpi"><div class="val">${hotLeadsData.filter((b) => b.pending_review).length}</div><div class="lbl">Awaiting Review</div></div>`;
  }

  let filtered = hotLeadsData;
  if (hotFilter === "hot") filtered = hotLeadsData.filter((b) => b.is_hot);
  else if (hotFilter === "warm") filtered = hotLeadsData.filter((b) => b.hot_score >= 50);

  if (activeLeadId) {
    if (!stepRunning) {
      try { activeBrief = await fetchBrief(activeLeadId); } catch { closeHotLead(); renderHotLeadsList(filtered); return; }
      renderStepView(activeBrief);
    }
    return;
  }
  renderHotLeadsList(filtered);
}

function onHotLeadPipelineEvent(ev) {
  if (!activeLeadId || !stepRunning) return;
  if (ev.data?.lead_id && ev.data.lead_id !== activeLeadId) return;
  if (ev.type === "lead_stage_started") {
    const msg = document.getElementById("activityMsg");
    if (msg) msg.textContent = `Running ${ev.data.stage || "step"}…`;
  }
  if (ev.type === "lead_stage_completed" && ev.data?.brief) activeBrief = ev.data.brief;
}

document.getElementById("btnAnalyzeHot")?.addEventListener("click", async () => {
  const btn = document.getElementById("btnAnalyzeHot");
  btn.disabled = true;
  btn.textContent = "Analyzing...";
  await fetch("/api/hot-leads/analyze", { method: "POST" });
  await loadHotLeads();
  btn.disabled = false;
  btn.textContent = "Re-analyze All";
});

document.querySelectorAll("[data-hot-filter]").forEach((btn) => {
  btn.onclick = () => {
    hotFilter = btn.dataset.hotFilter;
    document.querySelectorAll("[data-hot-filter]").forEach((b) => b.classList.toggle("active", b === btn));
    loadHotLeads();
  };
});
