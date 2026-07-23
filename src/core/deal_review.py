"""Assemble all deal artifacts for systematic review on Tracking page."""

from __future__ import annotations

from typing import Any

from src.core.contacts import alibaba_contact_url, extract_buyer_contacts, extract_contacts
from src.core.draft_composer import compose_proposal_client_email


PIPELINE_STEP_DEFS = [
    {"id": "company_research", "label": "Company research", "artifact": "company"},
    {"id": "personalization", "label": "Personalization", "artifact": "personalization"},
    {"id": "outreach", "label": "Outreach email", "artifact": "outreach"},
    {"id": "qualification", "label": "Deal opened", "artifact": "requirements"},
    {"id": "product_research", "label": "Product spec", "artifact": "product_spec"},
    {"id": "supplier_discovery", "label": "Supplier discovery", "artifact": "suppliers"},
    {"id": "supplier_verification", "label": "Supplier approval", "artifact": "supplier_approval"},
    {"id": "rfq", "label": "RFQ to suppliers", "artifact": "rfqs"},
    {"id": "quote_comparison", "label": "Quote comparison", "artifact": "quotes"},
    {"id": "proposal", "label": "Client proposal", "artifact": "proposal"},
]


def build_deal_review_package(
    storage: Any,
    deal: dict,
    lead: dict | None,
    *,
    tenant_id: str = "agency_primary",
) -> dict[str, Any]:
    deal_id = deal["id"]
    lead_id = deal.get("lead_id")
    lead_data = (lead or {}).get("data") or {}
    if isinstance(lead_data, str):
        import json
        try:
            lead_data = json.loads(lead_data)
        except json.JSONDecodeError:
            lead_data = {}

    company = storage.load_json_entity("companies", lead_id) if lead_id else {}
    personalization = storage.load_json_entity("personalization", lead_id) if lead_id else {}
    outreach = storage.load_json_entity("outreach", lead_id) if lead_id else {}
    product_spec = storage.load_json_entity("products", deal_id) or {}
    proposal = storage.load_json_entity("proposals", deal_id) or {}
    quotes_doc = storage.load_json_entity("quotes", deal_id) or {}
    quotes_list = quotes_doc.get("quotes") or []
    comparison = quotes_doc.get("comparison") or {}
    rfqs_raw = storage.get_rfqs_for_deal(deal_id)
    rfqs = [_enrich_rfq(r) for r in rfqs_raw]
    supplier_approval = storage.load_json_entity("supplier_approvals", deal_id) or {}
    requirements = deal.get("buyer_requirements") or {}
    if isinstance(requirements, str):
        import json
        try:
            requirements = json.loads(requirements)
        except json.JSONDecodeError:
            requirements = {}

    company_name = (lead or {}).get("company_name") or deal.get("lead_company", "Client")
    buyer_contacts = extract_buyer_contacts(lead_data)

    recommended_name = proposal.get("recommended_option") or comparison.get("recommended_supplier") or ""
    suppliers = _collect_suppliers(storage, tenant_id, quotes_list, rfqs_raw, supplier_approval, recommended_name)
    recommended_supplier = _pick_recommended(suppliers, recommended_name)

    proposal_email = proposal.get("client_email_draft") or compose_proposal_client_email(proposal, {
        "company_name": company_name,
        "email": buyer_contacts.get("primary_email", ""),
    })
    if proposal.get("sent_at"):
        proposal_email["sent_at"] = proposal.get("sent_at")
    if proposal.get("send_result"):
        proposal_email["send_result"] = proposal.get("send_result")
    proposal_email["status"] = proposal.get("status", proposal_email.get("status", "draft"))

    artifacts = {
        "company": company or {},
        "personalization": personalization or {},
        "outreach": outreach or {},
        "requirements": requirements,
        "product_spec": product_spec,
        "suppliers": suppliers,
        "recommended_supplier": recommended_supplier,
        "supplier_approval": supplier_approval,
        "rfqs": rfqs,
        "quotes": {"quotes": quotes_list, "comparison": comparison},
        "proposal": proposal,
        "proposal_email": proposal_email,
        "buyer_contacts": buyer_contacts,
    }

    steps = _build_steps(artifacts, deal)
    documents = _document_index(artifacts)

    return {
        "deal_id": deal_id,
        "lead_id": lead_id,
        "company_name": company_name,
        "steps": steps,
        "documents": documents,
        "artifacts": artifacts,
    }


