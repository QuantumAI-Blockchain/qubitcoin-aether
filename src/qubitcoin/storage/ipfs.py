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

                # Get blocks - use raw SQL for simplicity
                blocks_result = session.execute(
                    text("SELECT height, prev_hash, proof_json, difficulty, created_at, block_hash FROM blocks ORDER BY height")
                ).fetchall()

                # Convert to list of dicts manually
                blocks = []
                for row in blocks_result:
                    blocks.append({
                        'height': row[0],
                        'prev_hash': row[1],
                        'proof_json': row[2] if isinstance(row[2], dict) else json.loads(row[2]) if row[2] else {},
                        'difficulty': float(row[3]),
                        'created_at': row[4].isoformat() if hasattr(row[4], 'isoformat') else str(row[4]),
                        'block_hash': row[5]
                    })

                # Get UTXOs
                utxos_result = session.execute(
                    text("SELECT txid, vout, amount, address, proof, block_height, spent FROM utxos WHERE spent = false")
                ).fetchall()

                utxos = []
                for row in utxos_result:
                    utxos.append({
                        'txid': row[0],
                        'vout': row[1],
                        'amount': str(row[2]),
                        'address': row[3],
                        'proof': row[4] if isinstance(row[4], dict) else json.loads(row[4]) if row[4] else {},
                        'block_height': row[5],
                        'spent': row[6]
                    })

                # Get confirmed transactions
                txs_result = session.execute(
                    text("SELECT txid, inputs, outputs, fee, signature, public_key, timestamp, status, block_height FROM transactions WHERE status = 'confirmed'")
                ).fetchall()

                transactions = []
                for row in txs_result:
                    transactions.append({
                        'txid': row[0],
                        'inputs': row[1] if isinstance(row[1], list) else json.loads(row[1]) if row[1] else [],
                        'outputs': row[2] if isinstance(row[2], list) else json.loads(row[2]) if row[2] else [],
                        'fee': str(row[3]),
                        'signature': row[4],
                        'public_key': row[5],
                        'timestamp': float(row[6]),
                        'status': row[7],
                        'block_height': row[8]
                    })

                # Get chain hash
                chain_hash = None
                if height >= 0:
                    block = db_manager.get_block(height)
                    if block:
                        chain_hash = block.block_hash

                # Create snapshot object
                snapshot = {
                    'version': '1.0',
                    'timestamp': time.time(),
                    'height': height,
                    'blocks': blocks,
                    'utxos': utxos,
                    'transactions': transactions,
                    'chain_hash': chain_hash
                }

            # Upload to IPFS
            logger.info(f"Uploading snapshot to IPFS (blocks: {len(blocks)}, utxos: {len(utxos)}, txs: {len(transactions)})...")
            cid = self.client.add_json(snapshot)

            logger.info(f"✓ Snapshot created: {cid}")

            # Pin if Pinata configured
            if Config.PINATA_JWT:
                self._pin_to_pinata(cid)

            # Store in database
            self._store_snapshot_record(db_manager, cid, height, chain_hash)

            return cid

        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}", exc_info=True)
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

    # ── Periodic snapshot scheduling ────────────────────────────────
    SNAPSHOT_INTERVAL: int = 1000  # blocks between automatic snapshots

    def should_snapshot(self, current_height: int) -> bool:
        """Return True if a periodic snapshot is due at *current_height*.

        Snapshots are triggered every ``SNAPSHOT_INTERVAL`` blocks (default
        1000).  Callers (typically the mining loop) invoke this after each
        new block is committed and, if True, call ``create_snapshot()``.
        """
        if current_height <= 0:
            return False
        return current_height % self.SNAPSHOT_INTERVAL == 0

    def maybe_snapshot(self, db_manager, current_height: int) -> Optional[str]:
        """Convenience: create a snapshot only when the interval is met.

        Returns:
            The IPFS CID if a snapshot was created, else None.
        """
        if not self.should_snapshot(current_height):
            return None
        return self.create_snapshot(db_manager, current_height)
