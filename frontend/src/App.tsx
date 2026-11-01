import { useEffect, useRef, useState } from 'react';
import { listTickets } from './api';
import { TicketForm } from './TicketForm';
import { TicketList } from './TicketList';
import { HistoryPanel } from './HistoryPanel';
import type { Ticket } from './types';

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latestRequest = useRef(0);

  async function refreshTickets() {
    const request = ++latestRequest.current;
    setLoading(true);
    setError('');
    try {
      const data = await listTickets();
      if (request === latestRequest.current) setTickets(data);
    } catch (caught) {
      if (request === latestRequest.current) setError(caught instanceof Error ? caught.message : 'Не удалось загрузить обращения.');
    } finally {
      if (request === latestRequest.current) setLoading(false);
    }
  }

  useEffect(() => {
    void refreshTickets();
    return () => { latestRequest.current++; };
  }, []);

  function handleCreated(ticket: Ticket) {
    latestRequest.current++;
    // A stale GET must not overwrite a ticket confirmed by POST.
    setTickets(previous => [ticket, ...previous.filter(item => item.id !== ticket.id)]);
    // Recover older rows if the first GET was still pending. Failure keeps the
    // confirmed ticket and shows a separate list error, without failing POST.
    void refreshTickets();
  }

  return <div className="app-frame">
    <a className="skip-link" href="#main">Перейти к обращениям</a>
    <header className="app-header">
      <a className="brand" href="/" aria-label="Линия — поддержка"><svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M4 22h6l5-12 5 12h8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/><circle cx="4" cy="22" r="2" fill="currentColor"/><circle cx="28" cy="22" r="2" fill="currentColor"/></svg><span>линия<span className="brand-divider">/</span><span className="brand-subtitle">поддержка</span></span></a>
      <a className="history-link" href="#assistant-history">История</a><span className="workspace-label">Учебное пространство</span>
    </header>
    <main className="work-sheet" id="main">
      <div className="page-heading"><div><h1>Поддержка подключения</h1><p>Создайте обращение и следите за ним в общем списке.</p></div><span className="local-label">Локальная версия</span></div>
      <div className="workspace"><TicketForm onCreated={handleCreated}/><TicketList tickets={tickets} loading={loading} error={error} onRefresh={() => void refreshTickets()}/></div>
      <HistoryPanel />
      <footer className="app-footer"><span>Линия · Сервис обращений</span><span>Данные сохраняются после перезагрузки страницы</span></footer>
    </main>
  </div>;
}
