# AI Procurement Platform — Credentials (template)

> Copy structure only. Run `python -m src.main credentials` after `seed-demo` to generate real local credentials.
> **Never commit the generated `PLATFORM_CREDENTIALS.docx` or `.md` to a public repository.**

## Platform URLs

| URL | Link |
|-----|------|
| Landing | http://127.0.0.1:8765 |
| CRM Login | http://127.0.0.1:8765/login |
| CRM Dashboard | http://127.0.0.1:8765/app |
| Marketing | http://127.0.0.1:8765/marketing |

## Super Admin

- **Email:** `admin@yourdomain.local`
- **Password:** *(set during seed-demo)*
- **Role:** superadmin

## Tenant Admin Logins

| Tenant | Email | Password |
|--------|-------|----------|
| Demo Store | `demo@store.local` | *(see seed-demo output)* |
| Promo Pros Inc | `ops@promopros.demo` | *(see seed-demo output)* |

## Demo Stores

- Demo Store — `/store?tenant=demo`
- Promo Pros Inc — `/store?tenant=promo-pros`
- Gift Hub Agency — `/store?tenant=gift-hub`
- Merch Direct Co — `/store?tenant=merch-direct`
- Event Swag Solutions — `/store?tenant=event-swag`

## Generate locally

```bash
python -m src.main seed-demo
python -m src.main credentials
python -m src.main presentation
```
