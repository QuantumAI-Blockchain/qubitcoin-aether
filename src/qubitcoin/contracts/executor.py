"""
Smart Contract Executor
Executes contract code in sandboxed environment
"""

import json
import time
import hashlib
from decimal import Decimal
from typing import Dict, Any, Optional, Tuple

from sqlalchemy import text
from ..database.manager import DatabaseManager
from ..quantum.engine import QuantumEngine
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContractExecutor:
    """Executes smart contracts"""

    def __init__(self, db_manager: DatabaseManager, quantum_engine: QuantumEngine):
        """Initialize contract executor"""
        self.db = db_manager
        self.quantum = quantum_engine

        logger.info("✅ Contract executor initialized")

    # ========================================================================
    # CONTRACT DEPLOYMENT
    # ========================================================================

    def deploy_contract(self, contract_type: str, contract_code: dict,
                       deployer_address: str, gas_limit: Decimal = Decimal('1.0'),
                       block_height: int = 0) -> Tuple[bool, str, Optional[str]]:
        """
        Deploy a new smart contract
        
        Args:
            contract_type: Type of contract (stablecoin, token, etc.)
            contract_code: Contract code/configuration
            deployer_address: Address deploying the contract
            gas_limit: Max gas to spend
            block_height: Block height
            
        Returns:
            (success, message, contract_id)
        """
        try:
            # Validate contract type
            from ..config import Config
            if contract_type not in Config.SUPPORTED_CONTRACT_TYPES:
                return False, f"Invalid contract type: {contract_type}", None
            
            # Generate contract ID
            contract_id = self._generate_contract_id(contract_type, deployer_address)
            
            # Calculate gas cost
            gas_cost = self._calculate_deploy_gas(contract_code)
            
            if gas_cost > gas_limit:
                return False, f"Gas limit exceeded: {gas_cost} > {gas_limit}", None
            
            # Store contract
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO contracts 
                        (contract_id, deployer_address, contract_type, contract_code, 
                         contract_state, gas_paid, block_height, deployed_at, is_active)
                        VALUES (:cid, :deployer, :type, CAST(:code AS jsonb), 
                                CAST(:state AS jsonb), :gas, :height, CURRENT_TIMESTAMP, true)
                    """),
                    {
                        'cid': contract_id,
                        'deployer': deployer_address,
                        'type': contract_type,
                        'code': json.dumps(contract_code),
                        'state': json.dumps({'initialized': True}),
                        'gas': str(gas_cost),
                        'height': block_height
                    }
                )
                
                # If stablecoin, link to QUSD token
                if contract_type == 'stablecoin' and contract_code.get('symbol') == 'QUSD':
                    session.execute(
                        text("""
                            UPDATE tokens 
                            SET contract_id = :cid, active = true 
                            WHERE symbol = 'QUSD'
                        """),
                        {'cid': contract_id}
                    )
                
                session.commit()
            
            logger.info(f"✅ Contract deployed: {contract_id} ({contract_type})")
            return True, f"Contract deployed: {contract_id}", contract_id
            
        except Exception as e:
            logger.error(f"Contract deployment failed: {e}", exc_info=True)
            return False, f"Deployment error: {str(e)}", None

    def _generate_contract_id(self, contract_type: str, deployer: str) -> str:
        """Generate unique contract ID"""
        data = f"{contract_type}-{deployer}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()[:40]

    def _calculate_deploy_gas(self, contract_code: dict) -> Decimal:
        """Calculate gas cost for deployment"""
        # Base cost + size-based cost
        base_cost = Decimal('0.1')
        code_size = len(json.dumps(contract_code))
        size_cost = Decimal(code_size) / Decimal('1000') * Decimal('0.01')
        
        return base_cost + size_cost

    # ========================================================================
    # CONTRACT EXECUTION
    # ========================================================================

    def execute(self, contract_id: str, function: str, args: dict,
                caller: str, gas_limit: Decimal = Decimal('0.5'),
                block_height: int = 0) -> Tuple[bool, str, Any]:
        """
        Execute contract function
        
        Args:
            contract_id: Contract to execute
            function: Function name (mint, burn, transfer, etc.)
            args: Function arguments
            caller: Address calling the function
            gas_limit: Max gas
            block_height: Current block height
            
        Returns:
            (success, message, result)
        """
        try:
            # Load contract
            contract = self._load_contract(contract_id)
            
            if not contract:
                return False, "Contract not found", None
            
            if not contract.get('is_active'):
                return False, "Contract not active", None
            
            contract_type = contract['contract_type']
            contract_code = contract['contract_code']
            
            # Route to appropriate executor
            if contract_type == 'stablecoin':
                return self._execute_stablecoin(
                    contract_id, function, args, caller, block_height
                )
            elif contract_type == 'token':
                return self._execute_token(
                    contract_id, function, args, caller, block_height
                )
            else:
                return False, f"Contract type not implemented: {contract_type}", None
                
        except Exception as e:
            logger.error(f"Contract execution failed: {e}", exc_info=True)
            return False, f"Execution error: {str(e)}", None

    def _load_contract(self, contract_id: str) -> Optional[Dict]:
        """Load contract from database (always fresh to avoid stale state)"""
        with self.db.get_session() as session:
            result = session.execute(
                text("""
                    SELECT contract_type, contract_code, contract_state, is_active
                    FROM contracts
                    WHERE contract_id = :cid
                """),
                {'cid': contract_id}
            ).fetchone()

            if not result:
                return None

            return {
                'contract_type': result[0],
                'contract_code': json.loads(result[1]) if isinstance(result[1], str) else result[1],
                'contract_state': json.loads(result[2]) if isinstance(result[2], str) else result[2],
                'is_active': result[3]
            }

    # ========================================================================
    # STABLECOIN CONTRACT EXECUTION
    # ========================================================================

    def _execute_stablecoin(self, contract_id: str, function: str, args: dict,
                           caller: str, block_height: int) -> Tuple[bool, str, Any]:
        """Execute stablecoin contract function"""
        
        # Import stablecoin engine
        from ..stablecoin.engine import StablecoinEngine
        
        # Create engine instance
        engine = StablecoinEngine(self.db, self.quantum)
        
        # Route function calls
        if function == 'mint':
            success, msg, vault_id = engine.mint_qusd(
                user_address=caller,
                collateral_amount=Decimal(args['collateral_amount']),
                collateral_type=args['collateral_type'],
                block_height=block_height
            )
            return success, msg, {'vault_id': vault_id}
            
        elif function == 'burn':
            success, msg = engine.burn_qusd(
                user_address=caller,
                amount=Decimal(args['amount']),
                vault_id=args['vault_id'],
                block_height=block_height
            )
            return success, msg, None
            
        elif function == 'updateOracle':
            success = engine.update_price(
                asset_pair=args['asset_pair'],
                price=Decimal(args['price']),
                source=args['source'],
                block_height=block_height
            )
            return success, "Oracle updated" if success else "Update failed", None
            
        elif function == 'getHealth':
            health = engine.get_system_health()
            return True, "Health retrieved", health
            
        elif function == 'checkLiquidations':
            at_risk = engine.check_vault_health()
            return True, f"{len(at_risk)} vaults at risk", {'at_risk': at_risk}
            
        else:
            return False, f"Unknown function: {function}", None

    def _execute_token(self, contract_id: str, function: str, args: dict,
                      caller: str, block_height: int) -> Tuple[bool, str, Any]:
        """Execute token contract function (ERC-20 style)"""
        
        # Get token info
        with self.db.get_session() as session:
            token = session.execute(
                text("SELECT token_id, symbol FROM tokens WHERE contract_id = :cid"),
                {'cid': contract_id}
            ).fetchone()

            if not token:
                return False, "Token not found", None

            token_id = token[0]
            symbol = token[1]
            
            if function == 'transfer':
                to_address = args['to']
                amount = Decimal(args['amount'])

                # Check sender balance first
                sender_balance = session.execute(
                    text("""
                        SELECT balance FROM token_balances
                        WHERE contract_id = :cid AND holder_address = :from
                        FOR UPDATE
                    """),
                    {'cid': contract_id, 'from': caller}
                ).scalar()

                if not sender_balance or Decimal(str(sender_balance)) < amount:
                    return False, "Insufficient token balance", None

                # Debit sender
                session.execute(
                    text("""
                        UPDATE token_balances
                        SET balance = balance - :amt, last_updated = CURRENT_TIMESTAMP
                        WHERE contract_id = :cid AND holder_address = :from
                    """),
                    {'amt': str(amount), 'cid': contract_id, 'from': caller}
                )
                
                # Credit receiver
                session.execute(
                    text("""
                        INSERT INTO token_balances (contract_id, holder_address, balance, last_updated)
                        VALUES (:cid, :to, :amt, CURRENT_TIMESTAMP)
                        ON CONFLICT (contract_id, holder_address)
                        DO UPDATE SET balance = token_balances.balance + EXCLUDED.balance,
                                     last_updated = CURRENT_TIMESTAMP
                    """),
                    {'cid': contract_id, 'to': to_address, 'amt': str(amount)}
                )
                
                # Record transfer
                session.execute(
                    text("""
                        INSERT INTO token_transfers (token_id, from_address, to_address, amount, txid, block_height)
                        VALUES (:tid, :from, :to, :amt, :txid, :height)
                    """),
                    {
                        'tid': token_id,
                        'from': caller,
                        'to': to_address,
                        'amt': str(amount),
                        'txid': self._gen_txid(function, caller, amount),
                        'height': block_height
                    }
                )
                
                session.commit()
                
                return True, f"Transferred {amount} {symbol}", None
                
            elif function == 'balanceOf':
                balance = session.execute(
                    text("""
                        SELECT balance FROM token_balances
                        WHERE contract_id = :cid AND holder_address = :addr
                    """),
                    {'cid': contract_id, 'addr': args['address']}
                ).scalar()
                
                return True, "Balance retrieved", {'balance': str(balance or 0)}
            
            else:
                return False, f"Unknown function: {function}", None

    def _gen_txid(self, func: str, caller: str, amount: Decimal) -> str:
        """Generate transaction ID"""
        data = f"{func}-{caller}-{amount}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()

