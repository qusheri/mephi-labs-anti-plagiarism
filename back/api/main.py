from __future__ import annotations

from uuid import uuid4

import httpx
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from redis.exceptions import RedisError
from sqlalchemy import text

from . import repository
from .config import AI_SCORE_WEIGHT, CLASSIC_SCORE_WEIGHT, REDIS_URL
from .schemas import CheckCreated, CheckList, CheckSummary, ReportResponse, SimilarityResponse
from .storage import UploadValidationError, save_upload
from back.worker.ai_client import AiServiceClient
from back.worker.classic_client import ClassicAlgorithmClient
from back.worker.queue import get_redis
from back.worker.queue import enqueue_check
from back.worker.source_reader import read_source_text


app = FastAPI(title="Antiplag Backend API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    repository.init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
async def ready() -> dict[str, object]:
    checks: dict[str, object] = {}

    try:
        with repository.engine.begin() as db:
            db.execute(text("SELECT 1"))
        checks["postgres"] = {"ok": True}
    except Exception as exc:
        checks["postgres"] = {"ok": False, "error": str(exc)}

    try:
        get_redis().ping()
        checks["redis"] = {"ok": True, "url": REDIS_URL}
    except Exception as exc:
        checks["redis"] = {"ok": False, "error": str(exc)}

    classic_client = ClassicAlgorithmClient()
    checks["classic_cli"] = {
        "ok": classic_client.is_available(),
        "path": classic_client.executable_path,
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{AiServiceClient().base_url}/health")
            checks["ai_service"] = {"ok": response.is_success, "status_code": response.status_code}
    except Exception as exc:
        checks["ai_service"] = {"ok": False, "error": str(exc)}

    ok = all(bool(value.get("ok")) for value in checks.values() if isinstance(value, dict))
    return {"status": "ready" if ok else "not_ready", "checks": checks}


@app.post("/api/v1/checks", response_model=CheckCreated, status_code=status.HTTP_201_CREATED)
def create_check(
    file: UploadFile = File(...),
    title: str = Form(...),
    course: str | None = Form(default=None),
) -> CheckCreated:
    task_id = str(uuid4())
    try:
        stored_path = save_upload(task_id, file)
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    row = repository.create_check(
        task_id=task_id,
        title=title,
        course=course,
        original_filename=file.filename or stored_path.name,
        stored_path=stored_path,
    )
    try:
        enqueue_check(task_id)
    except RedisError as exc:
        repository.set_check_status(task_id, "failed", f"Queue is unavailable: {exc}")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Queue is unavailable") from exc
    return CheckCreated(task_id=row["id"], status=row["status"])


@app.post("/api/v1/similarity", response_model=SimilarityResponse)
async def compare_files(
    file_a: UploadFile = File(...),
    file_b: UploadFile = File(...),
    method: str = Form(default="dfg"),
) -> SimilarityResponse:
    if method not in {"dfg", "no_dfg"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="method must be dfg or no_dfg")

    task_id = str(uuid4())
    try:
        path_a = save_upload(f"{task_id}-a", file_a)
        path_b = save_upload(f"{task_id}-b", file_b)
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    code_a = read_source_text(path_a)
    code_b = read_source_text(path_b)

    try:
        classic = ClassicAlgorithmClient().compare_texts(code_a, code_b)
        ai = await AiServiceClient().compare(code_a, code_b, method=method)  # type: ignore[arg-type]
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Comparison failed: {exc}") from exc

    plagiarism_score = _weighted_score(classic.score, ai.similarity)
    return SimilarityResponse(
        plagiarism_score=plagiarism_score,
        classic_score=classic.score,
        ai_score=ai.similarity,
        classic_result={
            "algorithm": classic.algorithm,
            "score": classic.score,
            "containment": classic.containment,
            "component_scores": classic.component_scores,
            "fragments": classic.fragments,
            "warnings": classic.warnings,
        },
        ai_result={
            "score": ai.similarity,
            "model": ai.model,
            "method": ai.method,
            "device": ai.device,
            "duration_ms": ai.duration_ms,
        },
        score_formula={
            "classic_weight": CLASSIC_SCORE_WEIGHT,
            "ai_weight": AI_SCORE_WEIGHT,
        },
    )


@app.get("/api/v1/checks", response_model=CheckList)
def list_checks(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> CheckList:
    return CheckList(items=[_summary_from_row(row) for row in repository.list_checks(limit, offset)])


@app.get("/api/v1/checks/{task_id}", response_model=CheckSummary)
def get_check(task_id: str) -> CheckSummary:
    row = repository.get_check(task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check task not found")
    return _summary_from_row(row)


@app.get("/api/v1/checks/{task_id}/report", response_model=ReportResponse)
def get_report(task_id: str) -> ReportResponse:
    row = repository.get_check(task_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check task not found")

    if row["status"] != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Report is not ready. Current status: {row['status']}",
        )

    report = repository.get_report(task_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    return ReportResponse(task_id=task_id, status=row["status"], report=report)


def _summary_from_row(row: dict) -> CheckSummary:
    return CheckSummary(
        task_id=row["id"],
        status=row["status"],
        title=row["title"],
        course=row["course"],
        original_filename=row["original_filename"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error_message=row["error_message"],
    )


def _weighted_score(classic_score: float, ai_score: float) -> float:
    total_weight = CLASSIC_SCORE_WEIGHT + AI_SCORE_WEIGHT
    if total_weight <= 0:
        return 0.0
    value = (CLASSIC_SCORE_WEIGHT * classic_score + AI_SCORE_WEIGHT * ai_score) / total_weight
    return max(0.0, min(1.0, value))
