# syntax=docker/dockerfile:1.7
# ---------- build stage ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build deps in a separate layer so the final image stays slim.
COPY requirements.txt ./
RUN pip wheel --wheel-dir /wheels -r requirements.txt

# ---------- runtime stage ----------
FROM python:3.12-slim AS runtime

# Create a non-root user to run the app.
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /home/app app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0

WORKDIR /app

# Install Python deps from the wheelhouse.
COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Copy application source.
COPY classifier.py main.py ./

# Hand over to the unprivileged user.
RUN chown -R app:app /app
USER app

EXPOSE 8000

# Liveness check hits the same /health endpoint exposed by FastAPI.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"

# 2 workers is a sensible default for a t3.micro / t3.small; tune via env.
CMD ["sh", "-c", "exec gunicorn main:app \
  --workers ${GUNICORN_WORKERS:-2} \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind ${HOST}:${PORT} \
  --access-logfile - \
  --error-logfile - \
  --timeout 60"]