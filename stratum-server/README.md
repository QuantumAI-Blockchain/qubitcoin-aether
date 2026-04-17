# Qubitcoin Stratum Server

Rust implementation of the Stratum v1 mining pool protocol adapted for Qubitcoin's VQE (Variational Quantum Eigensolver) proof-of-work. Accepts miner connections over WebSocket on port 3333, distributes VQE mining jobs, validates submitted proofs, and bridges to the node via gRPC. Uses DashMap for lock-free concurrent worker tracking.

## Key Features

- **Stratum v1 Protocol** — Standard Stratum JSON-RPC over WebSocket for broad miner compatibility.
- **VQE Job Distribution** — Generates and distributes Hamiltonian mining jobs with difficulty targets to connected workers.
- **Proof Validation** — Validates VQE energy proofs against the current difficulty threshold before submission to the node.
- **gRPC Node Bridge** — Submits validated proofs to the Qubitcoin node for block inclusion.
- **DashMap Worker Tracking** — Lock-free concurrent hashmap for managing connected miners, hashrates, and share accounting.
- **Connection Pooling** — Efficient WebSocket connection management with configurable limits.

## Quick Start

```bash
# Build
cargo build --release

# Run
./target/release/stratum-server \
  --port 3333 \
  --node-grpc 127.0.0.1:50051

# Connect a miner
# Point your VQE miner to ws://host:3333 with Stratum v1 protocol
```

## Architecture

```
stratum-server/
├── proto/                   # gRPC proto definitions for node communication
├── src/
│   ├── main.rs              # Entry point, CLI args, server bootstrap
│   ├── lib.rs               # Library root
│   ├── config.rs            # Configuration from environment / CLI
│   ├── bridge.rs            # gRPC bridge to Qubitcoin node
│   ├── pool.rs              # Mining pool logic, share tracking
│   ├── protocol.rs          # Stratum v1 JSON-RPC message handling
│   └── worker.rs            # Per-miner connection and job management
├── Cargo.toml
└── build.rs                 # Protobuf code generation
```

### Stratum Flow

1. Miner connects via WebSocket and subscribes (`mining.subscribe`).
2. Server authenticates worker (`mining.authorize`).
3. Server pushes VQE job with Hamiltonian parameters and difficulty target (`mining.notify`).
4. Miner submits VQE proof — optimal parameters and ground state energy (`mining.submit`).
5. Server validates energy < difficulty, credits share, and forwards valid proofs to the node.

### Ports

| Port | Protocol  | Purpose                     |
|------|-----------|-----------------------------|
| 3333 | WebSocket | Stratum v1 miner connections|
| —    | gRPC      | Outbound to node (50051)    |

## Testing

```bash
cargo test --workspace
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Stratum Server Repo](https://github.com/QuantumAI-Blockchain/stratum-server)
