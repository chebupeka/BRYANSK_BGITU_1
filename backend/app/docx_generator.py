import re
from dataclasses import dataclass, field
from io import BytesIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor

from app.schemas import DocumentContent, DocumentType, RequisiteField, Template

ALIGNMENTS = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}

PAGE_WIDTH_MM = 210
PAGE_HEIGHT_MM = 297
LANGUAGE = "ru-RU"
NBSP = "\u00a0"
# Word prefers theme font attributes over explicit names, so they must be removed.
THEME_FONT_ATTRS = ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme")
FONT_ATTRS = ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs")
SIGN_BEFORE_NUMBER = re.compile(r"([№§]) (?=\d)")
GROUPED_NUMBER = re.compile(r"(?<!\d)(?<!\d )\d{1,3}(?: \d{3})+(?!\d)")

# Requisites printed as compact blocks with single line spacing.
COMPACT = {
    "letterhead", "letterhead_details", "addressee", "registration", "reference",
    "headline", "signature", "executor",
}
# Pairs of blocks that visually belong together and need no gap between them.
ATTACHED = {("letterhead", "letterhead_details"), ("registration", "reference")}
WIDE_GAP = {"signature", "executor"}


def keep_together(text: str) -> str:
    """Replace spaces that must not break a line: «№ 214», «30 000».

    Letters, digits and punctuation stay unchanged; only the kind of space differs.
    """
    text = SIGN_BEFORE_NUMBER.sub(rf"\1{NBSP}", text)
    return GROUPED_NUMBER.sub(lambda match: match.group(0).replace(" ", NBSP), text)


def set_fonts(rpr, font: str) -> None:
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in THEME_FONT_ATTRS:
        rfonts.attrib.pop(qn(attr), None)
    for attr in FONT_ATTRS:
        rfonts.set(qn(attr), font)


def remove_children(parent, *tags: str) -> None:
    if parent is None:
        return
    for tag in tags:
        for child in parent.findall(qn(tag)):
            parent.remove(child)


def apply_document_defaults(doc, template: Template) -> None:
    defaults = doc.styles.element.find(qn("w:docDefaults"))
    rpr = defaults.find(qn("w:rPrDefault")).find(qn("w:rPr"))
    set_fonts(rpr, template.font)
    lang = rpr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        rpr.append(lang)
    lang.set(qn("w:val"), LANGUAGE)


def apply_styles(doc, template: Template) -> None:
    apply_document_defaults(doc, template)
    normal = doc.styles["Normal"]
    set_fonts(normal.element.get_or_add_rPr(), template.font)
    normal.font.size = Pt(template.font_size)
    normal.font.color.rgb = RGBColor(0, 0, 0)
    normal.paragraph_format.line_spacing = template.line_spacing
    normal.paragraph_format.space_after = Pt(template.paragraph_space_after_pt)
    normal.paragraph_format.widow_control = True

    title = doc.styles["Title"]
    title_rpr = title.element.get_or_add_rPr()
    set_fonts(title_rpr, template.font)
    # The default python-docx Title has a blue bottom border, letter spacing and kerning.
    remove_children(title.element.pPr, "w:pBdr")
    remove_children(title_rpr, "w:spacing", "w:kern", "w:szCs")
    title.font.size = Pt(template.font_size + 2)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.space_before = Pt(16)
    title.paragraph_format.space_after = Pt(12)
    title.paragraph_format.keep_with_next = True


def add_page_numbers(section) -> None:
    """Page number at the top center, starting from the second page."""
    section.different_first_page_header_footer = True
    paragraph = section.header.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    page_field = OxmlElement("w:fldSimple")
    page_field.set(qn("w:instr"), "PAGE")
    run = OxmlElement("w:r")
    text = OxmlElement("w:t")
    text.text = "2"
    run.append(text)
    page_field.append(run)
    paragraph._p.append(page_field)


@dataclass
class Block:
    kind: str
    items: list[tuple[RequisiteField, str]] = field(default_factory=list)


def arrange_blocks(content: DocumentContent, doc_type: DocumentType) -> list[Block]:
    """Skip empty optional requisites and merge neighbours with the same placement."""
    fields = {item.id: item for item in doc_type.fields}
    blocks: list[Block] = []
    for name in doc_type.blocks:
        if name in {"title", "body"}:
            if name == "body" or doc_type.show_title:
                blocks.append(Block(name))
            continue
        requisite = fields[name]
        value = content.requisites.get(name, "").strip()
        if not value and not requisite.required:
            continue
        if not blocks or blocks[-1].kind != requisite.placement:
            blocks.append(Block(requisite.placement))
        blocks[-1].items.append((requisite, value))
    return blocks


def requisite_text(requisite: RequisiteField, value: str) -> str:
    if not value:
        return f"{requisite.prefix}[Заполнить: {requisite.label}]"
    return keep_together(requisite.prefix + value)


