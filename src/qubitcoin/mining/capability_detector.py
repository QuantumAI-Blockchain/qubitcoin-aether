"""
Mining node VQE capability detection.

Detects whether the node is using a classical simulator, AerSimulator,
or a real IBM Quantum backend. Reports qubit count, backend type,
estimated VQE throughput, and hardware capabilities so nodes can
advertise their mining power on the P2P network.
"""
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VQECapability:
    """Describes a node's VQE mining capabilities."""
    backend_type: str       # 'local_estimator' | 'aer_simulator' | 'ibm_quantum' | 'unknown'
    backend_name: str       # Human-readable name (e.g., 'ibm_brisbane')
    max_qubits: int         # Maximum qubit count supported
    is_simulator: bool      # True for simulators, False for real hardware
    is_available: bool      # Whether backend is currently operational
    estimated_vqe_time_s: float  # Estimated time per VQE optimization (seconds)
    features: Dict[str, bool] = field(default_factory=dict)
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'backend_type': self.backend_type,
            'backend_name': self.backend_name,
            'max_qubits': self.max_qubits,
            'is_simulator': self.is_simulator,
            'is_available': self.is_available,
            'estimated_vqe_time_s': round(self.estimated_vqe_time_s, 3),
            'features': self.features,
            'detected_at': self.detected_at,
        }


