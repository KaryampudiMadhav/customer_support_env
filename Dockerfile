FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app


RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && pip install uv openenv \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

RUN uv sync --frozen --no-install-project --no-dev
EXPOSE 8000

CMD ["uv", "run", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
