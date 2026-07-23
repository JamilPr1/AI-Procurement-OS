"""Compose review-ready email and proposal drafts for every pipeline stage."""

from __future__ import annotations

from typing import Any

from src.core.company_name import business_name_from_email, normalize_lead_record
from src.core.image_assets import images_html_block
from src.core.outreach_images import FACTORY_IMAGE_HEADING

DEFAULT_AGENCY_NAME = "Your Sourcing Team"
AGENCY_PITCH = (
    "We are a multi-supplier sourcing partner — one roof for vetted factories, QC, and logistics. "
    "Instead of chasing individual manufacturers, you get a single point of contact, competitive quotes "
    "from multiple factories, and transparent landed pricing on every program."
)


def agency_intro(*, agency_name: str = DEFAULT_AGENCY_NAME) -> str:
    return (
        f"{AGENCY_PITCH}\n\n"
        f"— {agency_name}"
    )


def _pick_outreach_email(lead: dict) -> str:
    """Use the lead's business email for outreach To field."""
    for key in ("email",):
        val = (lead.get(key) or "").strip()
        if val and "@" in val:
            return val
    data = lead.get("data") or {}
    if isinstance(data, dict):
        val = (data.get("email") or "").strip()
        if val and "@" in val:
            return val
    return ""


def _resolve_buyer_name(lead: dict) -> str:
    """Business name from To email domain, falling back to normalized company name."""
    email = _pick_outreach_email(lead)
    if email:
        from_domain = business_name_from_email(email)
        if from_domain:
            return from_domain
    return lead.get("company_name", "your company")


def _product_category_label(products: list[str]) -> str:
    joined = " ".join(products[:3]).lower()
    if any(w in joined for w in ("tumbler", "drinkware", "bottle", "mug", "cup", "water")):
        return "drinkware"
    if any(w in joined for w in ("bag", "apparel", "shirt", "hat", "cap", "polo")):
        return "apparel"
    if any(w in joined for w in ("gift", "promo", "swag")):
        return "promotional product"
    return (products[0] if products else "product").split()[0].lower()


def _collection_phrase(products: list[str], profile: dict) -> str:
    category = _product_category_label(products)
    labels = {
        "drinkware": "promotional drinkware collection",
        "apparel": "apparel and branded merchandise",
        "promotional product": "promotional product catalog",
    }
    summary = (profile.get("company_summary") or "").lower()
    if "drinkware" in summary or "tumbler" in summary:
        return "promotional drinkware collection"
    if products:
        first = products[0].lower()
        if "drinkware" in first or "tumbler" in first or "bottle" in first:
            return "promotional drinkware collection"
        if len(products) > 1:
            return f"{products[0]} and related product lines"
    return labels.get(category, f"{category} programs")


def compose_first_outreach_body(lead: dict, profile: dict, *, agency_name: str = DEFAULT_AGENCY_NAME) -> dict[str, str]:
    """First-touch outreach — consultative tone, business name from email domain."""
    lead = normalize_lead_record(lead)
    email = _pick_outreach_email(lead)
    if email:
        lead = {**lead, "email": email}
        domain_name = business_name_from_email(email)
        if domain_name:
            lead = {**lead, "company_name": domain_name}

    name = _resolve_buyer_name(lead)
    products_list = profile.get("products_services") or ["promotional products"]
    category = _product_category_label(products_list)
    collection = _collection_phrase(products_list, profile)
    product_word = products_list[0] if products_list else category

    email_body = (
        f"Dear {name},\n\n"
        f"I came across {name} and spent a few minutes looking through your {collection}. "
        f"It's clear you offer a wide range of styles, and I imagine keeping pricing competitive "
        f"while managing different suppliers can be a constant challenge.\n\n"
        f"We work a little differently. Instead of acting as another factory, we're a sourcing partner "
        f"that gives distributors and brand programs access to multiple vetted manufacturers through "
        f"a single point of contact. That means you can compare factory options, receive transparent "
        f"landed pricing, and have QC and logistics handled under one roof.\n\n"
        f"Our partners typically use us to:\n\n"
        f"• Compare multiple factory quotes before placing an order\n"
        f"• Improve margins without sacrificing quality\n"
        f"• Handle seasonal or large-volume programs with confidence\n"
        f"• Reduce the time spent coordinating with different suppliers\n\n"
        f"I noticed a few products on your website that look like good candidates for factory-direct "
        f"sourcing. There's a good chance we could provide a competitive benchmark for those programs, "
        f"and if not, at least you'll have another pricing option for future orders.\n\n"
        f"Would you be open to a quick 15-minute conversation sometime this week? I'd be happy to walk "
        f"you through how we work and prepare a no-obligation quote for one of your upcoming "
        f"{product_word} projects.\n\n"
        f"Best regards,\n"
        f"{agency_name}"
    )

    subject = f"A sourcing idea for your {category} programs"

    linkedin = (
        f"Hi — we help distributors like {name} cut landed costs on {category} through a vetted "
        f"multi-factory network under one roof. Happy to share a sample benchmark quote if useful."
    )

    return {
        "subject_line": subject,
        "email_body": email_body,
        "linkedin_message": linkedin,
    }


