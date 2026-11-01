import { useEffect, useRef, useState } from 'react';
import { ApiError, diagnoseProblem } from './api';
import type { DiagnosticResult } from './types';

export function Diagnostics({ description, disabled }: { description: string; disabled: boolean }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DiagnosticResult | null>(null);
  const [error, setError] = useState('');
  const pending = useRef(false);
  const activeRequest = useRef<AbortController | null>(null);

  useEffect(() => () => { activeRequest.current?.abort(); }, []);

  async function handleDiagnose() {
    if (pending.current || disabled) return;
    setError('');
    if (!description.trim()) {
      setError('Введите описание проблемы, чтобы получить рекомендации.');
      document.getElementById('description')?.focus();
      return;
    }
    const controller = new AbortController();
    activeRequest.current = controller;
    pending.current = true;
    setLoading(true);
    setResult(null);
    try {
      const answer = await diagnoseProblem(description, controller.signal);
      if (!controller.signal.aborted) setResult(answer);
    } catch (caught) {
      if (!controller.signal.aborted) {
        setError(caught instanceof ApiError ? caught.fields.description || caught.message : 'Не удалось получить рекомендации. Попробуйте ещё раз.');
      }
    } finally {
      pending.current = false;
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  return <section className="diagnostics" aria-labelledby="diagnostics-title" aria-busy={loading}>
    <div className="diagnostics-heading"><h3 id="diagnostics-title">Помощь с диагностикой</h3><span className="ai-label">ИИ</span></div>
    <p className="field-help">Получите рекомендации по описанию перед отправкой обращения.</p>
    <button type="button" className="diagnose-button" onClick={() => void handleDiagnose()} disabled={disabled || loading}>
      {loading ? 'Модель готовит ответ…' : 'Предложить диагностику'}
    </button>
    <div role="status" aria-live="polite">
      {loading && <p className="field-help">Ищем инструкции и готовим ответ. Первый запуск может занять до четырёх минут. Форму можно продолжать заполнять.</p>}
      {result && <div className="diagnostic-result">
        <p className="diagnostic-answer">{result.answer}</p>
        {result.mode === 'answer' && <>
          <p className="field-help">Ответ модели {result.model} по учебным инструкциям. Это не результат проверки линии.</p>
          <div className="diagnostic-sources">
            <h4>Источники ответа</h4>
            {result.sources.map(source => <details key={source.id}>
              <summary>{source.title} — {source.section}</summary>
              <p className="diagnostic-source-text">{source.excerpt}</p>
              <a href={source.url} target="_blank" rel="noreferrer">Открыть инструкцию</a>
            </details>)}
          </div>
        </>}
      </div>}
    </div>
    {error && <p className="message error-message diagnostic-error" role="alert">{error}</p>}
    <p className="field-help">Диагностика не создаёт заявку. Для отправки нажмите «Создать заявку».</p>
  </section>;
}
