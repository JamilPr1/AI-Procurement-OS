"""Human review gates — draft, approve, send, advance one step at a time."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from src.core.email import EmailService
from src.core.pipeline_stages import GATE_LABELS, stage_by_id


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_proposal_email(proposal: dict, company_name: str = "Client", lead: dict | None = None) -> str:
    """Plain-text proposal email body (full version with selling structure)."""
    from src.core.draft_composer import compose_proposal_client_email

    lead_data = lead or {"company_name": company_name, "email": ""}
    return compose_proposal_client_email(proposal, lead_data).get("body", "")


class ReviewWorkflow:
    def __init__(self, storage: Any, email: EmailService | None = None) -> None:
        self.storage = storage
        self.email = email or EmailService()

    def save_pending(
        self,
        *,
        gate: str,
        stage: str,
        draft: dict,
        lead_id: str | None = None,
        deal_id: str | None = None,
    ) -> dict:
        entity_id = deal_id or lead_id
        if not entity_id:
            raise ValueError("lead_id or deal_id required")
        record = {
            "gate": gate,
            "stage": stage,
            "gate_label": GATE_LABELS.get(gate, gate),
            "draft": draft,
            "lead_id": lead_id,
            "deal_id": deal_id,
            "status": "pending",
            "created_at": _utc_now(),
        }
        self.storage.save_json_entity("reviews", entity_id, record)
        return record

    def get_pending(self, *, lead_id: str | None = None, deal_id: str | None = None) -> dict | None:
        if deal_id:
            rec = self.storage.load_json_entity("reviews", deal_id)
            if rec and rec.get("status") == "pending":
                return rec
        if lead_id:
            rec = self.storage.load_json_entity("reviews", lead_id)
            if rec and rec.get("status") == "pending":
                return rec
        return None

    def clear_pending(self, entity_id: str) -> None:
        self.storage.save_json_entity("reviews", entity_id, {"status": "cleared", "cleared_at": _utc_now()})

    def approve_and_send(self, entity_id: str) -> dict[str, Any]:
        record = self.storage.load_json_entity("reviews", entity_id)
        if not record or record.get("status") != "pending":
            raise ValueError("No pending review for this item")

        gate = record["gate"]
        stage = record["stage"]
        draft = record.get("draft") or {}
        lead_id = record.get("lead_id")
        deal_id = record.get("deal_id")
        send_result: dict[str, Any] | None = None

        if gate == "outreach_first_batch":
            outreach = draft.get("draft") or draft
            to = outreach.get("to") or ""
            if not to and self.email.dry_run:
                to = "dry-run@example.com"
            if not to:
                raise ValueError("Lead has no email address — add one on the lead before sending outreach")
            send_result = self.email.send(
                to,
                outreach.get("subject", "Partnership opportunity"),
                outreach.get("body", ""),
                html_body=outreach.get("html_body"),
                html=bool(outreach.get("html_body")),
            )
            if send_result.get("status") == "dry_run":
                send_result["demo"] = True
            outreach["status"] = "sent"
            outreach["sent_at"] = _utc_now()
            outreach["send_result"] = send_result
            if lead_id:
                self.storage.save_json_entity("outreach", lead_id, outreach)

        elif gate == "supplier_final_approval":
            if deal_id:
                self.storage.save_json_entity("supplier_approvals", deal_id, {
                    "approved": True,
                    "suppliers": draft.get("suppliers") or draft.get("draft", {}).get("suppliers", []),
                    "approved_at": _utc_now(),
                })

        elif gate == "rfq_send":
            rfq_data = draft.get("draft") or draft
            body = rfq_data.get("rfq_body", "")
            suppliers = rfq_data.get("suppliers") or []
            rfq_id = draft.get("rfq_id")
            agency_email = self.email.from_email or "sourcing@agency.local"
            for sup in suppliers[:3]:
                to = sup.get("contact_email") or agency_email
                subject = rfq_data.get("subject") or f"RFQ: {draft.get('product', 'Quote request')}"
                send_result = self.email.send(to, subject, body)
            if rfq_id:
                self._update_rfq_status(rfq_id, "sent", send_result)

        elif gate == "proposal_send":
            email_draft = draft.get("draft") or draft
            to = email_draft.get("to") or ""
            if not to and self.email.dry_run:
                to = "dry-run@example.com"
            if not to:
                raise ValueError("Lead has no email address — add one before sending the proposal")
            send_result = self.email.send(
                to,
                email_draft.get("subject", "Your sourcing proposal"),
                email_draft.get("body", ""),
                html_body=email_draft.get("html_body"),
                html=bool(email_draft.get("html_body")),
            )
            if send_result.get("status") == "dry_run":
                send_result["demo"] = True
            if deal_id:
                proposal = email_draft.get("proposal") or self.storage.load_json_entity("proposals", deal_id) or {}
                proposal["status"] = "sent"
                proposal["sent_at"] = _utc_now()
                proposal["send_result"] = send_result
                self.storage.save_json_entity("proposals", deal_id, proposal)

        elif gate in ("contract_sign", "payment_over_threshold"):
            send_result = {"status": "auto_approved", "gate": gate}

        record["status"] = "approved"
        record["approved_at"] = _utc_now()
        record["send_result"] = send_result
        self.storage.save_json_entity("reviews", entity_id, record)

        return {
            "gate": gate,
            "stage": stage,
            "send_result": send_result,
            "lead_id": lead_id,
            "deal_id": deal_id,
        }

    def _update_rfq_status(self, rfq_id: str, status: str, send_result: dict | None) -> None:
        conn = self.storage._connect()
        now = _utc_now()
        row = conn.execute("SELECT data FROM rfqs WHERE id = ?", (rfq_id,)).fetchone()
        if row:
            data = json.loads(row["data"]) if row["data"] else {}
            data["send_result"] = send_result
            data["sent_at"] = now
            conn.execute(
                "UPDATE rfqs SET status = ?, data = ?, updated_at = ? WHERE id = ?",
                (status, json.dumps(data), now, rfq_id),
            )
            conn.commit()
            self.storage.save_json_entity("rfqs", rfq_id, data)


def extract_draft_for_stage(stage: str, ctx: dict) -> dict[str, Any]:
    """Build review payload after a pipeline stage runs."""
    lead = ctx.get("top_lead") or {}
    if stage == "personalization":
        return {"type": "personalization", "draft": ctx.get("personalization") or {}}
    if stage == "outreach":
        return {"type": "outreach", "draft": ctx.get("outreach") or {}}
    if stage == "supplier_verification":
        return {"type": "suppliers", "suppliers": ctx.get("verified_suppliers") or []}
    if stage == "rfq":
        req = ctx.get("requirements") or {}
        rfq = ctx.get("rfq") or {}
        return {
            "type": "rfq",
            "draft": rfq,
            "rfq_id": ctx.get("rfq_id"),
            "product": req.get("product_description", "products"),
        }
    if stage == "proposal":
        from src.core.draft_composer import compose_proposal_client_email

        proposal = ctx.get("proposal") or {}
        client_email = compose_proposal_client_email(proposal, lead)
        return {
            "type": "proposal",
            "draft": {
                "to": client_email.get("to") or lead.get("email"),
                "subject": client_email.get("subject", proposal.get("title", "Your sourcing proposal")),
                "body": client_email.get("body", ""),
                "html_body": client_email.get("html_body"),
                "product_images": client_email.get("product_images"),
                "proposal": proposal,
            },
        }
    return {"type": stage, "draft": ctx}


def gate_for_stage(stage: str) -> str | None:
    info = stage_by_id(stage)
    return info.get("gate") if info else None
