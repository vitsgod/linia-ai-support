"""Narrow rules for two known repeated checks, not general semantic validation."""
import re

OBJECTS = {
    'cables': r'\bкабел\w*',
    'router_restart': r'\b(?:роутер|маршрутизатор)\w*',
}
DONE = {
    'cables': r'\bпровер(?:ил[аи]?|ял[аи]?|ен[аоы]?)\b',
    'router_restart': r'\b(?:перезагрузил[аи]?|перезагружал[аи]?|перезапустил[аи]?|'
                      r'перезапускал[аи]?|перезагружен[аоы]?|перезапущен[аоы]?)\b',
}
SUGGEST = {
    'cables': r'\b(?:проверьте|проверяйте|проверить|осмотрите|посмотрите|убедитесь|'
              r'уточните(?=\s*,?\s*(?:подключены|проверены|не\s+отошли)\b))\b',
    'router_restart': r'\b(?:перезагрузите|перезагружайте|перезагрузить|перезагружать|'
                      r'перезапустите|перезапускайте|перезапустить|перезапускать|'
                      r'повторите\s+перезагрузку)\b',
}
OTHER_DEVICE = r'\b(?:ноутбук|компьютер|телефон)\w*'


def _normal(text: str) -> str:
    return re.sub(r'\s+', ' ', text.casefold().replace('ё', 'е'))


def _negated(prefix: str) -> bool:
    return re.search(r'\bне(?:\s+(?:еще|пока|успел|смог|стал|нужно|надо|следует|стоит))?\s*$', prefix) is not None


def completed_checks(description: str) -> set[str]:
    completed = set()
    for clause in re.split(r'[.!?;,\n]', _normal(description)):
        for action, pattern in DONE.items():
            for match in re.finditer(pattern, clause):
                prefix = clause[:match.start()]
                if (_negated(prefix) or re.search(r'\bесли\b', prefix)
                        or re.match(r'\s+ли\b', clause[match.end():])):
                    continue
                neighborhood = clause[max(0, match.start() - 50):match.end() + 50]
                if re.search(OBJECTS[action], neighborhood):
                    completed.add(action)
        if (re.search(r'\bперезагрузка(?:\s+роутера)?\s+не\s+помог(?:ла|ает)\b', clause)
                and not re.search(OTHER_DEVICE, clause)):
            completed.add('router_restart')
    return completed


def repeated_checks(description: str, answer: str) -> set[str]:
    completed = completed_checks(description)
    conflicts = set()
    for sentence in re.split(r'[.!?;\n]', _normal(answer)):
        for action in completed:
            if action == 'cables':
                # Keep enumerated checks together; an acknowledgement is not a recommendation.
                clauses = [re.sub(r'\bкабел\w*\s+(?:уже\s+)?проверен\w*', '', sentence)]
            else:
                clauses = re.split(r',\s*', sentence)
            for clause in clauses:
                for match in re.finditer(SUGGEST[action], clause):
                    if _negated(clause[:match.start()]):
                        continue
                    if re.match(r'(?:\s+\w+){0,3}\s+не\s+(?:нужно|надо|следует|стоит)\b', clause[match.end():]):
                        continue
                    neighborhood = clause[max(0, match.start() - 100):match.end() + 100]
                    if action == 'router_restart':
                        if not re.search(OTHER_DEVICE, neighborhood) or re.search(OBJECTS[action], neighborhood):
                            conflicts.add(action)
                    elif re.search(OBJECTS[action], neighborhood):
                        conflicts.add(action)
    return conflicts


def clarification_for_repeats(checks: set[str]) -> str:
    labels = {'cables': 'проверку кабелей', 'router_restart': 'перезагрузку роутера'}
    done = ' и '.join(labels[action] for action in sorted(checks))
    return (f'Вы уже описали {done}. Уточните, какие индикаторы горят на роутере '
            'и какую ошибку показывает устройство. Эти сведения помогут выбрать следующий шаг.')
