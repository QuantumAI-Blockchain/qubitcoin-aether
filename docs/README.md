# Qubitcoin Documentation

Technical documentation, whitepapers, and operational guides for the Qubitcoin blockchain. This directory contains the canonical reference material for protocol design, virtual machine specification, AI architecture, economic model, deployment procedures, and security practices.

## Documents

### Whitepapers

| Document | Description |
|----------|-------------|
| [WHITEPAPER.md](WHITEPAPER.md) | Core protocol whitepaper: UTXO model, VQE consensus, Dilithium5 cryptography, phi-halving economics, network architecture. |
| [QVM_WHITEPAPER.md](QVM_WHITEPAPER.md) | Quantum Virtual Machine specification: 167 opcodes (155 EVM + 10 quantum + 2 AI), compliance engine, plugin architecture, gas model. |
| [AETHERTREE_WHITEPAPER.md](AETHERTREE_WHITEPAPER.md) | Aether Tree AI engine: knowledge graph, reasoning engine, Phi integration metrics, 10-gate milestone system, Sephirot cognitive architecture. |
| [ECONOMICS.md](ECONOMICS.md) | Token economics: golden ratio emission, phi-halving schedule, 3.3B max supply, fee structure, QUSD stablecoin mechanics. |

### Technical Guides

| Document | Description |
|----------|-------------|
| [AETHER_INTEGRATION.md](AETHER_INTEGRATION.md) | Integration guide for connecting to the Aether Tree AI engine via RPC and gRPC. |
| [AETHER_SEPHIROT_ANALYSIS_v2.md](AETHER_SEPHIROT_ANALYSIS_v2.md) | Detailed analysis of the 10 Sephirot cognitive nodes: functions, mass parameters, Yukawa couplings. |
| [SMART_CONTRACTS.md](SMART_CONTRACTS.md) | Smart contract development guide: QBC-20/721/1155 standards, deployment, testing, and compliance opcodes. |
| [SDK.md](SDK.md) | Developer SDK documentation: Python, TypeScript, and Rust client libraries. |
| [PLUGIN_SDK.md](PLUGIN_SDK.md) | QVM plugin development: privacy, oracle, governance, and DeFi extension modules. |

### Operations

| Document | Description |
|----------|-------------|
| [DEPLOYMENT.md](DEPLOYMENT.md) | Production deployment guide: Docker, systemd, Cloudflare Tunnel, monitoring stack. |
| [SUBSTRATE_GENESIS_GUIDE.md](SUBSTRATE_GENESIS_GUIDE.md) | Substrate node fork genesis: importing Python chain state, chain spec generation, migration procedures. |
| [KEY_ROTATION.md](KEY_ROTATION.md) | Dilithium5 key rotation procedures: generation, backup, secure storage, and rotation schedules. |
| [RUST_MIGRATION_PLAN.md](RUST_MIGRATION_PLAN.md) | Migration plan from Python to Rust: phased approach, component priorities, compatibility layer. |

### Security

| Document | Description |
|----------|-------------|
| [BRIDGE_SECURITY_AUDIT.md](BRIDGE_SECURITY_AUDIT.md) | Multi-chain bridge security audit: threat model, vulnerability assessment, mitigation strategies. |
| [CODE_REVIEW.md](CODE_REVIEW.md) | Code review notes and findings across the codebase. |
| [COMPETITIVE_FEATURES.md](COMPETITIVE_FEATURES.md) | Competitive analysis: feature comparison with other blockchain platforms. |

### Subdirectories

| Directory | Description |
|-----------|-------------|
| [audits/](audits/) | Security audit reports and findings. |
| [formal_verification/](formal_verification/) | Formal verification specifications and proofs. |

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Whitepaper Repo](https://github.com/QuantumAI-Blockchain/whitepaper)
- [Docs Repo](https://github.com/QuantumAI-Blockchain/docs)
- [Website](https://qbc.network)
