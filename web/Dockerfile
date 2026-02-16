# ── Stage 1: Build React frontend ────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /build
COPY web/frontend/package.json web/frontend/package-lock.json* ./
RUN npm install
COPY web/frontend/ .
RUN npm run build

# ── Stage 2: Python API server ───────────────────────
FROM python:3.11-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y gcc postgresql-client && rm -rf /var/lib/apt/lists/*

# Python deps — install both bot and web requirements
COPY requirements.txt ./requirements-bot.txt
COPY web/requirements.txt ./requirements-web.txt
RUN pip install --no-cache-dir -r requirements-bot.txt -r requirements-web.txt

# Copy full project (needed for database/, services/, config, etc.)
COPY . .

# Copy built frontend into web/static/
COPY --from=frontend-build /static web/static/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

CMD ["uvicorn", "web.main:app", "--host", "0.0.0.0", "--port", "8000"]
