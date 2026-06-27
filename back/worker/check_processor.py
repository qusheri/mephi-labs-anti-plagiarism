from __future__ import annotations

from typing import Any

import httpx

from back.api import repository
from back.api.config import AI_SCORE_WEIGHT, CLASSIC_SCORE_WEIGHT, MAX_AI_CANDIDATES
from back.worker.ai_client import AiServiceClient
from back.worker.classic_client import ClassicAlgorithmClient
from back.worker.source_reader import read_source_text


async def process_check(task_id: str) -> None:
    task = repository.get_check(task_id)
    if task is None:
        return

    repository.set_check_status(task_id, "running")

    try:
        code = read_source_text(task["stored_path"])
        candidates = repository.list_candidate_checks(
            task_id=task_id,
            course=task["course"],
            limit=MAX_AI_CANDIDATES,
        )

        if not candidates:
            repository.save_report(task_id, _empty_report())
            return

        ai_client = AiServiceClient()
        classic_client = ClassicAlgorithmClient()
        matches: list[dict[str, Any]] = []

        for candidate in candidates:
            candidate_code = read_source_text(candidate["stored_path"])
            if not candidate_code.strip():
                continue

            classic_result = classic_client.compare_texts(code, candidate_code)
            ai_result = await ai_client.compare(code, candidate_code, method="dfg")
            combined_score = _weighted_score(classic_result.score, ai_result.similarity)
            matches.append(
                {
                    "task_id": candidate["id"],
                    "title": candidate["title"],
                    "course": candidate["course"],
                    "filename": candidate["original_filename"],
                    "combined_score": combined_score,
                    "classic_score": classic_result.score,
                    "classic_result": {
                        "algorithm": classic_result.algorithm,
                        "score": classic_result.score,
                        "containment": classic_result.containment,
                        "component_scores": classic_result.component_scores,
                        "fragments": classic_result.fragments,
                        "warnings": classic_result.warnings,
                    },
                    "ai_score": ai_result.similarity,
                    "ai_result": {
                        "score": ai_result.similarity,
                        "model": ai_result.model,
                        "method": ai_result.method,
                        "device": ai_result.device,
                        "duration_ms": ai_result.duration_ms,
                    },
                }
            )

        matches.sort(key=lambda item: item["combined_score"], reverse=True)
        best_match = matches[0] if matches else None
        best_ai_score = best_match["ai_score"] if best_match else 0.0
        best_classic_score = best_match["classic_score"] if best_match else 0.0
        plagiarism_score = best_match["combined_score"] if best_match else 0.0
        originality_score = max(0.0, min(1.0, 1.0 - plagiarism_score))

        repository.save_report(
            task_id,
            {
                "originality_score": originality_score,
                "plagiarism_score": plagiarism_score,
                "classic_score": best_classic_score,
                "ai_score": best_ai_score,
                "score_formula": {
                    "classic_weight": CLASSIC_SCORE_WEIGHT,
                    "ai_weight": AI_SCORE_WEIGHT,
                },
                "matches": matches,
            },
        )
    except httpx.HTTPError as exc:
        repository.set_check_status(task_id, "failed", f"AI service request failed: {exc}")
    except Exception as exc:
        repository.set_check_status(task_id, "failed", str(exc))


def _empty_report() -> dict[str, Any]:
    return {
        "originality_score": 1.0,
        "plagiarism_score": 0.0,
        "classic_score": None,
        "classic_result": None,
        "ai_score": None,
        "ai_result": None,
        "score_formula": {
            "classic_weight": CLASSIC_SCORE_WEIGHT,
            "ai_weight": AI_SCORE_WEIGHT,
        },
        "matches": [],
        "note": "No previous submissions were found for comparison.",
    }


def _weighted_score(classic_score: float, ai_score: float) -> float:
    total_weight = CLASSIC_SCORE_WEIGHT + AI_SCORE_WEIGHT
    if total_weight <= 0:
        return 0.0
    value = (CLASSIC_SCORE_WEIGHT * classic_score + AI_SCORE_WEIGHT * ai_score) / total_weight
    return max(0.0, min(1.0, value))
