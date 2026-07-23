# Going Live — Hostinger, Vercel & Alternatives

This platform is a **Python FastAPI application** with SQLite, static web files, and optional local/cloud LLM. Choose hosting that supports a **persistent Python process** and **writable disk** (or migrate DB to PostgreSQL).

---

## Quick recommendation

| Option | Fit | Verdict |
|--------|-----|---------|
| **Hostinger VPS** | Full control, your domain, always-on server | **Best choice** for this stack |
| **Railway / Render / Fly.io** | Managed Python + Postgres | Easiest managed deploy |
| **Hostinger shared hosting** | PHP/WordPress focused | **Not recommended** for FastAPI |
| **Vercel** | Serverless / static / Next.js | **Not recommended** as-is |

---

## Option A — Hostinger VPS (recommended)

### What you need
- Hostinger **VPS** plan (KVM) — not basic shared hosting
- A domain pointed to the VPS IP
- SSH access

### Steps

1. **Create VPS** in Hostinger hPanel → choose Ubuntu 22.04.

2. **Point domain** — DNS A record `@` and `www` → VPS IP.

3. **SSH into server** and install dependencies:
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx git
```

4. **Upload or clone** your project:
```bash
git clone <your-repo-url> /var/www/trading
cd /var/www/trading
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5. **Configure environment**:
```bash
cp .env.example .env
# Edit .env: SMTP, OPENAI_API_KEY or Ollama URL, AUTO_APPROVE, etc.
python -m src.main seed-demo
python -m src.main credentials
```

6. **Run as a systemd service** — create `/etc/systemd/system/aiprocurement.service`:
```ini
[Unit]
Description=AI Procurement OS
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/trading
Environment="PATH=/var/www/trading/.venv/bin"
ExecStart=/var/www/trading/.venv/bin/python -m src.main dashboard --host 0.0.0.0 --port 8765
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable aiprocurement
sudo systemctl start aiprocurement
```

7. **Nginx reverse proxy** — `/etc/nginx/sites-available/aiprocurement`:
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/aiprocurement /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

8. **Update credentials doc** with your live domain:
```bash
python -m src.main credentials --host yourdomain.com --port 443
# Or if using HTTP on 80: --host yourdomain.com --port 80
```

9. **Firewall** — allow 80, 443, 22 only:
```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
```

### Hostinger MCP (optional)
If you use Hostinger MCP in Cursor, you can manage DNS records and check domain forwarding from the IDE — but the app itself still runs on your VPS via the steps above.

---

## Option B — Vercel (not recommended without refactor)

**Why it doesn't fit today:**
- App is **FastAPI + Uvicorn**, not Next.js
- **SQLite** needs a persistent filesystem; Vercel serverless functions are ephemeral
- Long-running AI/quote sessions may hit serverless timeouts

**If you still want Vercel later:**
1. Split frontend (static HTML/JS) → Vercel static deploy
2. Move API → Railway/Render/Fly or Hostinger VPS
3. Replace SQLite with **PostgreSQL**
4. Use environment variables for secrets on both sides

For a **quick marketing-only site**, you could deploy `landing.html` + static assets to Vercel, but the **store, CRM, and AI backend must live elsewhere**.

---

## Option C — Railway / Render (easiest managed)

### Railway
1. Connect GitHub repo
2. Set start command: `python -m src.main dashboard --host 0.0.0.0 --port $PORT`
3. Add env vars from `.env.example`
4. Add **PostgreSQL** plugin (requires code change from SQLite for production)
5. Map custom domain in Railway dashboard

### Render
1. New **Web Service** → Python
2. Build: `pip install -r requirements.txt`
3. Start: `python -m src.main dashboard --host 0.0.0.0 --port $PORT`
4. Add disk for SQLite (Render persistent disk) or use Postgres

---

## Production checklist before go-live

- [ ] Change all demo passwords (`Admin2026!`, etc.)
- [ ] Set `EMAIL_DRY_RUN=false` and configure SMTP
- [ ] Use HTTPS (Let's Encrypt via Certbot on VPS)
- [ ] Back up `data/platform.db` daily
- [ ] Set `OPENAI_API_KEY` or run Ollama on the same VPS
- [ ] Regenerate docs: `python -m src.main credentials --host yourdomain.com`
- [ ] Test: landing, login, `/app`, `/store?tenant=demo`

---

## Documents for clients

| File | Purpose |
|------|---------|
| `docs/CLIENT_PRESENTATION.pdf` | Client-facing deck (run `python -m src.main presentation`) |
| `docs/PLATFORM_CREDENTIALS.docx` | Internal logins (confidential) |
| `docs/PRODUCTION_SETUP.md` | Technical setup reference |

---

## Summary

**Use Hostinger VPS** if you already have Hostinger — it's the straightest path to a live domain with full platform features. **Skip Vercel** unless you refactor to a split frontend/API architecture. **Railway/Render** are good if you prefer managed hosting over server admin.
