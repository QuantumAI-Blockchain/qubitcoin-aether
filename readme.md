```markdown
# Qubitcoin (QBC): A Supersymmetric Framework for Physics-Secured Digital Assets

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![Qiskit](https://img.shields.io/badge/Qiskit-1.2.4-blueviolet.svg)](https://qiskit.org/)
[![CockroachDB](https://img.shields.io/badge/CockroachDB-latest-orange.svg)](https://www.cockroachlabs.com/)
[![libp2p](https://img.shields.io/badge/libp2p-Rust%20Bindings-green.svg)](https://libp2p.io/)

Qubitcoin (QBC) is a pioneering decentralized digital asset system that shifts the paradigm from computational cryptography to physical security rooted in quantum mechanics and supersymmetry (SUSY). Inspired by Bitcoin's scarcity model (21M token cap, halvings every 210,000 blocks), QBC leverages the no-cloning theorem and SUSY principles to create unforgeable tokens encoded via Adinkra diagrams. Tokens are minted through low-power Proof-of-SUSY-Alignment (PoSA) using Variational Quantum Eigensolver (VQE) on randomized fermion-boson Hamiltonians, executable on NISQ devices like IBM Quantum or local simulators.

This project represents BTC 2.0 in the quantum era: Energy-efficient (50 mJ per proof vs. BTC's 700 kWh), scientifically valuable (shared Hamiltonians probe SUSY breaking), and post-quantum secure (Dilithium signatures). It evolves from a hybrid quantum-classical network to full decentralization, with features like P2P gossip via libp2p/IPFS, privacy-preserving SUSY swaps, fractional tokens, and an Ethereum cross-chain bridge (wQBC ERC-20 for DeFi liquidity via Chainlink oracles).

Deployable today (January 2026), Qubitcoin achieves >95% fidelity on NISQ/simulations, with phases for true unstoppability like BTC. For details, see the [White Paper](docs/QBC_White_paper.pdf).

## Key Features

- **Physical Unforgeability**: Tokens as SUSY multiplets (fermion-boson pairs) encoded in Adinkra graphs; cloning violates quantum laws, detectable via fidelity checks.
- **Low-Power Mining (PoSA)**: VQE-based alignment of SUSY Hamiltonians; toggles for local exact/noisy sim or real IBM Quantum (quota-aware).
- **Decentralized Network**: Full nodes merge mining/validation/sync (node.py); libp2p for robust P2P (pubsub for proofs/txns/snaps), IPFS for immutable ledger snapshots.
- **Economics**: 21M cap, halvings, 1.1M genesis pre-mine; incentives via fees/rewards (deflationary, page 3 table).
- **Privacy**: Distributed SUSY swaps for untraceable mixing (multi-party protocols, no central mixer).
- **Interoperability**: Ethereum bridge with oracle-verified proofs (wQBC mint/burn, Chainlink integration).
- **Fault Tolerance**: >95% fidelity; dynamic difficulty for 10-min blocks; longest chain consensus with fork resolution.
- **Production-Ready**: CockroachDB for distributed storage; FastAPI RPC for wallets; Prometheus metrics; Dockerized for multi-node clusters.
- **Scientific Impact**: Shared solved Hamiltonians advance SUSY research (IPFS CIDs, page 13).

## Project Structure

```
qubitcoin/
├── .env                  # Environment variables (IBM_TOKEN, DATABASE_URL, etc.)
├── .env.example          # Template for .env
├── .gitignore            # Git ignore rules
├── LICENSE               # Creative Commons Attribution 4.0
├── README.md             # This file
├── config/               # Configuration files (e.g., YAML for nodes)
├── data/                 # Data storage (e.g., IPFS pins, snapshots)
├── docker/               # Dockerfiles for node, DB, etc.
├── docker-compose.yml    # Multi-container setup (CockroachDB cluster, IPFS, nodes)
├── docs/                 # Documentation
│   ├── QBC_White_paper.pdf  # Core theory (17 pages, abstract on page 1)
│   └── QBC_launch_instructions.txt  # Deployment guide (superseded for decentralization)
├── logs/                 # Runtime logs (rich formatted)
├── requirements.txt      # Python dependencies (Qiskit, FastAPI, Dilithium, etc.)
├── scripts/              # Utility scripts (e.g., generate_keys.py, init_db.sh)
├── secure_key.env        # Sensitive keys (PRIVATE_KEY_HEX, etc.)
├── src/                  # Source code
│   ├── node.py           # Full decentralized node (mining, validation, P2P, RPC)
│   ├── db_scheme.sql     # CockroachDB schema (ledger, transactions, etc.)
│   ├── smart_contract.sol  # wQBC ERC-20 Solidity (with Chainlink oracles)
│   └── ...               # Helpers (VQE, oracle, etc.)
├── tests/                # Unit/integration tests (e.g., VQE convergence, P2P sync)
└── venv/                 # Virtual environment (local dev)
```

## Prerequisites

- Python 3.12+
- IBM Quantum account (for real NISQ; optional for sim)
- CockroachDB (for distributed DB; PostgreSQL for testing)
- IPFS daemon (local or remote like Pinata)
- Ethereum testnet (Sepolia) for bridge (Infura, private key)
- Chainlink node/oracle (for production bridge verification)
- Rust (for libp2p bindings via maturin/pyo3)

## Installation

1. **Clone the Repo**:
   ```
   git clone https://github.com/Qu_bitcoin/qubitcoin.git
   cd qubitcoin
   ```

2. **Set Up Virtual Environment**:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   - Copy `.env.example` to `.env` and fill in values (e.g., `IBM_TOKEN`, `DATABASE_URL=cockroach://...` with `sslmode=require` for prod).
   - Run `scripts/generate_keys.py` to create Dilithium keys; update `secure_key.env`.
   - For bridge: Set `INFURA_URL`, `ETH_PRIVATE_KEY`, `CHAINLINK_ORACLE`, etc.

