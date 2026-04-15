# ═══════════════════════════════════════════════════════════════════════
# Qubitcoin Block Indexer — Docker Image
# ═══════════════════════════════════════════════════════════════════════
#
# Multi-stage Rust build for minimal production image.
#
# Usage:
#   docker build -t qbc-indexer -f indexer/Dockerfile .
#   docker run --rm \
#     -e SUBSTRATE_WS_URL=ws://substrate-node:9944 \
#     -e DATABASE_URL=postgresql://root@cockroachdb:26257/qbc \
#     qbc-indexer
# ═══════════════════════════════════════════════════════════════════════

FROM rust:1-bookworm AS builder

WORKDIR /build

# Cache dependencies
COPY indexer/Cargo.toml indexer/Cargo.lock* ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs && cargo build --release 2>/dev/null || true
RUN rm -rf src target/release/qbc-indexer target/release/deps/qbc_indexer*

# Build real source
COPY indexer/src/ ./src/
RUN touch src/main.rs && cargo build --release

# ── Production stage ────────────────────────────────────────────────
FROM debian:bookworm-slim

LABEL org.opencontainers.image.title="Qubitcoin Block Indexer"
LABEL org.opencontainers.image.description="Subscribes to finalized Substrate blocks and writes to CockroachDB"

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/qbc-indexer /usr/local/bin/

# Environment defaults
ENV SUBSTRATE_WS_URL=ws://substrate-node:9944
ENV DATABASE_URL=postgresql://root@cockroachdb:26257/qbc?sslmode=disable
ENV DB_POOL_SIZE=10
ENV START_HEIGHT=0
ENV BACKFILL=false
ENV LOG_LEVEL=info

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD test -f /tmp/indexer_healthy || exit 1

ENTRYPOINT ["qbc-indexer"]
