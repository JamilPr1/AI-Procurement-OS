"""Generate simple social post images (one per platform)."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

POST_SPECS: list[dict[str, Any]] = [
    {"platform": "linkedin", "num": 1, "headline": "Stop losing deals\nin email chaos", "subline": "One platform from buyer research to factory quotes", "bullets": ["11-step sourcing pipeline", "AI-drafted RFQs & proposals", "Branded quote stores"], "accent": "#3b82f6"},
    {"platform": "facebook", "num": 1, "headline": "Sound familiar? 😅", "subline": "47 tabs open. Still can't find that RFQ.", "bullets": ["One system for sourcing", "AI helps, you approve", "Try the demo store →"], "accent": "#8b5cf6"},
    {"platform": "instagram", "num": 1, "headline": "6 tools → 1 platform", "subline": "AI Procurement OS", "bullets": ["Lead to delivery", "Branded stores", "Link in bio 👆"], "accent": "#ec4899"},
]

STORY_SPEC = {"num": 1, "headline": "Free 14-day\npilot", "subline": "Branded store + CRM setup", "bullets": ["No credit card", "Onboarding included"], "accent": "#8b5cf6"}


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _draw_gradient(img, color_top: str, color_bottom: str) -> None:
    from PIL import ImageDraw

    w, h = img.size
    draw = ImageDraw.Draw(img)
    r1, g1, b1 = _hex_to_rgb(color_top)
    r2, g2, b2 = _hex_to_rgb(color_bottom)
    for y in range(h):
        t = y / max(h - 1, 1)
        draw.line([(0, y), (w, y)], fill=(
            int(r1 + (r2 - r1) * t),
            int(g1 + (g2 - g1) * t),
            int(b1 + (b2 - b1) * t),
        ))


def _get_font(size: int, bold: bool = False):
    from PIL import ImageFont

    paths = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"] if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _draw_wrapped_text(draw, text: str, xy: tuple[int, int], font, fill: str, line_spacing: int = 8) -> int:
    x, y = xy
    for paragraph in text.split("\n"):
        for line in textwrap.wrap(paragraph, width=28) if paragraph.strip() else [""]:
            draw.text((x, y), line, font=font, fill=fill)
            y += draw.textbbox((x, y), line, font=font)[3] - draw.textbbox((x, y), line, font=font)[1] + line_spacing
    return y


def _render_post(spec: dict[str, Any], out_path: Path, *, size: tuple[int, int] = (1080, 1080)) -> Path:
    from PIL import Image, ImageDraw

    accent = spec.get("accent", "#3b82f6")
    img = Image.new("RGB", size, "#0b1220")
    _draw_gradient(img, "#0b1220", "#111827")
    draw = ImageDraw.Draw(img)
    ar, ag, ab = _hex_to_rgb(accent)

    draw.rounded_rectangle((60, 60, 140, 140), radius=16, fill=(ar, ag, ab))
    draw.text((78, 82), "AI", font=_get_font(36, bold=True), fill="white")

    y = _draw_wrapped_text(draw, spec["headline"], (60, 180), _get_font(56, bold=True), "#ffffff")
    y += 10
    draw.text((60, y), spec.get("subline", ""), font=_get_font(28), fill="#94a3b8")
    y += 50
    for bullet in spec.get("bullets", []):
        draw.ellipse((60, y + 8, 76, y + 24), fill=(ar, ag, ab))
        draw.text((90, y), bullet, font=_get_font(26), fill="#e2e8f0")
        y += 48

    draw.rounded_rectangle((60, size[1] - 130, size[0] - 60, size[1] - 60), radius=20, fill=(ar, ag, ab))
    draw.text((90, size[1] - 108), "Try demo store →", font=_get_font(24, bold=True), fill="white")
    draw.text((90, size[1] - 78), "ai-procurement-os.onrender.com", font=_get_font(18), fill="#dbeafe")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG", optimize=True)
    return out_path


def generate_marketing_images(output_dir: Path) -> list[Path]:
    from PIL import Image  # noqa: F401

    created = []
    for spec in POST_SPECS:
        out = output_dir / spec["platform"] / f"post-{spec['num']:02d}.png"
        created.append(_render_post(spec, out))
    return created


def generate_story_images(output_dir: Path) -> list[Path]:
    from PIL import Image  # noqa: F401

    out = output_dir / "instagram" / "story-01.png"
    return [_render_post(STORY_SPEC, out, size=(1080, 1920))]
