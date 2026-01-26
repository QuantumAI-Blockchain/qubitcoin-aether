"""
Database manager for CockroachDB
Handles all database operations with proper compatibility
"""

import json
import threading
from decimal import Decimal
from typing import List, Optional
import psycopg2.extras

from sqlalchemy import create_engine, text, event
from sqlalchemy.orm import sessionmaker, Session as DBSession
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
            execution_options={"isolation_level": "AUTOCOMMIT"},
            pool_size=Config.DB_POOL_SIZE,
            max_overflow=Config.DB_MAX_OVERFLOW,
            pool_timeout=Config.DB_POOL_TIMEOUT
        )
    
    def _test_connection(self):
        """Test database connection"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info("✓ Database connection established")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    def get_session(self) -> DBSession:
        """Get database session"""
        return self.SessionLocal()
    
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
                text("SELECT * FROM blocks WHERE height = :h"),
                {'h': height}
            ).fetchone()
            
            if not result:
                return None
            
            # Get transactions
            tx_results = session.execute(
                text("SELECT * FROM transactions WHERE block_height = :h"),
                {'h': height}
            )
            
            transactions = []
            for tx_row in tx_results:
                transactions.append(Transaction(
                    txid=tx_row[0],
                    inputs=json.loads(tx_row[1]) if isinstance(tx_row[1], str) else tx_row[1],
                    outputs=json.loads(tx_row[2]) if isinstance(tx_row[2], str) else tx_row[2],
                    fee=Decimal(tx_row[3]),
                    signature=tx_row[4],
                    public_key=tx_row[5],
                    timestamp=tx_row[6],
                    status=tx_row[7],
                    block_height=height
                ))
            
            return Block(
                height=result[0],
                prev_hash=result[1],
                proof_data=json.loads(result[2]) if isinstance(result[2], str) else result[2],
                transactions=transactions,
                timestamp=result[4].timestamp() if hasattr(result[4], 'timestamp') else result[4],
                difficulty=result[3],
                block_hash=result[5] if len(result) > 5 else None
            )
    
    def store_block(self, block: Block):
        """Store block and update UTXOs atomically"""
        with self.get_session() as session:
            # Insert block - FIXED: Use CAST instead of :: for parameter binding
            session.execute(
                text("""
                    INSERT INTO blocks (height, prev_hash, proof_json, difficulty, created_at, block_hash)
                    VALUES (:h, :ph, CAST(:pj AS jsonb), :d, to_timestamp(:ts), :bh)
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
                    SELECT * FROM transactions 
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
                    inputs=json.loads(row[1]) if isinstance(row[1], str) else row[1],
                    outputs=json.loads(row[2]) if isinstance(row[2], str) else row[2],
                    fee=Decimal(row[3]),
                    signature=row[4],
                    public_key=row[5],
                    timestamp=row[6],
                    status=row[7]
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
