# ============================================================================
# Qubitcoin Multi-Stage Docker Build
# Stage 1: Rust P2P daemon + Stratum Server build
# Stage 2: Aether Core + Security Core Rust/PyO3 module build
# Stage 3: Python node with compiled Rust binaries + modules
# ============================================================================

# ── Stage 1: Build Rust binaries (P2P + Stratum) ─────────────────────
FROM rust:latest AS rust-builder

RUN apt-get update && apt-get install -y \
    protobuf-compiler \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY rust-p2p/ ./rust-p2p/
COPY stratum-server/ ./stratum-server/

WORKDIR /build/rust-p2p
RUN cargo build --release

WORKDIR /build/stratum-server
RUN cargo build --release

# ── Stage 2: Build PyO3 modules (Aether Core + Security Core) ────────
# Use Python 3.12 base + install Rust to ensure wheel ABI matches production stage
FROM python:3.12-slim-bookworm AS aether-builder

RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

RUN pip install --no-cache-dir maturin>=1.7

WORKDIR /build
COPY aether-core/ ./aether-core/
COPY security-core/ ./security-core/

WORKDIR /build/aether-core
RUN maturin build --release --features extension-module --out /build/wheels

WORKDIR /build/security-core
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
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Install Rust-accelerated aether_core module
COPY --from=aether-builder /build/wheels/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# Copy Rust binaries from builder
COPY --from=rust-builder /build/rust-p2p/target/release/qubitcoin-p2p /usr/local/bin/qubitcoin-p2p
COPY --from=rust-builder /build/stratum-server/target/release/qbc-stratum /usr/local/bin/qbc-stratum
RUN chmod +x /usr/local/bin/qubitcoin-p2p /usr/local/bin/qbc-stratum

# Copy source code
COPY src/ ./src/
COPY sql/ ./sql/
COPY sql_new/ ./sql_new/
COPY contract_registry.json ./contract_registry.json

# Copy generated protobuf stubs for Rust P2P gRPC bridge
COPY rust-p2p/src/bridge/p2p_service_pb2.py ./rust-p2p/src/bridge/
COPY rust-p2p/src/bridge/p2p_service_pb2_grpc.py ./rust-p2p/src/bridge/

# Copy generated protobuf stubs for Rust Exchange gRPC bridge
COPY qbc-exchange/src/bridge/exchange_pb2.py ./qbc-exchange/src/bridge/
COPY qbc-exchange/src/bridge/exchange_pb2_grpc.py ./qbc-exchange/src/bridge/

# Create data directories
RUN mkdir -p /app/data /app/logs && \
    chown -R qbc:qbc /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Expose ports: RPC, P2P, gRPC, Stratum
EXPOSE 5000 4001 50051 3333

# Switch to non-root user
USER qbc

WORKDIR /app/src

# Default: run the node
CMD ["python3", "run_node.py"]
