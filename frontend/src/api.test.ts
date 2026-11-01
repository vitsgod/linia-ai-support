import { test, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { ApiError, createTicket, listTickets, diagnoseProblem, checkOutageStatus, askOutageAssistant, prepareTicketDraft, listHistory } from './api.ts';

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });
const ticket = { id: 17, name: 'Анна', subject: 'Нет сети', description: 'Не подключается', status: 'Новая', created_at: '2026-10-31T09:00:00Z' };

test('POST sends the entered fields and returns the created ticket', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/tickets');
    assert.equal(options?.method, 'POST');
    assert.deepEqual(JSON.parse(options?.body as string), { name: 'Анна', subject: 'Нет сети', description: 'Не подключается' });
    return Response.json(ticket, { status: 201 });
  };
  assert.deepEqual(await createTicket({ name: 'Анна', subject: 'Нет сети', description: 'Не подключается' }), ticket);
});

test('422 exposes errors at their fields', async () => {
  globalThis.fetch = async () => Response.json({ detail: [{ field: 'description', message: 'Введите описание проблемы' }] }, { status: 422 });
  await assert.rejects(createTicket({ name: 'Анна', subject: 'Нет сети', description: '   ' }), (error: unknown) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.fields.description, 'Введите описание проблемы');
    return true;
  });
});

test('503 preserves the safe server message', async () => {
  globalThis.fetch = async () => Response.json({ detail: 'Не удалось загрузить заявки. Попробуйте позже.' }, { status: 503 });
  await assert.rejects(listTickets(), /Не удалось загрузить заявки/);
});

test('network and non-JSON gateway failures have a readable fallback', async () => {
  globalThis.fetch = async () => { throw new TypeError('fetch failed'); };
  await assert.rejects(listTickets(), /Не удалось связаться с сервером/);
  globalThis.fetch = async () => new Response('Bad gateway', { status: 502 });
  await assert.rejects(listTickets(), /Сервис временно недоступен/);
});

test('diagnostics sends only the description and accepts HTTP 200', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/diagnostics');
    assert.equal(options?.method, 'POST');
    assert.deepEqual(JSON.parse(options?.body as string), { description: 'Нет интернета' });
    return Response.json({ model: 'qwen3:4b', answer: 'Проверьте кабель.', mode: 'answer', sources: [{ id: 'a:01', title: 'Интернет', section: 'Проверки', url: '/api/knowledge/all-devices-offline.md', excerpt: 'Проверьте кабель.' }] });
  };
  assert.equal((await diagnoseProblem('Нет интернета')).sources[0].id, 'a:01');
});

test('diagnostics accepts a clarification without a generating model or sources', async () => {
  globalThis.fetch = async () => Response.json({ model: null, answer: 'Уточните проблему.', mode: 'clarify', sources: [] });
  assert.equal((await diagnoseProblem('Привет')).mode, 'clarify');
});

test('diagnostics rejects malformed sources and external links', async () => {
  for (const url of ['javascript:alert(1)', 'https://example.com', '/api/knowledge/../.env']) {
    globalThis.fetch = async () => Response.json({ model: 'qwen3:4b', answer: 'Ответ', mode: 'answer', sources: [{ id: 'a', title: 'A', section: 'B', excerpt: 'C', url }] });
    await assert.rejects(diagnoseProblem('Нет сети'), /некоррект/);
  }
});

test('diagnostics network failure has its own message', async () => {
  globalThis.fetch = async () => { throw new TypeError('offline'); };
  await assert.rejects(diagnoseProblem('Нет интернета'), error => {
    assert.ok(error instanceof ApiError);
    assert.match(error.message, /диагностик/);
    assert.doesNotMatch(error.message, /заяв/);
    return true;
  });
});

const outage = { area_code: 'demo-north', area_name: 'Учебный Северный', status: 'active',
  incident: { id: 'DEMO-OUTAGE-001', title: 'Учебная авария' }, message: 'Учебный статус',
  checked_at: '2026-11-01T12:00:00Z', demo: true };

test('outage tool uses GET without a body and returns a demo result', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/outages/demo-north');
    assert.equal(options?.method, 'GET');
    assert.equal(options?.body, undefined);
    return Response.json(outage);
  };
  assert.deepEqual(await checkOutageStatus('demo-north'), outage);
});

test('outage client rejects wrong area, real-world data and inconsistent incidents', async () => {
  for (const changes of [{ area_code: 'demo-center' }, { demo: false }, { incident: null },
    { status: 'unknown' }, { checked_at: 'not-a-date' }, { message: '' }]) {
    globalThis.fetch = async () => Response.json({ ...outage, ...changes });
    await assert.rejects(checkOutageStatus('demo-north'), /некоррект/);
  }
});

test('outage errors have their own message and never claim a clear status', async () => {
  globalThis.fetch = async () => { throw new TypeError('offline'); };
  await assert.rejects(checkOutageStatus('demo-north'), error => {
    assert.ok(error instanceof ApiError);
    assert.match(error.message, /статус аварий/);
    assert.doesNotMatch(error.message, /заявк/);
    return true;
  });
  globalThis.fetch = async () => Response.json({ detail: 'Учебный статус временно недоступен.' }, { status: 503 });
  await assert.rejects(checkOutageStatus('demo-north'), /недоступен/);
});

