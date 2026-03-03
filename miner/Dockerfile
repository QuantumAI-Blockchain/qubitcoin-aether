# ═══════════════════════════════════════════════════════════════════════
# Qubitcoin VQE Mining Client — Docker Image
# ═══════════════════════════════════════════════════════════════════════
#
# Multi-stage build:
#   Stage 1: Install Python deps (cached layer)
#   Stage 2: Copy app code (fast rebuilds)
#
# Usage:
#   docker build -t qbc-miner -f miner/Dockerfile .
#   docker run --rm -e SUBSTRATE_WS_URL=ws://host:9944 qbc-miner
#
# GPU support:
#   docker run --rm --gpus all -e USE_GPU_AER=true qbc-miner
# ═══════════════════════════════════════════════════════════════════════

FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps for numpy/scipy wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ gfortran libopenblas-dev \
    && rm -rf /var/lib/apt/lists/*

COPY miner/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Production stage ────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Qubitcoin VQE Miner"
LABEL org.opencontainers.image.description="VQE mining client for Qubitcoin Proof-of-SUSY-Alignment"
LABEL org.opencontainers.image.source="https://github.com/BlockArtica/Qubitcoin"

# Runtime deps only (libopenblas for numpy/scipy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libopenblas0 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy miner source
COPY miner/ ./miner/

# Environment defaults
ENV SUBSTRATE_WS_URL=ws://substrate-node:9944
ENV MINER_SEED=//Alice
ENV NUM_QUBITS=4
ENV VQE_REPS=2
ENV VQE_MAXITER=200
ENV MAX_MINING_ATTEMPTS=50
ENV USE_GPU_AER=false
ENV USE_SIMULATOR=false
ENV LOG_LEVEL=INFO

# Health check: verify Python + Qiskit import
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "from miner.vqe_miner import VqeMiner; print('ok')" || exit 1

ENTRYPOINT ["python", "-m", "miner"]
