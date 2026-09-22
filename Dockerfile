# Backend image, shared by the API, the worker and the migration job.
#
# One image for all three on purpose: a worker running different code than the
# API is a failure mode that only shows up in production.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libpq for psycopg2; the rest are what OpenCV and Pillow link against.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first, so a source change does not invalidate the layer.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY truthshield/ ./truthshield/
COPY migrations/ ./migrations/
COPY alembic.ini .

# Non-root. A container that gets popped should not also be root.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/.uploads /app/.model_cache \
    && chown -R app:app /app
USER app

EXPOSE 8000
CMD ["uvicorn", "truthshield.main:app", "--host", "0.0.0.0", "--port", "8000"]
