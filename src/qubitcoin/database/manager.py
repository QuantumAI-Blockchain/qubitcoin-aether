"""
Database manager for CockroachDB
Handles all database operations with proper compatibility
"""
import json
import threading
from contextlib import contextmanager
from decimal import Decimal
from typing import List, Optional
import psycopg2
import psycopg2.extras
from sqlalchemy import (
    create_engine, text, event, Column, String, BigInteger, Integer,
    Float, Numeric, Boolean, JSON, DateTime, Text, UniqueConstraint
)
from sqlalchemy.orm import sessionmaker, Session as DBSession, declarative_base
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.pool import StaticPool
from .models import UTXO, Transaction, Block
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Disable psycopg2 hstore for CockroachDB compatibility
original_register_hstore = psycopg2.extras.register_hstore
def patched_register_hstore(*args, **kwargs):
    """Skip hstore registration"""
    pass
psycopg2.extras.register_hstore = patched_register_hstore

# ===========================================================
# SQLAlchemy Base and table definitions for first startup
# ===========================================================
Base = declarative_base()

# -----------------------------------------------------------
# Core Blockchain Tables
# -----------------------------------------------------------

class BlockModel(Base):
    __tablename__ = 'blocks'
    height = Column(BigInteger, primary_key=True)
    prev_hash = Column(String(64))
    difficulty = Column(Float)
    proof_json = Column(JSON)
    created_at = Column(Float)
    block_hash = Column(String(64))

class TransactionModel(Base):
    __tablename__ = 'transactions'
    txid = Column(String(64), primary_key=True)
    inputs = Column(JSON)
    outputs = Column(JSON)
    fee = Column(Numeric)
    signature = Column(String)
    public_key = Column(String)
    timestamp = Column(Float)
    block_height = Column(BigInteger, nullable=True)
    status = Column(String, default='pending')

class UTXOModel(Base):
    __tablename__ = 'utxos'
    txid = Column(String(64), primary_key=True)
    vout = Column(BigInteger, primary_key=True)
    amount = Column(Numeric)
    address = Column(String)
    proof = Column(JSON)
    block_height = Column(BigInteger, nullable=True)
    spent = Column(Boolean, default=False)
    spent_by = Column(String, nullable=True)

class SupplyModel(Base):
    __tablename__ = 'supply'
    id = Column(BigInteger, primary_key=True, default=1)
    total_minted = Column(Numeric, default=0)

class SolvedHamiltonianModel(Base):
    __tablename__ = 'solved_hamiltonians'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    hamiltonian = Column(JSON)
    params = Column(JSON)
    energy = Column(Float)
    miner_address = Column(String)
    block_height = Column(BigInteger)

# -----------------------------------------------------------
# Smart Contract Tables
# -----------------------------------------------------------

class ContractModel(Base):
    __tablename__ = 'contracts'
    contract_id = Column(String(66), primary_key=True, server_default=text("gen_random_uuid()::STRING"))
    deployer_address = Column(String, nullable=False)
    contract_type = Column(String(50), nullable=False)
    contract_code = Column(JSON, nullable=False)
    contract_state = Column(JSON, default={})
    gas_paid = Column(Numeric(18, 8), default=0)
    block_height = Column(BigInteger)
    deployed_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    is_active = Column(Boolean, default=True)
    last_executed = Column(DateTime, nullable=True)
    execution_count = Column(Integer, default=0)

class ContractExecutionModel(Base):
    __tablename__ = 'contract_executions'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_id = Column(String(66), nullable=False)
    executor_address = Column(String, nullable=False)
    method = Column(String(100))
    params = Column(JSON)
    gas_paid = Column(Numeric(18, 8), default=0)
    success = Column(Boolean)
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    block_height = Column(BigInteger)
    executed_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# Token Tables
# -----------------------------------------------------------

class TokenModel(Base):
    __tablename__ = 'tokens'
    token_id = Column(String(66), primary_key=True, server_default=text("gen_random_uuid()::STRING"))
    symbol = Column(String(20), nullable=False, unique=True)
    name = Column(String(100), nullable=True)
    contract_id = Column(String(66), nullable=True)
    active = Column(Boolean, default=True)
    total_supply = Column(Numeric(30, 8), default=0)
    decimals = Column(Integer, default=8)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class TokenBalanceModel(Base):
    __tablename__ = 'token_balances'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_id = Column(String(66), nullable=False)
    holder_address = Column(String, nullable=False)
    balance = Column(Numeric(30, 8), default=0)
    last_updated = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint('contract_id', 'holder_address', name='uq_token_balance'),
    )

