"""
Chain Synchronization Module

Fetches missing blocks from a peer node's REST API to catch up
when the local chain is behind. Supports:
- Batch fetching with configurable concurrency
- Sequential validation and storage
- Auto-detection of sync need from P2P block heights
- Progress logging
"""

import asyncio
import time
from typing import Optional, Callable

import httpx

from qubitcoin.database.models import Block, Transaction
from qubitcoin.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum blocks to fetch in a single sync batch
SYNC_BATCH_SIZE = 50
# Maximum concurrent HTTP requests
SYNC_CONCURRENCY = 10
# Minimum height gap to trigger auto-sync
AUTO_SYNC_THRESHOLD = 2


def _block_from_peer_dict(data: dict) -> Block:
    """Reconstruct a Block object from a peer's /block/{height} JSON response."""
    txs = []
    for tx_data in data.get('transactions', []):
        if isinstance(tx_data, str):
            # Just a txid string — create minimal tx
            txs.append(Transaction(
                txid=tx_data,
                inputs=[],
                outputs=[],
                fee=0.0,
                signature='',
                public_key='',
                timestamp=data.get('timestamp', 0),
            ))
        elif isinstance(tx_data, dict):
            txs.append(Transaction(
                txid=tx_data.get('txid', ''),
                inputs=tx_data.get('inputs', []),
                outputs=tx_data.get('outputs', []),
                fee=tx_data.get('fee', 0.0),
                signature=tx_data.get('signature', ''),
                public_key=tx_data.get('public_key', ''),
                timestamp=tx_data.get('timestamp', 0),
                tx_type=tx_data.get('tx_type'),
                to_address=tx_data.get('to_address'),
                data=tx_data.get('data'),
                gas_limit=tx_data.get('gas_limit'),
                gas_price=tx_data.get('gas_price'),
                nonce=tx_data.get('nonce'),
            ))

    return Block(
        height=data['height'],
        prev_hash=data.get('prev_hash', data.get('previous_hash', '')),
        proof_data=data.get('proof_data', {}),
        transactions=txs,
        timestamp=data.get('timestamp', 0),
        difficulty=data.get('difficulty', data.get('difficulty_target', 0)),
        block_hash=data.get('block_hash', data.get('hash', '')),
        state_root=data.get('state_root', ''),
        receipts_root=data.get('receipts_root', ''),
        quantum_state_root=data.get('quantum_state_root', ''),
        thought_proof=data.get('thought_proof'),
    )


