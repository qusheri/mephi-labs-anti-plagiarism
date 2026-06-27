# AI service

Internal HTTP service for the backend worker. The frontend must not call it directly.

## Install

```bash
cd ai_model
pip install -r requirements.txt
```

By default, `graphcodebert_dfg_encoder.py` uses:

- `HF_HOME=Q:\hf_cache`
- `TRANSFORMERS_OFFLINE=1`

Override them before startup if the model should be downloaded or cached elsewhere:

```bash
set TRANSFORMERS_OFFLINE=0
set HF_HOME=D:\hf_cache
```

## Run

```bash
cd ai_model
uvicorn app:app --host 127.0.0.1 --port 8001
```

Health check:

```bash
curl http://127.0.0.1:8001/health
```

Compare two C++ snippets:

```bash
curl -X POST http://127.0.0.1:8001/api/v1/compare ^
  -H "Content-Type: application/json" ^
  -d "{\"code_a\":\"int main(){return 0;}\",\"code_b\":\"int main(){return 1;}\",\"method\":\"dfg\"}"
```

Response:

```json
{
  "similarity": 0.82,
  "model": "microsoft/graphcodebert-base",
  "method": "dfg",
  "device": "cuda",
  "duration_ms": 350
}
```

## Backend usage

The backend worker can call the service through `back/worker/ai_client.py`.

```python
from back.worker.ai_client import AiServiceClient

client = AiServiceClient("http://127.0.0.1:8001")
result = await client.compare(code_a, code_b, method="dfg")
print(result.similarity)
```
