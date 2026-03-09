# ═══════════════════════════════════════════════════════════════════════
# Qubitcoin API Gateway — Docker Image
# ═══════════════════════════════════════════════════════════════════════
FROM rust:1.85-bookworm AS builder
WORKDIR /build
COPY api-gateway/Cargo.toml api-gateway/Cargo.lock* ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs && cargo build --release 2>/dev/null || true
RUN rm -rf src
COPY api-gateway/src/ ./src/
RUN cargo build --release

FROM debian:bookworm-slim
LABEL org.opencontainers.image.title="Qubitcoin API Gateway"
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=builder /build/target/release/qbc-api-gateway /usr/local/bin/

ENV API_LISTEN_ADDR=0.0.0.0:5000
ENV SUBSTRATE_WS_URL=ws://substrate-node:9944
ENV DATABASE_URL=postgresql://root@cockroachdb:26257/qbc?sslmode=disable
ENV AETHER_SERVICE_URL=http://aether-service:5001
ENV CHAIN_ID=3303
ENV LOG_LEVEL=info

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:5000/health || exit 1

ENTRYPOINT ["qbc-api-gateway"]
