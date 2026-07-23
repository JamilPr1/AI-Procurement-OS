"""Generate a short team marketing PDF from TEAM-GUIDE.md."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

DEMO_STORE = "https://ai-procurement-os.onrender.com/store?tenant=demo"


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _inline(text: str) -> str:
    text = _esc(text.strip())
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`([^`]+)`", r"<font face='Courier' size='8'>\1</font>", text)
    return text


def generate_marketing_pdf(marketing_dir: Path, output_path: Path) -> Path:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as e:
        raise RuntimeError("reportlab required: pip install reportlab") from e

    guide = marketing_dir / "TEAM-GUIDE.md"
    if not guide.exists():
        raise FileNotFoundError(f"Missing {guide}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    margin = 0.7 * inch
    pw, _ = letter
    cw = pw - 2 * margin

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=0.65 * inch,
        bottomMargin=0.55 * inch,
        title="AI Procurement OS — Team Marketing Guide",
    )

    base = getSampleStyleSheet()
    brand = colors.HexColor("#1e40af")
    muted = colors.HexColor("#64748b")

    h1 = ParagraphStyle("H1", parent=base["Heading1"], fontSize=14, leading=17, textColor=brand, spaceAfter=6)
    h2 = ParagraphStyle("H2", parent=base["Heading2"], fontSize=11, leading=14, textColor=colors.HexColor("#1e3a8a"), spaceAfter=4, spaceBefore=6)
    body = ParagraphStyle("Body", parent=base["Normal"], fontSize=9, leading=12, spaceAfter=3)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=10, spaceAfter=2)
    code = ParagraphStyle("Code", parent=body, fontName="Courier", fontSize=7.5, leading=10, leftIndent=8, spaceAfter=4)
    title = ParagraphStyle("Title", parent=base["Title"], fontSize=22, leading=26, textColor=brand, alignment=TA_CENTER, spaceAfter=4)
    sub = ParagraphStyle("Sub", parent=body, fontSize=10, textColor=muted, alignment=TA_CENTER, spaceAfter=10)

    story: list[Any] = []
    lines = guide.read_text(encoding="utf-8").splitlines()
    i = 0
    in_code = False
    code_buf: list[str] = []
    table_buf: list[str] = []

    def flush_code() -> None:
        nonlocal code_buf
        if code_buf:
            story.append(Paragraph("<br/>".join(_esc(l) for l in code_buf), code))
            code_buf = []

    def flush_table() -> None:
        nonlocal table_buf
        if not table_buf:
            return
        rows_raw = [r for r in table_buf if r.strip() and not re.match(r"^\|[-:\s|]+\|$", r.strip())]
        table_buf = []
        if len(rows_raw) < 2:
            return
        rows = [[Paragraph(_inline(c), body if ri else ParagraphStyle("TH", parent=body, fontName="Helvetica-Bold", textColor=colors.white))
                 for c in row.strip().strip("|").split("|")]
                for ri, row in enumerate(rows_raw)]
        n = len(rows[0])
        t = Table(rows, colWidths=[cw / n] * n, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    # Cover
    story.append(Spacer(1, 0.8 * inch))
    story.append(Paragraph("AI Procurement OS", title))
    story.append(Paragraph("Team Marketing Guide", sub))
    story.append(Paragraph(f"Updated {datetime.now().strftime('%B %d, %Y')}", sub))
    story.append(Paragraph(f'<a href="{DEMO_STORE}" color="blue">{DEMO_STORE}</a>', sub))
    story.append(PageBreak())

    while i < len(lines):
        line = lines[i]
        s = line.strip()

        if s.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if s.startswith("|"):
            table_buf.append(s)
            i += 1
            continue
        flush_table()

        if not s or s == "---":
            i += 1
            continue
        if s.startswith("# "):
            story.append(Paragraph(_inline(s[2:]), h1))
        elif s.startswith("## "):
            story.append(Paragraph(_inline(s[3:]), h2))
        elif s.startswith("> "):
            story.append(Paragraph(f"<i>{_inline(s[2:])}</i>", body))
        elif s.startswith("- "):
            items = []
            while i < len(lines) and lines[i].strip().startswith("- "):
                items.append(ListItem(Paragraph(_inline(lines[i].strip()[2:]), bullet), leftIndent=4))
                i += 1
            if items:
                story.append(ListFlowable(items, bulletType="bullet", start="•", leftIndent=8))
            continue
        else:
            story.append(Paragraph(_inline(s), body))
        i += 1

    flush_code()
    flush_table()

    def footer(canvas, doc_obj):  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(muted)
        canvas.drawString(margin, 0.4 * inch, "AI Procurement OS — Team Marketing Guide")
        canvas.drawRightString(pw - margin, 0.4 * inch, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output_path