def _enrich_rfq(rfq: dict) -> dict:
    data = rfq.get("data") or {}
    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}
    return {
        "id": rfq.get("id"),
        "status": rfq.get("status", "draft"),
        "created_at": rfq.get("created_at"),
        "rfq_body": data.get("rfq_body", ""),
        "subject": data.get("subject", ""),
        "suppliers": data.get("suppliers") or [],
        "sent_at": data.get("sent_at"),
        "send_result": data.get("send_result"),
    }


def _collect_suppliers(
    storage: Any,
    tenant_id: str,
    quotes: list,
    rfqs: list,
    approval: dict,
    recommended_name: str,
) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    def add(entry: dict) -> None:
        name = (entry.get("factory_name") or entry.get("factory") or "").strip()
        if not name or name.lower() in seen:
            return
        seen.add(name.lower())
        url = entry.get("url", "")
        data = {
            "factory_name": name,
            "url": url,
            "platform_source": entry.get("platform_source") or entry.get("platform", ""),
            "unit_price_estimate_usd": entry.get("unit_price_estimate_usd") or entry.get("price_usd"),
            "moq": entry.get("moq"),
            "trust_score": entry.get("trust_score") or entry.get("rating"),
            "recommendation": entry.get("recommendation", ""),
        }
        contacts = extract_contacts(data)
        out.append({
            **data,
            "contacts": contacts,
            "alibaba_profile": alibaba_contact_url(url),
            "is_recommended": bool(recommended_name and recommended_name.lower() in name.lower()),
        })

    for s in approval.get("suppliers") or []:
        add(s)
    for rfq in rfqs:
        data = rfq.get("data") or {}
        if isinstance(data, dict):
            for s in data.get("suppliers") or []:
                add(s)
    for q in quotes:
        add({
            "factory_name": q.get("factory"),
            "url": q.get("url"),
            "price_usd": q.get("price_usd"),
            "moq": q.get("moq"),
            "rating": q.get("rating"),
        })

    for row in storage.list_suppliers(tenant_id, limit=50):
        name = row.get("factory_name", "")
        if recommended_name and recommended_name.lower() in name.lower():
            d = row.get("data") or {}
            add({**d, "factory_name": name, "trust_score": row.get("trust_score")})

    out.sort(key=lambda s: (not s.get("is_recommended"), -(float(s.get("trust_score") or 0))))
    return out[:12]


def _pick_recommended(suppliers: list[dict], name: str) -> dict | None:
    if not suppliers:
        return None
    for s in suppliers:
        if s.get("is_recommended"):
            return s
    if name:
        for s in suppliers:
            if name.lower() in (s.get("factory_name") or "").lower():
                return s
    return suppliers[0]


def _build_steps(artifacts: dict, deal: dict) -> list[dict]:
    steps = []
    stage = deal.get("stage", "")
    for defn in PIPELINE_STEP_DEFS:
        art_key = defn["artifact"]
        art = artifacts.get(art_key)
        done = _artifact_ready(art_key, art, deal, artifacts)
        steps.append({
            "id": defn["id"],
            "label": defn["label"],
            "status": "completed" if done else "pending",
            "artifact": art_key,
            "viewable": done,
        })
    return steps


def _artifact_ready(key: str, data: Any, deal: dict, artifacts: dict) -> bool:
    stage = deal.get("stage", "")
    if key == "company":
        return bool(data and (data.get("company_summary") or data.get("products_services") or data.get("source")))
    if key == "personalization":
        return bool(data and (data.get("email_body") or data.get("subject_line")))
    if key == "outreach":
        return bool(data and (data.get("body") or data.get("status") == "sent"))
    if key == "requirements":
        return bool(data and data.get("product_description")) or bool(deal.get("id"))
    if key == "product_spec":
        return bool(data and (data.get("product_category") or data.get("materials")))
    if key == "suppliers":
        return bool(data)
    if key == "supplier_approval":
        return bool(data and data.get("approved")) or stage in (
            "rfq", "quote_comparison", "proposal", "proposal_sent", "order_tracking", "finance", "closed",
        )
    if key == "rfqs":
        return bool(data)
    if key == "quotes":
        return bool((data or {}).get("quotes"))
    if key == "proposal":
        return bool(data and (data.get("title") or data.get("executive_summary")))
    return bool(data)


