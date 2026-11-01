"""Draft generation only. No database writes or write tools are available here."""
from backend import ai, rag


def prepare(description: str) -> dict:
    if rag.needs_subject(description):
        return {'mode': 'clarify', 'draft': None, 'model': None, 'saved': False,
                'message': 'Опишите, что именно не работает, на каких устройствах и что вы уже проверили.'}
    if not rag.pipeline_slot.acquire(blocking=False):
        raise ai.AiServiceError(503, 'Модель уже обрабатывает запрос. Попробуйте чуть позже.')
    try:
        decision = ai.prepare_ticket_draft(description)
        return {
            **decision.model_dump(), 'model': ai.MODEL, 'saved': False,
            'message': ('Черновик подготовлен. Проверьте факты и текст перед использованием в форме.'
                        if decision.mode == 'draft' else 'Опишите проблему с подключением и выполненные проверки, чтобы подготовить черновик.'),
        }
    finally:
        rag.pipeline_slot.release()
