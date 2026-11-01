import { useEffect, useRef, useState } from 'react';
import { ApiError, checkOutageStatus, askOutageAssistant } from './api';
import type { AreaCode, OutageResult, OutageAssistantResult } from './types';

const statusLabels = {
  active: 'Зарегистрирована учебная авария',
  clear: 'Учебных аварий не зарегистрировано',
  unknown: 'Сведений о районе нет',
};

function OutageStatus({ result }: { result: OutageResult }) {
  return <div className="outage-result">
    <strong>{statusLabels[result.status]}</strong>
    <p>{result.message}</p>
    {result.incident && <p>{result.incident.title} · {result.incident.id}</p>}
    <p className="field-help">{result.area_name} · Проверка учебного набора: {new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(result.checked_at))}</p>
  </div>;
}

function AssistantLookup({ areaCode, question, disabled }: { areaCode: AreaCode | ''; question: string; disabled: boolean }) {
  const [result, setResult] = useState<OutageAssistantResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);
  useEffect(() => () => activeRequest.current?.abort(), []);

  async function ask() {
    if (disabled || pending.current) return;
    setError('');
    if (!question.trim() || question.trim().length > 1000) {
      setError('Введите в описании проблемы вопрос длиной от 1 до 1000 символов.');
      return;
    }
    const controller = new AbortController();
    activeRequest.current = controller;
    pending.current = true;
    setLoading(true);
    setResult(null);
    try {
      const response = await askOutageAssistant(question, areaCode || null, controller.signal);
      if (!controller.signal.aborted) setResult(response);
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught instanceof ApiError ? caught.fields.question || caught.message : 'Не удалось получить ответ помощника.');
    } finally {
      pending.current = false;
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  return <div className="outage-assistant" aria-busy={loading}>
    <p className="field-help">Помощник использует вопрос из описания проблемы выше и выбранный район. Например: «Проверь, есть ли авария».</p>
    <button type="button" className="diagnose-button" onClick={() => void ask()} disabled={disabled || loading}>
      {loading ? 'Помощник выбирает действие…' : 'Проверить через помощника'}
    </button>
    <div role="status" aria-live="polite">
      {loading && <p className="field-help">Первый запуск модели может занять до двух минут.</p>}
      {result?.tool_result && <><p className="field-help">Помощник запросил проверку выбранного района.</p><OutageStatus result={result.tool_result} /></>}
      {result?.mode === 'clarify' && <p className="outage-clarification">{result.answer}</p>}
    </div>
    {error && <p role="alert" className="message error-message">{error}</p>}
  </div>;
}

function OutageLookup({ areaCode, disabled }: { areaCode: AreaCode | ''; disabled: boolean }) {
  const [result, setResult] = useState<OutageResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const activeRequest = useRef<AbortController | null>(null);
  const pending = useRef(false);
  useEffect(() => () => activeRequest.current?.abort(), []);

  async function check() {
    if (!areaCode || disabled || pending.current) return;
    const controller = new AbortController();
    activeRequest.current = controller;
    pending.current = true;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const response = await checkOutageStatus(areaCode, controller.signal);
      if (!controller.signal.aborted) setResult(response);
    } catch (caught) {
      if (!controller.signal.aborted) setError(caught instanceof ApiError ? caught.message : 'Не удалось проверить учебный статус аварий.');
    } finally {
      pending.current = false;
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  return <div aria-busy={loading}>
    <button type="button" className="diagnose-button" onClick={() => void check()} disabled={disabled || !areaCode || loading}>
      {loading ? 'Проверяем учебный статус…' : 'Проверить аварии'}
    </button>
    <div role="status" aria-live="polite">
      {result && <OutageStatus result={result} />}
    </div>
    {error && <p role="alert" className="message error-message">{error}</p>}
  </div>;
}

export function OutageCheck({ disabled, question }: { disabled: boolean; question: string }) {
  const [area, setArea] = useState<AreaCode | ''>('');
  return <section className="outage-check" aria-labelledby="outage-title">
    <h3 id="outage-title">Учебный статус аварий</h3>
    <p className="field-help" id="outage-help">Вымышленные районы и события. С реальным провайдером не связано.</p>
    <label htmlFor="outage-area">Учебный район</label>
    <select id="outage-area" value={area} disabled={disabled} aria-describedby="outage-help"
      onChange={event => setArea(event.target.value as AreaCode | '')}>
      <option value="">Выберите район</option>
      <option value="demo-north">Учебный Северный</option>
      <option value="demo-center">Учебный Центральный</option>
      <option value="demo-south">Учебный Южный</option>
    </select>
    <OutageLookup key={area} areaCode={area} disabled={disabled} />
    <AssistantLookup key={JSON.stringify([area, question])} areaCode={area} question={question} disabled={disabled} />
  </section>;
}