4. **Initialize Database**:
   ```
   cockroach sql --url "$DATABASE_URL" < src/db_scheme.sql
   ```

5. **Docker Setup (Recommended for Production)**:
   ```
   docker-compose up -d  # Starts CockroachDB cluster, IPFS, and nodes
   ```

## Usage

### Running a Full Node
```
python src/node.py  # Starts mining cycle, P2P listeners, FastAPI RPC on port 5000
```
- Modes: Set `USE_LOCAL_ESTIMATOR=true` in `.env` for exact sim (testing); `false` for IBM.
- Debug: `DEBUG=true` for rich logs/tables (VQE energies, etc.).
- Mining: Loops fetch challenges, VQE optimize, submit proofs; broadcasts via libp2p.

### RPC Endpoints (for Wallets/Light Clients)
- `/balance?address=...`: Get balance.
- `/transfer`: POST JSON for signed transfers (propagated via P2P).
- `/bridge_to_chain`: Lock QBC, mint wQBC (oracle-verified).
- More: `/get_challenge`, `/submit_proof`, `/verify_token`, etc.

### Testing
```
pytest tests/  # Covers VQE convergence (>95% fidelity), P2P sync, fork resolution
```

### Multi-Node Deployment
- Use Docker Compose for clusters: Scale nodes with `PEER_SEEDS` for bootstraps.
- Monitor with Prometheus: `/metrics` endpoint (e.g., validation_energy gauge).

## Contributing

Contributions welcome! Focus on decentralization, perf (Rust bindings), quantum fidelity. Follow these steps:
1. Fork the repo.
2. Create a branch: `git checkout -b feature/xyz`.
3. Commit: `git commit -m 'Add xyz'`.
4. Push: `git push origin feature/xyz`.
5. Open a PR, reference white paper pages (e.g., "Aligns with page 10 VQE").

Issues: Report bugs, suggest features—tie to white paper (e.g., page 12 gossip).

## License

This project is licensed under the Creative Commons Attribution 4.0 International License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Inspired by Satoshi Nakamoto's Bitcoin.
- Theoretical foundations: S.J. Gates (Adinkra/SUSY), IBM Qiskit team.
- Tools: libp2p, IPFS, Chainlink, CockroachDB.

## Contact

- Twitter: [@Qu_bitcoin](https://twitter.com/Qu_bitcoin)
- Author: Ash (SUSY Labs, Brisbane, AU)
- For questions: Open an issue or DM on X.

*Project status: Production-ready as of Jan 2026. Next: Testnet launch Feb 2026.*
```
