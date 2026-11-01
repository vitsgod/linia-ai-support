"""Durable request/result journal. No prompts or model reasoning are collected."""
from uuid import uuid4
import psycopg
from psycopg.types.json import Jsonb
from pydantic import ValidationError
from backend.database import get_connection
from backend import ai, outages


class HistoryUnavailableError(RuntimeError):
    pass


def _start(kind: str, inputs: dict):
    run_id = uuid4()
    try:
        with get_connection() as conn:
            conn.execute('INSERT INTO assistant_runs (id,kind,status,request_data) VALUES (%s,%s,\'started\',%s)',
                         (run_id, kind, Jsonb(inputs)))
    except psycopg.Error:
        raise HistoryUnavailableError('История помощника недоступна. Попробуйте позже.') from None
    return run_id


def _finish(run_id, status: str, response: dict | None, error: str | None):
    try:
        with get_connection() as conn:
            row = conn.execute('''UPDATE assistant_runs
                SET status=%s,response_data=%s,error_message=%s,finished_at=clock_timestamp()
                WHERE id=%s AND status='started' RETURNING id''',
                (status, Jsonb(response) if response is not None else None, error, run_id)).fetchone()
            if row is None:
                raise HistoryUnavailableError('Не удалось подтвердить сохранение истории.')
    except psycopg.Error:
        raise HistoryUnavailableError('Не удалось подтвердить сохранение истории. Попробуйте позже.') from None


def record(kind: str, inputs: dict, operation, response_schema) -> dict:
    run_id = _start(kind, inputs)
    try:
        raw = operation()
        try:
            response = response_schema.model_validate(raw).model_dump(mode='json')
        except ValidationError:
            raise ai.AiServiceError(502, 'Получен некорректный результат помощника. Попробуйте позже.') from None
    except Exception as exc:
        public_error = str(exc) if isinstance(exc, (ai.AiServiceError, outages.OutageUnavailableError)) else 'Внутренняя ошибка обработки запроса.'
        try:
            _finish(run_id, 'failed', None, public_error)
        except HistoryUnavailableError:
            pass  # Keep the original service error; the persisted row remains unfinished.
        raise
    _finish(run_id, 'completed', response, None)
    return response


def list_runs(limit: int = 20) -> list[dict]:
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError('History limit must be between 1 and 50')
    try:
        with get_connection() as conn:
            rows = conn.execute('''SELECT id,kind,status,request_data,response_data,error_message,started_at,finished_at
                FROM assistant_runs ORDER BY started_at DESC,id DESC LIMIT %s''', (limit,)).fetchall()
    except psycopg.Error:
        raise HistoryUnavailableError('Не удалось загрузить историю помощника. Попробуйте позже.') from None
    return rows
