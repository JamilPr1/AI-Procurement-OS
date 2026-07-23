"""Repair store orders with incomplete buyer_requirements."""

from __future__ import annotations

import json
from typing import Any

from src.core.storage import Storage


def repair_store_orders(storage: Storage) -> dict[str, Any]:
    """Backfill buyer_requirements and tracking_entered_at for AI store orders."""
    conn = storage._connect()
    rows = conn.execute(
        """SELECT d.id, d.buyer_requirements, d.tracking_entered_at, d.updated_at,
                  l.data as lead_data
           FROM deals d
           LEFT JOIN leads l ON l.id = d.lead_id
           WHERE d.stage = 'order_tracking'"""
    ).fetchall()

    repaired = 0
    for row in rows:
        deal_id = row["id"]
        req = row["buyer_requirements"]
        if isinstance(req, str):
            try:
                req = json.loads(req)
            except json.JSONDecodeError:
                req = {}
        req = req or {}

        lead_data = {}
        if row["lead_data"]:
            try:
                lead_data = json.loads(row["lead_data"])
            except json.JSONDecodeError:
                pass

        if req.get("product_description"):
            continue

        proposal = storage.load_json_entity("proposals", deal_id) or {}
        order = storage.get_order_for_deal(deal_id)
        order_data = (order or {}).get("data") or {}
        recap = proposal.get("requirements_recap") or {}

        product = (
            req.get("product")
            or recap.get("product_description")
            or order_data.get("product")
            or lead_data.get("product_interest")
        )
        if not product:
            continue

        fixed = {
            **req,
            "product_description": product,
            "product": product,
            "quantity": req.get("quantity") or recap.get("quantity") or order_data.get("quantity"),
            "delivery_date": req.get("delivery_date") or recap.get("delivery_date"),
            "source": req.get("source") or order_data.get("source") or "product_finder_store",
        }
        storage.update_deal(
            deal_id,
            buyer_requirements=fixed,
            tracking_entered_at=row["tracking_entered_at"] or row["updated_at"],
        )
        repaired += 1

    return {"repaired": repaired}
