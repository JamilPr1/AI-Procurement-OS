"""Fast stateful pipeline engine with human-gate pause/resume."""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.agency import Agency
from src.core.brain import Brain
from src.core.event_bus import bus
from src.core.llm import LLMClient
from src.core.logger import PlatformLogger
from src.core.orchestrator import Orchestrator
from src.core.pipeline_stages import GATE_LABELS, PIPELINE_STAGES, ROADMAP_PHASES
from src.core.storage import Storage
from src.tools.lead_finder import LeadFinder
from src.tools.supplier_finder import SupplierFinder
from src.core.draft_composer import (
    compose_outreach_email,
    compose_personalization,
    compose_proposal_client_email,
    compose_proposal_document,
    compose_rfq_email,
)
from src.core.image_assets import cache_product_images
from src.agents.fallbacks import run_fallback
from src.tools.niche_finder import NicheFinder


class PipelineEngine:
    def __init__(
        self,
        brain: Brain,
        orchestrator: Orchestrator,
        storage: Storage,
        logger: PlatformLogger,
        agency: Agency,
        llm: LLMClient,
        project_root: Path,
    ) -> None:
        self.brain = brain
        self.orchestrator = orchestrator
        self.storage = storage
        self.logger = logger
        self.agency = agency
        self.llm = llm
        self.project_root = project_root
        self.tenant_id = agency.tenant_id
        self._threads: dict[str, threading.Thread] = {}
        self._resume_events: dict[str, threading.Event] = {}

    def start(self, run_id: str | None = None, *, auto_approve: bool = False) -> str:
        if not run_id:
            run_id = self.storage.create_pipeline_run(self.tenant_id)
        self._resume_events[run_id] = threading.Event()
        if auto_approve:
            self._resume_events[run_id].set()

        t = threading.Thread(target=self._run_loop, args=(run_id, auto_approve), daemon=True)
        self._threads[run_id] = t
        t.start()
        return run_id

    def approve_gate(self, run_id: str) -> bool:
        run = self.storage.get_pipeline_run(run_id)
        if not run or run["status"] != "paused":
            return False
        gate = run.get("pending_gate")
        self.storage.update_pipeline_run(run_id, pending_gate=None, status="running")
        bus.publish("gate_approved", {"run_id": run_id, "gate": gate})
        if run_id in self._resume_events:
            self._resume_events[run_id].set()
        return True

    def get_status(self, run_id: str) -> dict[str, Any]:
        run = self.storage.get_pipeline_run(run_id)
        if not run:
            return {}
        stages = []
        for s in PIPELINE_STAGES:
            stages.append({
                **s,
                "status": run["stage_status"].get(s["id"], "pending"),
                "gate_label": GATE_LABELS.get(s["gate"]) if s.get("gate") else None,
            })
        return {
            "run_id": run_id,
            "status": run["status"],
            "current_stage": run.get("current_stage"),
            "pending_gate": run.get("pending_gate"),
            "pending_gate_label": GATE_LABELS.get(run.get("pending_gate") or "", ""),
            "stages": stages,
            "summary": run.get("summary"),
            "context": run.get("context"),
            "error": run.get("error"),
            "roadmap": ROADMAP_PHASES,
        }

    def _run_loop(self, run_id: str, auto_approve: bool) -> None:
        ctx: dict[str, Any] = {}
        t0 = time.perf_counter()
        try:
            self.storage.update_pipeline_run(run_id, status="running")
            bus.publish("run_started", {"run_id": run_id})

            for stage in PIPELINE_STAGES:
                sid = stage["id"]
                if not self._should_continue(run_id):
                    return

                self._stage_start(run_id, sid)
                handler = getattr(self, f"_stage_{sid}", None)
                if handler:
                    ctx = handler(ctx, run_id)
                self.storage.update_pipeline_run(run_id, context=ctx)
                self._stage_done(run_id, sid)

                gate = stage.get("gate")
                if gate and not auto_approve:
                    if gate == "payment_over_threshold":
                        price = ctx.get("proposal", {}).get("client_price_usd", 0)
                        if price < self.brain.config.get("agency", {}).get("payment_threshold_usd", 5000):
                            gate = None
                    if gate:
                        self._pause_for_gate(run_id, sid, gate, ctx)
                        self._resume_events[run_id].wait()
                        self._resume_events[run_id].clear()

            elapsed = round(time.perf_counter() - t0, 1)
            summary = self._build_summary(ctx, elapsed)
            self.storage.update_pipeline_run(
                run_id, status="completed", summary=summary, context=ctx, current_stage=None
            )
            bus.publish("run_completed", {"run_id": run_id, "summary": summary, "elapsed_sec": elapsed})
        except Exception as e:
            self.logger.error("Pipeline failed", run_id=run_id, error=str(e))
            run = self.storage.get_pipeline_run(run_id)
            if run:
                ss = run["stage_status"]
                cur = run.get("current_stage")
                if cur and ss.get(cur) == "running":
                    ss[cur] = "failed"
                self.storage.update_pipeline_run(
                    run_id, status="failed", error=str(e), stage_status=ss
                )
            else:
                self.storage.update_pipeline_run(run_id, status="failed", error=str(e))
            bus.publish("run_failed", {"run_id": run_id, "error": str(e)})

    def _should_continue(self, run_id: str) -> bool:
        run = self.storage.get_pipeline_run(run_id)
        return run is not None and run["status"] in ("running", "paused")

    def _stage_start(self, run_id: str, stage_id: str) -> None:
        run = self.storage.get_pipeline_run(run_id)
        if not run:
            return
        ss = run["stage_status"]
        ss[stage_id] = "running"
        self.storage.update_pipeline_run(run_id, current_stage=stage_id, stage_status=ss)
        label = next((s["label"] for s in PIPELINE_STAGES if s["id"] == stage_id), stage_id)
        bus.publish("stage_started", {"run_id": run_id, "stage": stage_id, "label": label})

    def _stage_done(self, run_id: str, stage_id: str) -> None:
        run = self.storage.get_pipeline_run(run_id)
        if not run:
            return
        ss = run["stage_status"]
        ss[stage_id] = "completed"
        self.storage.update_pipeline_run(run_id, stage_status=ss, context=run["context"])
        bus.publish("stage_completed", {"run_id": run_id, "stage": stage_id})

    def _pause_for_gate(self, run_id: str, stage_id: str, gate: str, ctx: dict) -> None:
        self.storage.update_pipeline_run(
            run_id, status="paused", pending_gate=gate, context=ctx
        )
        bus.publish("human_gate", {
            "run_id": run_id,
            "stage": stage_id,
            "gate": gate,
            "label": GATE_LABELS.get(gate, gate),
        })

    def _emit(self, run_id: str, msg: str) -> None:
        bus.publish("log", {"run_id": run_id, "message": msg})

    # ── Stage handlers (fast / rule-based) ──

    def _stage_niche_finder(self, ctx: dict, run_id: str) -> dict:
        self._emit(run_id, "Finding top buyer niche for this run...")
        finder = NicheFinder(self.brain.config)
        niche = finder.find_top_niche(on_progress=lambda phase, msg: self._emit(run_id, msg))
        if self._use_llm("niche_finder"):
            r = self.orchestrator.run_agent(
                "niche_finder",
                json.dumps({"vertical": self.brain.config.get("vertical", {}), "region": niche.get("region")}),
                entity_type="system",
                entity_id="niche",
            )
            if r.get("status") == "success":
                niche = {**niche, **r.get("output", {})}
        else:
            fb = run_fallback("niche_finder", json.dumps(niche))
            niche = {**niche, **{k: v for k, v in fb.items() if k != "source"}}
        self.storage.save_json_entity("niche", "current", niche)
        self._emit(run_id, f"Top niche: {niche.get('niche_name')} (score {niche.get('niche_score', 0)})")
        ctx["niche"] = niche
        return ctx

    def _stage_lead_discovery(self, ctx: dict, run_id: str) -> dict:
        self._emit(run_id, "Searching web for real buyers (parallel)...")
        finder = LeadFinder(self.brain.config)
        niche = ctx.get("niche") or self.storage.load_json_entity("niche", "current") or {}
        leads = finder.discover(
            on_progress=lambda phase, msg: self._emit(run_id, msg),
            niche=niche,
        )
        if not leads:
            raise RuntimeError("No real leads found")
        saved = []
        new_count = 0
        for lead in leads:
            lid, is_new = self.storage.upsert_lead(self.tenant_id, lead["company_name"], lead)
            lead["id"] = lid
            lead["is_new"] = is_new
            saved.append(lead)
            if is_new:
                new_count += 1
            tag = "NEW" if is_new else "UPD"
            self._emit(run_id, f"[{tag}] {lead['company_name']} ({lead['lead_score']:.0f}) - {lead.get('email') or 'no email'}")
        self._emit(run_id, f"Leads: {new_count} new, {len(saved) - new_count} updated (deduped)")
        ctx["leads"] = saved
        ctx["top_lead"] = max(saved, key=lambda x: x.get("lead_score", 0))
        ctx["lead_id"] = ctx["top_lead"]["id"]
        return ctx

    def _stage_company_research(self, ctx: dict, run_id: str) -> dict:
        lead = ctx["top_lead"]
        profile = self._company_profile(lead)
        if self._use_llm("company_research"):
            r = self.orchestrator.run_agent(
                "company_research",
                json.dumps({"company_name": lead["company_name"], "website_text": lead.get("website_text_preview", "")[:1500]}),
                entity_type="lead", entity_id=ctx["lead_id"],
            )
            if r.get("status") == "success":
                profile = {**profile, **r.get("output", {})}
        images = self._cache_lead_images(lead, ctx["lead_id"])
        if images:
            profile["product_images"] = images
            lead["product_images"] = images
            self._emit(run_id, f"Cached {len(images)} product images from buyer website")
        self.storage.save_json_entity("companies", ctx["lead_id"], profile)
        ctx["profile"] = profile
        return ctx

    def _stage_personalization(self, ctx: dict, run_id: str) -> dict:
        lead, profile = ctx["top_lead"], ctx["profile"]
        draft = compose_personalization(lead, profile)
        if self._use_llm("personalization"):
            r = self.orchestrator.run_agent(
                "personalization",
                json.dumps({"company_profile": profile, "company_name": lead["company_name"]}),
                entity_type="lead", entity_id=ctx["lead_id"],
            )
            if r.get("status") == "success":
                draft = {**draft, **r.get("output", {})}
        else:
            fb = run_fallback("personalization", json.dumps({"company_profile": profile, "company_name": lead["company_name"]}))
            draft = {**draft, **{k: v for k, v in fb.items() if k != "source"}}
        ctx["personalization"] = draft
        return ctx

    def _stage_outreach(self, ctx: dict, run_id: str) -> dict:
        lead = ctx["top_lead"]
        pers = ctx.get("personalization") or compose_personalization(lead, ctx.get("profile", {}))
        images = (ctx.get("profile") or {}).get("product_images") or lead.get("product_images") or []
        from src.core.hot_leads import extract_buying_intent
        from src.core.outreach_images import resolve_outreach_images

        intent = extract_buying_intent(lead, ctx.get("profile", {}))
        factory_images = resolve_outreach_images(
            ctx["lead_id"], lead, intent, self.storage, self.tenant_id,
            dashboard_base=self._dashboard_base(),
        )
        outreach = compose_outreach_email(
            lead, pers,
            product_images=factory_images or images,
            profile=ctx.get("profile", {}),
        )
        if self._use_llm("outreach"):
            r = self.orchestrator.run_agent(
                "outreach",
                json.dumps({"personalization": pers, "outreach_draft": pers}),
                entity_type="lead", entity_id=ctx["lead_id"],
            )
            if r.get("status") == "success":
                out = r.get("output", {})
                outreach["body"] = out.get("message_to_send") or out.get("body") or outreach["body"]
                outreach["subject"] = out.get("subject") or outreach["subject"]
        else:
            fb = run_fallback("outreach", json.dumps({"personalization": pers}))
            outreach["body"] = fb.get("message_to_send") or outreach["body"]
            outreach["subject"] = fb.get("subject") or outreach["subject"]
        ctx["outreach"] = outreach
        return ctx

    def _stage_qualification(self, ctx: dict, run_id: str) -> dict:
        lead, profile = ctx["top_lead"], ctx["profile"]
        products = profile.get("products_services") or self._products_from_text(lead.get("website_text_preview", ""))
        desc = products[0] if products else "custom promotional products"
        ctx["requirements"] = {
            "product_description": desc,
            "quantity": 5000,
            "material": "custom",
            "color": "custom",
            "logo_spec": "custom branded",
            "packaging": "individual retail boxes",
            "delivery_date": "8 weeks",
            "shipping_destination": "United States",
            "ready_for_sourcing": True,
            "completeness_score": 90,
        }
        ctx["deal_id"] = self.storage.create_deal(self.tenant_id, ctx["lead_id"], "product_research")
        self.storage.update_deal(ctx["deal_id"], buyer_requirements=ctx["requirements"])
        return ctx

    def _stage_product_research(self, ctx: dict, run_id: str) -> dict:
        req = ctx["requirements"]
        profile = ctx.get("profile") or {}
        images = profile.get("product_images") or ctx.get("top_lead", {}).get("product_images") or []
        ctx["product_spec"] = {
            "product_category": req["product_description"],
            "materials": ["custom"],
            "typical_pricing_range": {"min_usd": 0.5, "max_usd": 5.0, "unit": "per piece"},
            "certifications_required": ["FDA", "LFGB"],
            "manufacturing_regions": ["China"],
            "standard_packaging": req.get("packaging"),
            "search_keywords": [req["product_description"], "custom OEM manufacturer"],
            "reference_images": images,
            "hero_image": images[0] if images else None,
        }
        self.storage.save_json_entity("products", ctx["deal_id"], ctx["product_spec"])
        return ctx

    def _stage_supplier_discovery(self, ctx: dict, run_id: str) -> dict:
        req = ctx.get("requirements") or {}
        product = req.get("product_description") or "promotional products"
        self._emit(run_id, f"Searching suppliers for: {product}")
        finder = SupplierFinder(self.brain.config)
        ctx["suppliers"] = finder.discover(product, max_suppliers=4)
        for s in ctx["suppliers"]:
            p = s.get("unit_price_estimate_usd") or "?"
            self._emit(run_id, f"Supplier: {s['factory_name'][:50]} - ${p}")
        return ctx

    def _stage_supplier_verification(self, ctx: dict, run_id: str) -> dict:
        verified = []
        for s in ctx.get("suppliers", []):
            score = 75.0
            if s.get("unit_price_estimate_usd"):
                score += 10
            if "alibaba" in (s.get("platform_source") or ""):
                score += 5
            verified.append({**s, "trust_score": min(score, 95), "recommendation": "proceed"})
        ctx["verified_suppliers"] = verified
        for s in verified:
            self.storage.create_supplier(self.tenant_id, s.get("factory_name", "Unknown"), s)
        return ctx

    def _stage_rfq(self, ctx: dict, run_id: str) -> dict:
        req = ctx.get("requirements") or {}
        spec = ctx.get("product_spec") or {}
        verified = ctx.get("verified_suppliers") or ctx.get("suppliers") or []
        if not verified:
            verified = [{"factory_name": "Supplier TBD", "url": "", "notes": "Run supplier discovery first"}]
        rfq_data = compose_rfq_email(req, verified, spec)
        if self._use_llm("rfq"):
            r = self.orchestrator.run_agent(
                "rfq",
                json.dumps({"requirements": req, "verified_suppliers": verified, "product_spec": spec}),
                entity_type="deal", entity_id=ctx.get("deal_id"),
            )
            if r.get("status") == "success":
                rfq_data = {**rfq_data, **r.get("output", {})}
        else:
            fb = run_fallback(
                "rfq",
                json.dumps({"requirements": req, "verified_suppliers": verified, "product_spec": spec}),
            )
            if fb.get("rfq_body"):
                rfq_data["rfq_body"] = fb["rfq_body"]
            rfq_data["suppliers"] = fb.get("suppliers") or rfq_data["suppliers"]
            rfq_data["subject"] = fb.get("subject") or rfq_data.get("subject")
        ctx["verified_suppliers"] = verified
        ctx["rfq"] = rfq_data
        ctx["rfq_id"] = self.storage.create_rfq(self.tenant_id, ctx["deal_id"], rfq_data)
        return ctx

    def _stage_quote_comparison(self, ctx: dict, run_id: str) -> dict:
        quotes = []
        for i, s in enumerate(ctx.get("verified_suppliers", [])):
            price = s.get("unit_price_estimate_usd") or 0
            quotes.append({
                "factory": s.get("factory_name"),
                "price_usd": price,
                "price_known": bool(price),
                "moq": s.get("moq") or 0,
                "url": s.get("url"),
                "rating": round(9.5 - i * 0.2, 1),
            })
        priced = [q for q in quotes if q.get("price_known")] or quotes
        best = min(priced, key=lambda q: q.get("price_usd") or 9999)
        ctx["quotes"] = quotes
        ctx["recommendation"] = {
            "recommended_supplier": best.get("factory"),
            "comparison_table": quotes,
            "reasoning": "Best price from live search data",
        }
        self.storage.save_json_entity("quotes", ctx["deal_id"], {"quotes": quotes, "comparison": ctx["recommendation"]})
        return ctx

    def _stage_proposal(self, ctx: dict, run_id: str) -> dict:
        lead = ctx.get("top_lead") or {}
        req = ctx.get("requirements") or {}
        spec = ctx.get("product_spec") or {}
        rec = ctx.get("recommendation") or {}
        quotes = ctx.get("quotes") or []
        best = next((q for q in quotes if q.get("factory") == rec.get("recommended_supplier")), quotes[0] if quotes else {})
        unit_price = best.get("price_usd") or 0
        if not unit_price:
            pr = spec.get("typical_pricing_range") or {}
            unit_price = pr.get("min_usd") or pr.get("max_usd") or 1.5
        cost = unit_price * req.get("quantity", 5000)
        pricing = self.agency.apply_margin(cost) if cost else {"client_price_usd": 0}
        client_price = pricing.get("client_price_usd", 0) or round(cost * 1.15, 2)

        proposal = compose_proposal_document(
            lead, req, rec, quotes,
            client_price_usd=client_price,
            product_spec=spec,
            factory_cost_usd=pricing.get("factory_cost_usd"),
            margin_usd=pricing.get("margin_usd"),
            margin_percent=pricing.get("margin_percent"),
        )
        if self._use_llm("proposal"):
            r = self.orchestrator.run_agent(
                "proposal",
                json.dumps({"requirements": req, "recommendation": rec, "quotes": quotes, "company_name": lead.get("company_name")}),
                entity_type="deal", entity_id=ctx.get("deal_id"),
            )
            if r.get("status") == "success":
                proposal = {**proposal, **r.get("output", {})}
        else:
            fb = run_fallback("proposal", json.dumps({
                "requirements": req, "recommendation": rec, "quotes": quotes,
                "company_name": lead.get("company_name"),
            }))
            proposal = {**proposal, **{k: v for k, v in fb.items() if k != "source"}}

        proposal["client_email_draft"] = compose_proposal_client_email(proposal, lead)
        proposal["status"] = "draft"
        ctx["proposal"] = proposal
        self.storage.save_json_entity("proposals", ctx["deal_id"], proposal)
        return ctx

    def _stage_order_tracking(self, ctx: dict, run_id: str) -> dict:
        lead = ctx.get("top_lead") or {}
        if not ctx.get("order_id"):
            ctx["order_id"] = self.storage.create_order(self.tenant_id, ctx["deal_id"], {
                "status": "awaiting_client_approval",
                "client": lead.get("company_name", "Client"),
                "proposal_summary": (ctx.get("proposal") or {}).get("executive_summary", ""),
            })
        ctx["order_status"] = {"production_percent": 0, "status": "proposal_sent"}
        return ctx

    def _stage_finance(self, ctx: dict, run_id: str) -> dict:
        proposal = ctx.get("proposal") or {}
        client_price = proposal.get("client_price_usd", 0)
        ctx["finance"] = {
            "deposit_status": "pending",
            "client_price_usd": client_price,
            "requires_human_approval": client_price > 5000,
        }
        return ctx

    def _use_llm(self, agent_id: str) -> bool:
        if not self.brain.config.get("pipeline", {}).get("fast_mode", True):
            return True
        return agent_id in self.brain.config.get("pipeline", {}).get("use_llm_for", [])

    def _company_profile(self, lead: dict) -> dict:
        text = lead.get("website_text_preview", "")
        return {
            "company_summary": lead.get("meta_description") or lead.get("search_snippet", ""),
            "products_services": self._products_from_text(text),
            "personalization_hooks": [lead.get("website_title", ""), lead.get("meta_description", "")],
            "source": "live_website_fetch",
            "product_images": lead.get("product_images") or [],
        }

    def _cache_lead_images(self, lead: dict, lead_id: str) -> list[dict]:
        candidates = lead.get("image_candidates") or []
        if not candidates and lead.get("website"):
            from src.tools.website import WebsiteFetcher
            site = WebsiteFetcher(timeout=10).fetch(lead["website"])
            candidates = site.get("image_candidates") or []
        if not candidates:
            return lead.get("product_images") or []
        return cache_product_images(
            candidates,
            lead_id,
            self.storage.data_dir,
            dashboard_base=self._dashboard_base(),
        )

    def _dashboard_base(self) -> str:
        from src.core.platform_urls import get_public_base_url

        return get_public_base_url(self.brain.config)

    def _products_from_text(self, text: str) -> list[str]:
        kws = ("tumbler", "drinkware", "lip balm", "bag", "apparel", "pen", "mug", "bottle", "hat", "shirt", "towel")
        found = [k for k in kws if k in text.lower()]
        return found[:5] or ["promotional products"]

    def _personalize(self, lead: dict, profile: dict) -> dict:
        from src.core.draft_composer import compose_personalization
        return compose_personalization(lead, profile)

    def _build_summary(self, ctx: dict, elapsed: float) -> dict:
        lead = ctx.get("top_lead", {})
        return {
            "status": "complete",
            "elapsed_seconds": elapsed,
            "lead": {
                "company": lead.get("company_name"),
                "website": lead.get("website"),
                "email": lead.get("email"),
                "score": lead.get("lead_score"),
            },
            "deal_id": ctx.get("deal_id"),
            "recommended_supplier": ctx.get("recommendation", {}).get("recommended_supplier"),
            "client_price_usd": ctx.get("proposal", {}).get("client_price_usd"),
            "outreach_subject": ctx.get("personalization", {}).get("subject_line"),
        }
