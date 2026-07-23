"""Hot lead analysis — intent detection, supplier matching, next-step routing."""

from __future__ import annotations

import re
from typing import Any

from src.core.deal_lifecycle import TRACKING_STAGES, is_closed_deal, is_tracking_deal
from src.core.pipeline_stages import GATE_LABELS, PIPELINE_STAGES

BUYING_INTENT_PATTERNS = [
    r"looking for\s+[\w\s]{3,40}",
    r"seeking\s+(?:a\s+)?[\w\s]{3,40}",
    r"need(?:s|ed)?\s+(?:a\s+)?(?:supplier|manufacturer|vendor)",
    r"sourcing\s+[\w\s]{3,40}",
    r"RFP|RFQ|request for (?:quote|proposal)",
    r"wholesale\s+[\w\s]{3,30}",
    r"custom\s+[\w\s]{3,30}",
    r"OEM\s+[\w\s]{3,30}",
    r"distributor(?:s)?\s+(?:wanted|needed|program)",
]

PRODUCT_KEYWORDS = (
    "tumbler", "drinkware", "lip balm", "bag", "apparel", "pen", "mug", "bottle",
    "hat", "shirt", "towel", "promotional", "merchandise", "swag", "gift", "cup",
    "cooler", "keychain", "notebook", "umbrella", "flashlight", "power bank",
)

DEAL_STAGE_ORDER = [
    "qualification",
    "product_research",
    "supplier_discovery",
    "supplier_verification",
    "rfq",
    "quote_comparison",
    "proposal",
    "order_tracking",
    "finance",
    "proposal_sent",
    "closed",
]

STAGE_TO_AGENT = {s["id"]: s for s in PIPELINE_STAGES}


def extract_buying_intent(data: dict, company: dict | None = None) -> dict[str, Any]:
    """Detect what a buyer is looking for from website text, snippets, and profiles."""
    company = company or {}
    text = " ".join(str(v) for v in [
        data.get("website_text_preview", ""),
        data.get("search_snippet", ""),
        data.get("meta_description", ""),
        data.get("website_title", ""),
        company.get("company_summary", ""),
    ]).lower()

    signals: list[str] = []
    for pat in BUYING_INTENT_PATTERNS:
        for m in re.finditer(pat, text, re.I):
            phrase = m.group(0).strip()
            if phrase and phrase not in signals:
                signals.append(phrase[:80])

    products = list(company.get("products_services") or [])
    for kw in PRODUCT_KEYWORDS:
        if kw in text and kw not in products:
            products.append(kw)

    primary = products[0] if products else _guess_product(text)
    return {
        "primary_need": primary,
        "products": products[:8],
        "buying_signals": signals[:5],
        "intent_strength": min(100, len(signals) * 15 + len(products) * 10),
        "summary": _intent_summary(primary, signals, company),
    }


def _guess_product(text: str) -> str:
    for kw in PRODUCT_KEYWORDS:
        if kw in text:
            return kw
    return "promotional products"


def _intent_summary(primary: str, signals: list[str], company: dict) -> str:
    parts = [f"Likely sourcing: {primary}"]
    if company.get("company_summary"):
        parts.append(company["company_summary"][:200])
    if signals:
        parts.append(f"Signals: {signals[0]}")
    return " · ".join(parts)


