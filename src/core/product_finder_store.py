"""AI Product Finder Store — conversational intake, quote, and order placement."""

from __future__ import annotations

import re
from typing import Any

from src.agency import Agency
from src.core.draft_composer import compose_proposal_document
from src.core.storage import Storage, _utc_now
from src.tools.supplier_finder import SupplierFinder


QTY_RE = re.compile(r"\b(\d{1,6})\b")
PRODUCT_HINTS = re.compile(
    r"(?:need|want|looking for|order|buy|get)\s+(?:\d+\s+)?(.+?)(?:\.|$)",
    re.I,
)

WIZARD_STEPS: list[dict[str, Any]] = [
    {
        "id": "product",
        "question": "What product do you need?",
        "placeholder": "e.g. custom ceramic mugs with logo",
        "type": "text",
    },
    {
        "id": "quantity",
        "question": "How many units?",
        "placeholder": "e.g. 500",
        "type": "number",
    },
    {
        "id": "budget",
        "question": "What's your total budget (USD)?",
        "placeholder": "e.g. 5000",
        "type": "number",
    },
    {
        "id": "material",
        "question": "Preferred material?",
        "placeholder": "e.g. ceramic, stainless steel, cotton",
        "type": "text",
    },
    {
        "id": "color",
        "question": "Color or finish?",
        "placeholder": "e.g. matte black, white with blue logo",
        "type": "text",
    },
    {
        "id": "logo",
        "question": "Logo or artwork details?",
        "placeholder": "e.g. 2-color screen print, vector file ready",
        "type": "text",
    },
    {
        "id": "delivery_date",
        "question": "When do you need delivery?",
        "placeholder": "e.g. March 15, 2026 or 6 weeks",
        "type": "text",
    },
    {
        "id": "company_name",
        "question": "Company or organization name?",
        "placeholder": "e.g. Acme Events Co.",
        "type": "text",
    },
    {
        "id": "contact_email",
        "question": "Email for your quote and order updates?",
        "placeholder": "you@company.com",
        "type": "email",
    },
]


def parse_product_query(query: str) -> dict[str, Any]:
    """Extract quantity and product hints from free-text like 'I need 500 custom mugs'."""
    text = (query or "").strip()
    hints: dict[str, Any] = {"product_query": text}
    if not text:
        return hints

    qty_match = QTY_RE.search(text)
    if qty_match:
        hints["quantity"] = int(qty_match.group(1))

    product_match = PRODUCT_HINTS.search(text)
    if product_match:
        hints["product"] = product_match.group(1).strip().rstrip(".")
    else:
        cleaned = re.sub(r"^(i\s+)?(need|want|looking for)\s+", "", text, flags=re.I)
        cleaned = re.sub(r"^\d+\s+", "", cleaned).strip()
        if cleaned:
            hints["product"] = cleaned

    return hints


def _next_step(answers: dict[str, Any]) -> dict[str, Any] | None:
    for step in WIZARD_STEPS:
        if not answers.get(step["id"]):
            return step
    return None


def _margin_for_tenant(tenant: dict[str, Any], agency: Agency) -> float:
    return float(tenant.get("margin_percent") or agency.margin_percent)


def _estimate_unit_price(product: str, material: str) -> float:
    p = f"{product} {material}".lower()
    if any(x in p for x in ("mug", "cup", "drinkware")):
        return 4.5
    if any(x in p for x in ("t-shirt", "shirt", "apparel", "hoodie")):
        return 8.0
    if any(x in p for x in ("bag", "tote")):
        return 6.0
    if any(x in p for x in ("pen", "notebook", "stationery")):
        return 1.2
    return 5.0


