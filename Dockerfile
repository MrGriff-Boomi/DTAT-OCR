# =============================================================================
# DTAT OCR (Ducktape and Twine OCR) - Docker Image
# =============================================================================
# Multi-stage build:
# 1. Download model weights (cached layer)
# 2. Build final image with code + model + Web UI
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Download model weights
# -----------------------------------------------------------------------------
FROM python:3.12-slim AS model-downloader

# Install minimal dependencies for downloading
RUN pip install --no-cache-dir huggingface_hub transformers torch --index-url https://download.pytorch.org/whl/cpu

# Download model weights to cache directory
ENV HF_HOME=/model-cache
RUN python -c "
from huggingface_hub import snapshot_download
snapshot_download('lightonai/LightOnOCR-1B-1025', local_dir='/model-cache/lightonai/LightOnOCR-1B-1025')
print('Model downloaded successfully')
"

# -----------------------------------------------------------------------------
# Stage 2: Final image
# -----------------------------------------------------------------------------
FROM python:3.12-slim

# Labels
LABEL maintainer="your-email@example.com"
LABEL description="DTAT OCR - Swiss Army Knife document processor with OCR fallback"
LABEL version="1.0.0"

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HF_HOME=/app/model-cache
ENV HF_HUB_OFFLINE=1

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # For PyMuPDF
    libmupdf-dev \
    mupdf-tools \
    # For image processing
    libjpeg-dev \
    libpng-dev \
    # General
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy model weights from downloader stage
COPY --from=model-downloader /model-cache /app/model-cache

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY config.py .
COPY database.py .
COPY extraction_pipeline.py .
COPY worker.py .
COPY api.py .

# Copy Web UI templates
COPY templates/ ./templates/

# Create directories
RUN mkdir -p /app/data /app/temp

# Volume for persistent data (SQLite DB)
VOLUME /app/data

# Environment variables (can be overridden)
ENV DATABASE_URL=sqlite:////app/data/documents.db
ENV OCR_OFFLINE_MODE=true
ENV ENABLE_TEXTRACT=false

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose API port
EXPOSE 8000

# Default command - run API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
