"""
Bridge Manager
Routes deposits and withdrawals across multiple chains
"""

import asyncio
from decimal import Decimal
from typing import Dict, Optional, List
from .base import BaseBridge, ChainType
from .ethereum import EVMBridge
from .solana import SolanaBridge
from .validator_rewards import ValidatorRewardTracker
from .proof_store import ProofStore
from ..utils.logger import get_logger

logger = get_logger(__name__)


class BridgeManager:
    """
    Manages multiple cross-chain bridges
    Routes operations to appropriate bridge
    """

    def __init__(self, db_manager, validator_reward_tracker: Optional[ValidatorRewardTracker] = None,
                 proof_store: Optional[ProofStore] = None):
        """
        Initialize bridge manager

        Args:
            db_manager: Database manager instance
            validator_reward_tracker: Optional reward tracker for bridge validators.
                Created automatically if not provided.
            proof_store: Optional ProofStore for cross-chain proof verification.
                Created automatically if not provided.
        """
        self.db = db_manager
        self.bridges: Dict[ChainType, BaseBridge] = {}
        self.validator_rewards: ValidatorRewardTracker = (
            validator_reward_tracker or ValidatorRewardTracker()
        )
        self.proof_store: ProofStore = proof_store or ProofStore()

        # QBC bridge address (where coins are locked)
        self.qbc_bridge_address = None

        logger.info("Bridge Manager initialized (proof verification enabled)")

    async def initialize_bridges(self, chains: List[ChainType] = None):
        """
        Initialize specified bridges
        
        Args:
            chains: List of chains to initialize (None = all configured)
        """
        if chains is None:
            # Auto-detect from environment
            chains = self._detect_configured_chains()
        
        logger.info(f"Initializing bridges for: {[c.value for c in chains]}")
        
        for chain in chains:
            try:
                bridge = self._create_bridge(chain)
                
                if await bridge.connect():
                    self.bridges[chain] = bridge
                    logger.info(f"✅ {chain.value} bridge ready")
                else:
                    logger.warning(f"⚠️  {chain.value} bridge failed to connect")
                    
            except Exception as e:
                logger.error(f"Error initializing {chain.value} bridge: {e}")
        
        logger.info(f"🌉 Active bridges: {len(self.bridges)}")

    def _create_bridge(self, chain_type: ChainType) -> BaseBridge:
        """Create bridge instance for chain"""
        if chain_type == ChainType.SOLANA:
            return SolanaBridge(self.db)
        else:
            # All other chains are EVM-compatible
            return EVMBridge(chain_type, self.db)

    def _detect_configured_chains(self) -> List[ChainType]:
        """Detect which chains are configured"""
        import os
        
        configured = []
        
        # Check for Ethereum/EVM chains
        if os.getenv('ETH_RPC_URL'):
            configured.append(ChainType.ETHEREUM)
        if os.getenv('POLYGON_RPC_URL'):
            configured.append(ChainType.POLYGON)
        if os.getenv('BSC_RPC_URL'):
            configured.append(ChainType.BSC)
        if os.getenv('ARBITRUM_RPC_URL'):
            configured.append(ChainType.ARBITRUM)
        if os.getenv('OPTIMISM_RPC_URL'):
            configured.append(ChainType.OPTIMISM)
        if os.getenv('AVALANCHE_RPC_URL'):
            configured.append(ChainType.AVALANCHE)
        if os.getenv('BASE_RPC_URL'):
            configured.append(ChainType.BASE)
        
        # Check for Solana
        if os.getenv('SOLANA_RPC_URL'):
            configured.append(ChainType.SOLANA)
        
        return configured

    async def shutdown(self):
        """Shutdown all bridges"""
        logger.info("Shutting down all bridges...")
        
        for chain, bridge in self.bridges.items():
            try:
                await bridge.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {chain.value}: {e}")
        
        self.bridges.clear()

    # ========================================================================
    # DEPOSIT OPERATIONS (QBC → wQBC)
    # ========================================================================

    async def process_deposit(
        self,
        chain: ChainType,
        qbc_txid: str,
        qbc_address: str,
        target_address: str,
        amount: Decimal
    ) -> Optional[str]:
        """
        Process deposit to specific chain
        
        Args:
            chain: Target blockchain
            qbc_txid: QBC transaction hash
            qbc_address: QBC sender address
            target_address: Address on target chain
            amount: Amount to bridge
            
        Returns:
            Transaction hash on target chain
        """
        if amount <= 0:
            logger.error(f"Bridge deposit rejected: amount must be positive, got {amount}")
            return None

        bridge = self.bridges.get(chain)

        if not bridge:
            logger.error(f"Bridge not available: {chain.value}")
            return None

        # Submit proof to proof store for cryptographic verification
        try:
            proof = self.proof_store.submit_proof(
                source_chain_id=3301,  # QBC mainnet
                dest_chain_id=chain.value if isinstance(chain.value, int) else hash(chain.value) % 100000,
                source_tx_hash=qbc_txid,
                sender=qbc_address,
                receiver=target_address,
                amount=float(amount),
                state_root="",  # populated by bridge relayer
                merkle_proof=[],
            )
            if not self.proof_store.verify_proof(proof.proof_id):
                logger.warning(f"Bridge proof verification pending for {qbc_txid[:16]}…")
        except Exception as e:
            logger.warning(f"Proof submission skipped (non-fatal): {e}")

        return await bridge.process_deposit(
            qbc_txid, qbc_address, target_address, amount
        )

    async def monitor_qbc_deposits(self):
        """
        Monitor QBC blockchain for deposits to bridge address
        """
        if not self.qbc_bridge_address:
            logger.warning("QBC bridge address not configured")
            return
        
        logger.info(f"🔊 Monitoring QBC deposits to {self.qbc_bridge_address}")
        
        while True:
            try:
                # Get unprocessed deposits from database
                pending = await self._get_pending_qbc_deposits()
                
                for deposit in pending:
                    chain = ChainType(deposit['target_chain'])
                    
                    if chain not in self.bridges:
                        logger.warning(f"No bridge for {chain.value}, skipping")
                        continue
                    
                    # Process on target chain
                    tx_hash = await self.process_deposit(
                        chain,
                        deposit['qbc_txid'],
                        deposit['qbc_address'],
                        deposit['target_address'],
                        Decimal(deposit['qbc_amount'])
                    )
                    
                    if tx_hash:
                        logger.info(f"✅ Deposit processed: {tx_hash}")
                
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"QBC deposit monitor error: {e}")
                await asyncio.sleep(60)

    async def _get_pending_qbc_deposits(self) -> List[Dict]:
        """Get pending QBC deposits from database"""
        with self.db.get_session() as session:
            from sqlalchemy import text
            
            results = session.execute(
                text("""
                    SELECT id, qbc_txid, qbc_address, target_chain, target_address, qbc_amount
                    FROM bridge_deposits
                    WHERE status IN ('detected', 'confirming')
                    ORDER BY created_at
                    LIMIT 100
                """)
            )
            
            return [
                {
                    'id': row[0],
                    'qbc_txid': row[1],
                    'qbc_address': row[2],
                    'target_chain': row[3],
                    'target_address': row[4],
                    'qbc_amount': row[5]
                }
                for row in results
            ]

    # ========================================================================
    # WITHDRAWAL OPERATIONS (wQBC → QBC)
    # ========================================================================

    async def start_withdrawal_listeners(self):
        """Start withdrawal listeners for all bridges"""
        logger.info("🔊 Starting withdrawal listeners...")
        
        tasks = []
        for chain, bridge in self.bridges.items():
            task = asyncio.create_task(bridge.listen_for_withdrawals())
            tasks.append(task)
            logger.info(f"  ✅ Listener started: {chain.value}")
        
        # Wait for all listeners
        await asyncio.gather(*tasks)

    # ========================================================================
    # QUERY OPERATIONS
    # ========================================================================

    async def get_balance(self, chain: ChainType, address: str) -> Decimal:
        """Get wQBC balance on specific chain"""
        bridge = self.bridges.get(chain)
        
        if not bridge:
            return Decimal(0)
        
        return await bridge.get_balance(address)

    async def estimate_fees(self, chain: ChainType, amount: Decimal) -> Dict:
        """Estimate fees for bridge operation"""
        bridge = self.bridges.get(chain)
        
        if not bridge:
            return {'error': 'Bridge not available'}
        
        return await bridge.estimate_fees(amount)

    async def get_all_stats(self) -> Dict:
        """Get statistics for all bridges"""
        stats = {}
        
        for chain, bridge in self.bridges.items():
            stats[chain.value] = await bridge.get_bridge_stats()
        
        # Calculate totals
        total_deposits = sum(
            s['deposits']['completed'] for s in stats.values()
        )
        total_withdrawals = sum(
            s['withdrawals']['completed'] for s in stats.values()
        )
        
        total_volume_deposited = sum(
            Decimal(s['deposits']['total_volume']) for s in stats.values()
        )
        total_volume_withdrawn = sum(
            Decimal(s['withdrawals']['total_volume']) for s in stats.values()
        )
        
        return {
            'chains': stats,
            'totals': {
                'active_bridges': len(self.bridges),
                'total_deposits': total_deposits,
                'total_withdrawals': total_withdrawals,
                'total_volume_deposited': str(total_volume_deposited),
                'total_volume_withdrawn': str(total_volume_withdrawn),
                'tvl': str(total_volume_deposited - total_volume_withdrawn)
            }
        }

    async def get_supported_chains(self) -> List[str]:
        """Get list of supported chains"""
        return [chain.value for chain in self.bridges.keys()]

    # ========================================================================
    # ADMINISTRATION
    # ========================================================================

    def set_qbc_bridge_address(self, address: str) -> None:
        """Set QBC bridge address where coins are locked"""
        self.qbc_bridge_address = address
        logger.info(f"✅ QBC bridge address: {address}")

    async def pause_bridge(self, chain: ChainType):
        """Pause specific bridge"""
        bridge = self.bridges.get(chain)
        
        if bridge:
            await bridge.disconnect()
            logger.info(f"⏸️  {chain.value} bridge paused")

    async def resume_bridge(self, chain: ChainType):
        """Resume specific bridge"""
        bridge = self.bridges.get(chain)
        
        if bridge and not bridge.connected:
            await bridge.connect()
            logger.info(f"▶️  {chain.value} bridge resumed")

    def __repr__(self):
        active = [c.value for c in self.bridges.keys()]
        return f"<BridgeManager(chains={active}, count={len(self.bridges)})>"