class VQECapabilityDetector:
    """Detects and reports VQE mining capabilities.

    Inspects the QuantumEngine (or standalone config) to determine
    what quantum backend is available, its qubit capacity, and
    estimated performance characteristics.

    Usage:
        detector = VQECapabilityDetector()
        cap = detector.detect(quantum_engine)
        print(cap.backend_type, cap.max_qubits)

        # Or detect from config alone (no engine)
        cap = detector.detect_from_config()
    """

    def __init__(self) -> None:
        self._cached: Optional[VQECapability] = None
        self._benchmark_results: List[dict] = []
        logger.info("VQE capability detector initialized")

    def detect(self, quantum_engine: object) -> VQECapability:
        """Detect capabilities from a live QuantumEngine instance.

        Args:
            quantum_engine: A QuantumEngine instance with estimator/backend/service attrs.

        Returns:
            VQECapability describing the node's mining power.
        """
        backend_type = 'unknown'
        backend_name = 'unknown'
        max_qubits = 4  # Minimum for QBC mining
        is_simulator = True
        is_available = False
        estimated_time = 5.0  # Conservative default
        features: Dict[str, bool] = {}

        try:
            engine = quantum_engine
            estimator = getattr(engine, 'estimator', None)
            backend = getattr(engine, 'backend', None)
            service = getattr(engine, 'service', None)

            if estimator is not None:
                is_available = True

            # Determine backend type
            if service is not None and backend is not None:
                # IBM Quantum real hardware
                backend_type = 'ibm_quantum'
                backend_name = getattr(backend, 'name', 'ibm_unknown')
                is_simulator = False
                max_qubits = self._get_ibm_qubits(backend)
                estimated_time = 30.0  # Queue + execution
                features['error_mitigation'] = True
                features['dynamic_circuits'] = self._has_dynamic_circuits(backend)
                features['real_hardware'] = True

            elif backend is not None:
                # AerSimulator or other local simulator
                backend_type = 'aer_simulator'
                backend_name = getattr(backend, 'name', 'aer_simulator')
                is_simulator = True
                max_qubits = 30  # Aer can handle ~30 qubits
                estimated_time = 2.0
                features['noise_model'] = True
                features['gpu_acceleration'] = self._has_gpu(backend)
                features['real_hardware'] = False

            elif estimator is not None:
                # Local Estimator (exact statevector)
                backend_type = 'local_estimator'
                backend_name = 'qiskit_local_estimator'
                is_simulator = True
                max_qubits = 20  # Statevector limits
                estimated_time = 1.0
                features['exact_expectation'] = True
                features['real_hardware'] = False

        except Exception as e:
            logger.warning(f"Capability detection error: {e}")
            is_available = False

        cap = VQECapability(
            backend_type=backend_type,
            backend_name=backend_name,
            max_qubits=max_qubits,
            is_simulator=is_simulator,
            is_available=is_available,
            estimated_vqe_time_s=estimated_time,
            features=features,
        )
        self._cached = cap
        logger.info(
            f"VQE capability: {backend_type} ({backend_name}), "
            f"{max_qubits} qubits, simulator={is_simulator}"
        )
        return cap

    def detect_from_config(self) -> VQECapability:
        """Detect capabilities from Config settings (without live engine).

        Useful for pre-flight checks before QuantumEngine is initialized.
        """
        from ..config import Config

        if Config.USE_LOCAL_ESTIMATOR:
            return VQECapability(
                backend_type='local_estimator',
                backend_name='qiskit_local_estimator',
                max_qubits=20,
                is_simulator=True,
                is_available=True,
                estimated_vqe_time_s=1.0,
                features={'exact_expectation': True, 'real_hardware': False},
            )
        elif Config.USE_SIMULATOR:
            return VQECapability(
                backend_type='aer_simulator',
                backend_name='aer_simulator',
                max_qubits=30,
                is_simulator=True,
                is_available=True,
                estimated_vqe_time_s=2.0,
                features={'noise_model': True, 'real_hardware': False},
            )
        else:
            # IBM Quantum — can't know exact backend without service
            ibm_token = getattr(Config, 'IBM_TOKEN', '')
            return VQECapability(
                backend_type='ibm_quantum',
                backend_name='ibm_pending',
                max_qubits=127,  # Assume Eagle-class
                is_simulator=False,
                is_available=bool(ibm_token),
                estimated_vqe_time_s=30.0,
                features={'real_hardware': True, 'error_mitigation': True},
            )

    def get_cached(self) -> Optional[VQECapability]:
        """Return the last detected capability (or None)."""
        return self._cached

    def benchmark_vqe(self, quantum_engine: object, n_runs: int = 3) -> dict:
        """Run a quick VQE benchmark to measure actual performance.

        Args:
            quantum_engine: A QuantumEngine instance.
            n_runs: Number of VQE runs to average.

        Returns:
            Dict with timing results.
        """
        times: List[float] = []
        try:
            for _ in range(n_runs):
                start = time.monotonic()
                # Use a simple 4-qubit Hamiltonian
                seed = quantum_engine.derive_hamiltonian_seed("0" * 64, 0)
                hamiltonian = quantum_engine.generate_hamiltonian(seed=seed)
                quantum_engine.optimize_vqe(hamiltonian)
                elapsed = time.monotonic() - start
                times.append(elapsed)
        except Exception as e:
            logger.warning(f"VQE benchmark failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'runs': 0,
            }

        result = {
            'success': True,
            'runs': len(times),
            'avg_time_s': round(sum(times) / len(times), 3) if times else 0,
            'min_time_s': round(min(times), 3) if times else 0,
            'max_time_s': round(max(times), 3) if times else 0,
        }
        self._benchmark_results.append(result)

        # Update cached capability with real timing
        if self._cached is not None and times:
            self._cached.estimated_vqe_time_s = result['avg_time_s']

        return result

    def get_p2p_advertisement(self) -> dict:
        """Generate a P2P capability advertisement message.

        This dict can be broadcast to peers so they know this node's
        mining power for peer scoring and task routing.
        """
        cap = self._cached or self.detect_from_config()
        return {
            'type': 'vqe_capability',
            'backend_type': cap.backend_type,
            'max_qubits': cap.max_qubits,
            'is_simulator': cap.is_simulator,
            'is_available': cap.is_available,
            'estimated_vqe_time_s': cap.estimated_vqe_time_s,
            'features': cap.features,
            'timestamp': time.time(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_ibm_qubits(backend: object) -> int:
        """Extract qubit count from IBM backend."""
        try:
            config = getattr(backend, 'configuration', None)
            if config is not None:
                return getattr(config(), 'n_qubits', 127)
            num_qubits = getattr(backend, 'num_qubits', None)
            if num_qubits is not None:
                return num_qubits
        except Exception as e:
            logger.debug("Could not detect qubit count: %s", e)
        return 127  # Default to Eagle-class

    @staticmethod
    def _has_dynamic_circuits(backend: object) -> bool:
        """Check if backend supports dynamic circuits."""
        try:
            config = getattr(backend, 'configuration', None)
            if config is not None:
                return getattr(config(), 'dynamic_reprate_enabled', False)
        except Exception as e:
            logger.debug("Could not detect dynamic circuits: %s", e)
        return False

    @staticmethod
    def _has_gpu(backend: object) -> bool:
        """Check if AerSimulator has GPU acceleration."""
        try:
            available_methods = getattr(backend, 'available_methods', None)
            if callable(available_methods):
                methods = available_methods()
                return 'statevector_gpu' in methods or 'density_matrix_gpu' in methods
        except Exception as e:
            logger.debug("Could not detect GPU: %s", e)
        return False
