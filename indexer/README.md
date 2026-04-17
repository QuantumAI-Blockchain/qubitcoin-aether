# Qubitcoin Blockchain Indexer

Rust blockchain indexer for the Qubitcoin network. Subscribes to the Substrate node, processes blocks, transactions, and runtime events in real time, and persists structured data to CockroachDB for fast querying by the API gateway and frontend. Provides the data layer powering the block explorer, wallet balance lookups, and analytics dashboards.

## Key Features

- **Real-Time Indexing** — Subscribes to finalized blocks from the Substrate node and processes them as they arrive.
- **Substrate Client** — Native Substrate RPC client for block fetching, event decoding, and storage queries.
- **Database Persistence** — Writes blocks, transactions, UTXO state, events, and address balances to CockroachDB.
- **Event Decoding** — Parses runtime events from all 7 custom pallets (utxo, consensus, dilithium, economics, qvm-anchor, aether-anchor, reversibility).
- **Backfill Support** — Can index historical blocks from genesis or a specified height.
- **Configurable** — Environment-based configuration for node endpoints, database connection, and indexing parameters.

## Quick Start

```bash
# Build
cargo build --release

# Run (connect to local Substrate node)
./target/release/qbc-indexer \
  --substrate-url ws://localhost:9944 \
  --database-url postgresql://root@localhost:26257/qbc

# Docker
docker build -t qbc-indexer .
docker run -d \
  -e SUBSTRATE_URL=ws://node:9944 \
  -e DATABASE_URL=postgresql://root@cockroachdb:26257/qbc \
  qbc-indexer

# Backfill from specific height
./target/release/qbc-indexer --from-block 208680
```

## Architecture

```
indexer/
├── src/
│   ├── main.rs              # Entry point, CLI args, service bootstrap
│   ├── config.rs            # Environment-based configuration
│   ├── indexer.rs           # Core indexing loop: subscribe, decode, persist
│   ├── substrate.rs         # Substrate RPC client (blocks, events, storage)
│   ├── db.rs                # CockroachDB persistence layer
│   └── types.rs             # Indexed data types (blocks, txs, events)
├── Cargo.toml
└── Dockerfile
```

### Indexing Pipeline

1. **Subscribe** — Connect to Substrate node via WebSocket, subscribe to finalized block headers.
2. **Fetch** — Retrieve full block body, extrinsics, and events for each finalized block.
3. **Decode** — Parse extrinsics and events from all 7 pallets into structured types.
4. **Persist** — Write to CockroachDB tables: `blocks`, `transactions`, `utxos`, `events`, `addresses`.
5. **Update** — Maintain running balances, UTXO set state, and indexer checkpoint.

### Data Flow

```
Substrate Node (ws://9944)
    │
    ▼
Indexer (subscribe + decode)
    │
    ▼
CockroachDB (port 26257)
    │
    ▼
API Gateway / Frontend
```

## Configuration

| Variable          | Default              | Description                       |
|-------------------|----------------------|-----------------------------------|
| `SUBSTRATE_URL`   | `ws://localhost:9944`| Substrate node WebSocket endpoint |
| `DATABASE_URL`    | —                    | CockroachDB connection string     |
| `FROM_BLOCK`      | latest               | Start indexing from this height   |
| `BATCH_SIZE`      | 100                  | Blocks per batch for backfill     |

## Testing

```bash
cargo test --workspace
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Indexer Repo](https://github.com/QuantumAI-Blockchain/blockchain-indexer)
