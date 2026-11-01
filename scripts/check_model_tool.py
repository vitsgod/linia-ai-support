"""Real native tool selection over fictional data; not a general accuracy claim."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import ai, outage_assistant


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cases = [(area, 'Проверь, есть ли авария в выбранном районе.', 'tool_result', status)
             for area, status in [('demo-north', 'active'), ('demo-center', 'clear'), ('demo-south', 'unknown')]]
    cases += [('demo-north', 'Привет', 'clarify', None), ('demo-north', 'Как приготовить борщ?', 'clarify', None),
              (None, 'Проверь аварии', 'clarify', None)]
    reports = []
    selector = ai.select_outage_tool
    for area, question, mode, status in cases:
        native_calls = []

        def capture(*args, **kwargs):
            calls = selector(*args, **kwargs)
            native_calls.append(calls)
            return calls

        with patch('backend.ai.select_outage_tool', side_effect=capture):
            response = outage_assistant.run(question, area)
        serialized = json.loads(json.dumps(response, default=lambda value: value.model_dump(mode='json')))
        passed = response['mode'] == mode and (status is None or serialized['tool_result']['status'] == status)
        reports.append({'area_code': area, 'question': question, 'native_calls': native_calls,
                        'response': serialized, 'passed': passed})
        (ROOT / 'docs' / 'model-tool-check.json').write_text(json.dumps({
            'scope': 'six_development_examples_not_general_accuracy', 'cases': reports,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"{'OK' if passed else 'FAIL'} {area}: {mode}", flush=True)
    if not all(case['passed'] for case in reports):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
