import type { DraftState, ThemeName } from './types';

const DRAFT_KEY = 'document-three-steps:draft:v1';
const THEME_KEY = 'document-three-steps:theme';

export const EMPTY_DRAFT: DraftState = {
  draft: '', docType: 'service_memo', templateId: 'classic', requisitesByType: {},
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
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
