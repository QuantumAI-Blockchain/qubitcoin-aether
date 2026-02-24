"""Tests for Contract Upgrade Patterns — Proxy Registry (Batch 19.1 + V15 Timelock)."""
import time

import pytest

from qubitcoin.contracts.proxy import (
    ProxyRegistry,
    ProxyRecord,
    ScheduledUpgrade,
    UpgradeEvent,
    UpgradeEventType,
    IMPLEMENTATION_SLOT,
    ADMIN_SLOT,
    MAX_SCHEDULE_AGE,
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


# ======================================================================
# V15 — Proxy Upgrade Timelock + upgrade_and_call Tests
# ======================================================================


class TestUpgradeAndCall:
    """Test the upgrade_and_call method (combines upgrade + initializer data)."""

    def test_upgrade_and_call_success(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        call_data = b"\x01\x02\x03"
        result = reg.upgrade_and_call("proxy1", "impl_v2", call_data, "admin", block_height=50)
        assert result is True
        rec = reg.get_proxy("proxy1")
        assert rec.implementation_address == "impl_v2"
        assert rec.version == 2

    def test_upgrade_and_call_denied_non_admin(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        result = reg.upgrade_and_call("proxy1", "impl_v2", b"\x01", "attacker")
        assert result is False
        assert reg.get_proxy("proxy1").implementation_address == "impl_v1"

    def test_upgrade_and_call_empty_data(self):
        """upgrade_and_call with empty data should still perform the upgrade."""
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        result = reg.upgrade_and_call("proxy1", "impl_v2", b"", "admin")
        assert result is True
        assert reg.get_proxy("proxy1").implementation_address == "impl_v2"


class TestScheduledUpgrade:
    """Test the timelocked/scheduled upgrade flow."""

    def test_schedule_upgrade_success(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=60.0, block_height=100
        )
        assert upgrade_id is not None
        scheduled = reg.get_scheduled_upgrade(upgrade_id)
        assert scheduled is not None
        assert scheduled.proxy_address == "proxy1"
        assert scheduled.new_implementation == "impl_v2"
        assert not scheduled.executed
        assert not scheduled.canceled
        assert scheduled.execute_after > scheduled.scheduled_at

    def test_schedule_denied_non_admin(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "attacker", delay=60.0
        )
        assert upgrade_id is None

    def test_schedule_denied_nonexistent_proxy(self):
        reg = ProxyRegistry()
        upgrade_id = reg.schedule_upgrade(
            "missing", "impl_v2", "admin", delay=60.0
        )
        assert upgrade_id is None

    def test_schedule_denied_empty_implementation(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade("proxy1", "", "admin", delay=60.0)
        assert upgrade_id is None

    def test_schedule_denied_below_minimum_delay(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        reg.set_minimum_delay(300.0)  # 5 minutes minimum
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=60.0  # only 1 minute
        )
        assert upgrade_id is None

    def test_execute_scheduled_upgrade_success(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=0.0
        )
        assert upgrade_id is not None
        # Execute immediately (delay=0 means execute_after = now)
        result = reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=time.time() + 1.0
        )
        assert result is True
        rec = reg.get_proxy("proxy1")
        assert rec.implementation_address == "impl_v2"
        assert rec.version == 2
        scheduled = reg.get_scheduled_upgrade(upgrade_id)
        assert scheduled.executed is True

    def test_execute_denied_timelock_active(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        now = time.time()
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=3600.0  # 1 hour
        )
        assert upgrade_id is not None
        # Try to execute immediately — should fail (timelock active)
        result = reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=now + 1.0
        )
        assert result is False
        assert reg.get_proxy("proxy1").implementation_address == "impl_v1"

    def test_execute_after_timelock_expires(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        now = time.time()
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=3600.0  # 1 hour
        )
        # Execute after 1 hour + 1 second
        result = reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=now + 3601.0
        )
        assert result is True
        assert reg.get_proxy("proxy1").implementation_address == "impl_v2"

    def test_execute_denied_expired_schedule(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        now = time.time()
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=0.0
        )
        # Try to execute after MAX_SCHEDULE_AGE (expired)
        result = reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=now + MAX_SCHEDULE_AGE + 100.0
        )
        assert result is False

    def test_cancel_scheduled_upgrade(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=3600.0
        )
        assert upgrade_id is not None
        result = reg.cancel_scheduled_upgrade(upgrade_id, "admin")
        assert result is True
        scheduled = reg.get_scheduled_upgrade(upgrade_id)
        assert scheduled.canceled is True

    def test_execute_canceled_upgrade_fails(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=0.0
        )
        reg.cancel_scheduled_upgrade(upgrade_id, "admin")
        result = reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=time.time() + 1.0
        )
        assert result is False

    def test_cancel_denied_non_admin(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=3600.0
        )
        result = reg.cancel_scheduled_upgrade(upgrade_id, "attacker")
        assert result is False

    def test_cancel_already_executed_fails(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("proxy1", "impl_v1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "proxy1", "impl_v2", "admin", delay=0.0
        )
        reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=time.time() + 1.0
        )
        result = reg.cancel_scheduled_upgrade(upgrade_id, "admin")
        assert result is False

    def test_list_scheduled_upgrades(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "i1", "admin")
        reg.deploy_proxy("p2", "i2", "admin")
        reg.schedule_upgrade("p1", "i1_v2", "admin", delay=60.0)
        reg.schedule_upgrade("p2", "i2_v2", "admin", delay=60.0)
        all_scheduled = reg.list_scheduled_upgrades()
        assert len(all_scheduled) == 2
        p1_only = reg.list_scheduled_upgrades(proxy_address="p1")
        assert len(p1_only) == 1
        assert p1_only[0]["proxy_address"] == "p1"

    def test_stats_include_scheduled(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "i1", "admin")
        reg.schedule_upgrade("p1", "i2", "admin", delay=60.0)
        stats = reg.get_stats()
        assert stats["total_scheduled"] == 1
        assert stats["pending_scheduled"] == 1

    def test_schedule_records_event_in_history(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "i1", "admin")
        reg.schedule_upgrade("p1", "i2", "admin", delay=60.0)
        history = reg.get_upgrade_history("p1")
        assert len(history) == 2  # deploy + schedule
        assert history[1]["event_type"] == "upgrade_scheduled"
        assert history[1]["new_implementation"] == "i2"

    def test_schedule_with_call_data(self):
        reg = ProxyRegistry()
        reg.deploy_proxy("p1", "i1", "admin")
        upgrade_id = reg.schedule_upgrade(
            "p1", "i2", "admin", delay=0.0, call_data=b"\xde\xad\xbe\xef"
        )
        scheduled = reg.get_scheduled_upgrade(upgrade_id)
        assert scheduled.call_data == b"\xde\xad\xbe\xef"
        result = reg.execute_scheduled_upgrade(
            upgrade_id, "admin", current_time=time.time() + 1.0
        )
        assert result is True
        assert reg.get_proxy("p1").implementation_address == "i2"

    def test_minimum_delay_getter_setter(self):
        reg = ProxyRegistry()
        assert reg.get_minimum_delay() == 0.0
        reg.set_minimum_delay(300.0)
        assert reg.get_minimum_delay() == 300.0
