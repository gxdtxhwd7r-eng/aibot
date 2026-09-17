from openai import AsyncOpenAI

from backend.models import AnalysisResult
from backend.system_prompt import build_system_prompt


class AIService:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self.client = client
        self.model = model

    async def analyze(self, advertisement: str) -> AnalysisResult:
        completion = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=[
                {"role": "system", "content": build_system_prompt()},
                {"role": "user", "content": advertisement},
            ],
            response_format=AnalysisResult,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("AI не вернул структурированный ответ")
        return parsed

