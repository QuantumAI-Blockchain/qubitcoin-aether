"""
Ethereum Bridge (EVM Chains)
Supports: Ethereum, Polygon, BSC, Arbitrum, Optimism, Avalanche, Base
"""

import asyncio
import json
from decimal import Decimal
from typing import Optional, Dict, List
from web3 import Web3
from web3.contract import Contract
from eth_account import Account
from eth_account.signers.local import LocalAccount

from .base import BaseBridge, ChainType, BridgeStatus
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


# Chain configurations
CHAIN_CONFIG = {
    ChainType.ETHEREUM: {
        'chain_id': 1,
        'name': 'Ethereum Mainnet',
        'rpc_env': 'ETH_RPC_URL',
        'explorer': 'https://etherscan.io',
        'confirmations': 12
    },
    ChainType.POLYGON: {
        'chain_id': 137,
        'name': 'Polygon',
        'rpc_env': 'POLYGON_RPC_URL',
        'explorer': 'https://polygonscan.com',
        'confirmations': 128
    },
    ChainType.BSC: {
        'chain_id': 56,
        'name': 'BNB Smart Chain',
        'rpc_env': 'BSC_RPC_URL',
        'explorer': 'https://bscscan.com',
        'confirmations': 15
    },
    ChainType.ARBITRUM: {
        'chain_id': 42161,
        'name': 'Arbitrum One',
        'rpc_env': 'ARBITRUM_RPC_URL',
        'explorer': 'https://arbiscan.io',
        'confirmations': 10
    },
    ChainType.OPTIMISM: {
        'chain_id': 10,
        'name': 'Optimism',
        'rpc_env': 'OPTIMISM_RPC_URL',
        'explorer': 'https://optimistic.etherscan.io',
        'confirmations': 10
    },
    ChainType.AVALANCHE: {
        'chain_id': 43114,
        'name': 'Avalanche C-Chain',
        'rpc_env': 'AVALANCHE_RPC_URL',
        'explorer': 'https://snowtrace.io',
        'confirmations': 10
    },
    ChainType.BASE: {
        'chain_id': 8453,
        'name': 'Base',
        'rpc_env': 'BASE_RPC_URL',
        'explorer': 'https://basescan.org',
        'confirmations': 10
    }
}


