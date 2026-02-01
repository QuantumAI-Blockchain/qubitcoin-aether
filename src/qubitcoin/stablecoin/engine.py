"""
QUSD Stablecoin Engine
Multi-collateral, multi-oracle stable USD token
"""

import time
import json
from decimal import Decimal
from typing import Tuple, Optional, List, Dict
import numpy as np

from sqlalchemy import text
from ..config import Config
from ..database.manager import DatabaseManager
from ..quantum.engine import QuantumEngine
from ..utils.logger import get_logger

logger = get_logger(__name__)


class StablecoinEngine:
    """Manages QUSD stablecoin operations"""

    def __init__(self, db_manager: DatabaseManager, quantum_engine: QuantumEngine):
        """Initialize stablecoin engine"""
        self.db = db_manager
        self.quantum = quantum_engine
        
        # Load system parameters
        self.params = self._load_params()
        
        # Initialize QUSD token if not exists
        self._ensure_qusd_token()
        
        logger.info("✅ Stablecoin engine initialized")

    def _load_params(self) -> Dict:
        """Load system parameters from database"""
        with self.db.get_session() as session:
            results = session.execute(
                text("SELECT param_name, param_value, param_type FROM stablecoin_params")
            )
            
            params = {}
            for row in results:
                name, value, ptype = row
                if ptype == 'decimal':
                    params[name] = Decimal(value)
                elif ptype == 'integer':
                    params[name] = int(value)
                elif ptype == 'boolean':
                    params[name] = value.lower() == 'true'
                else:
                    params[name] = value
            
            return params

    def _ensure_qusd_token(self):
        """Ensure QUSD token exists and is active"""
        with self.db.get_session() as session:
            result = session.execute(
                text("SELECT token_id, active FROM tokens WHERE symbol = 'QUSD'")
            ).fetchone()
            
            if result:
                token_id, active = result
                if not active:
                    # Activate QUSD token
                    session.execute(
                        text("UPDATE tokens SET active = true WHERE token_id = :tid"),
                        {'tid': token_id}
                    )
                    session.commit()
                    logger.info(f"✅ QUSD token activated: {token_id}")
                else:
                    logger.info(f"✅ QUSD token ready: {token_id}")
            else:
                logger.warning("⚠️  QUSD token not found - needs deployment")

    # ========================================================================
    # ORACLE OPERATIONS
    # ========================================================================

    def update_price(self, asset_pair: str, price: Decimal, source: str, 
                    block_height: int) -> bool:
        """
        Update price feed from oracle source
        
        Args:
            asset_pair: e.g., "USDT/USD", "ETH/USD"
            price: Current price
            source: Oracle source name
            block_height: Current block
            
        Returns:
            True if updated
        """
        try:
            with self.db.get_session() as session:
                # Get source ID
                result = session.execute(
                    text("SELECT id FROM oracle_sources WHERE source_name = :src AND active = true"),
                    {'src': source}
                ).fetchone()
                
                if not result:
                    logger.warning(f"Oracle source not found: {source}")
                    return False
                
                source_id = result[0]
                
                # Insert price feed
                session.execute(
                    text("""
                        INSERT INTO price_feeds (asset_pair, price, source_id, block_height, confidence)
                        VALUES (:pair, :price, :sid, :height, 0.95)
                    """),
                    {
                        'pair': asset_pair,
                        'price': str(price),
                        'sid': source_id,
                        'height': block_height
                    }
                )
                
                session.commit()
                logger.debug(f"📊 Price updated: {asset_pair} = ${price} ({source})")
                return True
                
        except Exception as e:
            logger.error(f"Price update failed: {e}")
            return False

    def get_aggregated_price(self, asset_pair: str) -> Optional[Decimal]:
        """
        Get aggregated price from multiple oracle sources
        
        Args:
            asset_pair: e.g., "USDT/USD"
            
        Returns:
            Median price or None if insufficient data
        """
        with self.db.get_session() as session:
            # Get recent prices (last 10 blocks)
            results = session.execute(
                text("""
                    SELECT price 
                    FROM price_feeds 
                    WHERE asset_pair = :pair 
                    AND block_height > (SELECT MAX(height) FROM blocks) - 10
                    ORDER BY timestamp DESC
                    LIMIT 10
                """),
                {'pair': asset_pair}
            )
            
            prices = [Decimal(row[0]) for row in results]
            
            if len(prices) < 2:
                logger.warning(f"Insufficient oracle data for {asset_pair}")
                return None
            
            # Calculate median
            sorted_prices = sorted(prices)
            mid = len(sorted_prices) // 2
            
            if len(sorted_prices) % 2 == 0:
                median = (sorted_prices[mid-1] + sorted_prices[mid]) / 2
            else:
                median = sorted_prices[mid]
            
            # Store aggregated price
            mean = sum(prices) / len(prices)
            std_dev = Decimal(np.std([float(p) for p in prices]))
            
            current_height = self.db.get_current_height()
            
            session.execute(
                text("""
                    INSERT INTO aggregated_prices 
                    (asset_pair, median_price, mean_price, std_deviation, num_sources, block_height, valid)
                    VALUES (:pair, :median, :mean, :std, :n, :height, :valid)
                """),
                {
                    'pair': asset_pair,
                    'median': str(median),
                    'mean': str(mean),
                    'std': str(std_dev),
                    'n': len(prices),
                    'height': current_height,
                    'valid': std_dev < Decimal('0.01')  # <1% deviation
                }
            )
            session.commit()
            
            return median

    # ========================================================================
    # MINT OPERATIONS
    # ========================================================================

    def mint_qusd(self, user_address: str, collateral_amount: Decimal,
                  collateral_type: str, block_height: int) -> Tuple[bool, str, Optional[str]]:
        """
        Mint QUSD against collateral
        
        Args:
            user_address: User's QBC address
            collateral_amount: Amount of collateral to lock
            collateral_type: Type of collateral (USDT, QBC, etc.)
            block_height: Current block height
            
        Returns:
            (success, message, vault_id)
        """
        try:
            # Check emergency shutdown
            if self.params.get('emergency_shutdown', False):
                return False, "System in emergency shutdown", None
            
            # Get collateral type info
            with self.db.get_session() as session:
                coll_info = session.execute(
                    text("""
                        SELECT id, liquidation_ratio, debt_ceiling, min_collateral, asset_type
                        FROM collateral_types
                        WHERE asset_name = :name AND active = true
                    """),
                    {'name': collateral_type}
                ).fetchone()
                
                if not coll_info:
                    return False, f"Invalid collateral type: {collateral_type}", None
                
                coll_id, liq_ratio, debt_ceiling, min_coll, asset_type = coll_info
                
                # Check minimum
                if collateral_amount < Decimal(min_coll):
                    return False, f"Below minimum: {min_coll} {collateral_type}", None
                
                # Get collateral price
                price_pair = f"{collateral_type}/USD"
                collateral_price = self.get_aggregated_price(price_pair)
                
                if not collateral_price:
                    # For stablecoins, assume $1.00
                    if asset_type == 'stablecoin':
                        collateral_price = Decimal('1.00')
                    else:
                        return False, "Price feed unavailable", None
                
                # Calculate max QUSD mintable
                collateral_value_usd = collateral_amount * collateral_price
                max_qusd = collateral_value_usd / Decimal(liq_ratio)
                
                # Check debt ceiling
                current_debt = session.execute(
                    text("""
                        SELECT COALESCE(SUM(debt_amount), 0)
                        FROM collateral_vaults
                        WHERE collateral_type_id = :cid AND NOT liquidated
                    """),
                    {'cid': coll_id}
                ).scalar()
                
                if Decimal(current_debt) + max_qusd > Decimal(debt_ceiling):
                    return False, "Debt ceiling reached", None
                
                # Generate quantum proof
                proof_data = self._generate_mint_proof(
                    user_address, 
                    collateral_amount, 
                    max_qusd
                )
                
                # Create vault
                vault_id = session.execute(
                    text("""
                        INSERT INTO collateral_vaults 
                        (owner_address, collateral_type_id, collateral_amount, debt_amount, collateral_ratio)
                        VALUES (:owner, :cid, :coll, :debt, :ratio)
                        RETURNING vault_id
                    """),
                    {
                        'owner': user_address,
                        'cid': coll_id,
                        'coll': str(collateral_amount),
                        'debt': str(max_qusd),
                        'ratio': str(Decimal(liq_ratio))
                    }
                ).scalar()
                
                # Mint QUSD tokens
                self._credit_qusd(session, user_address, max_qusd)
                
                # Record operation
                txid = self._create_txid('mint', user_address, max_qusd)
                
                session.execute(
                    text("""
                        INSERT INTO qusd_operations
                        (operation_type, user_address, amount, collateral_locked, collateral_type,
                         price_at_operation, quantum_proof, txid, block_height, status)
                        VALUES ('mint', :user, :amt, :coll, :ctype, :price, CAST(:proof AS jsonb), :txid, :height, 'confirmed')
                    """),
                    {
                        'user': user_address,
                        'amt': str(max_qusd),
                        'coll': str(collateral_amount),
                        'ctype': collateral_type,
                        'price': str(collateral_price),
                        'proof': json.dumps(proof_data),
                        'txid': txid,
                        'height': block_height
                    }
                )
                
                session.commit()
                
                logger.info(f"✅ Minted {max_qusd} QUSD for {user_address} (vault: {vault_id})")
                return True, f"Minted {max_qusd} QUSD", str(vault_id)
                
        except Exception as e:
            logger.error(f"Mint failed: {e}", exc_info=True)
            return False, f"Mint error: {str(e)}", None

    def _credit_qusd(self, session, address: str, amount: Decimal):
        """Credit QUSD to user balance"""
        # Get QUSD token ID
        token_id = session.execute(
            text("SELECT token_id FROM tokens WHERE symbol = 'QUSD'")
        ).scalar()
        
        # Update balance in token_balances (your existing table)
        session.execute(
            text("""
                INSERT INTO token_balances (contract_id, holder_address, balance, last_updated)
                VALUES (:tid, :addr, :amt, CURRENT_TIMESTAMP)
                ON CONFLICT (contract_id, holder_address) 
                DO UPDATE SET 
                    balance = token_balances.balance + EXCLUDED.balance,
                    last_updated = CURRENT_TIMESTAMP
            """),
            {'tid': token_id, 'addr': address, 'amt': str(amount)}
        )
        
        # Update total supply
        session.execute(
            text("UPDATE tokens SET total_supply = total_supply + :amt WHERE token_id = :tid"),
            {'amt': str(amount), 'tid': token_id}
        )

    def _generate_mint_proof(self, address: str, collateral: Decimal, 
                            qusd_amount: Decimal) -> dict:
        """Generate quantum proof for mint operation"""
        # Generate Hamiltonian based on mint data
        hamiltonian = self.quantum.generate_hamiltonian(num_qubits=4)
        
        # Optimize
        params, energy = self.quantum.optimize_vqe(hamiltonian, num_qubits=4)
        
        return {
            'hamiltonian': hamiltonian,
            'params': params.tolist(),
            'energy': float(energy),
            'user': address,
            'collateral': str(collateral),
            'qusd': str(qusd_amount),
            'timestamp': time.time()
        }

    def _create_txid(self, op_type: str, address: str, amount: Decimal) -> str:
        """Create transaction ID for operation"""
        import hashlib
        data = f"{op_type}-{address}-{amount}-{time.time()}"
        return hashlib.sha256(data.encode()).hexdigest()

    # ========================================================================
    # BURN OPERATIONS
    # ========================================================================

    def burn_qusd(self, user_address: str, amount: Decimal, 
                  vault_id: str, block_height: int) -> Tuple[bool, str]:
        """
        Burn QUSD to unlock collateral
        
        Args:
            user_address: User's address
            amount: QUSD to burn
            vault_id: Vault to repay
            block_height: Current block
            
        Returns:
            (success, message)
        """
        try:
            with self.db.get_session() as session:
                # Get vault
                vault = session.execute(
                    text("""
                        SELECT owner_address, collateral_amount, debt_amount, collateral_type_id
                        FROM collateral_vaults
                        WHERE vault_id = :vid AND NOT liquidated
                    """),
                    {'vid': vault_id}
                ).fetchone()
                
                if not vault:
                    return False, "Vault not found or liquidated"
                
                owner, coll_amt, debt_amt, coll_type_id = vault
                
                if owner != user_address:
                    return False, "Not vault owner"
                
                debt_amt = Decimal(debt_amt)
                
                if amount > debt_amt:
                    amount = debt_amt
                
                # Check user has QUSD
                token_id = session.execute(
                    text("SELECT token_id FROM tokens WHERE symbol = 'QUSD'")
                ).scalar()
                
                balance = session.execute(
                    text("""
                        SELECT balance FROM token_balances
                        WHERE contract_id = :tid AND holder_address = :addr
                    """),
                    {'tid': token_id, 'addr': user_address}
                ).scalar()
                
                if not balance or Decimal(balance) < amount:
                    return False, "Insufficient QUSD balance"
                
                # Burn QUSD
                session.execute(
                    text("""
                        UPDATE token_balances
                        SET balance = balance - :amt, last_updated = CURRENT_TIMESTAMP
                        WHERE contract_id = :tid AND holder_address = :addr
                    """),
                    {'amt': str(amount), 'tid': token_id, 'addr': user_address}
                )
                
                # Update total supply
                session.execute(
                    text("UPDATE tokens SET total_supply = total_supply - :amt WHERE token_id = :tid"),
                    {'amt': str(amount), 'tid': token_id}
                )
                
                # Update vault
                new_debt = debt_amt - amount
                
                if new_debt == 0:
                    # Fully repaid - return all collateral
                    session.execute(
                        text("""
                            UPDATE collateral_vaults
                            SET debt_amount = 0, liquidated = true
                            WHERE vault_id = :vid
                        """),
                        {'vid': vault_id}
                    )
                    logger.info(f"✅ Vault {vault_id} fully repaid")
                else:
                    session.execute(
                        text("""
                            UPDATE collateral_vaults
                            SET debt_amount = :debt, last_updated = CURRENT_TIMESTAMP
                            WHERE vault_id = :vid
                        """),
                        {'debt': str(new_debt), 'vid': vault_id}
                    )
                
                # Record operation
                txid = self._create_txid('burn', user_address, amount)
                
                session.execute(
                    text("""
                        INSERT INTO qusd_operations
                        (operation_type, user_address, amount, quantum_proof, txid, block_height, status)
                        VALUES ('burn', :user, :amt, '{}', :txid, :height, 'confirmed')
                    """),
                    {
                        'user': user_address,
                        'amt': str(amount),
                        'txid': txid,
                        'height': block_height
                    }
                )
                
                session.commit()
                
                logger.info(f"✅ Burned {amount} QUSD for {user_address}")
                return True, f"Burned {amount} QUSD, {new_debt} remaining"
                
        except Exception as e:
            logger.error(f"Burn failed: {e}", exc_info=True)
            return False, f"Burn error: {str(e)}"

    # ========================================================================
    # HEALTH & MONITORING
    # ========================================================================

    def check_vault_health(self) -> List[str]:
        """
        Check all vaults for liquidation
        
        Returns:
            List of vault IDs requiring liquidation
        """
        at_risk = []
        
        with self.db.get_session() as session:
            results = session.execute(
                text("""
                    SELECT vault_id FROM vault_health
                    WHERE health_status IN ('liquidatable', 'danger')
                """)
            )
            
            at_risk = [row[0] for row in results]
        
        if at_risk:
            logger.warning(f"⚠️  {len(at_risk)} vaults at risk")
        
        return at_risk

    def get_system_health(self) -> dict:
        """Get overall system health metrics"""
        with self.db.get_session() as session:
            health = session.execute(
                text("SELECT * FROM qusd_health")
            ).fetchone()
            
            if health:
                return {
                    'total_qusd': Decimal(health[0] or 0),
                    'reserve_backing': Decimal(health[1] or 0),
                    'cdp_debt': Decimal(health[2] or 0),
                    'active_vaults': int(health[3] or 0),
                    'at_risk_vaults': int(health[4] or 0)
                }
            
            return {}

