"""
IPFS storage manager for blockchain snapshots
Handles snapshot creation, retrieval, and pinning
"""

import json
import time
from typing import Optional

import ipfshttpclient

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IPFSManager:
    """Manages IPFS operations for snapshots"""
    
    def __init__(self):
        """Initialize IPFS connection"""
        self.client = None
        self._connect()
    
    def _connect(self):
        """Connect to IPFS daemon"""
        try:
            self.client = ipfshttpclient.connect(Config.IPFS_API)
            
            # Test connection
            version = self.client.version()
            logger.info(f"✓ IPFS connected: {version['Version']}")
            
        except Exception as e:
            logger.warning(f"IPFS connection failed: {e}")
            logger.info("Node will run without IPFS snapshot support")
            self.client = None
    
    def create_snapshot(self, db_manager, height: int) -> Optional[str]:
        """
        Create and upload blockchain snapshot
        
        Args:
            db_manager: Database manager instance
            height: Current blockchain height
            
        Returns:
            IPFS CID or None if failed
        """
        if not self.client:
            logger.warning("IPFS not available, skipping snapshot")
            return None
        
        try:
            logger.info(f"Creating snapshot at height {height}")
            
            # Export blockchain state
            with db_manager.get_session() as session:
                from sqlalchemy import text
                
                # Get blocks
                blocks_result = session.execute(
                    text("SELECT * FROM blocks ORDER BY height")
                ).fetchall()
                
                # Get UTXOs
                utxos_result = session.execute(
                    text("SELECT * FROM utxos WHERE spent = false")
                ).fetchall()
                
                # Get confirmed transactions
                txs_result = session.execute(
                    text("SELECT * FROM transactions WHERE status = 'confirmed'")
                ).fetchall()
                
                # Create snapshot object
                snapshot = {
                    'version': '1.0',
                    'timestamp': time.time(),
                    'height': height,
                    'blocks': [dict(zip(row.keys(), row)) for row in blocks_result],
                    'utxos': [dict(zip(row.keys(), row)) for row in utxos_result],
                    'transactions': [dict(zip(row.keys(), row)) for row in txs_result],
                    'chain_hash': db_manager.get_block(height).calculate_hash() if height >= 0 else None
                }
            
            # Upload to IPFS
            cid = self.client.add_json(snapshot)
            
            logger.info(f"✓ Snapshot created: {cid}")
            
            # Pin if Pinata configured
            if Config.PINATA_JWT:
                self._pin_to_pinata(cid)
            
            # Store in database
            self._store_snapshot_record(db_manager, cid, height, snapshot['chain_hash'])
            
            return cid
            
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}")
            return None
    
    def retrieve_snapshot(self, cid: str) -> Optional[dict]:
        """
        Retrieve snapshot from IPFS
        
        Args:
            cid: IPFS content identifier
            
        Returns:
            Snapshot data or None
        """
        if not self.client:
            return None
        
        try:
            logger.info(f"Retrieving snapshot: {cid}")
            snapshot = self.client.get_json(cid)
            logger.info(f"✓ Snapshot retrieved (height: {snapshot['height']})")
            return snapshot
            
        except Exception as e:
            logger.error(f"Snapshot retrieval failed: {e}")
            return None
    
    def reconstruct_from_snapshot(self, db_manager, cid: str, 
                                  expected_hash: Optional[str] = None):
        """
        Reconstruct database from IPFS snapshot
        
        Args:
            db_manager: Database manager instance
            cid: IPFS content identifier
            expected_hash: Expected chain hash for verification
        """
        snapshot = self.retrieve_snapshot(cid)
        
        if not snapshot:
            raise ValueError("Failed to retrieve snapshot")
        
        # Verify chain hash if provided
        if expected_hash and snapshot.get('chain_hash') != expected_hash:
            raise ValueError(f"Chain hash mismatch: {snapshot['chain_hash']} != {expected_hash}")
        
        logger.info(f"Reconstructing from snapshot (height: {snapshot['height']})")
        
        with db_manager.get_session() as session:
            from sqlalchemy import text
            
            # Clear existing data (DANGEROUS - backup first!)
            logger.warning("Clearing existing blockchain data...")
            session.execute(text("TRUNCATE TABLE blocks CASCADE"))
            session.execute(text("TRUNCATE TABLE utxos CASCADE"))
            session.execute(text("TRUNCATE TABLE transactions CASCADE"))
            
            # Restore blocks
            for block_data in snapshot['blocks']:
                session.execute(
                    text("""
                        INSERT INTO blocks (height, prev_hash, proof_json, difficulty, created_at, block_hash)
                        VALUES (:height, :prev_hash, :proof_json, :difficulty, :created_at, :block_hash)
                    """),
                    block_data
                )
            
            # Restore UTXOs
            for utxo_data in snapshot['utxos']:
                session.execute(
                    text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, :vout, :amount, :address, :proof, :block_height, :spent)
                    """),
                    utxo_data
                )
            
            # Restore transactions
            for tx_data in snapshot['transactions']:
                session.execute(
                    text("""
                        INSERT INTO transactions 
                        (txid, inputs, outputs, fee, signature, public_key, timestamp, status, block_height)
                        VALUES (:txid, :inputs, :outputs, :fee, :signature, :public_key, :timestamp, :status, :block_height)
                    """),
                    tx_data
                )
            
            session.commit()
        
        logger.info(f"✓ Blockchain reconstructed from snapshot (height: {snapshot['height']})")
    
    def _pin_to_pinata(self, cid: str):
        """Pin CID to Pinata for persistence"""
        try:
            import requests
            
            response = requests.post(
                'https://api.pinata.cloud/pinning/pinByHash',
                json={'hashToPin': cid},
                headers={'Authorization': f'Bearer {Config.PINATA_JWT}'}
            )
            
            if response.status_code == 200:
                logger.info(f"✓ Pinned to Pinata: {cid}")
            else:
                logger.warning(f"Pinata pinning failed: {response.text}")
                
        except Exception as e:
            logger.error(f"Pinata pinning error: {e}")
    
    def _store_snapshot_record(self, db_manager, cid: str, height: int, chain_hash: str):
        """Store snapshot record in database"""
        try:
            with db_manager.get_session() as session:
                from sqlalchemy import text
                
                session.execute(
                    text("""
                        INSERT INTO ipfs_snapshots (cid, block_height, chain_hash, pinned, created_at)
                        VALUES (:cid, :height, :hash, :pinned, CURRENT_TIMESTAMP)
                    """),
                    {
                        'cid': cid,
                        'height': height,
                        'hash': chain_hash,
                        'pinned': Config.PINATA_JWT is not None
                    }
                )
                session.commit()
                
        except Exception as e:
            logger.error(f"Failed to store snapshot record: {e}")
