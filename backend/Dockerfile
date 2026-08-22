# ── Stage 1: Build frontend ──────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Build backend ───────────────────────────────────────────────
FROM python:3.11-slim AS backend-builder
WORKDIR /build/backend
COPY backend/pyproject.toml /build/
RUN pip install --no-cache-dir /build/

# ── Stage 3: Runtime image ───────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Runtime deps only (no build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-hin \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/ /app/backend/
COPY backend/pyproject.toml /app/
RUN pip install --no-cache-dir -e /app/

# Copy built frontend
COPY --from=frontend-builder /build/frontend/dist /app/frontend/dist

# Copy config
COPY config/ /app/config/

# Create data directories
RUN mkdir -p /data/uploads /data/db /data/exports

# Set working directory to backend so 'app' package is importable
WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
