"""Pipeline stage definitions and roadmap phases."""

from __future__ import annotations

from typing import Any

PIPELINE_STAGES: list[dict[str, Any]] = [
    {"id": "niche_finder", "num": 1, "label": "Niche Finder", "agent": "niche_finder", "gate": None},
    {"id": "lead_discovery", "num": 2, "label": "Lead Discovery", "agent": "lead_discovery", "gate": None},
    {"id": "company_research", "num": 3, "label": "Company Research", "agent": "company_research", "gate": None},
    {"id": "personalization", "num": 4, "label": "Personalization", "agent": "personalization", "gate": None},
    {"id": "outreach", "num": 5, "label": "Outreach", "agent": "outreach", "gate": "outreach_first_batch"},
    {"id": "qualification", "num": 6, "label": "Qualification", "agent": "qualification", "gate": None},
    {"id": "product_research", "num": 7, "label": "Product Research", "agent": "product_research", "gate": None},
    {"id": "supplier_discovery", "num": 8, "label": "Supplier Discovery", "agent": "supplier_discovery", "gate": None},
    {"id": "supplier_verification", "num": 9, "label": "Supplier Verification", "agent": "supplier_verification", "gate": "supplier_final_approval"},
    {"id": "rfq", "num": 10, "label": "RFQ Generation", "agent": "rfq", "gate": "rfq_send"},
    {"id": "quote_comparison", "num": 11, "label": "Quote Comparison", "agent": "quote_comparison", "gate": None},
    {"id": "proposal", "num": 12, "label": "Proposal", "agent": "proposal", "gate": "proposal_send"},
    {"id": "order_tracking", "num": 13, "label": "Order Tracking", "agent": "order_tracking", "gate": "contract_sign"},
    {"id": "finance", "num": 14, "label": "Finance", "agent": "finance", "gate": "payment_over_threshold"},
]

GATE_LABELS = {
    "outreach_first_batch": "Review outreach before sending",
    "supplier_final_approval": "Approve final supplier selection",
    "rfq_send": "Review RFQ before sending to suppliers",
    "proposal_send": "Review proposal before sending to client",
    "contract_sign": "Approve contract / PO",
    "payment_over_threshold": "Authorize payment",
}