class ProductFinderStore:
    def __init__(
        self,
        storage: Storage,
        agency: Agency,
        brain_config: dict[str, Any],
        tenant_service: Any,
    ) -> None:
        self.storage = storage
        self.agency = agency
        self.brain_config = brain_config
        self.tenant_service = tenant_service
        self.supplier_finder = SupplierFinder(brain_config)

    def start_session(self, tenant_slug: str, query: str = "") -> dict[str, Any]:
        tenant = self.tenant_service.resolve_slug(tenant_slug)
        if not tenant:
            raise ValueError("Store not found for this tenant")
        hints = parse_product_query(query)
        session_id = self.storage.create_store_session(tenant["id"], query)
        answers = {k: v for k, v in hints.items() if k not in ("product_query",) and v}
        if hints.get("product"):
            answers["product"] = hints["product"]
        self.storage.update_store_session(session_id, answers=answers, product_query=query)
        return self.session_view(session_id, tenant)

    def answer(self, session_id: str, field: str, value: Any) -> dict[str, Any]:
        session = self.storage.get_store_session(session_id)
        if not session:
            raise ValueError("Session not found")
        answers = dict(session.get("answers") or {})
        answers[field] = value
        status = session.get("status", "intake")
        if not _next_step(answers):
            status = "ready_to_quote"
        self.storage.update_store_session(session_id, answers=answers, status=status)
        tenant = self.storage.get_tenant_by_id(session["tenant_id"])
        return self.session_view(session_id, tenant)

    def session_view(self, session_id: str, tenant: dict[str, Any] | None = None) -> dict[str, Any]:
        session = self.storage.get_store_session(session_id)
        if not session:
            raise ValueError("Session not found")
        if not tenant:
            tenant = self.storage.get_tenant_by_id(session["tenant_id"])
        answers = session.get("answers") or {}
        step = _next_step(answers)
        return {
            "session_id": session_id,
            "status": session.get("status"),
            "tenant": {
                "name": tenant.get("name") if tenant else "",
                "slug": tenant.get("slug") if tenant else "",
                "tagline": tenant.get("tagline") if tenant else "",
                "branding": (tenant or {}).get("branding") or {},
            },
            "product_query": session.get("product_query"),
            "answers": answers,
            "next_step": step,
            "quote": session.get("quote"),
            "deal_id": session.get("deal_id"),
            "order_id": session.get("order_id"),
            "portal_url": f"/portal/{session['deal_id']}" if session.get("deal_id") else None,
        }

    def generate_quote(self, session_id: str) -> dict[str, Any]:
        session = self.storage.get_store_session(session_id)
        if not session:
            raise ValueError("Session not found")
        answers = session.get("answers") or {}
        if _next_step(answers):
            raise ValueError("Please complete all questions first")

        tenant = self.storage.get_tenant_by_id(session["tenant_id"]) or {}
        margin_pct = _margin_for_tenant(tenant, self.agency)
        product = str(answers.get("product", "custom product"))
        quantity = int(answers.get("quantity") or 500)
        material = str(answers.get("material", ""))
        budget = float(answers.get("budget") or 0)

        suppliers = self.supplier_finder.discover(product, max_suppliers=3)
        best = suppliers[0] if suppliers else None
        unit = float(best.get("unit_price_estimate_usd") or 0) if best else 0
        if not unit:
            unit = _estimate_unit_price(product, material)
        factory_cost = round(unit * quantity, 2)
        margin_usd = round(factory_cost * (margin_pct / 100), 2)
        client_price = round(factory_cost + margin_usd, 2)

        if budget and client_price > budget * 1.15:
            scale = budget / client_price
            client_price = round(budget, 2)
            factory_cost = round(client_price / (1 + margin_pct / 100), 2)
            margin_usd = round(client_price - factory_cost, 2)

        spec = {
            "product_category": product,
            "materials": material,
            "color": answers.get("color"),
            "logo": answers.get("logo"),
            "delivery_date": answers.get("delivery_date"),
        }
        requirements = {
            "product_description": product,
            "quantity": quantity,
            "budget_usd": budget,
            "material": material,
            "color": answers.get("color"),
            "logo": answers.get("logo"),
            "delivery_date": answers.get("delivery_date"),
        }
        recommendation = {"recommended_supplier": (best or {}).get("factory_name", "Vetted manufacturing partner")}
        quotes = [
            {
                "supplier": s.get("factory_name"),
                "unit_price_usd": s.get("unit_price_estimate_usd"),
                "moq": s.get("moq"),
                "lead_time_days": s.get("lead_time_days"),
                "url": s.get("url"),
            }
            for s in suppliers
        ]

        proposal = compose_proposal_document(
            {"company_name": answers.get("company_name", "Store Customer")},
            requirements,
            recommendation,
            quotes,
            client_price_usd=client_price,
            product_spec=spec,
            factory_cost_usd=factory_cost,
            margin_usd=margin_usd,
            margin_percent=margin_pct,
        )

        quote = {
            "product": product,
            "quantity": quantity,
            "unit_price_usd": round(client_price / quantity, 2) if quantity else 0,
            "factory_cost_usd": factory_cost,
            "margin_usd": margin_usd,
            "margin_percent": margin_pct,
            "client_price_usd": client_price,
            "supplier": recommendation["recommended_supplier"],
            "suppliers": quotes,
            "timeline": answers.get("delivery_date", "8–10 weeks from PO"),
            "proposal_summary": proposal.get("executive_summary"),
        }

        self.storage.update_store_session(
            session_id,
            status="quoted",
            spec=spec,
            quote=quote,
        )
        return self.session_view(session_id, tenant)

    def place_order(self, session_id: str) -> dict[str, Any]:
        session = self.storage.get_store_session(session_id)
        if not session:
            raise ValueError("Session not found")
        if session.get("order_id"):
            return self.session_view(session_id)

        quote = session.get("quote")
        if not quote:
            raise ValueError("Generate a quote first")

        tenant_id = session["tenant_id"]
        ok, msg = self.tenant_service.can_create_deal(tenant_id)
        if not ok:
            raise ValueError(msg)

        answers = session.get("answers") or {}
        company = str(answers.get("company_name") or "Store Customer")
        email = str(answers.get("contact_email") or "")

        lead_data = {
            "company_name": company,
            "source": "product_finder_store",
            "contact_email": email,
            "product_interest": quote.get("product"),
            "quantity": quote.get("quantity"),
            "store_session_id": session_id,
            "notes": f"AI Store order — {quote.get('product')} x {quote.get('quantity')}",
        }
        lead_id = self.storage.create_lead(tenant_id, company, lead_data)
        deal_id = self.storage.create_deal(tenant_id, lead_id, stage="order_tracking")
        requirements = {
            "product_description": quote.get("product"),
            "product": quote.get("product"),
            "quantity": quote.get("quantity"),
            "delivery_date": answers.get("delivery_date"),
            "contact_email": email,
            "budget_usd": answers.get("budget"),
            "material": answers.get("material"),
            "color": answers.get("color"),
            "logo": answers.get("logo"),
            "source": "product_finder_store",
        }
        self.storage.update_deal(
            deal_id,
            status="tracking",
            buyer_requirements=requirements,
            tracking_entered_at=_utc_now(),
        )

        proposal = compose_proposal_document(
            lead_data,
            {
                "product_description": quote.get("product"),
                "quantity": quote.get("quantity"),
                "delivery_date": answers.get("delivery_date"),
            },
            {"recommended_supplier": quote.get("supplier")},
            quote.get("suppliers") or [],
            client_price_usd=quote.get("client_price_usd", 0),
            product_spec=session.get("spec") or {},
            factory_cost_usd=quote.get("factory_cost_usd"),
            margin_usd=quote.get("margin_usd"),
            margin_percent=quote.get("margin_percent"),
        )
        proposal["status"] = "accepted"
        self.storage.save_json_entity("proposals", deal_id, proposal)

        order_data = {
            "deal_id": deal_id,
            "lead_id": lead_id,
            "product": quote.get("product"),
            "quantity": quote.get("quantity"),
            "client_price_usd": quote.get("client_price_usd"),
            "factory_cost_usd": quote.get("factory_cost_usd"),
            "status": "confirmed",
            "source": "product_finder_store",
            "customer_email": email,
            "deposit_percent": 30,
            "deposit_due_usd": round(float(quote.get("client_price_usd", 0)) * 0.3, 2),
        }
        order_id = self.storage.create_order(tenant_id, deal_id, order_data)

        self.storage.update_store_session(
            session_id,
            status="ordered",
            deal_id=deal_id,
            order_id=order_id,
            customer_email=email,
        )
        tenant = self.storage.get_tenant_by_id(tenant_id)
        return self.session_view(session_id, tenant)
