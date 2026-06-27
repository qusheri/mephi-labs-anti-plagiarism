from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


CheckStatus = Literal["queued", "running", "done", "failed"]


class CheckCreated(BaseModel):
    task_id: str
    status: CheckStatus


class CheckSummary(BaseModel):
    task_id: str
    status: CheckStatus
    title: str
    course: str | None
    original_filename: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None


class CheckList(BaseModel):
    items: list[CheckSummary]


class ReportResponse(BaseModel):
    task_id: str
    status: CheckStatus
    report: dict[str, Any]


class SimilarityResponse(BaseModel):
    plagiarism_score: float
    classic_score: float
    ai_score: float
    classic_result: dict[str, Any]
    ai_result: dict[str, Any]
    score_formula: dict[str, float]
