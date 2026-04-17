# Qubitcoin Substrate Node

Hybrid Substrate node for the Qubitcoin blockchain, built on Polkadot SDK 0.57. Implements VQE-gated block authoring with on-chain re-verification, weighted fork choice, GRANDPA finality, and seven custom pallets covering UTXO management, post-quantum cryptography, and AI anchor points. Designed for seamless migration from the existing Python-based chain with fork genesis support.

## Key Features

- **VQE-Gated Block Authoring** — Blocks require valid Variational Quantum Eigensolver proofs; on-chain re-verification via the `vqe-verifier` crate prevents invalid blocks from entering the chain.
- **Weighted Fork Choice** — Custom fork selection rule that factors VQE proof quality and chain weight, not just longest chain.
- **7 Custom Pallets** — `qbc-utxo`, `qbc-consensus`, `qbc-dilithium`, `qbc-economics`, `qbc-qvm-anchor`, `qbc-aether-anchor`, `qbc-reversibility`.
- **GRANDPA Finality** — Deterministic finality via GRANDPA consensus gadget.
- **Post-Quantum P2P** — ML-KEM-768 (Kyber) key encapsulation + AES-256-GCM encrypted transport sessions.
- **Poseidon2 ZK Hashing** — Goldilocks-field Poseidon2 for ZK circuit compatibility (complements SHA3-256 for block hashing).
- **Fork Genesis** — Imports state from the Python chain at a specified block height for zero-downtime migration.
- **CRYSTALS-Dilithium5** — NIST Level 5 post-quantum signatures integrated at the pallet level.

## Quick Start

```bash
# Native build (skip WASM for development)
SKIP_WASM_BUILD=1 cargo build --release

# Run with development chain spec
./target/release/qubitcoin-node --dev

# Production with fork genesis
./target/release/qubitcoin-node \
  --chain mainnet \
  --fork-state fork_state.json \
  --port 30333 \
  --rpc-port 9944
```

### Docker

```bash
cd docker
docker build -t qubitcoin-substrate .
docker run -d -p 9944:9944 -p 30333:30333 qubitcoin-substrate
```

## Architecture

```
substrate-node/
├── node/                    # Client binary, service wiring, chain spec
├── runtime/                 # FRAME runtime with all 7 pallets composed
├── primitives/              # Shared types, Poseidon2 hashing, constants
├── pallets/
│   ├── qbc-utxo/            # UTXO set management and validation
│   ├── qbc-consensus/       # VQE proof validation, difficulty adjustment
│   ├── qbc-dilithium/       # CRYSTALS-Dilithium5 signature verification
│   ├── qbc-economics/       # Phi-halving emission, reward distribution
│   ├── qbc-qvm-anchor/      # QVM state root anchoring to L1
│   ├── qbc-aether-anchor/   # Aether Tree state root anchoring to L1
│   └── qbc-reversibility/   # Governor-managed transaction reversal (24h window)
├── mining/                  # VQE verifier crate for on-chain re-verification
└── crypto/
    └── kyber-transport/     # ML-KEM-768 + AES-256-GCM P2P encryption
```

### Chain Parameters

| Parameter        | Value               |
|------------------|---------------------|
| Chain ID         | 3303 (mainnet)      |
| Block Time       | 3.3 seconds         |
| Max Supply       | 3,300,000,000 QBC   |
| Consensus        | Proof-of-SUSY-Alignment (VQE) |
| Signatures       | CRYSTALS-Dilithium5 |
| Finality         | GRANDPA             |

## Testing

```bash
# Unit tests
SKIP_WASM_BUILD=1 cargo test --workspace

# Single pallet
SKIP_WASM_BUILD=1 cargo test -p qbc-consensus

# Primitives (includes Poseidon2 tests)
SKIP_WASM_BUILD=1 cargo test -p qubitcoin-primitives
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Substrate Node Repo](https://github.com/QuantumAI-Blockchain/substrate-node)
- [Whitepaper](../docs/WHITEPAPER.md)
