# Stage 1: Build stage
FROM python:3.12-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Enable bytecode compilation
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install runtime deps only (lean venv, no dev tools)
RUN uv sync --frozen --no-install-project --no-dev

# Build MkDocs site using uvx (isolated, does not touch .venv)
COPY mkdocs.yml ./
COPY docs ./docs
RUN uvx --with mkdocs-material mkdocs build

# Stage 2: Final runtime stage
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy virtual environment from builder (runtime deps only)
COPY --from=builder /app/.venv /app/.venv

# Copy built MkDocs static site
COPY --from=builder /app/site /app/site

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Copy source code and other necessary files
COPY src /app/src
COPY assets /app/assets
COPY server_run.py /app/server_run.py

# Download necessary files (models, etc.) during build
RUN python -m src.agents.session download-files

# Expose the API port
EXPOSE 8000

# Default command - can be overridden in docker-compose
CMD ["python", "server_run.py"]
