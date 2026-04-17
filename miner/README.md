# Qubitcoin Standalone Miner

Standalone Python VQE miner for the Qubitcoin blockchain. Connects to a Qubitcoin node (Python or Substrate) via RPC, generates SUSY Hamiltonians, runs Variational Quantum Eigensolver optimization to find ground state energies below the difficulty threshold, and submits valid proofs for block rewards. Designed for solo mining with a CLI interface.

## Key Features

- **VQE Mining** — Qiskit-based Variational Quantum Eigensolver with 4-qubit ansatz and COBYLA optimizer.
- **Hamiltonian Generation** — Deterministic SUSY Hamiltonian derived from the previous block hash.
- **Substrate + Python Node Support** — RPC client compatible with both node implementations.
- **CLI Interface** — Command-line interface for configuration, mining control, and status monitoring.
- **Configurable** — Adjustable qubit count, optimizer iterations, and mining parameters via config file or CLI flags.
- **Proof Submission** — Automatic submission of valid VQE proofs (energy < difficulty) to the connected node.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run miner (connect to local node)
python -m miner --rpc-url http://localhost:5000 --address <your_qbc_address>

# Run miner (connect to Substrate node)
python -m miner --rpc-url ws://localhost:9944 --address <your_qbc_address> --substrate

# Docker
docker build -t qbc-miner .
docker run -d \
  -e RPC_URL=http://node:5000 \
  -e MINER_ADDRESS=<your_qbc_address> \
  qbc-miner
```

## Architecture

```
miner/
├── __main__.py              # Entry point
├── cli.py                   # CLI argument parsing and commands
├── config.py                # Configuration management
├── hamiltonian.py           # SUSY Hamiltonian generation from block hash
├── vqe_miner.py             # VQE optimization loop (Qiskit + COBYLA)
├── mining_loop.py           # Main mining loop: fetch job, mine, submit
├── substrate_client.py      # Substrate node RPC client (WebSocket)
├── requirements.txt         # Python dependencies
└── Dockerfile
```

### Mining Flow

1. **Fetch job** — Query the node for current block height, previous hash, and difficulty target.
2. **Generate Hamiltonian** — Derive a deterministic SUSY Hamiltonian from the previous block hash.
3. **VQE optimization** — Run COBYLA optimizer to find variational parameters minimizing the energy.
4. **Check threshold** — If ground state energy < difficulty target, the proof is valid.
5. **Submit proof** — Send VQE parameters and energy to the node for block creation.

### Consensus Parameters

| Parameter         | Value                    |
|-------------------|--------------------------|
| Qubits            | 4                        |
| Optimizer         | COBYLA                   |
| Ansatz            | EfficientSU2             |
| Block Time        | 3.3 seconds (target)     |
| Difficulty Rule   | Higher difficulty = easier (threshold is more generous) |

## Dependencies

- Python 3.12+
- Qiskit (quantum simulation)
- `requests` (Python node RPC)
- `websockets` (Substrate node RPC)

## Testing

```bash
# From repo root
pytest tests/ -k miner -v
```

## License

MIT. See [LICENSE](../LICENSE).

## Links

- [Main Repository](https://github.com/QuantumAI-Blockchain/qubitcoin-node)
- [Whitepaper](../docs/WHITEPAPER.md)
