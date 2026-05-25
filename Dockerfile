# --- ESTÁGIO 1: Build do Frontend (React) ---
FROM node:20-slim AS frontend-builder
WORKDIR /frontend-build
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# --- ESTÁGIO 2: Backend (Python) ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copia código do backend e migrações
COPY . .

# Copia o build do frontend para a pasta 'static' que o FastAPI serve
COPY --from=frontend-builder /frontend-build/dist ./static

EXPOSE 8000

# Comando unificado: Roda migrações e inicia a API
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port 8000"]
