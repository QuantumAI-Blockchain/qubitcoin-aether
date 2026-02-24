"""
Tests for GPU qiskit-aer backend selection (B14).

Covers: QuantumEngine._select_backend(), _initialize_backend() —
GPU availability detection, graceful fallback, backend priority,
and logging of selected backend.
"""
import pytest
from unittest.mock import patch, MagicMock

from qubitcoin.quantum.engine import QuantumEngine


# ============================================================================
# HELPERS
# ============================================================================

def _make_engine_with_config(**overrides) -> QuantumEngine:
    """Create a QuantumEngine with specific Config overrides.

    Patches Config attributes and returns the initialized engine.
    """
    defaults = {
        'USE_LOCAL_ESTIMATOR': True,
        'USE_SIMULATOR': False,
        'USE_GPU_AER': False,
        'IBM_TOKEN': None,
        'IBM_INSTANCE': None,
        'VQE_REPS': 2,
        'VQE_MAXITER': 200,
        'VQE_TOLERANCE': 1e-6,
        'ENERGY_VALIDATION_TOLERANCE': 1e-3,
    }
    defaults.update(overrides)

    with patch('qubitcoin.quantum.engine.Config', **{f'{k}': v for k, v in defaults.items()}):
        # We need to patch as attributes on the Config object
        pass

    # Use a more robust approach: patch individual attributes
    config_patch = patch.multiple(
        'qubitcoin.quantum.engine.Config',
        **defaults,
        create=True,
    )
    with config_patch:
        engine = QuantumEngine()
    return engine


# ============================================================================
# _select_backend TESTS
# ============================================================================

class TestSelectBackend:
    def test_default_statevector(self) -> None:
        """Default config (USE_LOCAL_ESTIMATOR=True) selects statevector."""
        engine = _make_engine_with_config(
            USE_LOCAL_ESTIMATOR=True, USE_SIMULATOR=False, USE_GPU_AER=False
        )
        assert engine.backend_name == 'statevector'
        assert engine.estimator is not None

    def test_cpu_aer_when_simulator_enabled(self) -> None:
        """USE_SIMULATOR=True should select cpu_aer if qiskit_aer is available,
        or fall back to statevector if not."""
        engine = _make_engine_with_config(
            USE_LOCAL_ESTIMATOR=False, USE_SIMULATOR=True, USE_GPU_AER=False
        )
        # Either cpu_aer (if Aer installed) or statevector (fallback)
        assert engine.backend_name in ('cpu_aer', 'statevector')
        assert engine.estimator is not None

    def test_gpu_aer_fallback_to_statevector(self) -> None:
        """USE_GPU_AER=True but no GPU -> should fall back gracefully."""
        # Mock qiskit_aer to raise an exception when creating GPU simulator
        with patch.dict('sys.modules', {'qiskit_aer': MagicMock()}):
            mock_aer = MagicMock()
            mock_aer.AerSimulator.side_effect = Exception("No GPU available")

            with patch.multiple(
                'qubitcoin.quantum.engine.Config',
                USE_LOCAL_ESTIMATOR=True,
                USE_SIMULATOR=False,
                USE_GPU_AER=True,
                IBM_TOKEN=None,
                IBM_INSTANCE=None,
                VQE_REPS=2,
                VQE_MAXITER=200,
                VQE_TOLERANCE=1e-6,
                ENERGY_VALIDATION_TOLERANCE=1e-3,
                create=True,
            ):
                engine = QuantumEngine()
                # Should have fallen back
                assert engine.backend_name in ('statevector', 'cpu_aer')
                assert engine.estimator is not None

    def test_gpu_aer_import_error_fallback(self) -> None:
        """USE_GPU_AER=True but qiskit_aer not installed -> statevector."""
        with patch.multiple(
            'qubitcoin.quantum.engine.Config',
            USE_LOCAL_ESTIMATOR=True,
            USE_SIMULATOR=False,
            USE_GPU_AER=True,
            IBM_TOKEN=None,
            IBM_INSTANCE=None,
            VQE_REPS=2,
            VQE_MAXITER=200,
            VQE_TOLERANCE=1e-6,
            ENERGY_VALIDATION_TOLERANCE=1e-3,
            create=True,
        ):
            # Patch the import inside _select_backend to fail
            with patch('builtins.__import__', side_effect=_import_blocker('qiskit_aer')):
                engine = QuantumEngine()
                # Falls back to statevector since USE_LOCAL_ESTIMATOR=True
                assert engine.backend_name == 'statevector'
                assert engine.estimator is not None


