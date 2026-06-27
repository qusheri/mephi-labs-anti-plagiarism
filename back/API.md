# Backend API

Run from the project root:

```bash
pip install -r back/requirements.txt
docker compose up -d postgres redis
uvicorn back.api.main:app --host 127.0.0.1 --port 8000
```

Run the worker in a separate terminal:

```bash
python -m back.worker.run_worker
```

Default infrastructure URLs:

```text
ANTIPLAG_DATABASE_URL=postgresql+psycopg://antiplag:antiplag@127.0.0.1:55432/antiplag
ANTIPLAG_REDIS_URL=redis://127.0.0.1:6379/0
ANTIPLAG_QUEUE_NAME=antiplag-checks
```

For AI comparisons, run the AI service separately:

```bash
cd ai_model
pip install -r requirements.txt
uvicorn app:app --host 127.0.0.1 --port 8001
```

## Health

```http
GET /health
```

Response:

```json
{"status": "ok"}
```

## Create Check

```http
POST /api/v1/checks
Content-Type: multipart/form-data
```

Fields:

- `file`: source file or ZIP archive.
- `title`: lab title.
- `course`: optional course name.

Response:

```json
{
  "task_id": "6f4f08f3-28a6-437c-9a68-3d7a76194886",
  "status": "queued"
}
```

After creation, the backend starts background processing:

1. Saves the uploaded file.
2. Creates a row in PostgreSQL.
3. Enqueues `task_id` into Redis/RQ.
4. Worker finds previous submissions from the same course.
5. Worker calls C++ algorithms and the AI service.
6. Worker saves the report into PostgreSQL.
7. Worker sets task status to `done` or `failed`.

Frontend example:

```js
const result = await window.antiplagApi.createCheck({
  title: 'Лабораторная работа №5',
  course: 'Семантические технологии',
  file,
});
```

## Check Status

```http
GET /api/v1/checks/{task_id}
```

Response:

```json
{
  "task_id": "6f4f08f3-28a6-437c-9a68-3d7a76194886",
  "status": "queued",
  "title": "Лабораторная работа №5",
  "course": "Семантические технологии",
  "original_filename": "lab_05.cpp",
  "created_at": "2026-06-27T12:40:20.000000+00:00",
  "updated_at": "2026-06-27T12:40:20.000000+00:00",
  "error_message": null
}
```

Statuses:

- `queued`
- `running`
- `done`
- `failed`

Frontend polling example:

```js
const task = await window.antiplagApi.getCheck(taskId);
```

## List Checks

```http
GET /api/v1/checks?limit=50&offset=0
```

Response:

```json
{
  "items": []
}
```

## Get Report

```http
GET /api/v1/checks/{task_id}/report
```

If the report is not ready, the API returns `409 Conflict`.

Successful response:

```json
{
  "task_id": "6f4f08f3-28a6-437c-9a68-3d7a76194886",
  "status": "done",
  "report": {
    "originality_score": 0.82,
    "plagiarism_score": 0.18,
    "classic_score": 0.15,
    "ai_score": 0.24,
    "score_formula": {
      "classic_weight": 0.65,
      "ai_weight": 0.35
    },
    "matches": [
      {
        "task_id": "previous-task-id",
        "title": "Лабораторная работа №4",
        "combined_score": 0.18,
        "classic_score": 0.15,
        "ai_score": 0.24,
        "classic_result": {
          "algorithm": "combined_classic",
          "score": 0.15,
          "containment": 0.20,
          "component_scores": {
            "token_ngram": 0.10,
            "winnowing": 0.12,
            "greedy_string_tiling": 0.18,
            "structural_skeleton": 0.22
          },
          "fragments": []
        },
        "ai_result": {
          "score": 0.24,
          "model": "microsoft/graphcodebert-base",
          "method": "dfg",
          "device": "cuda",
          "duration_ms": 350
        }
      }
    ]
  }
}
```

## Direct AI Similarity

This endpoint lets the frontend call AI through the backend without talking to `ai_model` directly.

```http
POST /api/v1/similarity
Content-Type: multipart/form-data
```

Fields:

- `file_a`: first source file.
- `file_b`: second source file.
- `method`: `dfg` or `no_dfg`, default is `dfg`.

Response:

```json
{
  "plagiarism_score": 0.42,
  "classic_score": 0.38,
  "ai_score": 0.49,
  "classic_result": {
    "algorithm": "combined_classic",
    "score": 0.38,
    "containment": 0.44,
    "component_scores": {},
    "fragments": []
  },
  "ai_result": {
    "score": 0.49,
    "model": "microsoft/graphcodebert-base",
    "method": "dfg",
    "device": "cuda",
    "duration_ms": 350
  },
  "score_formula": {
    "classic_weight": 0.65,
    "ai_weight": 0.35
  }
}
```

Frontend example:

```js
const result = await window.antiplagApi.compareFiles({
  fileA,
  fileB,
  method: 'dfg',
});
```
