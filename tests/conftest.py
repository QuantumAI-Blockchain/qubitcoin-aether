"""
Pytest conftest — stub heavy third-party dependencies so unit tests
can run without Qiskit, CockroachDB, IBM Quantum, etc.

This file is auto-loaded by pytest before any test module imports.
"""
import sys
import types


def _make_stub(name: str) -> types.ModuleType:
    """Create a stub module that returns MagicMock for any attribute."""
    from unittest.mock import MagicMock
    mod = types.ModuleType(name)
    mod.__path__ = []  # make it a package
    mod.__file__ = f"<stub:{name}>"

    class _StubAttr(MagicMock):
        """Mock that also works as a base class and decorator."""
        def __init_subclass__(cls, **kw):
            pass

    mod.__dict__['__getattr__'] = lambda attr: _StubAttr()
    return mod


# ── Heavy deps that may not be installed in test environments ──
_STUBS = [
    # Quantum
    'qiskit', 'qiskit.quantum_info', 'qiskit.circuit', 'qiskit.circuit.library',
    'qiskit.primitives', 'qiskit_aer', 'qiskit_ibm_runtime',
    'qiskit_algorithms', 'qiskit_algorithms.minimum_eigensolvers',
    'qiskit_algorithms.optimizers',
    # Monitoring
    'prometheus_fastapi_instrumentator',
    # P2P
    'grpc', 'grpc._channel',
    # IPFS
    'ipfshttpclient',
    # Cryptography (optional)
    'sha3',
    'oqs',
]

for _name in _STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = _make_stub(_name)