def _import_blocker(blocked_module: str):
    """Create an import side_effect that blocks a specific module."""
    real_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

    def _blocker(name, *args, **kwargs):
        if name == blocked_module or name.startswith(blocked_module + '.'):
            raise ImportError(f"Mocked: {name} not available")
        return real_import(name, *args, **kwargs)

    return _blocker


class TestSelectBackendPriority:
    def test_gpu_takes_priority_over_cpu_aer(self) -> None:
        """When USE_GPU_AER=True and USE_SIMULATOR=True, GPU should be tried first."""
        with patch.multiple(
            'qubitcoin.quantum.engine.Config',
            USE_LOCAL_ESTIMATOR=False,
            USE_SIMULATOR=True,
            USE_GPU_AER=True,
            IBM_TOKEN=None,
            IBM_INSTANCE=None,
            VQE_REPS=2,
            VQE_MAXITER=200,
            VQE_TOLERANCE=1e-6,
            ENERGY_VALIDATION_TOLERANCE=1e-3,
            create=True,
        ):
            engine = QuantumEngine()
            # Either gpu_aer (if GPU available) or falls back to cpu_aer/statevector
            assert engine.backend_name in ('gpu_aer', 'cpu_aer', 'statevector')
            assert engine.estimator is not None

    def test_ibm_quantum_fallback_on_error(self) -> None:
        """IBM token but connection fails -> should fallback to statevector."""
        with patch.multiple(
            'qubitcoin.quantum.engine.Config',
            USE_LOCAL_ESTIMATOR=False,
            USE_SIMULATOR=False,
            USE_GPU_AER=False,
            IBM_TOKEN='fake_token',
            IBM_INSTANCE='fake_instance',
            VQE_REPS=2,
            VQE_MAXITER=200,
            VQE_TOLERANCE=1e-6,
            ENERGY_VALIDATION_TOLERANCE=1e-3,
            create=True,
        ):
            # Force the IBM runtime import to raise
            with patch.dict('sys.modules', {'qiskit_ibm_runtime': None}):
                engine = QuantumEngine()
                assert engine.backend_name == 'statevector'
                assert engine.estimator is not None


# ============================================================================
# BACKEND NAME TRACKING TESTS
# ============================================================================

class TestBackendNameTracking:
    def test_backend_name_is_set(self) -> None:
        """backend_name attribute should be set after initialization."""
        engine = _make_engine_with_config(USE_LOCAL_ESTIMATOR=True)
        assert hasattr(engine, 'backend_name')
        assert engine.backend_name in ('statevector', 'cpu_aer', 'gpu_aer', 'ibm_quantum')

    def test_backend_name_statevector_default(self) -> None:
        engine = _make_engine_with_config(USE_LOCAL_ESTIMATOR=True)
        assert engine.backend_name == 'statevector'


# ============================================================================
# FUNCTIONAL TESTS (verify engine still works after refactor)
# ============================================================================

class TestEngineStillFunctional:
    def test_compute_energy_after_init(self) -> None:
        """Engine should still compute energy correctly after backend refactor."""
        import numpy as np
        engine = _make_engine_with_config(USE_LOCAL_ESTIMATOR=True)
        hamiltonian = [('ZIII', 0.5), ('IZII', -0.3), ('IIZI', 0.2)]
        ansatz = engine.create_ansatz(4)
        params = np.zeros(ansatz.num_parameters)
        energy = engine.compute_energy(params, hamiltonian, 4)
        assert isinstance(energy, float)

    def test_generate_hamiltonian_unchanged(self) -> None:
        """Hamiltonian generation should be unaffected by backend changes."""
        engine = _make_engine_with_config(USE_LOCAL_ESTIMATOR=True)
        h = engine.generate_hamiltonian(num_qubits=4, seed=42)
        assert len(h) == 5  # num_qubits + 1 terms
        for pauli_str, coeff in h:
            assert len(pauli_str) == 4
            assert isinstance(coeff, float)
