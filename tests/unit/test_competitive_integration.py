"""Integration tests for all competitive features working together."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture()
def mock_db():
    db = MagicMock()
    db.get_session.side_effect = Exception("no db in unit tests")
    db.get_current_height.return_value = 1000
    return db


@pytest.fixture()
def config():
    """Set up all competitive feature configs."""
    from qubitcoin.config import Config
    Config.INHERITANCE_ENABLED = True
    Config.INHERITANCE_DEFAULT_INACTIVITY = 2618200
    Config.INHERITANCE_MIN_INACTIVITY = 26182
    Config.INHERITANCE_MAX_INACTIVITY = 95636360
    Config.INHERITANCE_GRACE_PERIOD = 78546

    Config.SECURITY_POLICY_ENABLED = True
    Config.SECURITY_DAILY_LIMIT_WINDOW = 26182
    Config.SECURITY_DEFAULT_TIME_LOCK = 7854
    Config.SECURITY_MAX_WHITELIST_SIZE = 100

    Config.DENIABLE_RPC_ENABLED = True
    Config.DENIABLE_RPC_MAX_BATCH = 100
    Config.DENIABLE_RPC_BLOOM_MAX_SIZE = 65536

    Config.FINALITY_ENABLED = True
    Config.FINALITY_MIN_STAKE = 100.0
    Config.FINALITY_THRESHOLD = 0.667
    Config.FINALITY_VOTE_EXPIRY_BLOCKS = 1000

    Config.STRATUM_ENABLED = False
    Config.STRATUM_PORT = 3333
    Config.STRATUM_GRPC_PORT = 50053


class TestAllFeaturesImport:
    """Verify all feature modules import cleanly."""

    def test_import_inheritance(self, config):
        from qubitcoin.reversibility.inheritance import InheritanceManager
        assert InheritanceManager is not None

    def test_import_high_security(self, config):
        from qubitcoin.reversibility.high_security import HighSecurityManager
        assert HighSecurityManager is not None

    def test_import_deniable_rpc(self, config):
        from qubitcoin.privacy.deniable_rpc import DeniableRPCHandler
        assert DeniableRPCHandler is not None

    def test_import_finality(self, config):
        from qubitcoin.consensus.finality import FinalityGadget
        assert FinalityGadget is not None

    def test_import_stratum_bridge(self, config):
        from qubitcoin.mining.stratum_bridge import StratumBridgeService
        assert StratumBridgeService is not None

    def test_import_bloom_filter(self, config):
        from qubitcoin.privacy.deniable_rpc import PythonBloomFilter, create_bloom_filter
        assert PythonBloomFilter is not None
        assert create_bloom_filter is not None


class TestFeatureCoexistence:
    """Verify features can coexist without conflicts."""

    def test_inheritance_and_security_together(self, mock_db, config):
        from qubitcoin.reversibility.inheritance import InheritanceManager
        from qubitcoin.reversibility.high_security import HighSecurityManager

        im = InheritanceManager(mock_db)
        hsm = HighSecurityManager(mock_db)

        # Both can operate on the same address
        addr = "test_address_12345"
        plan = im.set_beneficiary(addr, "beneficiary_addr", 100000, 500)
        assert plan is not None

        policy = hsm.set_policy(addr, daily_limit_qbc=1000.0)
        assert policy is not None

    def test_deniable_rpc_and_finality(self, mock_db, config):
        from qubitcoin.privacy.deniable_rpc import DeniableRPCHandler
        from qubitcoin.consensus.finality import FinalityGadget

        drpc = DeniableRPCHandler(mock_db)
        fg = FinalityGadget(mock_db)

        # Both work independently
        result = drpc.batch_balance(["a", "b", "c"])
        assert len(result) == 3

        fg.register_validator("v1", 500.0, 100)
        assert fg.get_validator_count() == 1

    def test_finality_reorg_protection(self, mock_db, config):
        from qubitcoin.consensus.finality import FinalityGadget

        fg = FinalityGadget(mock_db)
        fg.register_validator("v1", 500.0, 100)
        fg.submit_vote("v1", 50, "hash50")
        fg.check_finality(50)

        # Finalized at 50 — reorg to 40 blocked, to 60 OK
        assert not fg.is_reorg_allowed(40)
        assert fg.is_reorg_allowed(60)

    def test_bloom_filter_python_fallback(self, config):
        from qubitcoin.privacy.deniable_rpc import PythonBloomFilter

        bf = PythonBloomFilter(1024, 5)
        bf.insert("hello")
        bf.insert("world")
        assert bf.check("hello")
        assert bf.check("world")
        assert not bf.check("missing")

        # Serialization round-trip
        data = bf.to_bytes()
        bf2 = PythonBloomFilter.from_bytes(data, 5)
        assert bf2.check("hello")
        assert bf2.check("world")

    def test_all_metrics_importable(self, config):
        from qubitcoin.utils.metrics import (
            inheritance_active_plans,
            inheritance_pending_claims,
            security_active_policies,
            security_blocked_txs,
            stratum_workers_connected,
            stratum_blocks_found,
            deniable_batch_queries,
            deniable_bloom_queries,
            finality_last_finalized,
            finality_validator_count,
            finality_total_stake,
            finality_votes_cast,
            finality_checkpoints,
            finality_enabled,
        )
        # All metrics should be importable and usable
        assert finality_enabled is not None

    def test_config_all_features_have_defaults(self, config):
        from qubitcoin.config import Config

        # All competitive feature configs should have values
        assert isinstance(Config.INHERITANCE_ENABLED, bool)
        assert isinstance(Config.SECURITY_POLICY_ENABLED, bool)
        assert isinstance(Config.DENIABLE_RPC_ENABLED, bool)
        assert isinstance(Config.FINALITY_ENABLED, bool)
        assert isinstance(Config.STRATUM_ENABLED, bool)

        assert Config.INHERITANCE_DEFAULT_INACTIVITY > 0
        assert Config.FINALITY_THRESHOLD > 0
        assert Config.DENIABLE_RPC_MAX_BATCH > 0
