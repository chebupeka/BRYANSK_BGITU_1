from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Mm, Pt, RGBColor

from app.schemas import DocumentContent, DocumentType, Template

ALIGNMENTS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}


def generate_docx(content: DocumentContent, doc_type: DocumentType, template: Template) -> bytes:
    """Type controls content/order; template controls presentation, never wording."""
    doc = Document()
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.title = doc_type.title
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    for side, value in template.margins_mm.items():
        setattr(section, f"{side}_margin", Mm(value))

    normal = doc.styles["Normal"]
    normal.font.name = template.font
    normal.font.size = Pt(template.font_size)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.line_spacing = template.line_spacing
    normal.paragraph_format.space_after = Pt(template.paragraph_space_after_pt)
    normal.paragraph_format.widow_control = True
    title = doc.styles["Title"]
    title.font.name = template.font
    title.font.size = Pt(template.font_size + 2)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.space_before = Pt(16)
    title.paragraph_format.space_after = Pt(12)
    title.paragraph_format.keep_with_next = True

    fields = {field.id: field for field in doc_type.fields}
    for block in doc_type.blocks:
        if block == "title":
            paragraph = doc.add_paragraph(doc_type.title, style="Title")
            paragraph.alignment = ALIGNMENTS[template.title_alignment]
        elif block == "body":
            for text in content.body:
                paragraph = doc.add_paragraph(text)
                paragraph.alignment = ALIGNMENTS[template.body_alignment]
                paragraph.paragraph_format.first_line_indent = Mm(template.first_line_indent_mm)
        else:
            field = fields[block]
            value = content.requisites.get(block, "").strip()
            if not value and not field.required:
                continue
            paragraph = doc.add_paragraph()
            paragraph.add_run(f"{field.label}: ").bold = True
            paragraph.add_run(value or f"[Заполнить: {field.label}]")
            if block in {"recipient", "sender"}:
                paragraph.alignment = ALIGNMENTS[template.recipient_alignment]

    output = BytesIO()
    doc.save(output)
    return output.getvalue()
