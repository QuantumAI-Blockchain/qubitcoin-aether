# ═══════════════════════════════════════════════════════════════════
# AIKGS Sidecar — Multi-stage Docker build
# Rust gRPC sidecar for Aether Incentivized Knowledge Growth System
# ═══════════════════════════════════════════════════════════════════

# ── Stage 1: Build ──────────────────────────────────────────────────
FROM rust:latest AS builder

WORKDIR /build

# Install protobuf compiler for tonic-build
RUN apt-get update && apt-get install -y protobuf-compiler && rm -rf /var/lib/apt/lists/*

# Copy manifests first for dependency caching
COPY Cargo.toml Cargo.lock* build.rs ./
COPY proto/ proto/

# Create dummy src to build dependencies
RUN mkdir src && \
    echo 'fn main() {}' > src/main.rs && \
    echo 'pub mod config; pub mod db; pub mod scorer; pub mod rewards; pub mod contributions; pub mod affiliates; pub mod bounties; pub mod unlocks; pub mod curation; pub mod vault; pub mod treasury;' > src/lib.rs && \
    for f in config db scorer rewards contributions affiliates bounties unlocks curation vault treasury; do echo '' > src/$f.rs; done && \
    cargo build --release 2>/dev/null || true

# Copy actual source and rebuild
COPY src/ src/
RUN cargo build --release

# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/aikgs-sidecar /usr/local/bin/aikgs-sidecar

# Non-root user
RUN useradd -m -s /bin/bash aikgs
USER aikgs
WORKDIR /home/aikgs

ENV AIKGS_GRPC_PORT=50052
ENV RUST_LOG=info

EXPOSE 50052

ENTRYPOINT ["aikgs-sidecar"]
