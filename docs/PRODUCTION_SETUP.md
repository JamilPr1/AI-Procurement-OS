# Production Setup Guide — AI Procurement OS

This guide covers everything needed to run the full MVP in production.

## Quick start (5 minutes)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy environment file
copy .env.example .env        # Windows
# cp .env.example .env        # Mac/Linux

# 3. Start Ollama (for local AI — free, no API key)
ollama serve
ollama pull llama3.2:1b

# 4. Seed demo data + credentials doc
python -m src.main seed-demo
python -m src.main credentials

# 5. Start the platform
python -m src.main dashboard
```

Open:
- **CRM:** http://127.0.0.1:8765
- **Demo store:** http://127.0.0.1:8765/store?tenant=demo
- **Marketing:** http://127.0.0.1:8765/marketing
- **Credentials:** `docs/PLATFORM_CREDENTIALS.docx`

---

## System architecture

```
Customer Store (/store)  →  AI quote + order  →  CRM Tracking
CRM Discover Leads     →  Hot Leads pipeline  →  Tracking  →  Closed
SaaS Tenants (/saas)   →  Branded stores per customer
```

### CRM workflow (fully automated)

1. **Dashboard → Discover Leads** — finds 20 US buyers via web search
2. **Hot Leads → Next Step** — AI runs each stage automatically:
   - Personalization → Outreach email (auto-sent)
   - Supplier discovery → RFQ (auto-sent)
   - Quote comparison → Proposal (auto-sent)
3. **Tracking** — deal appears after proposal is sent
4. **Closed** — manually close won deals

No manual approval gates. Set `AUTO_APPROVE=false` in `.env` only if you want human review back.

---

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `AUTO_APPROVE` | No | `true` | Skip all human approval gates |
| `EMAIL_DRY_RUN` | No | `true` if no SMTP | Log emails without sending |
| `SMTP_HOST` | For live email | — | SMTP server hostname |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | For live email | — | SMTP username |
| `SMTP_PASS` | For live email | — | SMTP password / app password |
| `SMTP_FROM` | No | `SMTP_USER` | From address |
| `OLLAMA_BASE_URL` | No | `http://localhost:11434` | Local LLM endpoint |
| `LLM_MODEL` | No | `llama3.2:1b` | Model name |
| `OPENAI_API_KEY` | Optional | — | Cloud LLM fallback |

---

## Email setup (Gmail example)

1. Enable 2FA on your Google account
2. Create an App Password: Google Account → Security → App passwords
3. Add to `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=xxxx-xxxx-xxxx-xxxx
SMTP_FROM=you@gmail.com
EMAIL_DRY_RUN=false
AUTO_APPROVE=true
```

4. Verify: `GET http://127.0.0.1:8765/api/email/status` → `configured: true, dry_run: false`

---

## SaaS multi-tenant stores

Each tenant gets a branded AI Product Finder store:

| Tenant | Store URL |
|--------|-----------|
| Demo | `/store?tenant=demo` |
| Promo Pros | `/store?tenant=promo-pros` |
| Gift Hub | `/store?tenant=gift-hub` |

Manage tenants: CRM → **SaaS Platform** (`/#saas`)

Demo logins are in `docs/PLATFORM_CREDENTIALS.docx`.

---

## CLI commands

```bash
python -m src.main status          # Health check
python -m src.main dashboard       # Start web server
python -m src.main seed-demo       # Seed tenants + demo orders
python -m src.main credentials     # Regenerate Word credentials doc
python -m src.main execute         # Full batch pipeline (CLI)
python -m src.main reset           # Clear all leads/deals
```

---

## Production checklist

- [ ] Ollama running with `llama3.2:1b` pulled
- [ ] `.env` copied from `.env.example`
- [ ] `AUTO_APPROVE=true` set
- [ ] SMTP configured (or `EMAIL_DRY_RUN=true` for testing)
- [ ] `python -m src.main seed-demo` run once
- [ ] `python -m src.main status` passes without errors
- [ ] Dashboard loads at http://127.0.0.1:8765
- [ ] Store loads at http://127.0.0.1:8765/store?tenant=demo
- [ ] Discover Leads finds buyers
- [ ] Hot Leads → Run Full Pipeline sends proposal to Tracking

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `/store` returns 404 | Old server running — kill port 8765, restart dashboard |
| No leads found | Check internet; run `python -m src.main execute` |
| Emails not sending | Set SMTP vars + `EMAIL_DRY_RUN=false` |
| `status` command crashes | Fixed in latest — update and retry |
| Port 8765 in use | `Get-NetTCPConnection -LocalPort 8765` then kill process |

---

## File locations

| Path | Purpose |
|------|---------|
| `brain/config.yaml` | Agency settings, discovery limits, SaaS plans |
| `.env` | Secrets and runtime overrides |
| `data/platform.db` | SQLite database |
| `data/` | JSON artifacts (proposals, outreach, etc.) |
| `docs/PLATFORM_CREDENTIALS.docx` | All login credentials |
