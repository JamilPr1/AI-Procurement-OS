"""Generate accurate product SVG thumbnails for partner storefronts."""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "src" / "web" / "store-products"

SVG_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 420" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{bg1}"/>
      <stop offset="100%" stop-color="{bg2}"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000" flood-opacity="0.22"/>
    </filter>
  </defs>
  <rect width="640" height="420" fill="url(#bg)"/>
  <g filter="url(#shadow)">{body}</g>
</svg>"""


PRODUCTS: dict[str, dict[str, str]] = {
    "ceramic-mug.svg": {
        "label": "Ceramic mug",
        "bg1": "#f8fafc", "bg2": "#e2e8f0",
        "body": """
  <rect x="235" y="120" width="170" height="150" rx="18" fill="#ffffff" stroke="#cbd5e1" stroke-width="4"/>
  <path d="M405 155 C470 155 470 235 405 235" fill="none" stroke="#cbd5e1" stroke-width="14" stroke-linecap="round"/>
  <rect x="250" y="250" width="140" height="18" rx="9" fill="#e2e8f0"/>
  <ellipse cx="320" cy="120" rx="85" ry="10" fill="#f1f5f9"/>""",
    },
    "vacuum-tumbler.svg": {
        "label": "Vacuum tumbler",
        "bg1": "#eff6ff", "bg2": "#dbeafe",
        "body": """
  <rect x="255" y="95" width="130" height="220" rx="28" fill="#64748b"/>
  <rect x="265" y="105" width="110" height="200" rx="22" fill="#94a3b8"/>
  <rect x="285" y="70" width="70" height="35" rx="12" fill="#475569"/>
  <rect x="300" y="78" width="40" height="8" rx="4" fill="#cbd5e1"/>""",
    },
    "water-bottle.svg": {
        "label": "Water bottle",
        "bg1": "#ecfeff", "bg2": "#cffafe",
        "body": """
  <rect x="285" y="170" width="70" height="150" rx="22" fill="#0891b2"/>
  <rect x="295" y="95" width="50" height="85" rx="12" fill="#06b6d4"/>
  <rect x="305" y="75" width="30" height="28" rx="8" fill="#155e75"/>
  <rect x="300" y="110" width="40" height="18" rx="4" fill="#67e8f9" opacity="0.55"/>""",
    },
    "promo-tote.svg": {
        "label": "Promo tote bag",
        "bg1": "#fff7ed", "bg2": "#ffedd5",
        "body": """
  <path d="M170 170 H470 V330 C470 345 458 355 440 355 H200 C182 355 170 345 170 330 Z" fill="#f97316"/>
  <path d="M230 170 C230 120 260 95 320 95 C380 95 410 120 410 170" fill="none" stroke="#ea580c" stroke-width="16" stroke-linecap="round"/>
  <rect x="205" y="210" width="230" height="90" rx="8" fill="#fdba74" opacity="0.45"/>""",
    },
    "powder-tumbler.svg": {
        "label": "Powder coat tumbler",
        "bg1": "#fdf4ff", "bg2": "#fae8ff",
        "body": """
  <rect x="255" y="95" width="130" height="220" rx="28" fill="#7c3aed"/>
  <rect x="265" y="105" width="110" height="200" rx="22" fill="#8b5cf6"/>
  <rect x="285" y="70" width="70" height="35" rx="12" fill="#5b21b6"/>
  <rect x="290" y="150" width="60" height="8" rx="4" fill="#ddd6fe" opacity="0.8"/>""",
    },
    "travel-mug.svg": {
        "label": "Travel mug",
        "bg1": "#f8fafc", "bg2": "#e2e8f0",
        "body": """
  <rect x="230" y="130" width="180" height="170" rx="24" fill="#1e293b"/>
  <rect x="245" y="95" width="150" height="45" rx="14" fill="#334155"/>
  <rect x="275" y="78" width="90" height="22" rx="10" fill="#64748b"/>
  <rect x="255" y="170" width="130" height="55" rx="10" fill="#475569" opacity="0.55"/>""",
    },
    "wine-tumbler.svg": {
        "label": "Wine tumbler",
        "bg1": "#fff1f2", "bg2": "#ffe4e6",
        "body": """
  <path d="M250 110 H390 C390 230 365 290 320 310 C275 290 250 230 250 110 Z" fill="#be123c"/>
  <ellipse cx="320" cy="110" rx="70" ry="12" fill="#fda4af"/>
  <ellipse cx="320" cy="300" rx="42" ry="10" fill="#9f1239"/>""",
    },
    "polo-shirt.svg": {
        "label": "Polo shirt",
        "bg1": "#f0fdf4", "bg2": "#dcfce7",
        "body": """
  <path d="M210 120 L260 95 L320 130 L380 95 L430 120 L400 170 V330 H240 V170 Z" fill="#16a34a"/>
  <path d="M300 130 L320 155 L340 130 V180 H300 Z" fill="#15803d"/>
  <rect x="240" y="170" width="160" height="12" fill="#22c55e" opacity="0.5"/>
  <circle cx="320" cy="205" r="8" fill="#14532d"/>""",
    },
    "gift-box.svg": {
        "label": "Gift box",
        "bg1": "#fef2f2", "bg2": "#fee2e2",
        "body": """
  <rect x="190" y="170" width="260" height="170" rx="12" fill="#dc2626"/>
  <rect x="305" y="170" width="30" height="170" fill="#fbbf24"/>
  <rect x="190" y="235" width="260" height="30" fill="#fbbf24"/>
  <path d="M250 170 C280 120 360 120 390 170" fill="none" stroke="#fbbf24" stroke-width="18" stroke-linecap="round"/>""",
    },
    "journal.svg": {
        "label": "Journal",
        "bg1": "#fafaf9", "bg2": "#e7e5e4",
        "body": """
  <rect x="210" y="95" width="220" height="260" rx="10" fill="#78350f"/>
  <rect x="225" y="110" width="190" height="230" rx="6" fill="#fef3c7"/>
  <line x1="250" y1="150" x2="390" y2="150" stroke="#d6d3d1" stroke-width="4"/>
  <line x1="250" y1="190" x2="390" y2="190" stroke="#d6d3d1" stroke-width="4"/>
  <line x1="250" y1="230" x2="360" y2="230" stroke="#d6d3d1" stroke-width="4"/>""",
    },
    "pen-set.svg": {
        "label": "Pen set",
        "bg1": "#f8fafc", "bg2": "#e2e8f0",
        "body": """
  <rect x="170" y="250" width="300" height="70" rx="10" fill="#1e293b"/>
  <rect x="190" y="265" width="260" height="40" rx="6" fill="#0f172a"/>
  <rect x="230" y="130" width="18" height="150" rx="8" fill="#334155" transform="rotate(-12 239 205)"/>
  <rect x="290" y="120" width="20" height="160" rx="8" fill="#64748b" transform="rotate(8 300 200)"/>
  <circle cx="239" cy="132" r="10" fill="#fbbf24" transform="rotate(-12 239 205)"/>""",
    },
    "safety-vest.svg": {
        "label": "Safety vest",
        "bg1": "#fefce8", "bg2": "#fef08a",
        "body": """
  <path d="M220 110 L280 130 L360 130 L420 110 L450 170 L420 330 H220 L190 170 Z" fill="#facc15"/>
  <path d="M280 130 V330 M360 130 V330" stroke="#ca8a04" stroke-width="10"/>
  <rect x="250" y="180" width="140" height="22" rx="4" fill="#fef08a" opacity="0.9"/>
  <rect x="250" y="230" width="140" height="22" rx="4" fill="#fef08a" opacity="0.9"/>""",
    },
    "hard-hat.svg": {
        "label": "Hard hat",
        "bg1": "#fffbeb", "bg2": "#fde68a",
        "body": """
  <path d="M170 250 C170 150 250 95 320 95 C390 95 470 150 470 250 Z" fill="#fbbf24"/>
  <rect x="165" y="245" width="310" height="28" rx="8" fill="#d97706"/>
  <rect x="285" y="70" width="70" height="35" rx="10" fill="#f59e0b"/>""",
    },
    "work-polo.svg": {
        "label": "Work polo",
        "bg1": "#eff6ff", "bg2": "#dbeafe",
        "body": """
  <path d="M210 120 L260 95 L320 130 L380 95 L430 120 L400 170 V330 H240 V170 Z" fill="#2563eb"/>
  <path d="M300 130 L320 155 L340 130 V180 H300 Z" fill="#1d4ed8"/>
  <rect x="250" y="210" width="140" height="50" rx="6" fill="#93c5fd" opacity="0.45"/>""",
    },
    "softshell-jacket.svg": {
        "label": "Softshell jacket",
        "bg1": "#f1f5f9", "bg2": "#cbd5e1",
        "body": """
  <path d="M200 120 L250 95 L320 140 L390 95 L440 120 L420 180 V340 H220 V180 Z" fill="#334155"/>
  <path d="M300 140 L320 170 L340 140 V210 H300 Z" fill="#1e293b"/>
  <line x1="320" y1="170" x2="320" y2="340" stroke="#475569" stroke-width="4"/>
  <rect x="250" y="250" width="140" height="16" rx="4" fill="#64748b" opacity="0.6"/>""",
    },
    "lanyard-badge.svg": {
        "label": "Lanyard and badge",
        "bg1": "#eef2ff", "bg2": "#c7d2fe",
        "body": """
  <path d="M260 60 C300 120 340 120 380 60" fill="none" stroke="#4f46e5" stroke-width="16" stroke-linecap="round"/>
  <rect x="255" y="150" width="130" height="180" rx="14" fill="#ffffff" stroke="#6366f1" stroke-width="6"/>
  <circle cx="320" cy="205" r="28" fill="#c7d2fe"/>
  <rect x="280" y="250" width="80" height="12" rx="4" fill="#e0e7ff"/>
  <rect x="290" y="275" width="60" height="10" rx="4" fill="#e0e7ff"/>""",
    },
    "conference-tee.svg": {
        "label": "Conference t-shirt",
        "bg1": "#f8fafc", "bg2": "#e2e8f0",
        "body": """
  <path d="M180 170 L230 130 L320 170 L410 130 L460 170 L430 210 V320 H210 V210 Z" fill="#ffffff" stroke="#cbd5e1" stroke-width="4"/>
  <path d="M300 170 L320 195 L340 170 V220 H300 Z" fill="#e2e8f0"/>
  <rect x="250" y="240" width="140" height="40" rx="8" fill="#94a3b8" opacity="0.25"/>""",
    },
    "banner-stand.svg": {
        "label": "Banner stand",
        "bg1": "#f8fafc", "bg2": "#e2e8f0",
        "body": """
  <rect x="250" y="70" width="140" height="250" rx="6" fill="#ffffff" stroke="#94a3b8" stroke-width="4"/>
  <rect x="265" y="90" width="110" height="50" rx="4" fill="#3b82f6"/>
  <rect x="265" y="155" width="110" height="12" rx="3" fill="#cbd5e1"/>
  <rect x="265" y="180" width="90" height="12" rx="3" fill="#cbd5e1"/>
  <rect x="300" y="320" width="40" height="55" fill="#64748b"/>
  <rect x="270" y="370" width="100" height="12" rx="4" fill="#475569"/>""",
    },
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, spec in PRODUCTS.items():
        svg = SVG_TEMPLATE.format(**spec)
        (OUT / fname).write_text(svg, encoding="utf-8")
        print(f"OK  {fname}")


if __name__ == "__main__":
    main()
