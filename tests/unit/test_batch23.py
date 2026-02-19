"""Unit tests for Batch 23: Aether WS streaming, QBC circulation, Token indexer.

Tests:
  - AetherWSManager: registration, unregistration, stats, eviction
  - CirculationTracker: era, reward, emission, halving, history
  - TokenIndexer: registration, transfer parsing, balances, mint/burn
"""
import asyncio
import hashlib
import time
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock

from qubitcoin.aether.ws_streaming import AetherWSManager, AetherWSClient
from qubitcoin.aether.circulation import CirculationTracker, CirculationSnapshot
from qubitcoin.qvm.token_indexer import (
    TokenIndexer, TokenTransfer, TokenInfo, TRANSFER_TOPIC,
    _decode_address_topic, _decode_uint256,
)


# ---------------------------------------------------------------------------
# AetherWSManager tests
# ---------------------------------------------------------------------------

class TestAetherWSManager:
    """Test Aether WebSocket streaming manager."""

    def test_register_client(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        client_id = mgr.register(ws)
        assert mgr.client_count == 1
        assert client_id == id(ws)

    def test_register_with_session(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        mgr.register(ws, session_id='session-123')
        client = mgr._clients[id(ws)]
        assert client.session_id == 'session-123'
        assert 'aether_response' in client.subscriptions

    def test_register_with_custom_subscriptions(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        mgr.register(ws, subscriptions={'phi_update', 'token_transfer'})
        client = mgr._clients[id(ws)]
        assert 'phi_update' in client.subscriptions
        assert 'token_transfer' in client.subscriptions

    def test_register_filters_invalid_events(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        mgr.register(ws, subscriptions={'phi_update', 'invalid_event_xyz'})
        client = mgr._clients[id(ws)]
        assert 'phi_update' in client.subscriptions
        assert 'invalid_event_xyz' not in client.subscriptions

    def test_unregister_client(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        mgr.register(ws)
        assert mgr.client_count == 1
        mgr.unregister(ws)
        assert mgr.client_count == 0

    def test_unregister_nonexistent(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        mgr.unregister(ws)  # Should not raise
        assert mgr.client_count == 0

    def test_evict_oldest_on_capacity(self):
        mgr = AetherWSManager(max_clients=2)
        ws1, ws2, ws3 = MagicMock(), MagicMock(), MagicMock()
        mgr.register(ws1)
        mgr._clients[id(ws1)].connected_at = 100.0
        mgr.register(ws2)
        mgr._clients[id(ws2)].connected_at = 200.0
        mgr.register(ws3)
        mgr._clients[id(ws3)].connected_at = 300.0
        # ws1 should have been evicted (oldest)
        assert mgr.client_count == 2
        assert id(ws1) not in mgr._clients

    def test_broadcast_to_subscribers(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        ws.send_text = AsyncMock()
        mgr.register(ws, subscriptions={'phi_update'})

        sent = asyncio.run(
            mgr.broadcast('phi_update', {'value': 2.5})
        )
        assert sent == 1
        ws.send_text.assert_called_once()

    def test_broadcast_skips_non_subscribers(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        ws.send_text = AsyncMock()
        mgr.register(ws, subscriptions={'phi_update'})

        sent = asyncio.run(
            mgr.broadcast('consciousness_event', {'event': 'test'})
        )
        assert sent == 0
        ws.send_text.assert_not_called()

    def test_broadcast_session_scoped(self):
        mgr = AetherWSManager()
        ws1, ws2 = MagicMock(), MagicMock()
        ws1.send_text = AsyncMock()
        ws2.send_text = AsyncMock()
        mgr.register(ws1, session_id='session-A')
        mgr.register(ws2, session_id='session-B')

        sent = asyncio.run(
            mgr.broadcast('aether_response',
                          {'text': 'hello'}, session_id='session-A')
        )
        assert sent == 1
        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    def test_broadcast_removes_disconnected(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        ws.send_text = AsyncMock(side_effect=Exception("disconnected"))
        mgr.register(ws, subscriptions={'phi_update'})
        assert mgr.client_count == 1

        asyncio.run(
            mgr.broadcast('phi_update', {'value': 1.0})
        )
        assert mgr.client_count == 0

    def test_broadcast_invalid_event(self):
        mgr = AetherWSManager()
        ws = MagicMock()
        ws.send_text = AsyncMock()
        mgr.register(ws, subscriptions={'phi_update'})

        sent = asyncio.run(
            mgr.broadcast('nonexistent_event', {})
        )
        assert sent == 0

    def test_get_stats(self):
        mgr = AetherWSManager(max_clients=500)
        ws = MagicMock()
        mgr.register(ws, session_id='s1', subscriptions={'phi_update'})
        stats = mgr.get_stats()
        assert stats['connected_clients'] == 1
        assert stats['max_clients'] == 500
        assert len(stats['clients']) == 1
        assert stats['clients'][0]['session_id'] == 's1'

    def test_valid_events_constant(self):
        assert 'aether_response' in AetherWSManager.VALID_EVENTS
        assert 'phi_update' in AetherWSManager.VALID_EVENTS
        assert 'knowledge_node' in AetherWSManager.VALID_EVENTS
        assert 'consciousness_event' in AetherWSManager.VALID_EVENTS
        assert 'circulation_update' in AetherWSManager.VALID_EVENTS
        assert 'token_transfer' in AetherWSManager.VALID_EVENTS


# ---------------------------------------------------------------------------
# CirculationTracker tests
# ---------------------------------------------------------------------------

class TestCirculationTracker:
    """Test QBC circulation tracking."""

    def test_era_zero(self):
        assert CirculationTracker.compute_era(0) == 0
        assert CirculationTracker.compute_era(100) == 0

    def test_era_boundary(self):
        from qubitcoin.config import Config
        # First block of era 1
        era1_start = Config.HALVING_INTERVAL
        assert CirculationTracker.compute_era(era1_start) == 1
        assert CirculationTracker.compute_era(era1_start - 1) == 0

    def test_era_negative_height(self):
        assert CirculationTracker.compute_era(-1) == 0

    def test_block_reward_era0(self):
        from qubitcoin.config import Config
        reward = CirculationTracker.compute_block_reward(0)
        assert reward == Config.INITIAL_REWARD

    def test_block_reward_decreases_with_era(self):
        from qubitcoin.config import Config
        r0 = CirculationTracker.compute_block_reward(0)
        r1 = CirculationTracker.compute_block_reward(Config.HALVING_INTERVAL)
        assert r1 < r0
        # Should be ~INITIAL_REWARD / PHI
        expected = Config.INITIAL_REWARD / Decimal(str(Config.PHI))
        assert abs(r1 - expected) < Decimal('0.01')

    def test_total_emitted_genesis(self):
        # Block 0 should emit exactly 1 block reward
        from qubitcoin.config import Config
        total = CirculationTracker.compute_total_emitted(0)
        assert total == Config.INITIAL_REWARD

    def test_total_emitted_10_blocks(self):
        from qubitcoin.config import Config
        total = CirculationTracker.compute_total_emitted(9)
        expected = Config.INITIAL_REWARD * 10
        assert total == expected

    def test_total_emitted_negative(self):
        total = CirculationTracker.compute_total_emitted(-1)
        assert total == Decimal('0')

    def test_total_emitted_capped(self):
        from qubitcoin.config import Config
        # Very large height should be capped at MAX_SUPPLY
        total = CirculationTracker.compute_total_emitted(999_999_999)
        assert total <= Config.MAX_SUPPLY

    def test_record_block(self):
        tracker = CirculationTracker()
        snap = tracker.record_block(0, block_timestamp=1000.0)
        assert snap.block_height == 0
        assert snap.current_era == 0
        assert snap.total_circulating > Decimal('0')
        assert snap.halving_event is False

    def test_record_block_with_fees(self):
        tracker = CirculationTracker()
        tracker.record_block(0, fees_in_block=Decimal('0.5'))
        tracker.record_block(1, fees_in_block=Decimal('0.3'))
        snap = tracker.get_current()
        assert snap.total_fees_collected == Decimal('0.8')

    def test_halving_detected(self):
        from qubitcoin.config import Config
        tracker = CirculationTracker()
        # Record last block of era 0
        tracker.record_block(Config.HALVING_INTERVAL - 1)
        # Record first block of era 1 — should trigger halving
        snap = tracker.record_block(Config.HALVING_INTERVAL)
        assert snap.halving_event is True
        assert snap.current_era == 1
        assert len(tracker.get_halving_events()) == 1

    def test_no_false_halving(self):
        tracker = CirculationTracker()
        snap = tracker.record_block(5)
        assert snap.halving_event is False
        assert len(tracker.get_halving_events()) == 0

    def test_get_current(self):
        tracker = CirculationTracker()
        assert tracker.get_current() is None
        tracker.record_block(0)
        assert tracker.get_current() is not None
        assert tracker.get_current().block_height == 0

    def test_get_history(self):
        tracker = CirculationTracker()
        for i in range(5):
            tracker.record_block(i)
        history = tracker.get_history(limit=3)
        assert len(history) == 3

    def test_history_capped(self):
        tracker = CirculationTracker(max_history=3)
        for i in range(10):
            tracker.record_block(i)
        assert len(tracker._history) == 3

    def test_emission_schedule(self):
        tracker = CirculationTracker()
        schedule = tracker.get_emission_schedule(num_eras=3)
        assert len(schedule) == 3
        assert schedule[0]['era'] == 0
        assert schedule[1]['era'] == 1
        # Reward decreases each era
        r0 = Decimal(schedule[0]['reward_per_block'])
        r1 = Decimal(schedule[1]['reward_per_block'])
        assert r1 < r0

    def test_snapshot_to_dict(self):
        tracker = CirculationTracker()
        snap = tracker.record_block(100)
        d = snap.to_dict()
        assert 'block_height' in d
        assert 'total_circulating' in d
        assert 'current_reward' in d
        assert 'current_era' in d
        assert 'percent_emitted' in d
        assert 'max_supply' in d

    def test_get_stats(self):
        tracker = CirculationTracker()
        tracker.record_block(0)
        stats = tracker.get_stats()
        assert stats['current'] is not None
        assert stats['halving_events'] == 0
        assert stats['snapshots_stored'] == 1

    def test_percent_emitted_small(self):
        tracker = CirculationTracker()
        snap = tracker.record_block(0)
        assert snap.percent_emitted > 0
        assert snap.percent_emitted < 1  # 1 block is a tiny fraction


# ---------------------------------------------------------------------------
# TokenIndexer tests
# ---------------------------------------------------------------------------

class TestTokenIndexer:
    """Test QBC-20/721 token transfer indexing."""

    def test_register_token(self):
        indexer = TokenIndexer()
        info = indexer.register_token(
            '0xAbcD1234', 'QBC-20',
            name='TestToken', symbol='TT', decimals=18,
        )
        assert info.symbol == 'TT'
        assert info.token_standard == 'QBC-20'
        # Address should be lowercased
        assert info.contract_address == '0xabcd1234'

    def test_register_token_twice(self):
        indexer = TokenIndexer()
        indexer.register_token('0xABC', 'QBC-20', symbol='T1')
        indexer.register_token('0xABC', 'QBC-20', symbol='T2')
        # Second registration overwrites
        info = indexer.get_token_info('0xABC')
        assert info['symbol'] == 'T2'

    def test_get_all_tokens(self):
        indexer = TokenIndexer()
        indexer.register_token('0xA', 'QBC-20', symbol='A')
        indexer.register_token('0xB', 'QBC-721', symbol='B')
        tokens = indexer.get_all_tokens()
        assert len(tokens) == 2

    def test_process_transfer_log(self):
        indexer = TokenIndexer()
        indexer.register_token('0xtoken1', 'QBC-20', symbol='TK1')

        logs = [{
            'address': '0xtoken1',
            'topics': [
                '0x' + TRANSFER_TOPIC,
                '0x' + '0' * 24 + 'aaa' + '0' * 13,  # from
                '0x' + '0' * 24 + 'bbb' + '0' * 13,  # to
            ],
            'data': '0x' + hex(1000)[2:].zfill(64),  # amount
        }]

        transfers = indexer.process_receipt_logs(
            'tx1', block_height=10, logs=logs, timestamp=1000.0,
        )
        assert len(transfers) == 1
        assert transfers[0].amount == Decimal('1000')
        assert transfers[0].token_standard == 'QBC-20'

    def test_transfer_updates_balances(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        from_addr = '0x' + 'a' * 40
        to_addr = '0x' + 'b' * 40
        indexer.register_token(addr, 'QBC-20')

        # Mint to from_addr first
        mint_logs = [{
            'address': addr,
            'topics': [
                '0x' + TRANSFER_TOPIC,
                '0x' + '0' * 64,  # from zero (mint)
                '0x' + 'a' * 40,  # to from_addr
            ],
            'data': '0x' + hex(5000)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('mint_tx', 1, mint_logs)
        assert indexer.get_token_balance(addr, from_addr) == Decimal('5000')

        # Transfer from from_addr to to_addr
        transfer_logs = [{
            'address': addr,
            'topics': [
                '0x' + TRANSFER_TOPIC,
                '0x' + 'a' * 40,  # from
                '0x' + 'b' * 40,  # to
            ],
            'data': '0x' + hex(2000)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('tx2', 2, transfer_logs)
        assert indexer.get_token_balance(addr, from_addr) == Decimal('3000')
        assert indexer.get_token_balance(addr, to_addr) == Decimal('2000')

    def test_mint_increases_supply(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20', total_supply=Decimal('0'))

        logs = [{
            'address': addr,
            'topics': [
                '0x' + TRANSFER_TOPIC,
                '0x' + '0' * 64,  # from zero address (mint)
                '0x' + 'a' * 40,
            ],
            'data': '0x' + hex(10000)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('tx', 1, logs)
        info = indexer.get_token_info(addr)
        assert Decimal(info['total_supply']) == Decimal('10000')

    def test_burn_decreases_supply(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20', total_supply=Decimal('10000'))

        # Burn: transfer to zero address
        logs = [{
            'address': addr,
            'topics': [
                '0x' + TRANSFER_TOPIC,
                '0x' + 'a' * 40,
                '0x' + '0' * 64,  # to zero (burn)
            ],
            'data': '0x' + hex(3000)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('burn_tx', 5, logs)
        info = indexer.get_token_info(addr)
        assert Decimal(info['total_supply']) == Decimal('7000')

    def test_holder_count_updated(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20')

        # Mint to 3 different addresses
        for i in range(3):
            holder = '0x' + chr(ord('a') + i) * 40
            logs = [{
                'address': addr,
                'topics': [
                    '0x' + TRANSFER_TOPIC,
                    '0x' + '0' * 64,
                    '0x' + chr(ord('a') + i) * 40,
                ],
                'data': '0x' + hex(100)[2:].zfill(64),
            }]
            indexer.process_receipt_logs(f'tx{i}', i, logs)

        info = indexer.get_token_info(addr)
        assert info['total_holders'] == 3

    def test_holder_removed_on_zero_balance(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20')

        # Mint 100 to holder
        mint_logs = [{
            'address': addr,
            'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'a' * 40],
            'data': '0x' + hex(100)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('tx1', 1, mint_logs)
        assert indexer.get_token_info(addr)['total_holders'] == 1

        # Transfer all 100 to burn
        burn_logs = [{
            'address': addr,
            'topics': ['0x' + TRANSFER_TOPIC, '0x' + 'a' * 40, '0x' + '0' * 64],
            'data': '0x' + hex(100)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('tx2', 2, burn_logs)
        assert indexer.get_token_info(addr)['total_holders'] == 0

    def test_get_token_holders_sorted(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20')

        # Mint different amounts
        for i, amount in enumerate([50, 200, 100]):
            logs = [{
                'address': addr,
                'topics': [
                    '0x' + TRANSFER_TOPIC,
                    '0x' + '0' * 64,
                    '0x' + chr(ord('a') + i) * 40,
                ],
                'data': '0x' + hex(amount)[2:].zfill(64),
            }]
            indexer.process_receipt_logs(f'tx{i}', i, logs)

        holders = indexer.get_token_holders(addr, limit=10)
        assert len(holders) == 3
        # Sorted by balance descending
        balances = [Decimal(h['balance']) for h in holders]
        assert balances == sorted(balances, reverse=True)

    def test_get_transfers_all(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20')

        for i in range(5):
            logs = [{
                'address': addr,
                'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'a' * 40],
                'data': '0x' + hex(i + 1)[2:].zfill(64),
            }]
            indexer.process_receipt_logs(f'tx{i}', i, logs)

        transfers = indexer.get_transfers(limit=3)
        assert len(transfers) == 3

    def test_get_transfers_by_contract(self):
        indexer = TokenIndexer()
        indexer.register_token('0xtokenA', 'QBC-20')
        indexer.register_token('0xtokenB', 'QBC-20')

        for addr in ['0xtokenA', '0xtokenB']:
            logs = [{
                'address': addr,
                'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'a' * 40],
                'data': '0x64',
            }]
            indexer.process_receipt_logs(f'tx_{addr}', 1, logs)

        transfers_a = indexer.get_transfers(contract_address='0xtokenA')
        assert all(t['token_address'] == '0xtokena' for t in transfers_a)

    def test_get_transfers_by_address(self):
        indexer = TokenIndexer()
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20')

        holder = '0x' + 'f' * 40

        # Mint to holder
        logs = [{
            'address': addr,
            'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'f' * 40],
            'data': '0x' + hex(500)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('tx1', 1, logs)

        # Transfer from holder
        logs2 = [{
            'address': addr,
            'topics': ['0x' + TRANSFER_TOPIC, '0x' + 'f' * 40, '0x' + 'a' * 40],
            'data': '0x' + hex(200)[2:].zfill(64),
        }]
        indexer.process_receipt_logs('tx2', 2, logs2)

        transfers = indexer.get_transfers(address=holder)
        assert len(transfers) == 2  # received + sent

    def test_auto_register_unknown_token(self):
        indexer = TokenIndexer()
        # Process log for an unregistered token
        logs = [{
            'address': '0xunknown',
            'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'a' * 40],
            'data': '0x64',
        }]
        indexer.process_receipt_logs('tx1', 1, logs)
        assert indexer.get_token_info('0xunknown') is not None

    def test_non_transfer_log_ignored(self):
        indexer = TokenIndexer()
        logs = [{
            'address': '0xtoken',
            'topics': ['0xdeadbeef'],  # Not a Transfer event
            'data': '0x0',
        }]
        transfers = indexer.process_receipt_logs('tx1', 1, logs)
        assert len(transfers) == 0

    def test_empty_logs(self):
        indexer = TokenIndexer()
        transfers = indexer.process_receipt_logs('tx1', 1, [])
        assert len(transfers) == 0

    def test_max_transfers_cap(self):
        indexer = TokenIndexer(max_transfers=5)
        addr = '0xtoken'
        indexer.register_token(addr, 'QBC-20')

        for i in range(10):
            logs = [{
                'address': addr,
                'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'a' * 40],
                'data': '0x' + hex(i + 1)[2:].zfill(64),
            }]
            indexer.process_receipt_logs(f'tx{i}', i, logs)

        assert len(indexer._transfers) == 5

    def test_get_stats(self):
        indexer = TokenIndexer()
        indexer.register_token('0xA', 'QBC-20')
        stats = indexer.get_stats()
        assert stats['tracked_tokens'] == 1
        assert stats['total_transfers'] == 0


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------

class TestTokenHelpers:
    """Test token indexer helper functions."""

    def test_decode_address_topic(self):
        # Full 64-char topic with address in last 40 chars
        topic = '0x' + '0' * 24 + 'abcdef1234567890abcdef1234567890abcdef12'
        result = _decode_address_topic(topic)
        assert result == '0xabcdef1234567890abcdef1234567890abcdef12'

    def test_decode_address_topic_short(self):
        topic = '0xabcd'
        result = _decode_address_topic(topic)
        assert result.startswith('0x')
        assert len(result) == 42  # 0x + 40 chars

    def test_decode_uint256_hex(self):
        result = _decode_uint256('0x3e8')  # 1000
        assert result == Decimal('1000')

    def test_decode_uint256_zero(self):
        result = _decode_uint256('0x0')
        assert result == Decimal('0')

    def test_decode_uint256_empty(self):
        result = _decode_uint256('')
        assert result == Decimal('0')

    def test_decode_uint256_int(self):
        result = _decode_uint256(42)
        assert result == Decimal('42')

    def test_transfer_topic_is_sha3(self):
        expected = hashlib.sha3_256(
            b'Transfer(address,address,uint256)'
        ).hexdigest()
        assert TRANSFER_TOPIC == expected


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------

class TestCirculationIntegration:
    """Test circulation tracker with realistic block sequences."""

    def test_sequential_blocks(self):
        tracker = CirculationTracker()
        for height in range(100):
            snap = tracker.record_block(height, block_timestamp=1000 + height)
        current = tracker.get_current()
        assert current.block_height == 99
        from qubitcoin.config import Config
        expected = Config.INITIAL_REWARD * 100
        assert current.total_circulating == expected

    def test_circulation_never_exceeds_supply(self):
        from qubitcoin.config import Config
        for height in [0, 1000, Config.HALVING_INTERVAL, Config.HALVING_INTERVAL * 5]:
            total = CirculationTracker.compute_total_emitted(height)
            assert total <= Config.MAX_SUPPLY


class TestTokenIndexerIntegration:
    """Test token indexer with QBC-721 tokens."""

    def test_qbc721_transfer(self):
        indexer = TokenIndexer()
        indexer.register_token('0xnft', 'QBC-721', symbol='QNFT')

        # Mint token ID 42
        logs = [{
            'address': '0xnft',
            'topics': [
                '0x' + TRANSFER_TOPIC,
                '0x' + '0' * 64,  # from zero (mint)
                '0x' + 'a' * 40,  # to holder
            ],
            'data': '0x' + hex(42)[2:].zfill(64),  # token ID
        }]
        transfers = indexer.process_receipt_logs('nft_mint', 1, logs)
        assert len(transfers) == 1
        assert transfers[0].token_standard == 'QBC-721'
        assert transfers[0].amount == Decimal('42')

    def test_multiple_tokens_tracked(self):
        indexer = TokenIndexer()
        indexer.register_token('0xerc20', 'QBC-20', symbol='TK')
        indexer.register_token('0xerc721', 'QBC-721', symbol='NFT')

        for addr in ['0xerc20', '0xerc721']:
            logs = [{
                'address': addr,
                'topics': ['0x' + TRANSFER_TOPIC, '0x' + '0' * 64, '0x' + 'a' * 40],
                'data': '0x64',
            }]
            indexer.process_receipt_logs(f'tx_{addr}', 1, logs)

        stats = indexer.get_stats()
        assert stats['tracked_tokens'] == 2
        assert stats['total_transfers'] == 2
