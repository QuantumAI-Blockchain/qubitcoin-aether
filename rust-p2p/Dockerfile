# Qubitcoin Rust P2P Daemon — standalone container
FROM rust:latest AS builder

RUN apt-get update && apt-get install -y \
    protobuf-compiler \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY . .
RUN cargo build --release

# ── Runtime stage ──────────────────────────────────────────────────────
FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/qubitcoin-p2p /usr/local/bin/qubitcoin-p2p
RUN chmod +x /usr/local/bin/qubitcoin-p2p

# Run as non-root
RUN groupadd -r qbc && useradd -r -g qbc qbc
USER qbc

EXPOSE 4001 4002 50051

CMD ["qubitcoin-p2p"]