def match_suppliers(
    intent: dict[str, Any],
    suppliers: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank suppliers against lead intent using keyword overlap."""
    keywords = set()
    for p in intent.get("products") or []:
        keywords.update(w.lower() for w in re.findall(r"\w+", p) if len(w) > 2)
    primary = (intent.get("primary_need") or "").lower()
    if primary:
        keywords.update(w for w in re.findall(r"\w+", primary) if len(w) > 2)

    scored: list[tuple[float, dict]] = []
    for sup in suppliers:
        d = sup.get("data") or {}
        blob = " ".join(str(v) for v in [
            sup.get("factory_name", ""),
            d.get("search_snippet", ""),
            d.get("url", ""),
            d.get("platform_source", ""),
        ]).lower()

        overlap = sum(1 for k in keywords if k in blob)
        primary_hit = 1.5 if primary and primary in blob else 0
        price_bonus = 0.5 if d.get("unit_price_estimate_usd") else 0
        trust = (sup.get("trust_score") or d.get("trust_score") or 0) / 100
        score = overlap * 12 + primary_hit * 20 + price_bonus * 5 + trust * 15

        if score > 0 or overlap > 0:
            scored.append((score, {
                "supplier_id": sup.get("id"),
                "factory_name": sup.get("factory_name"),
                "platform": d.get("platform_source", ""),
                "url": d.get("url", ""),
                "price_usd": d.get("unit_price_estimate_usd"),
                "moq": d.get("moq"),
                "trust_score": sup.get("trust_score") or d.get("trust_score", 0),
                "match_score": round(min(99, score * 3), 1),
                "match_reason": _match_reason(overlap, primary_hit, primary),
                "recommendation": "best_fit" if score >= 25 else "alternative",
            }))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [s[1] for s in scored[:limit]]
    if not results and suppliers:
        for sup in suppliers[:3]:
            d = sup.get("data") or {}
            results.append({
                "supplier_id": sup.get("id"),
                "factory_name": sup.get("factory_name"),
                "platform": d.get("platform_source", ""),
                "url": d.get("url", ""),
                "price_usd": d.get("unit_price_estimate_usd"),
                "moq": d.get("moq"),
                "trust_score": sup.get("trust_score", 0),
                "match_score": 40.0,
                "match_reason": "General catalog match — run supplier discovery for better fit",
                "recommendation": "explore",
            })
    return results


def _match_reason(overlap: int, primary_hit: float, primary: str) -> str:
    if primary_hit and primary:
        return f"Direct match for '{primary}'"
    if overlap >= 3:
        return "Strong keyword overlap with product needs"
    if overlap >= 1:
        return "Partial product category match"
    return "Available supplier in catalog"


def compute_hot_score(
    lead: dict,
    intent: dict,
    deals: list,
    supplier_matches: list,
    data: dict,
) -> float:
    score = float(lead.get("lead_score") or 0) * 0.35
    if data.get("email"):
        score += 12
    if data.get("phone"):
        score += 5
    if intent.get("products"):
        score += 15
    if intent.get("buying_signals"):
        score += min(15, len(intent["buying_signals"]) * 5)
    if intent.get("intent_strength", 0) > 30:
        score += 10
    if deals:
        score += 10
    if supplier_matches:
        score += min(15, supplier_matches[0].get("match_score", 0) * 0.15)
    return round(min(100, score), 1)


DEAL_STAGE_ORDER = [
    "qualification",
    "product_research",
    "supplier_discovery",
    "supplier_verification",
    "rfq",
    "quote_comparison",
    "proposal",
    "proposal_sent",
    "order_tracking",
    "finance",
    "closed",
]


def _proposal_ready(proposal: dict | None, stage: str) -> bool:
    """Proposal counts as done if stage advanced past it or file has content (price may be 0)."""
    if stage in ("proposal_sent", "order_tracking", "finance", "closed", "awaiting_approval"):
        return True
    if not proposal:
        return False
    return bool(
        proposal.get("title")
        or proposal.get("executive_summary")
        or proposal.get("recommended_option")
    )


def determine_next_step(
    lead: dict,
    company: dict | None,
    deals: list,
    quotes: dict | None = None,
    proposal: dict | None = None,
    rfqs: list | None = None,
    *,
    pending_review: dict | None = None,
    outreach: dict | None = None,
    personalization: dict | None = None,
) -> dict[str, Any]:
    """Return the next pipeline action for a lead."""
    data = lead.get("data") or {}
    has_profile = bool(
        company
        and (
            company.get("company_summary")
            or company.get("products_services")
            or company.get("source")
        )
    )
    active_deal = deals[0] if deals else None
    deal_id = active_deal["id"] if active_deal else None

    if pending_review and pending_review.get("status") == "pending":
        gate = pending_review.get("gate", "")
        return _action(
            pending_review.get("stage", "review"),
            f"Review: {pending_review.get('gate_label', GATE_LABELS.get(gate, 'Approval'))}",
            "Review the draft below, then approve and send to continue",
            deal_id=deal_id,
            review=True,
            gate=gate,
        )

    if not has_profile:
        return _action("company_research", "Research Company", "AI agent will analyze their website and catalog")

    outreach = outreach or {}
    personalization = personalization or {}

    if not active_deal:
        if outreach.get("status") == "sent":
            return _action("qualification", "Qualify & Open Deal", "Create sourcing deal with buyer requirements")
        if outreach and outreach.get("status") == "draft":
            return _action("outreach", "Review Outreach Email", "Approve and send your outreach email", review=True, gate="outreach_first_batch")
        if personalization and not outreach:
            return _action("outreach", "Draft Outreach Email", "Generate email to introduce your agency")
        if has_profile and not personalization:
            return _action("personalization", "Personalize Outreach", "AI drafts email and LinkedIn message for this buyer")
        return _action("qualification", "Qualify & Open Deal", "Create sourcing deal with buyer requirements")

    stage = active_deal.get("stage", "qualification")
    req = active_deal.get("buyer_requirements") or {}
    rfqs = rfqs or []

    if stage in ("qualification", "new"):
        return _action("product_research", "Research Product Spec", "Define materials, certifications, and price range", deal_id=deal_id)

    if stage == "product_research":
        product = req.get("product_description") or "promotional products"
        return _action("supplier_discovery", "Find Suppliers", f"Search manufacturers for: {product}", deal_id=deal_id)

    if stage == "supplier_discovery":
        return _action("supplier_verification", "Verify Suppliers", "Score and vet factory options", deal_id=deal_id)

    if stage == "supplier_verification":
        approval = None  # loaded via caller if needed — check pending first above
        return _action("supplier_verification", "Verify Suppliers", "Score factories, then review shortlist before RFQ", deal_id=deal_id)

    if stage == "rfq":
        if not rfqs:
            return _action("rfq", "Generate RFQ", "Create formal quote request to top suppliers", deal_id=deal_id)
        latest = rfqs[0]
        if latest.get("status") == "draft":
            return _action("rfq", "Review RFQ Email", "Approve and send RFQ to suppliers", deal_id=deal_id, review=True, gate="rfq_send")
        if not (quotes and quotes.get("quotes")):
            return _action("quote_comparison", "Compare Quotes", "Rank suppliers by price, MOQ, and lead time", deal_id=deal_id)

    if stage == "quote_comparison":
        if not (quotes and quotes.get("quotes")):
            return _action("quote_comparison", "Compare Quotes", "Rank suppliers by price, MOQ, and lead time", deal_id=deal_id)

    if is_tracking_deal(active_deal) or stage in TRACKING_STAGES:
        return _action(
            "tracking",
            "On Tracking Page",
            "Review proposal, contact client, and manage deal from the Tracking page",
            deal_id=deal_id,
            terminal=True,
        )

    if is_closed_deal(active_deal):
        return _action("closed", "Deal Closed", "This deal is archived on the Closed Deals page", deal_id=deal_id, terminal=True)

    if not _proposal_ready(proposal, stage):
        return _action("proposal", "Build Proposal", "Generate client-facing offer for your review", deal_id=deal_id)

    if stage == "proposal":
        prop_status = (proposal or {}).get("status")
        if prop_status != "sent":
            return _action("proposal", "Review Proposal Email", "Approve and send proposal to client", deal_id=deal_id, review=True, gate="proposal_send")
        return _action("proposal", "Send to Tracking", "Proposal sent — opens on Tracking page", deal_id=deal_id)

    return _action("supplier_discovery", "Continue Sourcing", "Advance sourcing pipeline", deal_id=deal_id)


def _action(stage: str, label: str, description: str, *, deal_id: str | None = None, terminal: bool = False, review: bool = False, gate: str | None = None) -> dict:
    agent = STAGE_TO_AGENT.get(stage, {})
    return {
        "stage": stage,
        "agent": agent.get("agent", stage),
        "agent_label": agent.get("label", label),
        "label": label,
        "description": description,
        "deal_id": deal_id,
        "has_gate": bool(agent.get("gate") or gate),
        "gate": gate or agent.get("gate"),
        "terminal": terminal,
        "review": review,
    }


def build_hot_lead_brief(
    lead: dict,
    company: dict | None,
    deals: list,
    all_suppliers: list,
    *,
    quotes: dict | None = None,
    proposal: dict | None = None,
    rfqs: list | None = None,
    pending_review: dict | None = None,
    outreach: dict | None = None,
    personalization: dict | None = None,
    supplier_selection: dict | None = None,
) -> dict[str, Any]:
    data = lead.get("data") or {}
    intent = extract_buying_intent(data, company)
    if deals:
        req = deals[0].get("buyer_requirements") or {}
        if req.get("product_description"):
            intent["primary_need"] = req["product_description"]
            if req["product_description"] not in intent["products"]:
                intent["products"].insert(0, req["product_description"])

    matches = match_suppliers(intent, all_suppliers)
    selected_supplier = None
    selected_supplier_id = None
    if supplier_selection:
        selected_supplier_id = supplier_selection.get("supplier_id")
        for i, m in enumerate(matches):
            mid = m.get("supplier_id") or m.get("url") or f"idx-{i}"
            if mid == selected_supplier_id:
                selected_supplier = m
                break
        if not selected_supplier and supplier_selection.get("factory_name"):
            selected_supplier = {
                "supplier_id": selected_supplier_id,
                "factory_name": supplier_selection.get("factory_name"),
                "url": supplier_selection.get("url", ""),
                "platform": supplier_selection.get("platform", ""),
                "match_score": supplier_selection.get("match_score"),
                "trust_score": supplier_selection.get("trust_score"),
            }
    hot_score = compute_hot_score(lead, intent, deals, matches, data)
    active_deal = deals[0] if deals else None
    on_tracking = is_tracking_deal(active_deal) or is_closed_deal(active_deal)
    next_step = determine_next_step(
        lead, company, deals, quotes, proposal, rfqs,
        pending_review=pending_review,
        outreach=outreach,
        personalization=personalization,
    )

    return {
        "lead_id": lead["id"],
        "company_name": lead["company_name"],
        "hot_score": hot_score,
        "is_hot": hot_score >= 55 and not on_tracking,
        "on_tracking": on_tracking,
        "heat": _heat_label(hot_score),
        "intent": intent,
        "supplier_matches": matches,
        "selected_supplier_id": selected_supplier_id,
        "selected_supplier": selected_supplier,
        "recommended_supplier": selected_supplier or (matches[0] if matches else None),
        "deal": deals[0] if deals else None,
        "deal_count": len(deals),
        "next_step": next_step,
        "pending_review": pending_review,
        "outreach_draft": outreach,
        "personalization_draft": personalization,
        "product_images": (company or {}).get("product_images") or [],
        "contact": {
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "website": data.get("website", ""),
        },
        "analyzed_at": None,
    }


def _heat_label(score: float) -> str:
    if score >= 80:
        return "on_fire"
    if score >= 65:
        return "hot"
    if score >= 50:
        return "warm"
    return "cool"
