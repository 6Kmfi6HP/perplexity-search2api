# ==============================================================================
# Build Stage: Compile dependencies and setup virtualenv
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install project dependencies
COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir .

# ==============================================================================
# Runtime Stage: Minimal production image
# ==============================================================================
FROM python:3.12-slim AS runtime

# Metadata labels
LABEL maintainer="Perplexity Search2API Contributors"
LABEL org.opencontainers.image.title="perplexity-search2api"
LABEL org.opencontainers.image.description="Perplexity Pro search and reasoning gateway with OpenAI-compatible API"
LABEL org.opencontainers.image.source="https://github.com/6Kmfi6HP/perplexity-search2api"
LABEL org.opencontainers.image.licenses="MIT"

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOST=0.0.0.0 \
    PORT=8000 \
    HOME=/home/appuser

# Setup non-root user and persistent directory
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -d /home/appuser -m -s /bin/bash appuser && \
    mkdir -p /app /app/data /home/appuser && \
    chown -R appuser:appuser /app /app/data /home/appuser

WORKDIR /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=appuser:appuser /opt/venv /opt/venv

# Copy application source files
COPY --chown=appuser:appuser server.py perplexity_auth.py perplexity_client.py perplexity_config.py cli.py pyproject.toml README.md ./

# Switch to unprivileged user
USER appuser

# Expose service port
EXPOSE 8000

# Health check via FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health')" || exit 1

# Start the gateway server
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
