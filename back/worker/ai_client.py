from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

import httpx


DEFAULT_AI_SERVICE_URL = "http://127.0.0.1:8001"


@dataclass(frozen=True)
class AiCompareResult:
    similarity: float
    model: str
    method: str
    device: str
    duration_ms: int


class AiServiceClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: float = 180.0,
    ) -> None:
        self.base_url = (base_url or os.getenv("ANTIPLAG_AI_SERVICE_URL") or DEFAULT_AI_SERVICE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def compare(
        self,
        code_a: str,
        code_b: str,
        method: Literal["dfg", "no_dfg"] = "dfg",
    ) -> AiCompareResult:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/compare",
                json={
                    "code_a": code_a,
                    "code_b": code_b,
                    "method": method,
                },
            )
            response.raise_for_status()
            data = response.json()

        return AiCompareResult(
            similarity=float(data["similarity"]),
            model=str(data["model"]),
            method=str(data["method"]),
            device=str(data["device"]),
            duration_ms=int(data["duration_ms"]),
        )
