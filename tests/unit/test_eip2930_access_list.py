"""Unit tests for EIP-2930 access list support in QVM StateManager."""
import pytest
from unittest.mock import MagicMock


def _make_state_manager():
    """Create a StateManager with mocked dependencies."""
    from qubitcoin.qvm.state import StateManager
    db = MagicMock()
    sm = StateManager(db_manager=db)
    return sm


class TestAccessListEntry:
    """Test the AccessListEntry dataclass."""

    def test_import(self):
        from qubitcoin.qvm.state import AccessListEntry
        assert AccessListEntry is not None

    def test_create_with_defaults(self):
        from qubitcoin.qvm.state import AccessListEntry
        entry = AccessListEntry(address="abcdef1234567890" * 2 + "abcdef12")
        assert entry.address == "abcdef1234567890" * 2 + "abcdef12"
        assert entry.storage_keys == []

    def test_create_with_storage_keys(self):
        from qubitcoin.qvm.state import AccessListEntry
        keys = ["0000000000000000000000000000000000000000000000000000000000000001",
                "0000000000000000000000000000000000000000000000000000000000000002"]
        entry = AccessListEntry(address="aa" * 20, storage_keys=keys)
        assert len(entry.storage_keys) == 2
        assert entry.storage_keys[0].endswith("1")


class TestApplyAccessList:
    """Test apply_access_list gas calculation and warm cache population."""

    def test_empty_access_list_returns_zero_gas(self):
        sm = _make_state_manager()
        gas = sm.apply_access_list([])
        assert gas == 0
        assert len(sm.warm_addresses) == 0
        assert len(sm.warm_storage_keys) == 0

    def test_single_address_no_keys(self):
        from qubitcoin.qvm.state import AccessListEntry, ACCESS_LIST_ADDRESS_COST
        sm = _make_state_manager()
        entry = AccessListEntry(address="aa" * 20)
        gas = sm.apply_access_list([entry])
        assert gas == ACCESS_LIST_ADDRESS_COST
        assert ("aa" * 20) in sm.warm_addresses

    def test_single_address_with_keys(self):
        from qubitcoin.qvm.state import (
            AccessListEntry, ACCESS_LIST_ADDRESS_COST, ACCESS_LIST_STORAGE_KEY_COST,
        )
        sm = _make_state_manager()
        keys = ["key1", "key2", "key3"]
        entry = AccessListEntry(address="bb" * 20, storage_keys=keys)
        gas = sm.apply_access_list([entry])
        expected = ACCESS_LIST_ADDRESS_COST + 3 * ACCESS_LIST_STORAGE_KEY_COST
        assert gas == expected
        assert ("bb" * 20) in sm.warm_addresses
        for k in keys:
            assert (("bb" * 20), k) in sm.warm_storage_keys

    def test_multiple_entries(self):
        from qubitcoin.qvm.state import (
            AccessListEntry, ACCESS_LIST_ADDRESS_COST, ACCESS_LIST_STORAGE_KEY_COST,
        )
        sm = _make_state_manager()
        entries = [
            AccessListEntry(address="aa" * 20, storage_keys=["k1"]),
            AccessListEntry(address="bb" * 20, storage_keys=["k2", "k3"]),
            AccessListEntry(address="cc" * 20),
        ]
        gas = sm.apply_access_list(entries)
        expected = 3 * ACCESS_LIST_ADDRESS_COST + 3 * ACCESS_LIST_STORAGE_KEY_COST
        assert gas == expected
        assert len(sm.warm_addresses) == 3
        assert len(sm.warm_storage_keys) == 3

    def test_gas_cost_values_match_eip2930(self):
        """EIP-2930 specifies 2400 per address, 1900 per storage key."""
        from qubitcoin.qvm.state import ACCESS_LIST_ADDRESS_COST, ACCESS_LIST_STORAGE_KEY_COST
        assert ACCESS_LIST_ADDRESS_COST == 2400
        assert ACCESS_LIST_STORAGE_KEY_COST == 1900


class TestWarmCacheQueries:
    """Test is_address_warm and is_storage_key_warm."""

    def test_address_not_warm_by_default(self):
        sm = _make_state_manager()
        assert sm.is_address_warm("aa" * 20) is False

    def test_address_warm_after_apply(self):
        from qubitcoin.qvm.state import AccessListEntry
        sm = _make_state_manager()
        sm.apply_access_list([AccessListEntry(address="AA" * 20)])
        # Case-insensitive check
        assert sm.is_address_warm("AA" * 20) is True
        assert sm.is_address_warm("aa" * 20) is True

    def test_storage_key_not_warm_by_default(self):
        sm = _make_state_manager()
        assert sm.is_storage_key_warm("aa" * 20, "slot0") is False

    def test_storage_key_warm_after_apply(self):
        from qubitcoin.qvm.state import AccessListEntry
        sm = _make_state_manager()
        sm.apply_access_list([AccessListEntry(address="BB" * 20, storage_keys=["SLOT1"])])
        assert sm.is_storage_key_warm("BB" * 20, "SLOT1") is True
        # Case-insensitive
        assert sm.is_storage_key_warm("bb" * 20, "slot1") is True


class TestClearAccessList:
    """Test that clear_access_list resets warm caches."""

    def test_clear_resets_both_caches(self):
        from qubitcoin.qvm.state import AccessListEntry
        sm = _make_state_manager()
        sm.apply_access_list([
            AccessListEntry(address="aa" * 20, storage_keys=["k1", "k2"]),
        ])
        assert len(sm.warm_addresses) == 1
        assert len(sm.warm_storage_keys) == 2

        sm.clear_access_list()
        assert len(sm.warm_addresses) == 0
        assert len(sm.warm_storage_keys) == 0
        assert sm.is_address_warm("aa" * 20) is False


class TestConfigConstants:
    """Test that EIP-2930 gas costs are present in Config."""

    def test_config_has_eip2930_constants(self):
        from qubitcoin.config import Config
        assert hasattr(Config, 'EIP2930_ACCESS_LIST_ADDRESS_COST')
        assert hasattr(Config, 'EIP2930_ACCESS_LIST_STORAGE_KEY_COST')
        assert Config.EIP2930_ACCESS_LIST_ADDRESS_COST == 2400
        assert Config.EIP2930_ACCESS_LIST_STORAGE_KEY_COST == 1900
