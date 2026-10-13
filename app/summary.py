from datetime import date
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer

from .render import FONT
from .text import pdf_display_text


def _safe(value: str) -> str:
    return escape(pdf_display_text(value)).replace("\n", "<br/>")


def render_patient_summary(patients: list[dict], orders_by_patient: dict[int, list[dict]]) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=21 * mm, bottomMargin=20 * mm, title="Patient summary")
    title_style = ParagraphStyle("SummaryTitle", fontName=FONT, fontSize=17, leading=22, textColor=colors.HexColor("#15334c"), spaceAfter=5)
    subtitle_style = ParagraphStyle("SummarySubtitle", fontName=FONT, fontSize=8.5, leading=12, textColor=colors.HexColor("#657785"), spaceAfter=17)
    patient_style = ParagraphStyle("SummaryPatient", fontName=FONT, fontSize=11, leading=16, textColor=colors.HexColor("#176d83"), spaceBefore=7, spaceAfter=5, keepWithNext=True)
    body_style = ParagraphStyle("SummaryBody", fontName=FONT, fontSize=8.5, leading=12.5, textColor=colors.HexColor("#273746"), spaceAfter=4)

    story = [
        Paragraph("Patient summary", title_style),
        Paragraph(f"{date.today().isoformat()}  •  {len(patients)} patient{'s' if len(patients) != 1 else ''}", subtitle_style),
    ]
    if not patients:
        story.append(Paragraph("No patients in the registry.", body_style))
    for patient in patients:
        story.append(Paragraph(f"{_safe(patient['code'])}  |  {_safe(patient['name'])}", patient_style))
        story.append(Paragraph(f"<b>Age:</b> {patient['age']}", body_style))
        story.append(Paragraph(f"<b>Medical history:</b> {_safe(patient['medical_history'] or 'Not recorded')}", body_style))
        orders = orders_by_patient.get(patient["id"], [])
        test_names = [test["name"] for order in orders for test in order["tests"]]
        story.append(Paragraph(f"<b>Orders:</b> {_safe(', '.join(test_names) if test_names else 'None')}", body_style))
        story.extend([Spacer(1, 4 * mm), HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#dce5ea"), spaceAfter=3 * mm)])

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont(FONT, 8)
        canvas.setFillColor(colors.HexColor("#738595"))
        canvas.drawString(20 * mm, 12 * mm, "Patient Document Studio")
        canvas.drawRightString(190 * mm, 12 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
