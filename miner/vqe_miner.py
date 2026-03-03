"""
VQE Mining Engine — Qiskit-based VQE optimization for Proof-of-SUSY-Alignment.

Mining loop:
1. Subscribe to finalized block headers from Substrate
2. For each new block, derive the Hamiltonian from (parent_hash, target_height)
3. Run VQE optimization (COBYLA, up to MAX_MINING_ATTEMPTS random starts)
4. If energy < difficulty_threshold: submit proof to Substrate
5. Wait for next block
"""

import time
import logging
import numpy as np
from typing import Optional, Tuple, List

from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.library import TwoLocal
from qiskit.primitives import StatevectorEstimator
from scipy.optimize import minimize

from .config import MinerConfig
from .hamiltonian import generate_hamiltonian

logger = logging.getLogger("qubitcoin.miner")


class VqeMiner:
    """VQE-based mining engine for Qubitcoin."""

    def __init__(self):
        self.estimator = None
        self.backend_name: str = "unknown"
        self._initialize_backend()

    def _initialize_backend(self) -> None:
        """Initialize quantum computation backend."""
        if MinerConfig.USE_GPU_AER:
            try:
                from qiskit_aer import AerSimulator
                from qiskit_aer.primitives import EstimatorV2 as AerEstimator

                backend = AerSimulator(method="statevector", device="GPU")
                self.estimator = AerEstimator.from_backend(backend)
                self.backend_name = "gpu_aer"
                logger.info("VQE Miner: GPU Aer backend initialized")
                return
            except Exception as e:
                logger.debug(f"GPU Aer not available: {e}")

        if MinerConfig.USE_SIMULATOR:
            try:
                from qiskit_aer import AerSimulator
                from qiskit_aer.primitives import EstimatorV2 as AerEstimator

                backend = AerSimulator()
                self.estimator = AerEstimator.from_backend(backend)
                self.backend_name = "cpu_aer"
                logger.info("VQE Miner: CPU Aer backend initialized")
                return
            except ImportError:
                logger.debug("Aer not installed, falling back to StatevectorEstimator")

        self.estimator = StatevectorEstimator()
        self.backend_name = "statevector"
        logger.info("VQE Miner: StatevectorEstimator initialized (exact simulation)")

    def create_ansatz(self, num_qubits: int = None, reps: int = None) -> TwoLocal:
        """Create the parameterized VQE ansatz circuit."""
        num_qubits = num_qubits or MinerConfig.NUM_QUBITS
        reps = reps or MinerConfig.VQE_REPS

        return TwoLocal(
            num_qubits,
            rotation_blocks="ry",
            entanglement_blocks="cz",
            entanglement="linear",
            reps=reps,
            insert_barriers=True,
        )

    def compute_energy(
        self,
        params: np.ndarray,
        hamiltonian: List[Tuple[str, float]],
        num_qubits: int = None,
    ) -> float:
        """Compute <psi(params)|H|psi(params)> expectation value."""
        num_qubits = num_qubits or MinerConfig.NUM_QUBITS
        ansatz = self.create_ansatz(num_qubits)
        bound_circuit = ansatz.assign_parameters(params)
        observable = SparsePauliOp.from_list(hamiltonian)

        job = self.estimator.run([(bound_circuit, observable)])
        result = job.result()
        return float(result[0].data.evs)

    def optimize_vqe(
        self,
        hamiltonian: List[Tuple[str, float]],
        initial_params: Optional[np.ndarray] = None,
        num_qubits: int = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Run VQE optimization to find ground state energy.

        Args:
            hamiltonian: Target Hamiltonian [(pauli_str, coeff), ...]
            initial_params: Starting parameters (random if None)
            num_qubits: Number of qubits

        Returns:
            (optimized_params, ground_state_energy)
        """
        num_qubits = num_qubits or MinerConfig.NUM_QUBITS
        ansatz = self.create_ansatz(num_qubits)

        if initial_params is None:
            initial_params = np.random.uniform(0, 2 * np.pi, ansatz.num_parameters)

        def objective(params):
            return self.compute_energy(params, hamiltonian, num_qubits)

        result = minimize(
            objective,
            initial_params,
            method="COBYLA",
            options={
                "maxiter": MinerConfig.VQE_MAXITER,
                "tol": MinerConfig.VQE_TOLERANCE,
                "rhobeg": 0.1,
            },
        )

        return result.x, result.fun

    def mine_block(
        self,
        parent_hash: bytes,
        target_height: int,
        difficulty: float,
    ) -> Optional[dict]:
        """
        Attempt to mine a block by finding VQE params with energy < difficulty.

        This is the "nonce grinding" equivalent — we try different random
        initial parameters until we find one that converges to energy below
        the difficulty threshold.

        Args:
            parent_hash: 32-byte parent block hash (raw bytes)
            target_height: Block height being mined
            difficulty: Current difficulty (on-chain scaled value, NOT float)
                       Higher difficulty = easier mining.

        Returns:
            Mining proof dict if successful, None if all attempts fail.
            Dict keys: params, energy, hamiltonian_seed, n_qubits, energy_scaled
        """
        # Generate deterministic Hamiltonian
        hamiltonian, seed_bytes = generate_hamiltonian(parent_hash, target_height)

        # Convert on-chain difficulty to energy threshold
        # On-chain: energy (i128, scaled 10^12) < difficulty (u64, scaled 10^6) * 10^6
        # Float: energy_float < difficulty_float
        difficulty_threshold = difficulty / MinerConfig.DIFFICULTY_SCALE

        logger.info(
            f"Mining block {target_height}: "
            f"difficulty={difficulty_threshold:.6f}, "
            f"seed={seed_bytes[:8].hex()}..., "
            f"max_attempts={MinerConfig.MAX_MINING_ATTEMPTS}"
        )

        best_energy = float("inf")
        best_params = None

        for attempt in range(MinerConfig.MAX_MINING_ATTEMPTS):
            start = time.monotonic()
            params, energy = self.optimize_vqe(hamiltonian)
            elapsed = time.monotonic() - start

            if energy < best_energy:
                best_energy = energy
                best_params = params

            logger.debug(
                f"  Attempt {attempt + 1}/{MinerConfig.MAX_MINING_ATTEMPTS}: "
                f"energy={energy:.6f}, best={best_energy:.6f}, "
                f"threshold={difficulty_threshold:.6f}, "
                f"time={elapsed:.2f}s"
            )

            if energy < difficulty_threshold:
                # Scale to on-chain representation
                energy_scaled = int(energy * MinerConfig.ENERGY_SCALE)
                params_scaled = [int(p * MinerConfig.ENERGY_SCALE) for p in params]

                logger.info(
                    f"  BLOCK MINED! attempt={attempt + 1}, "
                    f"energy={energy:.6f} < {difficulty_threshold:.6f}, "
                    f"energy_scaled={energy_scaled}"
                )

                return {
                    "params": params.tolist(),
                    "params_scaled": params_scaled,
                    "energy": energy,
                    "energy_scaled": energy_scaled,
                    "hamiltonian_seed": seed_bytes,
                    "n_qubits": MinerConfig.NUM_QUBITS,
                    "attempt": attempt + 1,
                }

        logger.warning(
            f"  Mining failed after {MinerConfig.MAX_MINING_ATTEMPTS} attempts. "
            f"Best energy: {best_energy:.6f}, threshold: {difficulty_threshold:.6f}"
        )
        return None
