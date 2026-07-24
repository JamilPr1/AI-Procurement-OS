"""Per-lead pipeline advancement — run next AI stage for a single hot lead."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from src.core.event_bus import bus
from src.core.hot_leads import build_hot_lead_brief, determine_next_step
from src.core.pipeline_engine import PipelineEngine
from src.core.review_workflow import ReviewWorkflow, extract_draft_for_stage, gate_for_stage
from src.tools.supplier_finder import SupplierFinder


class LeadPipelineService:
    """Advance one lead through the next pipeline stage without a full batch run."""

    def __init__(self, engine: PipelineEngine) -> None:
        self.engine = engine
        self.storage = engine.storage
        self.tenant_id = engine.tenant_id
        self._locks: dict[str, threading.Lock] = {}
        self.review = ReviewWorkflow(self.storage)

    def analyze_all(self) -> list[dict[str, Any]]:
        leads = self.storage.list_leads(self.tenant_id)
        suppliers = self.storage.list_suppliers(self.tenant_id)
        briefs = []
        for lead in leads:
            brief = self._analyze_one(lead, suppliers)
            briefs.append(brief)
            self.storage.save_json_entity("hot_leads", lead["id"], brief)
        briefs.sort(key=lambda b: b.get("hot_score", 0), reverse=True)
        return briefs

    def analyze_lead(self, lead_id: str) -> dict[str, Any]:
        lead = self.storage.get_lead(lead_id)
        if not lead:
            raise ValueError("Lead not found")
        suppliers = self.storage.list_suppliers(self.tenant_id)
        brief = self._analyze_one(lead, suppliers)
        self.storage.save_json_entity("hot_leads", lead_id, brief)
        return brief

    def refresh_lead_drafts(self, lead_id: str) -> dict[str, Any]:
        """Regenerate personalization/outreach/proposal drafts with latest templates (unsent only)."""
        from src.core.company_name import normalize_lead_record
        from src.core.draft_composer import compose_outreach_email, compose_personalization

        lead = self.storage.get_lead(lead_id)
        if not lead:
            raise ValueError("Lead not found")

        data = lead.get("data") or {}
        if isinstance(data, str):
            data = json.loads(data)

        normalized = normalize_lead_record({
            **data,
            "id": lead_id,
            "company_name": lead["company_name"],
        })
        new_name = normalized.get("company_name", lead["company_name"])
        if new_name != lead["company_name"]:
            data = {**data, "email": normalized.get("email") or data.get("email", "")}
            conn = self.storage._connect()
            conn.execute(
                "UPDATE leads SET company_name=?, data=?, updated_at=? WHERE id=?",
                (new_name, json.dumps(data), datetime.now(timezone.utc).isoformat(), lead_id),
            )
            conn.commit()

        company = self.storage.load_json_entity("companies", lead_id) or {}
        deals = self.storage.get_deals_for_lead(lead_id)
        deal_id = deals[0]["id"] if deals else None

        top_lead = {**data, "id": lead_id, "company_name": new_name}
        top_lead["email"] = normalized.get("email") or data.get("email", "")

        pers = compose_personalization(top_lead, company)
        self.storage.save_json_entity("personalization", lead_id, pers)

        outreach = self.storage.load_json_entity("outreach", lead_id)
        scope = "personalization"
        if outreach and outreach.get("status") != "sent":
            images = company.get("product_images") or top_lead.get("product_images") or []
            from src.core.hot_leads import extract_buying_intent
            from src.core.outreach_images import resolve_outreach_images

            intent = extract_buying_intent(data, company)
            from src.core.platform_urls import get_public_base_url

            base = get_public_base_url(self.engine.brain.config)
            factory_images = resolve_outreach_images(
                lead_id, top_lead, intent, self.storage, self.tenant_id,
                dashboard_base=base, force_refresh=True,
            )
            outreach_images = factory_images or images
            new_outreach = compose_outreach_email(
                top_lead, pers, product_images=outreach_images, profile=company,
            )
            self.storage.save_json_entity("outreach", lead_id, new_outreach)

            pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
            if not pending or pending.get("gate") == "outreach_first_batch":
                self.review.save_pending(
                    gate="outreach_first_batch",
                    stage="outreach",
                    draft={"type": "outreach", "draft": new_outreach},
                    lead_id=lead_id,
                    deal_id=deal_id,
                )
            scope = "outreach"

        if deal_id:
            self._refresh_proposal_draft(lead_id, deal_id, top_lead)
            self._refresh_rfq_draft(lead_id, deal_id)
            if scope == "personalization":
                scope = "proposal"

        brief = self.analyze_lead(lead_id)
        return {
            "status": "refreshed",
            "scope": scope,
            "lead_id": lead_id,
            "company_name": new_name,
            "brief": brief,
        }

    def _refresh_proposal_draft(self, lead_id: str, deal_id: str, top_lead: dict) -> None:
        proposal = self.storage.load_json_entity("proposals", deal_id)
        if not proposal or proposal.get("status") != "draft":
            return
        from src.core.draft_composer import compose_proposal_client_email

        client_email = compose_proposal_client_email(proposal, top_lead)
        proposal["client_email_draft"] = client_email
        self.storage.save_json_entity("proposals", deal_id, proposal)
        pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
        if not pending or pending.get("gate") == "proposal_send":
            self.review.save_pending(
                gate="proposal_send",
                stage="proposal",
                draft={
                    "type": "proposal",
                    "draft": {
                        "to": client_email.get("to") or top_lead.get("email"),
                        "subject": client_email.get("subject") or proposal.get("title"),
                        "body": client_email.get("body", ""),
                        "html_body": client_email.get("html_body"),
                        "product_images": client_email.get("product_images"),
                        "proposal": proposal,
                    },
                },
                lead_id=lead_id,
                deal_id=deal_id,
            )

    def _refresh_rfq_draft(self, lead_id: str, deal_id: str) -> None:
        rfqs = self.storage.get_rfqs_for_deal(deal_id)
        if not rfqs or rfqs[0].get("status") != "draft":
            return
        from src.core.draft_composer import compose_rfq_email

        deal = self.storage.get_deal(deal_id) or {}
        req = deal.get("buyer_requirements") or {}
        if isinstance(req, str):
            try:
                req = json.loads(req)
            except json.JSONDecodeError:
                req = {}
        spec = self.storage.load_json_entity("products", deal_id) or {}
        suppliers = self._load_suppliers_for_ctx(req, lead_id=lead_id)
        rfq_data = compose_rfq_email(req, suppliers, spec)
        rfq = rfqs[0]
        rfq_id = rfq["id"]
        conn = self.storage._connect()
        conn.execute(
            "UPDATE rfqs SET data = ?, updated_at = ? WHERE id = ?",
            (json.dumps(rfq_data), datetime.now(timezone.utc).isoformat(), rfq_id),
        )
        conn.commit()
        self.storage.save_json_entity("rfqs", rfq_id, rfq_data)
        pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
        if not pending or pending.get("gate") == "rfq_send":
            self.review.save_pending(
                gate="rfq_send",
                stage="rfq",
                draft={
                    "type": "rfq",
                    "draft": rfq_data,
                    "rfq_id": rfq_id,
                    "product": rfq_data.get("product"),
                },
                lead_id=lead_id,
                deal_id=deal_id,
            )

    def refresh_all_drafts(self) -> dict[str, Any]:
        """Refresh outreach drafts for every lead that has not sent outreach yet."""
        leads = self.storage.list_leads(self.tenant_id)
        refreshed = 0
        skipped = 0
        errors: list[str] = []
        for lead in leads:
            try:
                result = self.refresh_lead_drafts(lead["id"])
                if result.get("status") == "refreshed":
                    refreshed += 1
                else:
                    skipped += 1
            except Exception as e:
                errors.append(f"{lead['id']}: {e}")
        return {"status": "ok", "refreshed": refreshed, "skipped": skipped, "errors": errors}

    def get_brief(self, lead_id: str, *, fresh: bool = False) -> dict[str, Any] | None:
        if fresh:
            return self.analyze_lead(lead_id)
        cached = self.storage.load_json_entity("hot_leads", lead_id)
        if cached:
            return cached
        return self.analyze_lead(lead_id)

    def list_hot(self, *, min_score: float = 50) -> list[dict[str, Any]]:
        cached = self._load_all_cached()
        if not cached:
            cached = self.analyze_all()
        return [
            b for b in cached
            if b.get("hot_score", 0) >= min_score and not b.get("on_tracking") and b.get("is_hot")
        ]

    def advance(self, lead_id: str, *, auto_approve: bool = False) -> dict[str, Any]:
        lock = self._locks.setdefault(lead_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return {"status": "busy", "message": "This lead is already being processed"}
        try:
            return self._advance_sync(lead_id, auto_approve=auto_approve)
        finally:
            lock.release()

    def approve_review(self, lead_id: str, *, draft_overrides: dict | None = None) -> dict[str, Any]:
        lock = self._locks.setdefault(lead_id, threading.Lock())
        if not lock.acquire(blocking=False):
            return {"status": "busy", "message": "This lead is already being processed"}
        try:
            deals = self.storage.get_deals_for_lead(lead_id)
            deal_id = deals[0]["id"] if deals else None
            entity_id = deal_id or lead_id
            pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
            if not pending:
                raise ValueError("Nothing pending review for this lead")

            if draft_overrides:
                self._apply_draft_overrides(lead_id, deal_id, pending, draft_overrides)

            result = self.review.approve_and_send(entity_id)
            self._advance_after_approve(lead_id, result["gate"], deal_id)
            brief = self.analyze_lead(lead_id)
            bus.publish("lead_review_approved", {"lead_id": lead_id, "gate": result["gate"], "brief": brief})
            return {
                "status": "approved",
                "gate": result["gate"],
                "send_result": result.get("send_result"),
                "brief": brief,
            }
        finally:
            lock.release()

    def update_draft(self, lead_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        """Save user edits to pending review and underlying artifacts."""
        ctx = self._context_for_lead(lead_id)
        deal_id = ctx["deal_id"]
        pending = ctx["pending"]
        if pending and pending.get("status") == "pending":
            self._apply_draft_overrides(lead_id, deal_id, pending, fields)
        else:
            self._apply_artifact_edits(lead_id, deal_id, fields)
        brief = self.analyze_lead(lead_id)
        return {"status": "saved", "brief": brief}

    def set_supplier_selection(self, lead_id: str, supplier_id: str) -> dict[str, Any]:
        """Persist the user's preferred supplier for a hot lead."""
        lead = self.storage.get_lead(lead_id)
        if not lead:
            raise ValueError("Lead not found")
        if not supplier_id:
            raise ValueError("supplier_id is required")

        suppliers = self.storage.list_suppliers(self.tenant_id)
        brief = self._analyze_one(lead, suppliers)
        matches = brief.get("supplier_matches") or []
        selected: dict[str, Any] | None = None
        for i, m in enumerate(matches):
            mid = m.get("supplier_id") or m.get("url") or f"idx-{i}"
            if mid == supplier_id:
                selected = m
                break
        if not selected:
            raise ValueError("Supplier not found in current matches")

        payload = {
            "supplier_id": supplier_id,
            "factory_name": selected.get("factory_name"),
            "url": selected.get("url", ""),
            "platform": selected.get("platform", ""),
            "match_score": selected.get("match_score"),
            "trust_score": selected.get("trust_score"),
            "selected_at": datetime.now(timezone.utc).isoformat(),
        }
        self.storage.save_json_entity("supplier_selection", lead_id, payload)
        deals = self.storage.get_deals_for_lead(lead_id)
        if deals:
            self.storage.save_json_entity("supplier_selection", deals[0]["id"], payload)
        brief = self.analyze_lead(lead_id)
        return {"status": "saved", "selection": payload, "brief": brief}

    def get_pipeline_package(self, lead_id: str) -> dict[str, Any]:
        from src.core.deal_review import build_lead_pipeline_package

        lead = self.storage.get_lead(lead_id)
        if not lead:
            raise ValueError("Lead not found")
        return build_lead_pipeline_package(self.storage, lead, tenant_id=self.tenant_id)

    def _apply_draft_overrides(
        self,
        lead_id: str,
        deal_id: str | None,
        pending: dict,
        fields: dict[str, Any],
    ) -> None:
        draft = pending.get("draft") or {}
        gate = pending.get("gate", "")
        inner = draft.get("draft") if isinstance(draft.get("draft"), dict) else draft

        for key in ("to", "subject", "body", "html_body", "email_body", "rfq_body", "linkedin_message"):
            if key in fields and fields[key] is not None:
                inner[key] = fields[key]

        if draft.get("draft") is not None:
            draft["draft"] = inner
        else:
            draft.update({k: v for k, v in fields.items() if v is not None})

        entity_id = deal_id or lead_id
        pending["draft"] = draft
        self.review.storage.save_json_entity("reviews", entity_id, pending)
        self._apply_artifact_edits(lead_id, deal_id, fields, gate=gate)

    def _apply_artifact_edits(
        self,
        lead_id: str,
        deal_id: str | None,
        fields: dict[str, Any],
        *,
        gate: str = "",
    ) -> None:
        if "company_summary" in fields and fields["company_summary"] is not None:
            company = self.storage.load_json_entity("companies", lead_id) or {}
            company["company_summary"] = fields["company_summary"]
            self.storage.save_json_entity("companies", lead_id, company)

        if any(k in fields for k in ("email_body", "subject_line", "linkedin_message")):
            pers = self.storage.load_json_entity("personalization", lead_id) or {}
            if "email_body" in fields and fields["email_body"] is not None:
                pers["email_body"] = fields["email_body"]
            if "subject_line" in fields and fields["subject_line"] is not None:
                pers["subject_line"] = fields["subject_line"]
            if "linkedin_message" in fields and fields["linkedin_message"] is not None:
                pers["linkedin_message"] = fields["linkedin_message"]
            self.storage.save_json_entity("personalization", lead_id, pers)

        if any(k in fields for k in ("to", "subject", "body")):
            outreach = self.storage.load_json_entity("outreach", lead_id) or {}
            if "to" in fields and fields["to"] is not None:
                outreach["to"] = fields["to"]
            if "subject" in fields and fields["subject"] is not None:
                outreach["subject"] = fields["subject"]
            if "body" in fields and fields["body"] is not None:
                outreach["body"] = fields["body"]
            self.storage.save_json_entity("outreach", lead_id, outreach)

        if deal_id and any(k in fields for k in ("rfq_body", "subject")):
            rfqs = self.storage.get_rfqs_for_deal(deal_id)
            if rfqs:
                rfq = rfqs[0]
                data = rfq.get("data") or {}
                if isinstance(data, str):
                    data = json.loads(data)
                if "rfq_body" in fields and fields["rfq_body"] is not None:
                    data["rfq_body"] = fields["rfq_body"]
                if "subject" in fields and fields["subject"] is not None:
                    data["subject"] = fields["subject"]
                self.storage._connect().execute(
                    "UPDATE rfqs SET data = ?, updated_at = ? WHERE id = ?",
                    (json.dumps(data), datetime.now(timezone.utc).isoformat(), rfq["id"]),
                )
                self.storage._connect().commit()
                self.storage.save_json_entity("rfqs", rfq["id"], data)

        if deal_id and any(k in fields for k in ("executive_summary", "title")):
            proposal = self.storage.load_json_entity("proposals", deal_id) or {}
            if "executive_summary" in fields and fields["executive_summary"] is not None:
                proposal["executive_summary"] = fields["executive_summary"]
            if "title" in fields and fields["title"] is not None:
                proposal["title"] = fields["title"]
            self.storage.save_json_entity("proposals", deal_id, proposal)

    def advance_async(self, lead_id: str, *, auto_approve: bool = False) -> None:
        t = threading.Thread(
            target=lambda: self.advance(lead_id, auto_approve=auto_approve),
            daemon=True,
        )
        t.start()

    def _context_for_lead(self, lead_id: str) -> dict[str, Any]:
        lead = self.storage.get_lead(lead_id)
        if not lead:
            raise ValueError("Lead not found")
        company = self.storage.load_json_entity("companies", lead_id) or {}
        deals = self.storage.get_deals_for_lead(lead_id)
        deal_id = deals[0]["id"] if deals else None
        outreach = self.storage.load_json_entity("outreach", lead_id)
        proposal = self.storage.load_json_entity("proposals", deal_id) if deal_id else None
        rfqs = self.storage.get_rfqs_for_deal(deal_id) if deal_id else []
        pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
        pending = self._sync_pending_from_drafts(lead_id, deal_id, pending, outreach, proposal, rfqs)
        return {
            "lead": lead,
            "company": company,
            "deals": deals,
            "deal_id": deal_id,
            "quotes": self.storage.load_json_entity("quotes", deal_id) if deal_id else None,
            "proposal": proposal,
            "rfqs": rfqs,
            "outreach": outreach,
            "personalization": self.storage.load_json_entity("personalization", lead_id),
            "pending": pending,
        }

    def _advance_sync(self, lead_id: str, *, auto_approve: bool) -> dict[str, Any]:
        ctx_data = self._context_for_lead(lead_id)
        lead = ctx_data["lead"]
        company = ctx_data["company"]
        deals = ctx_data["deals"]
        deal_id = ctx_data["deal_id"]

        if ctx_data["pending"] and auto_approve:
            self._auto_approve_pending(lead_id, deal_id)

        ctx_data = self._context_for_lead(lead_id)
        deals = ctx_data["deals"]
        deal_id = ctx_data["deal_id"]

        next_step = determine_next_step(
            lead, company, deals,
            ctx_data["quotes"], ctx_data["proposal"], ctx_data["rfqs"],
            pending_review=ctx_data["pending"],
            outreach=ctx_data["outreach"],
            personalization=ctx_data["personalization"],
        )
        stage = next_step["stage"]

        if ctx_data["pending"] and not auto_approve:
            return {
                "status": "pending_review",
                "gate": ctx_data["pending"].get("gate"),
                "gate_label": ctx_data["pending"].get("gate_label"),
                "draft": ctx_data["pending"].get("draft"),
                "message": "Review and approve before continuing",
                "brief": self.analyze_lead(lead_id),
            }

        if next_step.get("review") and not auto_approve:
            if not ctx_data["pending"]:
                self._sync_pending_from_drafts(
                    lead_id,
                    deal_id,
                    None,
                    ctx_data["outreach"],
                    ctx_data["proposal"],
                    ctx_data["rfqs"] or [],
                )
            return {
                "status": "pending_review",
                "gate": next_step.get("gate"),
                "message": "Use Approve & Send to continue",
                "brief": self.analyze_lead(lead_id),
            }

        if stage in ("tracking", "closed"):
            return {
                "status": stage,
                "message": next_step.get("description", "Deal is on Tracking or Closed page"),
                "brief": self.analyze_lead(lead_id),
            }

        if stage == "close":
            if deal_id:
                self.storage.update_deal(deal_id, stage="closed", status="completed")
            self.storage._connect().execute(
                "UPDATE leads SET status = ? WHERE id = ?",
                ("won", lead_id),
            )
            self.storage._connect().commit()
            brief = self.analyze_lead(lead_id)
            bus.publish("lead_advanced", {"lead_id": lead_id, "stage": "closed", "brief": brief})
            return {"status": "completed", "stage": "closed", "brief": brief}

        run_ctx = self._build_ctx(lead, company, deals)
        run_id = f"lead-{lead_id[:8]}"

        bus.publish("lead_stage_started", {"lead_id": lead_id, "stage": stage, "agent": next_step.get("agent")})

        if stage == "qualification" and run_ctx.get("deal_id"):
            stage = "product_research"
            next_step = {**next_step, "stage": stage, "label": "Research Product Spec"}

        handler = getattr(self.engine, f"_stage_{stage}", None)
        if handler:
            run_ctx = handler(run_ctx, run_id)
        else:
            self._run_custom_stage(stage, run_ctx, run_id)

        gate = gate_for_stage(stage)
        if gate and auto_approve:
            draft = extract_draft_for_stage(stage, run_ctx)
            self._persist_ctx(run_ctx, lead_id, stage, advance=False)
            entity_id = run_ctx.get("deal_id") or lead_id
            self.review.save_pending(
                gate=gate,
                stage=stage,
                draft=draft,
                lead_id=lead_id,
                deal_id=run_ctx.get("deal_id"),
            )
            result = self.review.approve_and_send(entity_id)
            self._advance_after_approve(lead_id, result["gate"], run_ctx.get("deal_id"))
            self._persist_ctx(run_ctx, lead_id, stage, advance=True)
            brief = self.analyze_lead(lead_id)
            bus.publish("lead_stage_completed", {
                "lead_id": lead_id,
                "stage": stage,
                "deal_id": run_ctx.get("deal_id"),
                "auto_approved": True,
                "brief": brief,
            })
            return {
                "status": "success",
                "stage": stage,
                "agent": next_step.get("agent"),
                "label": next_step.get("label"),
                "deal_id": run_ctx.get("deal_id"),
                "auto_approved": True,
                "send_result": result.get("send_result"),
                "brief": brief,
            }

        if gate and not auto_approve:
            draft = extract_draft_for_stage(stage, run_ctx)
            self._persist_ctx(run_ctx, lead_id, stage, advance=False)
            self.review.save_pending(
                gate=gate,
                stage=stage,
                draft=draft,
                lead_id=lead_id,
                deal_id=run_ctx.get("deal_id"),
            )
            brief = self.analyze_lead(lead_id)
            bus.publish("lead_stage_completed", {
                "lead_id": lead_id,
                "stage": stage,
                "deal_id": run_ctx.get("deal_id"),
                "pending_review": True,
                "gate": gate,
            })
            return {
                "status": "pending_review",
                "stage": stage,
                "gate": gate,
                "draft": draft,
                "label": next_step.get("label"),
                "brief": brief,
            }

        self._persist_ctx(run_ctx, lead_id, stage, advance=True)
        brief = self.analyze_lead(lead_id)

        bus.publish("lead_stage_completed", {
            "lead_id": lead_id,
            "stage": stage,
            "deal_id": run_ctx.get("deal_id"),
            "brief": brief,
        })
        return {
            "status": "success",
            "stage": stage,
            "agent": next_step.get("agent"),
            "label": next_step.get("label"),
            "deal_id": run_ctx.get("deal_id"),
            "brief": brief,
        }

    def _auto_approve_pending(self, lead_id: str, deal_id: str | None) -> None:
        entity_id = deal_id or lead_id
        pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
        if not pending or pending.get("status") != "pending":
            return
        result = self.review.approve_and_send(entity_id)
        self._advance_after_approve(lead_id, result["gate"], deal_id)

    def _advance_after_approve(self, lead_id: str, gate: str, deal_id: str | None) -> None:
        if gate == "outreach_first_batch":
            return
        if not deal_id:
            return
        if gate == "supplier_final_approval":
            self.storage.update_deal(deal_id, stage="rfq", status="active")
        elif gate == "rfq_send":
            self.storage.update_deal(deal_id, stage="quote_comparison", status="active")
        elif gate == "proposal_send":
            now = datetime.now(timezone.utc).isoformat()
            self.storage.update_deal(
                deal_id,
                stage="proposal_sent",
                status="tracking",
                tracking_entered_at=now,
            )
        elif gate == "contract_sign":
            self.storage.update_deal(deal_id, stage="order_tracking", status="tracking")
        elif gate == "payment_over_threshold":
            self.storage.update_deal(deal_id, stage="finance", status="tracking")

    def _run_custom_stage(self, stage: str, ctx: dict, run_id: str) -> None:
        if stage == "close":
            return
        raise ValueError(f"Unknown stage: {stage}")

    def _build_ctx(self, lead: dict, company: dict, deals: list) -> dict[str, Any]:
        data = lead.get("data") or {}
        if isinstance(data, str):
            data = json.loads(data)
        top_lead = {**data, "id": lead["id"], "company_name": lead["company_name"], "lead_score": lead.get("lead_score", 0)}
        ctx: dict[str, Any] = {
            "lead_id": lead["id"],
            "top_lead": top_lead,
            "profile": company or self.engine._company_profile(top_lead),
        }
        pers = self.storage.load_json_entity("personalization", lead["id"])
        if pers:
            ctx["personalization"] = pers
        if deals:
            deal = deals[0]
            ctx["deal_id"] = deal["id"]
            ctx["requirements"] = deal.get("buyer_requirements") or {}
            if isinstance(ctx["requirements"], str):
                try:
                    ctx["requirements"] = json.loads(ctx["requirements"])
                except json.JSONDecodeError:
                    ctx["requirements"] = {}
            ctx["product_spec"] = self.storage.load_json_entity("products", deal["id"]) or {}
            quotes = self.storage.load_json_entity("quotes", deal["id"])
            if quotes:
                ctx["quotes"] = quotes.get("quotes", [])
                ctx["recommendation"] = quotes.get("comparison", {})
            suppliers = self._load_suppliers_for_ctx(ctx.get("requirements", {}), lead_id=lead["id"])
            if suppliers:
                ctx["suppliers"] = suppliers
                ctx["verified_suppliers"] = suppliers
            rfqs = self.storage.get_rfqs_for_deal(deal["id"])
            if rfqs:
                ctx["rfq"] = rfqs[0].get("data") or {}
                ctx["rfq_id"] = rfqs[0].get("id")
            proposal = self.storage.load_json_entity("proposals", deal["id"])
            if proposal:
                ctx["proposal"] = proposal
            order = self.storage.get_order_for_deal(deal["id"])
            if order:
                ctx["order_id"] = order.get("id")
                ctx["order"] = order.get("data") or {}
        return ctx

    def _load_suppliers_for_ctx(self, requirements: dict, lead_id: str | None = None) -> list[dict[str, Any]]:
        rows = self.storage.list_suppliers(self.tenant_id, limit=20)
        if not rows:
            return []
        product = (requirements.get("product_description") or "").lower()
        selection = self.storage.load_json_entity("supplier_selection", lead_id) if lead_id else None
        selected_id = (selection or {}).get("supplier_id")
        out = []
        for s in rows:
            d = s.get("data") or {}
            sid = s.get("id") or d.get("url", "")
            out.append({
                "id": s.get("id"),
                "factory_name": s.get("factory_name"),
                "platform_source": d.get("platform_source", ""),
                "url": d.get("url", ""),
                "moq": d.get("moq", 0),
                "unit_price_estimate_usd": d.get("unit_price_estimate_usd", 0),
                "trust_score": s.get("trust_score") or d.get("trust_score", 75),
                "recommendation": d.get("recommendation", "proceed"),
            })
        if selected_id:
            picked = [e for e in out if (e.get("id") or e.get("url")) == selected_id]
            rest = [e for e in out if (e.get("id") or e.get("url")) != selected_id]
            if picked:
                out = picked + rest
            elif selection and selection.get("factory_name"):
                out.insert(0, {
                    "factory_name": selection["factory_name"],
                    "platform_source": selection.get("platform", ""),
                    "url": selection.get("url", ""),
                    "moq": 0,
                    "unit_price_estimate_usd": 0,
                    "trust_score": selection.get("trust_score") or 75,
                    "recommendation": "user_selected",
                })
        if product:
            matched = [e for e in out if product in (e.get("factory_name") or "").lower()]
            if matched:
                return matched[:8]
        return out[:8]

    def _persist_ctx(self, ctx: dict, lead_id: str, stage: str, *, advance: bool = True) -> None:
        if ctx.get("profile"):
            self.storage.save_json_entity("companies", lead_id, ctx["profile"])
        if ctx.get("personalization"):
            self.storage.save_json_entity("personalization", lead_id, ctx["personalization"])
        if ctx.get("outreach"):
            outreach = ctx["outreach"]
            if outreach.get("status") != "sent":
                outreach["status"] = "draft"
            self.storage.save_json_entity("outreach", lead_id, outreach)
        if ctx.get("deal_id"):
            deal_id = ctx["deal_id"]
            if ctx.get("requirements"):
                self.storage.update_deal(deal_id, buyer_requirements=ctx["requirements"])
            if ctx.get("product_spec"):
                self.storage.save_json_entity("products", deal_id, ctx["product_spec"])
            if ctx.get("verified_suppliers"):
                for s in ctx["verified_suppliers"]:
                    self.storage.upsert_supplier(self.tenant_id, s.get("factory_name", "Unknown"), s)
            if ctx.get("quotes"):
                self.storage.save_json_entity("quotes", deal_id, {
                    "quotes": ctx["quotes"],
                    "comparison": ctx.get("recommendation", {}),
                })
            if ctx.get("proposal"):
                prop = ctx["proposal"]
                if prop.get("status") != "sent":
                    prop["status"] = "draft"
                self.storage.save_json_entity("proposals", deal_id, prop)
            if not advance:
                return
            stage_map = {
                "qualification": "product_research",
                "product_research": "supplier_discovery",
                "supplier_discovery": "supplier_verification",
                "supplier_verification": "rfq",
                "rfq": "quote_comparison",
                "quote_comparison": "proposal",
                "proposal": "proposal",
                "order_tracking": "order_tracking",
                "finance": "finance",
            }
            new_stage = stage_map.get(stage, stage)
            if new_stage in ("order_tracking", "finance"):
                self.storage.update_deal(deal_id, stage=new_stage, status="tracking")
            else:
                self.storage.update_deal(deal_id, stage=new_stage, status="active")
        if stage == "company_research":
            self.storage._connect().execute(
                "UPDATE leads SET status = ? WHERE id = ?",
                ("researched", lead_id),
            )
            self.storage._connect().commit()
            return

    def _analyze_one(self, lead: dict, suppliers: list) -> dict[str, Any]:
        lead_id = lead["id"]
        company = self.storage.load_json_entity("companies", lead_id)
        deals = self.storage.get_deals_for_lead(lead_id)
        deal_id = deals[0]["id"] if deals else None
        quotes = self.storage.load_json_entity("quotes", deal_id) if deal_id else None
        proposal = self.storage.load_json_entity("proposals", deal_id) if deal_id else None
        rfqs = self.storage.get_rfqs_for_deal(deal_id) if deal_id else []
        outreach = self.storage.load_json_entity("outreach", lead_id)
        personalization = self.storage.load_json_entity("personalization", lead_id)
        supplier_selection = self.storage.load_json_entity("supplier_selection", lead_id)
        if deal_id:
            deal_sel = self.storage.load_json_entity("supplier_selection", deal_id)
            if deal_sel:
                supplier_selection = deal_sel
        pending = self.review.get_pending(lead_id=lead_id, deal_id=deal_id)
        pending = self._sync_pending_from_drafts(lead_id, deal_id, pending, outreach, proposal, rfqs)

        brief = build_hot_lead_brief(
            lead, company, deals, suppliers,
            quotes=quotes, proposal=proposal, rfqs=rfqs,
            pending_review=pending, outreach=outreach, personalization=personalization,
            supplier_selection=supplier_selection,
        )
        brief["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        brief["pending_review"] = pending
        brief["email_status"] = self.review.email.status()
        try:
            from src.core.deal_review import build_lead_pipeline_package
            brief["pipeline"] = build_lead_pipeline_package(self.storage, lead, tenant_id=self.tenant_id)
        except Exception:
            brief["pipeline"] = {"steps": [], "artifacts": {}, "documents": []}
        return brief

    def _sync_pending_from_drafts(
        self,
        lead_id: str,
        deal_id: str | None,
        pending: dict | None,
        outreach: dict | None,
        proposal: dict | None,
        rfqs: list,
    ) -> dict | None:
        if pending and pending.get("status") == "pending":
            return pending
        if outreach and outreach.get("status") == "draft":
            return self.review.save_pending(
                gate="outreach_first_batch",
                stage="outreach",
                draft={"type": "outreach", "draft": outreach},
                lead_id=lead_id,
            )
        if deal_id and proposal and proposal.get("status") == "draft" and proposal.get("title"):
            lead = self.storage.get_lead(lead_id)
            data = (lead or {}).get("data") or {}
            from src.core.draft_composer import compose_proposal_client_email

            lead_ctx = {
                "company_name": (lead or {}).get("company_name", "Client"),
                "email": data.get("email", ""),
            }
            client_email = compose_proposal_client_email(proposal, lead_ctx)
            return self.review.save_pending(
                gate="proposal_send",
                stage="proposal",
                draft={
                    "type": "proposal",
                    "draft": {
                        "to": client_email.get("to") or data.get("email"),
                        "subject": client_email.get("subject") or proposal.get("title"),
                        "body": client_email.get("body", ""),
                        "html_body": client_email.get("html_body"),
                        "product_images": client_email.get("product_images"),
                        "proposal": proposal,
                    },
                },
                lead_id=lead_id,
                deal_id=deal_id,
            )
        if deal_id and rfqs and rfqs[0].get("status") == "draft":
            rfq = rfqs[0]
            return self.review.save_pending(
                gate="rfq_send",
                stage="rfq",
                draft={
                    "type": "rfq",
                    "draft": rfq.get("data") or {},
                    "rfq_id": rfq.get("id"),
                },
                lead_id=lead_id,
                deal_id=deal_id,
            )
        return pending

    def _load_all_cached(self) -> list[dict[str, Any]]:
        leads = self.storage.list_leads(self.tenant_id)
        out = []
        for lead in leads:
            cached = self.storage.load_json_entity("hot_leads", lead["id"])
            if cached:
                out.append(cached)
        if out:
            out.sort(key=lambda b: b.get("hot_score", 0), reverse=True)
        return out
