FROM node:24-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AI_AGENT_HOST=0.0.0.0 \
    AI_AGENT_PORT=8080

WORKDIR /app

COPY requirements.txt requirements-chat.txt ./
RUN python -m pip install --no-cache-dir \
    -r requirements.txt \
    -r requirements-chat.txt

COPY app ./app
COPY frontend/index.html ./frontend/index.html
COPY --from=frontend-build /frontend/dist ./frontend/dist
COPY main.py .

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8080 8081

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/live', timeout=2)" || exit 1

CMD ["python", "-m", "app.api.server_main"]
