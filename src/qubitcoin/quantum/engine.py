"""
Quantum VQE Engine for Proof-of-SUSY-Alignment
Handles Hamiltonian generation and optimization

KEY DESIGN: Hamiltonians are deterministically derived from chain state
(prev_hash + height). Every miner works on the SAME puzzle. The first
to find VQE parameters that achieve energy < difficulty threshold wins.

QUANTUM ADVANTAGE NOTE (honest assessment):
  The current 4-qubit TwoLocal ansatz is exactly simulable on classical
  hardware in O(2^4 = 16) time per energy evaluation. At this scale,
  classical eigensolvers (e.g. numpy.linalg.eigh on a 16x16 matrix)
  are faster than VQE optimization. The VQE framework is used because:
  1. It is the correct algorithm — VQE is what scales to 50+ qubits
  2. The consensus mechanism is VQE-native from day one
  3. When qubit count increases to 30+, classical simulation becomes
     exponentially intractable (2^30 ≈ 1 billion amplitudes), while
     VQE on quantum hardware scales polynomially
  4. The mining protocol, proof format, and verification logic all
     work identically at any qubit count — only NUM_QUBITS changes

  Planned scaling path:
    4 qubits (current)  → classical-equivalent, proof-of-concept
    8 qubits            → still classically simulable, richer Hamiltonians
    16 qubits           → borderline classical (65K amplitudes)
    30+ qubits          → genuine quantum advantage territory
"""

import hashlib
import numpy as np
from typing import List, Tuple, Optional
from scipy.optimize import minimize

from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.library import TwoLocal
from qiskit.primitives import StatevectorEstimator

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

NUM_QUBITS = 4
MAX_MINING_ATTEMPTS = 50


