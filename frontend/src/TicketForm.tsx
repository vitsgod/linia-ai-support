import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, createTicket } from './api';
import type { Ticket, TicketInput } from './types';
import { Diagnostics } from './Diagnostics';
import { OutageCheck } from './OutageCheck';
import { TicketDraftAssistant } from './TicketDraftAssistant';

const emptyForm: TicketInput = { name: '', subject: '', description: '' };
const fields = [
  { key: 'name', label: 'Ваше имя', max: 100, placeholder: 'Как к вам обращаться' },
  { key: 'subject', label: 'Тема обращения', max: 200, placeholder: 'Например, пропадает соединение' },
  { key: 'description', label: 'Описание проблемы', max: 5000, placeholder: 'Что произошло и что вы уже попробовали?' },
] as const;

export function TicketForm({ onCreated }: { onCreated: (ticket: Ticket) => void }) {
  const [form, setForm] = useState<TicketInput>(emptyForm);
  const [saving, setSaving] = useState(false);
  const [draftActive, setDraftActive] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [success, setSuccess] = useState('');
  const pending = useRef(false);
  const errorSummary = useRef<HTMLDivElement>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending.current || draftActive) return;
    pending.current = true;
    setSaving(true);
    setError(null);
    setSuccess('');
    try {
      const ticket = await createTicket(form);
      onCreated(ticket);
      setForm(emptyForm);
      setSuccess(`Заявка №${ticket.id} создана. Она появилась в списке обращений.`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught : new ApiError('Не удалось отправить обращение. Проверьте список перед повтором.'));
      requestAnimationFrame(() => errorSummary.current?.focus());
    } finally {
      pending.current = false;
      setSaving(false);
    }
  }

  return (
    <section className="form-section" aria-labelledby="form-title">
      <div className="section-heading"><h2 id="form-title">Новое обращение</h2></div>
      <p className="section-intro">Расскажите о проблеме с подключением — сохраним её в заявке.</p>
      <form onSubmit={handleSubmit} noValidate aria-busy={saving}>
        {error && <div className="message error-message" role="alert" tabIndex={-1} ref={errorSummary}>
          <strong>{error.message}</strong>
          {Object.entries(error.fields).length > 0 && <ul>{Object.entries(error.fields).map(([field, message]) =>
            <li key={field}><a href={`#${field}`}>{message}</a></li>)}</ul>}
        </div>}
        <fieldset disabled={saving}>
          {fields.map(({ key, label, max, placeholder }) => {
            const props = {
              id: key, name: key, value: form[key], maxLength: max, required: true, placeholder,
              'aria-invalid': Boolean(error?.fields[key]),
              'aria-describedby': error?.fields[key] ? `${key}-error` : key === 'description' ? 'description-help' : undefined,
              onChange: (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
                setForm(previous => ({ ...previous, [key]: event.target.value }));
                setSuccess('');
              },
            };
            return <div className="field" key={key}>
              <label htmlFor={key}>{label}<span aria-hidden="true"> *</span></label>
              {key === 'description' ? <textarea {...props} rows={5} /> : <input {...props} type="text" autoComplete={key === 'name' ? 'name' : 'off'} />}
              {error?.fields[key] && <p className="field-error" id={`${key}-error`}>{error.fields[key]}</p>}
              {key === 'description' && <p className="field-help" id="description-help">Все поля обязательны · до 5 000 символов</p>}
            </div>;
          })}
          <TicketDraftAssistant key={`draft:${form.description}`} description={form.description} disabled={saving}
            onReviewChange={setDraftActive} onApply={draft => {
              setForm(previous => ({ ...previous, ...draft }));
              setError(null);
              setSuccess('Черновик перенесён в форму. Проверьте поля и нажмите «Создать заявку» для сохранения.');
            }} />
          <OutageCheck disabled={saving} question={form.description} />
          {/* A changed description gets fresh diagnostic state and cancels the old request. */}
          <Diagnostics key={`diagnostics:${form.description}`} description={form.description} disabled={saving} />
          {draftActive && <p className="field-help">Завершите проверку черновика: используйте его в форме или отмените.</p>}
          <button className="primary-button" type="submit" disabled={draftActive}>{saving ? 'Сохраняем заявку…' : 'Создать заявку'}<span aria-hidden="true">↗</span></button>
        </fieldset>
        <div role="status" aria-live="polite">{success && <p className="message success-message">{success}</p>}</div>
      </form>
      <p className="privacy-note">Учебный сервис. Используйте вымышленные данные.</p>
    </section>
  );
}
