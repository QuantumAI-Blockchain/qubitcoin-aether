# ═══════════════════════════════════════════════════════════════════════
# Qubitcoin Aether Service — Standalone AGI Engine
# ═══════════════════════════════════════════════════════════════════════
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ && rm -rf /var/lib/apt/lists/*
COPY aether-service/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
LABEL org.opencontainers.image.title="Qubitcoin Aether Service"
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy Aether service files
COPY aether-service/ ./

# Copy the qubitcoin source package (Aether modules live in src/qubitcoin/aether/)
COPY src/qubitcoin/ ./qubitcoin/

ENV AETHER_HOST=0.0.0.0
ENV AETHER_PORT=5001
ENV SUBSTRATE_WS_URL=ws://substrate-node:9944
ENV DATABASE_URL=postgresql://root@cockroachdb:26257/qbc?sslmode=disable
ENV LOG_LEVEL=INFO

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:5001/health'); assert r.status_code == 200" || exit 1

CMD ["python", "main.py"]
