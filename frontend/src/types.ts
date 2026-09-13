// Контракт backend приходит из `contracts/api.ts`: экспорт кладёт его точную копию в
// `generated/api.ts`. Параллельный контракт руками здесь не ведём — только то, что
// принадлежит самому интерфейсу.

export type {
  Catalog, DocumentContent, DocumentFormatting, DocumentType, RequisiteField, Template,
  ProcessRequest, ProcessResult, DownloadRequest,
  SuggestRequest, RequisiteSuggestions,
  ErrorResponse, ErrorInfo, ErrorIssue,
} from './generated/api';

import type { ErrorIssue, ReadyResponse, RequisiteField, Template } from './generated/api';

/** Ответ `/api/ready`; старый backend отвечает только `/api/health` и без `checks`. */
export type ServiceStatus = Omit<ReadyResponse, 'status' | 'checks'> & {
  status: string;
  checks?: ReadyResponse['checks'];
};

// Выравнивание и расположение берём из того же контракта: отдельный список значений
// разошёлся бы с каталогом при первой же правке YAML.
export type Alignment = Template['title_alignment'];
export type Placement = RequisiteField['placement'];

/** Что слой API отдаёт интерфейсу на любую неудачу. */
export interface ApiFailure {
  message: string;
  hint: string;
  retryable: boolean;
  code: string;
  requestId: string;
  issues: ErrorIssue[];
}

export interface DraftState {
  draft: string;
  docType: string;
  templateId: string;
  requisitesByType: Record<string, Record<string, string>>;
}

export type ThemeName = 'dark' | 'light';
