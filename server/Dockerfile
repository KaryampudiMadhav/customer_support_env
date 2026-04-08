FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY . /app

RUN apt-get update \
    && pip install --no-cache-dir -U pip \
    && pip install --no-cache-dir -r server/requirements.txt

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
