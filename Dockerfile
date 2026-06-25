# ── Base image ─────────────────────────────────────────
FROM python:3.12-slim

# ── Set environment variables ──────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# ── Set working directory ──────────────────────────────
WORKDIR /app

# ── Install system dependencies ────────────────────────
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    net-tools \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

# ── Install Python dependencies ────────────────────────
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Copy project files ─────────────────────────────────
COPY . .

# ── Create logs directory ──────────────────────────────
RUN mkdir -p /app/logs && \
    touch /app/logs/error.log


# ── Expose port ────────────────────────────────────────
# ── Install netcat for entrypoint health check ─────────
RUN apt-get update && apt-get install -y netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# ── Copy and set entrypoint ────────────────────────────
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]