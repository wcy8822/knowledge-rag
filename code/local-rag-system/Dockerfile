# Local RAG System v1.1.0 - Production Dockerfile
# Multi-stage build for optimized image size and security

FROM python:3.9-slim as builder

# Set working directory
WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Create wheels for dependencies
RUN pip install --no-cache-dir --wheel --no-binary :all: -r requirements.txt

# Final production stage
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOME=/app \
    PORT=8000

# Set working directory
WORKDIR ${APP_HOME}

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder
COPY --from=builder /build/wheels /wheels

# Install Python dependencies from wheels
RUN pip install --no-cache /wheels/*

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY VERSION ./
COPY CHANGELOG.md ./
COPY *.json ./

# Create data directories
RUN mkdir -p data/chroma logs test_reports

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser ${APP_HOME}
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Expose port
EXPOSE ${PORT}

# Labels for metadata
LABEL maintainer="Local RAG System Team" \
      version="1.1.0" \
      description="Local RAG System with Vectorization Support" \
      org.opencontainers.image.source="https://github.com/organization/local-rag-system"

# Run API server
CMD ["python", "-m", "src.serve.app"]
