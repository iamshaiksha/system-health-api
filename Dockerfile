# ─── Stage 1: dependency builder ────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools needed for some C-extension packages
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ─── Stage 2: runtime image ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Labels (OCI standard)
LABEL org.opencontainers.image.title="system-health-api" \
      org.opencontainers.image.description="DAG-based system health check API" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.authors="Abdul Rahiman Shaik"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    PORT=8080

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