# Each item: name, status (completed|in_progress|pending), ui_page (where in CRM), note
ROADMAP_PHASES: list[dict[str, Any]] = [
    {
        "id": "phase_0",
        "name": "Foundation",
        "status": "completed",
        "items": [
            {"name": "Brain system", "status": "completed", "ui_page": "agents", "note": "16 agents incl. niche_finder + email_drafter"},
            {"name": "Core runtime", "status": "completed", "ui_page": "pipeline", "note": "Orchestrator + fast engine"},
            {"name": "Logging", "status": "completed", "ui_page": "activity", "note": "SQLite + JSON audit trail"},
            {"name": "Dashboard", "status": "completed", "ui_page": "dashboard", "note": "CRM at :8765"},
        ],
    },
    {
        "id": "phase_1",
        "name": "Lead to Reply",
        "status": "completed",
        "items": [
            {"name": "Niche finder agent", "status": "completed", "ui_page": "agents", "note": "Picks top niche before lead search"},
            {"name": "Lead discovery", "status": "completed", "ui_page": "leads", "note": "DuckDuckGo + website fetch"},
            {"name": "Product image extraction", "status": "completed", "ui_page": "hot-leads", "note": "Images from buyer catalog pages"},
            {"name": "Company research", "status": "completed", "ui_page": "leads", "note": "Profile JSON per lead"},
            {"name": "Personalization", "status": "completed", "ui_page": "hot-leads", "note": "Draft composer agent"},
            {"name": "Outreach drafts", "status": "completed", "ui_page": "hot-leads", "note": "Review + send per lead"},
            {"name": "Qualification", "status": "completed", "ui_page": "hot-leads", "note": "Buyer requirements → deal"},
            {"name": "Human review gates", "status": "completed", "ui_page": "hot-leads", "note": "Approve & send at each step"},
        ],
    },
    {
        "id": "phase_2",
        "name": "Sourcing Engine",
        "status": "completed",
        "items": [
            {"name": "Product research", "status": "completed", "ui_page": "hot-leads", "note": "Spec + pricing range"},
            {"name": "Supplier discovery", "status": "completed", "ui_page": "suppliers", "note": "Alibaba/MIC search"},
            {"name": "Verification", "status": "completed", "ui_page": "suppliers", "note": "Trust score + match %"},
            {"name": "RFQ automation", "status": "completed", "ui_page": "hot-leads", "note": "Rich RFQ draft + review send"},
            {"name": "Email drafter agent", "status": "completed", "ui_page": "agents", "note": "All emails pre-written for review"},
        ],
    },
    {
        "id": "phase_3",
        "name": "Close the Deal",
        "status": "in_progress",
        "items": [
            {"name": "Quote comparison", "status": "completed", "ui_page": "tracking", "note": "Clickable comparison table"},
            {"name": "Proposal generation", "status": "completed", "ui_page": "tracking", "note": "Full doc + client email draft"},
            {"name": "Tracking review UI", "status": "completed", "ui_page": "tracking", "note": "All docs + supplier contact"},
            {"name": "Order tracking", "status": "completed", "ui_page": "tracking", "note": "Production milestones"},
            {"name": "Email send (SMTP)", "status": "in_progress", "ui_page": "hot-leads", "note": "Dry-run works; set SMTP in .env"},
            {"name": "Customer portal", "status": "in_progress", "ui_page": "portal", "note": "Read-only /portal/{deal_id}"},
        ],
    },
    {
        "id": "phase_4",
        "name": "SaaS Prep",
        "status": "pending",
        "items": [
            {"name": "Multi-tenant model", "status": "pending", "ui_page": None, "note": "Stub in src/saas/"},
            {"name": "Configurable verticals", "status": "pending", "ui_page": None, "note": "brain/config.yaml only"},
            {"name": "API layer", "status": "in_progress", "ui_page": None, "note": "REST for CRM — no public API keys"},
            {"name": "Billing schema", "status": "pending", "ui_page": None, "note": "Plans defined, no Stripe"},
        ],
    },
    {
        "id": "phase_5",
        "name": "Scale & License",
        "status": "pending",
        "items": [
            {"name": "Finance agent", "status": "in_progress", "ui_page": "tracking", "note": "Rule-based — no invoicing"},
            {"name": "Support agent", "status": "pending", "ui_page": None, "note": "customer_support agent stub"},
            {"name": "Analytics export", "status": "pending", "ui_page": "dashboard", "note": "Revenue KPIs only"},
            {"name": "Licensing docs", "status": "pending", "ui_page": "roadmap", "note": "Not written"},
        ],
    },
]

# CRM navigation map (single source — no duplicate pages)
CRM_PAGES = [
    {"id": "dashboard", "label": "Dashboard", "roadmap_phases": ["phase_0"], "purpose": "KPIs, revenue, pipeline quick-run"},
    {"id": "leads", "label": "Leads", "roadmap_phases": ["phase_1"], "purpose": "All discovered buyers"},
    {"id": "hot-leads", "label": "Hot Leads", "roadmap_phases": ["phase_1", "phase_2"], "purpose": "AI sourcing workflow (replaces old Deals page)"},
    {"id": "tracking", "label": "Tracking", "roadmap_phases": ["phase_1", "phase_3", "phase_5"], "purpose": "Post-proposal human review & fulfillment"},
    {"id": "closed-deals", "label": "Closed", "roadmap_phases": ["phase_3"], "purpose": "Won deals archive"},
    {"id": "suppliers", "label": "Suppliers", "roadmap_phases": ["phase_2"], "purpose": "Manufacturer catalog"},
    {"id": "agents", "label": "AI Agents", "roadmap_phases": ["phase_0"], "purpose": "Agent health & test"},
    {"id": "activity", "label": "Activity", "roadmap_phases": ["phase_0"], "purpose": "Audit log"},
    {"id": "pipeline", "label": "Pipeline", "roadmap_phases": ["phase_0"], "purpose": "Batch pipeline runner"},
    {"id": "roadmap", "label": "Roadmap", "roadmap_phases": [], "purpose": "Build progress"},
]

