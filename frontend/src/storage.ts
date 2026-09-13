import type { DraftState, Template, ThemeName } from './types';

const DRAFT_KEY = 'document-three-steps:draft:v1';
const THEME_KEY = 'document-three-steps:theme';
const CUSTOM_TEMPLATES_KEY = 'document-three-steps:custom-templates:v1';
const CUSTOM_TEMPLATE_LIMIT = 12;

export const EMPTY_DRAFT: DraftState = {
  draft: '', docType: 'service_memo', templateId: 'classic', requisitesByType: {},
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function isNumberIn(value: unknown, minimum: number, maximum: number): value is number {
  return isFiniteNumber(value) && value >= minimum && value <= maximum;
}

function isAlignment(value: unknown): boolean {
  return value === 'left' || value === 'center' || value === 'right' || value === 'justify';
}

function isCustomTemplate(value: unknown): value is Template {
  if (!isRecord(value) || typeof value.id !== 'string' || !value.id.startsWith('custom_')
    || typeof value.name !== 'string' || !value.name.trim() || value.name.length > 80
    || typeof value.description !== 'string' || value.description.length > 240
    || typeof value.font !== 'string' || !value.font.trim() || value.font.length > 80
    || !isNumberIn(value.font_size, 10, 16) || !isRecord(value.margins_mm)) return false;
  const margins = value.margins_mm;
  return ['top', 'right', 'bottom', 'left'].every(side => isNumberIn(margins[side], 5, 50))
    && isNumberIn(value.line_spacing, 1, 2)
    && isNumberIn(value.paragraph_space_after_pt, 0, 24)
    && isNumberIn(value.first_line_indent_mm, 0, 20)
    && isAlignment(value.title_alignment)
    && isAlignment(value.recipient_alignment)
    && isAlignment(value.body_alignment)
    && isAlignment(value.signature_alignment)
    && (value.recipient_layout === 'block' || value.recipient_layout === 'table')
    && (value.header === 'none' || value.header === 'organization')
    && (value.footer === 'none' || value.footer === 'page_number' || value.footer === 'title_and_date')
    && isNumberIn(value.header_footer_font_size, 8, 14)
    && isAlignment(value.letterhead_alignment)
    && isAlignment(value.headline_alignment)
    && typeof value.headline_bold === 'boolean'
    && isNumberIn(value.addressee_width_mm, 50, 120)
    && isNumberIn(value.small_font_size, 8, 14);
}

export function loadDraft(): DraftState {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(DRAFT_KEY) ?? 'null');
    if (!isRecord(value) || typeof value.draft !== 'string' || value.draft.length > 20_000
      || typeof value.docType !== 'string' || typeof value.templateId !== 'string'
      || !isRecord(value.requisitesByType)) return { ...EMPTY_DRAFT };
    const requisitesByType: DraftState['requisitesByType'] = {};
    for (const [type, fields] of Object.entries(value.requisitesByType)) {
      if (!isRecord(fields)) continue;
      requisitesByType[type] = Object.fromEntries(Object.entries(fields)
        .filter((entry): entry is [string, string] => typeof entry[1] === 'string' && entry[1].length <= 500));
    }
    return { draft: value.draft, docType: value.docType, templateId: value.templateId, requisitesByType };
  } catch {
    return { ...EMPTY_DRAFT };
  }
}

export function saveDraft(state: DraftState): boolean {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(DRAFT_KEY);
  } catch {
    // Nothing to clean up when the browser refused to store anything.
  }
}

export function loadTheme(): ThemeName {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch {
    // Private mode: fall through to the default.
  }
  // The shell is designed dark; the light one is a deliberate choice, not a system guess.
  return 'dark';
}

export function saveTheme(theme: ThemeName): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // The theme simply resets on the next visit.
  }
}

export function loadCustomTemplates(): Template[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(CUSTOM_TEMPLATES_KEY) ?? '[]');
    if (!Array.isArray(value)) return [];
    return value.filter(isCustomTemplate).slice(0, CUSTOM_TEMPLATE_LIMIT);
  } catch {
    return [];
  }
}

export function saveCustomTemplates(templates: Template[]): boolean {
  try {
    localStorage.setItem(CUSTOM_TEMPLATES_KEY, JSON.stringify(
      templates.filter(isCustomTemplate).slice(-CUSTOM_TEMPLATE_LIMIT),
    ));
    return true;
  } catch {
    return false;
  }
}
