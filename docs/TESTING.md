# Project Testing Guide

This document provides a complete local testing flow for the Customer Support Environment.

## 1. Prerequisites

- Python 3.10+
- pip or uv
- Docker Desktop (optional, for container checks)
- OpenEnv CLI installed

## 2. Install Dependencies

From the project root:

```bash
pip install -e .
pip install -r server/requirements.txt
pip install pytest pytest-cov
```

If you use uv:

```bash
uv sync
```

## 3. Run Unit and Integration Tests

Run all tests:

```bash
pytest -q tests
```

Run with coverage:

```bash
pytest --cov=. --cov-report=term-missing tests
```

Expected:
- All tests pass
- No import or validation errors

## 4. Validate OpenEnv Compliance

```bash
openenv validate
```

Expected:
- [OK] customerSupportEnv: Ready for multi-mode deployment

## 5. Start the API Server Locally

```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

In another terminal, verify health:

```bash
curl http://localhost:8000/health
```

Expected:
- HTTP 200 response

## 6. API Smoke Test

Reset:

```bash
curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d "{}"
```

Then step with a sample action:

```bash
curl -X POST http://localhost:8000/step -H "Content-Type: application/json" -d "{\"response\":\"Thank you for contacting support. I understand your concern and can help.\",\"action_type\":\"escalate\",\"amount\":null,\"reason\":\"Outside the normal window; manager review required.\"}"
```

Expected:
- Valid JSON response
- done is true
- reward is in range -1.0 to 1.0

## 7. Inference Script Test

Set environment variables first:

### PowerShell

```powershell
$env:API_BASE_URL="https://api.openai.com/v1"
$env:MODEL_NAME="gpt-4"
$env:OPENAI_API_KEY="your-key"
python inference.py
```

### Bash

```bash
export API_BASE_URL="https://api.openai.com/v1"
export MODEL_NAME="gpt-4"
export OPENAI_API_KEY="your-key"
python inference.py
```

Expected:
- Script runs all 3 tasks
- Prints task scores and weighted average

## 8. Docker Build and Runtime Test (Optional)

Build:

```bash
docker build -t customerSupportEnv-env:latest -f server/Dockerfile .
```

Run:

```bash
docker run -p 8000:8000 customerSupportEnv-env:latest
```

Health check:

```bash
curl http://localhost:8000/health
```

Expected:
- Container starts cleanly
- Health endpoint returns 200

## 9. Recommended Final Verification Order

1. pytest -q tests
2. openenv validate
3. local server + health check
4. inference.py
5. docker build/run (if Docker is available)

If all steps pass, the project is in strong submission-ready condition.