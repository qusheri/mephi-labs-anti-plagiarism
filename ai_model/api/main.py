"""
GraphCodeBERT + DFG — REST API для детектирования плагиата C++ кода.

Запуск:
    pip install fastapi uvicorn
    uvicorn ai_model.api.main:app --host 0.0.0.0 --port 8000

Или из папки ai_model/:
    uvicorn api.main:app --host 0.0.0.0 --port 8000

Эндпоинты:
    POST /similarity   — сравнить два куска кода
    GET  /health       — проверка что сервер жив
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel

from graphcodebert_dfg_encoder import get_embedding_with_dfg, get_embedding_no_dfg

MODEL_NAME = "microsoft/graphcodebert-base"
PLAGIARISM_THRESHOLD = 0.80  # порог cosine similarity

# ── глобальное состояние ──────────────────────────────────────────────────────
_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {MODEL_NAME} on {device}...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()
    _state["model"] = model
    _state["tokenizer"] = tokenizer
    _state["device"] = device
    print("Model ready.")
    yield
    _state.clear()


app = FastAPI(
    title="C++ Plagiarism Detector",
    description="GraphCodeBERT + DFG encoder для детектирования плагиата C++ кода",
    version="1.0.0",
    lifespan=lifespan,
)


# ── схемы ─────────────────────────────────────────────────────────────────────

class SimilarityRequest(BaseModel):
    code_a: str
    code_b: str
    use_dfg: bool = True  # False = без DFG (быстрее, менее точно)

    model_config = {
        "json_schema_extra": {
            "example": {
                "code_a": "int add(int a, int b) { return a + b; }",
                "code_b": "int sum(int x, int y) { return x + y; }",
                "use_dfg": True
            }
        }
    }


class SimilarityResponse(BaseModel):
    similarity: float
    is_plagiarism: bool
    threshold: float
    method: str


# ── эндпоинты ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": str(_state.get("device", "not loaded")),
    }


@app.post("/similarity", response_model=SimilarityResponse)
def similarity(req: SimilarityRequest):
    model     = _state.get("model")
    tokenizer = _state.get("tokenizer")
    device    = _state.get("device")

    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        if req.use_dfg:
            emb_a = get_embedding_with_dfg(req.code_a, model, tokenizer, device)
            emb_b = get_embedding_with_dfg(req.code_b, model, tokenizer, device)
            method = "GraphCodeBERT + DFG"
        else:
            emb_a = get_embedding_no_dfg(req.code_a, model, tokenizer, device)
            emb_b = get_embedding_no_dfg(req.code_b, model, tokenizer, device)
            method = "GraphCodeBERT (no DFG)"
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Encoding error: {e}")

    sim = float(np.dot(emb_a, emb_b))

    return SimilarityResponse(
        similarity=round(sim, 4),
        is_plagiarism=sim >= PLAGIARISM_THRESHOLD,
        threshold=PLAGIARISM_THRESHOLD,
        method=method,
    )
