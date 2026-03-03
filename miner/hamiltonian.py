"""
Hamiltonian seed derivation — MUST be bit-exact with Substrate pallet.

The Substrate pallet (qbc-consensus) derives the Hamiltonian seed as:
    data = b"hamiltonian-seed-v1:" + parent_hash_bytes + block_height_le_bytes
    seed = SHA2-256(data)

The first 4 bytes of the seed (big-endian) are used as numpy RandomState seed.
The Hamiltonian is then generated deterministically from that seed.
"""

import hashlib
import numpy as np
from typing import List, Tuple

from .config import MinerConfig


def derive_hamiltonian_seed(parent_hash: bytes, block_height: int) -> bytes:
    """
    Derive 32-byte Hamiltonian seed from parent block hash and target height.

    CRITICAL: This MUST produce the exact same H256 as the Substrate pallet's
    `derive_hamiltonian_seed()` function. Any deviation will cause proof rejection.

    The Substrate pallet computes:
        data = b"hamiltonian-seed-v1:" || parent_hash.as_ref() || block_height.to_le_bytes()
        seed = sha2_256(&data)

    Args:
        parent_hash: 32-byte parent block hash (raw bytes, NOT hex string)
        block_height: Target block height being mined (u64)

    Returns:
        32-byte SHA2-256 hash (the Hamiltonian seed H256)
    """
    data = bytearray()
    data.extend(b"hamiltonian-seed-v1:")
    data.extend(parent_hash)
    data.extend(block_height.to_bytes(8, byteorder="little")  )
    return hashlib.sha256(bytes(data)).digest()


def seed_to_numpy_seed(hamiltonian_seed: bytes) -> int:
    """
    Convert 32-byte Hamiltonian seed to numpy RandomState seed.

    Uses first 4 bytes as big-endian uint32 — matching the Python quantum
    engine's convention.

    Args:
        hamiltonian_seed: 32-byte seed from derive_hamiltonian_seed()

    Returns:
        Integer seed for numpy.random.RandomState (0 to 2^32 - 1)
    """
    return int.from_bytes(hamiltonian_seed[:4], byteorder="big")


def generate_hamiltonian(
    parent_hash: bytes,
    block_height: int,
    num_qubits: int = None,
) -> Tuple[List[Tuple[str, float]], bytes]:
    """
    Generate the deterministic SUSY Hamiltonian for a given block.

    Every miner and validator must produce the SAME Hamiltonian for the same
    (parent_hash, block_height) pair. This is the "challenge" — like Bitcoin's
    block header target.

    Args:
        parent_hash: 32-byte parent block hash
        block_height: Target block height
        num_qubits: Number of qubits (default from config)

    Returns:
        (hamiltonian_terms, hamiltonian_seed_bytes)
        - hamiltonian_terms: List of (pauli_string, coefficient) tuples
        - hamiltonian_seed_bytes: The 32-byte seed (needed for proof submission)
    """
    if num_qubits is None:
        num_qubits = MinerConfig.NUM_QUBITS

    # Step 1: Derive deterministic seed (bit-exact with Substrate)
    seed_bytes = derive_hamiltonian_seed(parent_hash, block_height)
    numpy_seed = seed_to_numpy_seed(seed_bytes)

    # Step 2: Generate Hamiltonian from seed (matches Python quantum/engine.py)
    rng = np.random.RandomState(numpy_seed)
    num_terms = num_qubits + 1
    hamiltonian = []

    for _ in range(num_terms):
        pauli_str = "".join(rng.choice(["I", "X", "Y", "Z"], num_qubits))
        coeff = rng.uniform(-1, 1)
        hamiltonian.append((pauli_str, coeff))

    return hamiltonian, seed_bytes
