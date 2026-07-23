# Vision: AI Procurement Operating System

## What We Are Building

Not a trading company that uses AI tools.

An **AI sourcing platform** that earns revenue by brokering manufacturing deals — with the software itself as a licensable asset.

## Two Businesses, One Platform

| Business | Revenue Model | Purpose |
|----------|---------------|---------|
| **Sourcing Agency** | Margin per transaction | Immediate cash flow, proves the system |
| **SaaS Platform** | Subscription (future) | Recurring revenue, scalable without headcount |

The agency runs on the same platform the SaaS product will eventually sell.

## Operating Model

Run with **3–5 people** instead of 30. Humans step in only when money, negotiations, or contracts require judgment.

```
Buyer Request
      │
      ▼
AI Sales Agent
      │
      ▼
AI Qualification Agent
      │
      ▼
AI Product Research
      │
      ▼
AI Supplier Research
      │
      ▼
AI RFQ Generator
      │
      ▼
AI Quote Comparison
      │
      ▼
Human Approval  ◄── money, contracts, disputes
      │
      ▼
Factory → Shipping → Customer
```

## Human-Only Steps

- Final supplier approval
- Contract review
- Major commercial negotiations
- Sample evaluation and QC decisions
- Dispute resolution
- Large payment authorization
- Strategic account management

## North Star

A buyer types: *"I need 20,000 custom water bottles delivered to Texas."*

Within minutes the system:

1. Finds qualified manufacturers
2. Drafts RFQs
3. Collects and compares quotations
4. Flags supplier risks
5. Generates a professional proposal
6. Tracks the order after placement

## Local-First (Phase 0)

Everything runs on your machine:

- Local LLM via Ollama (or API fallback)
- SQLite database
- File-based document storage
- Structured JSON logs for audit and future changes
- No cloud dependency required to operate