def build_lead_pipeline_package(
    storage: Any,
    lead: dict,
    *,
    tenant_id: str = "agency_primary",
) -> dict[str, Any]:
    """Pipeline artifacts + step status for hot-leads wizard (pre- and post-deal)."""
    lead_id = lead["id"]
    deals = storage.get_deals_for_lead(lead_id)
    if deals:
        return build_deal_review_package(storage, deals[0], lead, tenant_id=tenant_id)

    lead_data = lead.get("data") or {}
    if isinstance(lead_data, str):
        import json
        try:
            lead_data = json.loads(lead_data)
        except json.JSONDecodeError:
            lead_data = {}

    company = storage.load_json_entity("companies", lead_id) or {}
    personalization = storage.load_json_entity("personalization", lead_id) or {}
    outreach = storage.load_json_entity("outreach", lead_id) or {}
    buyer_contacts = extract_buyer_contacts(lead_data)
    pseudo_deal = {"id": None, "stage": "new", "buyer_requirements": {}}

    artifacts = {
        "company": company,
        "personalization": personalization,
        "outreach": outreach,
        "requirements": {},
        "product_spec": {},
        "suppliers": [],
        "recommended_supplier": None,
        "supplier_approval": {},
        "rfqs": [],
        "quotes": {"quotes": [], "comparison": {}},
        "proposal": {},
        "proposal_email": {},
        "buyer_contacts": buyer_contacts,
    }
    steps = _build_steps(artifacts, pseudo_deal)
    return {
        "deal_id": None,
        "lead_id": lead_id,
        "company_name": lead.get("company_name", "Client"),
        "steps": steps,
        "documents": _document_index(artifacts),
        "artifacts": artifacts,
    }


def _document_index(artifacts: dict) -> list[dict]:
    docs = []
    specs = [
        ("company", "Company profile", "Research summary and products"),
        ("personalization", "Personalization", "Email angles for this buyer"),
        ("outreach", "Outreach email", "First contact email draft/sent"),
        ("requirements", "Buyer requirements", "Product, quantity, destination"),
        ("product_spec", "Product spec", "Materials, packaging, price range"),
        ("suppliers", "All suppliers", "Factories with contact buttons"),
        ("recommended_supplier", "Recommended supplier", "Chosen factory — contact here"),
        ("supplier_approval", "Supplier approval", "Shortlist you approved"),
        ("rfqs", "RFQ email", "Quote request to factories"),
        ("quotes", "Quote comparison", "Side-by-side pricing"),
        ("proposal", "Proposal document", "Full client offer"),
        ("proposal_email", "Client email", "Proposal email sent to buyer"),
        ("buyer_contacts", "Contact buyer", "Client email and phone"),
    ]
    for key, label, desc in specs:
        art = artifacts.get(key)
        ready = False
        count = ""
        if key == "quotes":
            ready = bool((art or {}).get("quotes"))
            count = str(len((art or {}).get("quotes") or []))
        elif key == "rfqs":
            ready = bool(art)
            count = str(len(art or []))
        elif key == "suppliers":
            ready = bool(art)
            count = str(len(art or []))
        elif key == "recommended_supplier":
            ready = bool(art)
        elif key == "supplier_approval":
            ready = bool(art and art.get("approved")) or bool(artifacts.get("suppliers"))
        elif key == "buyer_contacts":
            c = art or {}
            ready = bool(c.get("emails") or c.get("phones") or c.get("whatsapp") or c.get("website"))
        elif key == "proposal_email":
            ready = bool((art or {}).get("body"))
        elif key == "outreach":
            ready = bool(art and art.get("body"))
        else:
            ready = bool(art) and art != {}
        if ready:
            docs.append({"id": key, "label": label, "description": desc, "count": count})
    return docs
