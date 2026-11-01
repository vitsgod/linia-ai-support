from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.staticfiles import StaticFiles
import os
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
import psycopg

from backend import ai, database, rag, outages, outage_assistant, ticket_draft, history
from backend.schemas import HistoryRun, AreaCode, OutageResult, OutageAssistantInput, OutageAssistantResult, DraftResult, DiagnosticInput, DiagnosticResult, TicketInput, TicketRecord

app = FastAPI(title="Помощник техподдержки")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    required_messages = {
        "name": "Введите имя",
        "subject": "Введите тему обращения",
        "description": "Введите описание проблемы",
        "question": "Введите вопрос помощнику",
    }
    details = []
    allowed_fields = ("question и area_code" if request.url.path == '/api/assistant/outage'
                      else "description" if request.url.path in {"/api/diagnostics", '/api/assistant/ticket-draft'} else "name, subject и description")
    for error in exc.errors():
        location = error["loc"]
        field = str(location[1]) if len(location) > 1 else "body"
        error_type = error["type"]
        if error_type == "json_invalid":
            field, message = "body", "Некорректный JSON: проверьте кавычки и запятые"
        elif field == "body":
            message = f"Передайте JSON-объект с полями: {allowed_fields}"
        elif error_type in {"missing", "string_too_short"}:
            message = required_messages.get(field, "Заполните обязательное поле")
        elif error_type == "description_needs_words":
            message = "Опишите словами, что не работает с интернетом или подключением."
        elif error_type == "string_too_long":
            message = f"Допустимо не более {error['ctx']['max_length']} символов"
        elif error_type == "string_type":
            message = "Значение должно быть строкой"
        elif error_type == "extra_forbidden":
            message = f"Лишнее поле. Разрешены только: {allowed_fields}"
        elif field == 'area_code':
            message = 'Выберите учебный район из списка'
        else:
            message = "Некорректное значение"
        details.append({"field": field, "message": message})
    return JSONResponse(status_code=422, content={"detail": details})


@app.post("/api/tickets/validate", summary="Проверить данные без сохранения")
def validate_ticket(ticket: TicketInput) -> dict:
    return {
        "message": "Данные проверены. Заявка пока не сохранена.",
        "saved": False,
        "ticket": ticket.model_dump(),
    }


@app.exception_handler(psycopg.Error)
async def database_error_handler(request: Request, exc: psycopg.Error) -> JSONResponse:
    message = (
        "Не удалось сохранить заявку. Попробуйте позже."
        if request.method == "POST"
        else "Не удалось загрузить заявки. Попробуйте позже."
    )
    return JSONResponse(status_code=503, content={"detail": message})


@app.post("/api/tickets", status_code=201, response_model=TicketRecord, summary="Создать заявку")
def create_ticket(ticket: TicketInput) -> dict:
    return database.create_ticket(ticket)


@app.get("/api/tickets", response_model=list[TicketRecord], summary="Список заявок")
def list_tickets() -> list[dict]:
    return database.list_tickets()


@app.exception_handler(ai.AiServiceError)
async def ai_error_handler(request: Request, exc: ai.AiServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.post("/api/diagnostics", response_model=DiagnosticResult, summary="Предложить шаги диагностики с ИИ")
def diagnose_problem(problem: DiagnosticInput) -> dict:
    return history.record('diagnostics', problem.model_dump(), lambda: rag.diagnose(problem.description), DiagnosticResult)


@app.get('/api/knowledge/{source}', summary='Учебная инструкция')
def get_knowledge_source(source: str):
    documents = {path.name: path for path in rag.KNOWLEDGE_DIR.glob('*.md')}
    if source not in documents:
        raise HTTPException(status_code=404, detail='Инструкция не найдена')
    return FileResponse(documents[source], media_type='text/plain; charset=utf-8')


@app.exception_handler(outages.OutageUnavailableError)
async def outage_error_handler(request: Request, exc: outages.OutageUnavailableError):
    return JSONResponse(status_code=503, content={'detail': str(exc)})


@app.get('/api/outages/{area_code}', response_model=OutageResult, summary='Проверить учебный статус аварий')
def check_outages(area_code: AreaCode) -> dict:
    return history.record('outage', {'area_code': area_code}, lambda: outages.check_outage_status(area_code), OutageResult)


@app.post('/api/assistant/outage', response_model=OutageAssistantResult, summary='Поручить помощнику проверить учебную аварию')
def assistant_outage(problem: OutageAssistantInput) -> dict:
    return history.record('outage_assistant', problem.model_dump(), lambda: outage_assistant.run(problem.question, problem.area_code), OutageAssistantResult)


@app.post('/api/assistant/ticket-draft', response_model=DraftResult, summary='Подготовить черновик без сохранения заявки')
def prepare_ticket_draft(problem: DiagnosticInput) -> dict:
    return history.record('ticket_draft', problem.model_dump(), lambda: ticket_draft.prepare(problem.description), DraftResult)


@app.exception_handler(history.HistoryUnavailableError)
async def history_error_handler(request: Request, exc: history.HistoryUnavailableError):
    return JSONResponse(status_code=503, content={'detail': str(exc)})


@app.get('/api/history', response_model=list[HistoryRun], summary='История запросов помощника')
def list_history(limit: int = Query(default=20, ge=1, le=50)) -> list[dict]:
    return history.list_runs(limit)


if static_directory := os.environ.get('FRONTEND_DIST'):
    app.mount('/', StaticFiles(directory=static_directory, html=True), name='frontend')
