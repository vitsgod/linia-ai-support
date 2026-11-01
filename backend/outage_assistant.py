"""One model selection, at most one allowlisted read-only tool execution."""
from pydantic import ValidationError
from backend import ai, outages, rag
from backend.schemas import OutageToolArguments


def run(question: str, area_code: str | None) -> dict:
    if area_code is None:
        return {'mode': 'clarify', 'answer': 'Выберите учебный район для проверки аварий.',
                'model': None, 'tool_name': None, 'tool_result': None}
    if not rag.pipeline_slot.acquire(blocking=False):
        raise ai.AiServiceError(503, 'Модель уже обрабатывает запрос. Попробуйте чуть позже.')
    try:
        calls = ai.select_outage_tool(question, area_code)
        if calls is None or calls == []:
            return {'mode': 'clarify', 'answer': 'Этот помощник проверяет учебные аварии. Сформулируйте просьбу проверить аварию в выбранном районе.',
                    'model': ai.MODEL, 'tool_name': None, 'tool_result': None}
        try:
            if not isinstance(calls, list) or len(calls) != 1:
                raise ValueError('Exactly one call is allowed')
            function = calls[0]['function']
            if function['name'] != 'check_outage_status':
                raise ValueError('Tool is not allowed')
            args = OutageToolArguments.model_validate(function['arguments'])
            if args.area_code != area_code:
                raise ValueError('Selected area mismatch')
        except (ValueError, ValidationError, KeyError, TypeError):
            raise ai.AiServiceError(502, 'Модель запросила недопустимое действие или параметры. Попробуйте уточнить вопрос.') from None
        result = outages.check_outage_status(args.area_code)
        return {'mode': 'tool_result', 'answer': result.area_name + '. ' + result.message,
                'model': ai.MODEL, 'tool_name': 'check_outage_status', 'tool_result': result}
    finally:
        rag.pipeline_slot.release()
