# Qubitcoin Substrate Node — Multi-stage Docker build
# Stage 1: Build the node binary
# Stage 2: Slim runtime image

FROM rust:1.93-bookworm AS builder

# Install system dependencies for Substrate
RUN apt-get update && apt-get install -y \
    cmake \
    pkg-config \
    libssl-dev \
    protobuf-compiler \
    clang \
    libclang-dev \
    && rm -rf /var/lib/apt/lists/*

# Install WASM targets
RUN rustup target add wasm32-unknown-unknown wasm32v1-none
RUN rustup component add rust-src

WORKDIR /build

# Copy manifests first for Docker layer caching
COPY Cargo.toml Cargo.lock ./
COPY node/Cargo.toml node/Cargo.toml
COPY node/build.rs node/build.rs
COPY runtime/Cargo.toml runtime/Cargo.toml
COPY runtime/build.rs runtime/build.rs
COPY primitives/Cargo.toml primitives/Cargo.toml
COPY pallets/qbc-utxo/Cargo.toml pallets/qbc-utxo/Cargo.toml
COPY pallets/qbc-consensus/Cargo.toml pallets/qbc-consensus/Cargo.toml
COPY pallets/qbc-dilithium/Cargo.toml pallets/qbc-dilithium/Cargo.toml
COPY pallets/qbc-economics/Cargo.toml pallets/qbc-economics/Cargo.toml
COPY pallets/qbc-qvm-anchor/Cargo.toml pallets/qbc-qvm-anchor/Cargo.toml
COPY pallets/qbc-aether-anchor/Cargo.toml pallets/qbc-aether-anchor/Cargo.toml
COPY pallets/qbc-reversibility/Cargo.toml pallets/qbc-reversibility/Cargo.toml
COPY crypto/kyber-transport/Cargo.toml crypto/kyber-transport/Cargo.toml

# Create dummy source files for dependency caching
RUN mkdir -p node/src runtime/src primitives/src \
    pallets/qbc-utxo/src pallets/qbc-consensus/src pallets/qbc-dilithium/src \
    pallets/qbc-economics/src pallets/qbc-qvm-anchor/src pallets/qbc-aether-anchor/src \
    pallets/qbc-reversibility/src crypto/kyber-transport/src \
    && echo "fn main() {}" > node/src/main.rs \
    && echo "" > runtime/src/lib.rs \
    && echo "" > primitives/src/lib.rs \
    && for p in qbc-utxo qbc-consensus qbc-dilithium qbc-economics qbc-qvm-anchor qbc-aether-anchor qbc-reversibility; do \
         echo "" > pallets/$p/src/lib.rs; \
       done \
    && echo "" > crypto/kyber-transport/src/lib.rs

# Build dependencies only (cached unless Cargo.toml changes)
RUN SKIP_WASM_BUILD=1 cargo build --release 2>/dev/null || true

# Copy actual source code
COPY . .

# Touch source files to invalidate cached builds of our crates only
RUN find node runtime primitives pallets -name "*.rs" -exec touch {} +

# Build the node binary (WASM build deferred — serde_core no_std conflict)
RUN SKIP_WASM_BUILD=1 cargo build --release

# ═══════════════════════════════════════════════════════════════
# Stage 2: Runtime image
# ═══════════════════════════════════════════════════════════════

FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
    ca-certificates \
    libssl3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 -U -s /bin/sh -d /qubitcoin qubitcoin

COPY --from=builder /build/target/release/qbc-node /usr/local/bin/qbc-node

USER qubitcoin

RUN mkdir -p /qubitcoin/data

EXPOSE 9944 9933 30333 9615

VOLUME ["/qubitcoin/data"]

ENTRYPOINT ["/usr/local/bin/qbc-node"]
CMD [ \
    "--base-path", "/qubitcoin/data", \
    "--name", "qubitcoin-node", \
    "--prometheus-external", \
    "--rpc-cors", "all", \
    "--rpc-external" \
]
