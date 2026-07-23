"""Rule-based agent fallbacks — used when fast_mode is on or LLM fails."""

from __future__ import annotations

import json
import re
from typing import Any

PRODUCT_KEYWORDS = (
    "tumbler", "drinkware", "lip balm", "bag", "apparel", "pen", "mug", "bottle",
    "hat", "shirt", "towel", "promotional", "merchandise", "swag", "gift", "cup",
)


def run_fallback(agent_id: str, user_input: str) -> dict[str, Any]:
    data = _parse_input(user_input)
    handler = _HANDLERS.get(agent_id)
    if not handler:
        return {"status": "ok", "agent": agent_id, "note": "No fallback handler; passthrough"}
    return handler(data)


def _parse_input(user_input: str) -> dict[str, Any]:
    try:
        return json.loads(user_input)
    except (json.JSONDecodeError, TypeError):
        return {"raw_text": user_input}


def _products_from_text(text: str) -> list[str]:
    lower = (text or "").lower()
    found = [k for k in PRODUCT_KEYWORDS if k in lower]
    return found[:5] or ["promotional products"]


def _fallback_lead_discovery(data: dict) -> dict:
    return {
        "leads": [{
            "company_name": data.get("company_name", "Sample Distributor Co"),
            "email": data.get("email", ""),
            "lead_score": 72,
            "industry": "promotional products",
            "notes": "Rule-based discovery — run pipeline for live web search",
        }],
        "source": "rule_based_fallback",
    }


def _fallback_company_research(data: dict) -> dict:
    text = data.get("website_text", "") or data.get("website_text_preview", "")
    return {
        "company_summary": data.get("meta_description") or data.get("search_snippet", "") or "Promotional products distributor",
        "products_services": _products_from_text(text),
        "target_customers": ["businesses", "events", "corporate clients"],
        "personalization_hooks": [data.get("website_title", ""), data.get("meta_description", "")],
        "source": "rule_based_fallback",
    }


def _fallback_personalization(data: dict) -> dict:
    from src.core.draft_composer import compose_personalization

    profile = data.get("company_profile", data)
    lead = {
        "company_name": data.get("company_name") or profile.get("company_name", "your company"),
        "email": data.get("email", ""),
        "product_images": data.get("product_images") or profile.get("product_images") or [],
    }
    result = compose_personalization(lead, profile)
    result["source"] = "rule_based_fallback"
    return result


def _fallback_outreach(data: dict) -> dict:
    draft = data.get("outreach_draft") or data.get("personalization") or data
    return {
        "channel": "email",
        "message_to_send": draft.get("email_body", draft.get("message_to_send", "")),
        "subject": draft.get("subject_line", "Partnership opportunity"),
        "follow_up_schedule": [{"day": 3, "message": "Following up on manufacturer sourcing."}],
        "status": "draft",
        "source": "rule_based_fallback",
    }


def _fallback_qualification(data: dict) -> dict:
    text = data.get("raw_text", "") if isinstance(data.get("raw_text"), str) else json.dumps(data)
    products = _products_from_text(text)
    return {
        "product_description": products[0] if products else "custom promotional products",
        "quantity": 5000,
        "material": "custom",
        "color": "custom",
        "logo_spec": "custom branded",
        "packaging": "individual retail boxes",
        "delivery_date": "8 weeks",
        "shipping_destination": "United States",
        "completeness_score": 85,
        "ready_for_sourcing": True,
        "source": "rule_based_fallback",
    }


def _fallback_product_research(data: dict) -> dict:
    desc = data.get("product_description") or "insulated drinkware"
    return {
        "product_category": desc.title(),
        "materials": [data.get("material", "stainless steel")],
        "typical_pricing_range": {"min_usd": 0.5, "max_usd": 5.0, "unit": "per piece"},
        "certifications_required": ["FDA", "LFGB"],
        "manufacturing_regions": ["China", "India"],
        "standard_packaging": data.get("packaging", "individual retail boxes"),
        "search_keywords": [desc, "custom OEM manufacturer"],
        "source": "rule_based_fallback",
    }


