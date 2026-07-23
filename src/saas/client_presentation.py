"""Generate client-facing PDF presentation for the SaaS platform."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from src.saas.store_catalog import PARTNER_STORE_PROFILES


def generate_client_presentation(
    creds: dict[str, Any],
    output_path: Path,
) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import landscape, letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            ListFlowable,
            ListItem,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as e:
        raise RuntimeError("reportlab required: pip install reportlab") from e

    output_path.parent.mkdir(parents=True, exist_ok=True)
    page = landscape(letter)
    pw, ph = page
    margin = 0.55 * inch
    content_w = pw - 2 * margin

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=page,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0.65 * inch,
        bottomMargin=0.55 * inch,
        title="AI Procurement OS — Client Presentation",
    )

    styles = getSampleStyleSheet()
    brand = colors.HexColor("#1e40af")
    brand_dark = colors.HexColor("#1e3a8a")
    muted = colors.HexColor("#475569")
    text = colors.HexColor("#1e293b")
    light_bg = colors.HexColor("#f8fafc")
    accent = colors.HexColor("#059669")

    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], fontSize=30, leading=34,
        textColor=brand_dark, alignment=TA_CENTER, spaceAfter=8,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle", parent=styles["Normal"], fontSize=13, leading=17,
        textColor=muted, alignment=TA_CENTER, spaceAfter=6,
    )
    h1 = ParagraphStyle(
        "H1", parent=styles["Heading1"], fontSize=20, leading=24,
        textColor=brand, spaceAfter=8, spaceBefore=2,
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=12, leading=15,
        textColor=brand_dark, spaceAfter=4, spaceBefore=2,
    )
    body = ParagraphStyle(
        "Body", parent=styles["Normal"], fontSize=10, leading=13,
        textColor=text, spaceAfter=4,
    )
    body_sm = ParagraphStyle(
        "BodySm", parent=body, fontSize=9, leading=12,
    )
    th = ParagraphStyle(
        "TH", parent=body_sm, fontName="Helvetica-Bold", textColor=colors.white,
    )
    td = ParagraphStyle("TD", parent=body_sm, textColor=text)
    td_bold = ParagraphStyle("TDBold", parent=td, fontName="Helvetica-Bold")
    footer_note = ParagraphStyle(
        "Footer", parent=body_sm, fontSize=8, textColor=muted, alignment=TA_CENTER,
    )

    plat = creds.get("platform", {})
    base = plat.get("landing_url", "http://127.0.0.1:8765")
    story: list[Any] = []

    def P(text: str, style: ParagraphStyle = td) -> Paragraph:
        return Paragraph(text.replace("\n", "<br/>"), style)

    def section(title: str) -> None:
        story.append(Paragraph(title, h1))

    def sub(title: str) -> Paragraph:
        return Paragraph(title, h2)

    def bullet_list(items: list[str], size: ParagraphStyle = body) -> ListFlowable:
        flow = [ListItem(Paragraph(i, size), leftIndent=8) for i in items]
        return ListFlowable(flow, bulletType="bullet", start="•", leftIndent=12)

    def styled_table(rows: list[list[Any]], widths: list[float], header_color=brand) -> Table:
        t = Table(rows, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), header_color),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, light_bg]),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def two_col(left: list[Any], right: list[Any], left_w: float | None = None) -> None:
        lw = left_w or content_w * 0.48
        rw = content_w - lw - 0.15 * inch
        left_cell = left if isinstance(left, list) else [left]
        right_cell = right if isinstance(right, list) else [right]
        t = Table([[left_cell, right_cell]], colWidths=[lw, rw])
        t.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 10),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ]))
        story.append(t)

    # ── Page 1: Cover + executive summary ─────────────────────────────
    story.append(Spacer(1, 0.55 * inch))
    story.append(Paragraph("AI Procurement OS", title_style))
    story.append(Paragraph(
        "Multi-tenant AI sourcing platform for promotional products, corporate gifts, and custom merchandise",
        subtitle_style,
    ))
    story.append(Paragraph(
        f"Client Presentation · {datetime.now().strftime('%B %Y')} · Demo: <b>{base}</b>",
        subtitle_style,
    ))
    story.append(Spacer(1, 0.22 * inch))

    exec_left = [
        sub("Market challenge"),
        bullet_list([
            "Distributors lose hours sourcing factories, building landed quotes, and chasing RFQs.",
            "Buyers expect instant pricing on mugs, apparel, safety gear, and event swag.",
            "Manual workflows don't scale when you manage multiple partner brands.",
        ], body_sm),
        Spacer(1, 0.08 * inch),
        sub("Our solution"),
        bullet_list([
            "Branded <b>AI Product Finder</b> storefront per partner with real product catalogs.",
            "Operator <b>CRM</b> automates outreach, supplier selection, RFQs, and proposals.",
            "<b>SaaS admin</b> provisions tenants, margins, and plans from one console.",
        ], body_sm),
    ]
    exec_right = [
        sub("Platform at a glance"),
        styled_table([
            [P("Capability", th), P("Business value", th)],
            [P("Partner stores", td_bold), P("Each distributor gets a live, branded quote engine", td)],
            [P("Hot Leads CRM", td_bold), P("AI pipeline from discovery → proposal → tracking", td)],
            [P("Quote wizard", td_bold), P("Buyers describe products; AI returns landed pricing", td)],
            [P("Multi-tenant SaaS", td_bold), P("One platform, many partner brands & margin rules", td)],
            [P("Super admin", td_bold), P("Provision stores, seed demos, manage all tenants", td)],
        ], [1.55 * inch, content_w * 0.48 - 1.55 * inch - 0.15 * inch], accent),
        Spacer(1, 0.06 * inch),
        Paragraph(
            "<i>Run your own sourcing agency and license the platform to other distributors.</i>",
            body_sm,
        ),
    ]
    two_col(exec_left, exec_right)
    story.append(PageBreak())

    # ── Page 2: Partner storefronts (fixed wrapping) + customer journey ─
    section("Partner Storefronts")
    story.append(Paragraph(
        "Each partner operates a branded store with custom colors, specialty categories, "
        "featured product photos, and an AI quote assistant. Stores are live at "
        f"<b>{base}/store?tenant=&#123;slug&#125;</b>.",
        body,
    ))
    story.append(Spacer(1, 0.06 * inch))

    store_header = [
        P("Partner", th),
        P("Specialties", th),
        P("Featured products", th),
        P("Store path", th),
    ]
    store_rows = [store_header]
    tenant_names = {
        "promo-pros": "Promo Pros Inc",
        "gift-hub": "Gift Hub Agency",
        "merch-direct": "Merch Direct Co",
        "event-swag": "Event Swag Solutions",
        "demo": "Demo Store",
    }
    for slug, profile in PARTNER_STORE_PROFILES.items():
        name = tenant_names.get(slug, slug)
        specialties = profile.get("specialties") or []
        products = profile.get("featured_products") or []
        product_lines = "<br/>".join(
            f"• {p['name']} <font color='#64748b'>(MOQ {p['moq']:,}, from ${p['from_price_usd']:.2f})</font>"
            for p in products
        )
        store_rows.append([
            P(f"<b>{name}</b><br/><font color='#64748b' size='8'>{profile.get('eyebrow', '')}</font>", td),
            P("<br/>".join(f"• {s}" for s in specialties), td),
            P(product_lines or "—", td),
            P(f"/store?tenant={slug}", td),
        ])

    col_w = [1.45 * inch, 1.85 * inch, 4.35 * inch, 1.55 * inch]
    story.append(styled_table(store_rows, col_w, accent))
    story.append(Spacer(1, 0.12 * inch))

    journey_left = [
        sub("Buyer journey (storefront)"),
        bullet_list([
            "<b>1. Discover</b> — visitor lands on partner store or clicks a featured product",
            "<b>2. Describe</b> — AI chat collects quantity, specs, branding, and timeline",
            "<b>3. Quote</b> — platform researches suppliers and returns all-in landed price",
            "<b>4. Order</b> — buyer confirms; deal enters operator CRM for fulfillment",
        ], body_sm),
    ]
    journey_right = [
        sub("Operator journey (CRM)"),
        bullet_list([
            "<b>Discover Leads</b> — AI finds US buyers in your product categories",
            "<b>Hot Leads</b> — personalization → outreach → supplier pick → RFQ → proposal",
            "<b>Tracking</b> — monitor deals from quote through shipment",
            "<b>SaaS Admin</b> — provision tenants, set margins, enable/disable stores",
        ], body_sm),
    ]
    two_col(journey_left, journey_right)
    story.append(PageBreak())

    # ── Page 3: CRM detail + revenue model ─────────────────────────────
    section("CRM Automation & Revenue Model")
    crm_left = [
        sub("Automated pipeline stages"),
        styled_table([
            [P("Stage", th), P("What happens", th)],
            [P("Personalization", td_bold), P("AI researches buyer company and drafts tailored outreach", td)],
            [P("Outreach", td_bold), P("Consultative email with factory images; editable before send", td)],
            [P("Supplier discovery", td_bold), P("Web search + supplier network; operator picks preferred factory", td)],
            [P("RFQ", td_bold), P("Professional multi-supplier RFQ with product specs", td)],
            [P("Proposal", td_bold), P("Plain-text proposal with aligned pricing columns", td)],
            [P("Tracking", td_bold), P("Deal moves to pipeline; status updates through close", td)],
        ], [1.35 * inch, content_w * 0.48 - 1.35 * inch - 0.15 * inch]),
    ]
    rev_right = [
        sub("Dual revenue model"),
        bullet_list([
            "<b>Agency margin</b> — earn % on every factory-direct deal you broker",
            "<b>SaaS subscription</b> — charge partners monthly for branded stores + CRM",
            "<b>Plans</b> — Starter (limited deals) and Growth (higher volume)",
            "<b>Per-tenant margins</b> — configure markup % per partner store",
        ], body_sm),
        Spacer(1, 0.1 * inch),
        sub("Why partners buy in"),
        bullet_list([
            "Instant quotes without hiring more sourcing staff",
            "Branded storefront their customers can self-serve on",
            "Professional proposals and RFQs generated automatically",
            "White-label ready — your brand, your partner network",
        ], body_sm),
    ]
    two_col(crm_left, rev_right)
    story.append(PageBreak())

    # ── Page 4: Demo access + pilot plan ───────────────────────────────
    section("Live Demo & Pilot Plan")
    admin = creds.get("platform_admin", {})

    demo_header = [P("Access", th), P("URL / credentials", th), P("Purpose", th)]
    demo_rows = [demo_header]
    demo_rows.append([
        P("Landing page", td_bold),
        P(base, td),
        P("Marketing site + partner store directory", td),
    ])
    demo_rows.append([
        P("CRM login", td_bold),
        P(f"{base}/login", td),
        P("Operator and super-admin sign-in", td),
    ])
    demo_rows.append([
        P("Super admin", td_bold),
        P(f"{admin.get('email', '')}<br/>Password: {admin.get('password', '')}", td),
        P("Manage all tenants, SaaS settings, seed data", td),
    ])
    for u in creds.get("tenant_users", []):
        if u.get("role") == "superadmin":
            continue
        demo_rows.append([
            P(u.get("tenant", ""), td_bold),
            P(f"{u.get('email', '')}<br/>Password: {u.get('password', '')}", td),
            P(f"CRM + {u.get('tenant', '')} store management", td),
        ])

    demo_w = [1.5 * inch, 3.4 * inch, content_w - 4.9 * inch]
    story.append(styled_table(demo_rows, demo_w, colors.HexColor("#7c3aed")))
    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph(
        "<i>Credentials are for demo/dev only. Change all passwords before production. "
        "Full detail: PLATFORM_CREDENTIALS.docx</i>",
        body_sm,
    ))
    story.append(Spacer(1, 0.12 * inch))

    pilot_rows = [
        [P("Week", th), P("Milestone", th), P("Deliverables", th)],
        [P("1", td_bold), P("Deploy & configure", td), P("VPS hosting, domain, SSL, SMTP, LLM API", td)],
        [P("2", td_bold), P("Onboard partners", td), P("2–3 branded stores with product catalogs & photos", td)],
        [P("3", td_bold), P("Run live quotes", td), P("Real buyer tests; tune margins, templates, suppliers", td)],
        [P("4", td_bold), P("Review & scale", td), P("Conversion metrics, expand tenants, white-label pitch", td)],
    ]
    story.append(sub("Recommended 4-week pilot"))
    story.append(styled_table(pilot_rows, [0.55 * inch, 1.65 * inch, content_w - 2.2 * inch], brand))
    story.append(Spacer(1, 0.18 * inch))
    story.append(Paragraph(
        "<b>Thank you</b> — ready to schedule a live walkthrough or begin pilot onboarding.",
        ParagraphStyle("Close", parent=subtitle_style, fontSize=12, textColor=brand_dark),
    ))

    def _footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(muted)
        canvas.drawString(margin, 0.38 * inch, "AI Procurement OS — Confidential")
        canvas.drawRightString(pw - margin, 0.38 * inch, f"Page {canvas.getPageNumber()}")
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.setLineWidth(0.5)
        canvas.line(margin, 0.48 * inch, pw - margin, 0.48 * inch)
        canvas.setFillColor(brand)
        canvas.rect(0, ph - 0.12 * inch, pw, 0.12 * inch, fill=1, stroke=0)
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return output_path
