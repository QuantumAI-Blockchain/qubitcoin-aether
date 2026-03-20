# QBC Exchange Engine — standalone container
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

COPY --from=builder /build/target/release/qbc-exchange /usr/local/bin/qbc-exchange
RUN chmod +x /usr/local/bin/qbc-exchange

RUN groupadd -r qbc && useradd -r -g qbc qbc
USER qbc

EXPOSE 50053

CMD ["qbc-exchange"]
