# Backend

## Infrastructure

```powershell
docker compose up -d postgres redis
```

## API

```powershell
pip install -r back\requirements.txt
uvicorn back.api.main:app --host 127.0.0.1 --port 8000
```

## Worker

```powershell
python -m back.worker.run_worker
```

## Readiness

```powershell
curl http://127.0.0.1:8000/ready
```

`/ready` checks PostgreSQL, Redis, the AI service, and the C++ algorithms CLI.
