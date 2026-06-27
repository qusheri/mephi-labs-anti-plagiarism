from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    MetaData,
    String,
    Table,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.engine import RowMapping

from .config import DATABASE_URL


metadata = MetaData()

check_tasks = Table(
    "check_tasks",
    metadata,
    Column("id", String, primary_key=True),
    Column("status", String, nullable=False),
    Column("title", String, nullable=False),
    Column("course", String, nullable=True),
    Column("original_filename", String, nullable=False),
    Column("stored_path", String, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("error_message", String, nullable=True),
)

reports = Table(
    "reports",
    metadata,
    Column("task_id", String, ForeignKey("check_tasks.id"), primary_key=True),
    Column("report_json", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def init_db() -> None:
    metadata.create_all(engine)


def create_check(
    task_id: str,
    title: str,
    course: str | None,
    original_filename: str,
    stored_path: Path,
) -> dict[str, Any]:
    now = utc_now()
    with engine.begin() as db:
        db.execute(
            insert(check_tasks).values(
                id=task_id,
                status="queued",
                title=title,
                course=course,
                original_filename=original_filename,
                stored_path=str(stored_path),
                created_at=now,
                updated_at=now,
                error_message=None,
            )
        )
        row = db.execute(select(check_tasks).where(check_tasks.c.id == task_id)).mappings().one()
    return _row_to_dict(row)


def get_check(task_id: str) -> dict[str, Any] | None:
    with engine.begin() as db:
        row = db.execute(select(check_tasks).where(check_tasks.c.id == task_id)).mappings().first()
    return _row_to_dict(row) if row else None


def list_checks(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    with engine.begin() as db:
        rows = (
            db.execute(
                select(check_tasks)
                .order_by(check_tasks.c.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
    return [_row_to_dict(row) for row in rows]


def list_candidate_checks(task_id: str, course: str | None, limit: int = 5) -> list[dict[str, Any]]:
    query = (
        select(check_tasks)
        .where(check_tasks.c.id != task_id)
        .where(check_tasks.c.status == "done")
        .order_by(check_tasks.c.created_at.desc())
        .limit(limit)
    )
    if course:
        query = query.where(check_tasks.c.course == course)

    with engine.begin() as db:
        rows = db.execute(query).mappings().all()
    return [_row_to_dict(row) for row in rows]


def set_check_status(task_id: str, status: str, error_message: str | None = None) -> None:
    with engine.begin() as db:
        db.execute(
            update(check_tasks)
            .where(check_tasks.c.id == task_id)
            .values(
                status=status,
                error_message=error_message,
                updated_at=utc_now(),
            )
        )


def save_report(task_id: str, report: dict[str, Any]) -> None:
    now = utc_now()
    with engine.begin() as db:
        existing = db.execute(select(reports.c.task_id).where(reports.c.task_id == task_id)).first()
        if existing:
            db.execute(
                update(reports)
                .where(reports.c.task_id == task_id)
                .values(report_json=report, created_at=now)
            )
        else:
            db.execute(insert(reports).values(task_id=task_id, report_json=report, created_at=now))

        db.execute(
            update(check_tasks)
            .where(check_tasks.c.id == task_id)
            .values(status="done", updated_at=now, error_message=None)
        )


def get_report(task_id: str) -> dict[str, Any] | None:
    with engine.begin() as db:
        row = db.execute(select(reports.c.report_json).where(reports.c.task_id == task_id)).first()
    if row is None:
        return None
    return row[0]


def _row_to_dict(row: RowMapping) -> dict[str, Any]:
    return dict(row)
