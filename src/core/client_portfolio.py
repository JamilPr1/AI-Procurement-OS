"""Client contact portfolio — full communication history per buyer."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.core.company_name import normalize_lead_record
from src.core.deal_review import PIPELINE_STEP_DEFS, build_deal_review_package
from src.core.draft_composer import compose_outreach_email, compose_personalization, compose_proposal_client_email
from src.core.email import EmailService


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lead_data(lead: dict) -> dict:
    data = lead.get("data") or {}
    if isinstance(data, str):
        import json
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            data = {}
    return normalize_lead_record({**data, "company_name": lead.get("company_name", "")})


def _event(
    *,
    event_id: str,
    kind: str,
    title: str,
    detail: str = "",
    when: str | None = None,
    status: str = "completed",
    channel: str = "system",
    to: str = "",
    subject: str = "",
    body: str = "",
    html_body: str = "",
    meta: dict | None = None,
) -> dict[str, Any]:
    return {
        "id": event_id,
        "kind": kind,
        "title": title,
        "detail": detail,
        "when": when,
        "status": status,
        "channel": channel,
        "to": to,
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "meta": meta or {},
    }


def _email_event_from_draft(
    *,
    event_id: str,
    kind: str,
    title: str,
    draft: dict,
    default_status: str = "draft",
) -> dict[str, Any]:
    send = draft.get("send_result") or {}
    status = draft.get("status") or default_status
    is_demo = send.get("status") == "dry_run" or send.get("demo")
    channel = "demo_email" if is_demo else ("email" if status == "sent" else "draft")
    detail = ""
    if send.get("message"):
        detail = send["message"]
    elif status == "sent":
        detail = "Sent to client"
    return _event(
        event_id=event_id,
        kind=kind,
        title=title,
        detail=detail,
        when=draft.get("sent_at") or draft.get("created_at"),
        status=status,
        channel=channel,
        to=draft.get("to", ""),
        subject=draft.get("subject", ""),
        body=draft.get("body", "") or draft.get("email_body", "") or draft.get("rfq_body", ""),
        html_body=draft.get("html_body", ""),
        meta={"send_result": send, "demo": is_demo},
    )


def build_client_timeline(storage: Any, lead: dict, deals: list[dict]) -> list[dict[str, Any]]:
    lead_id = lead["id"]
    lead_data = _lead_data(lead)
    events: list[dict[str, Any]] = []

    events.append(_event(
        event_id="lead_discovered",
        kind="milestone",
        title="Lead discovered",
        detail=f"Source: {lead_data.get('source', 'web')}",
        when=lead_data.get("first_seen_at") or lead.get("created_at"),
        status="completed",
    ))

    company = storage.load_json_entity("companies", lead_id) or {}
    if company:
        summary = (company.get("company_summary") or "")[:160]
        events.append(_event(
            event_id="company_research",
            kind="research",
            title="Company research",
            detail=summary or "Buyer profile and product catalog captured",
            when=lead.get("updated_at"),
            status="completed",
        ))

    personalization = storage.load_json_entity("personalization", lead_id) or {}
    if personalization:
        events.append(_event(
            event_id="personalization",
            kind="draft",
            title="Personalization draft",
            detail=personalization.get("subject_line", ""),
            when=lead.get("updated_at"),
            status="completed",
            subject=personalization.get("subject_line", ""),
            body=personalization.get("email_body", ""),
        ))

    outreach = storage.load_json_entity("outreach", lead_id) or {}
    if outreach:
        events.append(_email_event_from_draft(
            event_id="outreach_email",
            kind="outreach",
            title="Outreach email",
            draft=outreach,
        ))

    for deal in deals:
        deal_id = deal["id"]
        req = deal.get("buyer_requirements") or {}
        if isinstance(req, str):
            import json
            try:
                req = json.loads(req)
            except json.JSONDecodeError:
                req = {}

        events.append(_event(
            event_id=f"deal_{deal_id}",
            kind="milestone",
            title="Deal opened",
            detail=f"{req.get('product_description', 'Sourcing')} · Qty {req.get('quantity', '—')}",
            when=deal.get("created_at"),
            status="completed",
            meta={"deal_id": deal_id, "stage": deal.get("stage")},
        ))

        approval = storage.load_json_entity("supplier_approvals", deal_id) or {}
        if approval:
            events.append(_event(
                event_id=f"supplier_approval_{deal_id}",
                kind="internal",
                title="Suppliers approved",
                detail=f"{len(approval.get('suppliers') or [])} factories shortlisted",
                when=approval.get("approved_at") or deal.get("updated_at"),
                status="completed" if approval.get("approved") else "pending",
            ))

        for rfq in storage.get_rfqs_for_deal(deal_id):
            data = rfq.get("data") or {}
            if isinstance(data, str):
                import json
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    data = {}
            events.append(_email_event_from_draft(
                event_id=f"rfq_{rfq.get('id')}",
                kind="rfq",
                title="RFQ to suppliers",
                draft={
                    "to": "suppliers@factory",
                    "subject": data.get("subject", "RFQ"),
                    "body": data.get("rfq_body", ""),
                    "status": rfq.get("status", "draft"),
                    "sent_at": data.get("sent_at"),
                    "send_result": data.get("send_result"),
                },
            ))

        quotes = storage.load_json_entity("quotes", deal_id) or {}
        qlist = quotes.get("quotes") or []
        if qlist:
            events.append(_event(
                event_id=f"quotes_{deal_id}",
                kind="internal",
                title="Quote comparison",
                detail=f"{len(qlist)} supplier options evaluated",
                when=deal.get("updated_at"),
                status="completed",
                meta={"quotes": qlist},
            ))

        proposal = storage.load_json_entity("proposals", deal_id) or {}
        if proposal:
            events.append(_event(
                event_id=f"proposal_doc_{deal_id}",
                kind="proposal",
                title="Proposal document",
                detail=proposal.get("executive_summary", "")[:200],
                when=proposal.get("sent_at") or deal.get("updated_at"),
                status=proposal.get("status", "draft"),
                meta={
                    "client_price_usd": proposal.get("client_price_usd"),
                    "factory_cost_usd": proposal.get("factory_cost_usd"),
                    "margin_usd": proposal.get("margin_usd"),
                    "margin_percent": proposal.get("margin_percent"),
                    "recommended_option": proposal.get("recommended_option"),
                    "title": proposal.get("title"),
                },
            ))
            email_draft = proposal.get("client_email_draft") or compose_proposal_client_email(proposal, lead_data)
            events.append(_email_event_from_draft(
                event_id=f"proposal_email_{deal_id}",
                kind="proposal_email",
                title="Proposal email to client",
                draft={
                    **email_draft,
                    "status": proposal.get("status", email_draft.get("status", "draft")),
                    "sent_at": proposal.get("sent_at"),
                    "send_result": proposal.get("send_result"),
                },
            ))

        if deal.get("stage") in ("proposal_sent", "order_tracking", "finance", "closed", "client_review"):
            events.append(_event(
                event_id=f"tracking_{deal_id}",
                kind="milestone",
                title="Moved to tracking",
                detail=f"Stage: {(deal.get('stage') or '').replace('_', ' ')}",
                when=deal.get("tracking_entered_at") or deal.get("updated_at"),
                status="completed",
            ))

    events.sort(key=lambda e: e.get("when") or "", reverse=False)
    return events


def _available_views(storage: Any, lead_id: str, deals: list[dict]) -> list[dict[str, str]]:
    views: list[dict[str, str]] = []
    company = storage.load_json_entity("companies", lead_id) or {}
    if company and (company.get("company_summary") or company.get("products_services")):
        views.append({"id": "company", "label": "Company profile", "status": "ready"})
    personalization = storage.load_json_entity("personalization", lead_id) or {}
    if personalization.get("email_body") or personalization.get("subject_line"):
        views.append({"id": "personalization", "label": "Personalization", "status": "ready"})
    outreach = storage.load_json_entity("outreach", lead_id) or {}
    if outreach.get("body"):
        views.append({"id": "outreach", "label": "Outreach email", "status": outreach.get("status", "draft")})
    deal = deals[0] if deals else None
    if not deal:
        return views
    deal_id = deal["id"]
    req = deal.get("buyer_requirements") or {}
    if isinstance(req, str):
        import json
        try:
            req = json.loads(req)
        except json.JSONDecodeError:
            req = {}
    if req.get("product_description"):
        views.append({"id": "requirements", "label": "Requirements", "status": "ready"})
    if storage.load_json_entity("products", deal_id):
        views.append({"id": "product_spec", "label": "Product spec", "status": "ready"})
    if storage.get_rfqs_for_deal(deal_id):
        views.append({"id": "rfq", "label": "RFQ email", "status": "ready"})
    quotes = storage.load_json_entity("quotes", deal_id) or {}
    if quotes.get("quotes"):
        views.append({"id": "quotes", "label": "Quote comparison", "status": "ready"})
    proposal = storage.load_json_entity("proposals", deal_id) or {}
    if proposal.get("title") or proposal.get("executive_summary"):
        views.append({"id": "proposal", "label": "Proposal", "status": proposal.get("status", "draft")})
    if proposal.get("client_email_draft", {}).get("body") or proposal.get("executive_summary"):
        views.append({
            "id": "proposal_email",
            "label": "Proposal email",
            "status": proposal.get("status", "draft"),
        })
    return views


def build_client_summary_light(storage: Any, lead: dict, deals: list[dict]) -> dict[str, Any]:
    """Fast summary for list view — no full timeline build."""
    lead_id = lead["id"]
    lead_data = _lead_data(lead)
    outreach = storage.load_json_entity("outreach", lead_id) or {}
    active_deal = deals[0] if deals else None
    proposal = storage.load_json_entity("proposals", active_deal["id"]) or {} if active_deal else {}
    views = _available_views(storage, lead_id, deals)
    emails_sent = int(outreach.get("status") == "sent") + int(proposal.get("status") == "sent")
    return {
        "lead_id": lead_id,
        "company_name": lead_data.get("company_name", lead.get("company_name")),
        "email": lead_data.get("email", ""),
        "phone": lead_data.get("phone", ""),
        "website": lead_data.get("website", ""),
        "domain": lead_data.get("domain", ""),
        "lead_score": lead.get("lead_score", 0),
        "deal_id": active_deal.get("id") if active_deal else None,
        "deal_stage": active_deal.get("stage") if active_deal else None,
        "deal_status": active_deal.get("status") if active_deal else None,
        "emails_sent": emails_sent,
        "proposal_count": 1 if proposal else 0,
        "views": views,
        "last_activity": lead.get("updated_at"),
    }


def build_client_summary(storage: Any, lead: dict, deals: list[dict]) -> dict[str, Any]:
    """Full summary including timeline stats (slower — use for detail only)."""
    summary = build_client_summary_light(storage, lead, deals)
    timeline = build_client_timeline(storage, lead, deals)
    summary["timeline_count"] = len(timeline)
    summary["emails_sent"] = sum(
        1 for e in timeline if e.get("status") == "sent" and e.get("kind") in ("outreach", "proposal_email")
    )
    summary["proposal_count"] = sum(1 for e in timeline if e.get("kind") == "proposal")
    return summary


def build_client_detail(storage: Any, lead_id: str, *, tenant_id: str = "agency_primary") -> dict[str, Any] | None:
    lead = storage.get_lead(lead_id)
    if not lead:
        return None
    deals = storage.get_deals_for_lead(lead_id)
    lead_data = _lead_data(lead)
    timeline = build_client_timeline(storage, lead, deals)
    reviews = []
    for deal in deals:
        pkg = build_deal_review_package(storage, deal, lead, tenant_id=tenant_id)
        reviews.append(pkg)

    return {
        "summary": build_client_summary(storage, lead, deals),
        "lead": lead_data,
        "deals": deals,
        "timeline": timeline,
        "reviews": reviews,
        "steps": reviews[0].get("steps", []) if reviews else [],
        "email_status": EmailService().status(),
    }


def count_client_contacts(storage: Any, tenant_id: str) -> int:
    leads = storage.list_leads(tenant_id, limit=500)
    count = 0
    for lead in leads:
        lid = lead["id"]
        if storage.get_deals_for_lead(lid):
            count += 1
        elif storage.load_json_entity("outreach", lid) or storage.load_json_entity("personalization", lid):
            count += 1
    return count


def get_client_view(storage: Any, lead_id: str, view_id: str, *, tenant_id: str = "agency_primary") -> dict[str, Any] | None:
    """Load a single artifact for modal view — fast, no full timeline."""
    lead = storage.get_lead(lead_id)
    if not lead:
        return None
    lead_data = _lead_data(lead)
    deals = storage.get_deals_for_lead(lead_id)
    deal = deals[0] if deals else None
    deal_id = deal["id"] if deal else None
    company_name = lead_data.get("company_name", lead.get("company_name"))

    if view_id == "company":
        return {"view": view_id, "title": f"Company profile — {company_name}", "type": "company",
                "data": storage.load_json_entity("companies", lead_id) or {}}
    if view_id == "personalization":
        return {"view": view_id, "title": f"Personalization — {company_name}", "type": "text",
                "data": storage.load_json_entity("personalization", lead_id) or {}}
    if view_id == "outreach":
        return {"view": view_id, "title": f"Outreach email — {company_name}", "type": "email",
                "data": storage.load_json_entity("outreach", lead_id) or {}}
    if view_id == "requirements" and deal:
        req = deal.get("buyer_requirements") or {}
        if isinstance(req, str):
            import json
            try:
                req = json.loads(req)
            except json.JSONDecodeError:
                req = {}
        return {"view": view_id, "title": f"Requirements — {company_name}", "type": "kv", "data": req}
    if view_id == "product_spec" and deal_id:
        return {"view": view_id, "title": f"Product spec — {company_name}", "type": "kv",
                "data": storage.load_json_entity("products", deal_id) or {}}
    if view_id == "rfq" and deal_id:
        rfqs = storage.get_rfqs_for_deal(deal_id)
        data = rfqs[0].get("data") or {} if rfqs else {}
        if isinstance(data, str):
            import json
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        return {"view": view_id, "title": f"RFQ email — {company_name}", "type": "rfq", "data": data}
    if view_id == "quotes" and deal_id:
        return {"view": view_id, "title": f"Quote comparison — {company_name}", "type": "quotes",
                "data": storage.load_json_entity("quotes", deal_id) or {}}
    if view_id == "proposal" and deal_id:
        return {"view": view_id, "title": f"Proposal — {company_name}", "type": "proposal",
                "data": storage.load_json_entity("proposals", deal_id) or {}}
    if view_id == "proposal_email" and deal_id:
        proposal = storage.load_json_entity("proposals", deal_id) or {}
        email_draft = proposal.get("client_email_draft") or compose_proposal_client_email(proposal, lead_data)
        return {"view": view_id, "title": f"Proposal email — {company_name}", "type": "email", "data": {
            **email_draft,
            "status": proposal.get("status", email_draft.get("status", "draft")),
            "sent_at": proposal.get("sent_at"),
            "send_result": proposal.get("send_result"),
        }}
    return None


def list_client_contacts(storage: Any, tenant_id: str) -> list[dict[str, Any]]:
    leads = storage.list_leads(tenant_id, limit=500)
    clients: list[dict[str, Any]] = []
    for lead in leads:
        deals = storage.get_deals_for_lead(lead["id"])
        outreach = storage.load_json_entity("outreach", lead["id"])
        personalization = storage.load_json_entity("personalization", lead["id"])
        if not deals and not outreach and not personalization:
            continue
        clients.append(build_client_summary_light(storage, lead, deals))
    clients.sort(key=lambda c: c.get("last_activity") or "", reverse=True)
    return clients


def complete_demo_client_flow(
    storage: Any,
    lead_id: str,
    *,
    tenant_id: str = "agency_primary",
    email: EmailService | None = None,
) -> dict[str, Any]:
    """Mark outreach + proposal as demo-sent so full client flow is visible."""
    email = email or EmailService()
    lead = storage.get_lead(lead_id)
    if not lead:
        raise ValueError("Lead not found")

    lead_data = _lead_data(lead)
    now = _utc_now()
    actions: list[str] = []

    company = storage.load_json_entity("companies", lead_id) or {}
    profile = company if company else {"company_summary": lead_data.get("search_snippet", "")}
    personalization = storage.load_json_entity("personalization", lead_id) or compose_personalization(lead_data, profile)
    storage.save_json_entity("personalization", lead_id, personalization)

    outreach = storage.load_json_entity("outreach", lead_id) or compose_outreach_email(lead_data, personalization)
    if outreach.get("status") != "sent":
        to = outreach.get("to") or lead_data.get("email") or "demo-client@example.com"
        send_result = email.send(
            to,
            outreach.get("subject", "Partnership opportunity"),
            outreach.get("body", ""),
            html_body=outreach.get("html_body"),
            html=bool(outreach.get("html_body")),
        )
        send_result["demo"] = True
        send_result["message"] = "Demo email recorded — visible in Contacts (not sent via SMTP)"
        outreach["to"] = to
        outreach["status"] = "sent"
        outreach["sent_at"] = now
        outreach["send_result"] = send_result
        storage.save_json_entity("outreach", lead_id, outreach)
        actions.append("outreach_demo_sent")

    deals = storage.get_deals_for_lead(lead_id)
    for deal in deals:
        deal_id = deal["id"]
        approval = storage.load_json_entity("supplier_approvals", deal_id) or {}
        if not approval.get("approved"):
            quotes = storage.load_json_entity("quotes", deal_id) or {}
            approval = {
                "approved": True,
                "approved_at": now,
                "demo": True,
                "suppliers": quotes.get("quotes") or [],
            }
            storage.save_json_entity("supplier_approvals", deal_id, approval)
            actions.append(f"supplier_approval_{deal_id}")

        proposal = storage.load_json_entity("proposals", deal_id) or {}
        if proposal and proposal.get("status") != "sent":
            client_email = proposal.get("client_email_draft") or compose_proposal_client_email(proposal, lead_data)
            to = client_email.get("to") or lead_data.get("email") or "demo-client@example.com"
            send_result = email.send(
                to,
                client_email.get("subject", proposal.get("title", "Your proposal")),
                client_email.get("body", ""),
                html_body=client_email.get("html_body"),
                html=bool(client_email.get("html_body")),
            )
            send_result["demo"] = True
            send_result["message"] = "Demo proposal email recorded — visible in Contacts"
            proposal["client_email_draft"] = client_email
            proposal["status"] = "sent"
            proposal["sent_at"] = now
            proposal["send_result"] = send_result
            storage.save_json_entity("proposals", deal_id, proposal)
            storage.update_deal(
                deal_id,
                stage="proposal_sent",
                status="tracking",
                tracking_entered_at=now,
            )
            actions.append(f"proposal_demo_sent_{deal_id}")

    return {
        "lead_id": lead_id,
        "actions": actions,
        "detail": build_client_detail(storage, lead_id, tenant_id=tenant_id),
    }
