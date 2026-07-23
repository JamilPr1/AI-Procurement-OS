"""Partner storefront profiles — featured products, branding, and copy per tenant."""

from __future__ import annotations

from typing import Any

_IMAGE_BASE = "/static/store-products"


def _product(
    *,
    name: str,
    category: str,
    description: str,
    query: str,
    moq: int,
    from_price: float,
    image: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "category": category,
        "description": description,
        "query": query,
        "moq": moq,
        "from_price_usd": from_price,
        "image_url": f"{_IMAGE_BASE}/{image}",
    }


PARTNER_STORE_PROFILES: dict[str, dict[str, Any]] = {
    "demo": {
        "hero_title": "Custom drinkware & promo products",
        "hero_subtitle": "Factory-direct quotes on mugs, tumblers, bottles, and branded merchandise — landed pricing in minutes.",
        "eyebrow": "Official Demo Store",
        "specialty_lead": "Our most requested factory-direct programs for distributors and brand teams.",
        "specialties": ["Drinkware", "Promotional products", "Corporate gifting"],
        "category_chips": [
            {"label": "Ceramic mugs", "query": "500 custom ceramic mugs with 2-color logo"},
            {"label": "Tumblers", "query": "1000 insulated tumblers 20oz custom branded"},
            {"label": "Water bottles", "query": "750 stainless steel water bottles with laser logo"},
            {"label": "Tote bags", "query": "500 cotton tote bags with screen print logo"},
        ],
        "featured_products": [
            _product(name="Classic Ceramic Mug 11oz", category="Drinkware", description="Dishwasher-safe ceramic with full-wrap or spot logo.", query="500 custom ceramic mugs 11oz with logo", moq=144, from_price=2.85, image="ceramic-mug.jpg"),
            _product(name="Vacuum Insulated Tumbler 20oz", category="Drinkware", description="Double-wall stainless, powder coat colors, laser or pad print.", query="1000 insulated tumblers 20oz custom branded", moq=200, from_price=4.20, image="vacuum-tumbler.jpg"),
            _product(name="Sport Water Bottle 24oz", category="Drinkware", description="BPA-free Tritan or stainless options for gyms and events.", query="750 sport water bottles 24oz with logo", moq=300, from_price=3.10, image="water-bottle.jpg"),
            _product(name="Cotton Promo Tote Bag", category="Bags", description="Trade-show favorite with reinforced handles and vivid print.", query="1000 non-woven tote bags full color print", moq=500, from_price=1.45, image="promo-tote.jpg"),
        ],
    },
    "promo-pros": {
        "hero_title": "Your drinkware sourcing partner",
        "hero_subtitle": "Promo Pros specializes in mugs, tumblers, and beverageware for distributors — MOQ-friendly programs with fast quotes.",
        "eyebrow": "Promo Pros Inc · Drinkware specialists",
        "specialty_lead": "Programs we run every week for promotional product distributors.",
        "specialties": ["Ceramic mugs", "Vacuum tumblers", "Travel drinkware"],
        "category_chips": [
            {"label": "Mugs", "query": "500 ceramic mugs 11oz 2-color logo"},
            {"label": "Tumblers", "query": "1000 vacuum tumblers 20oz powder coat"},
            {"label": "Travel mugs", "query": "400 travel mugs with spill-proof lid and logo"},
            {"label": "Wine tumblers", "query": "600 stainless wine tumblers 12oz engraved"},
        ],
        "featured_products": [
            _product(name="Ceramic Mug 11oz", category="Ceramic", description="11oz & 15oz styles · 1–4 color imprint · gift boxes available.", query="500 ceramic mugs 11oz distributor program", moq=144, from_price=2.65, image="ceramic-mug.jpg"),
            _product(name="Powder Coat Tumbler 20oz", category="Tumblers", description="20oz & 30oz vacuum insulated · laser or screen print.", query="1000 powder coat tumblers 20oz logo", moq=200, from_price=3.95, image="powder-tumbler.jpg"),
            _product(name="Spill-Proof Travel Mug", category="Travel", description="Leak-proof lid · corporate color matching · retail packaging.", query="400 travel mugs spill-proof custom logo", moq=250, from_price=5.40, image="travel-mug.jpg"),
            _product(name="Stemless Wine Tumbler 12oz", category="Premium", description="12oz stainless · laser engraved · popular for hospitality.", query="600 stemless wine tumblers laser logo", moq=150, from_price=4.80, image="wine-tumbler.jpg"),
        ],
    },
    "gift-hub": {
        "hero_title": "Corporate gifts that impress",
        "hero_subtitle": "Gift Hub sources premium branded merchandise for employee recognition, client gifting, and executive programs.",
        "eyebrow": "Gift Hub Agency · Corporate gifting",
        "specialty_lead": "Curated gift programs with factory-direct landed pricing.",
        "specialties": ["Executive gifts", "Employee recognition", "Branded apparel"],
        "category_chips": [
            {"label": "Polo shirts", "query": "250 embroidered polo shirts company logo"},
            {"label": "Gift sets", "query": "300 corporate gift sets notebook pen mug"},
            {"label": "Notebooks", "query": "500 premium notebooks debossed logo"},
            {"label": "Pen sets", "query": "1000 metal pen sets engraved logo"},
        ],
        "featured_products": [
            _product(name="Embroidered Polo Shirt", category="Apparel", description="Pique cotton · left-chest embroidery · size runs XS–4XL.", query="250 embroidered polo shirts premium cotton", moq=100, from_price=8.50, image="polo-shirt.jpg"),
            _product(name="Corporate Gift Box Set", category="Gift sets", description="Notebook + pen + mug in custom mailer box.", query="300 corporate welcome gift sets custom box", moq=100, from_price=18.00, image="gift-box.jpg"),
            _product(name="Hardcover Journal A5", category="Stationery", description="Debossed or foil logo · ribbon bookmark · gift sleeve.", query="500 hardcover journals debossed logo", moq=200, from_price=4.25, image="journal.jpg"),
            _product(name="Metal Pen Gift Set", category="Writing", description="Twist-action metal pen in presentation box · laser engraved.", query="1000 metal pen sets laser engraved", moq=300, from_price=2.90, image="pen-set.jpg"),
        ],
    },
    "merch-direct": {
        "hero_title": "Workwear & safety merchandise",
        "hero_subtitle": "Merch Direct connects construction, industrial, and field teams with compliant hi-vis gear and durable branded workwear.",
        "eyebrow": "Merch Direct Co · Workwear & safety",
        "specialty_lead": "Built for crews, job sites, and industrial safety programs.",
        "specialties": ["Hi-vis safety", "Work polos", "Industrial outerwear"],
        "category_chips": [
            {"label": "Safety vests", "query": "800 hi-vis safety vests with logo"},
            {"label": "Hard hats", "query": "500 hard hats custom logo ANSI"},
            {"label": "Work polos", "query": "400 moisture-wick work polos embroidered"},
            {"label": "Jackets", "query": "200 softshell jackets embroidered logo"},
        ],
        "featured_products": [
            _product(name="Hi-Vis Safety Vest", category="Safety", description="Class 2 mesh or solid · reflective tape · front/back logo.", query="800 ANSI hi-vis safety vests screen print logo", moq=100, from_price=3.75, image="safety-vest.jpg"),
            _product(name="ANSI Hard Hat", category="PPE", description="ANSI Z89.1 · pad print or vinyl logo · multiple colors.", query="500 hard hats custom logo ANSI certified", moq=150, from_price=6.20, image="hard-hat.jpg"),
            _product(name="Work Polo Shirt", category="Apparel", description="Birdseye pique · durable for field teams · embroidery.", query="400 moisture-wick work polos embroidered logo", moq=72, from_price=9.80, image="work-polo.jpg"),
            _product(name="Softshell Jacket", category="Outerwear", description="Water-resistant · fleece lining · chest embroidery.", query="200 softshell jackets embroidered company logo", moq=50, from_price=22.50, image="softshell-jacket.jpg"),
        ],
    },
    "event-swag": {
        "hero_title": "Event swag that attendees keep",
        "hero_subtitle": "Event Swag Solutions powers conferences, trade shows, and activations with fast-turn tote bags, lanyards, tees, and booth essentials.",
        "eyebrow": "Event Swag Solutions · Conferences & trade shows",
        "specialty_lead": "High-volume programs with tight event deadlines.",
        "specialties": ["Trade show bags", "Lanyards & badges", "Event tees"],
        "category_chips": [
            {"label": "Tote bags", "query": "2000 branded tote bags trade show"},
            {"label": "Lanyards", "query": "3000 custom lanyards with badge holder"},
            {"label": "Event tees", "query": "1500 cotton t-shirts 2-color event logo"},
            {"label": "Banners", "query": "50 retractable banner stands full color"},
        ],
        "featured_products": [
            _product(name="Trade Show Tote Bag", category="Bags", description="12oz cotton or non-woven · full bleed print · reinforced gusset.", query="2000 trade show tote bags full color print", moq=500, from_price=1.35, image="promo-tote.jpg"),
            _product(name="Lanyard with Badge Holder", category="Event essentials", description="Polyester dye-sub · breakaway clip · ID pouch optional.", query="3000 custom lanyards with badge holder logo", moq=250, from_price=0.85, image="lanyard-badge.jpg"),
            _product(name="Screen-Printed T-Shirt", category="Apparel", description="100% cotton · 1–3 color screen print · fast production.", query="1500 conference t-shirts 2-color logo", moq=144, from_price=3.40, image="conference-tee.jpg"),
            _product(name="Roll-Up Banner Stand", category="Displays", description="33×80in · dye-sub graphic · carry case included.", query="50 retractable banner stands full color", moq=10, from_price=45.00, image="banner-stand.jpg"),
        ],
    },
}


