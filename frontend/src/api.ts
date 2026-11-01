import type { HistoryRun, AreaCode, OutageResult, OutageAssistantResult, DraftResult, DiagnosticResult, Ticket, TicketInput } from './types.ts';

export class ApiError extends Error {
  fields: Record<string, string>;

  constructor(message: string, fields: Record<string, string> = {}) {
    super(message);
    this.name = 'ApiError';
    this.fields = fields;
  }
}

async function request<T>(method: string, body?: TicketInput | { description: string } | { question: string; area_code: AreaCode | null }, path = '/api/tickets', signal?: AbortSignal): Promise<T> {
  const diagnostics = path === '/api/diagnostics';
  const outage = path.startsWith('/api/outages/');
  const assistant = path === '/api/assistant/outage';
  const drafting = path === '/api/assistant/ticket-draft';
  const history = path.startsWith('/api/history');
  const timeout = AbortSignal.timeout(diagnostics ? 250_000 : assistant || drafting ? 130_000 : 10_000);
  let response: Response;
  try {
    response = await fetch(path, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch {
    if (history) throw new ApiError('Не удалось загрузить историю помощника. Проверьте доступность сервера.');
    if (drafting) throw new ApiError('Не удалось подготовить черновик. Проверьте доступность сервера и модели.');
    if (diagnostics) throw new ApiError('Не удалось получить диагностику. Проверьте доступность сервера и попробуйте позже.');
    if (outage) throw new ApiError('Не удалось проверить учебный статус аварий. Проверьте доступность сервера.');
    if (assistant) throw new ApiError('Не удалось получить ответ помощника. Проверьте доступность сервера и модели.');
    throw new ApiError('Не удалось связаться с сервером. Проверьте список заявок перед повторной отправкой.');
  }
  const data = await response.json().catch(() => null);
  if ((diagnostics || outage || assistant || drafting) && typeof window !== 'undefined') {
    window.dispatchEvent(new Event('assistant-history-updated'));
  }
  if (!response.ok) {
    if (response.status === 422 && Array.isArray(data?.detail)) {
      const fields: Record<string, string> = {};
      for (const error of data.detail) {
        if (typeof error.field === 'string' && typeof error.message === 'string') {
          fields[error.field] = error.message;
        }
      }
      throw new ApiError(outage ? 'Выберите учебный район из списка.' : assistant ? 'Проверьте вопрос и выбранный район.' : 'Проверьте поля обращения.', fields);
    }
    throw new ApiError(typeof data?.detail === 'string' ? data.detail : 'Сервис временно недоступен. Попробуйте позже.');
  }
  if (data === null || response.status !== (method === 'POST' && path === '/api/tickets' ? 201 : 200)) {
    if (history) throw new ApiError('История вернула некорректный ответ. Попробуйте позже.');
    if (drafting) throw new ApiError('Помощник вернул некорректный черновик. Попробуйте позже.');
    if (assistant) throw new ApiError('Помощник вернул некорректный ответ. Попробуйте позже.');
    if (outage) throw new ApiError('Статус аварий вернул некорректный ответ. Попробуйте позже.');
    throw new ApiError(diagnostics ? 'Неожиданный ответ диагностики. Попробуйте позже.' : 'Неожиданный ответ сервера. Обновите список заявок перед повторной отправкой.');
  }
  return data as T;
}

export const listTickets = (): Promise<Ticket[]> => request('GET');
export const createTicket = (input: TicketInput): Promise<Ticket> => request('POST', input);

function isObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export async function listHistory(): Promise<HistoryRun[]> {
  const rows = await request<HistoryRun[]>('GET', undefined, '/api/history?limit=20');
  if (!Array.isArray(rows) || rows.some(row => !row
      || typeof row.id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(row.id)
      || !['diagnostics', 'outage', 'outage_assistant', 'ticket_draft'].includes(row.kind)
      || !['started', 'completed', 'failed'].includes(row.status)
      || !isObject(row.request_data)
      || typeof row.started_at !== 'string' || !Number.isFinite(Date.parse(row.started_at))
      || (row.status === 'started'
        ? row.finished_at !== null || row.response_data !== null || row.error_message !== null
        : typeof row.finished_at !== 'string' || !Number.isFinite(Date.parse(row.finished_at)))
      || (row.status === 'completed' && (!isObject(row.response_data) || row.error_message !== null))
      || (row.status === 'failed' && (row.response_data !== null || typeof row.error_message !== 'string' || !row.error_message.trim())))) {
    throw new ApiError('История вернула некорректные записи. Попробуйте позже.');
  }
  return rows;
}

export async function prepareTicketDraft(description: string, signal?: AbortSignal): Promise<DraftResult> {
  const result = await request<DraftResult>('POST', { description }, '/api/assistant/ticket-draft', signal);
  if (!result || result.saved !== false || !['draft', 'clarify'].includes(result.mode)
      || (result.model !== null && (typeof result.model !== 'string' || !result.model.trim()))
      || (result.mode === 'draft' && !result.model)
      || typeof result.message !== 'string' || !result.message.trim()
      || (result.mode === 'draft'
        ? !result.draft || Object.keys(result.draft).length !== 2
          || Object.keys(result.draft).some(key => !['subject', 'description'].includes(key))
          || typeof result.draft.subject !== 'string' || !result.draft.subject.trim() || result.draft.subject.length > 200
          || typeof result.draft.description !== 'string' || !result.draft.description.trim() || result.draft.description.length > 5000
        : result.draft !== null)) {
    throw new ApiError('Помощник вернул некорректный черновик. Попробуйте позже.');
  }
  return result;
}

export async function checkOutageStatus(areaCode: AreaCode, signal?: AbortSignal): Promise<OutageResult> {
  const result = await request<OutageResult>('GET', undefined, '/api/outages/' + encodeURIComponent(areaCode), signal);
  return validateOutageResult(result, areaCode);
}

function validateOutageResult(result: OutageResult | null, areaCode: AreaCode): OutageResult {
  if (!result || result.demo !== true || result.area_code !== areaCode
      || typeof result.area_name !== 'string' || !result.area_name.trim()
      || !['active', 'clear', 'unknown'].includes(result.status)
      || typeof result.message !== 'string' || !result.message.trim()
      || typeof result.checked_at !== 'string' || !Number.isFinite(Date.parse(result.checked_at))
      || (result.status === 'active'
        ? !result.incident || typeof result.incident.id !== 'string' || !result.incident.id.trim()
          || typeof result.incident.title !== 'string' || !result.incident.title.trim()
        : result.incident !== null)) {
    throw new ApiError('Статус аварий вернул некорректный ответ. Попробуйте позже.');
  }
  return result;
}

export async function askOutageAssistant(question: string, areaCode: AreaCode | null, signal?: AbortSignal): Promise<OutageAssistantResult> {
  const result = await request<OutageAssistantResult>('POST', { question, area_code: areaCode }, '/api/assistant/outage', signal);
  if (!result || !['tool_result', 'clarify'].includes(result.mode)
      || typeof result.answer !== 'string' || !result.answer.trim()
      || (result.model !== null && typeof result.model !== 'string')) {
    throw new ApiError('Помощник вернул некорректный ответ. Попробуйте позже.');
  }
  if (result.mode === 'tool_result') {
    if (!areaCode || !result.model || result.tool_name !== 'check_outage_status') {
      throw new ApiError('Помощник вернул некорректный результат инструмента.');
    }
    validateOutageResult(result.tool_result, areaCode);
  } else if (result.tool_name !== null || result.tool_result !== null) {
    throw new ApiError('Помощник вернул некорректное уточнение.');
  }
  return result;
}

export async function diagnoseProblem(description: string, signal?: AbortSignal): Promise<DiagnosticResult> {
  const result = await request<DiagnosticResult>('POST', { description }, '/api/diagnostics', signal);
  if (!result || (result.model !== null && typeof result.model !== 'string')
      || typeof result.answer !== 'string' || !result.answer.trim()
      || !['answer', 'clarify'].includes(result.mode)
      || !Array.isArray(result.sources) || result.sources.length > 3
      || (result.mode === 'answer' && (!result.model || result.sources.length === 0))
      || (result.mode === 'clarify' && result.sources.length !== 0)
      || result.sources.some(source => !source ||
        [source.id, source.title, source.section, source.excerpt].some(value => typeof value !== 'string' || !value.trim())
        || typeof source.url !== 'string' || !/^\/api\/knowledge\/[a-z0-9-]+\.md$/.test(source.url))) {
    throw new ApiError('Диагностика вернула пустой или некорректный ответ. Попробуйте позже.');
  }
  return result;
}
