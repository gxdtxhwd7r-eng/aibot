import io

import pytest
from openpyxl import Workbook

from backend.batch import process_leads
from backend.cm_expert_parser import advertisement_text, header_mapping, iter_xlsx_rows, normalize_header
from backend.database import LeadRepository
from backend.models import AnalysisResult
from backend.safety import find_contact_block


def xlsx(headers, rows):
    book = Workbook(); sheet = book.active; sheet.append(headers)
    for row in rows: sheet.append(row)
    output = io.BytesIO(); book.save(output); return output.getvalue()


def test_header_normalization_and_aliases():
    assert normalize_header("  КОЛ-ВО   ФОТО! ") == "кол во фото"
    assert header_mapping(["Марка автомобиля", "Ссылка / ID CM.Expert", "Неизвестно"]) == {0: "brand", 1: "cm_url"}


def test_row_import_and_missing_optional_columns():
    rows = list(iter_xlsx_rows(xlsx(["Марка", "Модель", "Ссылка Avito"], [["Lada", "Vesta", "https://avito.ru/a?utm_source=x"]])))
    assert rows[0]["source_url"] == "https://avito.ru/a"
    assert rows[0]["source"] == "avito"
    assert rows[0].get("owners") is None


REAL_CM_EXPERT_HEADERS = [
    "Дата публикации", "Дата последнего изменения цены", "Марка", "Модель", "Псевдомодель",
    "Поколение", "Год выпуска", "Состояние", "Пробег, км.", "Цена",
    "Прогнозируемая маржа в процентах", "Прогнозируемая маржа в рублях", "Категория цены",
    "Величина последнего изменения цены, руб", "Цвет", "Привод", "КПП", "Кузов",
    "Двигатель объем, л.", "Двигатель мощность, л.с.", "Двигатель тип", "Руль", "Тип ПТС",
    "Владельцев по ПТС", "Тип ТС", "Продавец", "Имя продавца", "Населенный пункт",
    "Место осмотра", "auto.ru", "Кол-во просмотров", "avito.ru", "Кол-во просмотров",
    "drom.ru", "Кол-во просмотров", "Другие источники",
    "Количество фотографий в объявлении с минимальной ценой", "Фотография 1", "Фотография 2",
    "Фотография 3", "Комментарий продавца на классифайде", "Ссылка в СМЕ",
]


def real_row(**overrides):
    values = {
        "Дата публикации": "17.09.2026", "Марка": "Jaecoo", "Модель": "J7",
        "Год выпуска": 2024, "Состояние": "Не требует ремонта", "Пробег, км.": 12000,
        "Цена": 2850000, "Тип ПТС": "Оригинал", "Владельцев по ПТС": 1,
        "Продавец": "Частное лицо", "Имя продавца": "Иван", "Населенный пункт": "Москва",
        "auto.ru": "https://auto.ru/cars/123", "avito.ru": "https://avito.ru/123",
        "drom.ru": "https://drom.ru/123",
        "Количество фотографий в объявлении с минимальной ценой": 12,
        "Комментарий продавца на классифайде": "Jaecoo в отличном состоянии, обслуживание у дилера.",
        "Ссылка в СМЕ": "https://cm.expert/vehicle/123",
    }
    values.update(overrides)
    return [values.get(header) for header in REAL_CM_EXPERT_HEADERS]


def test_real_cm_expert_headers_are_mapped():
    row = next(iter_xlsx_rows(xlsx(REAL_CM_EXPERT_HEADERS, [real_row()])))
    assert row == row | {
        "description": "Jaecoo в отличном состоянии, обслуживание у дилера.",
        "city": "Москва", "owners": "1", "mileage": "12000", "year": "2024",
        "pts": "Оригинал", "seller_type": "Частное лицо", "seller_name": "Иван",
        "auto_url": "https://auto.ru/cars/123", "avito_url": "https://avito.ru/123",
        "drom_url": "https://drom.ru/123", "cm_url": "https://cm.expert/vehicle/123", "photos": "12",
    }


@pytest.mark.asyncio
async def test_real_dealer_ban_is_blocked_without_ai(tmp_path):
    description = (
        "Один владелец, не бита, не крашена, то во время, пробег оригинал. "
        "С продажей не тороплюсь, торг есть, салонам не беспокоить."
    )
    parsed = next(iter_xlsx_rows(xlsx(REAL_CM_EXPERT_HEADERS, [real_row(**{
        "Комментарий продавца на классифайде": description,
    })])))
    assert parsed["description"] == description
    assert find_contact_block(parsed["description"]) is not None
    repository = LeadRepository(str(tmp_path / "blocked.sqlite3"))
    lead_id = repository.create(parsed)

    class Service:
        async def analyze(self, text):
            raise AssertionError("AIService must not be called for a blocked lead")

    await process_leads(repository, [lead_id], Service())
    assert repository.get(lead_id)["analysis_status"] == "do_not_contact"


@pytest.mark.asyncio
async def test_real_jaecoo_description_is_sent_to_ai(tmp_path):
    parsed = next(iter_xlsx_rows(xlsx(REAL_CM_EXPERT_HEADERS, [real_row()])))
    assert "Описание: Jaecoo в отличном состоянии" in advertisement_text(parsed)
    repository = LeadRepository(str(tmp_path / "jaecoo.sqlite3"))
    lead_id = repository.create(parsed)

    class Service:
        received = None

        async def analyze(self, text):
            self.received = text
            return AnalysisResult(status="ok", car="Jaecoo J7", hook="Дилерское ТО", message="Сообщение")

    service = Service()
    await process_leads(repository, [lead_id], service)
    assert "Описание: Jaecoo в отличном состоянии, обслуживание у дилера." in service.received
    assert repository.get(lead_id)["analysis_status"] == "ready"


def test_repository_deduplicates(tmp_path):
    repository = LeadRepository(str(tmp_path / "db.sqlite3")); row = {"external_id": "cm:123", "brand": "Kia"}
    assert repository.create(row) is not None
    assert repository.create(row) is None


@pytest.mark.asyncio
async def test_block_is_not_sent_to_ai(tmp_path):
    repository = LeadRepository(str(tmp_path / "db.sqlite3"))
    lead_id = repository.create({"external_id": "1", "brand": "Kia", "description": "Автосалонам не беспокоить"})
    class Service:
        async def analyze(self, text): raise AssertionError("AI must not be called")
    await process_leads(repository, [lead_id], Service())
    assert repository.get(lead_id)["analysis_status"] == "do_not_contact"


@pytest.mark.asyncio
async def test_one_ai_error_does_not_stop_batch(tmp_path):
    repository = LeadRepository(str(tmp_path / "db.sqlite3"))
    first = repository.create({"external_id": "1", "brand": "Bad"}); second = repository.create({"external_id": "2", "brand": "Good"})
    class Service:
        async def analyze(self, text):
            if "Bad" in text: raise RuntimeError("secret details")
            return AnalysisResult(status="ok", car="Good", hook="hook", message="message")
    await process_leads(repository, [first, second], Service(), concurrency=2)
    assert repository.get(first)["analysis_status"] == "error"
    assert repository.get(first)["reason"] == "Не удалось выполнить AI-анализ."
    assert repository.get(second)["analysis_status"] == "ready"
