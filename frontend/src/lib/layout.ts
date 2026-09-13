import type {
  Alignment, DocumentContent, DocumentFormatting, DocumentType, Placement, RequisiteField, Template,
} from '../types';

// The live preview mirrors backend/app/docx_generator.py: the same block order, the same
// skipping of empty optional requisites, the same «Заполнить» labels. Everything the DOCX
// generator reads from the catalog is optional over the wire, because older backends of the
// project send a shorter Template — the defaults below are what those backends actually do.

export const PAGE_WIDTH_MM = 210;
export const PAGE_HEIGHT_MM = 297;
/** Width of the label column of the «Кому / От кого» table, in millimetres. */
export const TABLE_LABEL_WIDTH_MM = 35;

export interface ResolvedTemplate {
  id: string;
  name: string;
  description: string;
  font: string;
  fontSize: number;
  margins: { top: number; right: number; bottom: number; left: number };
  lineSpacing: number;
  spaceAfterPt: number;
  firstLineIndentMm: number;
  titleAlignment: Alignment;
  recipientAlignment: Alignment;
  bodyAlignment: Alignment;
  signatureAlignment: Alignment;
  recipientLayout: 'block' | 'table';
  header: 'none' | 'organization';
  footer: 'none' | 'page_number' | 'title_and_date';
  headerFooterFontSize: number;
  letterheadAlignment: Alignment;
  headlineAlignment: Alignment;
  headlineBold: boolean;
  bodyBold: boolean;
  bodyItalic: boolean;
  bodyUnderline: boolean;
  addresseeWidthMm: number;
  smallFontSize: number;
  textWidthMm: number;
}

export function resolveTemplate(template: Template): ResolvedTemplate {
  // Контракт описывает поля как словарь, поэтому собираем нужную форму по ключам.
  const margins = {
    top: template.margins_mm?.top ?? 20,
    right: template.margins_mm?.right ?? 15,
    bottom: template.margins_mm?.bottom ?? 20,
    left: template.margins_mm?.left ?? 30,
  };
  const fontSize = template.font_size;
  return {
    id: template.id,
    name: template.name,
    description: template.description,
    font: template.font,
    fontSize,
    margins,
    lineSpacing: template.line_spacing ?? 1.5,
    spaceAfterPt: template.paragraph_space_after_pt ?? 0,
    firstLineIndentMm: template.first_line_indent_mm ?? 0,
    titleAlignment: template.title_alignment ?? 'center',
    recipientAlignment: template.recipient_alignment ?? 'right',
    bodyAlignment: template.body_alignment ?? 'justify',
    signatureAlignment: template.signature_alignment ?? 'left',
    recipientLayout: template.recipient_layout ?? 'block',
    header: template.header ?? 'none',
    footer: template.footer ?? 'none',
    headerFooterFontSize: template.header_footer_font_size ?? 10,
    letterheadAlignment: template.letterhead_alignment ?? 'center',
    headlineAlignment: template.headline_alignment ?? 'left',
    headlineBold: template.headline_bold ?? false,
    bodyBold: template.body_bold ?? false,
    bodyItalic: template.body_italic ?? false,
    bodyUnderline: template.body_underline ?? false,
    addresseeWidthMm: template.addressee_width_mm ?? 80,
    smallFontSize: template.small_font_size ?? Math.max(8, fontSize - 4),
    textWidthMm: PAGE_WIDTH_MM - margins.left - margins.right,
  };
}

export const EDITOR_FONTS: DocumentFormatting['font'][] = [
  'Times New Roman', 'Arial', 'Calibri', 'Georgia', 'Courier New',
];

/** Word-like controls start with the selected catalog template's current values. */
export function formattingForTemplate(template: Template): DocumentFormatting {
  return {
    font: EDITOR_FONTS.includes(template.font as DocumentFormatting['font'])
      ? template.font as DocumentFormatting['font'] : 'Arial',
    font_size: template.font_size,
    line_spacing: template.line_spacing ?? 1.5,
    paragraph_space_after_pt: template.paragraph_space_after_pt ?? 0,
    first_line_indent_mm: template.first_line_indent_mm ?? 0,
    body_alignment: template.body_alignment ?? 'justify',
    body_bold: template.body_bold ?? false,
    body_italic: template.body_italic ?? false,
    body_underline: template.body_underline ?? false,
  };
}

export type BlockKind = Placement | 'title' | 'body';

export interface BlockItem {
  field: RequisiteField;
  value: string;
  /** Prefix plus the value, or the «Заполнить» placeholder for a missing required one. */
  text: string;
}

export interface PageBlock {
  kind: BlockKind;
  items: BlockItem[];
}

/** Backends without the placement contract print every requisite as «Подпись: значение». */
export function placementOf(field: RequisiteField): Placement {
  return field.placement ?? 'labeled';
}

export function requisiteText(field: RequisiteField, value: string): string {
  return (field.prefix ?? '') + (value || `[Заполнить: ${field.label}]`);
}

export function arrangeBlocks(content: DocumentContent, docType: DocumentType): PageBlock[] {
  const fields = new Map(docType.fields.map(field => [field.id, field]));
  const blocks: PageBlock[] = [];
  for (const name of docType.blocks) {
    if (name === 'title' || name === 'body') {
      if (name === 'body' || docType.show_title !== false) blocks.push({ kind: name, items: [] });
      continue;
    }
    const field = fields.get(name);
    if (!field) continue;
    const value = (content.requisites[name] ?? '').trim();
    if (!value && !field.required) continue;
    const placement = placementOf(field);
    const last = blocks[blocks.length - 1];
    if (!last || last.kind !== placement) blocks.push({ kind: placement, items: [] });
    blocks[blocks.length - 1].items.push({ field, value, text: requisiteText(field, value) });
  }
  return blocks;
}

/** Gap above a block, in points — writer.space_before() of the generator. */
export function spaceBeforePt(
  kind: BlockKind, previous: BlockKind | null, template: ResolvedTemplate,
): number {
  if (previous === null || previous === 'title') return 0;
  return kind === 'signature' || kind === 'executor' ? template.fontSize * 2 : template.fontSize;
}

/** Blocks printed with single line spacing, as compact groups. */
export const COMPACT_BLOCKS = new Set<BlockKind>([
  'letterhead', 'addressee', 'registration', 'headline', 'signature', 'executor',
]);

export function isFilled(content: DocumentContent, field: RequisiteField): boolean {
  return Boolean((content.requisites[field.id] ?? '').trim());
}

/** Required requisites still waiting for a value — the same rule the backend applies. */
export function missingRequired(content: DocumentContent, docType: DocumentType): RequisiteField[] {
  return docType.fields.filter(field => field.required && !isFilled(content, field));
}

export function splitParagraphs(draft: string): string[] {
  return draft.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
}
