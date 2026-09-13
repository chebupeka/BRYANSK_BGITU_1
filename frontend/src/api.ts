import type {
  ApiFailure, Catalog, DocumentContent, DocumentFormatting, ErrorIssue, ProcessResult, ServiceStatus,
  Template,
} from './types';

const DEFAULT_TIMEOUT_MS = 30_000;
// Preparation waits for the model: one request plus the single allowed retry on the backend.
export const PROCESS_TIMEOUT_MS = 240_000;
const DOWNLOAD_TIMEOUT_MS = 60_000;

// error.code from the backend → what the person in front of the screen can do about it.
const HINTS: Record<string, string> = {
  validation_error: 'Проверьте выделенные поля и повторите.',
  unknown_doc_type: 'Каталог изменился. Обновите страницу, чтобы получить актуальные типы.',
  unknown_requisites: 'Каталог изменился. Обновите страницу, чтобы получить актуальные реквизиты.',
  unknown_template: 'Каталог изменился. Обновите страницу и выберите оформление заново.',
  processor_unavailable: 'Обработчик выключен или недоступен. Текст остался в форме — повторите позже.',
  llm_not_configured: 'На сервере не выбрана модель. Задайте LLM_MODEL и перезапустите backend.',
  processor_busy: 'Все слоты обработки заняты. Повторите через минуту.',
  llm_connection_error: 'Нет связи с сервером модели. Проверьте адрес, сеть и VPN.',
  llm_auth_error: 'Модель отклонила ключ доступа. Проверьте настройки backend.',
  llm_rate_limited: 'Провайдер модели ограничил частоту запросов. Повторите позже.',
  llm_upstream_error: 'Сервер модели ответил ошибкой. Повторите после восстановления.',
  llm_request_rejected: 'Сервер модели отклонил запрос. Проверьте совместимость API.',
  llm_invalid_output: 'Модель вернула ответ не по схеме. Повторите или переключите обработчик.',
  processor_invalid_output: 'Обработчик вернул чужой тип документа. Сообщите владельцу backend.',
  llm_timeout: 'Модель не ответила вовремя. Повторите или сократите черновик.',
  internal_error: 'Ошибка на сервере. Передайте номер запроса владельцу backend.',
  http_error: 'Такого маршрута нет. Проверьте, что запущен backend нужной версии.',
  network_error: 'Сервис не отвечает. Черновик и реквизиты остались в форме.',
  timeout: 'Ответ не пришёл вовремя. Черновик остался в форме — можно повторить.',
};

export class ApiError extends Error implements ApiFailure {
  readonly hint: string;
  readonly retryable: boolean;
  readonly code: string;
  readonly requestId: string;
  readonly issues: ErrorIssue[];

  constructor(failure: ApiFailure) {
    super(failure.message);
    this.name = 'ApiError';
    this.hint = failure.hint;
    this.retryable = failure.retryable;
    this.code = failure.code;
    this.requestId = failure.requestId;
    this.issues = failure.issues;
  }
}

export function asFailure(error: unknown): ApiFailure {
  if (error instanceof ApiError) return error;
  return {
    message: error instanceof Error && error.message ? error.message : 'Непредвиденная ошибка.',
    hint: '', retryable: true, code: 'unknown', requestId: '', issues: [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function newRequestId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `ui-${Date.now().toString(36)}`;
  }
}

/** Turns any failed response into the one shape the interface renders. */
async function failure(response: Response, requestId: string): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  const detail = isRecord(body) && typeof body.detail === 'string' ? body.detail : '';
  const info = isRecord(body) && isRecord(body.error) ? body.error : null;
  const code = typeof info?.code === 'string' ? info.code : `http_${response.status}`;
  const message = detail
    || (typeof info?.message === 'string' ? info.message : '')
    || 'Не удалось обработать запрос. Проверьте текст и реквизиты.';
  const issues = Array.isArray(info?.details)
    ? info.details.filter(isRecord).map(issue => ({
      field: String(issue.field ?? ''),
      message: String(issue.message ?? ''),
      type: String(issue.type ?? ''),
    }))
    : [];
  const fallbackId = typeof info?.request_id === 'string' ? info.request_id : requestId;
  return new ApiError({
    message,
    hint: HINTS[code] ?? (response.status >= 500 ? HINTS.internal_error : ''),
    // Older backends have no error.retryable; 5xx is the retryable half of what they return.
    retryable: typeof info?.retryable === 'boolean' ? info.retryable : response.status >= 500,
    code,
    requestId: response.headers.get('X-Request-ID') ?? fallbackId,
    issues,
  });
}

