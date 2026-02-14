"""Tests for Privacy Plugin (Batch 17.4)."""
import pytest

from qubitcoin.qvm.privacy_plugin import (
    PrivacyPlugin,
    PrivacyProof,
    StealthAddressRecord,
    create_plugin,
    _generate_blinding_factor,
    _compute_commitment,
)
from qubitcoin.qvm.plugins import PluginManager, HookType


class TestPrivacyPluginLifecycle:
    """Test plugin lifecycle."""

    def test_name_and_version(self):
        p = PrivacyPlugin()
        assert p.name() == 'privacy'
        assert p.version() == '0.1.0'

    def test_description(self):
        p = PrivacyPlugin()
        assert 'SUSY' in p.description()

    def test_hooks_registered(self):
        p = PrivacyPlugin()
        hooks = p.hooks()
        assert HookType.PRE_EXECUTE in hooks
        assert HookType.POST_EXECUTE in hooks
        assert HookType.ON_LOG in hooks

    def test_start_stop(self):
        p = PrivacyPlugin()
        p.on_load()
        p.on_start()
        assert p._started is True
        p.on_stop()
        assert p._started is False

    def test_create_plugin_factory(self):
        p = create_plugin()
        assert isinstance(p, PrivacyPlugin)


class TestPrivacyPreExecute:
    """Test pre-execute hook for private transactions."""

    def test_non_private_tx_returns_none(self):
        p = PrivacyPlugin()
        result = p._pre_execute_hook({'tx_data': {'is_private': False}})
        assert result is None

    def test_private_tx_generates_commitment(self):
        p = PrivacyPlugin()
        result = p._pre_execute_hook({
            'tx_data': {
                'is_private': True,
                'amount': 1000,
                'tx_hash': 'abc123',
                'sender': 'alice',
            }
        })
        assert result is not None
        assert 'privacy_commitment' in result
        assert 'privacy_blinding' in result
        assert result['is_private_tx'] is True

    def test_private_tx_increments_count(self):
        p = PrivacyPlugin()
        assert p._private_tx_count == 0
        p._pre_execute_hook({
            'tx_data': {
                'is_private': True,
                'amount': 100,
                'tx_hash': 'tx1',
                'sender': 's1',
            }
        })
        assert p._private_tx_count == 1

    def test_no_tx_data_returns_none(self):
        p = PrivacyPlugin()
        result = p._pre_execute_hook({})
        assert result is None


class TestPrivacyPostExecute:
    """Test post-execute hook for proof generation."""

    def test_non_private_returns_none(self):
        p = PrivacyPlugin()
        result = p._post_execute_hook({'is_private_tx': False})
        assert result is None

    def test_private_generates_proof(self):
        p = PrivacyPlugin()
        result = p._post_execute_hook({
            'is_private_tx': True,
            'tx_hash': 'txhash123',
            'privacy_commitment': 'commit_abc',
        })
        assert result is not None
        assert 'privacy_proof_id' in result
        proof_id = result['privacy_proof_id']
        proof = p.get_proof(proof_id)
        assert proof is not None
        assert proof.proof_type == 'range_proof'
        assert proof.verified is True

    def test_proof_for_tx(self):
        p = PrivacyPlugin()
        p._post_execute_hook({
            'is_private_tx': True,
            'tx_hash': 'tx999',
            'privacy_commitment': 'commit',
        })
        proofs = p.get_proofs_for_tx('tx999')
        assert len(proofs) == 1


class TestPrivacyOnLog:
    """Test log filtering for private transactions."""

    def test_non_private_returns_none(self):
        p = PrivacyPlugin()
        result = p._on_log_hook({'is_private_tx': False})
        assert result is None

    def test_private_redacts_amount(self):
        p = PrivacyPlugin()
        result = p._on_log_hook({
            'is_private_tx': True,
            'log_data': {'amount': 1000, 'sender': 'alice'},
        })
        assert result is not None
        assert result['log_data']['amount'] == '[REDACTED]'
        assert result['log_data']['sender'] == 'alice'


