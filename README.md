# AI Procurement OS

An AI-powered sourcing platform that earns on transactions today and becomes licensable SaaS tomorrow.

**Not** a trading company with AI bolted on — a procurement operating system where the agency is tenant #1.

## Two Businesses, One Codebase

| Business | Model | Status |
|----------|-------|--------|
| Sourcing Agency | Margin per deal | Active (Phase 0) |
| SaaS Platform | Subscription | Stubbed (Phase 4) |

## Quick Start (Local)

### 1. Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed (optional in fast mode — no LLM calls by default)

### 2. Install

```bash
cd d:\Trading
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Launch CRM Dashboard (recommended)

```bash
python -m src.main dashboard
```

Open **http://127.0.0.1:8765** — full CRM with:

- **Sidebar navigation** — Dashboard, Leads, Hot Leads, Tracking, Closed, Suppliers, Agents, Activity Log, Pipeline, Roadmap
- **Persistent data** — all leads/deals/suppliers saved in SQLite (survives refresh)
- **Deduplication** — same company domain never duplicated; existing leads get updated
- **Human gate approvals** — notification banner + Approve & Continue
- **AI Agent fleet** — see which agent is running in real time

### 4. CLI Pipeline (~17 seconds, auto-approve gates)

```bash
python -m src.main execute
```

With human gates (approve in dashboard):

```bash
python -m src.main execute --require-human-gates
```

### 5. Verify

```bash
python -m src.main status
```

## Project Structure

```
brain/          The "brain" — config, agents, prompts, workflows, policies
src/core/       Runtime: brain loader, logger, storage, LLM, orchestrator
src/agency/     Transaction business (margins, deals)
src/saas/       Multi-tenant prep (future)
data/           Local SQLite + JSON entities (gitignored)
logs/           Structured audit logs (changes, agents, system)
docs/           Vision, architecture, roadmap
```

## The Brain

Edit behavior without touching Python:

- `brain/config.yaml` — LLM, vertical, scoring weights, agency settings
- `brain/agents/*.yaml` — Agent roles, inputs/outputs, tools
- `brain/prompts/*.md` — System prompts (version in git)
- `brain/workflows/*.yaml` — Pipeline stage order
- `brain/policies/human_gate.yaml` — When humans must approve

## Logging

All changes and agent runs are logged as JSON:

- `logs/changes/` — Entity created/updated/deleted
- `logs/agents/` — Agent execution history
- `logs/system/` — Platform events

## Docs

- [Vision](docs/VISION.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Getting Started](docs/GETTING_STARTED.md)
- [Production Setup](docs/PRODUCTION_SETUP.md)
- [Deployment Guide](docs/DEPLOYMENT.md)

## CLI Commands

| Command | Description |
|---------|-------------|
| `python -m src.main status` | Health check, stats, agent list |
| `python -m src.main pipeline` | Show full sourcing pipeline |
| `python -m src.main agents` | List agents and prompt status |
| `python -m src.main execute` | Fast pipeline (~17s, live web data) |
| `python -m src.main execute --require-human-gates` | Pipeline with approval pauses |
| `python -m src.main dashboard` | Web dashboard at http://127.0.0.1:8765 |
| `python -m src.main seed-demo` | Seed partner tenants, stores, and demo users |
| `python -m src.main credentials` | Generate local credentials doc (not committed) |
| `python -m src.main presentation` | Generate client PDF presentation |

## Partner Storefronts

Public demo stores (after `seed-demo`):

- `/store?tenant=demo` — Demo Store
- `/store?tenant=promo-pros` — Promo Pros (drinkware)
- `/store?tenant=gift-hub` — Gift Hub (corporate gifts)
- `/store?tenant=merch-direct` — Merch Direct (workwear & safety)
- `/store?tenant=event-swag` — Event Swag (conference swag)

## Deployment

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for Hostinger VPS, Railway, and production checklist.

## Human-Only Steps

Final supplier approval, contracts, major negotiations, sample QC, disputes, large payments, strategic accounts — enforced via `brain/policies/human_gate.yaml`.

## Next Steps (Phase 1)

1. Install Ollama model matching `brain/config.yaml`
2. Import first lead CSV into `data/leads/`
3. Run lead_discovery → personalization → outreach (draft mode)
4. Validate qualification agent with real buyer replies
