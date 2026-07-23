# Integration Checklist

Items required to make the AI Procurement OS fully functional in production.  
The CRM dashboard shows live status on **Roadmap → Integrations Needed**; this doc is the full reference.

## Current state

| Area | Built today | Missing for production |
|------|-------------|------------------------|
| Lead discovery | DuckDuckGo + website fetch | Paid lead APIs, CRM import |
| Outreach | Drafts in DB | Email send + reply parsing |
| Sourcing | Supplier search + RFQ body | RFQ email + quote inbox |
| Proposals | Generated + human review | Client email delivery |
| Tracking | Internal CRM page | Secure client portal auth |
| Finance | Rule-based milestones | Invoicing + payments |
| SaaS | Single-tenant SQLite | Multi-tenant + billing |

---

## Phase 1 — Lead to Reply

| Priority | Integration | Purpose | Env / config |
|----------|-------------|---------|--------------|
| **Critical** | Email delivery (SMTP, SendGrid, or Resend) | Send outreach and follow-ups from drafts | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASS` or `SENDGRID_API_KEY` |
| **High** | Inbound email webhook (SendGrid Inbound / Mailgun) | Auto-qualify buyers from replies | Webhook URL + parser in `qualification` agent |
| Medium | LinkedIn / Sales Navigator export | Import leads without scraping ToS risk | CSV upload endpoint |
| Medium | Google Workspace / Microsoft 365 OAuth | Send as user's mailbox | OAuth client credentials |

**Unlocks:** Outreach drafts → sent campaigns; qualification from real replies.

---

## Phase 2 — Sourcing Engine

| Priority | Integration | Purpose | Env / config |
|----------|-------------|---------|--------------|
| **Critical** | RFQ email to suppliers | Deliver generated RFQs | Same email provider as Phase 1 |
| **High** | LLM provider (Ollama local or OpenAI API) | Disable `fast_mode` fallbacks | `OLLAMA_HOST` or `OPENAI_API_KEY` in `.env` |
| **High** | Alibaba / Made-in-China API or licensed feed | Reliable supplier data | Vendor API keys |
| Medium | WhatsApp Business API | Supplier messaging at scale | Meta Business API token |
| Low | Freight / shipping quote API | Landed cost in proposals | Flexport, Freightos, etc. |

**Unlocks:** End-to-end RFQ cycle with real supplier quotes logged.

---

## Phase 3 — Close the Deal

| Priority | Integration | Purpose | Env / config |
|----------|-------------|---------|--------------|
| **High** | Customer portal auth (magic link / JWT) | Secure `/portal/{deal_id}` | `PORTAL_SECRET`, signed tokens |
| **High** | Payment processor (Stripe or Wise) | Deposits and final payment | `STRIPE_SECRET_KEY`, webhook |
| Medium | E-signature (DocuSign, PandaDoc) | Contract sign gate | API key + webhook |
| Medium | Proposal PDF generation | Branded client deliverable | WeasyPrint or external service |

**Built stub:** Read-only portal at `/portal/{deal_id}` (no auth yet). Copy link from **Tracking** page.

**Unlocks:** Client self-service status; automated payment → finance agent.

---

## Phase 4 — SaaS Prep

| Priority | Integration | Purpose | Notes |
|----------|-------------|---------|-------|
| **Critical** | User authentication (Clerk, Auth0, or custom JWT) | Protect CRM dashboard | No login today |
| **Critical** | Multi-tenant data isolation | One install, many agencies | Stub in `src/saas/` |
| **High** | Public REST API + API keys | External triggers | Internal REST only |
| **High** | Stripe Billing | Subscription plans | Schema defined, not wired |
| Medium | Configurable vertical packs | Per-tenant agent prompts | `brain/config.yaml` only |

**Unlocks:** Sell platform as SaaS; second tenant on same host.

---

## Phase 5 — Scale & License

| Priority | Integration | Purpose |
|----------|-------------|---------|
| Medium | Accounting export (QuickBooks, Xero) | Sync invoices from finance agent |
| Medium | Analytics export (CSV, webhook to BI) | Beyond dashboard KPIs |
| Low | Support ticketing (Zendesk, Intercom) | `customer_support` agent |
| Low | Calendar (Cal.com) | Book calls from Tracking suggestions |
| Low | Licensing / white-label docs | Partner resale |

---

## Infrastructure (all phases)

| Priority | Integration | Purpose |
|----------|-------------|---------|
| **High** | Production hosting (VPS, Railway, Fly.io) | Not localhost-only |
| Medium | PostgreSQL | Replace SQLite for concurrency |
| Medium | Redis + job queue (Celery, RQ) | Long pipeline off HTTP thread |
| Medium | Object storage (S3) | Proposals, attachments |
| Low | Monitoring (Sentry, Datadog) | Agent failures and API errors |

---

## Recommended integration order

1. **Email send** — unblocks outreach, RFQ, and proposals  
2. **Inbound email** — closes the reply loop for qualification  
3. **LLM provider** — real AI when `fast_mode: false`  
4. **Portal auth + Stripe** — client-facing close-the-deal flow  
5. **Auth + multi-tenant** — SaaS readiness  
6. **PostgreSQL + queue** — scale beyond single operator  

---

## CRM pages (no duplicates)

| Page | Roadmap phases | Role |
|------|----------------|------|
| Dashboard | Foundation | KPIs, quick-run |
| Leads | Lead to Reply | All buyers |
| Hot Leads | Lead to Reply, Sourcing | AI workflow (**replaces old Deals page**) |
| Tracking | Lead to Reply, Close, Finance | Post-proposal human review |
| Closed | Close the Deal | Won deals archive |
| Suppliers | Sourcing | Manufacturer catalog |
| Agents | Foundation | Agent health |
| Activity | Foundation | Audit log |
| Pipeline | Foundation | Batch runner |
| Roadmap | — | Progress + this checklist |

---

## Quick env template

```env
# Email (Phase 1 & 2)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
SENDGRID_API_KEY=

# AI (Phase 2)
OLLAMA_HOST=http://127.0.0.1:11434
OPENAI_API_KEY=

# Payments (Phase 3)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=

# Portal (Phase 3)
PORTAL_SIGNING_SECRET=

# Auth (Phase 4)
CLERK_SECRET_KEY=
```

See `.env.example` for values already used by the platform.