class TokenTransferModel(Base):
    __tablename__ = 'token_transfers'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    token_id = Column(String(66), nullable=False)
    from_address = Column(String, nullable=False)
    to_address = Column(String, nullable=False)
    amount = Column(Numeric(30, 8), nullable=False)
    txid = Column(String(64))
    block_height = Column(BigInteger)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# Stablecoin Tables
# -----------------------------------------------------------

class StablecoinParamModel(Base):
    __tablename__ = 'stablecoin_params'
    param_name = Column(String(100), primary_key=True)
    param_value = Column(String, nullable=False)
    param_type = Column(String(20), default='string')

class OracleSourceModel(Base):
    __tablename__ = 'oracle_sources'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False, unique=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class PriceFeedModel(Base):
    __tablename__ = 'price_feeds'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    asset_pair = Column(String(20), nullable=False)
    price = Column(Numeric(30, 10), nullable=False)
    source_id = Column(BigInteger, nullable=False)
    block_height = Column(BigInteger)
    confidence = Column(Numeric(5, 4), default=0)
    timestamp = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class AggregatedPriceModel(Base):
    __tablename__ = 'aggregated_prices'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    asset_pair = Column(String(20), nullable=False)
    median_price = Column(Numeric(30, 10))
    mean_price = Column(Numeric(30, 10))
    std_deviation = Column(Numeric(30, 10))
    num_sources = Column(Integer)
    block_height = Column(BigInteger)
    valid = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class CollateralTypeModel(Base):
    __tablename__ = 'collateral_types'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    asset_name = Column(String(20), nullable=False, unique=True)
    asset_type = Column(String(20), nullable=False)
    liquidation_ratio = Column(Numeric(10, 4), nullable=False)
    debt_ceiling = Column(Numeric(30, 8), nullable=False)
    min_collateral = Column(Numeric(30, 8), nullable=False)
    active = Column(Boolean, default=True)

class CollateralVaultModel(Base):
    __tablename__ = 'collateral_vaults'
    vault_id = Column(BigInteger, primary_key=True, autoincrement=True)
    owner_address = Column(String, nullable=False)
    collateral_type_id = Column(BigInteger, nullable=False)
    collateral_amount = Column(Numeric(30, 8), nullable=False)
    debt_amount = Column(Numeric(30, 8), nullable=False)
    collateral_ratio = Column(Numeric(10, 4))
    liquidated = Column(Boolean, default=False)
    last_updated = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class QUSDOperationModel(Base):
    __tablename__ = 'qusd_operations'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    operation_type = Column(String(20), nullable=False)
    user_address = Column(String, nullable=False)
    amount = Column(Numeric(30, 8), nullable=False)
    collateral_locked = Column(Numeric(30, 8), nullable=True)
    collateral_type = Column(String(20), nullable=True)
    price_at_operation = Column(Numeric(30, 10), nullable=True)
    quantum_proof = Column(JSON, nullable=True)
    txid = Column(String(64))
    block_height = Column(BigInteger)
    status = Column(String(20), default='pending')
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# Bridge Tables
# -----------------------------------------------------------

class BridgeDepositModel(Base):
    __tablename__ = 'bridge_deposits'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    qbc_txid = Column(String(64), nullable=False)
    qbc_address = Column(String, nullable=False)
    target_chain = Column(String(20), nullable=False)
    target_address = Column(String, nullable=False)
    qbc_amount = Column(Numeric(30, 8), nullable=False)
    status = Column(String(20), default='detected')
    chain_data = Column(JSON, nullable=True)
    target_txhash = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class BridgeWithdrawalModel(Base):
    __tablename__ = 'bridge_withdrawals'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_chain = Column(String(20), nullable=False)
    source_txhash = Column(String, nullable=False)
    source_address = Column(String, nullable=False)
    qbc_address = Column(String, nullable=False)
    wqbc_amount = Column(Numeric(30, 8), nullable=False)
    status = Column(String(20), default='detected')
    chain_data = Column(JSON, nullable=True)
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# IPFS Tables
# -----------------------------------------------------------

class IPFSSnapshotModel(Base):
    __tablename__ = 'ipfs_snapshots'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cid = Column(String, nullable=False, unique=True)
    block_height = Column(BigInteger, nullable=False)
    chain_hash = Column(String(64), nullable=True)
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# Launchpad Tables
# -----------------------------------------------------------

