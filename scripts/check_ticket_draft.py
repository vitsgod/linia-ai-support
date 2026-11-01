"""Real draft generation; verify working tickets do not change."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.ticket_draft import prepare
from backend.database import list_tickets


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    before = list_tickets()
    cases = [
        ('На телефоне интернет есть, на ноутбуке нет. Переподключение к сети не помогло.', 'draft'),
        ('По кабелю интернет работает, но сеть Wi-Fi не видна. Роутер уже перезагружал.', 'draft'),
        ('Привет', 'clarify'), ('Как приготовить борщ?', 'clarify'), ('ничего не работает', 'clarify'),
    ]
    results = []
    for description, mode in cases:
        try:
            response = prepare(description)
            passed = response['mode'] == mode and response['saved'] is False
            results.append({'description': description, 'expected_mode': mode, 'passed': passed, 'response': response})
        except Exception as exc:
            results.append({'description': description, 'passed': False, 'error_type': type(exc).__name__})
        print(f"{'OK' if results[-1]['passed'] else 'FAIL'} {mode}", flush=True)
    unchanged = list_tickets() == before
    (ROOT / 'docs' / 'ticket-draft-check.json').write_text(json.dumps({
        'scope': 'development_examples_mode_only_human_fact_review_required',
        'tickets_unchanged': unchanged, 'cases': results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    if not unchanged or not all(case['passed'] for case in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
