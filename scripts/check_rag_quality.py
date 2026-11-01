"""Development evaluation: explicit criteria, real local model, visible fallback count."""
import json
from pathlib import Path
import re
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import ai, rag
from backend.answer_quality import repeated_checks

# Independent checks on selected recommendation forms, not a copy of the runtime detector.
CABLE_ADVICE = (r'\b(?:проверьте|проверяйте|убедитесь|осмотрите|посмотрите)[^.!?]{0,90}кабел'
                r'|\bуточните,?\s+(?:подключены|проверены)[^.!?]{0,60}кабел')
RESTART_ADVICE = r'\b(?:перезагрузите|перезапустите|повторите\s+перезагрузку)\b'
CASES = [
    {'id': 'one_device', 'question': 'На телефоне интернет есть, а на ноутбуке нет',
     'modes': ['answer'], 'document': 'one-device-offline', 'forbid': [RESTART_ADVICE]},
    {'id': 'completed_checks', 'question': 'Пропал интернет на всех устройствах, кабели проверены, перезагрузка не помогла',
     'modes': ['answer', 'clarify'], 'document': 'all-devices-offline', 'forbid': [CABLE_ADVICE, RESTART_ADVICE]},
    {'id': 'wifi_completed_restart', 'question': 'По кабелю интернет работает, Wi-Fi не виден, роутер уже перезагружал',
     'modes': ['answer', 'clarify'], 'document': 'wifi-network-missing', 'forbid': [RESTART_ADVICE]},
    {'id': 'not_completed', 'question': 'Интернет пропал на всех устройствах, кабели ещё не проверял, роутер не перезагружал',
     'modes': ['answer'], 'document': 'all-devices-offline', 'forbid': []},
    {'id': 'specialist_details', 'question': 'Какие данные сообщить специалисту при проблеме с интернетом?',
     'modes': ['answer'], 'document': None, 'forbid': []},
    {'id': 'completed_paraphrase', 'question': 'Интернета нет нигде. Я уже проверила кабель и перезапустила роутер.',
     'modes': ['answer', 'clarify'], 'document': 'all-devices-offline', 'forbid': [CABLE_ADVICE, RESTART_ADVICE]},
    {'id': 'off_topic', 'question': 'Как приготовить борщ?', 'modes': ['clarify'], 'forbid': []},
    {'id': 'greeting', 'question': 'Привет', 'modes': ['clarify'], 'forbid': []},
    {'id': 'vague', 'question': 'ничего не работает', 'modes': ['clarify'], 'forbid': []},
    {'id': 'poem', 'question': 'Напиши стихотворение про интернет', 'modes': ['clarify'], 'forbid': []},
]


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    results = []
    generate = ai.diagnose
    for case in CASES:
        raw_responses = []

        def capture(*args, **kwargs):
            result = generate(*args, **kwargs)
            raw_responses.append(result)
            return result

        started = time.monotonic()
        try:
            with patch('backend.rag.ai.diagnose', side_effect=capture):
                response = rag.diagnose(case['question'])
            criteria = {
                'allowed_mode': response['mode'] in case['modes'],
                'no_forbidden_advice': not any(re.search(p, response['answer'], re.I) for p in case['forbid']),
                'source_contract': bool(response['sources']) if response['mode'] == 'answer' else not response['sources'],
                'expected_document': response['mode'] != 'answer' or not case.get('document') or
                                     any(s['id'].startswith(case['document'] + ':') for s in response['sources']),
            }
            raw = raw_responses[-1] if raw_responses else None
            conflicts = sorted(repeated_checks(case['question'], raw['answer'])) if raw and raw['mode'] == 'answer' else []
            result = {'id': case['id'], 'question': case['question'], 'criteria': criteria,
                      'passed': all(criteria.values()), 'raw_generation': raw,
                      'blocked_repeats': conflicts, 'response': response}
        except Exception as exc:
            result = {'id': case['id'], 'question': case['question'], 'passed': False, 'error_type': type(exc).__name__}
        result['seconds'] = round(time.monotonic() - started, 2)
        results.append(result)
        report = {
            'scope': 'development_examples_not_general_accuracy',
            'criteria_limit': 'selected_wordings_only; human_review_still_required',
            'answer_count': sum(r.get('response', {}).get('mode') == 'answer' for r in results),
            'clarify_count': sum(r.get('response', {}).get('mode') == 'clarify' for r in results),
            'blocked_repeat_count': sum(bool(r.get('blocked_repeats')) for r in results),
            'cases': results,
        }
        (ROOT / 'docs' / 'rag-quality-check.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{'OK' if result['passed'] else 'FAIL'} {case['id']}: {result.get('response', {}).get('mode')} ({result['seconds']}s)", flush=True)
    if not all(r['passed'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
