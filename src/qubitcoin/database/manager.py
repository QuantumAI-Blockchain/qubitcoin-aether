"""
Database manager for CockroachDB
Handles all database operations with proper compatibility
"""
import json
from contextlib import contextmanager
from decimal import Decimal
from typing import Generator, List, Optional
import psycopg2
import psycopg2.extras
from sqlalchemy import (
    create_engine, text, event, Column, String, BigInteger, Integer,
    Float, Numeric, Boolean, JSON, DateTime, Text, UniqueConstraint
)
from sqlalchemy.orm import sessionmaker, Session as DBSession, declarative_base
from .models import UTXO, Transaction, Block, Account, TransactionReceipt
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
    state_root = Column(String(64), default='')
    receipts_root = Column(String(64), default='')
    thought_proof = Column(JSON, nullable=True)

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
    tx_type = Column(String(20), default='transfer')
    to_address = Column(String, nullable=True)
    data = Column(Text, nullable=True)
    gas_limit = Column(BigInteger, default=0)
    gas_price = Column(Numeric, default=0)
    nonce = Column(BigInteger, default=0)

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
    qbc_txid = Column(String(64), nullable=False, unique=True)
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
    source_txhash = Column(String, nullable=False, unique=True)
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
    claimed = Column(Boolean, default=False)
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

# -----------------------------------------------------------
# QVM Account Model (EVM-compatible)
# -----------------------------------------------------------

class AccountModel(Base):
    __tablename__ = 'accounts'
    address = Column(String(42), primary_key=True)
    nonce = Column(BigInteger, default=0)
    balance = Column(Numeric(30, 8), default=0)
    code_hash = Column(String(64), default='')
    storage_root = Column(String(64), default='')
    bytecode = Column(Text, nullable=True)  # Hex-encoded contract bytecode

class ContractStorageModel(Base):
    __tablename__ = 'contract_storage'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contract_address = Column(String(42), nullable=False)
    storage_key = Column(String(64), nullable=False)
    storage_value = Column(String(64), nullable=False)
    block_height = Column(BigInteger)
    __table_args__ = (
        UniqueConstraint('contract_address', 'storage_key', name='uq_contract_storage'),
    )

class TransactionReceiptModel(Base):
    __tablename__ = 'transaction_receipts'
    txid = Column(String(64), primary_key=True)
    block_height = Column(BigInteger, nullable=False)
    block_hash = Column(String(64))
    tx_index = Column(Integer)
    from_address = Column(String(42))
    to_address = Column(String(42), nullable=True)
    contract_address = Column(String(42), nullable=True)
    gas_used = Column(BigInteger, default=0)
    gas_limit = Column(BigInteger, default=0)
    status = Column(Integer, default=1)  # 1=success, 0=revert
    return_data = Column(Text, default='')
    revert_reason = Column(Text, default='')
    state_root = Column(String(64), default='')
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class EventLogModel(Base):
    __tablename__ = 'event_logs'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    txid = Column(String(64), nullable=False)
    log_index = Column(Integer, nullable=False)
    contract_address = Column(String(42), nullable=False)
    topic0 = Column(String(64), nullable=True)
    topic1 = Column(String(64), nullable=True)
    topic2 = Column(String(64), nullable=True)
    topic3 = Column(String(64), nullable=True)
    data = Column(Text, default='')
    block_height = Column(BigInteger)

# -----------------------------------------------------------
# QVM Opcode Gas Table
# -----------------------------------------------------------

class OpcodeGasModel(Base):
    __tablename__ = 'opcode_gas'
    opcode = Column(Integer, primary_key=True)
    name = Column(String(20), nullable=False)
    gas_cost = Column(BigInteger, nullable=False)
    category = Column(String(20), default='arithmetic')

# -----------------------------------------------------------
# Aether Tree Tables
# -----------------------------------------------------------