def compose_personalization(lead: dict, profile: dict) -> dict[str, Any]:
    outreach = compose_first_outreach_body(lead, profile)
    images = profile.get("product_images") or lead.get("product_images") or []
    return {
        **outreach,
        "product_images": images,
        "source": "draft_composer",
    }


def compose_outreach_email(
    lead: dict,
    personalization: dict,
    *,
    product_images: list[dict] | None = None,
    profile: dict | None = None,
) -> dict[str, Any]:
    lead = normalize_lead_record(lead)
    email = _pick_outreach_email(lead)
    if email:
        lead = {**lead, "email": email}
        domain_name = business_name_from_email(email)
        if domain_name:
            lead = {**lead, "company_name": domain_name}

    images = product_images or personalization.get("product_images") or lead.get("product_images") or []
    prof = profile or {
        "products_services": personalization.get("products_services") or [],
        "company_summary": personalization.get("company_summary") or "",
        "product_images": images,
    }
    fresh = compose_first_outreach_body(lead, prof)
    body = fresh["email_body"]
    subject = fresh["subject_line"]

    if images:
        if "products on your website" in body:
            body = body.replace(
                "I noticed a few products on your website that look like good candidates for factory-direct sourcing.",
                "Below are factory-direct product references from our vetted manufacturer network — "
                "programs like yours that we can often match with competitive landed pricing.",
            )
    name = _resolve_buyer_name(lead)

    html_body = f"<p>{body.replace(chr(10), '</p><p>')}</p>{images_html_block(images, heading=FACTORY_IMAGE_HEADING)}"
    return {
        "channel": "email",
        "to": email or lead.get("email", ""),
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "product_images": images,
        "linkedin_message": fresh.get("linkedin_message") or personalization.get("linkedin_message", ""),
        "status": "draft",
        "source": "draft_composer",
    }


def compose_rfq_email(requirements: dict, suppliers: list[dict], product_spec: dict | None = None) -> dict[str, Any]:
    spec = product_spec or {}
    product = requirements.get("product_description") or spec.get("product_category") or "custom products"
    qty = requirements.get("quantity", 5000)
    dest = requirements.get("shipping_destination", "United States")
    material = requirements.get("material") or (spec.get("materials") or ["custom"])[0]
    certs = spec.get("certifications_required") or ["FDA", "LFGB", "REACH"]
    cert_label = " / ".join(certs) if isinstance(certs, list) else str(certs)
    qty_label = f"{qty:,} units" if isinstance(qty, int) else str(qty)
    delivery = requirements.get("delivery_date", "8 weeks")

    body = (
        f"Dear Supplier,\n\n"
        f"We are a multi-supplier sourcing agency representing an established US distributor. "
        f"We are requesting a formal quotation for the program outlined below.\n\n"
        f"PRODUCT REQUIREMENTS\n"
        f"{'-' * 40}\n"
        f"Product:              {product}\n"
        f"Quantity:             {qty_label}\n"
        f"Material:             {material}\n"
        f"Logo / branding:      {requirements.get('logo_spec', 'custom branded')}\n"
        f"Packaging:            {requirements.get('packaging', 'standard export packaging')}\n"
        f"Shipping destination: {dest}\n"
        f"Target delivery:      {delivery}\n\n"
        f"PLEASE PROVIDE\n"
        f"{'-' * 40}\n"
        f"  • FOB unit price (USD)\n"
        f"  • Minimum order quantity (MOQ)\n"
        f"  • Production lead time\n"
        f"  • Sample cost and lead time\n"
        f"  • Applicable certifications ({cert_label})\n"
        f"  • Payment terms\n\n"
        f"We aim to place orders within 2 weeks of receiving competitive quotes. "
        f"Please reply with your best offer at your earliest convenience.\n\n"
        f"Best regards,\n"
        f"{DEFAULT_AGENCY_NAME}"
    )
    supplier_list = suppliers if isinstance(suppliers, list) else []
    supplier_rows = [
        {
            "factory_name": s.get("factory_name"),
            "url": s.get("url", ""),
            "platform_source": s.get("platform_source") or s.get("platform", ""),
            "trust_score": s.get("trust_score"),
        }
        for s in supplier_list[:8]
    ]
    return {
        "rfq_body": body,
        "subject": f"RFQ: {product} — {qty_label} to {dest}",
        "suppliers": supplier_rows,
        "product": product,
        "response_deadline_days": 7,
        "source": "draft_composer",
    }


