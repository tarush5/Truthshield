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

# Bind whatever port the platform assigns, defaulting to 8000 locally.
#
# Render, Railway, Fly and Cloud Run all inject $PORT and route to it; a
# container that hardcodes a port fails their health check. On Render the
# consequence is quiet and expensive to diagnose: the failed deploy is
# rolled back and the *previous* image keeps serving, so the service looks
# healthy while running whatever code last deployed successfully.
#
# Shell form is required here -- exec form does not expand environment
# variables -- and `exec` keeps uvicorn as PID 1 so SIGTERM still reaches it
# and shutdown stays graceful.
CMD ["sh", "-c", "exec uvicorn truthshield.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