class EVMBridge(BaseBridge):
    """Bridge for all EVM-compatible chains"""

    def __init__(self, chain_type: ChainType, db_manager):
        """
        Initialize EVM bridge
        
        Args:
            chain_type: Which EVM chain (ETH, Polygon, etc.)
            db_manager: Database manager
        """
        super().__init__(chain_type, db_manager)
        
        if chain_type not in CHAIN_CONFIG:
            raise ValueError(f"Unsupported EVM chain: {chain_type}")
        
        self.config = CHAIN_CONFIG[chain_type]
        self.w3: Optional[Web3] = None
        self.account: Optional[LocalAccount] = None
        self.wqbc_contract: Optional[Contract] = None
        self.bridge_contract: Optional[Contract] = None

    async def connect(self) -> bool:
        """Connect to EVM chain"""
        try:
            # Get RPC URL from environment
            import os
            rpc_url = os.getenv(self.config['rpc_env'])
            
            if not rpc_url:
                logger.warning(f"{self.config['rpc_env']} not configured")
                return False
            
            self.w3 = Web3(Web3.HTTPProvider(rpc_url))
            
            if not self.w3.is_connected():
                logger.error(f"Failed to connect to {self.config['name']}")
                return False
            
            chain_id = self.w3.eth.chain_id
            if chain_id != self.config['chain_id']:
                logger.error(f"Wrong chain ID: {chain_id} != {self.config['chain_id']}")
                return False
            
            logger.info(f"✅ Connected to {self.config['name']} (Chain ID: {chain_id})")
            
            # Load account if private key provided
            private_key = os.getenv(f"{self.chain_type.value.upper()}_PRIVATE_KEY") or os.getenv('ETH_PRIVATE_KEY')
            if private_key:
                self.account = Account.from_key(private_key)
                logger.info(f"✅ Account loaded: {self.account.address}")
            
            # Load contracts
            await self._load_contracts()
            
            self.connected = True
            return True
            
        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    async def disconnect(self):
        """Disconnect from chain"""
        self.w3 = None
        self.account = None
        self.wqbc_contract = None
        self.bridge_contract = None
        self.connected = False
        logger.info(f"Disconnected from {self.config['name']}")

    async def _load_contracts(self):
        """Load smart contract instances"""
        if not self.w3:
            return
        
        try:
            # Get bridge contract address
            import os
            contract_address = os.getenv(f"{self.chain_type.value.upper()}_BRIDGE_ADDRESS")
            if not contract_address:
                logger.warning(f"Bridge contract not configured for {self.chain_type.value}")
                return
            
            # Load ABIs
            wqbc_abi = self._load_abi('wQBC')
            bridge_abi = self._load_abi('Bridge')
            
            if not bridge_abi:
                logger.warning("Bridge ABI not found")
                return
            
            # Create bridge contract instance
            self.bridge_contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=bridge_abi
            )
            
            # Get wQBC token address from bridge
            wqbc_address = self.bridge_contract.functions.wqbcToken().call()
            
            if wqbc_abi:
                self.wqbc_contract = self.w3.eth.contract(
                    address=wqbc_address,
                    abi=wqbc_abi
                )
            
            logger.info(f"✅ Contracts loaded:")
            logger.info(f"   wQBC: {wqbc_address}")
            logger.info(f"   Bridge: {contract_address}")
            
        except Exception as e:
            logger.error(f"Failed to load contracts: {e}")

    def _load_abi(self, contract_name: str) -> Optional[List]:
        """Load contract ABI from file"""
        try:
            import os
            # Look in project root contracts directory
            abi_path = os.path.join('contracts', 'ethereum', 'abi', f'{contract_name}.json')
            
            if os.path.exists(abi_path):
                with open(abi_path, 'r') as f:
                    return json.load(f)
            else:
                logger.debug(f"ABI not found: {abi_path}")
                return None
        except Exception as e:
            logger.error(f"Error loading ABI: {e}")
            return None

    async def get_balance(self, address: str) -> Decimal:
        """Get wQBC balance"""
        if not self.wqbc_contract:
            return Decimal(0)
        
        try:
            balance_wei = self.wqbc_contract.functions.balanceOf(
                Web3.to_checksum_address(address)
            ).call()
            
            return Decimal(balance_wei) / Decimal(10**8)
            
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
        """Process QBC deposit and mint wQBC"""
        if not self.connected or not self.bridge_contract or not self.account:
            logger.error("Bridge not ready")
            return None
        
        try:
            logger.info(f"💎 Processing deposit: {amount} QBC → wQBC ({self.config['name']})")
            logger.info(f"  QBC TX: {qbc_txid}")
            logger.info(f"  Target: {target_address}")
            
            # Create deposit record
            deposit_id = await self._create_deposit_record(
                qbc_txid, qbc_address, target_address, amount,
                {'chain_id': self.config['chain_id']}
            )
            
            # Convert amount to wei (8 decimals)
            amount_wei = int(amount * 10**8)
            
            # Build transaction
            tx = self.bridge_contract.functions.initiateDeposit(
                Web3.to_checksum_address(target_address),
                amount_wei,
                qbc_txid
            ).build_transaction({
                'from': self.account.address,
                'nonce': self.w3.eth.get_transaction_count(self.account.address),
                'gas': 250000,
                'gasPrice': self.w3.eth.gas_price
            })
            
            # Sign and send
            signed_tx = self.account.sign_transaction(tx)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            logger.info(f"📤 TX sent: {tx_hash.hex()}")
            
            # Update status
            await self._update_deposit_status(deposit_id, BridgeStatus.PROCESSING, tx_hash.hex())
            
            # Wait for confirmation
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=300)
            
            if receipt['status'] == 1:
                await self._update_deposit_status(deposit_id, BridgeStatus.COMPLETED, tx_hash.hex())
                logger.info(f"✅ Deposit completed: {tx_hash.hex()}")
                return tx_hash.hex()
            else:
                await self._update_deposit_status(
                    deposit_id, BridgeStatus.FAILED, tx_hash.hex(), "Transaction reverted"
                )
                logger.error(f"❌ Deposit failed")
                return None
                
        except Exception as e:
            logger.error(f"Deposit error: {e}")
            return None

    async def listen_for_withdrawals(self):
        """Listen for wQBC burn events"""
        if not self.connected or not self.bridge_contract:
            logger.error("Bridge not ready for listening")
            return
        
        logger.info(f"🔊 Listening for withdrawals on {self.config['name']}...")
        
        latest_block = await self._get_latest_processed_block()
        
        # Create event filter
        event_filter = self.bridge_contract.events.WithdrawalInitiated.create_filter(
            fromBlock=latest_block
        )
        
        while self.connected:
            try:
                for event in event_filter.get_new_entries():
                    await self._process_withdrawal_event(event)
                
                await asyncio.sleep(15)
                
            except Exception as e:
                logger.error(f"Withdrawal listener error: {e}")
                await asyncio.sleep(60)

    async def _process_withdrawal_event(self, event: Dict):
        """Process withdrawal event"""
        try:
            withdrawal_id = event['args']['withdrawalId']
            eth_address = event['args']['ethAddress']
            qbc_address = event['args']['qbcAddress']
            amount = Decimal(event['args']['amount']) / Decimal(10**8)
            
            logger.info(f"📥 Withdrawal detected: {amount} wQBC → QBC")
            logger.info(f"  From: {eth_address}")
            logger.info(f"  To: {qbc_address}")
            
            # Create withdrawal record
            await self._create_withdrawal_record(
                event['transactionHash'].hex(),
                eth_address,
                qbc_address,
                amount,
                {
                    'withdrawal_id': withdrawal_id.hex(),
                    'chain_id': self.config['chain_id'],
                    'block_number': event['blockNumber']
                }
            )
            
            # TODO: Trigger QBC unlock (handled by relayer)
            
        except Exception as e:
            logger.error(f"Error processing withdrawal: {e}")

    async def _get_latest_processed_block(self) -> int:
        """Get latest processed block"""
        with self.db.get_session() as session:
            from sqlalchemy import text
            
            result = session.execute(
                text("""
                    SELECT COALESCE(MAX(CAST(chain_data->>'block_number' AS BIGINT)), 0)
                    FROM bridge_withdrawals
                    WHERE source_chain = :chain
                """),
                {'chain': self.chain_type.value}
            )
            latest = result.scalar()
        
        if latest == 0:
            latest = self.w3.eth.block_number - 100
        
        return latest

    async def get_transaction_status(self, tx_hash: str) -> Dict:
        """Get transaction status"""
        if not self.w3:
            return {'status': 'unknown'}
        
        try:
            receipt = self.w3.eth.get_transaction_receipt(tx_hash)
            
            return {
                'status': 'success' if receipt['status'] == 1 else 'failed',
                'block_number': receipt['blockNumber'],
                'confirmations': self.w3.eth.block_number - receipt['blockNumber'],
                'gas_used': receipt['gasUsed']
            }
        except Exception as e:
            return {'status': 'pending', 'error': str(e)}

    async def estimate_fees(self, amount: Decimal) -> Dict:
        """Estimate bridge fees"""
        bridge_fee = self._calculate_bridge_fee(amount)
        
        gas_price = 0
        if self.w3:
            gas_price = self.w3.eth.gas_price
        
        estimated_gas = 250000  # Typical gas for bridge transaction
        gas_fee_wei = gas_price * estimated_gas
        gas_fee_eth = Decimal(gas_fee_wei) / Decimal(10**18)
        
        return {
            'bridge_fee_qbc': str(bridge_fee),
            'gas_fee_native': str(gas_fee_eth),
            'gas_price_gwei': str(Decimal(gas_price) / Decimal(10**9)),
            'total_fee_qbc': str(bridge_fee)
        }
