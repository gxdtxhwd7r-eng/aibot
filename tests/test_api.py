import io
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

from backend.config import Settings, get_settings
from backend.database import LeadRepository
from backend.main import app, get_repository


client = TestClient(app)
TEST_DB = Path(".pytest_cache/api.sqlite3")


def no_key_settings() -> Settings:
    return Settings(openai_api_key="")


def setup_module() -> None:
    TEST_DB.unlink(missing_ok=True)
    app.dependency_overrides[get_settings] = no_key_settings
    app.dependency_overrides[get_repository] = lambda: LeadRepository(str(TEST_DB))


def teardown_module() -> None:
    app.dependency_overrides.clear()
    TEST_DB.unlink(missing_ok=True)


def test_home_page() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "АМК AI —" in response.text


def test_health_reports_missing_key() -> None:
    response = client.get("/api/health")
    assert response.json() == {"status": "ok", "openai_configured": False}


def test_whitespace_advertisement_is_rejected() -> None:
    response = client.post("/api/generate", json={"advertisement": "   "})
    assert response.status_code == 400
    assert response.json()["detail"] == "Вставьте текст объявления."


def test_missing_key_has_clear_error() -> None:
    response = client.post("/api/generate", json={"advertisement": "Lada Vesta, один владелец"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_explicit_legal_burden_is_blocked_without_ai() -> None:
    response = client.post("/api/generate", json={"advertisement": "Kia Rio, автомобиль в залоге у банка"})
    assert response.status_code == 200
    assert response.json() == {
        "status": "do_not_contact",
        "car": None,
        "hook": None,
        "message": None,
        "reason": "НЕ ПИСАТЬ — обнаружено юридическое обременение.",
    }


def test_explicit_dealer_ban_is_blocked() -> None:
    response = client.post("/api/generate", json={"advertisement": "Toyota Camry. Не звонить из автосалонов."})
    assert response.status_code == 200
    assert response.json()["reason"] == "НЕ ПИСАТЬ — продавец не принимает предложения от автосалонов."


def test_reseller_only_ban_is_not_blocked() -> None:
    response = client.post("/api/generate", json={"advertisement": "Toyota Camry. Перекупов не беспокоить."})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def make_xlsx() -> bytes:
    book = Workbook(); sheet = book.active
    sheet.append(["Марка", "Модель", "Описание продавца", "Ссылка CM.Expert"])
    sheet.append(["Toyota", "Camry", "Автосалонам не беспокоить", "https://cm.expert/cars/42"])
    output = io.BytesIO(); book.save(output); return output.getvalue()


def test_upload_rejects_wrong_file_type() -> None:
    response = client.post("/api/import", files={"file": ("report.csv", b"a,b", "text/csv")})
    assert response.status_code == 415


def test_repeated_upload_is_deduplicated_and_blocked_without_ai() -> None:
    content = make_xlsx()
    first = client.post("/api/import", files={"file": ("report.xlsx", content)})
    assert first.status_code == 202
    assert first.json() == {"total_rows": 1, "created": 1, "duplicates": 0, "blocked": 1, "queued": 0, "errors": 0}
    second = client.post("/api/import", files={"file": ("report.xlsx", content)})
    assert second.json()["duplicates"] == 1
    leads = client.get("/api/leads").json()["items"]
    assert len(leads) == 1 and leads[0]["analysis_status"] == "do_not_contact"
