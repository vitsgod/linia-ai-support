import { useEffect, useRef, useState } from 'react';
import { listHistory } from './api';
import type { HistoryRun } from './types';

const kinds: Record<HistoryRun['kind'], string> = {
  diagnostics: 'Диагностика', outage: 'Проверка аварий',
  outage_assistant: 'Проверка через помощника', ticket_draft: 'Черновик заявки',
};
const states = { started: 'Итог не записан', completed: 'Завершено', failed: 'Ошибка' };
const areaNames: Record<string, string> = {
  'demo-north': 'Учебный Северный', 'demo-center': 'Учебный Центральный', 'demo-south': 'Учебный Южный',
};
const text = (value: unknown): string => typeof value === 'string' ? value : '';
function object(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}
function question(run: HistoryRun): string {
  return text(run.request_data.question) || text(run.request_data.description)
    || areaNames[text(run.request_data.area_code)] || 'Проверка выбранного района';
}
function answer(data: Record<string, unknown>): string {
  const draft = object(data.draft);
  if (draft) return `Тема: ${text(draft.subject)}\n${text(draft.description)}`;
  return text(data.answer) || text(data.message) || 'Ответ получен.';
}

export function HistoryPanel() {
  const [rows, setRows] = useState<HistoryRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latestRequest = useRef(0);
  async function refresh() {
    const version = ++latestRequest.current;
    setLoading(true); setError('');
    try {
      const result = await listHistory();
      if (version === latestRequest.current) setRows(result);
    } catch (caught) {
      if (version === latestRequest.current) setError(caught instanceof Error ? caught.message : 'Не удалось загрузить историю.');
    } finally {
      if (version === latestRequest.current) setLoading(false);
    }
  }
  useEffect(() => {
    void refresh();
    const onUpdate = () => { void refresh(); };
    window.addEventListener('assistant-history-updated', onUpdate);
    return () => { latestRequest.current++; window.removeEventListener('assistant-history-updated', onUpdate); };
  }, []);

  return <section className="history-section" id="assistant-history" aria-labelledby="history-title" aria-busy={loading}>
    <div className="history-heading"><h2 id="history-title">История помощника</h2>
      <button type="button" className="history-refresh" onClick={() => void refresh()} disabled={loading}>Обновить историю</button></div>
    <p className="field-help">Последние 20 запросов общей учебной истории. Записи сохраняются после обновления страницы. Каждый запрос пока обрабатывается отдельно.</p>
    {loading && <p role="status" className="field-help">Загружаем историю…</p>}
    {error && <p role="alert" className="message error-message">{error}{rows.length > 0 && ' Показаны ранее загруженные записи.'}</p>}
    {!loading && !error && rows.length === 0 && <p className="history-empty">История пока пуста. Выполните диагностику, проверку аварий или подготовку черновика.</p>}
    <div className="history-list">{rows.map(run => {
      const data = run.response_data;
      const tool = data && (run.kind === 'outage' ? data : data.tool_name === 'check_outage_status' ? object(data.tool_result) : null);
      return <details className="history-run" data-run-id={run.id} key={run.id}>
        <summary><span className="history-summary-head"><strong>{kinds[run.kind]}</strong>
          <span className={`history-state history-state-${run.status}`}>{states[run.status]}</span>
          <time dateTime={run.started_at}>{new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(run.started_at))}</time></span>
          <span className="history-question">{question(run).slice(0, 120)}{question(run).length > 120 ? '…' : ''}</span></summary>
        <dl><dt>Запрос</dt><dd>{question(run)}</dd>
          {data && <><dt>Ответ</dt><dd>{answer(data)}</dd></>}
          {tool && <><dt>Выполнено</dt><dd>Проверка учебных аварий — {text(tool.area_name)}
            {object(tool.incident) && <p>{text(object(tool.incident)?.title)}</p>}</dd></>}
          {run.error_message && <><dt>Ошибка</dt><dd>{run.error_message}</dd></>}
          {run.status === 'started' && <dd>Запрос принят, но итог ещё не записан. Выполнение могло прерваться.</dd>}
        </dl>
      </details>;
    })}</div>
  </section>;
}