def _fallback_supplier_discovery(data: dict) -> dict:
    live = data.get("live_search_results") or data.get("suppliers") or []
    if live:
        return {"suppliers": live, "source": "live_search_data"}
    spec = data.get("product_spec", data)
    category = spec.get("product_category", "promotional products")
    return {
        "suppliers": [{
            "factory_name": f"OEM {category} Manufacturer",
            "platform_source": "alibaba.com",
            "url": "https://www.alibaba.com",
            "moq": 500,
            "unit_price_estimate_usd": 1.5,
            "certifications": ["ISO9001"],
            "years_in_business": 10,
            "export_countries": ["USA", "EU"],
            "notes": "Placeholder — run pipeline supplier discovery for live results",
        }],
        "source": "rule_based_fallback",
    }


def _fallback_supplier_verification(data: dict) -> dict:
    suppliers = data.get("suppliers") or data.get("verified_suppliers") or []
    verified = []
    for s in suppliers:
        score = 70.0
        if s.get("platform_source") in ("alibaba.com", "made-in-china.com"):
            score += 10
        if s.get("unit_price_estimate_usd", 0) > 0:
            score += 5
        verified.append({
            **s,
            "trust_score": min(score, 95),
            "risk_flags": [] if s.get("url") else ["no_url"],
            "verification_notes": "Rule-based verification from platform data",
            "recommendation": "proceed" if score >= 60 else "caution",
        })
    return {"verified_suppliers": verified, "source": "rule_based_fallback"}


def _fallback_rfq(data: dict) -> dict:
    from src.core.draft_composer import compose_rfq_email

    req = data.get("requirements") or data.get("buyer_requirements") or data
    suppliers = data.get("verified_suppliers") or data.get("suppliers") or []
    spec = data.get("product_spec") or {}
    return {
        **compose_rfq_email(req, suppliers, spec),
        "source": "rule_based_fallback",
    }


def _fallback_quote_comparison(data: dict) -> dict:
    quotes = data.get("quotes") or []
    if not quotes and data.get("verified_suppliers"):
        quotes = [
            {
                "factory": s.get("factory_name"),
                "price_usd": s.get("unit_price_estimate_usd", 0),
                "price_known": bool(s.get("unit_price_estimate_usd")),
                "moq": s.get("moq", 0),
                "url": s.get("url"),
            }
            for s in data["verified_suppliers"]
        ]
    priced = [q for q in quotes if q.get("price_known") or q.get("price_usd")]
    best = min(priced or quotes or [{"factory": "TBD"}], key=lambda q: q.get("price_usd") or 9999)
    return {
        "comparison_table": quotes,
        "recommended_supplier": best.get("factory"),
        "best_price": best.get("factory"),
        "reasoning": "Recommended based on lowest verified unit price",
        "source": "rule_based_fallback",
    }


def _fallback_proposal(data: dict) -> dict:
    rec = data.get("recommendation", {})
    req = data.get("requirements") or data.get("requirements_recap") or {}
    quotes = data.get("quotes") or rec.get("comparison_table") or []
    company = data.get("company_name", "Client")
    best = rec.get("recommended_supplier") or (quotes[0].get("factory") if quotes else "TBD")
    qty = req.get("quantity", 5000)
    best_q = next((q for q in quotes if q.get("factory") == best), quotes[0] if quotes else {})
    cost = (best_q.get("price_usd") or 1.5) * qty
    margin_pct = 15
    margin_usd = round(cost * margin_pct / 100, 2)
    client_price = round(cost + margin_usd, 2)
    product = req.get("product_description", "your product line")
    return {
        "title": f"Proposal for {company}",
        "executive_summary": (
            f"We've sourced a competitive factory option for your {product} program and prepared a transparent "
            f"all-in landed quote — production, QC, and logistics included."
        ),
        "recommended_option": best,
        "client_price_usd": client_price,
        "factory_cost_usd": round(cost, 2),
        "margin_usd": margin_usd,
        "margin_percent": margin_pct,
        "supplier_comparison": quotes,
        "requirements_recap": req,
        "timeline": "8-10 weeks",
        "next_steps": ["Approve proposal", "Issue PO", "Pay deposit"],
        "source": "rule_based_fallback",
    }


