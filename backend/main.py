from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAIError

from backend.ai_service import AIService
from backend.api_client import create_openai_client
from backend.config import Settings, get_settings
from backend.models import AnalysisResult, ErrorResponse, GenerateRequest
from backend.safety import find_contact_block

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(title="АМК AI", version="1.0.0", docs_url="/api/docs")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


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

