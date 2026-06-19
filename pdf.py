"""
pdf.py -- Client-presentation PDF: before/after, style + vision, element list, and
the rough cost estimate. Pure (no network): the caller resolves image bytes and
passes them in, so this module just lays out the document with ReportLab.
"""
from __future__ import annotations

import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
)

from elements import get_element
from styles import get_style


def _money(n) -> str:
    try:
        return "${:,.0f}".format(float(n))
    except (TypeError, ValueError):
        return "—"


def build_pdf(design: dict, prop: dict, cost: dict,
              before_bytes: bytes = None, after_bytes: bytes = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.6 * inch,
                            bottomMargin=0.6 * inch, leftMargin=0.6 * inch,
                            rightMargin=0.6 * inch)
    s = getSampleStyleSheet()
    green = colors.HexColor("#15803d")
    h1 = ParagraphStyle("h1", parent=s["Title"], textColor=green, fontSize=22)
    h2 = ParagraphStyle("h2", parent=s["Heading2"], textColor=green, fontSize=13)
    small = ParagraphStyle("sm", parent=s["Normal"], fontSize=8, textColor=colors.grey)
    flow = []

    style = get_style(design.get("style", "modern"))
    flow.append(Paragraph("Backyard Design Proposal", h1))
    flow.append(Paragraph(design.get("address") or prop.get("address", ""), s["Normal"]))
    flow.append(Paragraph(f"Style: <b>{style['name']}</b>", s["Normal"]))
    flow.append(Spacer(1, 12))

    # before / after
    def _img(b, w=3.3 * inch, h=3.3 * inch):
        try:
            return Image(io.BytesIO(b), width=w, height=h) if b else Paragraph("—", s["Normal"])
        except Exception:
            return Paragraph("(image unavailable)", small)

    ba = Table([[_img(before_bytes), _img(after_bytes)],
                ["Current property", "Proposed design"]],
               colWidths=[3.5 * inch, 3.5 * inch])
    ba.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 1), (-1, 1), 9),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.grey),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
    ]))
    flow.append(ba)
    flow.append(Spacer(1, 14))

    if design.get("vision"):
        flow.append(Paragraph("Vision", h2))
        flow.append(Paragraph(design["vision"], s["Normal"]))
        flow.append(Spacer(1, 10))

    sizes = (prop or {}).get("sizes", {})
    if any(sizes.values()):
        flow.append(Paragraph(
            f"Lot ~{_sz(sizes.get('lot_sqft'))} · House ~{_sz(sizes.get('house_sqft'))} "
            f"· Usable backyard ~{_sz(sizes.get('backyard_sqft'))} (approx).", small))
        flow.append(Spacer(1, 10))

    # elements + cost
    flow.append(Paragraph("Proposed elements & estimated budget", h2))
    data = [["Element", "Details", "Size", "Est. cost"]]
    for li in cost.get("line_items", []):
        data.append([li["label"], li.get("detail", ""), li.get("unit", ""), _money(li["amount"])])
    if len(data) == 1:
        data.append(["(no elements selected)", "", "", ""])
    tbl = Table(data, colWidths=[1.5 * inch, 3.0 * inch, 1.0 * inch, 1.0 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), green),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    flow.append(tbl)
    flow.append(Spacer(1, 8))
    flow.append(Paragraph(
        f"<b>Estimated range: {_money(cost.get('low'))} – {_money(cost.get('high'))}</b>",
        ParagraphStyle("rng", parent=s["Normal"], fontSize=13, textColor=green)))
    flow.append(Spacer(1, 14))
    flow.append(Paragraph(cost.get("note", ""), small))
    flow.append(Spacer(1, 6))
    flow.append(Paragraph(
        "This proposal is an AI-assisted visualization and a rough planning estimate, "
        "not a construction document, survey, or quote.", small))

    doc.build(flow)
    return buf.getvalue()


def _sz(n):
    return f"{n:,} sq ft" if n else "n/a"
