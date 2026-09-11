import type { DraftState } from './types';

const KEY = 'document-three-steps:draft:v1';
export const EMPTY_DRAFT: DraftState = {
  draft: '', docType: 'service_memo', templateId: 'classic', requisitesByType: {},
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function loadDraft(): DraftState {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) ?? 'null');
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
    localStorage.setItem(KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}
