import asyncio
import logging
from typing import Any

from backend.cm_expert_parser import advertisement_text
from backend.database import LeadRepository
from backend.safety import find_contact_block

logger = logging.getLogger(__name__)


async def process_leads(repository: LeadRepository, lead_ids: list[int], service: Any, concurrency: int = 3) -> None:
    semaphore = asyncio.Semaphore(concurrency)

    async def process(lead_id: int) -> None:
        row = repository.get(lead_id)
        if not row:
            return
        text = advertisement_text(row)
        if not text or not any(row.get(key) for key in ("brand", "model", "description")):
            repository.update_analysis(lead_id, "error", reason="Недостаточно данных для анализа.")
            return
        block = find_contact_block(text)
        if block:
            repository.update_analysis(lead_id, "do_not_contact", reason=block.reason)
            return
        repository.update_analysis(lead_id, "processing")
        try:
            async with semaphore:
                result = await service.analyze(text)
            if result.status == "do_not_contact":
                repository.update_analysis(lead_id, "do_not_contact", reason=result.reason)
            else:
                repository.update_analysis(lead_id, "ready", car=result.car, hook=result.hook, message=result.message, reason=result.reason)
        except Exception as error:  # one remote failure must not cancel the batch
            logger.warning("AI analysis failed for lead %s: %s", lead_id, type(error).__name__)
            repository.update_analysis(lead_id, "error", reason="Не удалось выполнить AI-анализ.")

    await asyncio.gather(*(process(lead_id) for lead_id in lead_ids))
