# Contributing to Quantum Blockchain

Thank you for your interest in contributing to Quantum Blockchain! This guide will help you get
started with the development workflow.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Architecture Overview](#architecture-overview)
- [Code Conventions](#code-conventions)
- [Submitting Changes](#submitting-changes)
- [Testing](#testing)
- [Risk Classification](#risk-classification)
- [Security](#security)

---

## Getting Started

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. **Read** `CLAUDE.md` thoroughly -- it is the single source of truth for the project
4. **Set up** your development environment (see below)
5. **Create a branch** from `main` for your changes

## Development Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend / L1 core |
| Node.js | 20+ | Frontend tooling |
| pnpm | latest | Frontend package manager |
| Rust | 2021 edition | P2P networking |
| CockroachDB | v24.2.0 | Database |
| Docker | latest | Containerized deployment |

### Backend Setup

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate node keys (creates secure_key.env)
python3 scripts/setup/generate_keys.py

# Copy config template
cp .env.example .env
# Edit .env for your environment (ports, database, quantum settings)

# Run the node
cd src && python3 run_node.py
```

### Frontend Setup

```bash
cd frontend
pnpm install
pnpm dev          # Development server at localhost:3000
pnpm build        # Production build
pnpm test         # Run unit tests
```

### Rust P2P Daemon

```bash
cd rust-p2p
cargo build --release
```

### Substrate Node (Optional)

```bash
cd substrate-node
SKIP_WASM_BUILD=1 cargo build --release
```

### Docker (Full Stack)

```bash
docker-compose up -d
```

## Architecture Overview

Qubitcoin has four main layers:

| Layer | Location | Technology |
|-------|----------|------------|
| **L1 Core** | `src/qubitcoin/` | Python (consensus, mining, crypto, database, network) |
| **L2 QVM** | `src/qubitcoin/qvm/` | Python prototype, Go production (planned) |
| **L3 Aether Tree** | `src/qubitcoin/aether/` | Python (knowledge graph, reasoning, consciousness) |
| **Substrate Node** | `substrate-node/` | Rust (future migration path, 6 custom pallets) |
| **Frontend** | `frontend/` | Next.js 15, React 19, TypeScript 5, TailwindCSS 4 |

Cross-cutting systems: `bridge/` (8 chains), `stablecoin/` (QUSD), `privacy/` (Susy Swaps)

See `CLAUDE.md` Sections 6-9 for detailed architecture documentation.

## Code Conventions

### Python (Backend)

- **Classes:** PascalCase (`QuantumEngine`, `DatabaseManager`)
- **Functions/methods:** snake_case (`calculate_reward`, `validate_block`)
- **Constants:** UPPER_CASE (`MAX_SUPPLY`, `PHI`)
- **Private methods:** underscore prefix (`_initialize_backend`)
- **Type hints:** Required on all function signatures
- **Logging:** Use `get_logger(__name__)` from `utils/logger.py` in every module
- **Config:** Use `Config` class from `config.py` -- never hardcode values
- **Line length:** ~100 characters
- **Imports:** Standard library first, third-party second, local imports third

### TypeScript (Frontend)

- **Strict mode:** No `any` types
- **Components:** Functional components with hooks
- **Server Components:** Default; use `'use client'` only when needed
- **Imports:** Use `@/` path alias for `src/` directory
- **State:** Zustand for global state, TanStack Query for server state
- **Styling:** TailwindCSS 4 utility classes

### Key Rules

- Never silently swallow exceptions -- use structured logging
- Never hardcode secrets -- private keys in `secure_key.env`, config in `.env`
- Never commit `secure_key.env` -- it is .gitignored
- Use `Config` class for all configuration values

## Submitting Changes

### Branching

- Create feature branches from `main`
- Branch naming: `feature/description`, `fix/description`, `docs/description`
- Never commit directly to `main`

### Commit Messages

Follow this format:

```
type: short description

Longer explanation if needed.
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

### Pull Request Process

1. Ensure all tests pass (`pytest tests/ -v --tb=short`)
2. Ensure the frontend builds (`cd frontend && pnpm build`)
3. Update task tracking if you completed tracked items
4. Write a clear PR description with:
   - Summary of changes
   - Which subsystem/layer is affected
   - Test plan
5. Request review

### Batch Protocol

For large changes, follow the batch protocol from `CLAUDE.md`:

1. **Plan** -- list files, identify dependencies, rate risk
2. **Implement** -- max 5 files per batch (STANDARD risk)
3. **Test** -- run tests after each batch
4. **Commit** -- only when tests pass

## Testing

### Running Tests

```bash
# Backend unit tests
pytest tests/unit/ -v --tb=short

# Backend integration tests
pytest tests/integration/ -v --tb=short

# Full backend suite
pytest tests/ -v --tb=short

# Frontend unit tests
cd frontend && pnpm test

# Frontend E2E tests
cd frontend && pnpm test:e2e
```

### Writing Tests

- Place unit tests in `tests/unit/`
- Place integration tests in `tests/integration/`
- Use `MagicMock` to stub heavy dependencies (Qiskit, gRPC, IPFS, CockroachDB)
- Follow existing patterns in `conftest.py` for dependency stubs
- Use `_make_engine()` factory pattern for creating test instances
- Async tests require `@pytest.mark.asyncio` decorator

### Test Coverage Goals

| Module | Current Tests | Status |
|--------|---------------|--------|
| Consensus | 83+ | Covered |
| Mining | 14+ | Covered |
| Quantum/Crypto | 26+ | Covered |
| QVM | 200+ | Covered |
| Aether Tree | 280+ | Covered |
| Privacy | 50+ | Covered |
| Network | 43+ | Covered |
| Contracts | 11+ | Covered |
| Bridge | 50+ | Covered |
| Stablecoin | 123+ | Covered |
| Frontend | 5 | Basic |
| **Total** | **3,901** | **All Passing** |

## Risk Classification

Changes are classified by risk level:

### CRITICAL (requires explicit approval)
- `consensus/engine.py` -- block validation, difficulty, rewards
- `quantum/crypto.py` -- Dilithium signatures, key derivation
- `database/models.py` -- data models (must match SQL schemas)
- `mining/engine.py` -- block creation, VQE mining loop
- `sql/09_genesis_block.sql` -- genesis block data
- Anything touching UTXO spending rules

### HIGH (max 3 files per batch)
- `qvm/vm.py`, `qvm/opcodes.py`, `qvm/state.py` -- QVM interpreter
- `privacy/*.py` -- privacy features
- `aether/*.py` -- Aether Tree AI
- `bridge/*.py` -- cross-chain bridges
- `network/jsonrpc.py` -- JSON-RPC compatibility

### STANDARD (max 5 files per batch)
- `network/rpc.py` -- REST endpoints
- `utils/*.py` -- logging, metrics
- `config.py` -- configuration
- `frontend/**` -- all frontend code
- `tests/**` -- all test files

## Security

### Reporting Vulnerabilities

If you discover a security vulnerability, please report it responsibly:
- Do NOT open a public issue
- Email: **info@qbc.network**
- Provide detailed reproduction steps

### Security Practices

- Never commit private keys or secrets
- `secure_key.env` contains Dilithium private keys -- NEVER commit this file
- `.env` contains non-secret configuration only
- Review OWASP top 10 before submitting changes to network-facing code
- All cryptographic operations use CRYSTALS-Dilithium2 (post-quantum)

---

*For detailed technical documentation, see `CLAUDE.md` (master development guide),
`docs/WHITEPAPER.md`, `docs/QVM_WHITEPAPER.md`, and `docs/AETHERTREE_WHITEPAPER.md`.*

**Website:** [qbc.network](https://qbc.network) | **Contact:** info@qbc.network | **GitHub:** [BlockArtica/Qubitcoin](https://github.com/BlockArtica/Qubitcoin)