class QuantumEngine:
    """VQE-based quantum computation engine"""

    def __init__(self):
        """Initialize quantum backend"""
        self.estimator = None
        self.backend = None
        self.service = None
        self.backend_name: str = "unknown"

        self._initialize_backend()

    def _select_backend(self) -> str:
        """Select the best available quantum backend.

        Priority order:
          1. GPU Aer (if USE_GPU_AER=true and GPU available)
          2. CPU Aer (if USE_SIMULATOR=true)
          3. StatevectorEstimator (default, exact simulation)
          4. IBM Quantum (if configured)

        Returns:
            String identifying the selected backend: 'gpu_aer', 'cpu_aer',
            'statevector', or 'ibm_quantum'.
        """
        if Config.USE_GPU_AER:
            try:
                from qiskit_aer import AerSimulator
                # Try to create a GPU-accelerated simulator
                gpu_sim = AerSimulator(method='statevector', device='GPU')
                # Validate GPU is actually available by checking config
                gpu_config = gpu_sim.configuration()
                if gpu_config is not None:
                    logger.info("GPU Aer backend available")
                    return 'gpu_aer'
            except Exception as e:
                logger.debug(f"GPU Aer not available, falling back: {e}")
                # Fall through to next option

        if Config.USE_LOCAL_ESTIMATOR:
            return 'statevector'

        if Config.USE_SIMULATOR:
            try:
                from qiskit_aer import AerSimulator  # noqa: F811
                return 'cpu_aer'
            except ImportError:
                logger.debug("Aer not installed, falling back to StatevectorEstimator")
                return 'statevector'

        # IBM Quantum
        if Config.IBM_TOKEN:
            return 'ibm_quantum'

        return 'statevector'

    def _initialize_backend(self) -> None:
        """Initialize appropriate quantum backend"""
        selected = self._select_backend()
        self.backend_name = selected

        if selected == 'gpu_aer':
            try:
                from qiskit_aer import AerSimulator
                from qiskit_aer.primitives import EstimatorV2 as AerEstimator

                self.backend = AerSimulator(method='statevector', device='GPU')
                self.estimator = AerEstimator.from_backend(self.backend)
                logger.info("Quantum Engine: AerSimulator GPU-accelerated")
                return
            except Exception as e:
                logger.debug(f"GPU Aer init failed, falling back to CPU: {e}")
                # Fall through to CPU Aer or Statevector
                selected = 'cpu_aer' if Config.USE_SIMULATOR else 'statevector'
                self.backend_name = selected

        if selected == 'statevector':
            self.estimator = StatevectorEstimator()
            logger.info("Quantum Engine: StatevectorEstimator (exact)")
        elif selected == 'cpu_aer':
            try:
                from qiskit_aer import AerSimulator
                from qiskit_aer.primitives import EstimatorV2 as AerEstimator

                self.backend = AerSimulator()
                self.estimator = AerEstimator.from_backend(self.backend)
                logger.info("Quantum Engine: AerSimulator with EstimatorV2")
            except ImportError:
                logger.debug("Aer not available, using StatevectorEstimator")
                self.estimator = StatevectorEstimator()
                self.backend_name = 'statevector'
        elif selected == 'ibm_quantum':
            try:
                from qiskit_ibm_runtime import QiskitRuntimeService, EstimatorV2 as RuntimeEstimator

                self.service = QiskitRuntimeService(
                    channel="ibm_quantum",
                    token=Config.IBM_TOKEN,
                    instance=Config.IBM_INSTANCE
                )
                self.backend = self.service.least_busy(
                    operational=True,
                    simulator=False,
                    min_num_qubits=5
                )
                self.estimator = RuntimeEstimator(backend=self.backend)
                logger.info(f"Quantum Engine: IBM Quantum ({self.backend.name})")
            except Exception as e:
                logger.error(f"Failed to connect to IBM Quantum: {e}")
                logger.info("Falling back to StatevectorEstimator")
                self.estimator = StatevectorEstimator()
                self.backend_name = 'statevector'

    # ========================================================================
    # DETERMINISTIC HAMILTONIAN GENERATION
    # ========================================================================

    def derive_hamiltonian_seed(self, prev_hash: str, height: int) -> int:
        """
        Derive a deterministic 256-bit seed from chain state.

        This ensures every miner/validator generates the SAME Hamiltonian
        for a given block position. Like Bitcoin's block header target,
        the challenge is identical for all participants.

        Args:
            prev_hash: Previous block hash (hex string)
            height: Block height being mined

        Returns:
            Integer seed for numpy RandomState
        """
        data = f"{prev_hash}:{height}".encode('utf-8')
        seed_hash = hashlib.sha256(data).digest()
        # Use first 4 bytes as numpy seed (uint32)
        seed = int.from_bytes(seed_hash[:4], 'big')
        return seed

    def generate_hamiltonian(self, num_qubits: int = NUM_QUBITS,
                             seed: Optional[int] = None,
                             prev_hash: str = None,
                             height: int = None) -> List[Tuple[str, float]]:
        """
        Generate SUSY Hamiltonian.

        If prev_hash and height are provided, generates a DETERMINISTIC
        Hamiltonian tied to chain state (production mode).
        If only seed is provided, uses that seed (test mode).
        If nothing is provided, generates random (legacy/fallback).

        Args:
            num_qubits: Number of qubits (default 4 for N=2 SUSY)
            seed: Explicit random seed (test mode)
            prev_hash: Previous block hash for deterministic derivation
            height: Block height for deterministic derivation

        Returns:
            List of (pauli_string, coefficient) tuples
        """
        if prev_hash is not None and height is not None:
            seed = self.derive_hamiltonian_seed(prev_hash, height)
            logger.debug(f"Deterministic Hamiltonian: prev_hash={prev_hash[:16]}..., height={height}, seed={seed}")

        rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()

        num_terms = num_qubits + 1
        hamiltonian = []

        for _ in range(num_terms):
            pauli_str = ''.join(rng.choice(['I', 'X', 'Y', 'Z'], num_qubits))
            coeff = rng.uniform(-1, 1)
            hamiltonian.append((pauli_str, coeff))

        logger.debug(f"Generated Hamiltonian with {num_terms} terms (seed={'deterministic' if seed else 'random'})")
        return hamiltonian

    # ========================================================================
    # EXACT GROUND STATE (consensus safety check)
    # ========================================================================

    def compute_exact_ground_state(self, hamiltonian: List[Tuple[str, float]],
                                    num_qubits: int = NUM_QUBITS) -> float:
        """Compute exact ground state energy by diagonalizing the Hamiltonian matrix.

        For 4 qubits this is a 16x16 matrix — trivial to diagonalize.
        Used by consensus to ensure difficulty is always above the ground state
        so that mining is always physically possible.

        Args:
            hamiltonian: List of (pauli_string, coefficient) tuples
            num_qubits: Number of qubits

        Returns:
            Exact minimum eigenvalue (ground state energy)
        """
        observable = SparsePauliOp.from_list(hamiltonian)
        matrix = observable.to_matrix()
        eigenvalues = np.linalg.eigvalsh(matrix.real)
        return float(eigenvalues[0])

    # ========================================================================
    # ANSATZ AND ENERGY COMPUTATION
    # ========================================================================

    def create_ansatz(self, num_qubits: int = NUM_QUBITS, reps: int = None) -> TwoLocal:
        """Create parameterized quantum circuit ansatz"""
        reps = reps or Config.VQE_REPS

        return TwoLocal(
            num_qubits,
            rotation_blocks='ry',
            entanglement_blocks='cz',
            entanglement='linear',
            reps=reps,
            insert_barriers=True
        )

    def compute_energy(self, params: np.ndarray, hamiltonian: List[Tuple[str, float]],
                      num_qubits: int = NUM_QUBITS) -> float:
        """
        Compute expectation value <psi|H|psi>

        Args:
            params: Circuit parameters
            hamiltonian: Hamiltonian as list of (pauli_string, coeff) tuples
            num_qubits: Number of qubits

        Returns:
            Energy expectation value
        """
        ansatz = self.create_ansatz(num_qubits)
        bound_circuit = ansatz.assign_parameters(params)
        observable = SparsePauliOp.from_list(hamiltonian)

        # V2 primitives API: pass (circuit, observable) as a pub
        job = self.estimator.run([(bound_circuit, observable)])
        result = job.result()

        return float(result[0].data.evs)

    # ========================================================================
    # VQE OPTIMIZATION (Mining)
    # ========================================================================

    def optimize_vqe(self, hamiltonian: List[Tuple[str, float]],
                    initial_params: Optional[np.ndarray] = None,
                    num_qubits: int = NUM_QUBITS) -> Tuple[np.ndarray, float]:
        """
        Run VQE optimization to find ground state.

        In mining, this is called repeatedly with different random initial
        parameters until the energy beats the difficulty threshold (the
        "nonce grinding" equivalent in quantum PoW).

        Args:
            hamiltonian: Target Hamiltonian
            initial_params: Starting parameters (random if None)
            num_qubits: Number of qubits

        Returns:
            (optimized_params, ground_state_energy)
        """
        ansatz = self.create_ansatz(num_qubits)

        if initial_params is None:
            initial_params = np.random.uniform(0, 2 * np.pi, ansatz.num_parameters)

        def objective(params):
            return self.compute_energy(params, hamiltonian, num_qubits)

        logger.debug(f"Starting VQE optimization (maxiter={Config.VQE_MAXITER})")

        result = minimize(
            objective,
            initial_params,
            method='COBYLA',
            options={
                'maxiter': Config.VQE_MAXITER,
                'tol': Config.VQE_TOLERANCE,
                'rhobeg': 0.1
            }
        )

        logger.debug(f"VQE converged: energy={result.fun:.6f}, nfev={result.nfev}")

        return result.x, result.fun

    # ========================================================================
    # PROOF VALIDATION (Consensus)
    # ========================================================================

    def validate_proof(self, params, hamiltonian: List[Tuple[str, float]],
                      claimed_energy: float, difficulty: float,
                      num_qubits: int = NUM_QUBITS,
                      prev_hash: str = None,
                      height: int = None) -> Tuple[bool, str]:
        """
        Validate a quantum proof.

        CRITICAL: If prev_hash and height are provided, the validator
        RE-DERIVES the Hamiltonian from chain state and checks that
        the miner's solution is against the correct challenge.

        Args:
            params: Circuit parameters (miner's solution)
            hamiltonian: Challenge Hamiltonian (miner-supplied, verified against re-derivation)
            claimed_energy: Claimed ground state energy
            difficulty: Required difficulty threshold
            num_qubits: Number of qubits
            prev_hash: Previous block hash (for deterministic verification)
            height: Block height (for deterministic verification)

        Returns:
            (is_valid, reason)
        """
        try:
            # If chain state provided, verify the Hamiltonian is correct
            if prev_hash is not None and height is not None:
                expected_hamiltonian = self.generate_hamiltonian(
                    num_qubits=num_qubits,
                    prev_hash=prev_hash,
                    height=height
                )
                # Compare Hamiltonian terms
                if len(hamiltonian) != len(expected_hamiltonian):
                    return False, "Hamiltonian term count mismatch"
                for (ps1, c1), (ps2, c2) in zip(hamiltonian, expected_hamiltonian):
                    if ps1 != ps2 or abs(c1 - c2) > 1e-10:
                        return False, "Hamiltonian does not match chain-derived challenge"
                # Use the re-derived Hamiltonian for energy computation
                hamiltonian = expected_hamiltonian

            # Convert params to numpy array if needed
            if not isinstance(params, np.ndarray):
                params = np.array(params)

            computed_energy = self.compute_energy(params, hamiltonian, num_qubits)

            energy_diff = abs(computed_energy - claimed_energy)
            if energy_diff > Config.ENERGY_VALIDATION_TOLERANCE:
                return False, f"Energy mismatch: {energy_diff:.6f} > tolerance"

            if computed_energy >= difficulty:
                return False, f"Energy {computed_energy:.6f} >= difficulty {difficulty:.6f}"

            logger.debug(f"Proof valid: energy={computed_energy:.6f}, diff={difficulty:.6f}")
            return True, "Valid"

        except Exception as e:
            logger.error(f"Proof validation error: {e}")
            return False, f"Validation exception: {str(e)}"

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def estimate_circuit_depth(self, num_qubits: int = NUM_QUBITS) -> int:
        """Estimate circuit depth for NISQ constraints"""
        ansatz = self.create_ansatz(num_qubits)
        return ansatz.decompose().depth()

    def get_fidelity(self, params1: np.ndarray, params2: np.ndarray,
                    num_qubits: int = NUM_QUBITS) -> float:
        """Compute state fidelity between two parameter sets"""
        from qiskit.quantum_info import Statevector

        ansatz = self.create_ansatz(num_qubits)

        state1 = Statevector.from_instruction(ansatz.assign_parameters(params1))
        state2 = Statevector.from_instruction(ansatz.assign_parameters(params2))

        return abs(state1.inner(state2)) ** 2