class ChainSync:
    """Synchronises the local chain from a peer node's REST API."""

    def __init__(self, db_manager, consensus=None, aether=None, ipfs_manager=None):
        self.db = db_manager
        self.consensus = consensus
        self.aether = aether
        self._ipfs_manager = ipfs_manager
        self._syncing = False
        self._peer_url: Optional[str] = None
        self._sync_task: Optional[asyncio.Task] = None
        # Track known peer URLs discovered from env or P2P
        self._known_peers: list[str] = []

    async def _get_peer_snapshot_cid(self) -> Optional[str]:
        """Fetch the latest snapshot CID from the sync peer."""
        if not self._peer_url:
            return None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._peer_url}/snapshots/latest")
                if resp.status_code == 200:
                    data = resp.json()
                    if 'error' not in data:
                        return data.get('cid')
        except Exception as e:
            logger.debug(f"Chain sync: failed to fetch snapshot CID from peer: {e}")
        return None

    @property
    def is_syncing(self) -> bool:
        return self._syncing

    def add_peer_url(self, url: str) -> None:
        """Register a peer RPC URL for future sync."""
        url = url.rstrip('/')
        if url not in self._known_peers:
            self._known_peers.append(url)
            logger.info(f"Chain sync: registered peer {url}")

    async def sync_from_peer(
        self,
        peer_url: str,
        target_height: Optional[int] = None,
        on_progress: Optional[Callable] = None,
    ) -> dict:
        """
        Fetch and store missing blocks from a peer.

        Args:
            peer_url: Base URL of the peer's RPC (e.g. http://152.42.215.182:5000)
            target_height: Sync up to this height (None = peer's tip)
            on_progress: Optional callback(current, target) for progress updates

        Returns:
            dict with sync stats
        """
        if self._syncing:
            return {"error": "Sync already in progress"}

        self._syncing = True
        self._peer_url = peer_url.rstrip('/')
        start_time = time.time()
        synced = 0
        failed = 0
        skipped = 0

        try:
            local_height = self.db.get_current_height()
            logger.info(f"Chain sync: local height={local_height}")

            # Get peer's tip height
            if target_height is None:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{self._peer_url}/chain/info")
                    resp.raise_for_status()
                    peer_info = resp.json()
                    target_height = peer_info.get('height', 0)

            if target_height <= local_height:
                logger.info(f"Chain sync: already at or ahead of peer (local={local_height}, peer={target_height})")
                return {
                    "status": "up_to_date",
                    "local_height": local_height,
                    "peer_height": target_height,
                }

            # If local chain is very short, verify genesis matches the peer.
            # If genesis hashes differ, wipe local chain and sync from block 0.
            if local_height >= 0:
                try:
                    local_genesis = self.db.get_block(0)
                    if local_genesis:
                        async with httpx.AsyncClient(timeout=10) as client:
                            resp = await client.get(f"{self._peer_url}/block/0")
                            if resp.status_code == 200:
                                peer_genesis = resp.json()
                                peer_genesis_hash = peer_genesis.get('block_hash', peer_genesis.get('hash', ''))
                                local_genesis_hash = local_genesis.block_hash or local_genesis.calculate_hash()
                                if peer_genesis_hash and local_genesis_hash != peer_genesis_hash:
                                    logger.warning(
                                        f"Chain sync: genesis mismatch! "
                                        f"local={local_genesis_hash[:16]}... "
                                        f"peer={peer_genesis_hash[:16]}... "
                                        f"Wiping local chain to sync from peer genesis."
                                    )
                                    # Wipe local blocks and start fresh
                                    try:
                                        self.db.wipe_chain()
                                        local_height = -1
                                        logger.info("Chain sync: local chain wiped, syncing from block 0")
                                    except Exception as wipe_err:
                                        # If wipe_chain doesn't exist, delete blocks manually
                                        logger.warning(f"Chain wipe not available ({wipe_err}), syncing from block 0 with overwrites")
                                        local_height = -1
                except Exception as e:
                    logger.debug(f"Chain sync: genesis check skipped: {e}")

            gap = target_height - local_height

            # Try IPFS snapshot restore first if gap is large (>500 blocks)
            if gap > 500:
                try:
                    snapshot_cid = await self._get_peer_snapshot_cid()
                    if snapshot_cid:
                        logger.info(f"Chain sync: large gap ({gap} blocks), trying IPFS snapshot restore (CID: {snapshot_cid})")
                        from ..storage.snapshot_scheduler import SnapshotScheduler
                        scheduler = SnapshotScheduler()
                        # ipfs_manager is on the node — get it from the db's engine context
                        ipfs_mgr = getattr(self, '_ipfs_manager', None)
                        if ipfs_mgr:
                            result = scheduler.restore_from_snapshot(
                                cid=snapshot_cid, db_manager=self.db, ipfs_manager=ipfs_mgr,
                            )
                            if result.get('success'):
                                restored_height = result.get('height', 0)
                                logger.info(
                                    f"Chain sync: IPFS snapshot restored to height {restored_height} "
                                    f"({result.get('blocks_restored', 0)} blocks, "
                                    f"{result.get('duration_s', 0)}s)"
                                )
                                local_height = self.db.get_current_height()
                                gap = target_height - local_height
                                if gap <= 0:
                                    return {
                                        "status": "synced_from_snapshot",
                                        "local_height": local_height,
                                        "peer_height": target_height,
                                        "snapshot_cid": snapshot_cid,
                                    }
                                logger.info(f"Chain sync: {gap} remaining blocks after snapshot, fetching via RPC")
                            else:
                                logger.warning(f"Chain sync: IPFS snapshot restore failed: {result.get('errors', [])}")
                        else:
                            logger.debug("Chain sync: no IPFS manager available, skipping snapshot restore")
                except Exception as e:
                    logger.warning(f"Chain sync: IPFS snapshot restore failed ({e}), falling back to block-by-block")

            logger.info(
                f"Chain sync: syncing {gap} blocks from {self._peer_url} "
                f"(local={local_height} → target={target_height})"
            )

            # Fetch and store in batches
            current = local_height + 1
            while current <= target_height:
                batch_end = min(current + SYNC_BATCH_SIZE - 1, target_height)
                batch_heights = list(range(current, batch_end + 1))

                # Fetch batch concurrently
                blocks = await self._fetch_batch(batch_heights)

                # Sort by height and store sequentially
                blocks.sort(key=lambda b: b.height)

                for block in blocks:
                    try:
                        # Validate block chain linkage
                        prev_block = self.db.get_block(block.height - 1)
                        if prev_block is None and block.height > 0:
                            logger.warning(
                                f"Chain sync: missing prev block {block.height - 1}, "
                                f"cannot validate block {block.height}"
                            )
                            failed += 1
                            continue

                        # Light validation — check prev_hash linkage
                        if prev_block:
                            expected_prev = prev_block.block_hash or prev_block.calculate_hash()
                            if block.prev_hash != expected_prev:
                                logger.warning(
                                    f"Chain sync: block {block.height} prev_hash mismatch "
                                    f"(got {block.prev_hash[:16]}, expected {expected_prev[:16]})"
                                )
                                failed += 1
                                continue

                        # Store the block
                        self.db.store_block(block)
                        synced += 1

                        # Update supply tracking
                        if block.transactions:
                            # Coinbase reward = first tx output value
                            coinbase = block.transactions[0]
                            if coinbase.outputs:
                                reward = sum(
                                    float(o.get('amount', 0)) if isinstance(o, dict) else float(getattr(o, 'amount', 0))
                                    for o in coinbase.outputs
                                )
                                from decimal import Decimal
                                with self.db.get_session() as session:
                                    self.db.update_supply(Decimal(str(reward)), session)
                                    session.commit()

                        # Process knowledge (lightweight — skips empty blocks now)
                        if self.aether and synced % 100 == 0:
                            try:
                                self.aether.process_block_knowledge(block)
                            except Exception:
                                pass

                    except Exception as e:
                        if 'already exists' in str(e).lower():
                            skipped += 1
                        else:
                            logger.error(f"Chain sync: failed to store block {block.height}: {e}")
                            failed += 1

                current = batch_end + 1

                # Progress logging
                progress = (current - local_height) / gap * 100
                elapsed = time.time() - start_time
                bps = synced / elapsed if elapsed > 0 else 0
                eta = (target_height - current) / bps if bps > 0 else 0
                logger.info(
                    f"Chain sync: {progress:.1f}% — block {current}/{target_height} "
                    f"({bps:.1f} blocks/s, ETA {eta:.0f}s)"
                )

                if on_progress:
                    try:
                        on_progress(current, target_height)
                    except Exception:
                        pass

            elapsed = time.time() - start_time
            result = {
                "status": "complete",
                "synced": synced,
                "failed": failed,
                "skipped": skipped,
                "from_height": local_height + 1,
                "to_height": target_height,
                "elapsed_seconds": round(elapsed, 1),
                "blocks_per_second": round(synced / elapsed, 1) if elapsed > 0 else 0,
            }
            logger.info(f"Chain sync complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Chain sync failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
                "synced": synced,
                "failed": failed,
            }
        finally:
            self._syncing = False

    async def _fetch_batch(self, heights: list[int]) -> list[Block]:
        """Fetch a batch of blocks concurrently from the peer."""
        sem = asyncio.Semaphore(SYNC_CONCURRENCY)
        blocks: list[Block] = []

        async def fetch_one(height: int) -> Optional[Block]:
            async with sem:
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(f"{self._peer_url}/block/{height}")
                        if resp.status_code == 200:
                            return _block_from_peer_dict(resp.json())
                        else:
                            logger.debug(f"Chain sync: block {height} not found on peer")
                            return None
                except Exception as e:
                    logger.debug(f"Chain sync: failed to fetch block {height}: {e}")
                    return None

        tasks = [fetch_one(h) for h in heights]
        results = await asyncio.gather(*tasks)
        for b in results:
            if b is not None:
                blocks.append(b)
        return blocks

    async def auto_sync_if_behind(self, peer_block_height: int) -> None:
        """
        Called when a P2P block is received that's ahead of our chain.
        Triggers sync if the gap is large enough and we have a known peer.
        """
        if self._syncing:
            return

        local_height = self.db.get_current_height()
        gap = peer_block_height - local_height

        if gap < AUTO_SYNC_THRESHOLD:
            return

        # Find a peer to sync from
        peer_url = None
        if self._known_peers:
            peer_url = self._known_peers[0]

        if not peer_url:
            logger.warning(
                f"Chain sync: {gap} blocks behind (local={local_height}, "
                f"peer={peer_block_height}) but no peer URL configured. "
                f"Set SYNC_PEER_URL env var or call POST /sync/start"
            )
            return

        logger.info(
            f"Chain sync: auto-syncing {gap} blocks from {peer_url} "
            f"(local={local_height} → {peer_block_height})"
        )

        # Run sync in background
        self._sync_task = asyncio.create_task(
            self.sync_from_peer(peer_url, target_height=peer_block_height)
        )