test('assistant sends question and selected area, accepts only an actual tool result', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/assistant/outage');
    assert.equal(options?.method, 'POST');
    assert.deepEqual(JSON.parse(options?.body as string), { question: 'Проверь аварии', area_code: 'demo-north' });
    return Response.json({ mode: 'tool_result', answer: 'Учебный статус', model: 'qwen3:4b', tool_name: 'check_outage_status', tool_result: outage });
  };
  assert.equal((await askOutageAssistant('Проверь аварии', 'demo-north')).tool_result?.status, 'active');
});

test('assistant accepts clarification, rejects invented tool names and area mismatch', async () => {
  globalThis.fetch = async () => Response.json({ mode: 'clarify', answer: 'Выберите район', model: null, tool_name: null, tool_result: null });
  assert.equal((await askOutageAssistant('Проверь', null)).mode, 'clarify');
  for (const changes of [{ tool_name: 'create_ticket' }, { tool_result: null },
    { tool_result: { ...outage, area_code: 'demo-center' } }, { mode: 'clarify' }]) {
    globalThis.fetch = async () => Response.json({ mode: 'tool_result', answer: 'Статус', model: 'qwen3:4b', tool_name: 'check_outage_status', tool_result: outage, ...changes });
    await assert.rejects(askOutageAssistant('Проверь', 'demo-north'), /некоррект/);
  }
});

test('assistant network error does not suggest a ticket was sent', async () => {
  globalThis.fetch = async () => { throw new TypeError('offline'); };
  await assert.rejects(askOutageAssistant('Проверь', 'demo-north'), error => {
    assert.ok(error instanceof ApiError);
    assert.match(error.message, /помощник/);
    assert.doesNotMatch(error.message, /заявк/);
    return true;
  });
});

test('draft sends only description and accepts an unsaved preview', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/assistant/ticket-draft');
    assert.deepEqual(JSON.parse(options?.body as string), { description: 'На ноутбуке нет сети' });
    return Response.json({ mode: 'draft', draft: { subject: 'Нет сети', description: 'На ноутбуке нет сети' }, model: 'qwen3:4b', saved: false, message: 'Проверьте' });
  };
  assert.equal((await prepareTicketDraft('На ноутбуке нет сети')).saved, false);
});

test('draft rejects saved results, unexpected fields and incomplete previews', async () => {
  for (const changes of [{ saved: true }, { draft: null }, { mode: 'clarify' },
    { draft: { subject: 'x', description: 'y', name: 'Придумано' } }, { draft: { subject: '', description: 'y' } }]) {
    globalThis.fetch = async () => Response.json({ mode: 'draft', draft: { subject: 'Тема', description: 'Описание' }, model: 'qwen3:4b', saved: false, message: 'Проверьте', ...changes });
    await assert.rejects(prepareTicketDraft('Нет сети'), /некоррект/);
  }
});

test('draft clarification can be produced without calling a model', async () => {
  globalThis.fetch = async () => Response.json({ mode: 'clarify', draft: null, model: null, saved: false, message: 'Уточните симптомы' });
  assert.equal((await prepareTicketDraft('ничего не работает')).mode, 'clarify');
});

const historyRun = { id: 'a0000000-0000-4000-8000-000000000001', kind: 'outage', status: 'completed',
  request_data: { area_code: 'demo-north' }, response_data: { status: 'active' }, error_message: null,
  started_at: '2026-11-01T12:00:00Z', finished_at: '2026-11-01T12:00:01Z' };

test('history uses bounded GET and accepts persisted records', async () => {
  globalThis.fetch = async (url, options) => {
    assert.equal(url, '/api/history?limit=20'); assert.equal(options?.method, 'GET');
    return Response.json([historyRun]);
  };
  assert.deepEqual(await listHistory(), [historyRun]);
});

test('history rejects invalid states rather than showing false success', async () => {
  for (const changes of [{ id: 'bad' }, { kind: 'execute-anything' }, { response_data: null },
    { status: 'started' }, { status: 'failed' }, { started_at: 'not-a-date' }]) {
    globalThis.fetch = async () => Response.json([{ ...historyRun, ...changes }]);
    await assert.rejects(listHistory(), /некоррект/);
  }
});

test('history network error refers to history, not tickets', async () => {
  globalThis.fetch = async () => { throw new TypeError('offline'); };
  await assert.rejects(listHistory(), /истори/);
});

test('history accepts incomplete and failed runs without inventing a response', async () => {
  globalThis.fetch = async () => Response.json([
    { ...historyRun, status: 'started', response_data: null, finished_at: null },
    { ...historyRun, status: 'failed', response_data: null, error_message: 'Модель недоступна.' },
  ]);
  const rows = await listHistory();
  assert.equal(rows[0].status, 'started'); assert.equal(rows[1].status, 'failed');
});