def get_store_profile(slug: str) -> dict[str, Any]:
    """Return storefront profile for slug, falling back to demo."""
    return PARTNER_STORE_PROFILES.get(slug) or PARTNER_STORE_PROFILES["demo"]


def enrich_branding(slug: str, branding: dict | None) -> dict[str, Any]:
    """Merge tenant branding with partner store profile."""
    base = dict(branding or {})
    profile = get_store_profile(slug)
    return {**base, "store_profile": profile}


def build_store_payload(tenant: dict[str, Any]) -> dict[str, Any]:
    """Full API payload for a partner storefront."""
    slug = tenant.get("slug") or "demo"
    branding = enrich_branding(slug, tenant.get("branding"))
    profile = branding.get("store_profile") or {}
    return {
        "name": tenant.get("name"),
        "slug": slug,
        "tagline": tenant.get("tagline"),
        "branding": branding,
        "plan": tenant.get("plan"),
        "hero_title": profile.get("hero_title"),
        "hero_subtitle": profile.get("hero_subtitle"),
        "eyebrow": profile.get("eyebrow"),
        "specialty_lead": profile.get("specialty_lead"),
        "specialties": profile.get("specialties") or [],
        "category_chips": profile.get("category_chips") or [],
        "featured_products": profile.get("featured_products") or [],
    }