class Writer:
    def __init__(self, doc, template: Template, doc_type: DocumentType, content: DocumentContent):
        self.doc = doc
        self.template = template
        self.doc_type = doc_type
        self.content = content
        margins = template.margins_mm
        self.text_width_mm = PAGE_WIDTH_MM - margins["left"] - margins["right"]
        self.gap = Pt(template.font_size)

    def paragraph(self, text: str = "", alignment: str = "left"):
        paragraph = self.doc.add_paragraph(text)
        paragraph.alignment = ALIGNMENTS[alignment]
        return paragraph

    def write(self, block: Block) -> list:
        template = self.template
        texts = [requisite_text(requisite, value) for requisite, value in block.items]
        if block.kind == "title":
            paragraph = self.doc.add_paragraph(self.doc_type.title, style="Title")
            paragraph.alignment = ALIGNMENTS[template.title_alignment]
            return [paragraph]
        if block.kind == "body":
            paragraphs = []
            for text in self.content.body:
                paragraph = self.paragraph(keep_together(text), template.body_alignment)
                paragraph.paragraph_format.first_line_indent = Mm(template.first_line_indent_mm)
                paragraphs.append(paragraph)
            return paragraphs
        if block.kind in {"letterhead", "letterhead_details"}:
            paragraphs = [self.paragraph(text, template.letterhead_alignment) for text in texts]
            if block.kind == "letterhead_details":
                self.set_small_font(paragraphs)
            return paragraphs
        if block.kind == "addressee":
            return [self.addressee(text) for text in texts]
        if block.kind in {"registration", "reference"}:
            return [self.paragraph(" ".join(texts))]
        if block.kind == "headline":
            paragraph = self.paragraph(" ".join(texts), template.headline_alignment)
            paragraph.paragraph_format.keep_with_next = True
            for run in paragraph.runs:
                run.bold = template.headline_bold
            return [paragraph]
        if block.kind == "signature":
            return [self.signature(texts)]
        if block.kind == "executor":
            paragraphs = [self.paragraph(text) for text in texts]
            self.set_small_font(paragraphs)
            return paragraphs
        if block.kind == "paragraph":
            return [self.paragraph(text) for text in texts]
        return [self.labeled(requisite, value) for requisite, value in block.items]

    def addressee(self, text: str):
        alignment = self.template.recipient_alignment
        if alignment == "right":
            # Standard corner block: lines start in the right part of the page and wrap there.
            paragraph = self.paragraph(text)
            indent = self.text_width_mm - self.template.addressee_width_mm
            paragraph.paragraph_format.left_indent = Mm(indent)
            return paragraph
        return self.paragraph(text, alignment)

    def signature(self, texts: list[str]):
        # Position on the left, name at the right margin: «Заведующий   И. И. Иванов».
        left, right = " ".join(texts[:-1]), texts[-1]
        paragraph = self.paragraph(f"{left}\t{right}")
        paragraph.paragraph_format.tab_stops.add_tab_stop(
            Mm(self.text_width_mm), WD_TAB_ALIGNMENT.RIGHT
        )
        return paragraph

    def labeled(self, requisite: RequisiteField, value: str):
        paragraph = self.paragraph()
        paragraph.add_run(f"{requisite.label}: ").bold = True
        paragraph.add_run(keep_together(value) if value else f"[Заполнить: {requisite.label}]")
        return paragraph

    def set_small_font(self, paragraphs: list) -> None:
        for paragraph in paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(self.template.small_font_size)

    def space_before(self, kind: str, previous: str | None):
        if previous is None or previous == "title" or (previous, kind) in ATTACHED:
            return Pt(0)
        return self.gap * 2 if kind in WIDE_GAP else self.gap


def generate_docx(content: DocumentContent, doc_type: DocumentType, template: Template) -> bytes:
    """Type controls content and placement; template controls presentation, never wording."""
    doc = Document()
    doc.core_properties.author = ""
    doc.core_properties.last_modified_by = ""
    doc.core_properties.title = doc_type.title
    doc.core_properties.language = LANGUAGE
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(PAGE_WIDTH_MM), Mm(PAGE_HEIGHT_MM)
    for side, value in template.margins_mm.items():
        setattr(section, f"{side}_margin", Mm(value))
    apply_styles(doc, template)
    if template.page_numbers:
        add_page_numbers(section)

    writer = Writer(doc, template, doc_type, content)
    previous, previous_last = None, None
    for block in arrange_blocks(content, doc_type):
        paragraphs = writer.write(block)
        if block.kind != "title":
            paragraphs[0].paragraph_format.space_before = writer.space_before(block.kind, previous)
        if (previous, block.kind) in ATTACHED:
            previous_last.paragraph_format.space_after = Pt(0)
        if block.kind == "signature" and previous_last is not None:
            # The signature must not be alone on a page.
            previous_last.paragraph_format.keep_with_next = True
        if block.kind in COMPACT:
            # Addressee lines of different fields («кому» / «от кого») get a small gap.
            inner_gap = Pt(template.font_size / 2) if block.kind == "addressee" else Pt(0)
            for paragraph in paragraphs:
                paragraph.paragraph_format.line_spacing = 1
            for paragraph in paragraphs[:-1]:
                paragraph.paragraph_format.space_after = inner_gap
        previous, previous_last = block.kind, paragraphs[-1]

    output = BytesIO()
    doc.save(output)
    return output.getvalue()
