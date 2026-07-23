"""Demo data seeding for SaaS tenants, store orders, and credentials."""

from __future__ import annotations

from typing import Any

from src.core.draft_composer import compose_proposal_document
from src.core.storage import Storage
from src.saas.tenant_service import TenantService
from src.saas.store_catalog import get_store_profile


def _tenant_store_meta(slug: str | None) -> dict[str, Any]:
    profile = get_store_profile(slug or "")
    products = profile.get("featured_products") or []
    return {
        "tagline": profile.get("hero_title") or "",
        "specialties": profile.get("specialties") or [],
        "featured_products": [p.get("name", "") for p in products],
    }


PLATFORM_ADMIN = {
    "email": "admin@aiprocurement.local",
    "password": "Admin2026!",
    "name": "Platform Super Admin",
    "role": "superadmin",
}

DEMO_TENANTS: list[dict[str, Any]] = [
    {
        "id": "tenant_demo",
        "name": "Demo Store",
        "slug": "demo",
        "plan": "growth",
        "margin_percent": 18,
        "tagline": "Try our AI Product Finder — custom sourcing in minutes",
        "branding": {"primary_color": "#8b5cf6", "accent_color": "#6d28d9", "logo_text": "DS"},
        "admin_email": "demo@store.local",
        "admin_password": "Demo2026!",
        "admin_name": "Demo Store Admin",
    },
    {
        "id": "tenant_promo_pros",
        "name": "Promo Pros Inc",
        "slug": "promo-pros",
        "plan": "growth",
        "margin_percent": 17,
        "tagline": "Promotional products sourced by AI — mugs, apparel, bags & more",
        "branding": {"primary_color": "#2563eb", "accent_color": "#1d4ed8", "logo_text": "PP"},
        "admin_email": "ops@promopros.demo",
        "admin_password": "Promo2026!",
        "admin_name": "Sarah Chen",
    },
    {
        "id": "tenant_gift_hub",
        "name": "Gift Hub Agency",
        "slug": "gift-hub",
        "plan": "starter",
        "margin_percent": 15,
        "tagline": "Corporate gifts and branded merchandise — quoted in minutes",
        "branding": {"primary_color": "#059669", "accent_color": "#047857", "logo_text": "GH"},
        "admin_email": "ops@gifthub.demo",
        "admin_password": "Gift2026!",
        "admin_name": "Mike Rivera",
    },
    {
        "id": "tenant_merch_direct",
        "name": "Merch Direct Co",
        "slug": "merch-direct",
        "plan": "growth",
        "margin_percent": 20,
        "tagline": "Direct-to-factory custom merch for events and teams",
        "branding": {"primary_color": "#dc2626", "accent_color": "#b91c1c", "logo_text": "MD"},
        "admin_email": "ops@merchdirect.demo",
        "admin_password": "Merch2026!",
        "admin_name": "Lisa Park",
    },
    {
        "id": "tenant_event_swag",
        "name": "Event Swag Solutions",
        "slug": "event-swag",
        "plan": "starter",
        "margin_percent": 16,
        "tagline": "Conference swag, trade show giveaways, and bulk event merchandise",
        "branding": {"primary_color": "#d97706", "accent_color": "#c2410c", "logo_text": "ES"},
        "admin_email": "ops@eventswag.demo",
        "admin_password": "Event2026!",
        "admin_name": "James Wilson",
    },
]

DEMO_STORE_ORDERS: list[dict[str, Any]] = [
    {
        "tenant_slug": "demo",
        "company_name": "Summit Events LLC",
        "contact_email": "procurement@summitevents.demo",
        "product": "custom ceramic mugs with 2-color logo",
        "quantity": 500,
        "unit_price": 5.2,
        "delivery_date": "8 weeks",
    },
    {
        "tenant_slug": "promo-pros",
        "company_name": "Brand My Beverage",
        "contact_email": "orders@brandmybeverage.demo",
        "product": "insulated tumblers 20oz",
        "quantity": 1000,
        "unit_price": 8.75,
        "delivery_date": "6 weeks",
    },
    {
        "tenant_slug": "gift-hub",
        "company_name": "Northstar Healthcare",
        "contact_email": "gifts@northstar.demo",
        "product": "embroidered polo shirts",
        "quantity": 250,
        "unit_price": 14.5,
        "delivery_date": "10 weeks",
    },
    {
        "tenant_slug": "merch-direct",
        "company_name": "BuildRight Construction",
        "contact_email": "safety@buildright.demo",
        "product": "hi-vis safety vests with logo",
        "quantity": 800,
        "unit_price": 6.25,
        "delivery_date": "5 weeks",
    },
    {
        "tenant_slug": "event-swag",
        "company_name": "TechConf 2026",
        "contact_email": "swag@techconf.demo",
        "product": "branded tote bags",
        "quantity": 2000,
        "unit_price": 3.8,
        "delivery_date": "4 weeks",
    },
]


