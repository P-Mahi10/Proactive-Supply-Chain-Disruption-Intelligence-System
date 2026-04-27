# ── Stage 1: base image ──────────────────────────────────────────────────────
FROM python:3.11-slim AS base

# Keep Python output unbuffered so logs appear immediately in `docker logs`
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# /app       → project root  (simulation_model.py, calibration.json live here)
# /app/backend → makes `from app.x import y` work the same as running
#               `uvicorn app.main:app` from inside the backend/ directory
ENV PYTHONPATH=/app:/app/backend

WORKDIR /app

# ── Stage 2: install dependencies ────────────────────────────────────────────
FROM base AS deps

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ── Stage 3: final image ──────────────────────────────────────────────────────
FROM deps AS final

# Copy project root files (simulation_model.py, calibration.json, .env.example)
COPY simulation_model.py ./
COPY calibration.json    ./

# Copy backend package
COPY backend/ ./backend/

# .env is intentionally NOT copied — inject secrets via environment variables
# or a Docker secret at runtime (see README / docker-compose below).

# Expose the port uvicorn listens on
EXPOSE 8000

# Non-root user for security
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app
USER appuser

# `app.main:app` works because /app/backend is on PYTHONPATH,
# which mirrors running `uvicorn app.main:app` from inside backend/.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--workers", "1"]