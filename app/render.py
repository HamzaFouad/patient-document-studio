import re
from datetime import date
from html import escape
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import BaseDocTemplate, Frame, HRFlowable, KeepTogether, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .models import DocumentTemplate, GenerateRequest


TOKEN = re.compile(r"{{\s*([a-z][a-z0-9_.]*)\s*}}")


def _font_name() -> str:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("ClinicalUnicode", str(path)))
            return "ClinicalUnicode"
    return "Helvetica"


FONT = _font_name()


def _values(template: DocumentTemplate, request: GenerateRequest) -> dict[str, str]:
    values = {
        "patient.name": request.patient.name,
        "patient.age": str(request.patient.age),
        "patient.medical_history": request.patient.medical_history or "—",
        "doctor.name": request.doctor.name,
        "today": date.today().isoformat(),
    }
    submitted = request.fields.get(template.id, {})
    values.update({f"fields.{field.key}": submitted.get(field.key, "").strip() or "—" for field in template.fields})
    return values


def fill_text(source: str, values: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise ValueError(f"Unknown placeholder: {key}")
        return escape(values[key]).replace("\n", "<br/>")

    return TOKEN.sub(replace, escape(source, quote=False))


def render_pdf(template: DocumentTemplate, request: GenerateRequest) -> bytes:
    values = _values(template, request)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ClinicalTitle", parent=styles["Title"], fontName=FONT, fontSize=18, leading=23, textColor=colors.HexColor("#15334c"), spaceAfter=6)
    subtitle_style = ParagraphStyle("ClinicalSubtitle", parent=styles["Normal"], fontName=FONT, fontSize=9, leading=14, textColor=colors.HexColor("#5f7080"), alignment=TA_CENTER, spaceAfter=20)
    heading_style = ParagraphStyle("ClinicalHeading", parent=styles["Heading2"], fontName=FONT, fontSize=11, leading=16, textColor=colors.HexColor("#176d83"), spaceBefore=14, spaceAfter=7)
    body_style = ParagraphStyle("ClinicalBody", parent=styles["BodyText"], fontName=FONT, fontSize=9.5, leading=15, textColor=colors.HexColor("#273746"), spaceAfter=8)
    label_style = ParagraphStyle("ClinicalLabel", parent=body_style, fontSize=8, leading=13, textColor=colors.HexColor("#637487"))

    story = [Paragraph(escape(template.title), title_style), Paragraph(f"{escape(template.category.upper())}  •  {values['today']}", subtitle_style)]
    for block in template.blocks:
        if block.type == "spacer":
            story.append(Spacer(1, 8 * mm))
        elif block.type == "heading":
            story.append(Paragraph(fill_text(block.text, values), heading_style))
        elif block.type == "paragraph":
            story.append(Paragraph(fill_text(block.text, values), body_style))
        elif block.type == "field":
            filled = fill_text(block.text, values)
            if len(filled) > 300 or filled.count("<br/>") > 4:
                story.extend([
                    Paragraph(escape(block.label), label_style),
                    Paragraph(filled, body_style),
                    HRFlowable(width="100%", thickness=0.35, color=colors.HexColor("#dce5ea"), spaceAfter=8),
                ])
            else:
                row = Table([[Paragraph(escape(block.label), label_style), Paragraph(filled, body_style)]], colWidths=[43 * mm, 120 * mm], hAlign="LEFT")
                row.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.HexColor("#dce5ea")), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
                story.append(KeepTogether(row))

    buffer = BytesIO()
    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=23 * mm, rightMargin=23 * mm, topMargin=25 * mm, bottomMargin=23 * mm, title=template.title)
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def page_decoration(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#dce5ea"))
        canvas.line(23 * mm, 18 * mm, 187 * mm, 18 * mm)
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#738595"))
        canvas.drawString(23 * mm, 13 * mm, "Patient Document Studio")
        canvas.drawRightString(187 * mm, 13 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.addPageTemplates(PageTemplate(id="clinical", frames=frame, onPage=page_decoration))
    doc.build(story)
    return buffer.getvalue()