def seed_demo_data(
    storage: Storage,
    tenant_service: TenantService,
    agency_config: dict[str, Any],
    *,
    force_orders: bool = False,
) -> dict[str, Any]:
    """Seed demo tenants, users, and sample store orders."""
    tenant_service.bootstrap()

    agency_id = agency_config.get("tenant_id", "agency_primary")
    storage.upsert_tenant_user(
        agency_id,
        PLATFORM_ADMIN["email"],
        PLATFORM_ADMIN["password"],
        role=PLATFORM_ADMIN["role"],
        name=PLATFORM_ADMIN["name"],
    )

    tenants_created = 0
    users_created = 0
    for t in DEMO_TENANTS:
        existing = storage.get_tenant_by_slug(t["slug"])
        if not existing:
            tenants_created += 1
        storage.upsert_tenant(t["id"], t["name"], tenant_type="saas")
        storage.upsert_tenant_settings(
            t["id"],
            t["slug"],
            plan=t["plan"],
            margin_percent=t["margin_percent"],
            store_enabled=True,
            tagline=t["tagline"],
            branding=t["branding"],
        )
        storage.upsert_tenant_user(
            t["id"],
            t["admin_email"],
            t["admin_password"],
            role="admin",
            name=t["admin_name"],
        )
        users_created += 1

    orders_created = 0
    for order in DEMO_STORE_ORDERS:
        tenant = storage.get_tenant_by_slug(order["tenant_slug"])
        if not tenant:
            continue
        tenant_id = tenant["id"]
        if not force_orders:
            existing = storage.list_leads(tenant_id, limit=200)
            if any(
                (l.get("data") or {}).get("source") == "product_finder_store"
                and l.get("company_name") == order["company_name"]
                for l in existing
            ):
                continue

        margin_pct = float(tenant.get("margin_percent") or 15)
        qty = int(order["quantity"])
        unit = float(order["unit_price"])
        factory_cost = round(unit * qty, 2)
        margin_usd = round(factory_cost * (margin_pct / 100), 2)
        client_price = round(factory_cost + margin_usd, 2)

        lead_data = {
            "company_name": order["company_name"],
            "source": "product_finder_store",
            "contact_email": order["contact_email"],
            "product_interest": order["product"],
            "quantity": qty,
            "notes": f"Demo store order — {order['product']}",
        }
        lead_id = storage.create_lead(tenant_id, order["company_name"], lead_data)
        deal_id = storage.create_deal(tenant_id, lead_id, stage="order_tracking")
        storage.update_deal(deal_id, status="tracking", buyer_requirements={
            "product_description": order["product"],
            "quantity": qty,
            "delivery_date": order["delivery_date"],
            "contact_email": order["contact_email"],
        })

        proposal = compose_proposal_document(
            lead_data,
            {
                "product_description": order["product"],
                "quantity": qty,
                "delivery_date": order["delivery_date"],
            },
            {"recommended_supplier": "Vetted manufacturing partner (demo)"},
            [],
            client_price_usd=client_price,
            product_spec={"product_category": order["product"]},
            factory_cost_usd=factory_cost,
            margin_usd=margin_usd,
            margin_percent=margin_pct,
        )
        proposal["status"] = "accepted"
        storage.save_json_entity("proposals", deal_id, proposal)

        storage.create_order(tenant_id, deal_id, {
            "deal_id": deal_id,
            "lead_id": lead_id,
            "product": order["product"],
            "quantity": qty,
            "client_price_usd": client_price,
            "factory_cost_usd": factory_cost,
            "status": "confirmed",
            "source": "product_finder_store",
            "customer_email": order["contact_email"],
            "deposit_percent": 30,
            "deposit_due_usd": round(client_price * 0.3, 2),
        })
        orders_created += 1

    return {
        "tenants_seeded": len(DEMO_TENANTS) + 1,
        "tenants_created": tenants_created,
        "users_seeded": users_created + 1,
        "orders_created": orders_created,
        "platform_admin": PLATFORM_ADMIN["email"],
    }


