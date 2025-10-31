# Dockerfile (Python backend + Streamlit frontend, dirs: app/, static/, ui/)

# 1) Build stage: prebuild wheels for faster installs
FROM python:3.11-slim AS builder
WORKDIR /build
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-deps --wheel-dir /wheels -r requirements.txt

# 2) Runtime stage
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
RUN adduser --disabled-password --gecos "" appuser
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt && rm -rf /wheels

# copy only needed dirs
COPY app ./app
COPY ui ./ui
COPY static ./static

USER appuser
EXPOSE 8000 8501
CMD ["python", "-V"]