def compose_proposal_document(
    lead: dict,
    requirements: dict,
    recommendation: dict,
    quotes: list[dict],
    *,
    client_price_usd: float,
    product_spec: dict | None = None,
    factory_cost_usd: float | None = None,
    margin_usd: float | None = None,
    margin_percent: float | None = None,
) -> dict[str, Any]:
    lead = normalize_lead_record(lead)
    company = lead.get("company_name", "Client")
    product = requirements.get("product_description", "promotional products")
    supplier = recommendation.get("recommended_supplier") or "our vetted manufacturing partner"
    qty = requirements.get("quantity", 5000)
    spec = product_spec or {}
    images = spec.get("reference_images") or spec.get("product_images") or []
    qty_label = f"{qty:,} units" if isinstance(qty, int) else str(qty)
    margin_line = ""
    if factory_cost_usd and margin_usd:
        margin_line = (
            f" Factory cost: ${factory_cost_usd:,.2f} · Our margin ({margin_percent or 15}%): "
            f"${margin_usd:,.2f} · Client all-in: ${client_price_usd:,.2f}."
        )
    return {
        "title": f"Proposal for {company}",
        "executive_summary": (
            f"{AGENCY_PITCH} "
            f"We've completed factory sourcing for {company}'s {product} program and prepared a transparent, "
            f"all-in landed quote for {qty_label}.{margin_line} "
            f"Our recommended partner balances unit cost, MOQ flexibility, and production reliability — "
            f"with full QC and logistics coordination handled on your behalf."
        ),
        "recommended_option": supplier,
        "client_price_usd": client_price_usd,
        "factory_cost_usd": factory_cost_usd,
        "margin_usd": margin_usd,
        "margin_percent": margin_percent,
        "supplier_comparison": quotes,
        "requirements_recap": requirements,
        "product_spec_summary": {
            "category": spec.get("product_category"),
            "materials": spec.get("materials"),
            "certifications": spec.get("certifications_required"),
        },
        "reference_images": images,
        "hero_image": spec.get("hero_image") or (images[0] if images else None),
        "timeline": requirements.get("delivery_date", "8–10 weeks from PO"),
        "payment_terms": "30% Deposit • 70% Before Shipment",
        "next_steps": [
            "Review and approve the proposal",
            "Confirm final product specifications and artwork",
            "Issue the purchase order",
            "Begin production coordination, sampling (if required), and quality control",
        ],
        "status": "draft",
        "source": "draft_composer",
    }


def _format_proposal_timeline(timeline: str) -> str:
    t = (timeline or "8-10 weeks").strip()
    if not t:
        return "8–10 Weeks"
    t = t.replace("weeks", "Weeks").replace("Weeks", "Weeks")
    if "-" in t and "–" not in t:
        t = t.replace("-", "–")
    return t[0].upper() + t[1:] if t else "8–10 Weeks"


def _proposal_costs(proposal: dict) -> tuple[float, float, float, int]:
    """Return factory_cost, margin, client_price, margin_percent."""
    margin_pct = int(proposal.get("margin_percent") or 15)
    client_price = float(proposal.get("client_price_usd") or 0)
    factory_cost = proposal.get("factory_cost_usd")
    margin = proposal.get("margin_usd")
    if client_price and not factory_cost:
        factory_cost = round(client_price / (1 + margin_pct / 100), 2)
    if factory_cost and not margin:
        margin = round(float(factory_cost) * margin_pct / 100, 2)
    if not client_price and factory_cost and margin:
        client_price = round(float(factory_cost) + float(margin), 2)
    return float(factory_cost or 0), float(margin or 0), float(client_price or 0), margin_pct


_PRICING_LABEL_WIDTH = 42
_PRICING_AMOUNT_WIDTH = 16
_DETAIL_LABEL_WIDTH = 34


