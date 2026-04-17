# Qubitcoin AIKGS Sidecar

Rust gRPC sidecar implementing the AI Knowledge Growth System (AIKGS) for the Qubitcoin blockchain. Provides 35 RPC endpoints for knowledge contributions, curation, bounties, rewards, and treasury management. Runs as a Docker container (`qbc-aikgs-sidecar`) on port 50052, complementing the Aether Tree AI engine with high-performance knowledge lifecycle operations.

## Key Features

- **35 gRPC RPCs** — Full knowledge lifecycle: submit, validate, curate, score, reward, and query contributions.
- **Knowledge Curation** — Automated quality scoring with configurable thresholds and multi-stage validation pipelines.
- **Bounty System** — Create, fund, claim, and settle knowledge bounties with escrow semantics.
- **Reward Engine** — Contributor reward calculation and distribution tracking tied to knowledge quality scores.
- **Treasury Management** — On-chain treasury accounting for bounty funding and reward pools.
- **AES-256-GCM Vault** — Encrypted storage for sensitive knowledge artifacts and contributor credentials.
- **Affiliate Tracking** — Referral and affiliate commission accounting for knowledge contributions.

## Quick Start

```bash
# Build
cargo build --release

# Run
./target/release/aikgs-sidecar --port 50052

# Docker (recommended)
docker build -t qbc-aikgs-sidecar .
docker run -d \
  -p 50052:50052 \
  --name qbc-aikgs-sidecar \
  qbc-aikgs-sidecar
```

## Architecture

```
aikgs-sidecar/
├── proto/
│   └── aikgs.proto          # gRPC service definition (35 RPCs)
├── src/
│   ├── main.rs              # Entry point and server bootstrap
│   ├── lib.rs               # Library root
│   ├── service.rs           # gRPC service implementation
│   ├── config.rs            # Configuration management
│   ├── db.rs                # Database layer (CockroachDB)
│   ├── contributions.rs     # Knowledge contribution submission and tracking
│   ├── curation.rs          # Multi-stage curation pipeline
│   ├── scorer.rs            # Knowledge quality scoring
│   ├── validation.rs        # Contribution validation rules
│   ├── bounties.rs          # Bounty lifecycle (create, claim, settle)
│   ├── rewards.rs           # Reward calculation and distribution
│   ├── treasury.rs          # Treasury accounting
│   ├── affiliates.rs        # Affiliate commission tracking
│   ├── unlocks.rs           # Vesting and unlock schedules
│   └── vault.rs             # AES-256-GCM encrypted artifact storage
├── Cargo.toml
├── build.rs                 # Protobuf code generation
└── Dockerfile
```

### Integration

The AIKGS sidecar connects to:

| Dependency   | Purpose                              |
|--------------|--------------------------------------|
| CockroachDB  | Persistent storage (port 26257)      |
| Python Node  | Aether Tree client calls via gRPC    |
| Agent Stack  | Knowledge submissions from AI agents |

## Testing

```bash
cargo test --workspace
```

## Configuration

Environment variables:

| Variable          | Default | Description                  |
|-------------------|---------|------------------------------|
| `AIKGS_PORT`      | 50052   | gRPC listen port             |
| `DATABASE_URL`    | —       | CockroachDB connection string|
| `VAULT_KEY`       | —       | AES-256-GCM encryption key   |

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [AIKGS Sidecar Repo](https://github.com/QuantumAI-Blockchain/aikgs-sidecar)
