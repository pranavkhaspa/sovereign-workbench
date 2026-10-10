# Build from the repository root: docker build -f backend/Dockerfile .
# Multi-stage: build wheels, then a slim runtime. Runs fully offline at runtime.
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml backend/README.md ./
COPY backend/src ./src
RUN pip install --upgrade pip build \
    && pip wheel --wheel-dir /wheels ".[ocr]"

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# tesseract for OCR; curl for healthcheck. No compilers in the runtime image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr curl libgomp1 poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-index --find-links /wheels "sovereign-workbench[ocr]" \
    && rm -rf /wheels

# Non-root runtime user.
RUN useradd --create-home --uid 10001 workbench \
    && mkdir -p /app/data && chown -R workbench:workbench /app
USER workbench

ENV AIRGAP=true \
    HARDWARE_TIER=min \
    MODEL_REGISTRY_PATH=/app/models/models.toml \
    DATABASE_URL=sqlite:////app/data/workbench.sqlite3
COPY --chown=workbench:workbench models /app/models

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "sovereign_workbench.main:app", "--host", "0.0.0.0", "--port", "8000"]