def collect_credentials(
    storage: Storage,
    agency_config: dict[str, Any],
    brain_config: dict[str, Any],
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> dict[str, Any]:
    """Gather all platform credentials for documentation."""
    import os

    from src.core.platform_urls import get_public_base_url

    base = get_public_base_url(brain_config)
    if base.startswith("http://127.0.0.1") or base.startswith("http://localhost"):
        base = f"http://{host}:{port}"
    tenants = storage.list_tenants()
    users = storage.list_tenant_users()

    return {
        "platform": {
            "name": brain_config.get("project", {}).get("name", "AI Procurement OS"),
            "version": brain_config.get("project", {}).get("version", "0.2.0"),
            "landing_url": base,
            "dashboard_url": f"{base}/app",
            "crm_login_url": f"{base}/login",
            "marketing_url": f"{base}/marketing",
            "database": str(brain_config.get("paths", {}).get("database", "data/platform.db")),
        },
        "platform_admin": PLATFORM_ADMIN,
        "agency": {
            "name": agency_config.get("name"),
            "tenant_id": agency_config.get("tenant_id"),
            "slug": agency_config.get("slug", "default"),
            "store_url": f"{base}/store?tenant={agency_config.get('slug', 'default')}",
            "margin_percent": agency_config.get("default_margin_percent", 15),
        },
        "tenants": [
            {
                "name": t.get("name"),
                "slug": t.get("slug"),
                "plan": t.get("plan"),
                "margin_percent": t.get("margin_percent"),
                "store_url": f"{base}/store?tenant={t.get('slug')}",
                "crm_note": "Use tenant admin login below to manage this store",
                **_tenant_store_meta(t.get("slug")),
            }
            for t in tenants
            if t.get("slug") and t.get("type") != "agency"
        ],
        "tenant_users": [
            {
                "tenant": u.get("tenant_name"),
                "slug": u.get("tenant_slug"),
                "name": u.get("name"),
                "email": u.get("email"),
                "password": u.get("password"),
                "role": u.get("role"),
            }
            for u in users
        ],
        "llm": {
            "provider": brain_config.get("llm", {}).get("provider"),
            "base_url": brain_config.get("llm", {}).get("base_url"),
            "model": brain_config.get("llm", {}).get("model"),
            "openai_api_key": "SET" if os.getenv("OPENAI_API_KEY") else "(not set — using Ollama)",
        },
        "email": {
            "smtp_host": os.getenv("SMTP_HOST") or "(not set — dry-run mode)",
            "smtp_port": os.getenv("SMTP_PORT", "587"),
            "smtp_user": os.getenv("SMTP_USER") or "(not set)",
            "smtp_pass": os.getenv("SMTP_PASS") or "(not set)",
            "smtp_from": os.getenv("SMTP_FROM") or "(not set)",
            "dry_run": os.getenv("EMAIL_DRY_RUN", "true"),
        },
        "api_endpoints": {
            "health": f"{base}/api/health",
            "store_tenant": f"{base}/api/store/tenant/{{slug}}",
            "store_sessions": f"{base}/api/store/sessions",
            "saas_tenants": f"{base}/api/saas/tenants",
            "seed_demo": f"{base}/api/admin/seed-demo",
        },
        "notes": [
            "Landing page: http://127.0.0.1:8765/",
            "CRM (login required): http://127.0.0.1:8765/app",
            "Super admin: admin@aiprocurement.local / Admin2026!",
            "Demo tenant: demo@store.local / Demo2026!",
            "Restart dashboard after code updates: python -m src.main dashboard",
            "Seed demo data: python -m src.main seed-demo",
            "Generate this doc: python -m src.main credentials",
            "All demo passwords are for local development only.",
        ],
    }
