import type { Ticket } from './types';

const dateFormat = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', year: 'numeric' });

export function TicketList({ tickets, loading, error, onRefresh }: {
  tickets: Ticket[]; loading: boolean; error: string; onRefresh: () => void;
}) {
  return <section className="list-section" aria-labelledby="list-title" aria-busy={loading}>
    <div className="list-header">
      <div className="section-heading"><h2 id="list-title">Обращения {(tickets.length > 0 || (!loading && !error)) && <span className="count">{tickets.length}</span>}</h2></div>
      <button className="refresh-button" onClick={onRefresh} disabled={loading}>{loading ? 'Загрузка…' : 'Обновить'}</button>
    </div>
    <p className="section-intro">Новые заявки — в начале списка.</p>
    {error && <div className="message error-message" role="alert">{error} Нажмите «Обновить», чтобы попробовать снова.</div>}
    {loading && tickets.length === 0 && <p className="empty-state" role="status">Загружаем обращения…</p>}
    {!loading && !error && tickets.length === 0 && <div className="empty-state"><h3>Пока ни одного обращения</h3><p>Создайте первую заявку через форму — она появится здесь.</p></div>}
    <div className="ticket-list">{tickets.map(ticket => <article className="ticket" key={ticket.id}>
      <div className="ticket-meta"><span className="ticket-id">№{ticket.id}</span><span className="status"><span aria-hidden="true" />{ticket.status}</span></div>
      <h3>{ticket.subject}</h3>
      {ticket.description.length <= 200 ? <p className="ticket-description">{ticket.description}</p> : <details><summary>Описание проблемы</summary><p className="ticket-description">{ticket.description}</p></details>}
      <div className="ticket-footer"><span>{ticket.name}</span><time dateTime={ticket.created_at}>{dateFormat.format(new Date(ticket.created_at))}</time></div>
    </article>)}</div>
  </section>;
}
