"""Retrieval and grounded generation; never creates a ticket."""
import math
import re
from pathlib import Path
from threading import BoundedSemaphore
from urllib.parse import quote

import psycopg
from backend import ai
from backend.answer_quality import repeated_checks, clarification_for_repeats
from backend.embeddings import EmbeddingError, embed_query
from backend.vector_store import get_search_connection, search_index

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / 'knowledge'
MIN_SIMILARITY = 0.55
pipeline_slot = BoundedSemaphore(1)
CLARIFICATION = ('В учебной базе недостаточно подходящих сведений для ответа. '
                 'Опишите проблему с интернетом: что не работает, на каких устройствах '
                 'и что вы уже проверили.')


def needs_subject(description: str) -> bool:
    # Deliberately narrow: known vague phrases, not a general classifier of meaning.
    return re.fullmatch(
        r'\W*(?:(?:у меня|помогите|пожалуйста)\W+)*'
        r'(?:ничего|вс[её]|что-то|это|оно)\W+'
        r'(?:не\W+работает|сломалось|пропало|не\W+открывается)\W*',
        description.casefold(),
    ) is not None


def retrieve_context(description: str) -> list[dict]:
    vector = embed_query(description)
    with get_search_connection() as conn:
        return search_index(conn, vector)


def diagnose(description: str) -> dict:
    if not pipeline_slot.acquire(blocking=False):
        raise ai.AiServiceError(503, 'Модель уже обрабатывает запрос. Попробуйте чуть позже.')
    try:
        if needs_subject(description):
            return {'model': None, 'mode': 'clarify', 'answer': CLARIFICATION, 'sources': []}
        try:
            rows = retrieve_context(description)
        except (EmbeddingError, psycopg.Error, RuntimeError):
            raise ai.AiServiceError(503, 'Не удалось выполнить поиск по инструкциям. Попробуйте позже.') from None
        context = [row for row in rows if math.isfinite(row['score']) and row['score'] >= MIN_SIMILARITY][:3]
        if not context:
            return {'model': None, 'mode': 'clarify', 'answer': CLARIFICATION, 'sources': []}
        allowed_sources = {path.name for path in KNOWLEDGE_DIR.glob('*.md')}
        if any(row['source'] not in allowed_sources for row in context):
            raise ai.AiServiceError(503, 'Источники инструкций изменились. Требуется обновить поисковую базу.')
        result = ai.diagnose(description, context=context)
        if result['mode'] == 'clarify':
            return {'model': result['model'], 'mode': 'clarify', 'answer': CLARIFICATION, 'sources': []}
        conflicts = repeated_checks(description, result['answer'])
        if conflicts:
            return {'model': result['model'], 'mode': 'clarify',
                    'answer': clarification_for_repeats(conflicts), 'sources': []}
        sources = [{
            'id': row['id'], 'title': row['title'], 'section': row['section'],
            'url': '/api/knowledge/' + quote(row['source']), 'excerpt': row['text'],
        } for row in context if row['id'] in result['source_ids']]
        return {'model': result['model'], 'mode': 'answer', 'answer': result['answer'], 'sources': sources}
    finally:
        pipeline_slot.release()
