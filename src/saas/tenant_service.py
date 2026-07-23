"""SaaS multi-tenant provisioning and plan enforcement."""

from __future__ import annotations

import re
import uuid
from typing import Any

from src.core.storage import Storage
from src.saas.store_catalog import get_store_profile


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:48] or "tenant"


class TenantService:
    def __init__(self, storage: Storage, saas_config: dict[str, Any], agency_config: dict[str, Any]) -> None:
        self.storage = storage
        self.config = saas_config
        self.plans = saas_config.get("plans", {})
        self.enabled = saas_config.get("enabled", False)
        self.agency_config = agency_config

    def bootstrap(self) -> None:
        """Ensure primary agency and demo store tenants exist."""
        agency_id = self.agency_config.get("tenant_id", "agency_primary")
        agency_name = self.agency_config.get("name", "Agency")
        agency_slug = self.agency_config.get("slug", "default")
        margin = float(self.agency_config.get("default_margin_percent", 15))

        self.storage.upsert_tenant(agency_id, agency_name, tenant_type="agency")
        self.storage.upsert_tenant_settings(
            agency_id,
            agency_slug,
            plan=self.config.get("default_plan", "starter"),
            margin_percent=margin,
            store_enabled=True,
            tagline="AI-powered sourcing for promotional products",
            branding={"primary_color": "#3b82f6", "logo_text": agency_name[:2].upper()},
        )

        demo_id = "tenant_demo"
        self.storage.upsert_tenant(demo_id, "Demo Store", tenant_type="saas")
        self.storage.upsert_tenant_settings(
            demo_id,
            "demo",
            plan="growth",
            margin_percent=18,
            store_enabled=True,
            tagline="Try our AI Product Finder — custom sourcing in minutes",
            branding={"primary_color": "#8b5cf6", "logo_text": "DS"},
        )

    def list_tenants(self) -> list[dict[str, Any]]:
        tenants = self.storage.list_tenants()
        for t in tenants:
            t["plan_limits"] = self.plan_limits(t.get("plan") or "starter")
            t["store_url"] = self.store_url(t.get("slug") or "")
            profile = get_store_profile(t.get("slug") or "")
            t["store_specialties"] = profile.get("specialties") or []
        return tenants

    def plan_limits(self, plan: str) -> dict[str, Any]:
        return dict(self.plans.get(plan, self.plans.get("starter", {})))

    def store_url(self, slug: str, base: str = "") -> str:
        if not slug:
            return ""
        path = f"/store?tenant={slug}"
        return f"{base}{path}" if base else path

    def resolve_slug(self, slug: str) -> dict[str, Any] | None:
        tenant = self.storage.get_tenant_by_slug(slug)
        if not tenant:
            return None
        if not tenant.get("store_enabled", True):
            return None
        tenant["plan_limits"] = self.plan_limits(tenant.get("plan") or "starter")
        return tenant

    def can_create_deal(self, tenant_id: str) -> tuple[bool, str]:
        tenant = self.storage.get_tenant_by_id(tenant_id)
        if not tenant:
            return False, "Tenant not found"
        limits = self.plan_limits(tenant.get("plan") or "starter")
        max_deals = int(limits.get("max_active_deals", 999))
        active = self.storage.count_active_deals(tenant_id)
        if active >= max_deals:
            return False, f"Plan limit reached ({max_deals} active deals). Upgrade to continue."
        return True, ""

    def create_tenant(
        self,
        name: str,
        *,
        slug: str | None = None,
        plan: str | None = None,
        margin_percent: float = 15.0,
        tagline: str = "",
    ) -> dict[str, Any]:
        slug = slugify(slug or name)
        if self.storage.get_tenant_by_slug(slug):
            raise ValueError(f"Slug '{slug}' is already taken")
        tenant_id = f"tenant_{uuid.uuid4().hex[:12]}"
        plan = plan or self.config.get("default_plan", "starter")
        self.storage.upsert_tenant(tenant_id, name, tenant_type="saas")
        self.storage.upsert_tenant_settings(
            tenant_id,
            slug,
            plan=plan,
            margin_percent=margin_percent,
            store_enabled=True,
            tagline=tagline or f"{name} — AI Product Finder Store",
            branding={"primary_color": "#0ea5e9", "logo_text": name[:2].upper()},
        )
        return self.storage.get_tenant_by_id(tenant_id) or {}

    def update_tenant(
        self,
        tenant_id: str,
        *,
        name: str | None = None,
        plan: str | None = None,
        margin_percent: float | None = None,
        store_enabled: bool | None = None,
        tagline: str | None = None,
    ) -> dict[str, Any] | None:
        tenant = self.storage.get_tenant_by_id(tenant_id)
        if not tenant:
            return None
        if name:
            self.storage.upsert_tenant(tenant_id, name, tenant_type=tenant.get("type", "saas"))
        slug = tenant.get("slug") or slugify(name or tenant.get("name", "tenant"))
        self.storage.upsert_tenant_settings(
            tenant_id,
            slug,
            plan=plan or tenant.get("plan") or "starter",
            margin_percent=margin_percent if margin_percent is not None else float(tenant.get("margin_percent") or 15),
            store_enabled=store_enabled if store_enabled is not None else bool(tenant.get("store_enabled", True)),
            tagline=tagline if tagline is not None else tenant.get("tagline"),
            branding=tenant.get("branding") or {},
        )
        return self.storage.get_tenant_by_id(tenant_id)

    def summary(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "plans": self.plans,
            "tenant_count": len(self.storage.list_tenants()),
            "status": "active" if self.enabled else "ready",
        }
