# Qubitcoin (QBC)

> **Quantum-Secured Cryptocurrency with SUSY Economics**

A next-generation blockchain combining quantum computing, post-quantum cryptography, and supersymmetric economic principles.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status: Production Ready](https://img.shields.io/badge/status-production%20ready-green.svg)]()

---

## 🌟 **Key Features**

### **Quantum-Secured Mining**
- **Proof-of-SUSY-Alignment (PoSA)** consensus
- Variational Quantum Eigensolver (VQE) mining
- ASIC-resistant quantum computation
- Contributes to supersymmetric physics research

### **Post-Quantum Cryptography**
- CRYSTALS-Dilithium signatures
- Resistant to quantum computer attacks
- Future-proof cryptographic security

### **SUSY Economics**
- Golden ratio (φ = 1.618) halvings
- 3.3 billion max supply
- 3.3 second block time
- 33-year emission schedule

### **Multi-Chain Bridge**
- Native bridges to 8+ blockchains
- Ethereum, Polygon, BSC, Arbitrum, Optimism, Avalanche, Base, Solana
- Decentralized validator network

### **QUSD Stablecoin**
- Algorithmic USD-pegged stablecoin
- Multi-collateral support (QBC, ETH, USDT, USDC, DAI)
- Over-collateralized positions

---

## 📊 **Network Specifications**

| Parameter | Value |
|-----------|-------|
| **Ticker** | QBC |
| **Max Supply** | 3.3 billion QBC |
| **Block Time** | 3.3 seconds |
| **Initial Reward** | 15.27 QBC |
| **Halving Interval** | 15,474,020 blocks (~1.618 years) |
| **Consensus** | Proof-of-SUSY-Alignment (PoSA) |
| **Mining Algorithm** | VQE (Variational Quantum Eigensolver) |
| **Signature Scheme** | CRYSTALS-Dilithium (post-quantum) |
| **Total Emission Period** | ~33 years |

---

## 🚀 **Quick Start**

### **Prerequisites**
```bash
# System requirements
- Python 3.11+
- CockroachDB v24.2+
- IPFS (Kubo) v0.30.0+
- 4GB+ RAM
- 20GB+ disk space
```

### **Installation**
```bash
# Clone repository
git clone https://github.com/qubitcoin/qubitcoin.git
cd qubitcoin

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate node keys
python3 scripts/generate_keys.py

# Copy keys to .env
cat secure_key.env >> .env

# Initialize database
cockroach start-single-node --insecure --listen-addr=localhost:26257 &
cockroach sql --insecure -e "CREATE DATABASE qbc;"
cockroach sql --insecure --database=qbc < scripts/migrations.sql
cockroach sql --insecure --database=qbc < scripts/multi_chain_bridge.sql

# Start IPFS
ipfs daemon &

# Run node
cd src
python3 run_node.py
```

### **Docker Deployment**
```bash
# Using Docker Compose
docker-compose up -d

# Check logs
docker-compose logs -f qubitcoin
```

---

## 🔬 **How It Works**

### **Proof-of-SUSY-Alignment Mining**

1. **Challenge Generation**: Node generates random supersymmetric Hamiltonian
2. **VQE Optimization**: Miner uses quantum algorithms to find ground state
3. **Proof Submission**: Submit optimized parameters + energy eigenvalue
4. **Validation**: Network verifies quantum proof meets difficulty target
5. **Block Reward**: Miner receives QBC for valid proof

### **Why Quantum Mining?**

- **Research Contribution**: Every mined block advances SUSY physics research
- **ASIC Resistance**: Quantum algorithms can't be trivially parallelized
- **Future-Proof**: Designed for quantum computing era
- **Verifiable**: Classical computers can verify quantum proofs

---

## 🌉 **Multi-Chain Bridges**

### **Supported Chains**

| Chain | Status | wQBC Contract |
|-------|--------|---------------|
| Ethereum | 🟢 Ready | TBD |
| Polygon | 🟢 Ready | TBD |
| BSC | 🟢 Ready | TBD |
| Arbitrum | 🟢 Ready | TBD |
| Optimism | 🟢 Ready | TBD |
| Avalanche | 🟢 Ready | TBD |
| Base | 🟢 Ready | TBD |
| Solana | 🟢 Ready | TBD |

### **How to Bridge**
```bash
# QBC → wQBC (Ethereum example)
1. Send QBC to bridge address: qbc1bridge...
2. Include Ethereum address in memo
3. Wait 6 confirmations
4. Receive wQBC on Ethereum

# wQBC → QBC
1. Call bridge.withdraw(amount, qbc_address) on Ethereum
2. Wait 12 confirmations
3. Receive QBC on Qubitcoin
```

See [MULTICHAIN_BRIDGE_GUIDE.md](docs/MULTICHAIN_BRIDGE_GUIDE.md) for details.

---

## 💰 **QUSD Stablecoin**

Algorithmic stablecoin pegged to 1 USD, backed by:
- **QBC** (native token)
- **ETH** (Ethereum)
- **USDT, USDC, DAI** (stablecoins)

**Collateralization Ratios:**
- Stablecoins: 105%
- Volatile assets (QBC, ETH): 150%

**Auto-Liquidation:** Positions liquidated at threshold to maintain peg

---

## 📈 **Economics**

### **Golden Ratio Halvings**
```
Era 0 (Years 0-1.618):    15.27 QBC/block
Era 1 (Years 1.618-3.236):  9.437 QBC/block
Era 2 (Years 3.236-4.854):  5.833 QBC/block
Era 3 (Years 4.854-6.472):  3.604 QBC/block
...continues for ~33 years
```

### **Supply Schedule**

| Year | Cumulative Supply | % of Max Supply |
|------|-------------------|-----------------|
| 1 | ~750M QBC | 22.7% |
| 5 | ~2.1B QBC | 63.6% |
| 10 | ~2.8B QBC | 84.8% |
| 20 | ~3.2B QBC | 97.0% |
| 33 | 3.3B QBC | 100% |

See [ECONOMICS.md](docs/ECONOMICS.md) for detailed analysis.

---

## 🛠️ **Development**

### **Project Structure**
```
qubitcoin/
├── src/qubitcoin/
│   ├── consensus/       # Proof-of-SUSY-Alignment
│   ├── quantum/         # VQE engine
│   ├── mining/          # Mining loop
│   ├── database/        # CockroachDB layer
│   ├── network/         # RPC & P2P
│   ├── stablecoin/      # QUSD engine
│   ├── bridge/          # Multi-chain bridges
│   └── contracts/       # Native smart contracts
├── scripts/             # Utilities & migrations
├── tests/              # Unit & integration tests
└── docs/               # Documentation
```

### **Running Tests**
```bash
# Full system test
python3 test_system.py

# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/
```

### **API Documentation**

RPC API available at `http://localhost:5000`

**Key Endpoints:**
- `GET /` - Node info
- `GET /chain/info` - Blockchain stats
- `GET /balance/{address}` - Get balance
- `GET /mining/stats` - Mining stats
- `POST /mining/start` - Start mining
- `GET /bridge/stats` - Bridge statistics

Full API docs: [API.md](docs/API.md)

---

## 🔒 **Security**

### **Audits**
- [ ] Smart contract audit (pending)
- [ ] Quantum algorithm review (pending)
- [ ] Bridge security audit (pending)

### **Bug Bounty**
Coming soon - rewards for responsible disclosure

### **Responsible Disclosure**
security@qubitcoin.org

---

## 📚 **Documentation**

- [Whitepaper](docs/WHITEPAPER.md) - Technical overview
- [Economics](docs/ECONOMICS.md) - SUSY Economics explained
- [Bridge Guide](docs/MULTICHAIN_BRIDGE_GUIDE.md) - Cross-chain bridges
- [Mining Guide](docs/MINING.md) - How to mine QBC
- [API Reference](docs/API.md) - RPC endpoints

---

## 🤝 **Contributing**

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### **Areas We Need Help**
- Quantum algorithm optimization
- Bridge validators
- Frontend development
- Documentation
- Testing

---

## 📜 **License**

MIT License - see [LICENSE](LICENSE) for details

---

## 🌐 **Links**

- **Website**: https://qubitcoin.org
- **Explorer**: https://explorer.qubitcoin.org
- **Twitter**: @Qubitcoin
- **Discord**: https://discord.gg/qubitcoin
- **GitHub**: https://github.com/qubitcoin

---

## ⚠️ **Disclaimer**

Qubitcoin is experimental software. Use at your own risk. 
Cryptocurrency investments are subject to market volatility.

---

**Built with ❤️ by the Qubitcoin community**

*"Where quantum meets consensus"*
