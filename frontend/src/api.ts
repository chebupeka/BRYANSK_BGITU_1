import type { Catalog, DocumentContent, ProcessResult } from './types';

const TIMEOUT_MS = 30_000;
// Подготовка ждёт модель: LLM_TIMEOUT_SECONDS на запрос плюс один повтор.
const PROCESS_TIMEOUT_MS = 240_000;

async function request(path: string, payload?: unknown, timeoutMs = TIMEOUT_MS): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: payload === undefined ? 'GET' : 'POST',
      headers: payload === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: payload === undefined ? undefined : JSON.stringify(payload),
      signal: AbortSignal.timeout(timeoutMs),
    });
  } catch {
    throw new Error('Сервис не отвечает. Проверьте подключение и повторите попытку. Введённые данные остались в форме.');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(typeof data?.detail === 'string'
      ? data.detail
      : 'Не удалось обработать запрос. Проверьте текст и реквизиты и повторите попытку.');
  }
  return response;
}

export async function getCatalog(): Promise<Catalog> {
  return (await request('/catalog')).json();
}

export async function processDocument(
  draft: string, docType: string, requisites: Record<string, string>,
): Promise<ProcessResult> {
  const payload = { draft, doc_type: docType, requisites };
  return (await request('/process', payload, PROCESS_TIMEOUT_MS)).json();
}

export async function downloadDocument(document: DocumentContent, templateId: string): Promise<void> {
  const response = await request('/documents/download', { document, template_id: templateId });
  const url = URL.createObjectURL(await response.blob());
  const link = window.document.createElement('a');
  link.href = url;
  link.download = `${document.doc_type}-${templateId}.docx`;
  window.document.body.appendChild(link);
  link.click();
  link.remove();
  // Give the browser time to consume the blob before releasing it.
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
