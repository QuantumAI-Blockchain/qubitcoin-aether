# Qubitcoin Rust P2P

Rust networking daemon built on libp2p 0.56 for the Qubitcoin blockchain. Handles block and transaction propagation via Gossipsub, peer discovery via Kademlia DHT, and exposes a gRPC bridge on port 50051 for the Python node to publish and subscribe to network events. Runs as a Docker container (`qbc-p2p`).

## Key Features

- **Gossipsub 1.1** — Efficient pub/sub for block announcements and transaction broadcast with mesh peer scoring.
- **Kademlia DHT** — Distributed peer discovery and routing table management.
- **gRPC Bridge** — Bidirectional bridge (port 50051) allowing the Python node to publish blocks/transactions and receive network events.
- **Connection Multiplexing** — Yamux stream multiplexing over TCP with Noise protocol encryption.
- **Worker Pool Management** — Concurrent connection handling with configurable pool sizing.
- **Docker-Native** — Production deployment as `qbc-p2p` container with host networking on port 4002.

## Quick Start

```bash
# Build
cargo build --release

# Run standalone
./target/release/qbc-p2p \
  --listen-port 4002 \
  --grpc-port 50051 \
  --peer-seeds /ip4/152.42.215.182/tcp/4002

# Docker (recommended)
docker build -t qbc-p2p .
docker run -d \
  -p 4002:4001 \
  -p 50051:50051 \
  --name qbc-p2p \
  qbc-p2p
```

## Architecture

```
rust-p2p/
├── proto/
│   └── p2p_service.proto    # gRPC service definition (publish, subscribe, peers)
├── src/
│   ├── main.rs              # Entry point, CLI args, service bootstrap
│   ├── config.rs            # Configuration from environment / CLI
│   ├── lib.rs               # Library root
│   ├── bridge.rs            # gRPC bridge server (node <-> P2P)
│   ├── pool.rs              # Connection pool management
│   ├── protocol.rs          # Gossipsub + Kademlia protocol setup
│   └── worker.rs            # Per-connection worker tasks
├── Cargo.toml
├── build.rs                 # Protobuf code generation
└── Dockerfile
```

### Network Topology

| Port  | Protocol | Purpose                          |
|-------|----------|----------------------------------|
| 4002  | TCP      | libp2p swarm (Gossipsub + DHT)   |
| 50051 | gRPC     | Bridge to Python/Substrate node  |

### gRPC Services

- `PublishBlock` / `PublishTransaction` — Node pushes data to the P2P network.
- `SubscribeBlocks` / `SubscribeTransactions` — Streaming subscription for incoming network data.
- `GetPeers` / `GetPeerCount` — Peer discovery and connectivity status.

## Testing

```bash
cargo test --workspace
```

## Configuration

Environment variables:

| Variable       | Default | Description                |
|----------------|---------|----------------------------|
| `LISTEN_PORT`  | 4001    | libp2p swarm listen port   |
| `GRPC_PORT`    | 50051   | gRPC bridge port           |
| `PEER_SEEDS`   | —       | Comma-separated multiaddrs |

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Rust P2P Repo](https://github.com/QuantumAI-Blockchain/rust-p2p)