interface Options {
  body?: unknown;
  timeoutMs?: number;
  /** Routes that only exist on some branches: 404/405 answers null instead of throwing. */
  optional?: boolean;
}

async function request(path: string, options: Options = {}): Promise<Response | null> {
  const requestId = newRequestId();
  const hasBody = options.body !== undefined;
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: hasBody ? 'POST' : 'GET',
      headers: hasBody
        ? { 'Content-Type': 'application/json', 'X-Request-ID': requestId }
        : { 'X-Request-ID': requestId },
      body: hasBody ? JSON.stringify(options.body) : undefined,
      signal: AbortSignal.timeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS),
    });
  } catch (error) {
    const timedOut = error instanceof DOMException && error.name === 'TimeoutError';
    throw new ApiError({
      message: timedOut
        ? 'Сервис не ответил вовремя.'
        : 'Сервис не отвечает. Проверьте подключение и повторите попытку.',
      hint: timedOut ? HINTS.timeout : HINTS.network_error,
      retryable: true,
      code: timedOut ? 'timeout' : 'network_error',
      requestId,
      issues: [],
    });
  }
  if (options.optional && (response.status === 404 || response.status === 405)) return null;
  if (!response.ok) throw await failure(response, requestId);
  return response;
}

export async function getCatalog(): Promise<Catalog> {
  const response = await request('/catalog');
  return response!.json();
}

/** /api/ready exists on feat/role-1-backend-integration; every backend has /api/health. */
export async function getStatus(): Promise<ServiceStatus | null> {
  try {
    const ready = await request('/ready', { optional: true, timeoutMs: 8_000 });
    if (ready) return ready.json();
    const health = await request('/health', { optional: true, timeoutMs: 8_000 });
    return health ? health.json() : null;
  } catch {
    // The status badge is a nicety; the catalog request is what reports a dead backend.
    return null;
  }
}

/**
 * feature/ollama-text-processor: values the person already wrote in their own draft.
 * `null` means this backend has no such route — the form simply stays empty.
 */
export async function suggestRequisites(
  draft: string, docType: string,
): Promise<Record<string, string> | null> {
  const response = await request('/requisites/suggest', {
    body: { draft, doc_type: docType }, optional: true, timeoutMs: 60_000,
  });
  if (!response) return null;
  const data: unknown = await response.json();
  const requisites = isRecord(data) ? data.requisites : null;
  if (!isRecord(requisites)) return {};
  return Object.fromEntries(Object.entries(requisites)
    .filter((entry): entry is [string, string] => typeof entry[1] === 'string'));
}

export interface ProcessOutcome {
  result: ProcessResult;
  /** X-Cache from feat/role-1-backend-integration: HIT means the answer was already prepared. */
  cache: string;
  elapsedMs: number;
}

export async function processDocument(
  draft: string, docType: string, requisites: Record<string, string>,
): Promise<ProcessOutcome> {
  const started = performance.now();
  const response = await request('/process', {
    body: { draft, doc_type: docType, requisites }, timeoutMs: PROCESS_TIMEOUT_MS,
  });
  return {
    result: await response!.json(),
    cache: response!.headers.get('X-Cache') ?? '',
    elapsedMs: performance.now() - started,
  };
}

function filenameFrom(response: Response, fallback: string): string {
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(disposition);
  return match ? decodeURIComponent(match[1]) : fallback;
}

export async function downloadDocument(
  document: DocumentContent, template: Template, formatting?: DocumentFormatting,
): Promise<string> {
  const custom = template.id.startsWith('custom_') ? template : undefined;
  const response = await request('/documents/download', {
    body: {
      document, template_id: template.id, custom_template: custom, formatting,
    },
    timeoutMs: DOWNLOAD_TIMEOUT_MS,
  });
  const blob = await response!.blob();
  const name = filenameFrom(response!, `${document.doc_type}-${template.id}.docx`);
  const url = URL.createObjectURL(blob);
  const link = window.document.createElement('a');
  link.href = url;
  link.download = name;
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  // Give the browser time to consume the blob before releasing it.
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return name;
}
