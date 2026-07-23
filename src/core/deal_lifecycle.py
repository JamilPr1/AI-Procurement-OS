"""Deal lifecycle — tracking vs closed, stage constants."""

from __future__ import annotations

from typing import Any

# Pre-proposal sourcing stages (Hot Leads / Deals pages)
SOURCING_STAGES = frozenset({
    "qualification", "new", "product_research", "supplier_discovery",
    "supplier_verification", "rfq", "quote_comparison", "proposal",
})

# Post-proposal — requires human review (Tracking page)
TRACKING_STAGES = frozenset({
    "proposal_sent", "client_review", "order_tracking", "production",
    "awaiting_payment", "finance",
})

CLOSED_STAGES = frozenset({"closed"})
CLOSED_STATUSES = frozenset({"closed", "completed", "won"})


def is_tracking_deal(deal: dict[str, Any] | None) -> bool:
    if not deal:
        return False
    if deal.get("status") == "tracking":
        return True
    return deal.get("stage") in TRACKING_STAGES


def is_closed_deal(deal: dict[str, Any] | None) -> bool:
    if not deal:
        return False
    if deal.get("closed_manually"):
        return True
    return deal.get("stage") in CLOSED_STAGES or deal.get("status") in CLOSED_STATUSES


def is_sourcing_deal(deal: dict[str, Any] | None) -> bool:
    if not deal or is_closed_deal(deal) or is_tracking_deal(deal):
        return False
    return deal.get("stage") in SOURCING_STAGES or deal.get("status") == "active"


def enters_tracking(stage: str) -> bool:
    return stage in ("proposal", "proposal_sent")
