# Qubitcoin Security Core

Rust/PyO3 extension crate providing performance-critical security primitives for the Qubitcoin blockchain. Implements a probabilistic Bloom filter with SHA-256 double-hashing for rapid set membership tests and a stake-weighted BFT finality tracker for consensus vote accounting. Exposed to Python via PyO3 bindings with pure-Python fallback shims for graceful degradation.

## Key Features

- **Bloom Filter** — Space-efficient probabilistic set membership using SHA-256 double-hashing. Configurable false positive rate and capacity. Used for UTXO spent-set checks, mempool deduplication, and peer message filtering.
- **Finality Core** — Stake-weighted Byzantine Fault Tolerant vote tracking. Accumulates validator votes weighted by stake, determines finality when 2/3+ supermajority is reached, and tracks finalized block heights.
- **PyO3 Bindings** — Native Python integration via PyO3. Import directly as a Python module with zero-copy where possible.
- **Graceful Degradation** — Pure-Python fallback implementations ensure the node operates correctly even when the Rust extension is unavailable (at reduced performance).

## Quick Start

```bash
# Build Rust extension
cargo build --release

# Build Python extension (via maturin)
pip install maturin
maturin develop --release

# Use from Python
from security_core import BloomFilter, FinalityCore

# Bloom filter
bf = BloomFilter(capacity=1_000_000, fp_rate=0.001)
bf.add(b"utxo_hash_here")
assert bf.contains(b"utxo_hash_here")

# Finality tracker
fc = FinalityCore(threshold=0.667)
fc.add_vote(validator_id, stake_weight, block_hash)
if fc.is_finalized(block_hash):
    print("Block finalized")
```

## Architecture

```
security-core/
├── src/
│   ├── lib.rs               # PyO3 module definition
│   ├── bloom.rs             # Bloom filter (SHA-256 double-hashing)
│   └── finality.rs          # Stake-weighted BFT vote tracking
├── Cargo.toml               # Rust dependencies (pyo3, sha2)
└── pyproject.toml            # Python package configuration
```

### Bloom Filter Details

- **Hash function:** SHA-256 double-hashing (`H1(x) + i * H2(x)`) for `k` independent hash functions.
- **Optimal parameters:** Given target capacity `n` and false positive rate `p`, automatically computes optimal bit array size `m` and hash count `k`.
- **Thread-safe:** Interior mutability with atomic operations for concurrent access.

### Finality Core Details

- **Stake-weighted votes:** Each validator vote is weighted by their staked QBC balance.
- **BFT threshold:** Configurable supermajority threshold (default: 2/3).
- **Fork handling:** Tracks votes per fork; competing chains resolved by stake weight.

## Testing

```bash
# Rust tests
cargo test

# Python integration (requires maturin develop)
python -c "from security_core import BloomFilter; print('OK')"
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Security Core Repo](https://github.com/QuantumAI-Blockchain/security-core)
