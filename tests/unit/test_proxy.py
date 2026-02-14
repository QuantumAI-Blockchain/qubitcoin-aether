"""Tests for Contract Upgrade Patterns — Proxy Registry (Batch 19.1)."""
import pytest

from qubitcoin.contracts.proxy import (
    ProxyRegistry,
    ProxyRecord,
    UpgradeEvent,
    UpgradeEventType,
    IMPLEMENTATION_SLOT,
    ADMIN_SLOT,
)


class TestProxyDeployment:
    def test_deploy_proxy(self):
        reg = ProxyRegistry()
        rec = reg.deploy_proxy("proxy1", "impl_v1", "admin", block_height=10)
        assert rec.proxy_address == "proxy1"
        assert rec.implementation_address == "impl_v1"
        assert rec.admin_address == "admin"
        assert rec.version == 1
        assert rec.block_height == 10

    def test_deploy_records_event(self):
        reg = ProxyRegistry()
        rec = reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert len(rec.upgrade_history) == 1
        assert rec.upgrade_history[0].event_type == UpgradeEventType.DEPLOYED

    def test_deploy_duplicate_raises(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        with pytest.raises(ValueError, match="already exists"):
            reg.deploy_proxy("proxy1", "impl_v2", "admin")

    def test_deploy_empty_impl_raises(self):
        reg = ProxyRegistry()
        with pytest.raises(ValueError, match="Implementation address required"):
            reg.deploy_proxy("proxy1", "", "admin")

    def test_to_dict(self):
        reg = ProxyRegistry()
        rec = reg.deploy_proxy("proxy1", "impl_v1", "admin")
        d = rec.to_dict()
        assert d["proxy_address"] == "proxy1"
        assert d["upgrade_count"] == 1
        assert len(d["history"]) == 1


class TestProxyUpgrade:
    def test_upgrade_success(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.upgrade("proxy1", "impl_v2", "admin", block_height=50) is True
        rec = reg.get_proxy("proxy1")
        assert rec.implementation_address == "impl_v2"
        assert rec.version == 2

    def test_upgrade_denied_non_admin(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.upgrade("proxy1", "impl_v2", "attacker") is False
        rec = reg.get_proxy("proxy1")
        assert rec.implementation_address == "impl_v1"

    def test_upgrade_nonexistent(self):
        reg = ProxyRegistry()
        assert reg.upgrade("missing", "impl_v2", "admin") is False

    def test_upgrade_same_impl_skipped(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.upgrade("proxy1", "impl_v1", "admin") is False

    def test_upgrade_empty_impl_denied(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.upgrade("proxy1", "", "admin") is False

    def test_multiple_upgrades(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        reg.upgrade("proxy1", "impl_v2", "admin", block_height=10)
        reg.upgrade("proxy1", "impl_v3", "admin", block_height=20)
        rec = reg.get_proxy("proxy1")
        assert rec.version == 3
        assert len(rec.upgrade_history) == 3  # deploy + 2 upgrades

    def test_upgrade_event_recorded(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        reg.upgrade("proxy1", "impl_v2", "admin")
        hist = reg.get_upgrade_history("proxy1")
        assert len(hist) == 2
        assert hist[1]["event_type"] == "upgraded"
        assert hist[1]["old_implementation"] == "impl_v1"
        assert hist[1]["new_implementation"] == "impl_v2"


class TestAdminChange:
    def test_change_admin(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin1")
        assert reg.change_admin("proxy1", "admin2", "admin1") is True
        rec = reg.get_proxy("proxy1")
        assert rec.admin_address == "admin2"

    def test_change_admin_denied(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin1")
        assert reg.change_admin("proxy1", "admin2", "attacker") is False
        assert reg.get_proxy("proxy1").admin_address == "admin1"

    def test_change_admin_nonexistent(self):
        reg = ProxyRegistry()
        assert reg.change_admin("missing", "new_admin", "admin") is False

    def test_change_admin_empty_denied(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.change_admin("proxy1", "", "admin") is False

    def test_new_admin_can_upgrade(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin1")
        reg.change_admin("proxy1", "admin2", "admin1")
        # Old admin can no longer upgrade
        assert reg.upgrade("proxy1", "impl_v2", "admin1") is False
        # New admin can
        assert reg.upgrade("proxy1", "impl_v2", "admin2") is True


class TestResolution:
    def test_resolve_implementation(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.resolve_implementation("proxy1") == "impl_v1"

    def test_resolve_nonexistent(self):
        reg = ProxyRegistry()
        assert reg.resolve_implementation("not_a_proxy") is None

    def test_is_proxy(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        assert reg.is_proxy("proxy1") is True
        assert reg.is_proxy("regular_contract") is False

    def test_resolve_after_upgrade(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        reg.upgrade("proxy1", "impl_v2", "admin")
        assert reg.resolve_implementation("proxy1") == "impl_v2"


class TestQueries:
    def test_list_proxies(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "i1", "a")
        reg.deploy_proxy("p2", "i2", "a")
        assert len(reg.list_proxies()) == 2

    def test_get_proxies_for_implementation(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "shared_impl", "a")
        reg.deploy_proxy("p2", "shared_impl", "a")
        reg.deploy_proxy("p3", "other_impl", "a")
        proxies = reg.get_proxies_for_implementation("shared_impl")
        assert set(proxies) == {"p1", "p2"}

    def test_impl_mapping_updated_on_upgrade(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "impl_v1", "admin")
        reg.upgrade("p1", "impl_v2", "admin")
        assert reg.get_proxies_for_implementation("impl_v1") == []
        assert reg.get_proxies_for_implementation("impl_v2") == ["p1"]

    def test_stats(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "i1", "a")
        reg.deploy_proxy("p2", "i2", "a")
        reg.upgrade("p1", "i3", "a")
        stats = reg.get_stats()
        assert stats["total_proxies"] == 2
        assert stats["total_upgrades"] == 1

    def test_upgrade_history_empty_for_nonexistent(self):
        reg = ProxyRegistry()
        assert reg.get_upgrade_history("missing") == []


class TestEIP1967Slots:
    def test_slots_are_deterministic(self):
        assert isinstance(IMPLEMENTATION_SLOT, int)
        assert isinstance(ADMIN_SLOT, int)
        assert IMPLEMENTATION_SLOT != ADMIN_SLOT

    def test_static_accessors(self):
        assert ProxyRegistry.get_implementation_slot() == IMPLEMENTATION_SLOT
        assert ProxyRegistry.get_admin_slot() == ADMIN_SLOT
