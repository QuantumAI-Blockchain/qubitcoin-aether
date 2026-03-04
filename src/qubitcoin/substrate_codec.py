"""
Substrate SCALE Codec utilities for Qubitcoin.

Handles encoding/decoding of Substrate-specific types for the Python execution
service. Uses substrate-interface library when available, with minimal fallbacks.
"""

import hashlib
import struct
from typing import Any, Optional

from .utils.logger import get_logger

logger = get_logger(__name__)

# Scale factors matching primitives/lib.rs
QBC_UNIT: int = 100_000_000          # 1 QBC = 10^8 units
ENERGY_SCALE: int = 1_000_000_000_000  # VQE energy/params scaled by 10^12
DIFFICULTY_SCALE: int = 1_000_000    # Difficulty scaled by 10^6
PHI_SCALE: int = 1_000              # Phi scaled by 10^3


def substrate_block_to_python(
    block_height: int,
    block_hash: str,
    header: dict,
    block_data: dict,
) -> dict:
    """Convert a Substrate block to a Python-compatible block dict.

    The Python node stores blocks in CockroachDB with a specific schema.
    This function converts the Substrate block format to match.

    Args:
        block_height: Block number.
        block_hash: Block hash (hex string with 0x prefix).
        header: Block header dict from chain_getHeader.
        block_data: Full block dict from chain_getBlock.

    Returns:
        Dict compatible with the Python node's Block model.
    """
    parent_hash = header.get("parentHash", "0x" + "0" * 64)
    state_root = header.get("stateRoot", "0x" + "0" * 64)
    extrinsics_root = header.get("extrinsicsRoot", "0x" + "0" * 64)

    # Strip 0x prefix for internal storage
    block_hash_clean = block_hash.replace("0x", "")
    parent_hash_clean = parent_hash.replace("0x", "")

    # Extract timestamp from Substrate extrinsics if available
    timestamp = _extract_timestamp(block_data.get("extrinsics", []))

    return {
        "height": block_height,
        "block_hash": block_hash_clean,
        "prev_hash": parent_hash_clean,
        "timestamp": timestamp,
        "state_root": state_root.replace("0x", ""),
        "extrinsics_root": extrinsics_root.replace("0x", ""),
        "transactions": [],  # Transactions parsed from extrinsics if needed
        "difficulty": 1.0,   # Default — actual difficulty from pallet storage
        "source": "substrate",
    }


def _extract_timestamp(extrinsics: list) -> float:
    """Extract the timestamp from the Timestamp::set inherent extrinsic.

    Substrate encodes the timestamp inherent as the first extrinsic in each block.
    If we can't decode it, return current time.
    """
    import time
    # The timestamp inherent is typically the first extrinsic.
    # Without full SCALE decoding, we fall back to current time.
    # When substrate-interface is available, we could decode it properly.
    return time.time()


def python_vqe_to_substrate(
    params: list[float],
    energy: float,
    prev_hash: str,
    n_qubits: int = 4,
) -> dict:
    """Convert Python VQE mining result to Substrate VqeProof format.

    Args:
        params: VQE optimized parameters (list of floats).
        energy: Ground state energy (float).
        prev_hash: Previous block hash (used as hamiltonian seed).
        n_qubits: Number of qubits used.

    Returns:
        Dict matching the VqeProof SCALE struct.
    """
    # Scale float params to fixed-point i64 * 10^12
    params_scaled = [int(p * ENERGY_SCALE) for p in params]
    # Scale energy to fixed-point i128 * 10^12
    energy_scaled = int(energy * ENERGY_SCALE)

    # Derive hamiltonian seed from prev_hash (matches quantum/engine.py)
    if prev_hash and len(prev_hash) >= 64:
        hamiltonian_seed = "0x" + prev_hash[:64]
    else:
        hamiltonian_seed = "0x" + "0" * 64

    return {
        "params": params_scaled,
        "energy": energy_scaled,
        "hamiltonian_seed": hamiltonian_seed,
        "n_qubits": n_qubits,
    }


def difficulty_to_float(scaled_difficulty: int) -> float:
    """Convert Substrate scaled difficulty (u64 * 10^6) to Python float."""
    return scaled_difficulty / DIFFICULTY_SCALE


def float_to_difficulty(difficulty: float) -> int:
    """Convert Python float difficulty to Substrate scaled u64."""
    return int(difficulty * DIFFICULTY_SCALE)


def qbc_to_smallest(qbc_amount: float) -> int:
    """Convert QBC amount (float) to smallest units (u128)."""
    return int(qbc_amount * QBC_UNIT)


def smallest_to_qbc(smallest_units: int) -> float:
    """Convert smallest units (u128) to QBC amount (float)."""
    return smallest_units / QBC_UNIT


def phi_to_scaled(phi_value: float) -> int:
    """Convert Phi value (float) to scaled integer (u64 * 10^3)."""
    return int(phi_value * PHI_SCALE)


def scaled_to_phi(phi_scaled: int) -> float:
    """Convert scaled Phi integer to float."""
    return phi_scaled / PHI_SCALE


def compute_coinbase_txid(block_height: int) -> str:
    """Compute the deterministic coinbase txid for a given block height.

    Must match the Substrate chain_spec.rs derivation:
    SHA2-256("coinbase:" || block_height_le_bytes)
    """
    data = b"coinbase:" + struct.pack("<Q", block_height)
    return hashlib.sha256(data).hexdigest()


def compute_premine_txid() -> str:
    """Compute the genesis premine txid.

    Must match chain_spec.rs: SHA2-256("genesis_premine")
    """
    return hashlib.sha256(b"genesis_premine").hexdigest()