class LaunchpadSaleModel(Base):
    __tablename__ = 'launchpad_sales'
    sale_id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_id = Column(String(66), nullable=False)
    raise_target = Column(Numeric(30, 8))
    current_raised = Column(Numeric(30, 8), default=0)
    token_price = Column(Numeric(30, 8))
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    status = Column(String(20), default='active')

class LaunchpadParticipantModel(Base):
    __tablename__ = 'launchpad_participants'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sale_id = Column(BigInteger, nullable=False)
    participant_address = Column(String, nullable=False)
    amount_contributed = Column(Numeric(30, 8), default=0)
    __table_args__ = (
        UniqueConstraint('sale_id', 'participant_address', name='uq_launchpad_participant'),
    )

# -----------------------------------------------------------
# Quantum Gate Tables
# -----------------------------------------------------------

class QuantumGateModel(Base):
    __tablename__ = 'quantum_gates'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_id = Column(String(66), nullable=False)
    is_unlocked = Column(Boolean, default=False)
    unlocked_by = Column(String, nullable=True)
    unlock_proof = Column(JSON, nullable=True)
    unlocked_at = Column(DateTime, nullable=True)

# ===========================================================
# Database Manager
# ===========================================================
class DatabaseManager:
    """Manages all database operations"""
    def __init__(self):
        """Initialize database connection"""
        self._patch_sqlalchemy()
        self.engine = self._create_engine()
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False
        )
        self._create_tables()
        self._test_connection()
        logger.info("✓ Database manager initialized")

    def _patch_sqlalchemy(self):
        """Patch SQLAlchemy for CockroachDB compatibility"""
        from sqlalchemy.dialects.postgresql import psycopg2 as psycopg2_dialect
        from sqlalchemy.dialects.postgresql import base
        # Patch hstore checks
        original_on_connect = psycopg2_dialect.PGDialect_psycopg2.on_connect
        def patched_on_connect(self):
            def on_connect(conn):
                pass
            return on_connect
        psycopg2_dialect.PGDialect_psycopg2.on_connect = patched_on_connect
        # Patch version detection
        original_get_version = base.PGDialect._get_server_version_info
        def patched_get_version(self, connection):
            try:
                version = connection.exec_driver_sql("SELECT version()").scalar()
                if 'CockroachDB' in str(version):
                    logger.debug(f"Detected: {version}")
                    return (13, 0)
                return original_get_version(self, connection)
            except:
                return (13, 0)
        base.PGDialect._get_server_version_info = patched_get_version

    def _create_engine(self):
        """Create SQLAlchemy engine"""
        return create_engine(
            Config.DATABASE_URL,
            pool_pre_ping=True,
            echo=Config.DEBUG,
            pool_size=Config.DB_POOL_SIZE,
            max_overflow=Config.DB_MAX_OVERFLOW,
            pool_timeout=Config.DB_POOL_TIMEOUT
        )

    def _create_tables(self):
        """Create all tables if they don't exist"""
        Base.metadata.create_all(self.engine)
        # Ensure supply row exists
        with self.get_session() as session:
            res = session.execute(text("SELECT 1 FROM supply WHERE id = 1")).fetchone()
            if not res:
                session.execute(text("INSERT INTO supply (id, total_minted) VALUES (1, 0)"))
                session.commit()
        # Seed default stablecoin params if empty
        with self.get_session() as session:
            res = session.execute(text("SELECT 1 FROM stablecoin_params LIMIT 1")).fetchone()
            if not res:
                defaults = [
                    ('min_collateral_ratio', '1.5', 'decimal'),
                    ('liquidation_ratio', '1.2', 'decimal'),
                    ('stability_fee', '0.02', 'decimal'),
                    ('emergency_shutdown', 'false', 'boolean'),
                ]
                for name, value, ptype in defaults:
                    session.execute(
                        text("INSERT INTO stablecoin_params (param_name, param_value, param_type) VALUES (:n, :v, :t)"),
                        {'n': name, 'v': value, 't': ptype}
                    )
                session.commit()
        # Create database views for health monitoring
        with self.get_session() as session:
            session.execute(text("""
                CREATE VIEW IF NOT EXISTS vault_health AS
                SELECT vault_id,
                       CASE
                           WHEN liquidated THEN 'liquidated'
                           WHEN collateral_ratio < 1.2 THEN 'liquidatable'
                           WHEN collateral_ratio < 1.5 THEN 'danger'
                           WHEN collateral_ratio < 2.0 THEN 'warning'
                           ELSE 'healthy'
                       END AS health_status
                FROM collateral_vaults
            """))
            session.execute(text("""
                CREATE VIEW IF NOT EXISTS qusd_health AS
                SELECT
                    COALESCE((SELECT SUM(total_supply) FROM tokens WHERE symbol = 'QUSD'), 0) AS total_qusd,
                    COALESCE((SELECT SUM(collateral_amount) FROM collateral_vaults WHERE NOT liquidated), 0) AS reserve_backing,
                    COALESCE((SELECT SUM(debt_amount) FROM collateral_vaults WHERE NOT liquidated), 0) AS cdp_debt,
                    COALESCE((SELECT COUNT(*) FROM collateral_vaults WHERE NOT liquidated), 0) AS active_vaults,
                    COALESCE((SELECT COUNT(*) FROM collateral_vaults WHERE NOT liquidated AND collateral_ratio < 1.5), 0) AS at_risk_vaults
            """))
            session.commit()
        logger.info("✅ All tables and views verified/created")

    def _test_connection(self):
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✓ Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    @contextmanager
    def get_session(self):
        """Get database session with proper cleanup"""
        session = self.SessionLocal()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ========================================================================
    # UTXO OPERATIONS
    # ========================================================================
    def get_utxos(self, address: str) -> List[UTXO]:
        """Get all unspent outputs for address"""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT txid, vout, amount, address, proof, block_height, spent
                    FROM utxos
                    WHERE address = :addr AND spent = false
                    ORDER BY block_height DESC
                """),
                {'addr': address}
            )
            utxos = []
            for row in result:
                utxos.append(UTXO(
                    txid=row[0],
                    vout=row[1],
                    amount=Decimal(row[2]),
                    address=row[3],
                    proof=json.loads(row[4]) if isinstance(row[4], str) else row[4],
                    block_height=row[5],
                    spent=row[6]
                ))
            return utxos
    def mark_utxos_spent(self, inputs: List[dict], txid: str, session: DBSession):
        """Mark UTXOs as spent"""
        for inp in inputs:
            session.execute(
                text("""
                    UPDATE utxos
                    SET spent = true, spent_by = :spent_by
                    WHERE txid = :txid AND vout = :vout AND spent = false
                """),
                {'txid': inp['txid'], 'vout': inp['vout'], 'spent_by': txid}
            )
    def create_utxos(self, txid: str, outputs: List[dict], block_height: int,
                     proof: dict, session: DBSession):
        """Create new UTXOs"""
        for vout, output in enumerate(outputs):
            session.execute(
                text("""
                    INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                    VALUES (:txid, :vout, :amount, :address, CAST(:proof AS jsonb), :height, false)
                """),
                {
                    'txid': txid,
                    'vout': vout,
                    'amount': str(output['amount']),
                    'address': output['address'],
                    'proof': json.dumps(proof),
                    'height': block_height
                }
            )
    def get_balance(self, address: str) -> Decimal:
        """Get total balance for address"""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM utxos
                    WHERE address = :addr AND spent = false
                """),
                {'addr': address}
            )
            return Decimal(result.scalar() or 0)
    # ========================================================================
    # BLOCK OPERATIONS
    # ========================================================================
    def get_current_height(self) -> int:
        """Get current blockchain height"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT COALESCE(MAX(height), -1) FROM blocks")
            )
            return result.scalar()
    def get_block(self, height: int) -> Optional[Block]:
        """Get block by height"""
        with self.get_session() as session:
            result = session.execute(
                text("""SELECT height, prev_hash, difficulty, proof_json,
                        created_at, block_hash
                        FROM blocks WHERE height = :h"""),
                {'h': height}
            ).fetchone()
            if not result:
                return None
            # Get transactions with explicit column names
            tx_results = session.execute(
                text("""SELECT txid, inputs, outputs, fee, signature,
                        public_key, timestamp, block_height, status
                        FROM transactions WHERE block_height = :h"""),
                {'h': height}
            )
            transactions = []
            for tx_row in tx_results:
                transactions.append(Transaction(
                    txid=tx_row[0],
                    inputs=json.loads(tx_row[1]) if isinstance(tx_row[1], str) else (tx_row[1] or []),
                    outputs=json.loads(tx_row[2]) if isinstance(tx_row[2], str) else (tx_row[2] or []),
                    fee=Decimal(str(tx_row[3] or 0)),
                    signature=tx_row[4] or '',
                    public_key=tx_row[5] or '',
                    timestamp=float(tx_row[6] or 0),
                    block_height=tx_row[7],
                    status=tx_row[8] or 'confirmed'
                ))
            # Column order: height(0), prev_hash(1), difficulty(2),
            #               proof_json(3), created_at(4), block_hash(5)
            return Block(
                height=result[0],
                prev_hash=result[1],
                difficulty=float(result[2] or Config.INITIAL_DIFFICULTY),
                proof_data=json.loads(result[3]) if isinstance(result[3], str) else (result[3] or {}),
                timestamp=float(result[4] or 0),
                transactions=transactions,
                block_hash=result[5]
            )
    def store_block(self, block: Block):
        """Store block and update UTXOs atomically"""
        with self.get_session() as session:
            # Check for existing (prevent dups, per multi-node sync)
            existing = session.execute(
                text("SELECT 1 FROM blocks WHERE height = :h"),
                {'h': block.height}
            ).first()
            if existing:
                logger.warning(f"Block {block.height} already exists - skipping (possible dup from P2P)")
                return  # Or trigger reorg if longer chain
            # Insert block
            session.execute(
                text("""
                    INSERT INTO blocks (height, prev_hash, proof_json, difficulty, created_at, block_hash)
                    VALUES (:h, :ph, CAST(:pj AS jsonb), :d, :ts, :bh)
                """),
                {
                    'h': block.height,
                    'ph': block.prev_hash,
                    'pj': json.dumps(block.proof_data),
                    'd': block.difficulty,
                    'ts': block.timestamp,
                    'bh': block.block_hash or block.calculate_hash()
                }
            )
            # Process transactions
            for tx in block.transactions:
                # Mark inputs spent (skip coinbase)
                if tx.inputs:
                    self.mark_utxos_spent(tx.inputs, tx.txid, session)
                # Create outputs
                self.create_utxos(tx.txid, tx.outputs, block.height, block.proof_data, session)
                # Update transaction status
                session.execute(
                    text("""
                        UPDATE transactions
                        SET status = 'confirmed', block_height = :bh
                        WHERE txid = :txid
                    """),
                    {'bh': block.height, 'txid': tx.txid}
                )
            session.commit()
    # ========================================================================
    # TRANSACTION OPERATIONS
    # ========================================================================
    def get_pending_transactions(self, limit: int = 1000) -> List[Transaction]:
        """Get pending transactions"""
        with self.get_session() as session:
            results = session.execute(
                text("""
                    SELECT txid, inputs, outputs, fee, signature,
                           public_key, timestamp, block_height, status
                    FROM transactions
                    WHERE status = 'pending'
                    ORDER BY CAST(fee AS DECIMAL) DESC
                    LIMIT :limit
                """),
                {'limit': limit}
            )
            transactions = []
            for row in results:
                transactions.append(Transaction(
                    txid=row[0],
                    inputs=json.loads(row[1]) if isinstance(row[1], str) else (row[1] or []),
                    outputs=json.loads(row[2]) if isinstance(row[2], str) else (row[2] or []),
                    fee=Decimal(str(row[3] or 0)),
                    signature=row[4] or '',
                    public_key=row[5] or '',
                    timestamp=float(row[6] or 0),
                    block_height=row[7],
                    status=row[8] or 'pending'
                ))
            return transactions
    # ========================================================================
    # SUPPLY & ECONOMICS
    # ========================================================================
    def get_total_supply(self) -> Decimal:
        """Get total minted supply"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT total_minted FROM supply WHERE id = 1")
            )
            return Decimal(result.scalar() or 0)
    def update_supply(self, amount: Decimal, session: DBSession):
        """Update total supply"""
        session.execute(
            text("UPDATE supply SET total_minted = total_minted + :amt WHERE id = 1"),
            {'amt': str(amount)}
        )
    # ========================================================================
    # RESEARCH DATA
    # ========================================================================
    def store_hamiltonian(self, hamiltonian: list, params: list, energy: float,
                         miner_address: str, block_height: int, session: DBSession):
        """Store solved Hamiltonian for research"""
        session.execute(
            text("""
                INSERT INTO solved_hamiltonians
                (hamiltonian, params, energy, miner_address, block_height)
                VALUES (CAST(:h AS jsonb), CAST(:p AS jsonb), :e, :a, :bh)
            """),
            {
                'h': json.dumps(hamiltonian),
                'p': json.dumps(params),
                'e': energy,
                'a': miner_address,
                'bh': block_height
            }
        )
