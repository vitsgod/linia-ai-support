from datetime import datetime
from uuid import UUID
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic_core import PydanticCustomError


class TicketInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1, max_length=100, examples=["Алексей"])
    subject: str = Field(min_length=1, max_length=200, examples=["Не работает интернет"])
    description: str = Field(min_length=1, max_length=5000, examples=["Соединение пропало утром"])

    @field_validator("name", "subject", "description", mode="before")
    @classmethod
    def trim_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class TicketRecord(TicketInput):
    id: int
    status: Literal["Новая"]
    created_at: datetime


class DiagnosticInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    description: str = Field(min_length=1, max_length=5000, examples=["Wi-Fi подключён, но сайты не открываются"])

    @field_validator("description")
    @classmethod
    def require_words(cls, value: str) -> str:
        if not any(character.isalpha() for character in value):
            raise PydanticCustomError("description_needs_words", "Опишите словами, что не работает с интернетом или подключением.")
        return value


class DiagnosticSource(BaseModel):
    id: str
    title: str
    section: str
    url: str
    excerpt: str


class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mode: Literal["answer", "clarify"]
    answer: str = Field(min_length=1, max_length=4000)
    source_ids: list[str] = Field(max_length=3)


class DiagnosticResult(BaseModel):
    model: str | None
    answer: str
    mode: Literal["answer", "clarify"]
    sources: list[DiagnosticSource]


AreaCode = Literal['demo-north', 'demo-center', 'demo-south']


class OutageIncident(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=200)


class OutageResult(BaseModel):
    area_code: AreaCode
    area_name: str
    status: Literal['active', 'clear', 'unknown']
    incident: OutageIncident | None
    message: str
    checked_at: datetime
    demo: Literal[True] = True


class OutageToolArguments(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    area_code: AreaCode


class OutageAssistantInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=1000)
    area_code: AreaCode | None = None


class OutageAssistantResult(BaseModel):
    mode: Literal['tool_result', 'clarify']
    answer: str
    model: str | None
    tool_name: Literal['check_outage_status'] | None
    tool_result: OutageResult | None


class TicketDraft(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=5000)


class DraftDecision(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    mode: Literal['draft', 'clarify']
    draft: TicketDraft | None


class DraftResult(DraftDecision):
    model: str | None
    saved: Literal[False] = False
    message: str


class HistoryRun(BaseModel):
    id: UUID
    kind: Literal['diagnostics', 'outage', 'outage_assistant', 'ticket_draft']
    status: Literal['started', 'completed', 'failed']
    request_data: dict
    response_data: dict | None
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
