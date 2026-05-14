FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY features/ ./features/
COPY tests/ ./tests/

# Default to mock mode so the container starts without requiring API keys
ENV KANIT_AI_MODE=nvidia
ENV KANIT_ALLOW_MOCK=false
ENV KANIT_DB_PATH=/data/kanit.sqlite3
ENV KANIT_MAX_UPLOAD_BYTES=5242880

# Persist SQLite on a named volume: docker run -v kanit_data:/data ...
RUN mkdir -p /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "features.main:app", "--host", "0.0.0.0", "--port", "8000"]
