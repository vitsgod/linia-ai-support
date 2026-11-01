import { useEffect, useRef, useState } from 'react';
import { ApiError, prepareTicketDraft } from './api';
import type { TicketDraft } from './types';

type Props = { description: string; disabled: boolean;
  onApply: (draft: TicketDraft) => void; onReviewChange: (active: boolean) => void };

export function TicketDraftAssistant({ description, disabled, onApply, onReviewChange }: Props) {
  const [draft, setDraft] = useState<TicketDraft | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const activeRequest = useRef<AbortController | null>(null);
  const pending = useRef(false);
  useEffect(() => () => { activeRequest.current?.abort(); onReviewChange(false); }, [onReviewChange]);

  function cancel() {
    activeRequest.current?.abort();
    activeRequest.current = null;
    pending.current = false;
    setLoading(false);
    setDraft(null);
    setMessage('');
    setError('');
    onReviewChange(false);
  }

  async function prepare() {
    if (disabled || pending.current) return;
    setError('');
    if (!description.trim()) {
      setError('Введите описание проблемы для подготовки черновика.');
      return;
    }
    const controller = new AbortController();
    activeRequest.current = controller;
    pending.current = true;
    setLoading(true);
    setDraft(null);
    setMessage('');
    onReviewChange(true);
    try {
      const response = await prepareTicketDraft(description, controller.signal);
      if (activeRequest.current !== controller || controller.signal.aborted) return;
      setDraft(response.draft);
      setMessage(response.message);
      if (response.mode === 'clarify') onReviewChange(false);
    } catch (caught) {
      if (activeRequest.current === controller && !controller.signal.aborted) {
        setError(caught instanceof ApiError ? caught.fields.description || caught.message : 'Не удалось подготовить черновик.');
        onReviewChange(false);
      }
    } finally {
      if (activeRequest.current === controller) { pending.current = false; setLoading(false); }
    }
  }

  function apply() {
    if (!draft || disabled) return;
    const clean = { subject: draft.subject.trim(), description: draft.description.trim() };
    if (!clean.subject || !clean.description) { setError('Заполните тему и описание черновика.'); return; }
    setDraft(null);
    setMessage('');
    setError('');
    onReviewChange(false);
    onApply(clean);
  }

  return <section className="draft-assistant" aria-labelledby="draft-title" aria-busy={loading}>
    <h3 id="draft-title">Черновик от помощника</h3>
    <p className="field-help">Помощник предложит тему и описание. Проверьте факты — заявка сохранится только после вашего нажатия «Создать заявку».</p>
    <button type="button" className="diagnose-button" onClick={() => void prepare()} disabled={disabled || loading}>
      {loading ? 'Готовим черновик…' : 'Подготовить черновик'}
    </button>
    <div role="status" aria-live="polite">{message && <p className="field-help">{message}</p>}</div>
    {draft && <div className="draft-preview">
      <h4>Предпросмотр — заявка ещё не создана</h4>
      <div className="field"><label htmlFor="draft-subject">Тема черновика</label>
        <input id="draft-subject" value={draft.subject} maxLength={200} onChange={event => setDraft({ ...draft, subject: event.target.value })} /></div>
      <div className="field"><label htmlFor="draft-description">Описание черновика</label>
        <textarea id="draft-description" rows={5} value={draft.description} maxLength={5000} onChange={event => setDraft({ ...draft, description: event.target.value })} /></div>
      <button type="button" className="diagnose-button" onClick={apply} disabled={disabled}>Использовать в форме</button>
    </div>}
    {(loading || draft) && <button type="button" className="draft-cancel" onClick={cancel} disabled={disabled}>Отменить черновик</button>}
    {error && <p className="message error-message" role="alert">{error}</p>}
  </section>;
}
