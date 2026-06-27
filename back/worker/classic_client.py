from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from back.api.config import BACK_DIR


@dataclass(frozen=True)
class ClassicCompareResult:
    score: float
    containment: float
    algorithm: str
    component_scores: dict[str, float]
    fragments: list[dict[str, Any]]
    warnings: list[str]


class ClassicAlgorithmClient:
    def __init__(self, executable_path: str | None = None, timeout_seconds: float = 30.0) -> None:
        self.executable_path = executable_path or os.getenv("ANTIPLAG_ALGOS_CLI") or _default_executable()
        self.timeout_seconds = timeout_seconds

    def compare_files(self, file_a: str | Path, file_b: str | Path) -> ClassicCompareResult:
        completed = subprocess.run(
            [self.executable_path, str(file_a), str(file_b)],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout_seconds,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            raise RuntimeError(f"classic algorithms failed: {detail}")

        data = json.loads(completed.stdout)
        return ClassicCompareResult(
            score=float(data["score"]),
            containment=float(data["containment"]),
            algorithm=str(data["algorithm"]),
            component_scores={str(key): float(value) for key, value in data.get("component_scores", {}).items()},
            fragments=list(data.get("fragments", [])),
            warnings=list(data.get("warnings", [])),
        )

    def compare_texts(self, code_a: str, code_b: str) -> ClassicCompareResult:
        with tempfile.TemporaryDirectory(prefix="antiplag-classic-") as tmp_dir:
            path_a = Path(tmp_dir) / "a.cpp"
            path_b = Path(tmp_dir) / "b.cpp"
            path_a.write_text(code_a, encoding="utf-8")
            path_b.write_text(code_b, encoding="utf-8")
            return self.compare_files(path_a, path_b)

    def is_available(self) -> bool:
        return Path(self.executable_path).exists()


def _default_executable() -> str:
    suffix = ".exe" if os.name == "nt" else ""
    candidates = [
        BACK_DIR / "algos" / "build" / "Debug" / f"antiplag_algos_cli{suffix}",
        BACK_DIR / "algos" / "build" / f"antiplag_algos_cli{suffix}",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])
