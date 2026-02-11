"""
Quantum VQE Engine for Proof-of-SUSY-Alignment
Handles Hamiltonian generation and optimization
"""

import numpy as np
from typing import List, Tuple, Optional
from scipy.optimize import minimize

from qiskit.quantum_info import SparsePauliOp
from qiskit.circuit.library import TwoLocal
from qiskit.primitives import Estimator  # FIXED: Use Estimator, not StatevectorEstimator

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class QuantumEngine:
    """VQE-based quantum computation engine"""

    def __init__(self):
        """Initialize quantum backend"""
        self.estimator = None
        self.backend = None
        self.service = None

        self._initialize_backend()

    def _initialize_backend(self):
        """Initialize appropriate quantum backend"""
        if Config.USE_LOCAL_ESTIMATOR:
            self.estimator = Estimator()  # FIXED: Correct class name
            logger.info("⚛️  Quantum Engine: Local Estimator (exact)")
        elif Config.USE_SIMULATOR:
            try:
                from qiskit_aer import AerSimulator
                from qiskit_aer.primitives import Estimator as AerEstimator

                self.backend = AerSimulator()
                self.estimator = AerEstimator()
                logger.info("⚛️  Quantum Engine: AerSimulator with Estimator")
            except ImportError:
                logger.warning("Aer not available, using local estimator")
                self.estimator = Estimator()
        else:
            try:
                from qiskit_ibm_runtime import QiskitRuntimeService, Estimator as RuntimeEstimator

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
                logger.info(f"⚛️  Quantum Engine: IBM Quantum ({self.backend.name})")
            except Exception as e:
                logger.error(f"Failed to connect to IBM Quantum: {e}")
                logger.info("Falling back to local estimator")
                self.estimator = Estimator()

    def generate_hamiltonian(self, num_qubits: int = 4, seed: Optional[int] = None) -> List[Tuple[str, float]]:
        """
        Generate random SUSY Hamiltonian

        Args:
            num_qubits: Number of qubits (default 4 for N=2 SUSY)
            seed: Random seed for reproducibility

        Returns:
            List of (pauli_string, coefficient) tuples
        """
        rng = np.random.RandomState(seed) if seed is not None else np.random.RandomState()

        num_terms = num_qubits + 1
        hamiltonian = []

        for _ in range(num_terms):
            pauli_str = ''.join(rng.choice(['I', 'X', 'Y', 'Z'], num_qubits))
            coeff = rng.uniform(-1, 1)
            hamiltonian.append((pauli_str, coeff))

        logger.debug(f"Generated Hamiltonian with {num_terms} terms")
        return hamiltonian

    def create_ansatz(self, num_qubits: int = 4, reps: int = None) -> TwoLocal:
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
                      num_qubits: int = 4) -> float:
        """
        Compute expectation value <ψ|H|ψ>

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

        # FIXED: Qiskit 1.0 API
        job = self.estimator.run([bound_circuit], [observable])
        result = job.result()
        
        # Extract expectation value from result
        return float(result.values[0])

    def optimize_vqe(self, hamiltonian: List[Tuple[str, float]],
                    initial_params: Optional[np.ndarray] = None,
                    num_qubits: int = 4) -> Tuple[np.ndarray, float]:
        """
        Run VQE optimization to find ground state

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

    def validate_proof(self, params: np.ndarray, hamiltonian: List[Tuple[str, float]],
                      claimed_energy: float, difficulty: float,
                      num_qubits: int = 4) -> Tuple[bool, str]:
        """
        Validate a quantum proof

        Args:
            params: Circuit parameters
            hamiltonian: Challenge Hamiltonian
            claimed_energy: Claimed ground state energy
            difficulty: Required difficulty threshold
            num_qubits: Number of qubits

        Returns:
            (is_valid, reason)
        """
        try:
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

    def estimate_circuit_depth(self, num_qubits: int = 4) -> int:
        """Estimate circuit depth for NISQ constraints"""
        ansatz = self.create_ansatz(num_qubits)
        return ansatz.decompose().depth()

    def get_fidelity(self, params1: np.ndarray, params2: np.ndarray,
                    num_qubits: int = 4) -> float:
        """Compute state fidelity between two parameter sets"""
        from qiskit.quantum_info import Statevector

        ansatz = self.create_ansatz(num_qubits)

        state1 = Statevector.from_instruction(ansatz.assign_parameters(params1))
        state2 = Statevector.from_instruction(ansatz.assign_parameters(params2))

        return abs(state1.inner(state2)) ** 2