def _fallback_order_tracking(data: dict) -> dict:
    return {
        "order_id": data.get("order_id", ""),
        "status": data.get("status", "proposal_sent_awaiting_approval"),
        "production_percent": 0,
        "milestones": [
            {"name": "Proposal sent", "status": "complete"},
            {"name": "Client approval", "status": "pending"},
            {"name": "Production", "status": "pending"},
        ],
        "source": "rule_based_fallback",
    }


def _fallback_finance(data: dict) -> dict:
    price = data.get("client_price_usd", 0)
    return {
        "order_id": data.get("order_id", ""),
        "deposit_status": "pending",
        "client_price_usd": price,
        "deposit_amount_usd": round(price * 0.3, 2) if price else 0,
        "requires_human_approval": price > 5000,
        "source": "rule_based_fallback",
    }


def _fallback_email_drafter(data: dict) -> dict:
    lead = data.get("lead") or {"company_name": data.get("company_name", "Client"), "email": data.get("email", "")}
    profile = data.get("company_profile") or {}
    req = data.get("requirements") or data.get("buyer_requirements") or {}
    rec = data.get("recommendation") or {}
    quotes = data.get("quotes") or []
    suppliers = data.get("verified_suppliers") or data.get("suppliers") or []
    spec = data.get("product_spec") or {}
    from src.core.draft_composer import (
        compose_outreach_email,
        compose_personalization,
        compose_proposal_client_email,
        compose_proposal_document,
        compose_rfq_email,
    )
    pers = compose_personalization(lead, profile)
    outreach = compose_outreach_email(lead, pers)
    rfq = compose_rfq_email(req, suppliers, spec)
    price = data.get("client_price_usd") or 0
    proposal = compose_proposal_document(lead, req, rec, quotes, client_price_usd=price, product_spec=spec)
    client_email = compose_proposal_client_email(proposal, lead)
    return {
        "personalization": pers,
        "outreach_email": outreach,
        "rfq_email": rfq,
        "proposal_document": proposal,
        "proposal_client_email": client_email,
        "source": "draft_composer",
    }


def _fallback_customer_support(data: dict) -> dict:
    return {
        "response": "Thank you for your inquiry. Our sourcing team will respond within 24 hours.",
        "ticket_status": "open",
        "priority": "normal",
        "source": "rule_based_fallback",
    }


def _fallback_niche_finder(data: dict) -> dict:
    return {
        "niche_name": data.get("niche_name", "Custom drinkware & tumblers"),
        "niche_score": data.get("niche_score", 75),
        "product_keywords": data.get("product_keywords", ["tumbler", "drinkware", "bottle"]),
        "buyer_search_queries": data.get("buyer_search_queries", data.get("buyer_types", [])),
        "rationale": data.get("rationale", "Rule-based niche selection from trend signals"),
        "source": "rule_based_fallback",
    }


_HANDLERS: dict[str, Any] = {
    "niche_finder": _fallback_niche_finder,
    "lead_discovery": _fallback_lead_discovery,
    "company_research": _fallback_company_research,
    "personalization": _fallback_personalization,
    "outreach": _fallback_outreach,
    "qualification": _fallback_qualification,
    "product_research": _fallback_product_research,
    "supplier_discovery": _fallback_supplier_discovery,
    "supplier_verification": _fallback_supplier_verification,
    "rfq": _fallback_rfq,
    "quote_comparison": _fallback_quote_comparison,
    "proposal": _fallback_proposal,
    "order_tracking": _fallback_order_tracking,
    "finance": _fallback_finance,
    "customer_support": _fallback_customer_support,
    "email_drafter": _fallback_email_drafter,
}
