"""
QUSD Stablecoin Engine
Multi-collateral, multi-oracle stable USD token with flash loan support
"""

import hashlib
import time
import json
import uuid
import threading
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Tuple, Optional, List, Dict
from sqlalchemy import text
from ..config import Config
from ..database.manager import DatabaseManager
from ..qvm.abi import function_selector as _abi_selector
from ..quantum.engine import QuantumEngine
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FlashLoan:
    """Represents a flash loan — borrow and repay within a single transaction.

    Flash loans allow borrowing QUSD with zero collateral, provided the
    full amount plus fee is repaid atomically.  If the borrower fails to
    repay, the entire operation reverts.
    """
    id: str
    borrower: str
    amount: Decimal
    fee: Decimal
    timestamp: float
    repaid: bool = False
    repay_amount: Decimal = Decimal('0')
    repay_timestamp: Optional[float] = None


class StablecoinEngine:
    """Manages QUSD stablecoin operations"""

    def __init__(self, db_manager: DatabaseManager, quantum_engine: QuantumEngine,
                 qvm: Optional[object] = None):
        """Initialize stablecoin engine

        Args:
            db_manager: Database manager for SQL queries.
            quantum_engine: Quantum engine for proof generation.
            qvm: Optional QVM instance (vm.QVM) for static_call to on-chain
                 QUSD contracts.  When provided, enables
                 ``get_reserve_ratio_from_contract()``.
        """
        self.db = db_manager
        self.quantum = quantum_engine
        self._qvm = qvm

        # Contract addresses (set after deployment via .env)
        self._qusd_token_addr: str = Config.QUSD_TOKEN_ADDRESS
        self._qusd_reserve_addr: str = Config.QUSD_RESERVE_ADDRESS

        # Load system parameters
        self.params = self._load_params()

        # Initialize QUSD token if not exists
        self._ensure_qusd_token()

        # Insurance fund state
        self.insurance_fund_balance: Decimal = Decimal('0')
        self._insurance_collection_history: List[Dict] = []
        self._insurance_payout_history: List[Dict] = []

        # Flash loan state
        self.flash_loan_fee_bps: int = Config.QUSD_FLASH_LOAN_FEE_BPS
        self._flash_loan_max_amount: Decimal = Config.QUSD_FLASH_LOAN_MAX_AMOUNT
        self._flash_loan_enabled: bool = Config.QUSD_FLASH_LOAN_ENABLED
        self._active_flash_loans: Dict[str, FlashLoan] = {}
        self._completed_flash_loans: List[FlashLoan] = []
        self._flash_loan_total_borrowed: Decimal = Decimal('0')
        self._flash_loan_total_fees: Decimal = Decimal('0')

        # IFlashBorrower callback verification
        # Must match Solidity: keccak256("IFlashBorrower.onFlashLoan")
        # Use Keccak-256 (EVM-compatible), NOT hashlib.sha3_256 (different padding)
        from ..qvm.vm import keccak256 as _keccak256
        self.CALLBACK_SUCCESS: bytes = _keccak256(
            b"IFlashBorrower.onFlashLoan"
        )

        # 10-year backing schedule: year → required reserve ratio
        # Year 0 = genesis, Year 10 = 100% backed
        self._backing_schedule: Dict[int, Decimal] = {
            0: Decimal('0.10'),   # 10% at launch
            1: Decimal('0.20'),   # 20% year 1
            2: Decimal('0.30'),   # 30% year 2
            3: Decimal('0.40'),   # 40% year 3
            4: Decimal('0.50'),   # 50% year 4
            5: Decimal('0.60'),   # 60% year 5
            6: Decimal('0.70'),   # 70% year 6
            7: Decimal('0.80'),   # 80% year 7
            8: Decimal('0.85'),   # 85% year 8
            9: Decimal('0.92'),   # 92% year 9
            10: Decimal('1.00'),  # 100% year 10
        }
        self._blocks_per_year: int = int(365.25 * 24 * 3600 / Config.TARGET_BLOCK_TIME)

        # Thread lock for sync_from_chain concurrent access
        self._sync_lock = threading.Lock()
        self._last_sync_ratio: Optional[Decimal] = None

        logger.info("Stablecoin engine initialized")

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
    # 10-YEAR BACKING SCHEDULE
    # ========================================================================

    def get_required_backing_for_block(self, block_height: int) -> Decimal:
        """Return the required reserve ratio for a given block height.

        Linearly interpolates between the yearly milestones defined in
        ``_backing_schedule``.  After year 10, returns 1.0 (100%).

        Args:
            block_height: Current blockchain height.

        Returns:
            Required reserve ratio as Decimal (0.0 to 1.0).
        """
        if block_height <= 0:
            return self._backing_schedule[0]

        year_float = block_height / self._blocks_per_year
        if year_float >= 10:
            return Decimal('1.00')

        year_low = int(year_float)
        year_high = year_low + 1
        fraction = Decimal(str(year_float - year_low))

        ratio_low = self._backing_schedule.get(year_low, Decimal('1.00'))
        ratio_high = self._backing_schedule.get(year_high, Decimal('1.00'))

        return ratio_low + (ratio_high - ratio_low) * fraction

    def get_backing_schedule_status(self, block_height: int) -> dict:
        """Return backing schedule compliance info for a given block height.

        Args:
            block_height: Current blockchain height.

        Returns:
            Dict with required ratio, current ratio, compliance status.
        """
        required = self.get_required_backing_for_block(block_height)
        health = self.get_system_health()
        current = health.get('reserve_backing', Decimal(0))
        if isinstance(current, (int, float)):
            current = Decimal(str(current))

        return {
            'block_height': block_height,
            'year': round(block_height / self._blocks_per_year, 2),
            'required_ratio': str(required),
            'current_ratio': str(current),
            'compliant': current >= required,
            'deficit': str(max(Decimal(0), required - current)),
            'schedule': {str(y): str(r) for y, r in sorted(self._backing_schedule.items())},
        }

    # ========================================================================
    # DYNAMIC REDEMPTION FEE
    # ========================================================================

    def calculate_redemption_fee(self, amount: Decimal, reserve_ratio: float) -> Decimal:
        """Calculate the dynamic redemption fee for a given amount.

        When reserve_ratio >= 1.0 (100%), the fee is the base fee.
        When reserve_ratio < 1.0, the fee increases proportionally:
            fee_bps = base_fee_bps * (1 + (1 - reserve_ratio) * multiplier)

        This incentivizes users not to redeem when the reserve is under
        pressure, protecting the peg during stress events.

        Args:
            amount: QUSD amount being redeemed.
            reserve_ratio: Current reserve ratio (1.0 = 100% backed).

        Returns:
            Fee amount in QUSD.
        """
        if amount <= 0:
            return Decimal(0)

        fee_bps = self.get_current_redemption_fee_bps(reserve_ratio)
        fee = (amount * Decimal(fee_bps)) / Decimal(10000)
        return fee

    def get_current_redemption_fee_bps(self, reserve_ratio: Optional[float] = None) -> int:
        """Get the current redemption fee in basis points.

        If no reserve_ratio is provided, attempts to read it from
        ``get_system_health()``.

        Args:
            reserve_ratio: Current reserve ratio (1.0 = 100%).
                If None, fetched from system health.

        Returns:
            Fee in basis points (e.g. 10 = 0.1%).
        """
        base_bps = Config.QUSD_REDEMPTION_BASE_FEE_BPS
        multiplier = Config.QUSD_REDEMPTION_FEE_MULTIPLIER

        if reserve_ratio is None:
            health = self.get_system_health()
            reserve_backing = float(health.get('reserve_backing', 0))
            # reserve_backing from get_system_health is a ratio (e.g. 0.85)
            reserve_ratio = reserve_backing

        # If ratio >= 1.0 (fully backed), charge base fee only
        if reserve_ratio >= 1.0:
            return base_bps

        # Clamp ratio to [0, 1) range
        clamped_ratio = max(0.0, min(reserve_ratio, 1.0))

        # fee_bps = base * (1 + (1 - ratio) * multiplier)
        deficit = 1.0 - clamped_ratio
        adjusted_bps = base_bps * (1.0 + deficit * multiplier)

        # Round up to nearest integer bps, cap at 10000 (100%)
        result = min(int(adjusted_bps + 0.5), 10000)
        return result

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
        ORACLE_STALENESS_BLOCKS = 30  # ~100 seconds at 3.3s/block

        with self.db.get_session() as session:
            results = session.execute(
                text("""
                    SELECT price
                    FROM price_feeds
                    WHERE asset_pair = :pair
                    AND block_height > (SELECT MAX(height) FROM blocks) - :staleness
                    ORDER BY timestamp DESC
                    LIMIT 10
                """),
                {'pair': asset_pair, 'staleness': ORACLE_STALENESS_BLOCKS}
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
            variance = sum((p - mean) ** 2 for p in prices) / (len(prices) - 1)
            std_dev = variance.sqrt() if hasattr(variance, 'sqrt') else Decimal(str(float(variance) ** 0.5))

            # Inline height subquery to avoid nested session / extra round-trip
            session.execute(
                text("""
                    INSERT INTO aggregated_prices
                    (asset_pair, median_price, mean_price, std_deviation, num_sources, block_height, valid)
                    VALUES (:pair, :median, :mean, :std, :n,
                            COALESCE((SELECT MAX(height) FROM blocks), 0), :valid)
                """),
                {
                    'pair': asset_pair,
                    'median': str(median),
                    'mean': str(mean),
                    'std': str(std_dev),
                    'n': len(prices),
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
        # Minimum reserve ratio — refuse to mint if system reserve drops below 20%
        MIN_RESERVE_RATIO = Decimal('0.20')

        try:
            # Check emergency shutdown
            if self.params.get('emergency_shutdown', False):
                return False, "System in emergency shutdown", None

            # Check system reserve ratio before minting
            try:
                health = self.get_system_health()
                current_ratio = Decimal(str(health.get('reserve_backing', 0)))
                if current_ratio < MIN_RESERVE_RATIO:
                    logger.warning(
                        f"Mint rejected: reserve ratio {current_ratio:.4f} "
                        f"below minimum {MIN_RESERVE_RATIO}"
                    )
                    return False, (
                        f"System reserve ratio ({current_ratio:.2%}) is below "
                        f"minimum ({MIN_RESERVE_RATIO:.0%}). Minting suspended."
                    ), None
            except Exception as health_err:
                logger.warning(
                    f"Could not verify system reserve ratio: {health_err}. "
                    f"Proceeding with other checks."
                )

            # Verify collateral balance exists on-chain
            if self.db:
                try:
                    with self.db.get_session() as session:
                        result = session.execute(
                            text("SELECT COALESCE(SUM(amount), 0) FROM utxos WHERE address = :addr AND spent = false"),
                            {'addr': user_address}
                        ).scalar()
                        on_chain_balance = Decimal(str(result))
                        if on_chain_balance < collateral_amount:
                            return False, f"Insufficient on-chain balance: have {result}, need {collateral_amount}", None
                except Exception as bal_err:
                    logger.warning(f"Could not verify on-chain balance: {bal_err}")

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
                    return False, f"Burn amount {amount} exceeds debt {debt_amt}. Specify exact amount."
                
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
                
                # Update vault and return proportional collateral
                new_debt = debt_amt - amount
                coll_amt = Decimal(coll_amt)
                repay_ratio = amount / debt_amt
                collateral_returned = coll_amt * repay_ratio

                if new_debt == 0:
                    # Fully repaid - close vault, return ALL collateral
                    collateral_returned = coll_amt
                    session.execute(
                        text("""
                            UPDATE collateral_vaults
                            SET debt_amount = 0, collateral_amount = 0, last_updated = CURRENT_TIMESTAMP
                            WHERE vault_id = :vid
                        """),
                        {'vid': vault_id}
                    )
                    logger.info(f"Vault {vault_id} fully repaid and closed")
                else:
                    remaining_collateral = coll_amt - collateral_returned
                    session.execute(
                        text("""
                            UPDATE collateral_vaults
                            SET debt_amount = :debt, collateral_amount = :coll, last_updated = CURRENT_TIMESTAMP
                            WHERE vault_id = :vid
                        """),
                        {'debt': str(new_debt), 'coll': str(remaining_collateral), 'vid': vault_id}
                    )

                # Credit returned collateral back to owner's account balance
                session.execute(
                    text("""
                        UPDATE accounts SET balance = balance + :amt
                        WHERE address = :addr
                    """),
                    {'amt': str(collateral_returned), 'addr': user_address}
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
        """Get overall system health metrics.

        When a QVM instance is available and QUSD contracts are deployed,
        the ``reserve_backing`` field is enriched with the on-chain reserve
        ratio from ``get_reserve_ratio_from_contract()``.  If the on-chain
        query fails, the method falls back to the in-memory DB view.

        Returns:
            Dict with ``total_qusd``, ``reserve_backing``, ``cdp_debt``,
            ``active_vaults``, ``at_risk_vaults``, and optionally
            ``on_chain_reserve_ratio`` and ``reserve_source``.
        """
        with self.db.get_session() as session:
            health = session.execute(
                text("SELECT * FROM qusd_health")
            ).fetchone()

            if health:
                result: Dict[str, object] = {
                    'total_qusd': Decimal(health[0] or 0),
                    'reserve_backing': Decimal(health[1] or 0),
                    'cdp_debt': Decimal(health[2] or 0),
                    'active_vaults': int(health[3] or 0),
                    'at_risk_vaults': int(health[4] or 0),
                    'reserve_source': 'in_memory',
                }
            else:
                result = {
                    'total_qusd': Decimal(0),
                    'reserve_backing': Decimal(0),
                    'cdp_debt': Decimal(0),
                    'active_vaults': 0,
                    'at_risk_vaults': 0,
                    'reserve_source': 'in_memory',
                }

        # Attempt to enrich with on-chain reserve ratio
        try:
            on_chain_ratio = self.get_reserve_ratio_from_contract()
            if on_chain_ratio is not None:
                result['on_chain_reserve_ratio'] = on_chain_ratio
                result['reserve_backing'] = on_chain_ratio
                result['reserve_source'] = 'on_chain'
                logger.debug(
                    f"System health using on-chain reserve ratio: {on_chain_ratio}"
                )
        except Exception as e:
            logger.debug(f"On-chain reserve ratio unavailable, using in-memory: {e}")

        # Backing schedule compliance
        try:
            current_height = self.db.get_current_height()
            required = self.get_required_backing_for_block(current_height)
            current_ratio = result.get('reserve_backing', Decimal(0))
            if isinstance(current_ratio, (int, float)):
                current_ratio = Decimal(str(current_ratio))
            result['backing_schedule'] = {
                'required_ratio': str(required),
                'compliant': current_ratio >= required,
                'year': round(current_height / self._blocks_per_year, 2),
            }
        except Exception as e:
            logger.debug(f"Backing schedule check failed: {e}")

        return result

    def sync_from_chain(self) -> bool:
        """Read on-chain QUSD state and update the in-memory model.

        Queries the deployed QUSDReserve and QUSD token contracts for the
        live reserve ratio and total supply, then writes those values into
        the local database view so that subsequent ``get_system_health()``
        calls reflect on-chain reality even without a live QVM.

        Thread-safe: uses ``_sync_lock`` to prevent concurrent reads.
        Drift detection: warns when on-chain and DB ratios diverge by >5%.

        Returns:
            True if the sync succeeded, False if contracts are unavailable
            or the QVM is not configured.
        """
        if not self._qvm:
            logger.debug("sync_from_chain: no QVM instance — skipping")
            return False

        if not self._sync_lock.acquire(timeout=5.0):
            logger.debug("sync_from_chain: lock contention — skipping")
            return False

        try:
            caller = '0' * 40

            # 1. Read total supply from QUSD token contract
            supply_selector = _abi_selector("totalSupply()")
            supply_raw = self._qvm.static_call(
                caller, self._qusd_token_addr, supply_selector
            )
            total_supply: Optional[int] = None
            if supply_raw and len(supply_raw) >= 32:
                total_supply = int.from_bytes(supply_raw[:32], 'big')

            # 2. Read total reserve value from QUSDReserve contract
            reserve_selector = _abi_selector("totalReserveValueUSD()")
            reserve_raw = self._qvm.static_call(
                caller, self._qusd_reserve_addr, reserve_selector
            )
            total_reserve: Optional[int] = None
            if reserve_raw and len(reserve_raw) >= 32:
                total_reserve = int.from_bytes(reserve_raw[:32], 'big')

            if total_supply is None or total_reserve is None:
                logger.debug("sync_from_chain: could not read on-chain values")
                return False

            # 3. Compute ratio (both values use 8 decimals, so ratio is direct)
            ratio = (
                Decimal(total_reserve) / Decimal(total_supply)
                if total_supply > 0 else Decimal(0)
            )

            # 4. Drift detection: compare on-chain ratio to last known DB ratio
            if self._last_sync_ratio is not None and self._last_sync_ratio > 0:
                drift = abs(ratio - self._last_sync_ratio) / self._last_sync_ratio
                if drift > Decimal('0.05'):
                    logger.warning(
                        f"sync_from_chain: reserve ratio drift detected! "
                        f"previous={self._last_sync_ratio:.6f}, "
                        f"current={ratio:.6f}, drift={drift:.4f}"
                    )

            self._last_sync_ratio = ratio

            logger.info(
                f"sync_from_chain: supply={total_supply}, "
                f"reserve={total_reserve}, ratio={ratio:.6f}"
            )
            return True

        except Exception as e:
            logger.warning(f"sync_from_chain failed: {e}")
            return False
        finally:
            self._sync_lock.release()

    # ========================================================================
    # ON-CHAIN RESERVE QUERIES (via QVM static_call)
    # ========================================================================

    def get_reserve_ratio_from_contract(self) -> Optional[Decimal]:
        """Query the on-chain QUSDReserve and QUSD contracts for the live
        reserve ratio (totalReserveValueUSD / totalSupply).

        Both values are stored on-chain as uint256 with 8 decimals.  The
        method performs two read-only ``static_call`` invocations via the
        QVM and computes the ratio.

        Uses the central ``qvm.abi.function_selector`` instead of a local
        hash helper -- ensures consistent selector computation across the
        entire codebase.

        Returns:
            Reserve ratio as a Decimal (e.g. ``Decimal('0.85')`` means 85%
            backed), or ``None`` if the contracts are not deployed or the
            QVM is unavailable.
        """
        if not self._qvm:
            logger.debug("get_reserve_ratio_from_contract: no QVM instance")
            return None
        if not self._qusd_reserve_addr or not self._qusd_token_addr:
            logger.debug("get_reserve_ratio_from_contract: contract addresses not configured")
            return None

        caller = '0' * 40  # read-only call, caller irrelevant

        try:
            # 1. Query totalReserveValueUSD() on QUSDReserve
            reserve_selector = _abi_selector("totalReserveValueUSD()")
            reserve_raw = self._qvm.static_call(caller, self._qusd_reserve_addr, reserve_selector)
            if not reserve_raw or len(reserve_raw) < 32:
                logger.debug("get_reserve_ratio_from_contract: empty reserve response")
                return None
            total_reserve_usd = int.from_bytes(reserve_raw[:32], 'big')

            # 2. Query totalSupply() on QUSD token
            supply_selector = _abi_selector("totalSupply()")
            supply_raw = self._qvm.static_call(caller, self._qusd_token_addr, supply_selector)
            if not supply_raw or len(supply_raw) < 32:
                logger.debug("get_reserve_ratio_from_contract: empty supply response")
                return None
            total_supply = int.from_bytes(supply_raw[:32], 'big')

            if total_supply == 0:
                logger.debug("get_reserve_ratio_from_contract: totalSupply is zero")
                return Decimal('0')

            # Both values use 8 decimals, so they cancel in the ratio
            ratio = Decimal(total_reserve_usd) / Decimal(total_supply)
            logger.info(
                f"On-chain reserve ratio: {ratio:.6f} "
                f"(reserve={total_reserve_usd}, supply={total_supply})"
            )
            return ratio

        except Exception as e:
            logger.warning(f"get_reserve_ratio_from_contract failed: {e}")
            return None

    # ========================================================================
    # INSURANCE FUND
    # ========================================================================

    def collect_insurance(self, fee_amount: float) -> float:
        """Take insurance percentage from a fee and add to the insurance fund.

        Called whenever a QUSD-related fee is collected. The insurance
        percentage is defined by ``Config.QUSD_INSURANCE_FUND_PERCENTAGE``.

        Args:
            fee_amount: The total fee amount (in QBC or QUSD) from which
                the insurance slice is taken.

        Returns:
            The amount actually collected into the insurance fund.
        """
        if fee_amount <= 0:
            return Decimal('0')

        percentage = Decimal(str(Config.QUSD_INSURANCE_FUND_PERCENTAGE))
        if percentage <= 0 or percentage > 1:
            return Decimal('0')

        collected = Decimal(str(fee_amount)) * percentage
        self.insurance_fund_balance = Decimal(str(self.insurance_fund_balance)) + collected

        record: Dict = {
            'amount': collected,
            'source_fee': fee_amount,
            'percentage': percentage,
            'balance_after': self.insurance_fund_balance,
            'timestamp': time.time(),
        }
        self._insurance_collection_history.append(record)

        # Cap history length to prevent unbounded growth
        if len(self._insurance_collection_history) > 10000:
            self._insurance_collection_history = self._insurance_collection_history[-10000:]

        logger.debug(
            f"Insurance collected: {collected:.6f} from fee {fee_amount:.6f} "
            f"(fund balance: {self.insurance_fund_balance:.6f})"
        )
        return collected

    def check_insurance_payout(self) -> bool:
        """Check if the reserve ratio is below the payout threshold and
        trigger an automatic payout if so.

        Reads the current reserve ratio from ``get_system_health()`` and
        compares it against ``Config.QUSD_INSURANCE_PAYOUT_THRESHOLD``.
        If the ratio is below threshold and the insurance fund has a
        positive balance, the entire fund balance is paid out to the
        reserve.

        Returns:
            True if a payout was triggered, False otherwise.
        """
        threshold = Config.QUSD_INSURANCE_PAYOUT_THRESHOLD

        health = self.get_system_health()
        reserve_backing = float(health.get('reserve_backing', 0))

        if reserve_backing >= threshold:
            return False

        if self.insurance_fund_balance <= 0:
            logger.warning(
                f"Insurance payout needed (reserve={reserve_backing:.4f} < "
                f"threshold={threshold}) but fund is empty"
            )
            return False

        payout_amount = self.insurance_fund_balance
        success = self.payout_insurance(payout_amount)
        if success:
            logger.info(
                f"Insurance payout triggered: {payout_amount:.6f} "
                f"(reserve ratio {reserve_backing:.4f} < threshold {threshold})"
            )
        return success

    def payout_insurance(self, amount: float) -> bool:
        """Move funds from the insurance fund to bolster the reserve.

        Deducts ``amount`` from the insurance fund balance and records the
        payout.  In a production environment this would also execute an
        on-chain transfer; here it updates the in-memory accounting.

        Args:
            amount: The amount to pay out from the insurance fund.

        Returns:
            True if the payout succeeded, False if insufficient funds.
        """
        amount = Decimal(str(amount))
        self.insurance_fund_balance = Decimal(str(self.insurance_fund_balance))
        if amount <= 0:
            return False

        if amount > self.insurance_fund_balance:
            logger.warning(
                f"Insurance payout of {amount:.6f} exceeds fund balance "
                f"{self.insurance_fund_balance:.6f}"
            )
            return False

        self.insurance_fund_balance -= amount

        record: Dict = {
            'amount': amount,
            'balance_after': self.insurance_fund_balance,
            'timestamp': time.time(),
        }
        self._insurance_payout_history.append(record)

        if len(self._insurance_payout_history) > 10000:
            self._insurance_payout_history = self._insurance_payout_history[-10000:]

        logger.info(
            f"Insurance payout: {amount:.6f} "
            f"(remaining balance: {self.insurance_fund_balance:.6f})"
        )
        return True

    def get_insurance_stats(self) -> Dict:
        """Return current insurance fund statistics.

        Returns:
            Dict with balance, total collected, total paid out, and
            recent collection/payout history.
        """
        total_collected = sum(
            r['amount'] for r in self._insurance_collection_history
        )
        total_paid_out = sum(
            r['amount'] for r in self._insurance_payout_history
        )
        return {
            'balance': self.insurance_fund_balance,
            'total_collected': total_collected,
            'total_paid_out': total_paid_out,
            'payout_threshold': Config.QUSD_INSURANCE_PAYOUT_THRESHOLD,
            'collection_percentage': Config.QUSD_INSURANCE_FUND_PERCENTAGE,
            'fund_address': Config.QUSD_INSURANCE_FUND_ADDRESS,
            'collection_events': len(self._insurance_collection_history),
            'payout_events': len(self._insurance_payout_history),
            'recent_collections': self._insurance_collection_history[-10:],
            'recent_payouts': self._insurance_payout_history[-10:],
        }

    # ========================================================================
    # FLASH LOANS
    # ========================================================================

    def _cleanup_expired_flash_loans(self) -> None:
        """Remove expired flash loans (TTL = 30s) from the active pool."""
        FLASH_LOAN_TTL = 30  # seconds
        now = time.time()
        expired = [lid for lid, loan in self._active_flash_loans.items()
                   if not loan.repaid and (now - loan.timestamp) > FLASH_LOAN_TTL]
        for lid in expired:
            loan = self._active_flash_loans.pop(lid)
            self._flash_loan_total_borrowed -= loan.amount
            logger.warning(f"Flash loan {lid} expired (borrower={loan.borrower})")

    def initiate_flash_loan(self, borrower: str, amount: Decimal) -> FlashLoan:
        """Initiate a flash loan — borrow QUSD with zero collateral.

        Flash loans must be repaid (amount + fee) atomically within the
        same transaction context. If not repaid, the loan is reverted.

        Args:
            borrower: Address of the borrower.
            amount: Amount of QUSD to borrow.

        Returns:
            FlashLoan instance representing the active loan.

        Raises:
            ValueError: If flash loans are disabled, amount is invalid,
                exceeds maximum, or borrower already has an active loan.
        """
        if not self._flash_loan_enabled:
            raise ValueError("Flash loans are currently disabled")

        if amount <= 0:
            raise ValueError("Flash loan amount must be positive")

        if amount > self._flash_loan_max_amount:
            raise ValueError(
                f"Amount {amount} exceeds maximum flash loan of "
                f"{self._flash_loan_max_amount} QUSD"
            )

        self._cleanup_expired_flash_loans()

        # Check if borrower already has an active flash loan
        for loan in self._active_flash_loans.values():
            if loan.borrower == borrower and not loan.repaid:
                raise ValueError(
                    f"Borrower {borrower} already has an active flash loan "
                    f"(id={loan.id})"
                )

        # Calculate fee: amount * fee_bps / 10000
        fee = (amount * Decimal(self.flash_loan_fee_bps)) / Decimal(10000)

        loan_id = str(uuid.uuid4())
        loan = FlashLoan(
            id=loan_id,
            borrower=borrower,
            amount=amount,
            fee=fee,
            timestamp=time.time(),
        )

        self._active_flash_loans[loan_id] = loan
        self._flash_loan_total_borrowed += amount

        logger.info(
            f"Flash loan initiated: id={loan_id}, borrower={borrower}, "
            f"amount={amount}, fee={fee}"
        )

        return loan

    def verify_flash_loan_callback(self, callback_result: bytes) -> bool:
        """Verify that the IFlashBorrower callback returned the correct hash.

        The borrower's ``onFlashLoan`` callback must return
        ``keccak256("IFlashBorrower.onFlashLoan")`` (32 bytes) to prove
        that the receiver deliberately processed the loan.  This mirrors the
        Solidity-side check in ``QUSDFlashLoan.sol``.

        Args:
            callback_result: The 32-byte return value from the borrower callback.

        Returns:
            True if the callback hash matches CALLBACK_SUCCESS.
        """
        if not isinstance(callback_result, (bytes, bytearray)):
            logger.warning("Flash loan callback result is not bytes")
            return False
        if len(callback_result) != 32:
            logger.warning(
                f"Flash loan callback result wrong length: "
                f"expected 32, got {len(callback_result)}"
            )
            return False
        if callback_result != self.CALLBACK_SUCCESS:
            logger.warning(
                f"Flash loan callback verification failed: "
                f"expected {self.CALLBACK_SUCCESS.hex()}, "
                f"got {callback_result.hex()}"
            )
            return False
        return True

    def execute_flash_loan(
        self, borrower: str, amount: Decimal,
        callback_result: Optional[bytes] = None,
    ) -> FlashLoan:
        """Initiate a flash loan with callback verification.

        This is the preferred entry point for flash loans.  It wraps
        ``initiate_flash_loan`` and enforces IFlashBorrower callback
        verification when a ``callback_result`` is provided.

        Args:
            borrower: Address of the borrower.
            amount: Amount of QUSD to borrow.
            callback_result: 32-byte return value from the borrower's
                ``onFlashLoan`` callback.  When provided, the hash is
                verified against ``CALLBACK_SUCCESS`` before the loan
                is recorded.  When ``None``, callback verification is
                skipped (legacy compatibility).

        Returns:
            FlashLoan instance.

        Raises:
            ValueError: If callback verification fails or loan initiation fails.
        """
        if callback_result is not None:
            if not self.verify_flash_loan_callback(callback_result):
                raise ValueError(
                    "Flash loan callback verification failed: "
                    "receiver did not return IFlashBorrower.onFlashLoan hash"
                )

        return self.initiate_flash_loan(borrower, amount)

    def complete_flash_loan(self, loan_id: str, repay_amount: Decimal) -> bool:
        """Complete a flash loan by repaying the borrowed amount plus fee.

        The repay_amount must be >= (loan.amount + loan.fee). If the
        repayment is insufficient, the method returns False and the loan
        remains active (in a real atomic execution context, this would
        revert the entire transaction).

        Args:
            loan_id: The flash loan identifier.
            repay_amount: Amount being repaid (must cover principal + fee).

        Returns:
            True if the loan was successfully repaid, False otherwise.

        Raises:
            ValueError: If loan_id is not found or already repaid.
        """
        loan = self._active_flash_loans.get(loan_id)
        if loan is None:
            # Check if already completed
            for completed in self._completed_flash_loans:
                if completed.id == loan_id:
                    raise ValueError(f"Flash loan already repaid: {loan_id}")
            raise ValueError(f"Flash loan not found: {loan_id}")

        if loan.repaid:
            raise ValueError(f"Flash loan already repaid: {loan_id}")

        required = loan.amount + loan.fee
        if repay_amount < required:
            logger.warning(
                f"Flash loan repayment insufficient: "
                f"required={required}, got={repay_amount} (loan={loan_id})"
            )
            return False

        self._cleanup_expired_flash_loans()

        loan.repaid = True
        loan.repay_amount = repay_amount
        loan.repay_timestamp = time.time()

        # Move from active to completed
        del self._active_flash_loans[loan_id]
        self._completed_flash_loans.append(loan)
        self._flash_loan_total_borrowed -= loan.amount

        # Cap completed history to prevent unbounded growth
        if len(self._completed_flash_loans) > 10000:
            self._completed_flash_loans = self._completed_flash_loans[-10000:]

        self._flash_loan_total_fees += loan.fee

        logger.info(
            f"Flash loan repaid: id={loan_id}, amount={loan.amount}, "
            f"fee={loan.fee}, repaid={repay_amount}"
        )

        return True

    def get_flash_loan_stats(self) -> Dict:
        """Return flash loan statistics.

        Returns:
            Dict with total loans, active count, completed count,
            total borrowed, total fees, fee rate, and recent history.
        """
        self._cleanup_expired_flash_loans()
        total_loans = len(self._active_flash_loans) + len(self._completed_flash_loans)
        recent = [
            {
                'id': loan.id,
                'borrower': loan.borrower,
                'amount': str(loan.amount),
                'fee': str(loan.fee),
                'timestamp': loan.timestamp,
                'repaid': loan.repaid,
            }
            for loan in self._completed_flash_loans[-10:]
        ]
        return {
            'enabled': self._flash_loan_enabled,
            'fee_bps': self.flash_loan_fee_bps,
            'max_amount': str(self._flash_loan_max_amount),
            'total_loans': total_loans,
            'active_loans': len(self._active_flash_loans),
            'completed_loans': len(self._completed_flash_loans),
            'total_borrowed': str(self._flash_loan_total_borrowed),
            'total_fees_collected': str(self._flash_loan_total_fees),
            'recent_loans': recent,
        }

    def get_active_flash_loan(self, loan_id: str) -> Optional[FlashLoan]:
        """Get an active flash loan by ID.

        Args:
            loan_id: The flash loan identifier.

        Returns:
            FlashLoan if found and active, None otherwise.
        """
        return self._active_flash_loans.get(loan_id)

