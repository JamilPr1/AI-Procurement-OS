"""FastAPI CRM dashboard server."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.agency import Agency
from src.core.brain import Brain
from src.core.event_bus import bus
from src.core.llm import LLMClient
from src.core.logger import PlatformLogger
from src.core.orchestrator import Orchestrator
from src.core.pipeline_engine import PipelineEngine
from src.core.pipeline_stages import CRM_PAGES, INTEGRATIONS_NEEDED, PIPELINE_STAGES, ROADMAP_PHASES
from src.core.contacts import alibaba_contact_url, extract_buyer_contacts, extract_contacts
from src.core.email import EmailService
from src.core.deal_lifecycle import is_closed_deal, is_tracking_deal
from src.core.tracking import aggregate_revenue, build_tracking_record
from src.core.lead_pipeline import LeadPipelineService
from src.core.storage import Storage
from src.core.deal_review import build_deal_review_package
from src.core.client_portfolio import (
    build_client_detail,
    complete_demo_client_flow,
    count_client_contacts,
    get_client_view,
    list_client_contacts,
)
from src.core.product_finder_store import ProductFinderStore
from src.saas import SaaSPlatform
from src.saas.demo_seed import collect_credentials, seed_demo_data
from src.saas.credentials_doc import generate_credentials_doc
from src.core.store_repair import repair_store_orders

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="AI Procurement CRM")
_brain: Brain | None = None
_engine: PipelineEngine | None = None
_storage: Storage | None = None
_agency: Agency | None = None
_active_run_id: str | None = None
_lead_pipeline: LeadPipelineService | None = None
_saas: SaaSPlatform | None = None
_store: ProductFinderStore | None = None
_agent_status: dict[str, str] = {s["agent"]: "idle" for s in PIPELINE_STAGES}


def _init() -> PipelineEngine:
    global _brain, _engine, _storage, _agency, _lead_pipeline, _saas, _store
    if _engine:
        return _engine
    _brain = Brain(PROJECT_ROOT)
    _brain.load()
    logger = PlatformLogger(PROJECT_ROOT, _brain.config)
    _storage = Storage(_brain.db_path(), _brain.data_dir(), logger)
    _storage.initialize(_brain.config.get("agency", {}))
    llm = LLMClient(_brain.config)
    orchestrator = Orchestrator(_brain, llm, _storage, logger)
    _agency = Agency(_brain.config.get("agency", {}))
    _saas = SaaSPlatform(_brain.config.get("saas", {}))
    tenant_svc = _saas.bind(_storage, _brain.config.get("agency", {}))
    tenant_svc.bootstrap()
    try:
        seed_demo_data(_storage, tenant_svc, _brain.config.get("agency", {}))
        repair_store_orders(_storage)
    except Exception:
        pass  # seed is idempotent; don't block startup
    _store = ProductFinderStore(_storage, _agency, _brain.config, tenant_svc)
    _engine = PipelineEngine(_brain, orchestrator, _storage, logger, _agency, llm, PROJECT_ROOT)
    _lead_pipeline = LeadPipelineService(_engine)
    return _engine


@app.on_event("startup")
def startup() -> None:
    global _active_run_id
    engine = _init()
    runs = _storage.list_pipeline_runs(_agency.tenant_id, limit=1)  # type: ignore
    if runs and runs[0]["status"] in ("running", "paused"):
        _active_run_id = runs[0]["id"]
    # Warm hot-leads cache and refresh drafts in background
    import threading
    def _warm():
        try:
            _lead_pipeline.refresh_all_drafts()  # type: ignore
            _lead_pipeline.analyze_all()  # type: ignore
        except Exception:
            pass
    threading.Thread(target=_warm, daemon=True).start()


@app.get("/")
def landing_page() -> FileResponse:
    return FileResponse(WEB_DIR / "landing.html")


@app.get("/app")
def crm_app() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def _tid() -> str:
    return _agency.tenant_id  # type: ignore


@app.get("/api/health")
def health() -> dict:
    from src.core.platform_urls import get_public_base_url

    engine = _init()
    dash = _brain.config.get("dashboard", {}) if _brain else {}  # type: ignore
    public_url = get_public_base_url(_brain.config if _brain else {})
    return {
        "status": "ok",
        "llm": engine.llm.health_check(),
        "project": _brain.config.get("project") if _brain else {},
        "public_url": public_url,
        "store": {"enabled": True, "url": f"{public_url}/store?tenant=demo"},
        "landing": "/",
        "crm": "/app",
        "login": "/login",
        "marketing": "/marketing",
        "port": dash.get("port", 8765),
    }


@app.get("/api/overview")
def overview() -> dict:
    _init()
    stats = _storage.stats(_tid())  # type: ignore
    runs = _storage.list_pipeline_runs(_tid(), limit=5)  # type: ignore
    active = None
    if _active_run_id:
        active = _engine.get_status(_active_run_id)  # type: ignore
    return {
        "stats": stats,
        "revenue": _storage.revenue_stats(_tid()),  # type: ignore
        "contacts_count": count_client_contacts(_storage, _tid()),  # type: ignore
        "active_run": active,
        "active_run_id": _active_run_id,
        "agency": _agency.summary() if _agency else {},  # type: ignore
        "saas": _saas.summary() if _saas else {},
    }


@app.get("/api/stats")
def stats() -> dict:
    _init()
    return _storage.stats(_tid())  # type: ignore


@app.get("/api/leads")
def list_leads() -> dict:
    _init()
    rows = _storage.list_leads(_tid())  # type: ignore
    items = []
    for r in rows:
        deals = _storage.get_deals_for_lead(r["id"])  # type: ignore
        if deals and (is_tracking_deal(deals[0]) or is_closed_deal(deals[0])):
            continue
        d = r.get("data") or {}
        items.append({
            "id": r["id"],
            "company_name": r["company_name"],
            "email": d.get("email", ""),
            "phone": d.get("phone", ""),
            "website": d.get("website", ""),
            "domain": d.get("domain", ""),
            "industry": d.get("industry", ""),
            "lead_score": r.get("lead_score", 0),
            "status": r.get("status", "new"),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "data": d,
        })
    return {"leads": items, "total": len(items)}


@app.get("/api/deals")
def list_deals() -> dict:
    _init()
    rows = _storage.list_active_sourcing_deals(_tid())  # type: ignore
    return {"deals": rows, "total": len(rows)}


@app.get("/api/suppliers")
def list_suppliers() -> dict:
    _init()
    rows = _storage.list_suppliers(_tid())  # type: ignore
    items = []
    for r in rows:
        d = r.get("data") or {}
        items.append({
            "id": r["id"],
            "factory_name": r["factory_name"],
            "trust_score": r.get("trust_score", 0),
            "platform": d.get("platform_source", ""),
            "url": d.get("url", ""),
            "price": d.get("unit_price_estimate_usd", 0),
            "moq": d.get("moq", 0),
            "created_at": r.get("created_at"),
            "updated_at": r.get("updated_at"),
            "data": d,
        })
    return {"suppliers": items, "total": len(items)}


@app.get("/api/leads/{lead_id}")
def get_lead_detail(lead_id: str) -> dict:
    _init()
    detail = _storage.get_lead_detail(lead_id)  # type: ignore
    if not detail:
        raise HTTPException(404, "Lead not found")
    detail["contacts"] = extract_buyer_contacts(detail.get("data") or {})
    return detail


@app.get("/api/deals/{deal_id}")
def get_deal_detail(deal_id: str) -> dict:
    _init()
    detail = _storage.get_deal_detail(deal_id)  # type: ignore
    if not detail:
        raise HTTPException(404, "Deal not found")
    return detail


@app.get("/api/suppliers/{supplier_id}")
def get_supplier_detail(supplier_id: str) -> dict:
    _init()
    detail = _storage.get_supplier_detail(supplier_id)  # type: ignore
    if not detail:
        raise HTTPException(404, "Supplier not found")
    data = detail.get("data") or {}
    detail["contacts"] = extract_contacts(data)
    detail["alibaba_profile"] = alibaba_contact_url(data.get("url", ""))
    return detail


@app.get("/api/hot-leads")
def list_hot_leads(min_score: float = 0, hot_only: bool = False) -> dict:
    _init()
    briefs = _lead_pipeline.analyze_all()  # type: ignore
    if min_score > 0:
        briefs = [b for b in briefs if b.get("hot_score", 0) >= min_score]
    if hot_only:
        briefs = [b for b in briefs if b.get("is_hot")]
    hot_count = sum(1 for b in briefs if b.get("is_hot"))
    return {"hot_leads": briefs, "total": len(briefs), "hot_count": hot_count}


@app.post("/api/hot-leads/analyze")
def analyze_hot_leads() -> dict:
    _init()
    _lead_pipeline.refresh_all_drafts()  # type: ignore
    briefs = _lead_pipeline.analyze_all()  # type: ignore
    hot_count = sum(1 for b in briefs if b.get("is_hot"))
    return {"hot_leads": briefs, "total": len(briefs), "hot_count": hot_count, "status": "analyzed"}


@app.post("/api/hot-leads/refresh-drafts")
def refresh_all_hot_lead_drafts() -> dict:
    _init()
    return _lead_pipeline.refresh_all_drafts()  # type: ignore


@app.get("/api/hot-leads/{lead_id}")
def get_hot_lead(lead_id: str) -> dict:
    _init()
    try:
        _lead_pipeline.refresh_lead_drafts(lead_id)  # type: ignore
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except Exception:
        pass  # refresh optional — still return analyzed brief
    brief = _lead_pipeline.analyze_lead(lead_id)  # type: ignore
    if not brief:
        raise HTTPException(404, "Lead not found")
    return brief


@app.post("/api/hot-leads/{lead_id}/refresh-drafts")
def refresh_hot_lead_drafts(lead_id: str) -> dict:
    _init()
    try:
        return _lead_pipeline.refresh_lead_drafts(lead_id)  # type: ignore
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.get("/api/hot-leads/{lead_id}/pipeline")
def get_hot_lead_pipeline(lead_id: str) -> dict:
    _init()
    try:
        return _lead_pipeline.get_pipeline_package(lead_id)  # type: ignore
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.patch("/api/hot-leads/{lead_id}/draft")
def patch_hot_lead_draft(lead_id: str, body: dict) -> dict:
    _init()
    try:
        return _lead_pipeline.update_draft(lead_id, body)  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.patch("/api/hot-leads/{lead_id}/supplier-selection")
def patch_hot_lead_supplier_selection(lead_id: str, body: dict) -> dict:
    _init()
    try:
        return _lead_pipeline.set_supplier_selection(lead_id, body.get("supplier_id", ""))  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.get("/api/email/status")
def email_status() -> dict:
    return EmailService().status()


def _auto_approve() -> bool:
    import os
    env = os.getenv("AUTO_APPROVE", "").strip().lower()
    if env in ("0", "false", "no"):
        return False
    if env in ("1", "true", "yes"):
        return True
    _init()
    return bool(_brain.config.get("agency", {}).get("auto_approve", True))  # type: ignore


@app.post("/api/hot-leads/{lead_id}/advance")
def advance_hot_lead(lead_id: str, run_all: bool = False, auto_approve: bool | None = None) -> dict:
    _init()
    auto = _auto_approve() if auto_approve is None else auto_approve
    try:
        if run_all:
            results = []
            for _ in range(20):
                r = _lead_pipeline.advance(lead_id, auto_approve=auto)  # type: ignore
                results.append(r)
                if r.get("status") in ("completed", "busy", "tracking", "closed"):
                    break
                if r.get("brief", {}).get("next_step", {}).get("terminal"):
                    break
            return {"status": "success", "steps": len(results), "last": results[-1] if results else {}, "auto_approve": auto}
        return _lead_pipeline.advance(lead_id, auto_approve=auto)  # type: ignore
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


@app.post("/api/hot-leads/{lead_id}/approve")
def approve_hot_lead_review(lead_id: str, body: dict | None = Body(None)) -> dict:
    """Approve pending review and send email (if applicable), then advance to next stage."""
    _init()
    try:
        overrides = body if body else None
        return _lead_pipeline.approve_review(lead_id, draft_overrides=overrides)  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(500, str(e)) from e


def _tracking_record(deal: dict) -> dict:
    lead = _storage.get_lead(deal["lead_id"]) if deal.get("lead_id") else None  # type: ignore
    did = deal["id"]
    return build_tracking_record(
        deal,
        lead,
        proposal=_storage.load_json_entity("proposals", did),  # type: ignore
        quotes=_storage.load_json_entity("quotes", did),  # type: ignore
        order=_storage.get_order_for_deal(did),  # type: ignore
        company=_storage.load_json_entity("companies", deal["lead_id"]) if deal.get("lead_id") else None,  # type: ignore
        storage=_storage,  # type: ignore
        tenant_id=_tid(),
    )


@app.get("/portal/{deal_id}")
def portal_page(deal_id: str) -> FileResponse:
    return FileResponse(WEB_DIR / "portal.html")


@app.get("/store")
def store_page() -> FileResponse:
    return FileResponse(WEB_DIR / "store.html")


@app.get("/marketing")
def marketing_page() -> FileResponse:
    return FileResponse(WEB_DIR / "marketing.html")


@app.get("/login")
def login_page() -> FileResponse:
    return FileResponse(WEB_DIR / "login.html")


@app.post("/api/auth/login")
def auth_login(body: dict) -> dict:
    _init()
    email = (body.get("email") or "").strip()
    password = body.get("password") or ""
    if not email or not password:
        raise HTTPException(400, "Email and password required")
    user = _storage.verify_tenant_user(email, password)  # type: ignore
    if not user:
        raise HTTPException(401, "Invalid email or password")
    return {
        "user": {
            "email": user["email"],
            "name": user.get("name"),
            "role": user.get("role"),
            "tenant_id": user.get("tenant_id"),
            "tenant_name": user.get("tenant_name"),
            "tenant_slug": user.get("tenant_slug"),
        }
    }


@app.get("/api/store/tenant/{slug}")
def store_tenant(slug: str) -> dict:
    from src.saas.store_catalog import build_store_payload

    _init()
    tenant = _saas.tenants.resolve_slug(slug)  # type: ignore
    if not tenant:
        raise HTTPException(404, "Store not found")
    return build_store_payload(tenant)


@app.post("/api/store/sessions")
def store_start_session(body: dict) -> dict:
    _init()
    slug = body.get("tenant") or body.get("tenant_slug") or "demo"
    query = body.get("query", "")
    try:
        return _store.start_session(slug, query)  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/store/sessions/{session_id}")
def store_get_session(session_id: str) -> dict:
    _init()
    try:
        return _store.session_view(session_id)  # type: ignore
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@app.post("/api/store/sessions/{session_id}/answer")
def store_answer(session_id: str, body: dict) -> dict:
    _init()
    field = body.get("field")
    value = body.get("value")
    if not field:
        raise HTTPException(400, "field required")
    try:
        return _store.answer(session_id, field, value)  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/store/sessions/{session_id}/quote")
def store_quote(session_id: str) -> dict:
    _init()
    try:
        return _store.generate_quote(session_id)  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/store/sessions/{session_id}/order")
def store_place_order(session_id: str) -> dict:
    _init()
    try:
        return _store.place_order(session_id)  # type: ignore
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/saas/summary")
def saas_summary() -> dict:
    _init()
    return _saas.summary()  # type: ignore


@app.get("/api/saas/tenants")
def saas_list_tenants() -> dict:
    _init()
    tenants = _saas.tenants.list_tenants()  # type: ignore
    return {"tenants": tenants, "plans": _saas.plans}  # type: ignore


@app.post("/api/saas/tenants")
def saas_create_tenant(body: dict) -> dict:
    _init()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(400, "name required")
    try:
        tenant = _saas.tenants.create_tenant(  # type: ignore
            name,
            slug=body.get("slug"),
            plan=body.get("plan"),
            margin_percent=float(body.get("margin_percent", 15)),
            tagline=body.get("tagline", ""),
        )
        tenant["store_url"] = _saas.tenants.store_url(tenant.get("slug", ""))  # type: ignore
        return tenant
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.patch("/api/saas/tenants/{tenant_id}")
def saas_update_tenant(tenant_id: str, body: dict) -> dict:
    _init()
    tenant = _saas.tenants.update_tenant(  # type: ignore
        tenant_id,
        name=body.get("name"),
        plan=body.get("plan"),
        margin_percent=body.get("margin_percent"),
        store_enabled=body.get("store_enabled"),
        tagline=body.get("tagline"),
    )
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    tenant["store_url"] = _saas.tenants.store_url(tenant.get("slug", ""))  # type: ignore
    return tenant


@app.get("/api/portal/{deal_id}")
def portal_data(deal_id: str) -> dict:
    """Public read-only order status for clients (no auth yet — use magic links in production)."""
    _init()
    deal = _storage.get_deal(deal_id)  # type: ignore
    if not deal:
        raise HTTPException(404, "Order not found")
    if not (is_tracking_deal(deal) or is_closed_deal(deal)):
        raise HTTPException(404, "Order not yet available")
    rec = _tracking_record(deal)
    offer = rec.get("offer") or {}
    return {
        "deal_id": deal_id,
        "company_name": rec.get("company_name"),
        "stage": rec.get("stage"),
        "status_label": _portal_status_label(deal.get("stage", "")),
        "offer": {
            "title": offer.get("title"),
            "summary": offer.get("summary"),
            "product": offer.get("product"),
            "quantity": offer.get("quantity"),
            "client_price_usd": offer.get("client_price_usd"),
            "deposit_due_usd": offer.get("deposit_due_usd"),
            "delivery_date": offer.get("delivery_date"),
            "recommended_supplier": offer.get("recommended_supplier"),
        },
        "timeline": rec.get("timeline") or [],
        "updated_at": rec.get("updated_at"),
    }


def _portal_status_label(stage: str) -> str:
    labels = {
        "proposal_sent": "Proposal under review",
        "order_tracking": "In production",
        "finance": "Payment & invoicing",
        "closed": "Order complete",
    }
    return labels.get(stage, stage.replace("_", " ").title())


@app.get("/api/contacts")
def list_contacts() -> dict:
    """All clients with communication history."""
    _init()
    clients = list_client_contacts(_storage, _tid())  # type: ignore
    return {"clients": clients, "count": len(clients)}


@app.get("/api/contacts/{lead_id}/view/{view_id}")
def get_contact_view(lead_id: str, view_id: str) -> dict:
    _init()
    payload = get_client_view(_storage, lead_id, view_id, tenant_id=_tid())  # type: ignore
    if not payload:
        raise HTTPException(404, "View not found for this client")
    return payload


@app.get("/api/contacts/{lead_id}")
def get_contact(lead_id: str) -> dict:
    _init()
    detail = build_client_detail(_storage, lead_id, tenant_id=_tid())  # type: ignore
    if not detail:
        raise HTTPException(404, "Client not found")
    return detail


@app.post("/api/contacts/{lead_id}/demo-complete")
def demo_complete_contact(lead_id: str) -> dict:
    """Record demo outreach + proposal emails and complete visible client flow."""
    _init()
    try:
        result = complete_demo_client_flow(
            _storage, lead_id, tenant_id=_tid(), email=EmailService()  # type: ignore
        )
        return {"status": "ok", **result}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/contacts/demo-complete-all")
def demo_complete_all_contacts() -> dict:
    _init()
    clients = list_client_contacts(_storage, _tid())  # type: ignore
    results = []
    for c in clients:
        try:
            r = complete_demo_client_flow(
                _storage, c["lead_id"], tenant_id=_tid(), email=EmailService()  # type: ignore
            )
            results.append({"lead_id": c["lead_id"], "company_name": c["company_name"], "actions": r.get("actions", [])})
        except ValueError:
            continue
    return {"status": "ok", "processed": len(results), "results": results}


@app.get("/api/tracking")
def list_tracking() -> dict:
    _init()
    deals = _storage.list_tracking_deals(_tid())  # type: ignore
    records = [_tracking_record(d) for d in deals]
    return {
        "tracking": records,
        "total": len(records),
        "revenue": aggregate_revenue(records),
    }


@app.get("/api/tracking/{deal_id}/review")
def get_tracking_review(deal_id: str) -> dict:
    _init()
    deal = _storage.get_deal(deal_id)  # type: ignore
    if not deal:
        raise HTTPException(404, "Deal not found")
    lead = _storage.get_lead(deal["lead_id"]) if deal.get("lead_id") else None  # type: ignore
    return build_deal_review_package(_storage, deal, lead, tenant_id=_tid())  # type: ignore


@app.get("/api/tracking/{deal_id}")
def get_tracking(deal_id: str) -> dict:
    _init()
    deal = _storage.get_deal(deal_id)  # type: ignore
    if not deal or is_closed_deal(deal):
        raise HTTPException(404, "Tracking record not found")
    return _tracking_record(deal)


@app.post("/api/tracking/{deal_id}/advance")
def advance_tracking(deal_id: str, action: str = "") -> dict:
    """Manual stage advance on tracking page: order_tracking | finance."""
    _init()
    deal = _storage.get_deal(deal_id)  # type: ignore
    if not deal or is_closed_deal(deal):
        raise HTTPException(404, "Deal not found")
    stage = deal.get("stage", "proposal_sent")
    if action == "start_production" or stage == "proposal_sent":
        _storage.update_deal(deal_id, stage="order_tracking", status="tracking")  # type: ignore
    elif action == "finance" or stage == "order_tracking":
        _storage.update_deal(deal_id, stage="finance", status="tracking")  # type: ignore
    else:
        _storage.update_deal(deal_id, stage="order_tracking", status="tracking")  # type: ignore
    deal = _storage.get_deal(deal_id)  # type: ignore
    return _tracking_record(deal)


@app.post("/api/tracking/{deal_id}/close")
def close_tracking_deal(deal_id: str) -> dict:
    _init()
    ok = _storage.close_deal_manually(deal_id, _tid())  # type: ignore
    if not ok:
        raise HTTPException(404, "Deal not found")
    return {"status": "closed", "deal_id": deal_id}


@app.get("/api/closed-deals")
def list_closed_deals() -> dict:
    _init()
    deals = _storage.list_closed_deals(_tid())  # type: ignore
    records = [_tracking_record(d) for d in deals]
    return {
        "closed": records,
        "total": len(records),
        "revenue": aggregate_revenue(records, closed=True),
    }


@app.get("/api/revenue")
def revenue_stats() -> dict:
    _init()
    return _storage.revenue_stats(_tid())  # type: ignore


@app.get("/api/niche")
def get_current_niche() -> dict:
    _init()
    niche = _storage.load_json_entity("niche", "current")  # type: ignore
    return {"niche": niche or {}}


@app.post("/api/demo-request")
def demo_request(body: dict = Body(...)) -> dict:
    """Capture inbound demo/pilot requests from the landing page."""
    import os
    from datetime import datetime, timezone

    name = str(body.get("name") or "").strip()
    email = str(body.get("email") or "").strip()
    company = str(body.get("company") or "").strip()
    message = str(body.get("message") or "").strip()
    if not name or not email or not company:
        raise HTTPException(status_code=400, detail="Name, email, and company are required.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    entry = {
        "name": name,
        "email": email,
        "company": company,
        "message": message,
        "source": body.get("source") or "landing",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = PROJECT_ROOT / "data" / "demo_requests.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    contact = os.getenv("CONTACT_EMAIL", "").strip()
    return {
        "status": "ok",
        "message": "Thanks! We'll be in touch within 24 hours.",
        "contact_email": contact or None,
    }


@app.get("/api/demo-requests")
def list_demo_requests() -> dict:
    """List inbound demo requests (for admin review)."""
    path = PROJECT_ROOT / "data" / "demo_requests.jsonl"
    if not path.exists():
        return {"requests": []}
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    rows.reverse()
    return {"requests": rows[:100], "total": len(rows)}


@app.post("/api/admin/seed-demo")
def admin_seed_demo(force: bool = False) -> dict:
    """Seed demo tenants, users, and sample store orders."""
    _init()
    result = seed_demo_data(
        _storage,  # type: ignore
        _saas.tenants,  # type: ignore
        _brain.config.get("agency", {}),  # type: ignore
        force_orders=force,
    )
    return result


@app.post("/api/admin/generate-credentials")
def admin_generate_credentials() -> dict:
    """Generate PLATFORM_CREDENTIALS.docx in docs/ folder."""
    _init()
    cfg = _brain.config  # type: ignore
    dash = cfg.get("dashboard", {})
    creds = collect_credentials(
        _storage,  # type: ignore
        cfg.get("agency", {}),
        cfg,
        host=dash.get("host", "127.0.0.1"),
        port=dash.get("port", 8765),
    )
    out = PROJECT_ROOT / "docs" / "PLATFORM_CREDENTIALS.docx"
    generate_credentials_doc(creds, out)
    return {"path": str(out), "tenants": len(creds.get("tenants", [])), "users": len(creds.get("tenant_users", []))}


@app.post("/api/admin/repair-store-orders")
def admin_repair_store_orders() -> dict:
    _init()
    return repair_store_orders(_storage)  # type: ignore


@app.post("/api/admin/repair-names")
def repair_company_names() -> dict:
    """Fix SEO titles stored as company names and refresh drafts."""
    _init()
    result = _storage.repair_company_names(_tid())  # type: ignore
    return {"status": "ok", **result}


@app.post("/api/admin/reset")
def reset_workspace(include_suppliers: bool = False) -> dict:
    """Delete all leads and deals — fresh start."""
    _init()
    result = _storage.reset_workspace(_tid(), include_suppliers=include_suppliers)  # type: ignore
    return {"status": "ok", **result}


@app.get("/api/media/{entity_id}/{filename}")
def serve_media(entity_id: str, filename: str) -> FileResponse:
    _init()
    path = _storage.data_dir / "images" / entity_id / filename  # type: ignore
    if not path.exists() or not path.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(path)


@app.get("/api/agents")
def list_agents() -> dict:
    _init()
    agents = []
    last_runs = _storage.get_latest_agent_runs()  # type: ignore
    for s in PIPELINE_STAGES:
        aid = s["agent"]
        lr = last_runs.get(aid, {})
        agents.append({
            "id": aid,
            "name": s["label"],
            "stage_num": s["num"],
            "status": _agent_status.get(aid, "idle"),
            "last_run": lr.get("created_at"),
            "last_status": lr.get("status"),
            "duration_ms": lr.get("duration_ms"),
            "model": lr.get("model"),
            "has_gate": bool(s.get("gate")),
            "gate": s.get("gate"),
        })
  # Shared agents not tied to a single pipeline stage
    extra = _brain.agents.get("email_drafter") if _brain else None  # type: ignore
    if extra:
        lr = last_runs.get("email_drafter", {})
        agents.append({
            "id": "email_drafter",
            "name": extra.name,
            "stage_num": 0,
            "status": _agent_status.get("email_drafter", "idle"),
            "last_run": lr.get("created_at"),
            "last_status": lr.get("status"),
            "duration_ms": lr.get("duration_ms"),
            "model": lr.get("model"),
            "has_gate": False,
            "gate": None,
        })
    return {"agents": agents}


@app.post("/api/agents/test-all")
def test_all_agents() -> dict:
    """Run every pipeline agent with sample input to verify all are working."""
    engine = _init()
    orchestrator = engine.orchestrator
    samples = _agent_test_samples()
    results = []
    for s in PIPELINE_STAGES:
        aid = s["agent"]
        sample = samples.get(aid, "{}")
        try:
            r = orchestrator.run_agent(aid, sample, entity_type="test", entity_id="health-check")
            results.append({
                "agent": aid,
                "status": r.get("status"),
                "source": r.get("source", "llm"),
                "duration_ms": r.get("duration_ms"),
            })
            _agent_status[aid] = "idle"
        except Exception as e:
            results.append({"agent": aid, "status": "error", "error": str(e)})
    ok = sum(1 for r in results if r.get("status") == "success")
    # Test shared email_drafter agent
    try:
        r = orchestrator.run_agent("email_drafter", samples.get("email_drafter", "{}"), entity_type="test", entity_id="health-check")
        results.append({"agent": "email_drafter", "status": r.get("status"), "source": r.get("source", "llm"), "duration_ms": r.get("duration_ms")})
        ok += 1 if r.get("status") == "success" else 0
    except Exception as e:
        results.append({"agent": "email_drafter", "status": "error", "error": str(e)})
    return {"results": results, "passed": ok, "total": len(results)}


def _agent_test_samples() -> dict[str, str]:
    import json as _json
    return {
        "lead_discovery": _json.dumps({"region": "United States", "vertical": "promotional products"}),
        "company_research": _json.dumps({
            "company_name": "YMlabs Promotional Products",
            "website_text": "custom lip balm and promotional hats for distributors",
            "meta_description": "Promotional products distributor",
        }),
        "personalization": _json.dumps({
            "company_name": "YMlabs",
            "company_profile": {"products_services": ["lip balm", "hats"]},
        }),
        "outreach": _json.dumps({
            "outreach_draft": {"subject_line": "Test", "email_body": "Hello from SupplyIA"},
        }),
        "qualification": "We need 5000 custom lip balms shipped to the US.",
        "product_research": _json.dumps({"product_description": "lip balm", "quantity": 5000}),
        "supplier_discovery": _json.dumps({
            "product_spec": {"product_category": "lip balm"},
            "live_search_results": [{"factory_name": "Test Factory", "platform_source": "alibaba.com", "url": "https://alibaba.com", "unit_price_estimate_usd": 0.5}],
        }),
        "supplier_verification": _json.dumps({
            "suppliers": [{"factory_name": "Test Factory", "platform_source": "alibaba.com", "url": "https://alibaba.com", "unit_price_estimate_usd": 0.5}],
        }),
        "rfq": _json.dumps({
            "requirements": {"product_description": "lip balm", "quantity": 5000},
            "verified_suppliers": [{"factory_name": "Test Factory", "url": "https://alibaba.com"}],
        }),
        "quote_comparison": _json.dumps({
            "quotes": [{"factory": "Test Factory", "price_usd": 0.5, "price_known": True, "moq": 500}],
        }),
        "proposal": _json.dumps({
            "company_name": "YMlabs",
            "requirements": {"product_description": "lip balm", "quantity": 5000},
            "recommendation": {"recommended_supplier": "Test Factory"},
            "quotes": [{"factory": "Test Factory", "price_usd": 0.5}],
        }),
        "order_tracking": _json.dumps({"order_id": "test-order", "status": "proposal_sent"}),
        "finance": _json.dumps({"order_id": "test-order", "client_price_usd": 4000}),
        "email_drafter": _json.dumps({
            "company_name": "YMlabs",
            "email": "buyer@test.com",
            "company_profile": {"products_services": ["bags"]},
            "requirements": {"product_description": "bags", "quantity": 5000},
            "verified_suppliers": [{"factory_name": "Test Factory", "url": "https://alibaba.com"}],
        }),
    }


@app.get("/api/activity")
def activity(limit: int = 150) -> dict:
    _init()
    logs = _storage.get_activity_log(limit)  # type: ignore
    events = bus.history(limit)
    return {"logs": logs, "live_events": events}


@app.get("/api/roadmap")
def roadmap() -> dict:
    return {"phases": ROADMAP_PHASES, "crm_pages": CRM_PAGES}


@app.get("/api/roadmap/integrations")
def roadmap_integrations() -> dict:
    return {"integrations": INTEGRATIONS_NEEDED}


@app.get("/api/runs")
def list_runs() -> dict:
    _init()
    return {"runs": _storage.list_pipeline_runs(_tid()), "active_run_id": _active_run_id}  # type: ignore


@app.get("/api/runs/active")
def active_run() -> dict:
    _init()
    if not _active_run_id:
        return {"active": False}
    status = _engine.get_status(_active_run_id)  # type: ignore
    return {"active": True, "run_id": _active_run_id, **status}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    _init()
    status = _engine.get_status(run_id)  # type: ignore
    if not status:
        raise HTTPException(404, "Run not found")
    return status


@app.post("/api/runs/start")
def start_run(auto_approve: bool | None = None) -> dict:
    global _active_run_id
    engine = _init()
    if auto_approve is None:
        auto_approve = _auto_approve()
    _active_run_id = engine.start(auto_approve=auto_approve)
    bus.publish("run_started", {"run_id": _active_run_id})
    return {"run_id": _active_run_id, "status": "started"}


@app.post("/api/runs/{run_id}/approve")
def approve(run_id: str) -> dict:
    engine = _init()
    ok = engine.approve_gate(run_id)
    if not ok:
        raise HTTPException(400, "No pending gate to approve")
    return {"run_id": run_id, "status": "resumed"}


@app.get("/api/events")
async def events() -> StreamingResponse:
    async def stream():
        q = await bus.subscribe()
        try:
            for ev in bus.history(50):
                yield f"data: {json.dumps(ev)}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=20)
                    if ev.get("type") == "stage_started":
                        sid = ev.get("data", {}).get("stage", "")
                        _agent_status[sid] = "running"
                    if ev.get("type") == "stage_completed":
                        sid = ev.get("data", {}).get("stage", "")
                        _agent_status[sid] = "idle"
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping'})}\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(stream(), media_type="text/event-stream")