def _proposal_pricing_block(
    factory_cost: float,
    margin: float,
    client_price: float,
    margin_pct: int,
) -> str:
    def row(label: str, amount: float) -> str:
        amt = f"${amount:,.2f} USD"
        return f"  {label[:_PRICING_LABEL_WIDTH].ljust(_PRICING_LABEL_WIDTH)}{amt:>{_PRICING_AMOUNT_WIDTH}}"

    divider = f"  {' ' * _PRICING_LABEL_WIDTH}{'-' * _PRICING_AMOUNT_WIDTH}"
    margin_label = f"Sourcing & Coordination ({margin_pct}%)"
    if len(margin_label) > _PRICING_LABEL_WIDTH:
        margin_label = f"Coordination & QC ({margin_pct}%)"

    return "\n".join([
        row("Factory Production & Landed Cost", factory_cost),
        row(margin_label, margin),
        divider,
        row("TOTAL LANDED PRICE", client_price),
    ])


def _proposal_detail_line(label: str, value: str) -> str:
    return f"  {label.ljust(_DETAIL_LABEL_WIDTH)}{value}"


def _compose_proposal_plain_body(
    *,
    company: str,
    category: str,
    supplier: str,
    qty_label: str,
    factory_cost: float,
    margin: float,
    client_price: float,
    margin_pct: int,
    timeline: str,
) -> str:
    return (
        f"Hi {company} Team,\n\n"
        f"Thank you for the opportunity to prepare a sourcing proposal for your {category} program.\n\n"
        f"Based on the information provided, we've identified a vetted manufacturing partner that we believe "
        f"offers a strong combination of pricing, quality, and production capacity. Below is our initial proposal.\n\n"
        f"PROPOSED SOLUTION\n"
        f"{'-' * 40}\n\n"
        f"Recommended Factory:  {supplier}\n"
        f"Order Quantity:       {qty_label}\n\n"
        f"PRICING SUMMARY\n"
        f"{'-' * 40}\n"
        f"{_proposal_pricing_block(factory_cost, margin, client_price, margin_pct)}\n\n"
        f"{_proposal_detail_line('Estimated Production Timeline', timeline)}\n"
        f"{_proposal_detail_line('Payment Terms', '30% Deposit · 70% Before Shipment')}\n\n"
        f"WHAT'S INCLUDED\n"
        f"{'-' * 40}\n"
        f"  • Factory selection from our vetted manufacturing network\n"
        f"  • Production coordination and supplier management\n"
        f"  • Quality control inspections throughout production\n"
        f"  • Export documentation and logistics coordination\n"
        f"  • Transparent landed pricing with no hidden sourcing costs\n\n"
        f"If you'd like to explore alternative factories, pricing options, or different order quantities, "
        f"we're happy to prepare additional comparisons so you can choose the best fit for your program.\n\n"
        f"NEXT STEPS\n"
        f"{'-' * 40}\n"
        f"  1. Review and approve the proposal.\n"
        f"  2. Confirm final product specifications and artwork.\n"
        f"  3. Issue the purchase order.\n"
        f"  4. We'll begin production coordination, sampling (if required), and quality control.\n\n"
        f"If you have any questions or would like to discuss adjustments before moving forward, "
        f"feel free to reply to this email or schedule a quick call. We look forward to supporting your "
        f"team on this and future sourcing programs.\n\n"
        f"Best regards,\n\n"
        f"{DEFAULT_AGENCY_NAME}"
    )


