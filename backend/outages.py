"""Read-only tool over fictional local data, not a provider integration."""
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, TypeAdapter, model_validator
from typing import Literal
from backend.schemas import AreaCode, OutageIncident, OutageResult

DATA_FILE = Path(__file__).resolve().parents[1] / 'data' / 'demo_outages.json'
AREA_NAMES = {
    'demo-north': 'Учебный Северный',
    'demo-center': 'Учебный Центральный',
    'demo-south': 'Учебный Южный',
}


class OutageUnavailableError(RuntimeError):
    pass


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    status: Literal['active', 'clear']
    incident: OutageIncident | None

    @model_validator(mode='after')
    def consistent_incident(self):
        if (self.status == 'active') != (self.incident is not None):
            raise ValueError('Incident must exist only for an active outage')
        return self


def check_outage_status(area_code: str) -> OutageResult:
    if area_code not in AREA_NAMES:
        raise ValueError('Unknown demo area')
    try:
        catalog = TypeAdapter(dict[AreaCode, CatalogEntry]).validate_json(DATA_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise OutageUnavailableError('Учебный статус аварий временно недоступен. Попробуйте позже.') from None
    entry = catalog.get(area_code)
    status = entry.status if entry else 'unknown'
    messages = {
        'active': 'В учебном наборе зарегистрирована авария. Срок восстановления не указан.',
        'clear': 'В учебном наборе аварий не зарегистрировано. Это не доказывает, что подключение исправно.',
        'unknown': 'В учебном наборе нет данных по этому району. Сделать вывод о наличии аварии нельзя.',
    }
    return OutageResult(area_code=area_code, area_name=AREA_NAMES[area_code], status=status,
                        incident=entry.incident if entry else None, message=messages[status],
                        checked_at=datetime.now(timezone.utc))