class TestStealthAddresses:
    """Test stealth address management."""

    def test_register_stealth(self):
        p = PrivacyPlugin()
        record = p.register_stealth_address(
            one_time='0x111',
            ephemeral='0x222',
            hint='view_key_alice',
            block_height=100,
        )
        assert record.one_time_address == '0x111'
        assert record.block_height == 100

    def test_scan_stealth(self):
        p = PrivacyPlugin()
        p.register_stealth_address('0xa', '0xb', 'alice_view', 1)
        p.register_stealth_address('0xc', '0xd', 'bob_view', 2)
        p.register_stealth_address('0xe', '0xf', 'alice_view', 3)
        results = p.scan_stealth_addresses('alice_view')
        assert len(results) == 2

    def test_scan_no_match(self):
        p = PrivacyPlugin()
        p.register_stealth_address('0xa', '0xb', 'alice_view', 1)
        results = p.scan_stealth_addresses('unknown_view')
        assert len(results) == 0

    def test_record_to_dict(self):
        record = StealthAddressRecord(
            one_time_address='0x1',
            ephemeral_pubkey='0x2',
            recipient_hint='hint',
            block_height=5,
        )
        d = record.to_dict()
        assert d['one_time_address'] == '0x1'
        assert d['block_height'] == 5


class TestPluginManagerIntegration:
    """Test privacy plugin with PluginManager."""

    def test_register_and_start(self):
        mgr = PluginManager()
        plugin = PrivacyPlugin()
        mgr.register(plugin)
        assert mgr.load('privacy') is True
        assert mgr.start('privacy') is True

    def test_dispatch_pre_execute(self):
        mgr = PluginManager()
        plugin = PrivacyPlugin()
        mgr.register(plugin)
        mgr.load('privacy')
        mgr.start('privacy')

        ctx = mgr.dispatch_hook(HookType.PRE_EXECUTE, {
            'tx_data': {
                'is_private': True,
                'amount': 500,
                'tx_hash': 'tx_dispatch',
                'sender': 'sender1',
            }
        })
        assert ctx.get('is_private_tx') is True


class TestHelpers:
    """Test helper functions."""

    def test_blinding_factor_deterministic(self):
        b1 = _generate_blinding_factor('tx1', 'alice')
        b2 = _generate_blinding_factor('tx1', 'alice')
        assert b1 == b2

    def test_blinding_factor_different_inputs(self):
        b1 = _generate_blinding_factor('tx1', 'alice')
        b2 = _generate_blinding_factor('tx2', 'alice')
        assert b1 != b2

    def test_commitment_deterministic(self):
        b = _generate_blinding_factor('tx1', 'alice')
        c1 = _compute_commitment(100, b)
        c2 = _compute_commitment(100, b)
        assert c1 == c2

    def test_commitment_different_amounts(self):
        b = _generate_blinding_factor('tx1', 'alice')
        c1 = _compute_commitment(100, b)
        c2 = _compute_commitment(200, b)
        assert c1 != c2


class TestPrivacyStats:
    """Test plugin statistics."""

    def test_initial_stats(self):
        p = PrivacyPlugin()
        stats = p.get_stats()
        assert stats['private_tx_count'] == 0
        assert stats['proofs_generated'] == 0
        assert stats['stealth_addresses'] == 0

    def test_stats_after_activity(self):
        p = PrivacyPlugin()
        p._pre_execute_hook({
            'tx_data': {'is_private': True, 'amount': 1, 'tx_hash': 't', 'sender': 's'}
        })
        p._post_execute_hook({
            'is_private_tx': True, 'tx_hash': 't', 'privacy_commitment': 'c'
        })
        p.register_stealth_address('a', 'b', 'c')
        stats = p.get_stats()
        assert stats['private_tx_count'] == 1
        assert stats['proofs_generated'] == 1
        assert stats['stealth_addresses'] == 1

    def test_proof_to_dict(self):
        proof = PrivacyProof(
            proof_id='p1', tx_hash='tx1', proof_type='range_proof',
            proof_data=b'\x00' * 32, verified=True, created_at=1000.0,
        )
        d = proof.to_dict()
        assert d['proof_id'] == 'p1'
        assert d['proof_size'] == 32
