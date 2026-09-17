import io

import pytest
from openpyxl import Workbook

from backend.batch import process_leads
from backend.cm_expert_parser import header_mapping, iter_xlsx_rows, normalize_header
from backend.database import LeadRepository
from backend.models import AnalysisResult


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
