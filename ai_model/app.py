from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Literal

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoTokenizer

MODULE_DIR = Path(__file__).resolve().parent
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from graphcodebert_dfg_encoder import get_embedding_no_dfg, get_embedding_with_dfg


DEFAULT_MODEL_NAME = "microsoft/graphcodebert-base"
MODEL_NAME = os.getenv("ANTIPLAG_AI_MODEL", DEFAULT_MODEL_NAME)

app = FastAPI(title="Antiplag AI Service", version="0.1.0")

_model_lock = asyncio.Lock()
_tokenizer = None
_model = None
_device: torch.device | None = None


class CompareRequest(BaseModel):
    code_a: str = Field(..., min_length=1)
    code_b: str = Field(..., min_length=1)
    method: Literal["dfg", "no_dfg"] = "dfg"


class CompareResponse(BaseModel):
    similarity: float
    model: str
    method: str
    device: str
    duration_ms: int


class HealthResponse(BaseModel):
    status: str
    model: str
    loaded: bool
    device: str | None


def _load_model() -> None:
    global _tokenizer, _model, _device

    if _model is not None and _tokenizer is not None and _device is not None:
        return

    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    _model = AutoModel.from_pretrained(MODEL_NAME).to(_device).eval()


@app.on_event("startup")
def startup() -> None:
    if os.getenv("ANTIPLAG_AI_LOAD_ON_STARTUP", "1") == "1":
        _load_model()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        model=MODEL_NAME,
        loaded=_model is not None and _tokenizer is not None,
        device=str(_device) if _device is not None else None,
    )


@app.post("/api/v1/compare", response_model=CompareResponse)
async def compare(payload: CompareRequest) -> CompareResponse:
    try:
        _load_model()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"AI model is not available: {exc}") from exc

    started = time.perf_counter()

    async with _model_lock:
        try:
            assert _model is not None
            assert _tokenizer is not None
            assert _device is not None

            if payload.method == "dfg":
                emb_a = get_embedding_with_dfg(payload.code_a, _model, _tokenizer, _device)
                emb_b = get_embedding_with_dfg(payload.code_b, _model, _tokenizer, _device)
            else:
                emb_a = get_embedding_no_dfg(payload.code_a, _model, _tokenizer, _device)
                emb_b = get_embedding_no_dfg(payload.code_b, _model, _tokenizer, _device)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"AI comparison failed: {exc}") from exc

    similarity = float(np.dot(emb_a, emb_b))
    duration_ms = int((time.perf_counter() - started) * 1000)

    return CompareResponse(
        similarity=max(0.0, min(1.0, similarity)),
        model=MODEL_NAME,
        method=payload.method,
        device=str(_device),
        duration_ms=duration_ms,
    )