# External services required for full production operation
INTEGRATIONS_NEEDED: list[dict[str, Any]] = [
    # Lead to Reply
    {"phase": "Lead to Reply", "name": "Email delivery (SMTP / SendGrid / Resend)", "priority": "critical",
     "description": "Send outreach, follow-ups, and proposal emails from drafts.", "blocker": "Dry-run mode — set SMTP_* in .env"},
    {"phase": "Lead to Reply", "name": "LinkedIn / CRM sync (optional)", "priority": "medium",
     "description": "Push personalized drafts or log replies from LinkedIn Sales Navigator.", "blocker": None},
    {"phase": "Lead to Reply", "name": "Inbound email webhook", "priority": "high",
     "description": "Parse buyer replies into qualification agent automatically.", "blocker": "Manual qualification"},
    # Sourcing Engine
    {"phase": "Sourcing Engine", "name": "Alibaba / MIC API or licensed data feed", "priority": "high",
     "description": "Reliable supplier search beyond DuckDuckGo snippets.", "blocker": "Search-based discovery"},
    {"phase": "Sourcing Engine", "name": "RFQ email to suppliers", "priority": "high",
     "description": "Email generated RFQs and track supplier responses.", "blocker": "Review UI ready — SMTP for live send"},
    {"phase": "Sourcing Engine", "name": "WhatsApp Business API", "priority": "medium",
     "description": "Contact suppliers on WhatsApp from supplier cards.", "blocker": "wa.me links only"},
    {"phase": "Sourcing Engine", "name": "LLM provider (Ollama / OpenAI)", "priority": "high",
     "description": "Real AI analysis when fast_mode is disabled.", "blocker": "Rule-based fallbacks"},
    # Close the Deal
    {"phase": "Close the Deal", "name": "E-signature (DocuSign / PandaDoc)", "priority": "medium",
     "description": "Contract sign gate before order tracking.", "blocker": "Manual approval"},
    {"phase": "Close the Deal", "name": "Customer portal auth (magic link)", "priority": "high",
     "description": "Secure read-only order status for buyers.", "blocker": "Public deal ID only"},
    {"phase": "Close the Deal", "name": "Payment processor (Stripe / Wise)", "priority": "high",
     "description": "Collect deposits and final payment; feed finance agent.", "blocker": "Manual finance"},
    # SaaS Prep
    {"phase": "SaaS Prep", "name": "Multi-tenant database isolation", "priority": "critical",
     "description": "Org-scoped data, users, and config per customer.", "blocker": "Single tenant"},
    {"phase": "SaaS Prep", "name": "User authentication (OAuth / Clerk)", "priority": "critical",
     "description": "Login for CRM dashboard and API keys.", "blocker": "No auth on CRM"},
    {"phase": "SaaS Prep", "name": "Public REST API + API keys", "priority": "high",
     "description": "External systems trigger pipeline stages.", "blocker": "Internal REST only"},
    {"phase": "SaaS Prep", "name": "Stripe Billing", "priority": "high",
     "description": "Subscription plans and usage metering.", "blocker": "Schema only"},
    {"phase": "SaaS Prep", "name": "Configurable vertical packs", "priority": "medium",
     "description": "Swap agent prompts and product categories per tenant.", "blocker": "YAML edit"},
    # Scale & License
    {"phase": "Scale & License", "name": "Accounting export (QuickBooks / Xero)", "priority": "medium",
     "description": "Sync invoices and payments from finance agent.", "blocker": None},
    {"phase": "Scale & License", "name": "Support ticketing (Zendesk / Intercom)", "priority": "low",
     "description": "Route customer_support agent to real tickets.", "blocker": "Agent stub"},
    {"phase": "Scale & License", "name": "Analytics export (CSV / BI webhook)", "priority": "medium",
     "description": "Export leads, deals, revenue for reporting.", "blocker": "Dashboard KPIs only"},
    {"phase": "Scale & License", "name": "Calendar scheduling (Cal.com)", "priority": "low",
     "description": "Book calls from Tracking suggested actions.", "blocker": "Manual call"},
    # Infrastructure
    {"phase": "Infrastructure", "name": "Production hosting (VPS / cloud)", "priority": "high",
     "description": "Deploy FastAPI + SQLite/Postgres beyond localhost.", "blocker": "Local only"},
    {"phase": "Infrastructure", "name": "PostgreSQL (replace SQLite)", "priority": "medium",
     "description": "Concurrent writes and multi-tenant scale.", "blocker": "SQLite"},
    {"phase": "Infrastructure", "name": "Background job queue (Redis / Celery)", "priority": "medium",
     "description": "Long-running pipeline and email jobs off HTTP thread.", "blocker": "Threading"},
]


def stage_by_id(stage_id: str) -> dict[str, Any] | None:
    for s in PIPELINE_STAGES:
        if s["id"] == stage_id:
            return s
    return None