class KnowledgeNodeModel(Base):
    __tablename__ = 'knowledge_nodes'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    node_type = Column(String(50), nullable=False)
    content_hash = Column(String(64), nullable=False)
    content = Column(JSON, nullable=False)
    confidence = Column(Float, default=0.5)
    source_block = Column(BigInteger)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class KnowledgeEdgeModel(Base):
    __tablename__ = 'knowledge_edges'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    from_node_id = Column(BigInteger, nullable=False)
    to_node_id = Column(BigInteger, nullable=False)
    edge_type = Column(String(50), nullable=False)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        UniqueConstraint('from_node_id', 'to_node_id', 'edge_type', name='uq_knowledge_edge'),
    )

class ReasoningOperationModel(Base):
    __tablename__ = 'reasoning_operations'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    operation_type = Column(String(30), nullable=False)  # deductive, inductive, abductive
    premise_nodes = Column(JSON)
    conclusion_node_id = Column(BigInteger, nullable=True)
    confidence = Column(Float, default=0.0)
    reasoning_chain = Column(JSON)
    block_height = Column(BigInteger)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class PhiMeasurementModel(Base):
    __tablename__ = 'phi_measurements'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    phi_value = Column(Float, nullable=False)
    phi_threshold = Column(Float, default=3.0)
    integration_score = Column(Float, default=0.0)
    differentiation_score = Column(Float, default=0.0)
    num_nodes = Column(BigInteger, default=0)
    num_edges = Column(BigInteger, default=0)
    block_height = Column(BigInteger)
    measured_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

class ConsciousnessEventModel(Base):
    __tablename__ = 'consciousness_events'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    phi_at_event = Column(Float)
    trigger_data = Column(JSON)
    is_verified = Column(Boolean, default=False)
    block_height = Column(BigInteger)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# Privacy Tables (Key Images for double-spend prevention)
# -----------------------------------------------------------

class KeyImageModel(Base):
    __tablename__ = 'key_images'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    key_image = Column(String(128), nullable=False, unique=True, index=True)
    txid = Column(String(64), nullable=False)
    block_height = Column(BigInteger, nullable=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))

# -----------------------------------------------------------
# Sephirot Staking Tables
# -----------------------------------------------------------

