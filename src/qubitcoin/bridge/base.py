"""
Base Bridge Interface
Abstract class for all cross-chain bridges
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Optional, Dict, List, Tuple
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ChainType(Enum):
    """Supported blockchain types"""
    ETHEREUM = "ethereum"
    POLYGON = "polygon"
    BSC = "bsc"
    ARBITRUM = "arbitrum"
    OPTIMISM = "optimism"
    SOLANA = "solana"
    AVALANCHE = "avalanche"
    BASE = "base"


class BridgeStatus(Enum):
    """Bridge operation status"""
    DETECTED = "detected"
    CONFIRMING = "confirming"
    PENDING = "pending"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class BaseBridge(ABC):
    """
    Abstract base class for cross-chain bridges
    
    All bridges (ETH, SOL, etc.) must implement these methods
    """

    def __init__(self, chain_type: ChainType, db_manager):
        """
        Initialize bridge
        
        Args:
            chain_type: Type of blockchain
            db_manager: Database manager instance
        """
        self.chain_type = chain_type
        self.db = db_manager
        self.connected = False
        
        logger.info(f"🌉 Initializing {chain_type.value} bridge")

    @abstractmethod
    async def connect(self) -> bool:
        """
        Connect to blockchain
        
        Returns:
            True if connected successfully
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from blockchain"""
        pass

    @abstractmethod
    async def get_balance(self, address: str) -> Decimal:
        """
        Get wrapped QBC balance on target chain
        
        Args:
            address: Address on target chain
            
        Returns:
            wQBC balance
        """
        pass

    @abstractmethod
    async def process_deposit(
        self,
        qbc_txid: str,
        qbc_address: str,
        target_address: str,
        amount: Decimal
    ) -> Optional[str]:
        """
        Process QBC deposit and mint wQBC on target chain
        
        Args:
            qbc_txid: QBC transaction hash
            qbc_address: QBC address that locked coins
            target_address: Address on target chain to receive wQBC
            amount: Amount to bridge
            
        Returns:
            Transaction hash on target chain or None if failed
        """
        pass

    @abstractmethod
    async def listen_for_withdrawals(self):
        """
        Listen for wQBC burn events on target chain
        and process QBC unlocks
        """
        pass

    @abstractmethod
    async def get_transaction_status(self, tx_hash: str) -> Dict:
        """
        Get transaction status
        
        Args:
            tx_hash: Transaction hash on target chain
            
        Returns:
            Transaction status info
        """
        pass

    @abstractmethod
    async def estimate_fees(self, amount: Decimal) -> Dict:
        """
        Estimate bridge fees
        
        Args:
            amount: Amount to bridge
            
        Returns:
            Fee breakdown
        """
        pass

    # ========================================================================
    # HELPER METHODS (Implemented for all bridges)
    # ========================================================================

    # Bridge fee bounds (basis points): 0.01% minimum, 10% maximum
    MIN_FEE_BPS: int = 1
    MAX_FEE_BPS: int = 1000

    @classmethod
    def validate_fee_bps(cls, fee_bps: int) -> int:
        """Validate that fee BPS is within safe bounds.

        Args:
            fee_bps: Fee in basis points to validate.

        Returns:
            The validated fee_bps value.

        Raises:
            ValueError: If fee_bps is outside [MIN_FEE_BPS, MAX_FEE_BPS].
        """
        if not isinstance(fee_bps, int) or fee_bps < cls.MIN_FEE_BPS or fee_bps > cls.MAX_FEE_BPS:
            raise ValueError(
                f"Bridge fee {fee_bps} BPS out of bounds "
                f"[{cls.MIN_FEE_BPS}, {cls.MAX_FEE_BPS}]"
            )
        return fee_bps

    def _calculate_bridge_fee(self, amount: Decimal, fee_bps: Optional[int] = None) -> Decimal:
        """
        Calculate bridge fee

        Args:
            amount: Amount to bridge
            fee_bps: Fee in basis points (default: Config.BRIDGE_FEE_BPS)

        Returns:
            Fee amount

        Raises:
            ValueError: If amount is not positive or fee_bps is out of bounds.
        """
        if amount <= 0:
            raise ValueError(f"Bridge amount must be positive, got {amount}")
        if fee_bps is None:
            from ..config import Config
            fee_bps = Config.BRIDGE_FEE_BPS
        fee_bps = self.validate_fee_bps(fee_bps)
        return (amount * Decimal(fee_bps)) / Decimal(10000)

    async def _create_deposit_record(
        self,
        qbc_txid: str,
        qbc_address: str,
        target_address: str,
        amount: Decimal,
        chain_specific_data: Dict = None
    ) -> str:
        """
        Create deposit record in database
        
        Args:
            qbc_txid: QBC transaction hash
            qbc_address: QBC address
            target_address: Target chain address
            amount: Amount
            chain_specific_data: Additional chain-specific data
            
        Returns:
            Deposit ID
        """
        import json
        with self.db.get_session() as session:
            from sqlalchemy import text
            
            result = session.execute(
                text("""
                    INSERT INTO bridge_deposits 
                    (qbc_txid, qbc_address, target_chain, target_address, qbc_amount, status, chain_data)
                    VALUES (:txid, :qbc_addr, :chain, :target_addr, :amount, 'detected', CAST(:chain_data AS jsonb))
                    RETURNING id
                """),
                {
                    'txid': qbc_txid,
                    'qbc_addr': qbc_address,
                    'chain': self.chain_type.value,
                    'target_addr': target_address,
                    'amount': str(amount),
                    'chain_data': json.dumps(chain_specific_data or {})
                }
            )
            session.commit()
            deposit_id = result.scalar()
            
        logger.info(f"📝 Deposit record created: {deposit_id}")
        return deposit_id

    async def _update_deposit_status(
        self,
        deposit_id: str,
        status: BridgeStatus,
        tx_hash: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """
        Update deposit status
        
        Args:
            deposit_id: Deposit ID
            status: New status
            tx_hash: Transaction hash (if completed)
            error_message: Error message (if failed)
        """
        with self.db.get_session() as session:
            from sqlalchemy import text
            
            query = """
                UPDATE bridge_deposits 
                SET status = :status, updated_at = CURRENT_TIMESTAMP
            """
            
            params = {'deposit_id': deposit_id, 'status': status.value}
            
            if tx_hash:
                query += ", target_txhash = :tx_hash"
                params['tx_hash'] = tx_hash
            
            if error_message:
                query += ", error_message = :error"
                params['error'] = error_message
            
            if status == BridgeStatus.COMPLETED:
                query += ", completed_at = CURRENT_TIMESTAMP"
            
            query += " WHERE id = :deposit_id"
            
            session.execute(text(query), params)
            session.commit()
        
        logger.info(f"✅ Deposit {deposit_id} status: {status.value}")

    async def _create_withdrawal_record(
        self,
        target_txhash: str,
        target_address: str,
        qbc_address: str,
        amount: Decimal,
        chain_specific_data: Dict = None
    ) -> str:
        """
        Create withdrawal record
        
        Args:
            target_txhash: Transaction hash on target chain
            target_address: Address on target chain
            qbc_address: QBC address to receive coins
            amount: Amount
            chain_specific_data: Additional data
            
        Returns:
            Withdrawal ID
        """
        import json
        with self.db.get_session() as session:
            from sqlalchemy import text
            
            result = session.execute(
                text("""
                    INSERT INTO bridge_withdrawals
                    (source_chain, source_txhash, source_address, qbc_address, wqbc_amount, status, chain_data)
                    VALUES (:chain, :txhash, :source_addr, :qbc_addr, :amount, 'detected', CAST(:chain_data AS jsonb))
                    RETURNING id
                """),
                {
                    'chain': self.chain_type.value,
                    'txhash': target_txhash,
                    'source_addr': target_address,
                    'qbc_addr': qbc_address,
                    'amount': str(amount),
                    'chain_data': json.dumps(chain_specific_data or {})
                }
            )
            session.commit()
            withdrawal_id = result.scalar()
        
        logger.info(f"📝 Withdrawal record created: {withdrawal_id}")
        return withdrawal_id

    async def get_bridge_stats(self) -> Dict:
        """
        Get bridge statistics for this chain
        
        Returns:
            Bridge stats
        """
        with self.db.get_session() as session:
            from sqlalchemy import text
            
            result = session.execute(
                text("""
                    SELECT 
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_deposits,
                        COUNT(*) FILTER (WHERE status IN ('detected', 'pending', 'processing')) as pending_deposits,
                        COALESCE(SUM(qbc_amount) FILTER (WHERE status = 'completed'), 0) as total_deposited
                    FROM bridge_deposits
                    WHERE target_chain = :chain
                """),
                {'chain': self.chain_type.value}
            ).fetchone()
            
            deposits_stats = {
                'completed': result[0],
                'pending': result[1],
                'total_volume': str(result[2])
            }
            
            result = session.execute(
                text("""
                    SELECT 
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_withdrawals,
                        COUNT(*) FILTER (WHERE status IN ('detected', 'pending', 'processing')) as pending_withdrawals,
                        COALESCE(SUM(wqbc_amount) FILTER (WHERE status = 'completed'), 0) as total_withdrawn
                    FROM bridge_withdrawals
                    WHERE source_chain = :chain
                """),
                {'chain': self.chain_type.value}
            ).fetchone()
            
            withdrawals_stats = {
                'completed': result[0],
                'pending': result[1],
                'total_volume': str(result[2])
            }
        
        return {
            'chain': self.chain_type.value,
            'connected': self.connected,
            'deposits': deposits_stats,
            'withdrawals': withdrawals_stats
        }

    def __repr__(self):
        return f"<{self.__class__.__name__}(chain={self.chain_type.value}, connected={self.connected})>"
