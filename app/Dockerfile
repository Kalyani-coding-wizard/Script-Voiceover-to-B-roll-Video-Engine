# =============================================================================
# Dockerfile — shared base for api and worker services
# =============================================================================
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/workspace/.cache/huggingface \
    TORCH_HOME=/workspace/.cache/torch

# System deps: FFmpeg, git, build tools (needed for openai-whisper / torch)
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        curl \
        build-essential \
        libpq-dev \
        fonts-noto-core \
        fonts-noto-extra \
        && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN mkdir -p /workspace/.cache/huggingface /workspace/.cache/torch

# Install Python dependencies first (layer-cached unless requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# ---------------------------------------------------------------------------
# api target — runs the FastAPI application
# ---------------------------------------------------------------------------
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------------------------------------------------------------------------
# worker target — runs the ARQ worker
# ---------------------------------------------------------------------------
FROM base AS worker
CMD ["python", "-m", "arq", "worker.main.WorkerSettings"]
