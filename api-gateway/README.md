# Qubitcoin API Gateway

Rust HTTP API gateway for the Qubitcoin blockchain. Provides a unified entry point for all client-facing API routes including chain queries, wallet operations, mining control, Aether Tree AI endpoints, JSON-RPC (eth_* compatible), and health monitoring. Intended as the production replacement for the Python FastAPI server, offering lower latency and higher throughput.

## Key Features

- **Unified API Surface** — Single gateway serving REST, JSON-RPC, and WebSocket endpoints.
- **Route Modules** — Organized by domain: aether, chain, health, jsonrpc, mining, wallet.
- **JSON-RPC Compatibility** — `eth_*` namespace for MetaMask and Web3 tooling integration.
- **Aether Tree Routes** — Chat, knowledge graph queries, Phi metrics, and contribution endpoints.
- **Health Monitoring** — Component-level health checks with structured status responses.
- **Configuration** — Environment-based configuration with sensible defaults.

## Quick Start

```bash
# Build
cargo build --release

# Run
./target/release/api-gateway --port 5000

# Docker
docker build -t qbc-api-gateway .
docker run -d -p 5000:5000 qbc-api-gateway

# Health check
curl http://localhost:5000/health
```

## Architecture

```
api-gateway/
├── src/
│   ├── main.rs              # Entry point, server bootstrap
│   ├── config.rs            # Environment-based configuration
│   ├── state.rs             # Shared application state
│   └── routes/
│       ├── mod.rs            # Route registration
│       ├── aether.rs         # /aether/* — AI chat, knowledge, Phi
│       ├── chain.rs          # /chain/* — blocks, transactions, UTXO
│       ├── health.rs         # /health — component status
│       ├── jsonrpc.rs        # / — eth_* JSON-RPC handler
│       ├── mining.rs         # /mining/* — start, stop, status
│       └── wallet.rs         # /wallet/* — balance, send, keys
├── Cargo.toml
└── Dockerfile
```

### Route Overview

| Prefix      | Methods | Description                           |
|-------------|---------|---------------------------------------|
| `/health`   | GET     | Component health, readiness, liveness |
| `/chain`    | GET     | Block, transaction, and UTXO queries  |
| `/wallet`   | GET/POST| Balance lookup, transaction creation  |
| `/mining`   | POST    | Mining start/stop, status, difficulty |
| `/aether`   | GET/POST| AI chat, knowledge graph, Phi metrics |
| `/`         | POST    | JSON-RPC (`eth_*` namespace)          |

### Integration

| Upstream         | Purpose                              |
|------------------|--------------------------------------|
| Python Node      | Chain state, UTXO, mempool (port 5000) |
| Substrate Node   | Block queries, extrinsic submission  |
| AIKGS Sidecar    | Knowledge contributions (port 50052) |
| CockroachDB      | Direct DB queries for indexing       |

## Testing

```bash
cargo test --workspace
```

## Configuration

| Variable        | Default | Description                  |
|-----------------|---------|------------------------------|
| `API_PORT`      | 5000    | HTTP listen port             |
| `NODE_URL`      | —       | Upstream node RPC URL        |
| `DATABASE_URL`  | —       | CockroachDB connection       |

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [API Gateway Repo](https://github.com/QuantumAI-Blockchain/api-gateway)
