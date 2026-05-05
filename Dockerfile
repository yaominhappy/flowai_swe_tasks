# ── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Copy dependency manifest only to leverage Docker layer cache.
COPY requirements.txt .

# Install into a local prefix so the runtime stage can copy them cleanly.
RUN pip install --no-cache-dir --prefix=/install \
    --index-url https://pypi.org/simple/ \
    --trusted-host pypi.org \
    --trusted-host files.pythonhosted.org \
    -r requirements.txt

# ── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Create a non-root user for the application process.
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Install the pre-built dependencies from the builder stage.
COPY --from=builder /install /usr/local

# Writable directory for the SQLite database file.
RUN mkdir -p /data && chown appuser:appgroup /data

WORKDIR /app

# Copy application source.
COPY app/ ./app/

USER appuser

ENV DATABASE_URL="sqlite+aiosqlite:////data/urlshort.db"
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
