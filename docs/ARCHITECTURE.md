# Architecture

## Stack (Local-First)

| Layer | Technology | Why |
|-------|------------|-----|
| Runtime | Python 3.11+ | Agent orchestration, data extraction |
| LLM | Ollama (local) | Privacy, no API cost, offline capable |
| Database | SQLite | Zero setup, portable, single file |
| Storage | JSON/YAML files | Human-readable, versionable |
| Logs | Structured JSON | Machine-parseable change history |
| Config | YAML | Agent definitions, workflows, policies |

## Directory Layout

```
Trading/
├── brain/                  # Project intelligence ("the brain")
│   ├── config.yaml         # Global settings
│   ├── agents/             # Agent role definitions
│   ├── prompts/            # Prompt templates per agent
│   ├── workflows/          # Pipeline stage definitions
│   └── policies/           # Human-in-the-loop rules
├── src/
│   ├── core/               # Brain loader, logger, storage, LLM
│   ├── agents/             # Agent runtime implementations
│   ├── agency/             # Transaction business (deals, margins)
│   └── saas/               # Multi-tenant prep (orgs, seats)
├── data/                   # Runtime data (local, gitignored)
│   ├── leads/
│   ├── companies/
│   ├── products/
│   ├── suppliers/
│   ├── rfqs/
│   ├── quotes/
│   ├── proposals/
│   └── orders/
├── logs/                   # Audit trail
│   ├── changes/            # What changed and why
│   ├── agents/             # Per-agent execution logs
│   └── system/             # Startup, errors, health
└── docs/                   # Planning and reference
```

## The Brain

The brain is the single source of truth for how the system thinks and behaves.

| Component | Purpose |
|-----------|---------|
| `config.yaml` | LLM model, paths, business defaults, verticals |
| `agents/*.yaml` | Role, inputs, outputs, tools, escalation rules |
| `prompts/*.md` | System and task prompts (editable without code) |
| `workflows/*.yaml` | Stage order, handoffs, required fields |
| `policies/human_gate.yaml` | When to pause for human approval |

Agents read from the brain at runtime. Changing a prompt or workflow does not require redeploying code.

## Dual-Business Separation

```
┌─────────────────────────────────────────────────┐
│                   PLATFORM CORE                  │
│  brain · logger · storage · LLM · orchestrator   │
└─────────────────────┬───────────────────────────┘
                      │
        ┌─────────────┴─────────────┐
        ▼                           ▼
┌───────────────┐           ┌───────────────┐
│    AGENCY     │           │     SAAS      │
│  (tenant: us) │           │ (multi-tenant)│
│               │           │               │
│ deals         │           │ organizations │
│ margins       │           │ subscriptions │
│ our pipeline  │           │ white-label   │
└───────────────┘           └───────────────┘
```

Agency is tenant #1. SaaS modules are stubbed now but share the same core.

## Pipeline Stages

| Stage | Agent | Output |
|-------|-------|--------|
| 1 | Lead Discovery | Scored lead list |
| 2 | Company Research | Company profile |
| 3 | Personalization | Custom outreach copy |
| 4 | Outreach | Sent messages, follow-up queue |
| 5 | Qualification | Structured buyer requirements |
| 6 | Product Research | Product spec, pricing bands |
| 7 | Supplier Discovery | Factory shortlist |
| 8 | Supplier Verification | Risk flags, trust score |
| 9 | RFQ | Sent RFQs, tracking IDs |
| 10 | Quote Comparison | Ranked quotes, recommendation |
| 11 | Proposal | Client-ready proposal draft |
| 12 | Order Tracking | Production/shipping milestones |
| 13 | Finance | Invoices, payments status |
| 14 | Customer Support | Status answers (portal-ready) |

## Logging Strategy

Every meaningful action writes to `logs/`:

- **changes/** — entity created/updated/deleted with before/after
- **agents/** — agent run: inputs, outputs, duration, model used
- **system/** — startup, config load, errors

Log format: JSON lines (one object per line) for grep and future analytics.

## LLM Abstraction

```
Local (default)  →  Ollama at localhost:11434
API (optional)   →  OpenAI / Anthropic via .env
```

Switch provider in `brain/config.yaml` without touching agent code.

## Security (Local)

- `.env` for API keys (never committed)
- `data/` gitignored (PII, deal data)
- Human gates enforced in policy layer, not optional in agents
