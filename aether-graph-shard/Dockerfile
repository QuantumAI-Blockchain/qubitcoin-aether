FROM rust:1.86-bookworm AS builder

RUN apt-get update && apt-get install -y protobuf-compiler libclang-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY Cargo.toml build.rs ./
COPY proto/ proto/
COPY src/ src/

RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y ca-certificates wget && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/target/release/aether-graph-shard /usr/local/bin/

ENV GRAPH_SHARD_PORT=50053
ENV GRAPH_SHARD_DATA_DIR=/data/graph-shards
ENV GRAPH_SHARD_CACHE=100000
ENV RUST_LOG=info

EXPOSE 50053 51053

VOLUME /data/graph-shards

CMD ["aether-graph-shard"]
