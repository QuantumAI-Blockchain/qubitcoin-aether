# Qubitcoin (QBC)
### Quantum-Secured Cryptocurrency with Supersymmetric Consensus

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Qiskit](https://img.shields.io/badge/Qiskit-1.0.0-purple.svg)](https://qiskit.org/)
[![CockroachDB](https://img.shields.io/badge/CockroachDB-v23.2+-green.svg)](https://www.cockroachlabs.com/)

---

## 🌟 Overview

**Qubitcoin** is a physics-backed Layer 1 blockchain that combines quantum computing, post-quantum cryptography, and supersymmetric (SUSY) principles to create a truly quantum-resistant digital currency. Unlike traditional proof-of-work systems, Qubitcoin uses **Proof-of-SUSY-Alignment (PoSA)** where miners solve variational quantum eigenvalue (VQE) problems to secure the network.

### Key Features

- ⚛️ **Quantum Mining** - VQE optimization using Qiskit for block production
- 🔐 **Post-Quantum Security** - Dilithium2 signatures resistant to Shor's algorithm
- 🌌 **Physics-Backed Economics** - Golden ratio (φ) emission curve over 40-50 years
- 📜 **Smart Contracts** - Quantum-native contracts (tokens, NFTs, launchpads, governance)
- 🔗 **Ethereum Bridge** - Wrapped QBC (wQBC) for DeFi interoperability
- 🌐 **P2P Network** - Distributed consensus with libp2p
- 💾 **IPFS Snapshots** - Decentralized chain state storage
- 📊 **3.3B Supply Cap** - Mathematically perfect with φ-based halvings

---

## 🎯 Why Qubitcoin?

### The Quantum Threat
Current cryptocurrencies like Bitcoin use ECDSA signatures, which will be broken by quantum computers running Shor's algorithm. Qubitcoin addresses this existential threat **now**, not later.

### Physics-First Design
Every design decision is rooted in quantum mechanics and supersymmetry:
- **PoSA Consensus** - Miners find ground states of Hamiltonian systems
- **No-Cloning Theorem** - Guarantees transaction uniqueness at quantum level
- **SUSY Multiplets** - Enable privacy-preserving swaps with >95% fidelity
- **Golden Ratio Economics** - φ appears naturally in quantum spectra

### Research Value
Every block solved contributes to fundamental physics research by mapping the energy landscape of supersymmetric systems. All solved Hamiltonians are shared openly for academic use.

---

## 📊 Economics

### Golden Ratio Emission Curve

```
Reward(k) = 50 × (0.618)^k  QBC per block
where k = era number, φ = 1.618033988749...
```

| Metric | Value |
|--------|-------|
| **Total Supply** | 3,300,000,000 QBC |
| **Initial Reward** | 50 QBC/block |
| **Block Time** | 5 seconds |
| **Halving Factor** | 0.618 (φ⁻¹) |
| **Halving Interval** | 25,228,800 blocks (~4 years) |
| **First Era Emission** | ~315M QBC (9.5% of supply) |
| **95% Emitted** | ~Year 30 |
| **99% Emitted** | ~Year 40 |

This gradual decay ensures sustainable long-term security while incentivizing early adoption.

---

## 🛠️ Technology Stack

### Core Components
- **Python 3.11+** - Node implementation
- **Qiskit 1.0** - Quantum circuit simulation and VQE
- **CockroachDB** - Distributed SQL database
- **FastAPI** - RPC/REST API
- **SQLAlchemy** - ORM and query builder
- **IPFS** - Decentralized snapshot storage
- **Dilithium2** - Post-quantum signatures

### Optional Integrations
- **IBM Quantum** - Real quantum hardware (via Qiskit Runtime)
- **Pinata** - IPFS pinning service
- **Chainlink** - Ethereum bridge oracles
- **Prometheus + Grafana** - Monitoring and metrics

---

## 🚀 Quick Start

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3.11 python3.11-venv postgresql-client

# Install CockroachDB
wget -qO- https://binaries.cockroachdb.com/cockroach-v23.2.0.linux-amd64.tgz | tar xvz
sudo cp cockroach-v23.2.0.linux-amd64/cockroach /usr/local/bin/
```

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/qubitcoin.git
cd qubitcoin

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate node keys
python3 scripts/generate_keys.py
python3 scripts/generate_ed25519.py

# Configure environment
cp .env.example .env
# Edit .env with your generated keys

# Start CockroachDB
cockroach start-single-node --insecure --listen-addr=localhost:26257 --background

# Initialize database
cockroach sql --insecure < scripts/init_db.sql
cockroach sql --insecure --database=qbc < scripts/migrations.sql

# Start node
cd src
python3 run_node.py
```

### Verify Installation

```bash
# In another terminal
curl http://localhost:5000/ | python3 -m json.tool

# Expected output:
{
  "node": "Qubitcoin Full Node v2.0",
  "network": "mainnet",
  "height": 0,
  "address": "your_node_address",
  "economics": {
    "model": "Golden Ratio (φ = 1.618...)",
    "current_reward": 50.0
  }
}
```

---

## 📡 API Reference

### Node Information
```bash
GET /                    # Node info and status
GET /health             # Health check
GET /info               # Detailed node information
```

### Blockchain Queries
```bash
GET /block/{height}           # Get block by height
GET /chain/info              # Chain statistics
GET /chain/tip               # Latest block
GET /balance/{address}       # Address balance
GET /utxos/{address}         # Unspent outputs
```

### Economics
```bash
GET /economics/emission           # Current emission stats
GET /economics/simulate?years=40  # Simulate emission schedule
```

### Smart Contracts
```bash
POST /contracts/deploy           # Deploy new contract
POST /contracts/execute          # Execute contract method
GET  /contracts/{id}             # Get contract details
GET  /contracts                  # List contracts
GET  /tokens/{id}/balance/{addr} # Token balance
```

### Mining
```bash
GET  /mining/stats    # Mining statistics
POST /mining/start    # Start mining
POST /mining/stop     # Stop mining
```

Full API documentation: [API.md](docs/API.md)

---

## 🎨 Smart Contracts

Qubitcoin supports quantum-native smart contracts with 6 built-in types:

### 1. Token Contracts (ERC-20 style)
```python
# Deploy a fungible token
{
  "contract_type": "token",
  "contract_code": {
    "symbol": "MYTOKEN",
    "name": "My Custom Token",
    "total_supply": "10000000",
    "decimals": 8
  }
}
```

### 2. NFT Contracts (ERC-721 style)
Non-fungible tokens with metadata storage.

### 3. Launchpad Contracts
Token sales and IDO platforms:
```python
{
  "contract_type": "launchpad",
  "contract_code": {
    "raise_target": "1000",      # QBC to raise
    "token_price": "0.1",        # QBC per token
    "duration_hours": 168        # 7 days
  }
}
```

### 4. Escrow Contracts
Multi-party agreements with atomic settlement.

### 5. Governance Contracts
On-chain voting and DAO management.

### 6. Quantum Gate Contracts
Unlockable with valid VQE proofs:
```python
{
  "contract_type": "quantum_gate",
  "contract_code": {
    "gate_condition": {
      "energy_threshold": 0.3,
      "fidelity_requirement": 0.95
    }
  }
}
```

See [CONTRACTS.md](docs/CONTRACTS.md) for full documentation.

---

## ⚛️ Proof-of-SUSY-Alignment (PoSA)

### How It Works

1. **Hamiltonian Generation** - Each block candidate includes a random SUSY Hamiltonian
2. **VQE Optimization** - Miners use variational quantum algorithms to find ground state
3. **Difficulty Check** - Ground state energy must be below difficulty threshold
4. **Proof Submission** - Optimized parameters + energy form the quantum proof
5. **Validation** - Network verifies proof by re-running VQE
6. **Consensus** - Valid proofs with lowest energy win (if multiple in same slot)

### Energy-Based Mining

```python
# Simplified mining loop
hamiltonian = generate_hamiltonian(num_qubits=4)
params, energy = optimize_vqe(hamiltonian)

if energy < difficulty:
    proof = {
        'challenge': hamiltonian,
        'params': params,
        'energy': energy,
        'signature': sign(params, private_key)
    }
    broadcast_block(proof)
```

### Quantum Resistance
- **Mining**: VQE is a quantum algorithm, giving no advantage to quantum attackers
- **Signatures**: Dilithium2 is lattice-based, resistant to Grover's and Shor's algorithms
- **Transaction Privacy**: SUSY swaps use quantum entanglement properties

---

## 🌐 Network Architecture

### P2P Layer
- **Protocol**: libp2p with GossipSub
- **Topics**: `/qbc/blocks`, `/qbc/txns`, `/qbc/contracts`
- **Discovery**: DHT-based peer discovery
- **Sync**: Headers-first + UTXO set validation

### Storage
- **CockroachDB**: ACID transactions, distributed consensus
- **IPFS**: Periodic blockchain snapshots (every 100 blocks)
- **Local Cache**: Recent block headers and UTXO set

### Bridge to Ethereum
- **wQBC Token**: ERC-20 on Ethereum
- **Lock/Mint**: QBC locked on native chain → wQBC minted on Ethereum
- **Burn/Release**: wQBC burned → QBC released
- **Oracle**: Chainlink price feeds for bridge security

---

## 🔬 Research Contributions

### Open Data
Every solved Hamiltonian is stored on-chain and made publicly available:

```sql
SELECT hamiltonian, params, energy, block_height
FROM solved_hamiltonians
ORDER BY energy ASC
LIMIT 100;
```

Researchers can use this data to:
- Study SUSY breaking patterns
- Map energy landscapes of N=2 multiplets
- Develop better VQE optimization strategies
- Validate quantum hardware performance

### Academic Partnerships
We welcome collaborations with:
- Quantum computing labs
- High energy physics departments  
- Cryptography research groups
- Distributed systems researchers

---

## 📚 Documentation

- [**Whitepaper**](WHITEPAPER.md) - Complete technical specification
- [**API Reference**](docs/API.md) - RPC endpoint documentation
- [**Contract Guide**](docs/CONTRACTS.md) - Smart contract development
- [**Mining Guide**](docs/MINING.md) - How to mine QBC
- [**Bridge Guide**](docs/BRIDGE.md) - Using wQBC on Ethereum
- [**Upgrade Guide**](UPGRADE_GUIDE.md) - v1 → v2 migration

---

## 🛣️ Roadmap

### Phase 1: Testnet ✅ (Current)
- [x] Core blockchain implementation
- [x] VQE mining engine
- [x] Smart contract framework
- [x] Golden ratio economics
- [ ] Multi-node P2P testing
- [ ] Performance optimization (target 1000 TPS)

### Phase 2: Mainnet Launch (Q1 2026)
- [ ] Security audit
- [ ] Bridge deployment on Ethereum
- [ ] Mobile wallet (iOS/Android)
- [ ] Block explorer
- [ ] Public testnet with faucet

### Phase 3: Ecosystem Growth (Q2-Q4 2026)
- [ ] DEX integration (wQBC trading)
- [ ] Launchpad platform for token sales
- [ ] Governance DAO
- [ ] Hardware wallet support
- [ ] Real quantum hardware mining (IBM Quantum)

### Phase 4: Advanced Features (2027+)
- [ ] ZK-rollups for scalability
- [ ] Cross-chain bridges (BSC, Polygon)
- [ ] Quantum internet integration
- [ ] SUSY privacy protocol v2

---

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup
```bash
# Fork and clone
git clone https://github.com/yourusername/qubitcoin.git
cd qubitcoin

# Create feature branch
git checkout -b feature/amazing-feature

# Make changes and test
python3 -m pytest tests/

# Submit PR
git push origin feature/amazing-feature
```

### Areas for Contribution
- 🐛 Bug fixes and optimizations
- 📝 Documentation improvements
- 🧪 Test coverage expansion
- 🎨 Frontend development (wallet, explorer)
- 🔬 Research and analysis
- 🌍 Internationalization

---

## 📜 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

### Physics & Mathematics
- **Edward Witten** - Supersymmetry theory
- **John Preskill** - Quantum error correction
- **Peter Shor** - Quantum algorithms (and the threat they pose!)

### Cryptography
- **CRYSTALS-Dilithium Team** - Post-quantum signatures
- **NIST** - Post-quantum cryptography standardization

### Quantum Computing
- **IBM Quantum** - Qiskit framework and quantum hardware access
- **Google Quantum AI** - VQE research and benchmarking

### Blockchain
- **Satoshi Nakamoto** - Bitcoin inspiration
- **Vitalik Buterin** - Smart contract paradigm
- **CockroachDB Team** - Distributed database technology

---

## 📞 Contact & Community

- **Website**: https://qubitcoin.io (coming soon)
- **Twitter**: [@Qubitcoin](https://twitter.com/qubitcoin)
- **Discord**: [Join our community](https://discord.gg/qubitcoin)
- **Telegram**: [QBC Official](https://t.me/qubitcoin)
- **Email**: contact@qubitcoin.io
- **GitHub**: [Issues & Discussions](https://github.com/yourusername/qubitcoin/issues)

---

## ⚠️ Disclaimer

This is experimental software. Use at your own risk. Qubitcoin is designed for research and educational purposes. While we strive for security and correctness, we cannot guarantee:

- Absence of bugs or vulnerabilities
- Protection against all attack vectors
- Value preservation or investment returns
- Regulatory compliance in all jurisdictions

**Not Financial Advice**: Cryptocurrency investments are highly speculative and risky. Do your own research.

---

## 📊 Stats

![GitHub stars](https://img.shields.io/github/stars/yourusername/qubitcoin?style=social)
![GitHub forks](https://img.shields.io/github/forks/yourusername/qubitcoin?style=social)
![GitHub issues](https://img.shields.io/github/issues/yourusername/qubitcoin)
![GitHub pull requests](https://img.shields.io/github/issues-pr/yourusername/qubitcoin)

---

<p align="center">
  <b>Built with ⚛️ Quantum Physics | 🔐 Post-Quantum Crypto | 🌌 Supersymmetry</b>
</p>

<p align="center">
  <i>The future of money is quantum-resistant</i>
</p>

---

**Current Version**: 2.0.0  
**Last Updated**: January 27, 2026  
**Maintainers**: [@Qu_bitcoin](https://github.com/Qu_bitcoin)

