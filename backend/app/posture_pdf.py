"""
"IP Posture Summary" PDF export.

Turns one /api/analyze result into a downloadable, timestamped PDF a founder
could actually hand to a patent attorney or facilitator — the same fields
already shown in the UI (query, classification, jurisdiction, cited answer,
confidence, sources, escalation status), laid out as a standalone document
rather than a chat answer.

Deliberately renders ONLY fields that were actually present on the analyzed
result — no field is invented here. If sources is empty (an abstained
result), the PDF says so instead of printing a blank section.
"""
import io
from datetime import datetime, timezone
from typing import Any, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

GREEN_DARK = HexColor("#142A1F")
GREEN = HexColor("#1F3B2C")
GOLD_DARK = HexColor("#8F6A22")
INK = HexColor("#1C2420")
HAIRLINE = HexColor("#DED6C0")
PAPER_DIM = HexColor("#F2EEE1")


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("SutraTitle", parent=ss["Title"], textColor=GREEN_DARK, fontSize=20, spaceAfter=2))
    ss.add(ParagraphStyle("SutraSub", parent=ss["Normal"], textColor=GOLD_DARK, fontSize=10, spaceAfter=10))
    ss.add(ParagraphStyle("SutraH2", parent=ss["Heading2"], textColor=GREEN_DARK, fontSize=13, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle("SutraBody", parent=ss["Normal"], textColor=INK, fontSize=10, leading=14))
    ss.add(ParagraphStyle("SutraMuted", parent=ss["Normal"], textColor=HexColor("#4B5750"), fontSize=8.5, leading=12))
    return ss


def build_posture_pdf(result: Dict[str, Any], query: str) -> bytes:
    """
    `result` is the same dict/JSON shape as AnalyzeResponse. Returns raw PDF
    bytes, ready to stream back as an application/pdf response.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title="SUTRADHARA IP Posture Summary",
    )
    ss = _styles()
    story = []

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph("SUTRADHARA — IP Posture Summary", ss["SutraTitle"]))
    story.append(Paragraph(f"Generated {generated_at} &nbsp;·&nbsp; Informational summary, not legal advice", ss["SutraSub"]))
    story.append(HRFlowable(width="100%", thickness=1, color=HAIRLINE, spaceAfter=10))

    story.append(Paragraph("Query", ss["SutraH2"]))
    story.append(Paragraph(query or "—", ss["SutraBody"]))

    classification = result.get("classification") or {}
    meta_rows = [
        ["Classification", classification.get("category", "—")],
        ["Jurisdiction", result.get("jurisdiction", "—")],
        ["Input language", (result.get("input_language") or "en").upper()],
        ["Confidence", f'{result.get("confidence_label", "—")}  ({result.get("confidence", 0)})'],
        ["Status", "Safe abstention (insufficient evidence)" if result.get("abstained") else "Answered with cited evidence"],
    ]
    meta_table = Table(meta_rows, colWidths=[42 * mm, 118 * mm])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (0, -1), GOLD_DARK),
        ("TEXTCOLOR", (1, 0), (1, -1), INK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, HAIRLINE),
    ]))
    story.append(meta_table)

    areas = result.get("applicable_areas") or []
    if areas:
        story.append(Paragraph("Applicable IP &amp; Regulatory Areas", ss["SutraH2"]))
        story.append(Paragraph(" &nbsp;•&nbsp; ".join(areas), ss["SutraBody"]))

    story.append(Paragraph("AI Assessment" if not result.get("abstained") else "Evidence Boundary", ss["SutraH2"]))
    if classification.get("needs_clarification") and classification.get("clarification_question"):
        story.append(Paragraph(
            "This query needed one clarifying question before an assessment could be produced:",
            ss["SutraBody"],
        ))
        story.append(Paragraph(classification["clarification_question"], ss["SutraBody"]))
    else:
        story.append(Paragraph((result.get("answer") or "—").replace("\n\n", "<br/><br/>").replace("\n", "<br/>"), ss["SutraBody"]))

    tk_pointer = result.get("tk_pointer")
    if tk_pointer:
        story.append(Paragraph("Traditional Knowledge / Prior-Art Pointer", ss["SutraH2"]))
        story.append(Paragraph(tk_pointer, ss["SutraBody"]))

    pathway = result.get("regulatory_pathway") or []
    if pathway:
        story.append(Paragraph("Indicative Regulatory Pathway", ss["SutraH2"]))
        step_style = ParagraphStyle("SutraStep", parent=ss["SutraBody"], spaceAfter=6)
        for i, step in enumerate(pathway, 1):
            story.append(Paragraph(f"{i}. {step}", step_style))
        story.append(Paragraph(
            "Indicative administrative sequence only — not legal advice and not a guarantee of any outcome.",
            ss["SutraMuted"],
        ))

    sources = result.get("sources") or []
    story.append(Paragraph("Evidence &amp; Citations", ss["SutraH2"]))
    if sources:
        cell_style = ParagraphStyle("SutraCell", parent=ss["SutraBody"], fontSize=8.5, leading=11)
        header_style = ParagraphStyle("SutraCellHeader", parent=cell_style, textColor=HexColor("#FAF7EF"), fontName="Helvetica-Bold")
        rows = [[Paragraph(h, header_style) for h in ["#", "Source", "Section", "Authority"]]]
        for i, s in enumerate(sources, 1):
            rows.append([
                Paragraph(str(i), cell_style),
                Paragraph(s.get("title", "—"), cell_style),
                Paragraph(s.get("section", "—"), cell_style),
                Paragraph(s.get("authority", "—"), cell_style),
            ])
        src_table = Table(rows, colWidths=[8 * mm, 55 * mm, 47 * mm, 45 * mm], repeatRows=1)
        src_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREEN),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFE"), PAPER_DIM]),
            ("GRID", (0, 0), (-1, -1), 0.4, HAIRLINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(src_table)
    else:
        story.append(Paragraph("No sources met the evidence threshold for this query.", ss["SutraBody"]))

    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=1, color=HAIRLINE, spaceAfter=6))
    story.append(Paragraph(
        "SUTRADHARA is an informational assistant, not a law firm or a substitute for legal advice. "
        "Verify every citation and filing step with a qualified IP professional or the named authority "
        "before acting. Generated automatically from the retrieved evidence for this query only.",
        ss["SutraMuted"],
    ))

    doc.build(story)
    return buf.getvalue()
