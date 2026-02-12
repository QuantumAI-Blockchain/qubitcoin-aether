# CLAUDE.md - Qubitcoin Development Guide

This file provides context and instructions for Claude Code (and other AI assistants) when working on the Qubitcoin codebase.

## Project Overview

Qubitcoin (QBC) is a quantum-secured Layer 1 blockchain combining quantum computing (Qiskit VQE), post-quantum cryptography (CRYSTALS-Dilithium2), and supersymmetric (SUSY) economics with golden ratio principles.

- **Primary language:** Python 3.11+
- **Secondary language:** Rust 2021 (P2P networking via libp2p)
- **Framework:** FastAPI + SQLAlchemy + Qiskit
- **Database:** CockroachDB (distributed SQL)
- **License:** MIT

## Repository Structure

```
src/qubitcoin/           # Main Python package
  aether/                # Aether Tree AGI/reasoning engine
  bridge/                # Multi-chain bridge system (ETH, SOL, etc.)
  consensus/             # Proof-of-SUSY-Alignment (PoSA) consensus
  contracts/             # Smart contract execution engine
  database/              # CockroachDB abstraction (SQLAlchemy ORM)
  mining/                # PoSA mining engine
  network/               # RPC (FastAPI) + P2P networking
  quantum/               # VQE quantum engine + post-quantum crypto
  qvm/                   # Quantum Virtual Machine (smart contracts)
  stablecoin/            # QUSD stablecoin engine
  storage/               # IPFS integration
  utils/                 # Logging + Prometheus metrics
  config.py              # Centralized configuration (env-based)
  node.py                # Main node orchestrator
rust-p2p/                # Rust P2P daemon (libp2p 0.56)
sql/                     # CockroachDB schema files (00-09)
tests/                   # Unit, integration, and validation tests
scripts/                 # Utility and operational scripts
deployment/              # Docker deployment configs
docs/                    # Whitepaper, economics docs
```

## Build & Run

### Python (core blockchain)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd src && python3 run_node.py
```

### Rust (P2P networking)

```bash
cd rust-p2p
cargo build --release
```

### Docker

```bash
# Development
docker-compose up -d

# Production (multi-node CockroachDB cluster)
bash fresh_start.sh
docker-compose -f docker-compose.production.yml up -d
```

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Full system validation
python3 test_system.py

# Endpoint tests (requires running node)
bash tests/scripts/test_all_endpoints.sh
```

## Environment Configuration

Copy `.env.example` to `.env` and configure. Key variables:

- `DATABASE_URL` - CockroachDB connection string
- `USE_SIMULATOR=true` - Use Qiskit simulator (no IBM Quantum account needed)
- `P2P_PORT`, `RPC_PORT` - Network ports
- `AUTO_MINE` - Enable automatic mining
- `IPFS_API` - IPFS daemon endpoint

## Code Conventions

### Style

- **Classes:** PascalCase (`QuantumEngine`, `DatabaseManager`)
- **Functions/methods:** snake_case (`calculate_reward`, `validate_block`)
- **Constants:** UPPER_CASE (`MAX_SUPPLY`, `PHI`, `INITIAL_REWARD`)
- **Private methods:** underscore prefix (`_initialize_backend`)
- **Type hints:** Required on all function signatures
- **Line length:** ~100 characters (not strictly enforced)

### Patterns

- **Logging:** Use `get_logger(__name__)` from `utils/logger.py` in every module
- **Metrics:** Instrument with Prometheus via `utils/metrics.py`
- **Configuration:** Access via `Config` class from `config.py` (never hardcode values)
- **Database:** Use SQLAlchemy ORM sessions via `DatabaseManager` context managers
- **Async:** FastAPI routes are async; use `await` for I/O operations
- **Error handling:** Try/except with structured logging; never silently swallow exceptions

### Key Constants (Golden Ratio Economics)

- `PHI = 1.618033988749895` (golden ratio)
- `MAX_SUPPLY = 3,300,000,000 QBC`
- Block time: 3.3 seconds
- Emission period: 33 years
- Halving based on golden ratio (`reward / PHI^era`)

## Database Schemas

Schema files in `sql/` are numbered and must be applied in order:

1. `00_init_database.sql` - Database initialization
2. `01_core_blockchain.sql` - Blocks, transactions, wallets
3. `02_privacy_susy_swaps.sql` - Privacy and SUSY swap tables
4. `03_smart_contracts_qvm.sql` - QVM contract tables
5. `04_multi_chain_bridge.sql` - Cross-chain bridge tables
6. `05_qusd_stablecoin.sql` - QUSD stablecoin tables
7. `06_quantum_research.sql` - Quantum research data
8. `07_ipfs_storage.sql` - IPFS pinning and storage
9. `08_system_configuration.sql` - System config tables
10. `09_genesis_block.sql` - Genesis block insertion

When modifying schemas, ensure column names and types match the SQLAlchemy models in `database/models.py`.

## Important Warnings

- **Schema-model alignment:** Past bugs have come from mismatches between SQL schemas (`sql/`) and SQLAlchemy models (`database/models.py`). Always verify both sides when changing data structures.
- **Quantum imports:** Qiskit imports can be slow. The codebase uses lazy imports and simulator fallbacks. Respect this pattern.
- **No secrets in code:** Keys, tokens, and credentials go in `.env` only. Never commit `.env` files.
- **Bridge security:** Multi-chain bridge code handles real asset transfers. Changes to `bridge/` require extra scrutiny.

## Useful Commands

```bash
# Generate new node keys
python3 scripts/generate_keys.py

# Monitor cluster health
bash monitor.sh

# Check all RPC endpoints
bash tests/scripts/test_all_endpoints.sh

# Database statistics
bash tests/scripts/db_stats.sh
```
