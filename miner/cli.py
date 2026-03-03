"""
CLI entry point for the Qubitcoin VQE Mining Client.

Usage:
    python -m miner                     # Start mining (default settings)
    python -m miner --ws ws://host:9944 # Custom node endpoint
    python -m miner --seed "//Bob"      # Use Bob dev account
    python -m miner --qubits 4          # Override qubit count
    python -m miner --test              # Run a single VQE test (no node needed)

Environment variables (override via .env or export):
    SUBSTRATE_WS_URL     WebSocket endpoint (default: ws://127.0.0.1:9944)
    MINER_SEED           sr25519 seed phrase or //DevAccount
    NUM_QUBITS           Number of qubits (default: 4)
    VQE_REPS             Ansatz circuit repetitions (default: 2)
    VQE_MAXITER          COBYLA max iterations (default: 200)
    MAX_MINING_ATTEMPTS  Random starts per block (default: 50)
    USE_GPU_AER          Enable GPU Aer backend (default: false)
    USE_SIMULATOR        Enable CPU Aer backend (default: false)
    LOG_LEVEL            Logging level (default: INFO)
"""

import argparse
import logging
import sys

from .config import MinerConfig


def setup_logging() -> None:
    """Configure structured logging."""
    level = getattr(logging, MinerConfig.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Suppress noisy Qiskit/scipy logs
    logging.getLogger("qiskit").setLevel(logging.WARNING)
    logging.getLogger("scipy").setLevel(logging.WARNING)


def run_test() -> None:
    """
    Run a single VQE optimization test without connecting to a node.

    Useful for verifying the quantum backend works correctly.
    """
    import numpy as np
    from .vqe_miner import VqeMiner
    from .hamiltonian import generate_hamiltonian

    logger = logging.getLogger("qubitcoin.miner")
    logger.info("Running VQE test (no node connection)...")

    miner = VqeMiner()
    logger.info(f"Backend: {miner.backend_name}")

    # Generate a test Hamiltonian from a fake parent hash
    parent_hash = bytes(32)  # all zeros
    block_height = 1
    hamiltonian, seed = generate_hamiltonian(parent_hash, block_height)

    logger.info(f"Test Hamiltonian ({len(hamiltonian)} terms):")
    for pauli_str, coeff in hamiltonian:
        logger.info(f"  {pauli_str}: {coeff:+.6f}")

    # Run VQE optimization
    params, energy = miner.optimize_vqe(hamiltonian)
    energy_scaled = int(energy * MinerConfig.ENERGY_SCALE)

    logger.info(f"Optimized energy: {energy:.6f}")
    logger.info(f"Energy (scaled): {energy_scaled}")
    logger.info(f"Parameters: {len(params)} angles")
    logger.info(f"Seed: {seed.hex()}")

    # Check against default difficulty
    default_difficulty = 1_000_000  # 1.0 scaled
    threshold = default_difficulty / MinerConfig.DIFFICULTY_SCALE
    if energy < threshold:
        logger.info(f"PASS: energy {energy:.6f} < threshold {threshold:.6f}")
    else:
        logger.info(f"FAIL: energy {energy:.6f} >= threshold {threshold:.6f}")

    logger.info("VQE test complete.")


def main() -> None:
    """Parse arguments and start mining."""
    parser = argparse.ArgumentParser(
        description="Qubitcoin VQE Mining Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--ws",
        type=str,
        help=f"Substrate WebSocket URL (default: {MinerConfig.SUBSTRATE_WS_URL})",
    )
    parser.add_argument(
        "--seed",
        type=str,
        help="Miner sr25519 seed phrase or //DevAccount",
    )
    parser.add_argument(
        "--qubits",
        type=int,
        help=f"Number of qubits (default: {MinerConfig.NUM_QUBITS})",
    )
    parser.add_argument(
        "--reps",
        type=int,
        help=f"VQE ansatz reps (default: {MinerConfig.VQE_REPS})",
    )
    parser.add_argument(
        "--maxiter",
        type=int,
        help=f"COBYLA max iterations (default: {MinerConfig.VQE_MAXITER})",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        help=f"Max mining attempts per block (default: {MinerConfig.MAX_MINING_ATTEMPTS})",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Enable GPU Aer backend",
    )
    parser.add_argument(
        "--simulator",
        action="store_true",
        help="Enable CPU Aer simulator backend",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run a single VQE test without connecting to a node",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=f"Logging level (default: {MinerConfig.LOG_LEVEL})",
    )

    args = parser.parse_args()

    # Override config from CLI args
    if args.ws:
        MinerConfig.SUBSTRATE_WS_URL = args.ws
    if args.seed:
        MinerConfig.MINER_SEED = args.seed
    if args.qubits:
        MinerConfig.NUM_QUBITS = args.qubits
    if args.reps:
        MinerConfig.VQE_REPS = args.reps
    if args.maxiter:
        MinerConfig.VQE_MAXITER = args.maxiter
    if args.attempts:
        MinerConfig.MAX_MINING_ATTEMPTS = args.attempts
    if args.gpu:
        MinerConfig.USE_GPU_AER = True
    if args.simulator:
        MinerConfig.USE_SIMULATOR = True
    if args.log_level:
        MinerConfig.LOG_LEVEL = args.log_level

    setup_logging()

    if args.test:
        run_test()
        sys.exit(0)

    # Start mining
    from .mining_loop import MiningLoop

    loop = MiningLoop()
    try:
        loop.start()
    except KeyboardInterrupt:
        pass
    finally:
        loop.stop()


if __name__ == "__main__":
    main()