class SephirotStakeModel(Base):
    __tablename__ = 'sephirot_stakes'
    stake_id = Column(String(66), primary_key=True, server_default=text("gen_random_uuid()::STRING"))
    address = Column(String(64), nullable=False)
    node_id = Column(Integer, nullable=False)  # 0-9 (Keter through Malkuth)
    amount = Column(Numeric(20, 8), nullable=False)
    status = Column(String(20), default='active')  # active, unstaking, withdrawn
    staked_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    unstake_requested_at = Column(DateTime, nullable=True)
    rewards_earned = Column(Numeric(20, 8), default=0)
    rewards_claimed = Column(Numeric(20, 8), default=0)

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
        # Ensure supply row exists (atomic upsert to avoid race on concurrent init)
        with self.get_session() as session:
            session.execute(text(
                "INSERT INTO supply (id, total_minted) VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
            ))
            session.commit()
        # Seed default stablecoin params if empty (atomic upsert per row)
        with self.get_session() as session:
            defaults = [
                ('min_collateral_ratio', '1.5', 'decimal'),
                ('liquidation_ratio', '1.2', 'decimal'),
                ('stability_fee', '0.02', 'decimal'),
                ('emergency_shutdown', 'false', 'boolean'),
            ]
            for name, value, ptype in defaults:
                session.execute(
                    text("""INSERT INTO stablecoin_params (param_name, param_value, param_type)
                            VALUES (:n, :v, :t) ON CONFLICT (param_name) DO NOTHING"""),
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
    def get_session(self) -> Generator:
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
    def get_utxo(self, txid: str, vout: int) -> Optional[UTXO]:
        """Get a specific UTXO by txid and vout"""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT txid, vout, amount, address, proof, block_height, spent, spent_by
                    FROM utxos
                    WHERE txid = :txid AND vout = :vout
                """),
                {'txid': txid, 'vout': vout}
            ).fetchone()
            if not result:
                return None
            return UTXO(
                txid=result[0],
                vout=result[1],
                amount=Decimal(str(result[2])),
                address=result[3],
                proof=json.loads(result[4]) if isinstance(result[4], str) else (result[4] or {}),
                block_height=result[5],
                spent=result[6],
                spent_by=result[7]
            )

    def mark_utxos_spent(self, inputs: List[dict], txid: str, session: DBSession) -> None:
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
                     proof: dict, session: DBSession) -> None:
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
                        created_at, block_hash, state_root, receipts_root,
                        thought_proof
                        FROM blocks WHERE height = :h"""),
                {'h': height}
            ).fetchone()
            if not result:
                return None
            # Get transactions with all columns including QVM fields
            tx_results = session.execute(
                text("""SELECT txid, inputs, outputs, fee, signature,
                        public_key, timestamp, block_height, status,
                        tx_type, to_address, data, gas_limit, gas_price, nonce
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
                    status=tx_row[8] or 'confirmed',
                    tx_type=tx_row[9] or 'transfer',
                    to_address=tx_row[10],
                    data=tx_row[11],
                    gas_limit=tx_row[12] or 0,
                    gas_price=Decimal(str(tx_row[13] or 0)),
                    nonce=tx_row[14] or 0,
                ))
            # Column order: height(0), prev_hash(1), difficulty(2),
            #               proof_json(3), created_at(4), block_hash(5),
            #               state_root(6), receipts_root(7), thought_proof(8)
            return Block(
                height=result[0],
                prev_hash=result[1],
                difficulty=float(result[2] or Config.INITIAL_DIFFICULTY),
                proof_data=json.loads(result[3]) if isinstance(result[3], str) else (result[3] or {}),
                timestamp=float(result[4] or 0),
                transactions=transactions,
                block_hash=result[5],
                state_root=result[6] or '',
                receipts_root=result[7] or '',
                thought_proof=json.loads(result[8]) if isinstance(result[8], str) else result[8],
            )
    def store_block(self, block: Block, session: DBSession = None) -> None:
        """Store block and update UTXOs atomically.

        When session is provided, uses it without committing (caller commits).
        When session is None, creates its own session and commits.
        """
        if session is not None:
            self._store_block_impl(block, session)
        else:
            with self.get_session() as s:
                self._store_block_impl(block, s)
                s.commit()

    def _store_block_impl(self, block: Block, session: DBSession):
        """Internal: store block in provided session without committing"""
        # Check for existing (prevent dups, per multi-node sync)
        existing = session.execute(
            text("SELECT 1 FROM blocks WHERE height = :h"),
            {'h': block.height}
        ).first()
        if existing:
            logger.warning(f"Block {block.height} already exists - skipping (possible dup from P2P)")
            return
        # Insert block
        session.execute(
            text("""
                INSERT INTO blocks (height, prev_hash, proof_json, difficulty, created_at, block_hash,
                                   state_root, receipts_root, thought_proof)
                VALUES (:h, :ph, CAST(:pj AS jsonb), :d, :ts, :bh, :sr, :rr, CAST(:tp AS jsonb))
            """),
            {
                'h': block.height,
                'ph': block.prev_hash,
                'pj': json.dumps(block.proof_data),
                'd': block.difficulty,
                'ts': block.timestamp,
                'bh': block.block_hash or block.calculate_hash(),
                'sr': block.state_root or '',
                'rr': block.receipts_root or '',
                'tp': json.dumps(block.thought_proof) if block.thought_proof else None
            }
        )
        # Process transactions
        for tx in block.transactions:
            # Mark inputs spent (skip coinbase)
            if tx.inputs:
                self.mark_utxos_spent(tx.inputs, tx.txid, session)
            # Create outputs
            self.create_utxos(tx.txid, tx.outputs, block.height, block.proof_data, session)
            # Upsert transaction (INSERT if new, UPDATE if already pending)
            session.execute(
                text("""
                    INSERT INTO transactions
                    (txid, inputs, outputs, fee, signature, public_key, timestamp,
                     block_height, status, tx_type, to_address, data, gas_limit, gas_price, nonce)
                    VALUES (:txid, CAST(:inputs AS jsonb), CAST(:outputs AS jsonb),
                            :fee, :sig, :pk, :ts, :bh, 'confirmed',
                            :tx_type, :to_addr, :data, :gas_limit, :gas_price, :nonce)
                    ON CONFLICT (txid) DO UPDATE SET
                        status = 'confirmed', block_height = :bh
                """),
                {
                    'txid': tx.txid,
                    'inputs': json.dumps(tx.inputs),
                    'outputs': json.dumps([
                        {'address': o['address'], 'amount': str(o['amount'])}
                        for o in tx.outputs
                    ]),
                    'fee': str(tx.fee),
                    'sig': tx.signature,
                    'pk': tx.public_key,
                    'ts': tx.timestamp,
                    'bh': block.height,
                    'tx_type': tx.tx_type or 'transfer',
                    'to_addr': tx.to_address,
                    'data': tx.data,
                    'gas_limit': tx.gas_limit or 0,
                    'gas_price': str(tx.gas_price or 0),
                    'nonce': tx.nonce or 0,
                }
            )
    # ========================================================================
    # TRANSACTION OPERATIONS
    # ========================================================================
    def get_pending_transactions(self, limit: int = 1000) -> List[Transaction]:
        """Get pending transactions with all fields including QVM columns"""
        with self.get_session() as session:
            results = session.execute(
                text("""
                    SELECT txid, inputs, outputs, fee, signature,
                           public_key, timestamp, block_height, status,
                           tx_type, to_address, data, gas_limit, gas_price, nonce
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
                    status=row[8] or 'pending',
                    tx_type=row[9] or 'transfer',
                    to_address=row[10],
                    data=row[11],
                    gas_limit=row[12] or 0,
                    gas_price=Decimal(str(row[13] or 0)),
                    nonce=row[14] or 0,
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
    def update_supply(self, amount: Decimal, session: DBSession) -> None:
        """Update total supply"""
        session.execute(
            text("UPDATE supply SET total_minted = total_minted + :amt WHERE id = 1"),
            {'amt': str(amount)}
        )
    # ========================================================================
    # UTXO MAINTENANCE
    # ========================================================================
    def compute_utxo_commitment(self) -> str:
        """Compute a SHA-256 commitment over the entire unspent UTXO set.

        This provides a compact hash that uniquely represents the current state
        of all unspent outputs. Can be included in block headers for lightweight
        UTXO set verification.

        Returns:
            Hex-encoded SHA-256 hash of the sorted UTXO set.
        """
        import hashlib
        with self.get_session() as session:
            results = session.execute(
                text("""
                    SELECT txid, vout, amount, address
                    FROM utxos
                    WHERE spent = false
                    ORDER BY txid, vout
                """)
            )
            hasher = hashlib.sha256()
            count = 0
            for row in results:
                entry = f"{row[0]}:{row[1]}:{row[2]}:{row[3]}"
                hasher.update(entry.encode())
                count += 1
            commitment = hasher.hexdigest()
            logger.debug(f"UTXO commitment computed over {count} UTXOs: {commitment[:16]}...")
            return commitment

    def get_utxo_stats(self) -> dict:
        """Get UTXO set statistics."""
        with self.get_session() as session:
            unspent = session.execute(
                text("SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM utxos WHERE spent = false")
            ).fetchone()
            spent = session.execute(
                text("SELECT COUNT(*) FROM utxos WHERE spent = true")
            ).fetchone()
            return {
                'unspent_count': unspent[0] if unspent else 0,
                'unspent_total': float(unspent[1]) if unspent else 0,
                'spent_count': spent[0] if spent else 0,
            }

    # ========================================================================
    # RESEARCH DATA
    # ========================================================================
    def store_hamiltonian(self, hamiltonian: list, params: list, energy: float,
                         miner_address: str, block_height: int, session: DBSession) -> None:
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

    # ========================================================================
    # QUERY HELPERS (used by node.py metrics)
    # ========================================================================
    def query_one(self, sql: str, params: dict = None) -> Optional[dict]:
        """Execute query and return first row as dict, or None"""
        try:
            with self.get_session() as session:
                result = session.execute(text(sql), params or {}).fetchone()
                if not result:
                    return None
                # Convert Row to dict
                if hasattr(result, '_mapping'):
                    return dict(result._mapping)
                # Fallback for tuple rows
                return {f'col_{i}': v for i, v in enumerate(result)}
        except Exception as e:
            logger.debug(f"query_one failed: {e}")
            return None

    # ========================================================================
    # ACCOUNT OPERATIONS (QVM)
    # ========================================================================
    def get_account(self, address: str) -> Optional[Account]:
        """Get account by address"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT address, nonce, balance, code_hash, storage_root FROM accounts WHERE address = :addr"),
                {'addr': address}
            ).fetchone()
            if not result:
                return None
            return Account(
                address=result[0],
                nonce=result[1],
                balance=Decimal(str(result[2])),
                code_hash=result[3] or '',
                storage_root=result[4] or ''
            )

    def get_or_create_account(self, address: str) -> Account:
        """Get account or create empty one (concurrent-safe)"""
        account = self.get_account(address)
        if account:
            return account
        with self.get_session() as session:
            session.execute(
                text("INSERT INTO accounts (address, nonce, balance, code_hash, storage_root) VALUES (:addr, 0, 0, '', '') ON CONFLICT (address) DO NOTHING"),
                {'addr': address}
            )
            session.commit()
        return self.get_account(address) or Account(address=address)

    def update_account(self, account: Account, session: DBSession = None) -> None:
        """Update account state"""
        def _do(s):
            s.execute(
                text("""
                    INSERT INTO accounts (address, nonce, balance, code_hash, storage_root, bytecode)
                    VALUES (:addr, :nonce, :balance, :code_hash, :storage_root, :bytecode)
                    ON CONFLICT (address) DO UPDATE SET
                        nonce = :nonce, balance = :balance,
                        code_hash = :code_hash, storage_root = :storage_root,
                        bytecode = COALESCE(EXCLUDED.bytecode, accounts.bytecode)
                """),
                {
                    'addr': account.address,
                    'nonce': account.nonce,
                    'balance': str(account.balance),
                    'code_hash': account.code_hash,
                    'storage_root': account.storage_root,
                    'bytecode': None
                }
            )
        if session:
            _do(session)
        else:
            with self.get_session() as s:
                _do(s)
                s.commit()

    def get_account_balance(self, address: str) -> Decimal:
        """Get account balance (QVM account model)"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT COALESCE(balance, 0) FROM accounts WHERE address = :addr"),
                {'addr': address}
            ).scalar()
            return Decimal(str(result)) if result else Decimal(0)

    # ========================================================================
    # CONTRACT STORAGE (QVM)
    # ========================================================================
    def get_storage(self, contract_address: str, key: str) -> str:
        """Get contract storage value"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT storage_value FROM contract_storage WHERE contract_address = :addr AND storage_key = :key"),
                {'addr': contract_address, 'key': key}
            ).scalar()
            return result or '0' * 64

    def set_storage(self, contract_address: str, key: str, value: str, block_height: int, session: DBSession = None) -> None:
        """Set contract storage value"""
        def _do(s):
            s.execute(
                text("""
                    INSERT INTO contract_storage (contract_address, storage_key, storage_value, block_height)
                    VALUES (:addr, :key, :val, :height)
                    ON CONFLICT (contract_address, storage_key) DO UPDATE SET
                        storage_value = :val, block_height = :height
                """),
                {'addr': contract_address, 'key': key, 'val': value, 'height': block_height}
            )
        if session:
            _do(session)
        else:
            with self.get_session() as s:
                _do(s)
                s.commit()

    def get_contract_bytecode(self, address: str) -> Optional[str]:
        """Get contract bytecode by address"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT bytecode FROM accounts WHERE address = :addr AND code_hash != ''"),
                {'addr': address}
            ).scalar()
            return result

    # ========================================================================
    # TRANSACTION RECEIPTS
    # ========================================================================
    def store_receipt(self, receipt: TransactionReceipt, session: DBSession = None) -> None:
        """Store transaction receipt"""
        def _do(s):
            s.execute(
                text("""
                    INSERT INTO transaction_receipts
                    (txid, block_height, block_hash, tx_index, from_address, to_address,
                     contract_address, gas_used, gas_limit, status, return_data, revert_reason, state_root)
                    VALUES (:txid, :bh, :bhash, :idx, :from_addr, :to_addr,
                            :contract, :gas_used, :gas_limit, :status, :ret, :reason, :sr)
                """),
                {
                    'txid': receipt.txid, 'bh': receipt.block_height,
                    'bhash': receipt.block_hash, 'idx': receipt.tx_index,
                    'from_addr': receipt.from_address, 'to_addr': receipt.to_address,
                    'contract': receipt.contract_address,
                    'gas_used': receipt.gas_used, 'gas_limit': receipt.gas_limit,
                    'status': receipt.status, 'ret': receipt.return_data,
                    'reason': receipt.revert_reason, 'sr': receipt.state_root
                }
            )
            # Store event logs
            for i, log in enumerate(receipt.logs):
                s.execute(
                    text("""
                        INSERT INTO event_logs
                        (txid, log_index, contract_address, topic0, topic1, topic2, topic3, data, block_height)
                        VALUES (:txid, :idx, :addr, :t0, :t1, :t2, :t3, :data, :bh)
                    """),
                    {
                        'txid': receipt.txid, 'idx': i,
                        'addr': log.get('address', ''),
                        't0': log.get('topic0'), 't1': log.get('topic1'),
                        't2': log.get('topic2'), 't3': log.get('topic3'),
                        'data': log.get('data', ''), 'bh': receipt.block_height
                    }
                )
        if session:
            _do(session)
        else:
            with self.get_session() as s:
                _do(s)
                s.commit()

    def get_receipt(self, txid: str) -> Optional[TransactionReceipt]:
        """Get transaction receipt"""
        with self.get_session() as session:
            row = session.execute(
                text("""SELECT txid, block_height, block_hash, tx_index, from_address, to_address,
                        contract_address, gas_used, gas_limit, status, return_data, revert_reason, state_root
                        FROM transaction_receipts WHERE txid = :txid"""),
                {'txid': txid}
            ).fetchone()
            if not row:
                return None
            # Get logs
            log_rows = session.execute(
                text("SELECT contract_address, topic0, topic1, topic2, topic3, data FROM event_logs WHERE txid = :txid ORDER BY log_index"),
                {'txid': txid}
            )
            logs = [
                {'address': r[0], 'topic0': r[1], 'topic1': r[2], 'topic2': r[3], 'topic3': r[4], 'data': r[5]}
                for r in log_rows
            ]
            return TransactionReceipt(
                txid=row[0], block_height=row[1], block_hash=row[2] or '',
                tx_index=row[3] or 0, from_address=row[4] or '',
                to_address=row[5], contract_address=row[6],
                gas_used=row[7] or 0, gas_limit=row[8] or 0,
                status=row[9] or 1, logs=logs,
                return_data=row[10] or '', revert_reason=row[11] or '',
                state_root=row[12] or ''
            )

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        """Get block by hash"""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT height FROM blocks WHERE block_hash = :bh"),
                {'bh': block_hash}
            ).fetchone()
            if not result:
                return None
            return self.get_block(result[0])

    # ========================================================================
    # ACCOUNT TRANSFERS (MetaMask / EVM-style)
    # ========================================================================
    def transfer_between_accounts(self, from_addr: str, to_addr: str,
                                  amount: Decimal) -> bool:
        """Atomic debit/credit between QVM accounts.

        Debits from_addr and credits to_addr in a single transaction.
        Creates the recipient account if it doesn't exist.

        Returns:
            True on success, raises on insufficient balance.
        """
        with self.get_session() as session:
            # Debit sender (fails if balance < amount)
            result = session.execute(
                text("""
                    UPDATE accounts SET balance = balance - :amt
                    WHERE address = :addr AND balance >= :amt
                """),
                {'addr': from_addr, 'amt': str(amount)}
            )
            if result.rowcount == 0:
                raise ValueError(f"Insufficient balance for {from_addr}")
            # Credit recipient (upsert)
            session.execute(
                text("""
                    INSERT INTO accounts (address, nonce, balance, code_hash, storage_root)
                    VALUES (:addr, 0, :amt, '', '')
                    ON CONFLICT (address) DO UPDATE SET balance = accounts.balance + :amt
                """),
                {'addr': to_addr, 'amt': str(amount)}
            )
            # Increment sender nonce
            session.execute(
                text("UPDATE accounts SET nonce = nonce + 1 WHERE address = :addr"),
                {'addr': from_addr}
            )
            session.commit()
            return True

    # ========================================================================
    # SEPHIROT STAKING
    # ========================================================================
    def create_stake(self, address: str, node_id: int, amount: Decimal) -> str:
        """Create a new Sephirot stake. Returns stake_id."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    INSERT INTO sephirot_stakes (address, node_id, amount, status)
                    VALUES (:addr, :nid, :amt, 'active')
                    RETURNING stake_id
                """),
                {'addr': address, 'nid': node_id, 'amt': str(amount)}
            )
            stake_id = result.scalar()
            session.commit()
            return stake_id

    def get_stakes_by_address(self, address: str) -> list:
        """Get all stakes for an address."""
        with self.get_session() as session:
            rows = session.execute(
                text("""
                    SELECT stake_id, address, node_id, amount, status,
                           staked_at, unstake_requested_at,
                           rewards_earned, rewards_claimed
                    FROM sephirot_stakes
                    WHERE address = :addr AND status != 'withdrawn'
                    ORDER BY staked_at DESC
                """),
                {'addr': address}
            ).fetchall()
            return [
                {
                    'stake_id': r[0], 'address': r[1], 'node_id': r[2],
                    'amount': str(r[3]), 'status': r[4],
                    'staked_at': str(r[5]) if r[5] else None,
                    'unstake_requested_at': str(r[6]) if r[6] else None,
                    'rewards_earned': str(r[7] or 0),
                    'rewards_claimed': str(r[8] or 0),
                }
                for r in rows
            ]

    def request_unstake(self, stake_id: str, address: str) -> bool:
        """Request unstaking (7-day delay). Returns True if found."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    UPDATE sephirot_stakes
                    SET status = 'unstaking', unstake_requested_at = CURRENT_TIMESTAMP
                    WHERE stake_id = :sid AND address = :addr AND status = 'active'
                """),
                {'sid': stake_id, 'addr': address}
            )
            session.commit()
            return result.rowcount > 0

    def get_sephirot_summary(self) -> dict:
        """Get aggregated staking summary for all 10 nodes."""
        with self.get_session() as session:
            rows = session.execute(
                text("""
                    SELECT node_id,
                           COUNT(*) AS staker_count,
                           COALESCE(SUM(amount), 0) AS total_staked
                    FROM sephirot_stakes
                    WHERE status = 'active'
                    GROUP BY node_id
                    ORDER BY node_id
                """)
            ).fetchall()
            summary = {}
            for r in rows:
                summary[r[0]] = {
                    'staker_count': r[1],
                    'total_staked': str(r[2]),
                }
            return summary

    def get_address_stake_on_node(self, address: str, node_id: int) -> Decimal:
        """Get total active stake for a specific address on a specific node."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM sephirot_stakes
                    WHERE address = :addr AND node_id = :nid AND status = 'active'
                """),
                {'addr': address, 'nid': node_id}
            ).scalar()
            return Decimal(str(result or 0))

    def get_node_total_stake(self, node_id: int) -> Decimal:
        """Get total active stake on a specific Sephirot node."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM sephirot_stakes
                    WHERE node_id = :nid AND status = 'active'
                """),
                {'nid': node_id}
            ).scalar()
            return Decimal(str(result or 0))

    def get_total_staked_all_nodes(self) -> Decimal:
        """Get total active stake across all 10 Sephirot nodes."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM sephirot_stakes
                    WHERE status = 'active'
                """)
            ).scalar()
            return Decimal(str(result or 0))

    def get_stake(self, stake_id: str) -> Optional[dict]:
        """Get a single stake by ID."""
        with self.get_session() as session:
            r = session.execute(
                text("""
                    SELECT stake_id, address, node_id, amount, status,
                           staked_at, unstake_requested_at,
                           rewards_earned, rewards_claimed
                    FROM sephirot_stakes WHERE stake_id = :sid
                """),
                {'sid': stake_id}
            ).fetchone()
            if not r:
                return None
            return {
                'stake_id': r[0], 'address': r[1], 'node_id': r[2],
                'amount': str(r[3]), 'status': r[4],
                'staked_at': str(r[5]) if r[5] else None,
                'unstake_requested_at': str(r[6]) if r[6] else None,
                'rewards_earned': str(r[7] or 0),
                'rewards_claimed': str(r[8] or 0),
            }

    def claim_rewards(self, address: str) -> Decimal:
        """Claim all pending rewards for an address. Returns amount claimed."""
        with self.get_session() as session:
            # Sum pending rewards
            result = session.execute(
                text("""
                    SELECT COALESCE(SUM(rewards_earned - rewards_claimed), 0)
                    FROM sephirot_stakes
                    WHERE address = :addr AND status = 'active'
                      AND rewards_earned > rewards_claimed
                """),
                {'addr': address}
            ).scalar()
            claimable = Decimal(str(result or 0))
            if claimable <= 0:
                return Decimal(0)
            # Mark claimed
            session.execute(
                text("""
                    UPDATE sephirot_stakes
                    SET rewards_claimed = rewards_earned
                    WHERE address = :addr AND status = 'active'
                      AND rewards_earned > rewards_claimed
                """),
                {'addr': address}
            )
            session.commit()
            return claimable

    def distribute_rewards(self, node_id: int, reward_amount: Decimal) -> None:
        """Distribute rewards pro-rata to all active stakers on a node."""
        with self.get_session() as session:
            # Get total staked on this node
            total = session.execute(
                text("""
                    SELECT COALESCE(SUM(amount), 0) FROM sephirot_stakes
                    WHERE node_id = :nid AND status = 'active'
                """),
                {'nid': node_id}
            ).scalar()
            total = Decimal(str(total or 0))
            if total <= 0:
                return
            # Pro-rata distribution
            session.execute(
                text("""
                    UPDATE sephirot_stakes
                    SET rewards_earned = rewards_earned + (:reward * amount / :total)
                    WHERE node_id = :nid AND status = 'active'
                """),
                {'reward': str(reward_amount), 'total': str(total), 'nid': node_id}
            )
            session.commit()

    def process_unstakes(self, block_height: int) -> int:
        """Process matured unstaking requests (7-day lock expired).

        Called once per block. Finds stakes where status='unstaking' and
        unstake_requested_at is older than 7 days, creates UTXOs to return
        the staked amount, and marks them as 'withdrawn'.

        Returns:
            Number of stakes withdrawn.
        """
        import hashlib
        import time as _time

        with self.get_session() as session:
            # Find matured unstakes (7 days = 168 hours)
            rows = session.execute(
                text("""
                    SELECT stake_id, address, amount, rewards_earned, rewards_claimed
                    FROM sephirot_stakes
                    WHERE status = 'unstaking'
                      AND unstake_requested_at <= CURRENT_TIMESTAMP - INTERVAL '7 days'
                """)
            ).fetchall()

            if not rows:
                return 0

            withdrawn = 0
            for r in rows:
                stake_id, address, amount, rewards_earned, rewards_claimed = r
                amount = Decimal(str(amount))
                unclaimed = Decimal(str(rewards_earned or 0)) - Decimal(str(rewards_claimed or 0))
                total_return = amount + unclaimed

                # Create UTXO returning staked amount + unclaimed rewards
                tx_hash = hashlib.sha256(
                    f"unstake:{stake_id}:{block_height}:{_time.time()}".encode()
                ).hexdigest()
                session.execute(
                    text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, 0, :amt, :addr, '{}', :h, false)
                    """),
                    {'txid': tx_hash, 'amt': str(total_return), 'addr': address, 'h': block_height}
                )

                # Mark stake as withdrawn
                session.execute(
                    text("""
                        UPDATE sephirot_stakes
                        SET status = 'withdrawn', rewards_claimed = rewards_earned
                        WHERE stake_id = :sid
                    """),
                    {'sid': stake_id}
                )
                withdrawn += 1
                logger.info(f"Unstake matured: {address[:8]} stake {stake_id[:8]} → {total_return} QBC returned")

            session.commit()
            return withdrawn
