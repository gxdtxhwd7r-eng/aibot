from fastapi.testclient import TestClient

from backend.config import Settings, get_settings
from backend.main import app


client = TestClient(app)


def no_key_settings() -> Settings:
    return Settings(openai_api_key="")


def setup_module() -> None:
    app.dependency_overrides[get_settings] = no_key_settings


def teardown_module() -> None:
    app.dependency_overrides.clear()


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

