"""Deal tracking — timeline, suggested actions, revenue for post-proposal deals."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.contacts import extract_buyer_contacts
from src.core.deal_lifecycle import TRACKING_STAGES, is_tracking_deal
from src.core.deal_review import build_deal_review_package


def build_tracking_record(
    deal: dict,
    lead: dict | None,
    *,
    proposal: dict | None = None,
    quotes: dict | None = None,
    order: dict | None = None,
    company: dict | None = None,
    storage: Any | None = None,
    tenant_id: str = "agency_primary",
) -> dict[str, Any]:
    lead_data = (lead or {}).get("data") or {}
    req = deal.get("buyer_requirements") or {}
    if isinstance(req, str):
        import json
        try:
            req = json.loads(req)
        except json.JSONDecodeError:
            req = {}

    proposal = proposal or {}
    quotes_list = (quotes or {}).get("quotes") or []
    client_price = float(proposal.get("client_price_usd") or 0)
    order_data = (order or {}).get("data") or {} if order else {}
    req_recap = proposal.get("requirements_recap") or {}

    product = (
        req.get("product_description")
        or req.get("product")
        or req_recap.get("product_description")
        or order_data.get("product")
        or lead_data.get("product_interest")
        or ""
    )
    quantity = req.get("quantity") or req_recap.get("quantity") or order_data.get("quantity")

    timeline = _build_timeline(deal, proposal, quotes_list, order)
    actions = _suggested_actions(deal, lead_data, proposal)
    revenue = _revenue_snapshot(deal, proposal, order_data)

    review = {}
    if storage:
        try:
            review = build_deal_review_package(storage, deal, lead, tenant_id=tenant_id)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(
                "deal review package failed for %s: %s", deal.get("id"), exc
            )
            review = _minimal_review_fallback(deal, lead, proposal, quotes_list, lead_data)

    prop_status = proposal.get("status", "draft")
    proposal_label = "Proposal sent to client" if prop_status == "sent" else "Proposal ready for review"
    buyer_contact = extract_buyer_contacts(lead_data)

    return {
        "deal_id": deal["id"],
        "lead_id": deal.get("lead_id"),
        "company_name": (lead or {}).get("company_name") or deal.get("lead_company", "—"),
        "stage": deal.get("stage"),
        "status": deal.get("status"),
        "proposal_status": prop_status,
        "proposal_sent_at": proposal.get("sent_at"),
        "contact": {
            "email": buyer_contact.get("primary_email", ""),
            "phone": buyer_contact.get("primary_phone", ""),
            "website": buyer_contact.get("website", ""),
            "note": buyer_contact.get("contact_note", ""),
        },
        "offer": {
            "title": proposal.get("title", ""),
            "summary": proposal.get("executive_summary", ""),
            "product": product,
            "quantity": quantity,
            "recommended_supplier": proposal.get("recommended_option", ""),
            "client_price_usd": client_price,
            "factory_cost_usd": float(proposal.get("factory_cost_usd") or 0),
            "margin_usd": float(proposal.get("margin_usd") or 0),
            "margin_percent": proposal.get("margin_percent"),
            "supplier_comparison": proposal.get("supplier_comparison") or quotes_list,
            "deposit_due_usd": order_data.get("deposit_due_usd"),
            "delivery_date": req.get("delivery_date") or req_recap.get("delivery_date") or proposal.get("timeline"),
        },
        "timeline": timeline,
        "suggested_actions": actions,
        "revenue": revenue,
        "review": review,
        "proposal_label": proposal_label,
        "product_images": (company or {}).get("product_images")
        or (review.get("artifacts") or {}).get("company", {}).get("product_images")
        or [],
        "entered_tracking_at": deal.get("tracking_entered_at") or deal.get("updated_at"),
        "updated_at": deal.get("updated_at"),
    }


def _build_timeline(deal: dict, proposal: dict, quotes: list, order: dict | None) -> list[dict]:
    req = deal.get("buyer_requirements") or {}
    if isinstance(req, str):
        import json
        try:
            req = json.loads(req)
        except json.JSONDecodeError:
            req = {}
    order_data = (order or {}).get("data") or {} if order else {}
    is_store = req.get("source") == "product_finder_store" or order_data.get("source") == "product_finder_store"

    events = [
        {"when": deal.get("created_at"), "event": "Deal opened", "detail": "Sourcing pipeline started"},
    ]
    if is_store:
        product = req.get("product_description") or req.get("product") or order_data.get("product", "")
        qty = req.get("quantity") or order_data.get("quantity", "")
        qty_label = f"{qty:,}" if isinstance(qty, int) else str(qty)
        events = [
            {"when": deal.get("created_at"), "event": "Order received", "detail": f"{product} — {qty_label} units"},
            {"when": deal.get("created_at"), "event": "Quote accepted", "detail": "Customer confirmed via AI Product Finder store"},
        ]
    if quotes:
        events.append({
            "when": deal.get("updated_at"),
            "event": "Quotes compared",
            "detail": f"{len(quotes)} supplier options evaluated",
            "artifact": "quotes",
        })
    if proposal.get("title") and not is_store:
        sent = proposal.get("status") == "sent"
        events.append({
            "when": proposal.get("sent_at") or deal.get("updated_at"),
            "event": "Proposal sent to client" if sent else "Proposal generated",
            "detail": proposal.get("executive_summary", "")[:120],
            "artifact": "proposal",
        })
    elif proposal.get("title") and is_store and proposal.get("status") != "accepted":
        events.append({
            "when": proposal.get("sent_at") or deal.get("updated_at"),
            "event": "Proposal generated",
            "detail": proposal.get("executive_summary", "")[:120],
            "artifact": "proposal",
        })
    stage = deal.get("stage", "")
    if stage in TRACKING_STAGES or stage == "proposal_sent":
        if proposal.get("status") not in ("sent", "accepted") and not is_store:
            events.append({
                "when": deal.get("tracking_entered_at") or deal.get("updated_at"),
                "event": "Awaiting your review",
                "detail": "Open Review Documents below before contacting client",
                "artifact": "proposal_email",
            })
    if order:
        od = order_data or {}
        deposit = od.get("deposit_due_usd")
        status = od.get("status", "pending")
        detail = f"Status: {status}"
        if deposit:
            detail += f" · 30% deposit due: ${deposit:,.2f}"
        events.append({
            "when": order.get("updated_at") or order.get("created_at"),
            "event": "Order confirmed",
            "detail": detail,
        })
        if deal.get("stage") == "order_tracking":
            events.append({
                "when": deal.get("updated_at"),
                "event": "In production",
                "detail": "Factory sourcing and production underway",
            })
    if stage == "finance":
        events.append({"when": deal.get("updated_at"), "event": "Finance", "detail": "Invoice / deposit tracking"})
    return events


def _suggested_actions(deal: dict, lead_data: dict, proposal: dict) -> list[dict]:
    stage = deal.get("stage", "proposal_sent")
    email = lead_data.get("email", "")
    actions: list[dict] = []

    if stage in ("proposal_sent", "client_review", "proposal"):
        actions.extend([
            {"type": "review", "label": "View proposal", "doc_id": "proposal", "description": "Full client offer document", "priority": "high"},
            {"type": "review", "label": "View client email", "doc_id": "proposal_email", "description": "Email sent or ready to send to buyer", "priority": "high"},
            {"type": "review", "label": "Quote comparison", "doc_id": "quotes", "description": "All supplier options compared", "priority": "high"},
            {"type": "review", "label": "Contact supplier", "doc_id": "recommended_supplier", "description": "WhatsApp / email / platform link", "priority": "high"},
            {"type": "review", "label": "Contact buyer", "doc_id": "buyer_contacts", "description": f"Reach {email or 'the client'}", "priority": "high"},
            {"type": "review", "label": "View RFQ", "doc_id": "rfqs", "description": "RFQ sent to factories", "priority": "medium"},
            {"type": "review", "label": "View outreach", "doc_id": "outreach", "description": "Original outreach email to this lead", "priority": "medium"},
        ])
    elif stage == "order_tracking":
        actions.extend([
            {"type": "update", "label": "Update client", "description": "Share production / shipping status with buyer", "priority": "high"},
            {"type": "email", "label": "Email status update", "description": "Send progress note to client", "priority": "medium", "mailto": email},
            {"type": "call", "label": "Call factory", "description": "Confirm production timeline with supplier", "priority": "medium"},
        ])
    elif stage == "finance":
        actions.extend([
            {"type": "invoice", "label": "Send invoice", "description": "Issue deposit or final invoice to client", "priority": "high"},
            {"type": "payment", "label": "Record payment", "description": "Mark deposit received when paid", "priority": "high"},
            {"type": "close", "label": "Close deal", "description": "Move to Closed Deals once fully paid and delivered", "priority": "medium"},
        ])
    else:
        actions.append({"type": "review", "label": "Review deal", "description": "Check current status and next steps", "priority": "high"})

    return actions


def _revenue_snapshot(deal: dict, proposal: dict, order_data: dict) -> dict:
    client_price = float(proposal.get("client_price_usd") or 0)
    factory_cost = float(proposal.get("factory_cost_usd") or 0)
    margin_usd = float(proposal.get("margin_usd") or max(0, client_price - factory_cost))
    margin_pct = proposal.get("margin_percent")
    if margin_pct is None and client_price and factory_cost:
        margin_pct = round(100 * margin_usd / client_price, 1)
    deposit_pct = 0.3
    billed = float(order_data.get("amount_billed_usd") or order_data.get("deposit_received_usd") or 0)
    return {
        "expected_usd": client_price,
        "factory_cost_usd": factory_cost,
        "margin_usd": round(margin_usd, 2),
        "margin_percent": margin_pct,
        "billed_usd": billed,
        "outstanding_usd": max(0, client_price - billed),
        "deposit_expected_usd": round(client_price * deposit_pct, 2) if client_price else 0,
        "currency": "USD",
    }


def _minimal_review_fallback(
    deal: dict,
    lead: dict | None,
    proposal: dict,
    quotes_list: list,
    lead_data: dict,
) -> dict[str, Any]:
    """Lightweight review when full package build fails."""
    from src.core.draft_composer import compose_proposal_client_email

    company_name = (lead or {}).get("company_name") or deal.get("lead_company", "Client")
    comparison = proposal.get("supplier_comparison") or quotes_list
    rec_name = proposal.get("recommended_option") or ""
    recommended = None
    for q in comparison:
        factory = q.get("factory") or q.get("factory_name") or ""
        if factory and (not rec_name or rec_name.lower() in factory.lower()):
            recommended = {
                "factory_name": factory,
                "url": q.get("url", ""),
                "unit_price_estimate_usd": q.get("price_usd"),
                "moq": q.get("moq"),
                "trust_score": q.get("rating"),
                "contacts": {"emails": [], "phones": [], "whatsapp": []},
            }
            break
    proposal_email = proposal.get("client_email_draft") or compose_proposal_client_email(
        proposal, {"company_name": company_name, "email": lead_data.get("email", "")}
    )
    buyer_contacts = extract_buyer_contacts(lead_data)
    return {
        "deal_id": deal["id"],
        "company_name": company_name,
        "steps": [],
        "documents": [],
        "artifacts": {
            "proposal": proposal,
            "proposal_email": proposal_email,
            "buyer_contacts": buyer_contacts,
            "quotes": {"quotes": comparison, "comparison": {"recommended_supplier": rec_name}},
            "recommended_supplier": recommended,
        },
    }


def aggregate_revenue(records: list[dict], *, closed: bool = False) -> dict[str, Any]:
    expected = sum(r.get("revenue", {}).get("expected_usd", 0) for r in records)
    billed = sum(r.get("revenue", {}).get("billed_usd", 0) for r in records)
    return {
        "deal_count": len(records),
        "expected_revenue_usd": round(expected, 2),
        "billed_usd": round(billed, 2),
        "outstanding_usd": round(max(0, expected - billed), 2),
        "closed": closed,
    }
