# ============================================================================
# Qubitcoin Multi-Stage Docker Build
# Stage 1: Rust P2P daemon build
# Stage 2: Aether Core Rust/PyO3 module build
# Stage 3: Python node with compiled Rust binaries + aether_core
# ============================================================================

# ── Stage 1: Build Rust P2P daemon ──────────────────────────────────────
FROM rust:1.85-slim-bookworm AS rust-builder

RUN apt-get update && apt-get install -y \
    protobuf-compiler \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY rust-p2p/ ./rust-p2p/

WORKDIR /build/rust-p2p
RUN cargo build --release

# ── Stage 2: Build Aether Core Rust module (PyO3) ─────────────────────
FROM rust:1.85-slim-bookworm AS aether-builder

RUN apt-get update && apt-get install -y \
    python3-dev \
    python3-pip \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --break-system-packages maturin>=1.7

WORKDIR /build
COPY aether-core/ ./aether-core/

WORKDIR /build/aether-core
RUN maturin build --release --features extension-module --out /build/wheels

# ── Stage 3: Python application ─────────────────────────────────────────
FROM python:3.12-slim-bookworm AS production

LABEL maintainer="Qubitcoin Team <dev@qbc.network>"
LABEL description="Qubitcoin Node — Quantum-Secured Layer 1 Blockchain"
LABEL version="1.0.0"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r qbc && useradd -r -g qbc -m -d /home/qbc qbc

WORKDIR /app

# Copy and install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Rust-accelerated aether_core module
COPY --from=aether-builder /build/wheels/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy Rust P2P binary from builder
COPY --from=rust-builder /build/rust-p2p/target/release/qubitcoin-p2p /usr/local/bin/qubitcoin-p2p
RUN chmod +x /usr/local/bin/qubitcoin-p2p

# Copy source code
COPY src/ ./src/
COPY sql/ ./sql/
COPY sql_new/ ./sql_new/

# Copy generated protobuf stubs for Rust P2P gRPC bridge
COPY rust-p2p/src/bridge/p2p_service_pb2.py ./rust-p2p/src/bridge/
COPY rust-p2p/src/bridge/p2p_service_pb2_grpc.py ./rust-p2p/src/bridge/

# Create data directories
RUN mkdir -p /app/data /app/logs && \
    chown -R qbc:qbc /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose ports: RPC, P2P, gRPC
EXPOSE 5000 4001 50051

# Switch to non-root user
USER qbc

WORKDIR /app/src

# Default: run the node
CMD ["python3", "run_node.py"]