def _compose_proposal_html_body(
    *,
    company: str,
    category: str,
    supplier: str,
    qty_label: str,
    factory_cost: float,
    margin: float,
    client_price: float,
    margin_pct: int,
    timeline: str,
    images: list,
) -> str:
    import html as html_module

    esc = html_module.escape
    rows = (
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;'>"
        f"Factory Production &amp; Landed Cost</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right;'>"
        f"${factory_cost:,.2f} USD</td></tr>"
        f"<tr><td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;'>"
        f"Sourcing, Production Coordination &amp; QC ({margin_pct}%)</td>"
        f"<td style='padding:8px 12px;border-bottom:1px solid #e5e7eb;text-align:right;'>"
        f"${margin:,.2f} USD</td></tr>"
        f"<tr><td style='padding:10px 12px;font-weight:700;'>Total Landed Price</td>"
        f"<td style='padding:10px 12px;text-align:right;font-weight:700;'>"
        f"${client_price:,.2f} USD</td></tr>"
    )
    return (
        f"<div style='font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.6;color:#1f2937;max-width:640px;'>"
        f"<p>Hi {esc(company)} Team,</p>"
        f"<p>Thank you for the opportunity to prepare a sourcing proposal for your {esc(category)} program.</p>"
        f"<p>Based on the information provided, we've identified a vetted manufacturing partner that we believe "
        f"offers a strong combination of pricing, quality, and production capacity. Below is our initial proposal.</p>"
        f"<h2 style='font-size:18px;margin:24px 0 12px;color:#111827;'>Proposed Solution</h2>"
        f"<p><strong>Recommended Factory:</strong> {esc(supplier)}<br>"
        f"<strong>Order Quantity:</strong> {esc(qty_label)}</p>"
        f"<table style='width:100%;border-collapse:collapse;margin:16px 0;background:#f9fafb;border-radius:8px;'>"
        f"<thead><tr>"
        f"<th style='padding:10px 12px;text-align:left;border-bottom:2px solid #d1d5db;'>Description</th>"
        f"<th style='padding:10px 12px;text-align:right;border-bottom:2px solid #d1d5db;'>Amount</th>"
        f"</tr></thead><tbody>{rows}</tbody></table>"
        f"<p><strong>Estimated Production Timeline:</strong> {esc(timeline)}<br>"
        f"<strong>Payment Terms:</strong> 30% Deposit · 70% Before Shipment</p>"
        f"<h3 style='font-size:16px;margin:24px 0 8px;color:#111827;'>What's Included</h3>"
        f"<ul style='margin:0 0 16px;padding-left:20px;'>"
        f"<li>Factory selection from our vetted manufacturing network</li>"
        f"<li>Production coordination and supplier management</li>"
        f"<li>Quality control inspections throughout production</li>"
        f"<li>Export documentation and logistics coordination</li>"
        f"<li>Transparent landed pricing with no hidden sourcing costs</li>"
        f"</ul>"
        f"<p>If you'd like to explore alternative factories, pricing options, or different order quantities, "
        f"we're happy to prepare additional comparisons so you can choose the best fit for your program.</p>"
        f"<h3 style='font-size:16px;margin:24px 0 8px;color:#111827;'>Next Steps</h3>"
        f"<ol style='margin:0 0 16px;padding-left:20px;'>"
        f"<li>Review and approve the proposal.</li>"
        f"<li>Confirm final product specifications and artwork.</li>"
        f"<li>Issue the purchase order.</li>"
        f"<li>We'll begin production coordination, sampling (if required), and quality control.</li>"
        f"</ol>"
        f"<p>If you have any questions or would like to discuss adjustments before moving forward, "
        f"feel free to reply to this email or schedule a quick call. We look forward to supporting your "
        f"team on this and future sourcing programs.</p>"
        f"<p>Best regards,<br><strong>{esc(DEFAULT_AGENCY_NAME)}</strong></p>"
        f"{images_html_block(images, heading='Product references')}"
        f"</div>"
    )


def compose_proposal_client_email(proposal: dict, lead: dict) -> dict[str, Any]:
    lead = normalize_lead_record(lead)
    email = _pick_outreach_email(lead)
    if email:
        lead = {**lead, "email": email}
        domain_name = business_name_from_email(email)
        if domain_name:
            lead = {**lead, "company_name": domain_name}

    company = _resolve_buyer_name(lead)
    requirements = proposal.get("requirements_recap") or {}
    product = requirements.get("product_description") or "your program"
    category = _product_category_label([product] if product else [])
    supplier = proposal.get("recommended_option") or "our vetted manufacturing partner"
    qty = requirements.get("quantity", 5000)
    qty_label = f"{qty:,} Units" if isinstance(qty, int) else f"{qty} Units"
    timeline = _format_proposal_timeline(proposal.get("timeline", "8–10 weeks"))
    factory_cost, margin, client_price, margin_pct = _proposal_costs(proposal)
    images = proposal.get("reference_images") or []

    body = _compose_proposal_plain_body(
        company=company,
        category=category,
        supplier=supplier,
        qty_label=qty_label,
        factory_cost=factory_cost,
        margin=margin,
        client_price=client_price,
        margin_pct=margin_pct,
        timeline=timeline,
    )
    html_body = _compose_proposal_html_body(
        company=company,
        category=category,
        supplier=supplier,
        qty_label=qty_label,
        factory_cost=factory_cost,
        margin=margin,
        client_price=client_price,
        margin_pct=margin_pct,
        timeline=timeline,
        images=images,
    )
    return {
        "to": email or lead.get("email", ""),
        "subject": proposal.get("title", f"Proposal for {company}"),
        "body": body,
        "html_body": html_body,
        "product_images": images,
        "status": proposal.get("status", "draft"),
        "source": "draft_composer",
    }