"""Unit tests for the QVM ABI Registry."""
import pytest
from unittest.mock import MagicMock


SAMPLE_ABI = [
    {"type": "function", "name": "transfer", "inputs": [
        {"name": "to", "type": "address"},
        {"name": "amount", "type": "uint256"},
    ], "outputs": [{"name": "", "type": "bool"}]},
    {"type": "event", "name": "Transfer", "inputs": [
        {"name": "from", "type": "address", "indexed": True},
        {"name": "to", "type": "address", "indexed": True},
        {"name": "value", "type": "uint256"},
    ]},
]


class TestABIRegistryInit:
    """Test ABIRegistry initialization."""

    def test_init_no_db(self):
        """Registry initializes without a database."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        registry = ABIRegistry()
        assert registry.get_stats()["total_registered"] == 0

    def test_init_with_db(self):
        """Registry accepts a mock database manager."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        db = MagicMock()
        registry = ABIRegistry(db_manager=db)
        assert registry._db is db


class TestABIRegistration:
    """Test ABI registration and retrieval."""

    def _make_registry(self):
        from qubitcoin.qvm.abi_registry import ABIRegistry
        return ABIRegistry()

    def test_register_and_get(self):
        """Registered ABI can be retrieved."""
        registry = self._make_registry()
        registry.register_abi("0xABC123", SAMPLE_ABI)
        abi = registry.get_abi("0xABC123")
        assert abi == SAMPLE_ABI

    def test_case_insensitive_lookup(self):
        """Addresses are normalized to lowercase."""
        registry = self._make_registry()
        registry.register_abi("0xABC123", SAMPLE_ABI)
        assert registry.get_abi("0xabc123") is not None
        assert registry.get_abi("0xABC123") is not None

    def test_get_nonexistent_returns_none(self):
        """Getting ABI for unregistered address returns None."""
        registry = self._make_registry()
        assert registry.get_abi("0xNONEXIST") is None

    def test_overwrite_abi(self):
        """Registering a new ABI overwrites the previous one."""
        registry = self._make_registry()
        registry.register_abi("0xABC", SAMPLE_ABI)
        new_abi = [{"type": "function", "name": "foo", "inputs": [], "outputs": []}]
        registry.register_abi("0xABC", new_abi)
        assert registry.get_abi("0xABC") == new_abi

    def test_get_record_returns_full_record(self):
        """get_record returns a ContractABIRecord with metadata."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        registry = ABIRegistry()
        registry.register_abi("0xDEF", SAMPLE_ABI)
        record = registry.get_record("0xDEF")
        assert record is not None
        assert record.address == "0xdef"
        assert record.abi == SAMPLE_ABI
        assert record.verified is False
        assert record.abi_hash != ""
        assert record.registered_at > 0


class TestContractVerification:
    """Test contract verification workflow."""

    def _make_registry(self):
        from qubitcoin.qvm.abi_registry import ABIRegistry
        return ABIRegistry()

    def test_verify_registered_contract(self):
        """Verification succeeds for a registered contract."""
        registry = self._make_registry()
        registry.register_abi("0xABC", SAMPLE_ABI)
        result = registry.verify_contract("0xABC", "pragma solidity ^0.8.24;", "0.8.24")
        assert result is True
        assert registry.is_verified("0xABC")

    def test_verify_unregistered_returns_false(self):
        """Verification fails for an unregistered contract."""
        registry = self._make_registry()
        result = registry.verify_contract("0xNONE", "source", "0.8.24")
        assert result is False

    def test_is_verified_false_by_default(self):
        """Contracts are not verified by default."""
        registry = self._make_registry()
        registry.register_abi("0xABC", SAMPLE_ABI)
        assert registry.is_verified("0xABC") is False

    def test_is_verified_nonexistent(self):
        """is_verified returns False for unknown addresses."""
        registry = self._make_registry()
        assert registry.is_verified("0xUNKNOWN") is False

    def test_get_verified_contracts(self):
        """get_verified_contracts returns only verified addresses."""
        registry = self._make_registry()
        registry.register_abi("0xA", SAMPLE_ABI)
        registry.register_abi("0xB", SAMPLE_ABI)
        registry.register_abi("0xC", SAMPLE_ABI)
        registry.verify_contract("0xA", "source", "0.8.24")
        registry.verify_contract("0xC", "source", "0.8.24")
        verified = registry.get_verified_contracts()
        assert "0xa" in verified
        assert "0xc" in verified
        assert "0xb" not in verified
        assert len(verified) == 2

    def test_verified_record_has_source(self):
        """Verified record stores source code and compiler version."""
        registry = self._make_registry()
        registry.register_abi("0xABC", SAMPLE_ABI)
        registry.verify_contract("0xABC", "contract Foo {}", "0.8.24")
        record = registry.get_record("0xABC")
        assert record.source_code == "contract Foo {}"
        assert record.compiler_version == "0.8.24"
        assert record.verified_at is not None


class TestABIRegistryStats:
    """Test statistics reporting."""

    def test_stats_empty(self):
        """Stats for empty registry."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        registry = ABIRegistry()
        stats = registry.get_stats()
        assert stats["total_registered"] == 0
        assert stats["total_verified"] == 0
        assert stats["total_unverified"] == 0

    def test_stats_with_data(self):
        """Stats reflect registered and verified contracts."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        registry = ABIRegistry()
        registry.register_abi("0xA", SAMPLE_ABI)
        registry.register_abi("0xB", SAMPLE_ABI)
        registry.register_abi("0xC", SAMPLE_ABI)
        registry.verify_contract("0xB", "source", "0.8.24")
        stats = registry.get_stats()
        assert stats["total_registered"] == 3
        assert stats["total_verified"] == 1
        assert stats["total_unverified"] == 2

    def test_get_all_contracts(self):
        """get_all_contracts returns all registered addresses."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        registry = ABIRegistry()
        registry.register_abi("0xA", SAMPLE_ABI)
        registry.register_abi("0xB", SAMPLE_ABI)
        all_contracts = registry.get_all_contracts()
        assert len(all_contracts) == 2
        assert "0xa" in all_contracts
        assert "0xb" in all_contracts


class TestContractABIRecordSerialization:
    """Test ContractABIRecord.to_dict()."""

    def test_to_dict(self):
        """to_dict produces JSON-safe output."""
        from qubitcoin.qvm.abi_registry import ABIRegistry
        registry = ABIRegistry()
        registry.register_abi("0xABC", SAMPLE_ABI)
        record = registry.get_record("0xABC")
        d = record.to_dict()
        assert d["address"] == "0xabc"
        assert d["abi"] == SAMPLE_ABI
        assert d["verified"] is False
        assert isinstance(d["abi_hash"], str)
        assert len(d["abi_hash"]) == 64  # SHA-256 hex
