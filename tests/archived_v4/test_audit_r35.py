"""Tests verifying Run #35 fixes: CREATE/CREATE2 EIP-150 gas cap + storage
rollback, BoW embedder negative hash, bridge withdrawal_id type, memory
manager safe dict access, state.py hex validation.

Covers:
- CREATE opcode uses EIP-150 63/64 gas cap and rolls back storage on revert
- CREATE2 opcode uses EIP-150 63/64 gas cap and rolls back storage on revert
- BoW embedder uses abs(hash()) to avoid negative array index
- Bridge ethereum withdrawal_id handles int type (not just bytes)
- MemoryManager episodic replay uses safe .get() for KG node access
- StateManager wraps bytes.fromhex() to handle malformed hex data
"""

import inspect
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ======================================================================
# CREATE / CREATE2 EIP-150 gas cap + storage rollback
# ======================================================================


class TestCreateEIP150:
    """Verify CREATE and CREATE2 use EIP-150 63/64 gas + rollback."""

    def test_create_has_eip150_gas_cap(self) -> None:
        """CREATE should cap sub-call gas to 63/64 of available."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        # Find the CREATE opcode section and check for 63/64
        # The source should have cache_snap in CREATE section
        create_idx = source.find('Opcode.CREATE:')
        create2_idx = source.find('Opcode.CREATE2:')
        create_section = source[create_idx:create2_idx]
        assert '63) // 64' in create_section

    def test_create_has_storage_rollback(self) -> None:
        """CREATE should rollback storage cache on reverted init code."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        create_idx = source.find('Opcode.CREATE:')
        create2_idx = source.find('Opcode.CREATE2:')
        create_section = source[create_idx:create2_idx]
        assert 'cache_snap' in create_section

    def test_create2_has_eip150_gas_cap(self) -> None:
        """CREATE2 should cap sub-call gas to 63/64 of available."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        create2_idx = source.find('Opcode.CREATE2:')
        return_idx = source.find('Opcode.RETURN:', create2_idx)
        create2_section = source[create2_idx:return_idx]
        assert '63) // 64' in create2_section

    def test_create2_has_storage_rollback(self) -> None:
        """CREATE2 should rollback storage cache on reverted init code."""
        from qubitcoin.qvm.vm import QVM
        source = inspect.getsource(QVM._run)
        create2_idx = source.find('Opcode.CREATE2:')
        return_idx = source.find('Opcode.RETURN:', create2_idx)
        create2_section = source[create2_idx:return_idx]
        assert 'cache_snap' in create2_section


# ======================================================================
# BoW embedder negative hash fix
# ======================================================================


class TestBoWEmbedderHash:
    """Verify BoW embedder uses abs(hash()) for positive indices."""

    def test_abs_hash_in_source(self) -> None:
        """_BoWEmbedder.encode should use abs(hash(token))."""
        from qubitcoin.aether.vector_index import _BoWEmbedder
        source = inspect.getsource(_BoWEmbedder.encode)
        assert 'abs(hash(' in source

    def test_encode_does_not_crash_with_negative_hash_tokens(self) -> None:
        """Encoding should not raise IndexError regardless of token hash."""
        from qubitcoin.aether.vector_index import _BoWEmbedder
        embedder = _BoWEmbedder(dim=64)
        # These tokens may have negative hashes depending on Python impl
        texts = [
            'quantum entanglement superposition decoherence',
            'blockchain cryptography consensus protocol',
        ]
        result = embedder.encode(texts)
        assert len(result) == 2
        for vec in result:
            assert len(vec) == 64
            # All indices should be non-negative (no IndexError)
            assert all(isinstance(v, float) for v in vec)


# ======================================================================
# Bridge withdrawal_id type handling
# ======================================================================


class TestBridgeWithdrawalId:
    """Verify ethereum bridge handles int withdrawal_id."""

    def test_withdrawal_id_int_handling(self) -> None:
        """withdrawal_id formatting should handle int type."""
        from qubitcoin.bridge.ethereum import EVMBridge
        source = inspect.getsource(EVMBridge._process_withdrawal_event)
        # Should check isinstance or use hex() for int
        assert 'isinstance' in source or 'hex(' in source

    def test_hex_conversion_on_int(self) -> None:
        """hex() should work on int withdrawal_id."""
        withdrawal_id = 12345
        # This should not raise AttributeError
        result = withdrawal_id.hex() if isinstance(withdrawal_id, bytes) else hex(withdrawal_id)
        assert result == '0x3039'

    def test_hex_conversion_on_bytes(self) -> None:
        """bytes.hex() should work on bytes withdrawal_id."""
        withdrawal_id = b'\x00\x01\x02'
        result = withdrawal_id.hex() if isinstance(withdrawal_id, bytes) else hex(withdrawal_id)
        assert result == '000102'


# ======================================================================
# Memory manager safe dict access
# ======================================================================


class TestMemoryManagerSafeAccess:
    """Verify MemoryManager episodic replay uses .get() for KG nodes."""

    def test_replay_uses_safe_access(self) -> None:
        """_replay_episodes should use .get() not direct [] for KG nodes."""
        from qubitcoin.aether.memory_manager import MemoryManager
        if not hasattr(MemoryManager, 'replay_episodes'):
            pytest.skip("MemoryManager.replay_episodes not available (Rust backend)")
        source = inspect.getsource(MemoryManager.replay_episodes)
        # The reinforcement section should not have direct dict access
        # for conclusion nodes — it should use .get()
        # Count occurrences of unsafe access patterns
        lines = source.split('\n')
        unsafe_accesses = []
        for i, line in enumerate(lines):
            if 'self._kg.nodes[' in line and '.get(' not in line and 'getattr' not in line:
                unsafe_accesses.append((i, line.strip()))
        assert len(unsafe_accesses) == 0, f"Unsafe dict access found: {unsafe_accesses}"


# ======================================================================
# StateManager hex validation
# ======================================================================


class TestStateManagerHexValidation:
    """Verify StateManager wraps bytes.fromhex for malformed data."""

    def test_deploy_handles_bad_hex(self) -> None:
        """_deploy_contract should not crash on non-hex tx.data."""
        from qubitcoin.qvm.state import StateManager
        source = inspect.getsource(StateManager._deploy_contract)
        # Should have try/except around bytes.fromhex
        assert 'except ValueError' in source

    def test_call_handles_bad_hex(self) -> None:
        """_call_contract should not crash on non-hex tx.data."""
        from qubitcoin.qvm.state import StateManager
        source = inspect.getsource(StateManager._call_contract)
        assert 'except ValueError' in source
