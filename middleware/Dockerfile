# Informatics tier image (SRS FR-DAT-001). Python 3.11 per SRS FR-DAT-001.
# Build context: ./middleware (see docker-compose.yml).
# The Pulse physiology engine is not in this image. See middleware/Dockerfile.pulse.
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd -m -u 1000 surgitwin && chown -R surgitwin:surgitwin /app
USER surgitwin

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
