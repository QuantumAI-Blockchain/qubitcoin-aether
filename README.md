# Qubitcoin (QBC) - Quantum-Secured Cryptocurrency

A supersymmetric framework for physics-secured digital assets using Proof-of-SUSY-Alignment consensus.

## Features

- ✨ **Quantum Security**: Proofs secured by VQE optimization and no-cloning theorem
- 🔐 **Post-Quantum Cryptography**: Dilithium signatures
- 💎 **Fixed Supply**: 21 million QBC with halvings every 210,000 blocks
- ⚡ **Energy Efficient**: ~50mJ per proof vs Bitcoin's 700kWh per block
- 🌐 **Distributed**: P2P network with IPFS snapshots
- 📊 **Observable**: Prometheus metrics and rich CLI output

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- 16GB RAM (32GB recommended)
- 500GB SSD

### Installation
```bash
# Clone repository
git clone https://github.com/susylabs/qubitcoin
cd qubitcoin

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Generate keys
python scripts/generate_keys.py
python scripts/generate_ed25519.py

# Start infrastructure
docker compose up -d

# Initialize database
docker exec -i qbc-cockroachdb cockroach sql --insecure --database=qbc < scripts/migrations.sql

# Run node
python src/run_node.py
```

### Access Interfaces

- **Node RPC**: http://localhost:5000
- **CockroachDB UI**: http://localhost:8080
- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000
- **IPFS Gateway**: http://localhost:8081

## Architecture
```
qubitcoin/
├── src/qubitcoin/
│   ├── database/        # CockroachDB operations
│   ├── quantum/         # VQE engine & crypto
│   ├── consensus/       # PoSA validation
│   ├── mining/          # Block creation
│   ├── network/         # RPC & P2P
│   ├── storage/         # IPFS snapshots
│   └── utils/           # Logging & metrics
├── scripts/             # Helper scripts
├── tests/               # Test suite
└── config/              # Configuration files
```

## Development

### Run Tests
```bash
pytest tests/ -v --cov=qubitcoin
```

### Code Formatting
```bash
black src/
flake8 src/
mypy src/
```

### Build Binary
```bash
pyinstaller qubitcoin.spec
# Binary: dist/qubitcoin-node
```

## API Endpoints

### Blockchain

- `GET /` - Node info
- `GET /health` - Health check
- `GET /block/{height}` - Get block
- `GET /chain/info` - Chain information

### Wallet

- `GET /balance/{address}` - Get balance
- `GET /utxos/{address}` - Get UTXOs

### Mining

- `GET /mining/stats` - Mining statistics
- `POST /mining/start` - Start mining
- `POST /mining/stop` - Stop mining

### Quantum

- `GET /quantum/info` - Backend information
- `POST /quantum/verify_proof` - Verify proof

### Monitoring

- `GET /metrics` - Prometheus metrics

## Configuration

Edit `.env`:
```bash
# Node Identity
ADDRESS=your-address
PRIVATE_KEY_HEX=your-private-key
PUBLIC_KEY_HEX=your-public-key

# Quantum Mode
USE_LOCAL_ESTIMATOR=true  # false for IBM Quantum

# Mining
AUTO_MINE=true
MINING_INTERVAL=10

# Database
DATABASE_URL=postgresql+psycopg2://root@localhost:26257/qbc?sslmode=disable
```

## White Paper

See `docs/whitepaper.pdf` for detailed technical specifications.

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -am 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open Pull Request

## License

MIT License - see LICENSE file

## Contact

- Website: https://qubitcoin.io
- Discord: https://discord.gg/qubitcoin
- Email: contact@susylabs.io

## Acknowledgments

- Quantum computing powered by Qiskit
- Database by CockroachDB
- Storage by IPFS
