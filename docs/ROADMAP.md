# Six-Month Roadmap

> Live status: CRM → **Roadmap** page, or `GET /api/roadmap`

## Phase 0 — Foundation ✓ COMPLETED

- [x] Brain system (15 agents incl. email_drafter)
- [x] Core runtime, SQLite, activity log
- [x] CRM dashboard at `:8765`

---

## Phase 1 — Lead to Reply ✓ COMPLETED

| Item | Status | Where |
|------|--------|-------|
| Lead discovery | ✓ | Leads |
| Company research | ✓ | Leads |
| Personalization | ✓ | Hot Leads (draft composer) |
| Outreach drafts | ✓ | Hot Leads — review + send |
| Qualification | ✓ | Hot Leads |
| Human review gates | ✓ | Approve & send each step |

---

## Phase 2 — Sourcing Engine ✓ COMPLETED

| Item | Status | Where |
|------|--------|-------|
| Product research | ✓ | Hot Leads |
| Supplier discovery | ✓ | Suppliers |
| Verification | ✓ | Suppliers |
| RFQ automation | ✓ | Rich RFQ draft + review send |
| Email drafter agent | ✓ | Agents — pre-writes all emails |

---

## Phase 3 — Close the Deal ◐ IN PROGRESS

| Item | Status | Where |
|------|--------|-------|
| Quote comparison | ✓ | Tracking — clickable table |
| Proposal generation | ✓ | Tracking — full doc + client email |
| Tracking review UI | ✓ | All docs + supplier contact buttons |
| Order tracking | ✓ | Tracking |
| Email send (SMTP) | ◐ | Dry-run works; set SMTP in `.env` |
| Customer portal | ◐ | `/portal/{deal_id}` (no auth yet) |

---

## Phase 4 — SaaS Prep ○ PENDING

| Item | Status |
|------|--------|
| Multi-tenant model | ○ stub |
| Configurable verticals | ○ YAML only |
| API layer | ◐ internal REST |
| Billing schema | ○ no Stripe |

---

## Phase 5 — Scale & License ○ PENDING

| Item | Status |
|------|--------|
| Finance agent | ◐ rule-based |
| Support agent | ○ stub |
| Analytics export | ○ dashboard KPIs only |
| Licensing docs | ○ not written |

---

## What's next

1. Set `SMTP_*` in `.env` for live email send
2. Portal auth (magic links)
3. Multi-tenant + billing for SaaS
