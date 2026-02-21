"""
Pytest conftest — stub heavy third-party dependencies so unit tests
can run without Qiskit, CockroachDB, IBM Quantum, etc.

This file is auto-loaded by pytest before any test module imports.
"""
import os
import sys
import types
from pathlib import Path

# Ensure src/ is on the Python path so `import qubitcoin` works
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# Ensure log directory is writable — Docker may leave logs/ root-owned.
# Redirect to /tmp if the default path is not writable.
_project_root = Path(__file__).resolve().parent.parent
_log_dir = _project_root / "logs"
try:
    _log_dir.mkdir(parents=True, exist_ok=True)
    _test_file = _log_dir / ".write_test"
    _test_file.touch()
    _test_file.unlink()
except (PermissionError, OSError):
    _tmp_log = Path("/tmp/qbc_test_logs")
    _tmp_log.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QBC_LOG_DIR", str(_tmp_log))


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
    # Web3 / bridge deps
    'web3', 'web3.contract', 'web3.middleware', 'web3.types',
    'eth_account', 'eth_account.signers', 'eth_account.signers.local',
    'base58',
    'solders', 'solders.keypair', 'solders.pubkey', 'solders.system_program',
    'solana', 'solana.rpc', 'solana.rpc.async_api', 'solana.rpc.commitment',
    'spl', 'spl.token', 'spl.token.client', 'spl.token.constants',
    # Cryptography (optional)
    'sha3',
    'oqs',
    # gRPC generated stubs
    'p2p_service_pb2', 'p2p_service_pb2_grpc',
]

for _name in _STUBS:
    if _name not in sys.modules:
        sys.modules[_name] = _make_stub(_name)
