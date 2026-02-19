"""Unit tests for bridge manager and bridge base types."""
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch


class TestBridgeTypes:
    """Test bridge type enumerations."""

    def test_chain_types(self):
        """All 8 chain types are defined."""
        from qubitcoin.bridge.base import ChainType
        assert ChainType.ETHEREUM.value == "ethereum"
        assert ChainType.POLYGON.value == "polygon"
        assert ChainType.BSC.value == "bsc"
        assert ChainType.ARBITRUM.value == "arbitrum"
        assert ChainType.OPTIMISM.value == "optimism"
        assert ChainType.SOLANA.value == "solana"
        assert ChainType.AVALANCHE.value == "avalanche"
        assert ChainType.BASE.value == "base"
        assert len(ChainType) == 8

    def test_bridge_statuses(self):
        """All bridge statuses are defined."""
        from qubitcoin.bridge.base import BridgeStatus
        expected = {'detected', 'confirming', 'pending', 'validating',
                    'processing', 'completed', 'failed', 'refunded'}
        actual = {s.value for s in BridgeStatus}
        assert actual == expected


class TestBridgeManagerInit:
    """Test bridge manager initialization."""

    def _make_manager(self):
        from qubitcoin.bridge.manager import BridgeManager
        db = MagicMock()
        return BridgeManager(db_manager=db)

    def test_init_empty_bridges(self):
        """Manager starts with no active bridges."""
        mgr = self._make_manager()
        assert len(mgr.bridges) == 0

    def test_init_no_bridge_address(self):
        """QBC bridge address is None by default."""
        mgr = self._make_manager()
        assert mgr.qbc_bridge_address is None


class TestBridgeCreation:
    """Test bridge instance creation."""

    def _make_manager(self):
        from qubitcoin.bridge.manager import BridgeManager
        return BridgeManager(db_manager=MagicMock())

    def test_create_ethereum_bridge(self):
        """Creating Ethereum bridge returns EVMBridge."""
        from qubitcoin.bridge.base import ChainType
        from qubitcoin.bridge.ethereum import EVMBridge
        mgr = self._make_manager()
        bridge = mgr._create_bridge(ChainType.ETHEREUM)
        assert isinstance(bridge, EVMBridge)

    def test_create_solana_bridge(self):
        """Creating Solana bridge returns SolanaBridge."""
        from qubitcoin.bridge.base import ChainType
        from qubitcoin.bridge.solana import SolanaBridge
        mgr = self._make_manager()
        bridge = mgr._create_bridge(ChainType.SOLANA)
        assert isinstance(bridge, SolanaBridge)

    def test_evm_chains_use_evm_bridge(self):
        """All non-Solana chains create EVMBridge instances."""
        from qubitcoin.bridge.base import ChainType
        from qubitcoin.bridge.ethereum import EVMBridge
        mgr = self._make_manager()
        evm_chains = [
            ChainType.POLYGON, ChainType.BSC, ChainType.ARBITRUM,
            ChainType.OPTIMISM, ChainType.AVALANCHE, ChainType.BASE,
        ]
        for chain in evm_chains:
            bridge = mgr._create_bridge(chain)
            assert isinstance(bridge, EVMBridge), f"{chain.value} should be EVMBridge"


class TestBridgeChainDetection:
    """Test auto-detection of configured chains."""

    def _make_manager(self):
        from qubitcoin.bridge.manager import BridgeManager
        return BridgeManager(db_manager=MagicMock())

    @patch.dict('os.environ', {}, clear=True)
    def test_no_chains_configured(self):
        """No chains detected when no env vars set."""
        mgr = self._make_manager()
        chains = mgr._detect_configured_chains()
        assert chains == []

    @patch.dict('os.environ', {'ETH_RPC_URL': 'http://eth:8545'})
    def test_ethereum_detected(self):
        """Ethereum detected when ETH_RPC_URL set."""
        from qubitcoin.bridge.base import ChainType
        mgr = self._make_manager()
        chains = mgr._detect_configured_chains()
        assert ChainType.ETHEREUM in chains

    @patch.dict('os.environ', {
        'ETH_RPC_URL': 'http://eth:8545',
        'SOLANA_RPC_URL': 'https://api.mainnet-beta.solana.com',
        'POLYGON_RPC_URL': 'https://polygon-rpc.com',
    })
    def test_multiple_chains_detected(self):
        """Multiple chains detected from env."""
        from qubitcoin.bridge.base import ChainType
        mgr = self._make_manager()
        chains = mgr._detect_configured_chains()
        assert ChainType.ETHEREUM in chains
        assert ChainType.SOLANA in chains
        assert ChainType.POLYGON in chains
        assert len(chains) == 3


class TestBridgeDeposit:
    """Test deposit processing."""

    def _make_manager(self):
        from qubitcoin.bridge.manager import BridgeManager
        return BridgeManager(db_manager=MagicMock())

    def test_deposit_unavailable_chain(self):
        """Deposit to unavailable chain returns None."""
        from qubitcoin.bridge.base import ChainType
        mgr = self._make_manager()

        async def _run():
            return await mgr.process_deposit(
                chain=ChainType.ETHEREUM,
                qbc_txid='tx123',
                qbc_address='qbc1sender',
                target_address='0xreceiver',
                amount=Decimal('100'),
            )

        result = asyncio.run(_run())
        assert result is None

    def test_deposit_routes_to_bridge(self):
        """Deposit routes to correct bridge's process_deposit."""
        from qubitcoin.bridge.base import ChainType
        mgr = self._make_manager()
        mock_bridge = AsyncMock()
        mock_bridge.process_deposit.return_value = '0xtxhash'
        mgr.bridges[ChainType.ETHEREUM] = mock_bridge

        async def _run():
            return await mgr.process_deposit(
                chain=ChainType.ETHEREUM,
                qbc_txid='tx123',
                qbc_address='qbc1sender',
                target_address='0xreceiver',
                amount=Decimal('50'),
            )

        result = asyncio.run(_run())
        assert result == '0xtxhash'
        mock_bridge.process_deposit.assert_called_once()


class TestBridgeShutdown:
    """Test bridge shutdown."""

    def test_shutdown_disconnects_all(self):
        """Shutdown disconnects all active bridges."""
        from qubitcoin.bridge.manager import BridgeManager
        from qubitcoin.bridge.base import ChainType
        mgr = BridgeManager(db_manager=MagicMock())

        bridge1 = AsyncMock()
        bridge2 = AsyncMock()
        mgr.bridges[ChainType.ETHEREUM] = bridge1
        mgr.bridges[ChainType.POLYGON] = bridge2

        asyncio.run(mgr.shutdown())
        bridge1.disconnect.assert_called_once()
        bridge2.disconnect.assert_called_once()
        assert len(mgr.bridges) == 0

    def test_shutdown_handles_errors(self):
        """Shutdown continues even if one bridge fails."""
        from qubitcoin.bridge.manager import BridgeManager
        from qubitcoin.bridge.base import ChainType
        mgr = BridgeManager(db_manager=MagicMock())

        bridge1 = AsyncMock()
        bridge1.disconnect.side_effect = RuntimeError("connection error")
        bridge2 = AsyncMock()
        mgr.bridges[ChainType.ETHEREUM] = bridge1
        mgr.bridges[ChainType.POLYGON] = bridge2

        asyncio.run(mgr.shutdown())  # should not raise
        bridge2.disconnect.assert_called_once()
        assert len(mgr.bridges) == 0
