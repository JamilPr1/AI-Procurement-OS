"""SaaS layer — multi-tenant platform."""

from __future__ import annotations

from typing import Any

from src.saas.tenant_service import TenantService

__all__ = ["SaaSPlatform", "TenantService"]


class SaaSPlatform:
    def __init__(self, config: dict[str, Any], storage=None, agency_config: dict | None = None) -> None:
        self.config = config
        self.enabled = config.get("enabled", False)
        self.plans = config.get("plans", {})
        self._tenant_service: TenantService | None = None
        if storage is not None:
            self._tenant_service = TenantService(storage, config, agency_config or {})

    @property
    def tenants(self) -> TenantService | None:
        return self._tenant_service

    def bind(self, storage, agency_config: dict) -> TenantService:
        self._tenant_service = TenantService(storage, self.config, agency_config)
        return self._tenant_service

    def summary(self) -> dict[str, Any]:
        base = {
            "enabled": self.enabled,
            "plans": self.plans,
            "status": "active" if self.enabled else "ready",
        }
        if self._tenant_service:
            base.update(self._tenant_service.summary())
        else:
            base["tenant_count"] = 0
        return base
