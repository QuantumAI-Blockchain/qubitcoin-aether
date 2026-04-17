# Qubitcoin QVM

Production-grade Quantum Virtual Machine (QVM) written in Go. Implements 167 opcodes: 155 standard EVM opcodes, 10 quantum-computing opcodes, and 2 AI opcodes. Provides full EVM compatibility for Solidity smart contracts while extending execution with quantum state manipulation, on-chain compliance, and AI integration. Supports QBC-20, QBC-721, and QBC-1155 token standards.

## Key Features

- **167 Opcodes** — Full EVM instruction set (155) plus quantum (0xF0-0xF9) and AI (0xFA-0xFB) extensions.
- **Compliance Engine** — VM-level KYC/AML/sanctions enforcement via `QCOMPLIANCE` (0xF5) and `QRISK` (0xF6) opcodes.
- **Plugin Architecture** — Modular plugin system for privacy, oracle, governance, and DeFi extensions.
- **EVM Compatible** — Deploy and execute standard Solidity contracts. Tooling-compatible gas metering.
- **Quantum Opcodes** — `QCREATE`, `QMEASURE`, `QENTANGLE`, `QGATE`, `QVERIFY` for quantum state operations.
- **Cross-Chain Bridge Opcodes** — `QBRIDGE_ENTANGLE` (0xF8) and `QBRIDGE_VERIFY` (0xF9) for bridge proof verification.
- **Token Standards** — QBC-20 (fungible), QBC-721 (NFT), QBC-1155 (multi-token), ERC-20-QC (compliance-aware).
- **Production Deployment** — Distroless Docker image, Kubernetes manifests, health probes.

## Quick Start

```bash
# Build
make build

# Run QVM node
./bin/qvm --config config.yaml

# CLI tools
./bin/qvm-cli deploy --bytecode contract.bin
./bin/qvm-cli call --address 0x... --method "transfer(address,uint256)"

# Docker
docker build -t qubitcoin-qvm .
docker run -d -p 8545:8545 qubitcoin-qvm

# Tests
make test
```

## Architecture

```
qubitcoin-qvm/
├── cmd/
│   ├── qvm/               # QVM server binary
│   ├── qvm-cli/           # Command-line interface
│   └── plugin-loader/     # Dynamic plugin loader
├── pkg/
│   ├── vm/                # Core VM: interpreter, stack, memory, opcodes (167)
│   ├── state/             # World state: accounts, storage, trie
│   ├── compliance/        # KYC/AML/sanctions engine
│   ├── crypto/            # Keccak-256, signature verification
│   ├── database/          # State persistence
│   ├── rpc/               # JSON-RPC server (eth_* compatible)
│   └── plugin/            # Plugin SDK and registry
├── tests/                 # Integration and opcode tests
├── deployments/           # Kubernetes manifests, Dockerfiles
├── Makefile
└── go.mod
```

### Quantum Opcodes

| Opcode           | Hex  | Gas    | Description                      |
|------------------|------|--------|----------------------------------|
| `QCREATE`        | 0xF0 | 5,000+ | Create quantum state             |
| `QMEASURE`       | 0xF1 | 3,000  | Measure and collapse state       |
| `QENTANGLE`      | 0xF2 | 10,000 | Create entangled pair            |
| `QGATE`          | 0xF3 | 2,000  | Apply quantum gate               |
| `QVERIFY`        | 0xF4 | 8,000  | Verify quantum proof             |
| `QCOMPLIANCE`    | 0xF5 | 15,000 | KYC/AML/sanctions check          |
| `QRISK`          | 0xF6 | 5,000  | SUSY risk score                  |
| `QRISK_SYSTEMIC` | 0xF7 | 10,000 | Systemic risk query              |
| `QBRIDGE_ENTANGLE` | 0xF8 | 20,000 | Cross-chain entanglement       |
| `QBRIDGE_VERIFY` | 0xF9 | 15,000 | Cross-chain bridge proof         |

## Testing

```bash
# All tests
make test

# Specific package
go test ./pkg/vm/... -v

# Benchmarks
go test ./pkg/vm/... -bench=.
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [QVM Repo](https://github.com/QuantumAI-Blockchain/qubitcoin-qvm)
- [QVM Whitepaper](../docs/QVM_WHITEPAPER.md)
