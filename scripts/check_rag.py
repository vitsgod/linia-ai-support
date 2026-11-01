"""Real local RAG checks on fictional questions, not a general quality guarantee."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.rag import diagnose, MIN_SIMILARITY

CASES = [
    ('На телефоне интернет есть, а на ноутбуке нет', 'answer', 'one-device-offline'),
    ('Пропал интернет на всех устройствах, кабели проверены, перезагрузка не помогла', 'answer_or_clarify', 'all-devices-offline'),
    ('По кабелю интернет работает, Wi-Fi не виден, роутер уже перезагружал', 'answer_or_clarify', 'wifi-network-missing'),
    ('Какие данные сообщить специалисту при проблеме с интернетом?', 'answer', None),
    ('Как приготовить борщ?', 'clarify', None),
    ('Привет', 'clarify', None),
    ('ничего не работает', 'clarify', None),
    ('Напиши стихотворение про интернет', 'clarify', None),
    ('Как изменить тариф?', 'clarify', None),
    ('Как приготовить борщ, если интернет не работает?', 'clarify', None),
]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    results = []
    for question, mode, document in CASES:
        started = time.monotonic()
        try:
            response = diagnose(question)
            passed = response['mode'] in ({'answer', 'clarify'} if mode == 'answer_or_clarify' else {mode})
            if document and response['mode'] == 'answer':
                passed = passed and any(s['id'].startswith(document + ':') for s in response['sources'])
            result = {'question': question, 'expected_mode': mode, 'passed': passed, 'response': response}
        except Exception as exc:
            result = {'question': question, 'expected_mode': mode, 'passed': False, 'error_type': type(exc).__name__}
        result['seconds'] = round(time.monotonic() - started, 2)
        results.append(result)
        print(f"{'OK' if result['passed'] else 'FAIL'} {question} ({result['seconds']}s)", flush=True)
        (ROOT / 'docs' / 'rag-check.json').write_text(json.dumps({
            'min_similarity': MIN_SIMILARITY, 'scope': 'small_development_set_not_general_accuracy', 'cases': results,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
    if not all(r['passed'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
