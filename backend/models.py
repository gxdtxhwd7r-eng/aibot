from typing import Literal

from pydantic import BaseModel, Field, model_validator


class GenerateRequest(BaseModel):
    advertisement: str = Field(min_length=1, max_length=20_000)


class AnalysisResult(BaseModel):
    status: Literal["ok", "do_not_contact"]
    car: str | None = None
    hook: str | None = None
    message: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> "AnalysisResult":
        if self.status == "ok" and not all((self.car, self.hook, self.message)):
            raise ValueError("Для status=ok обязательны car, hook и message")
        if self.status == "do_not_contact" and not self.reason:
            raise ValueError("Для status=do_not_contact обязательна reason")
        return self


class ErrorResponse(BaseModel):
    detail: str

