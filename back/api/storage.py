from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import UploadFile

from .config import ALLOWED_EXTENSIONS, MAX_UPLOAD_BYTES, UPLOADS_DIR


class UploadValidationError(ValueError):
    pass


def validate_upload_filename(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise UploadValidationError(f"Unsupported file extension '{suffix}'. Allowed: {allowed}")


def save_upload(task_id: str, upload: UploadFile) -> Path:
    if not upload.filename:
        raise UploadValidationError("File name is required")

    validate_upload_filename(upload.filename)

    task_dir = UPLOADS_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    target_path = task_dir / Path(upload.filename).name

    total = 0
    with target_path.open("wb") as output:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                output.close()
                target_path.unlink(missing_ok=True)
                raise UploadValidationError("Uploaded file is too large")
            output.write(chunk)

    upload.file.seek(0)
    return target_path


def remove_task_uploads(task_id: str) -> None:
    task_dir = UPLOADS_DIR / task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)
