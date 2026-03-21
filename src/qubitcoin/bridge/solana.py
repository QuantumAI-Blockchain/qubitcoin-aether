"""
Solana Bridge
Cross-chain bridge for Solana blockchain
"""

import asyncio
import base58
from decimal import Decimal
from typing import Optional, Dict, List
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Confirmed
from spl.token.client import Token
from .base import BaseBridge, ChainType, BridgeStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SolanaBridge(BaseBridge):
    """Bridge for Solana blockchain"""

    # Deployed SPL token mints on Solana mainnet
    WQBC_MINT = "Ew7o13E7gwcbYsv4aRpoZEKonTW6snAGYHerD9j3C1Kf"
    WQUSD_MINT = "CfipKUW1vTGt1Y9jcFwDsrafD3bvxaD9PUMD9zjRRWR3"

    def __init__(self, db_manager):
        """Initialize Solana bridge"""
        super().__init__(ChainType.SOLANA, db_manager)

        self.client: Optional[AsyncClient] = None
        self.keypair: Optional[Keypair] = None
        self.token_mint: Optional[Pubkey] = None
        self.qusd_mint: Optional[Pubkey] = None
        self.bridge_program_id: Optional[Pubkey] = None

        # Solana confirmation requirements
        self.confirmations_required = 32  # ~13 seconds on Solana

    async def connect(self) -> bool:
        """Connect to Solana"""
        try:
            import os
            
            # Get RPC URL
            rpc_url = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
            
            self.client = AsyncClient(rpc_url, commitment=Confirmed)
            
            # Test connection
            version = await self.client.get_version()
            if not version.value:
                logger.error("Failed to connect to Solana")
                return False
            
            logger.info(f"✅ Connected to Solana (Version: {version.value.get('solana-core', 'unknown')})")
            
            # Load keypair
            private_key_b58 = os.getenv('SOLANA_PRIVATE_KEY')
            if private_key_b58:
                private_key_bytes = base58.b58decode(private_key_b58)
                self.keypair = Keypair.from_bytes(private_key_bytes)
                logger.info(f"✅ Keypair loaded: {self.keypair.pubkey()}")
            
            # Load token mint addresses (env override or deployed defaults)
            wqbc_mint_str = os.getenv('SOLANA_WQBC_MINT', self.WQBC_MINT)
            self.token_mint = Pubkey.from_string(wqbc_mint_str)
            logger.info(f"✅ wQBC Token Mint: {self.token_mint}")

            wqusd_mint_str = os.getenv('SOLANA_WQUSD_MINT', self.WQUSD_MINT)
            self.qusd_mint = Pubkey.from_string(wqusd_mint_str)
            logger.info(f"✅ wQUSD Token Mint: {self.qusd_mint}")

            # Load bridge program ID
            program_id_str = os.getenv('SOLANA_BRIDGE_PROGRAM')
            if program_id_str:
                self.bridge_program_id = Pubkey.from_string(program_id_str)
                logger.info(f"✅ Bridge Program: {self.bridge_program_id}")
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Solana connection error: {e}")
            return False

    async def disconnect(self):
        """Disconnect from Solana"""
        if self.client:
            await self.client.close()
        
        self.client = None
        self.keypair = None
        self.connected = False
        logger.info("Disconnected from Solana")

    async def get_balance(self, address: str) -> Decimal:
        """Get wQBC SPL token balance"""
        if not self.client or not self.token_mint:
            return Decimal(0)
        
        try:
            # Convert address to Pubkey
            owner = Pubkey.from_string(address)
            
            # Get token account
            token_accounts = await self.client.get_token_accounts_by_owner(
                owner,
                {"mint": self.token_mint}
            )
            
            if not token_accounts.value:
                return Decimal(0)
            
            # Parse balance (SPL tokens have 8 decimals like QBC)
            account_info = token_accounts.value[0]
            amount = int.from_bytes(account_info.account.data[64:72], 'little')
            
            return Decimal(amount) / Decimal(10**8)
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return Decimal(0)

    async def process_deposit(
        self,
        qbc_txid: str,
        qbc_address: str,
        target_address: str,
        amount: Decimal
    ) -> Optional[str]:
        """Process QBC deposit and mint wQBC SPL tokens"""
        if not self.connected or not self.client or not self.keypair:
            logger.error("Solana bridge not ready")
            return None
        
        try:
            logger.info(f"💎 Processing deposit: {amount} QBC → wQBC (Solana)")
            logger.info(f"  QBC TX: {qbc_txid}")
            logger.info(f"  Target: {target_address}")
            
            # Create deposit record
            deposit_id = await self._create_deposit_record(
                qbc_txid, qbc_address, target_address, amount,
                {'network': 'solana'}
            )
            
            # Convert amount to SPL token amount (8 decimals)
            spl_amount = int(amount * 10**8)
            
            # Get or create associated token account for recipient
            recipient = Pubkey.from_string(target_address)
            
            # Minting wQBC requires the on-chain Solana bridge program.
            # Until the program is deployed, deposits are queued as PENDING
            # and will be processed once the bridge program is live.
            logger.warning(
                "Solana bridge program not yet deployed — deposit %s queued "
                "(amount=%s, target=%s)", deposit_id, amount, target_address
            )
            await self._update_deposit_status(
                deposit_id,
                BridgeStatus.PENDING,
                error_message="Solana bridge program not yet deployed"
            )

            return None
            
        except Exception as e:
            logger.error(f"Solana deposit error: {e}")
            return None

    async def listen_for_withdrawals(self):
        """Listen for wQBC SPL token burns on Solana"""
        if not self.connected or not self.client:
            logger.error("Solana bridge not ready")
            return
        
        logger.info("🔊 Listening for Solana withdrawals...")
        
        # Solana uses program logs (not EVM events) for withdrawal detection.
        # Once the bridge program is deployed, this loop will parse transaction
        # logs for burn instructions and trigger QBC unlock on the L1 side.
        logger.info(
            "Solana withdrawal listener active — waiting for bridge program deployment"
        )

        while self.connected:
            try:
                if not self.bridge_program_id:
                    await asyncio.sleep(60)
                    continue

                # Poll recent program transactions for burn events
                # (full implementation requires deployed bridge program)
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Solana listener error: {e}")
                await asyncio.sleep(30)

    async def get_transaction_status(self, tx_hash: str) -> Dict:
        """Get transaction status on Solana"""
        if not self.client:
            return {'status': 'unknown'}
        
        try:
            from solders.signature import Signature
            
            sig = Signature.from_string(tx_hash)
            status = await self.client.get_signature_statuses([sig])
            
            if not status.value or not status.value[0]:
                return {'status': 'pending'}
            
            tx_status = status.value[0]
            
            return {
                'status': 'success' if tx_status.err is None else 'failed',
                'slot': tx_status.slot,
                'confirmations': tx_status.confirmations or 0,
                'error': str(tx_status.err) if tx_status.err else None
            }
            
        except Exception as e:
            return {'status': 'error', 'error': str(e)}

    async def estimate_fees(self, amount: Decimal) -> Dict:
        """Estimate Solana bridge fees"""
        bridge_fee = self._calculate_bridge_fee(amount)
        
        # Solana transaction fees are very low (~0.000005 SOL)
        sol_fee = Decimal('0.000005')
        
        return {
            'bridge_fee_qbc': str(bridge_fee),
            'gas_fee_sol': str(sol_fee),
            'total_fee_qbc': str(bridge_fee)
        }

    async def _create_token_account_if_needed(self, owner: Pubkey) -> Pubkey:
        """
        Create associated token account if it doesn't exist
        
        Args:
            owner: Owner's public key
            
        Returns:
            Token account public key
        """
        if not self.token_mint:
            raise ValueError("Token mint not configured")
        
        # Calculate associated token account address
        from spl.token.instructions import get_associated_token_address
        
        ata = get_associated_token_address(owner, self.token_mint)
        
        # Check if account exists
        account_info = await self.client.get_account_info(ata)
        
        if not account_info.value:
            logger.warning(
                "Associated token account for %s does not exist yet. "
                "Account creation requires the bridge keypair and a funded "
                "transaction — will be created on first deposit.", owner
            )

        return ata

    def __repr__(self):
        return f"<SolanaBridge(connected={self.connected}, mint={self.token_mint})>"
