from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError

from backend.ai_service import AIService
from backend.api_client import create_openai_client
from backend.batch import process_leads
from backend.cm_expert_parser import advertisement_text, iter_xlsx_rows
from backend.config import Settings, get_settings
from backend.database import LeadRepository
from backend.models import AnalysisResult, ErrorResponse, GenerateRequest
from backend.safety import find_contact_block

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="АМК AI", version="1.0.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def get_repository(settings: Settings = Depends(get_settings)) -> LeadRepository:
    return LeadRepository(settings.database_path)


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health(settings: Settings = Depends(get_settings)) -> dict[str, str | bool]:
    return {"status": "ok", "openai_configured": bool(settings.openai_api_key)}


@app.post(
    "/api/generate",
    response_model=AnalysisResult,
    responses={400: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
)
async def generate(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
) -> AnalysisResult:
    advertisement = request.advertisement.strip()
    if not advertisement:
        raise HTTPException(status_code=400, detail="Вставьте текст объявления.")

    block = find_contact_block(advertisement)
    if block:
        return AnalysisResult(status="do_not_contact", reason=block.reason)

    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="Не настроен OpenAI API. Добавьте OPENAI_API_KEY в файл .env.",
        )

    try:
        service = AIService(create_openai_client(settings), settings.openai_model)
        return await service.analyze(advertisement)
    except (APIConnectionError, APIStatusError, APITimeoutError, OpenAIError, RuntimeError):
        raise HTTPException(
            status_code=503,
            detail="Не удалось получить ответ от AI. Проверьте подключение и API.",
        ) from None


@app.post("/api/import", status_code=202)
async def import_xlsx(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
    repository: LeadRepository = Depends(get_repository),
) -> dict[str, int]:
    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".xlsx":
        raise HTTPException(status_code=415, detail="Поддерживаются только файлы .xlsx.")
    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    await file.close()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Файл больше {settings.max_upload_mb} МБ.")

    stats = {"total_rows": 0, "created": 0, "duplicates": 0, "blocked": 0, "queued": 0, "errors": 0}
    queued_ids: list[int] = []
    try:
        for row in iter_xlsx_rows(content):
            stats["total_rows"] += 1
            text = advertisement_text(row)
            block = find_contact_block(text)
            invalid = not text or not any(row.get(key) for key in ("brand", "model", "description"))
            lead_id = repository.create(row)
            if lead_id is None:
                stats["duplicates"] += 1
                continue
            stats["created"] += 1
            if invalid:
                stats["errors"] += 1
                repository.update_analysis(lead_id, "error", reason="Недостаточно данных для анализа.")
            elif block:
                stats["blocked"] += 1
                repository.update_analysis(lead_id, "do_not_contact", reason=block.reason)
            elif not settings.openai_api_key:
                stats["errors"] += 1
                repository.update_analysis(lead_id, "error", reason="OpenAI API не настроен.")
            else:
                stats["queued"] += 1
                queued_ids.append(lead_id)
    except (ValueError, OSError, KeyError):
        raise HTTPException(status_code=400, detail="Не удалось прочитать XLSX или найти заголовки CM.Expert.") from None

    if queued_ids:
        # A single client is shared by all rows in this batch.
        service = AIService(create_openai_client(settings), settings.openai_model)
        background_tasks.add_task(process_leads, repository, queued_ids, service, settings.ai_concurrency)
    return stats


@app.get("/api/leads")
async def list_leads(
    limit: int = 200,
    offset: int = 0,
    repository: LeadRepository = Depends(get_repository),
) -> dict:
    if not 1 <= limit <= 500 or offset < 0:
        raise HTTPException(status_code=422, detail="Некорректные параметры списка.")
    return {"items": repository.list(limit, offset), "status": repository.counts()}


@app.get("/api/leads/{lead_id}")
async def get_lead(lead_id: int, repository: LeadRepository = Depends(get_repository)) -> dict:
    lead = repository.get(lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Объявление не найдено.")
    return lead


@app.patch("/api/leads/{lead_id}/status")
async def update_lead_status(lead_id: int, payload: dict, repository: LeadRepository = Depends(get_repository)) -> dict:
    status = payload.get("status")
    if status not in {"new", "contacted", "skipped"}:
        raise HTTPException(status_code=422, detail="Статус должен быть new, contacted или skipped.")
    if not repository.manager_status(lead_id, status):
        raise HTTPException(status_code=404, detail="Объявление не найдено.")
    return repository.get(lead_id) or {}
