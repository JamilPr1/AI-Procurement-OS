# Team Marketing Guide

**Product:** AI Procurement OS — white-label sourcing platform for promo distributors  
**Live site:** https://ai-procurement-os.onrender.com

---

## Say this in 15 seconds

> "We help promotional product distributors go from buyer research to factory quotes to client proposals in one system. Each client gets their own branded online quote store."

---

## Links to share (use these everywhere)

| What | Link |
|------|------|
| **Demo store** (share most) | https://ai-procurement-os.onrender.com/store?tenant=demo |
| Free pilot signup | https://ai-procurement-os.onrender.com/#get-started |
| Pricing | https://ai-procurement-os.onrender.com/marketing |

---

## Who to contact

- Promotional product distributors (1–20 people)
- Marketing agencies that source merch for clients
- Corporate gifting & event swag companies

**Find them on:** LinkedIn ("promotional products distributor"), Facebook promo groups, Google Maps.

---

## Pricing

| Plan | Price | Includes |
|------|-------|----------|
| Starter | $99/mo | 3 users, 10 deals, branded store |
| Growth | $299/mo | 10 users, 50 deals |
| **Pilot** | **Free 14 days** | **Lead with this — not price** |

Founding partner: **$79/mo** for first 10 clients (optional urgency offer).

---

## Daily routine (30 min)

1. **Send 3 messages** — use template below  
2. **Follow up 2 old leads** — "Just checking if you had a chance to see the demo?"  
3. **Post or comment once** — share demo store link  

**Month 1 goal:** 50 outreaches → 5 demos → 2 paying clients

---

## Cold email (copy & personalize)

**Subject:** Quick question about [Company]

```
Hi [Name],

How does your team handle RFQs and client proposals today?

We built a sourcing platform for promo distributors — CRM, supplier matching,
and a branded quote store per client.

Live demo (no login): https://ai-procurement-os.onrender.com/store?tenant=demo

Worth a 15-min look this week?

[Your name]
```

---

## LinkedIn DM (after connecting)

```
Thanks for connecting! Live demo store — no signup needed:
https://ai-procurement-os.onrender.com/store?tenant=demo

Happy to set up a free 14-day pilot if useful.
```

---

## 15-minute demo (screen share)

1. Open **demo store** → walk through a quote request  
2. Show **partner stores** on homepage (different brands, same platform)  
3. Mention CRM: leads → suppliers → RFQs → proposals  
4. Offer **free 14-day pilot**  
5. Get their email → set up tenant within 24 hours  

---

## Social posts

Use images in `docs/marketing/images/` — one per platform:

| Platform | Image | Caption (short) |
|----------|-------|-----------------|
| LinkedIn | `linkedin/post-01.png` | See `SOCIAL-POSTS.md` |
| Facebook | `facebook/post-01.png` | See `SOCIAL-POSTS.md` |
| Instagram | `instagram/post-01.png` | See `SOCIAL-POSTS.md` |

---

## Track leads

Use `lead-tracker.csv` — log: name, company, date sent, replied Y/N, demo Y/N.

View inbound form leads: https://ai-procurement-os.onrender.com/api/demo-requests

**Team email:** aarfa.developers@gmail.com (all pilot form submissions notify this inbox when SMTP or Resend is configured on Render)

---

## Regenerate PDF & images

```bash
python -m src.main marketing-kit
```

Output: `TEAM-GUIDE.pdf` + social images in `images/`
