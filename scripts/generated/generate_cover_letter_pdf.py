from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY, TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
from reportlab.lib.colors import HexColor

OUTPUT = "outputs/felipe_armel_cv_cover_letter_chief_of_staff_dehaze_en.pdf"

doc = SimpleDocTemplate(
    OUTPUT,
    pagesize=A4,
    leftMargin=2.54*cm,
    rightMargin=2.54*cm,
    topMargin=2.54*cm,
    bottomMargin=2.54*cm,
)

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "CoverTitle",
    parent=styles["Normal"],
    fontSize=14,
    leading=18,
    spaceAfter=12,
    fontName="Helvetica-Bold",
)

contact_style = ParagraphStyle(
    "Contact",
    parent=styles["Normal"],
    fontSize=10,
    leading=14,
    spaceAfter=2,
    fontName="Helvetica",
)

link_style = ParagraphStyle(
    "Link",
    parent=styles["Normal"],
    fontSize=10,
    leading=14,
    spaceAfter=2,
    fontName="Helvetica",
    textColor=HexColor("#0000EE"),
)

body_style = ParagraphStyle(
    "Body",
    parent=styles["Normal"],
    fontSize=11,
    leading=16,
    spaceAfter=8,
    alignment=TA_JUSTIFY,
    fontName="Helvetica",
)

salutation_style = ParagraphStyle(
    "Salutation",
    parent=styles["Normal"],
    fontSize=11,
    leading=16,
    spaceAfter=10,
    fontName="Helvetica",
)

elements = []

elements.append(Paragraph("Cover Letter — Felipe Armel Dias da Silva", title_style))
elements.append(Paragraph("Felipe Armel Dias da Silva", contact_style))
elements.append(Paragraph('<a href="https://linkedin.com/in/felipearmel" color="#0000EE">linkedin.com/in/felipearmel</a>', link_style))
elements.append(Paragraph('<a href="https://wa.me/5511986748218" color="#0000EE">(11) 98674-8218</a>', link_style))
elements.append(Paragraph('<a href="mailto:armelfelipe@gmail.com" color="#0000EE">armelfelipe@gmail.com</a>', link_style))

elements.append(Spacer(1, 16))
elements.append(Paragraph("Dear dehaze team,", salutation_style))

elements.append(Paragraph(
    "With 20+ years building and scaling operations from scratch — including a 15% impact on gross margin "
    "and 13% cost reduction in a startup context — I want to share my strong interest in the "
    "<b>Chief of Staff - Brazil</b> position.",
    body_style
))

elements.append(Paragraph(
    "What draws me to dehaze is the mission to catch what 31% of chronic diagnoses currently miss by "
    "building AI infrastructure on existing, unharmonized health data. Saving 10% of health spend for "
    "insurers while helping patients live healthier lives is the kind of problem where operational "
    "execution directly translates to real-world impact. That is exactly the space where I believe I "
    "can contribute most directly: being on the ground in Brazil, opening doors, and building the "
    "structure that makes the mission possible.",
    body_style
))

elements.append(Paragraph(
    "My experience building operations from scratch — specifically at <b>wehandle</b>, where I "
    "reported directly to the CEO, built CX and data capabilities before the data team existed, and "
    "impacted 15% of gross margin — connects directly with what this role demands: a first employee "
    "in Brazil who can build the backbone of the operation while the CEO is not physically present. "
    "In parallel, my experience at iFood shows I can operate at scale — owning a R$300MM annual P&L, "
    "leading monthly S&OP executive with C-level, and managing 240 people across 800 cities.",
    body_style
))

elements.append(Paragraph(
    "I would welcome the opportunity to discuss how my background can contribute to dehaze's growth "
    "in Brazil.",
    body_style
))

elements.append(Spacer(1, 12))
elements.append(Paragraph("Best regards,", body_style))
elements.append(Spacer(1, 12))
elements.append(Paragraph("Felipe Armel Dias da Silva", contact_style))

doc.build(elements)
print(f"PDF generated: {OUTPUT}")
