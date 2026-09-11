FROM python:3.11-slim

# opencv-python-headless still needs libGL/glib at runtime.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so a source edit does not invalidate the wheel cache.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production

ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import os,urllib.request;urllib.request.urlopen('http://localhost:%s/api/v1/health' % os.environ.get('PORT','8000'))"

# Shell form so $PORT expands: managed hosts (Render, Fly, Cloud Run) assign the
# port at runtime and health-check that exact one. A hardcoded port fails there.
# One worker on purpose - the OCR pass is memory-hungry, and a second worker on a
# 512 MB free instance gets the whole service OOM-killed mid-scan.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --timeout-keep-alive 65
