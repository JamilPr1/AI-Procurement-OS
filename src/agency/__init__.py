"""Agency business layer — tenant #1, transaction revenue."""

from __future__ import annotations

from typing import Any


class Agency:
    """Our sourcing company. Uses platform core; earns margin per deal."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.tenant_id = config.get("tenant_id", "agency_primary")
        self.name = config.get("name", "Agency")
        self.margin_percent = config.get("default_margin_percent", 15)

    def apply_margin(self, factory_cost_usd: float) -> dict[str, float]:
        margin = factory_cost_usd * (self.margin_percent / 100)
        return {
            "factory_cost_usd": factory_cost_usd,
            "margin_percent": self.margin_percent,
            "margin_usd": round(margin, 2),
            "client_price_usd": round(factory_cost_usd + margin, 2),
        }

    def summary(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "margin_percent": self.margin_percent,
            "type": "agency",
        }
