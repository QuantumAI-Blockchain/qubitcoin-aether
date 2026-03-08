"""
Chain Synchronization Module

Fetches missing blocks from a peer node's REST API to catch up
when the local chain is behind. Supports:
- Batch fetching with configurable concurrency
- Sequential validation and storage
- Auto-detection of sync need from P2P block heights
- Progress logging
- Fork detection and chain reorganization (rollback + resync)
- Maximum reorg depth protection against 51% attacks
- Checkpoint finality for deep blocks
"""

import asyncio
import time
from typing import Optional, Callable

import httpx

from qubitcoin.database.models import Block, Transaction
from qubitcoin.utils.logger import get_logger

logger = get_logger(__name__)

# Maximum blocks to fetch in a single sync batch (used for pre-fetching)
SYNC_BATCH_SIZE = 50
# Maximum concurrent HTTP requests (used for pre-fetching)
SYNC_CONCURRENCY = 10
# Minimum height gap to trigger auto-sync
AUTO_SYNC_THRESHOLD = 2
# Max retries per block fetch before giving up
SYNC_FETCH_RETRIES = 3
# Delay between fetch retries (seconds)
SYNC_RETRY_DELAY = 2.0
# Max consecutive fetch failures before stopping sync
SYNC_MAX_CONSECUTIVE_FAILURES = 5
# Maximum reorg depth — blocks deeper than this CANNOT be rolled back.
# Prevents 51% attacks from rewriting ancient history.
# ~5.5 hours of blocks at 3.3s/block = ~6000 blocks
MAX_REORG_DEPTH = 6000
# Checkpoint interval — every N blocks becomes a hard checkpoint
# once it's older than MAX_REORG_DEPTH. Checkpoints are immutable.
CHECKPOINT_INTERVAL = 1000


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
    """Synchronises the local chain from a peer node's REST API.

    Implements full chain reorganization:
    1. Detect fork — compare block hashes at same heights
    2. Find fork point — binary search for last common ancestor
    3. Validate reorg — check depth limits and checkpoint protection
    4. Rollback — remove local blocks above fork point
    5. Resync — fetch and store peer's blocks from fork point
    """

    def __init__(self, db_manager, consensus=None, aether=None, ipfs_manager=None,
                 mining_engine=None):
        self.db = db_manager
        self.consensus = consensus
        self.aether = aether
        self._ipfs_manager = ipfs_manager
        self._mining = mining_engine  # Optional: pause mining during sync
        self._syncing = False
        self._peer_url: Optional[str] = None
        self._sync_task: Optional[asyncio.Task] = None
        # Track known peer URLs discovered from env or P2P
        self._known_peers: list[str] = []
        # Hard checkpoints — heights that can NEVER be rolled back past
        self._checkpoints: dict[int, str] = {}  # height -> block_hash

    async def _get_peer_snapshot_cid(self) -> Optional[str]:
        """Fetch the latest snapshot CID from the sync peer, or fall back to env var."""
        import os
        # Try peer endpoint first
        if self._peer_url:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(f"{self._peer_url}/snapshots/latest")
                    if resp.status_code == 200:
                        data = resp.json()
                        if 'error' not in data:
                            cid = data.get('cid')
                            if cid:
                                logger.info(f"Chain sync: got snapshot CID from peer: {cid}")
                                return cid
                        else:
                            logger.debug(f"Chain sync: peer /snapshots/latest returned error: {data.get('error')}")
            except Exception as e:
                logger.debug(f"Chain sync: failed to fetch snapshot CID from peer: {e}")
        # Fall back to SNAPSHOT_CID env var
        env_cid = os.environ.get('SNAPSHOT_CID', '').strip()
        if env_cid:
            logger.info(f"Chain sync: using SNAPSHOT_CID from environment: {env_cid}")
            return env_cid
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

    def add_checkpoint(self, height: int, block_hash: str) -> None:
        """Add a hard checkpoint. Blocks at or below this height can NEVER be rolled back."""
        self._checkpoints[height] = block_hash
        logger.info(f"Chain sync: checkpoint added at height {height} ({block_hash[:16]}...)")

    # ── Fork Detection & Resolution ──────────────────────────────────────

    async def _get_peer_block_hash(self, height: int) -> Optional[str]:
        """Fetch a single block hash from the peer."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._peer_url}/block/{height}")
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get('block_hash', data.get('hash', ''))
        except Exception as e:
            logger.debug(f"Chain sync: failed to fetch block hash at {height}: {e}")
        return None

    def _get_local_block_hash(self, height: int) -> Optional[str]:
        """Get local block hash at a given height."""
        block = self.db.get_block(height)
        if block:
            return block.block_hash or block.calculate_hash()
        return None

    async def _find_fork_point(self, local_height: int, peer_height: int) -> int:
        """Binary search for the last common block between local and peer chains.

        Returns the height of the last block where local and peer agree.
        Returns -1 if even genesis differs (should not happen with same code).
        """
        low = 0
        high = min(local_height, peer_height)

        # Quick check: if tip matches, no fork
        local_hash = self._get_local_block_hash(high)
        peer_hash = await self._get_peer_block_hash(high)
        if local_hash and peer_hash and local_hash == peer_hash:
            return high

        # Quick check: genesis must match
        local_genesis = self._get_local_block_hash(0)
        peer_genesis = await self._get_peer_block_hash(0)
        if not local_genesis or not peer_genesis or local_genesis != peer_genesis:
            logger.error("Chain sync: GENESIS MISMATCH — chains are incompatible")
            return -1

        # Binary search for fork point
        logger.info(f"Chain sync: searching for fork point between heights 0 and {high}")
        while low < high:
            mid = (low + high + 1) // 2
            local_hash = self._get_local_block_hash(mid)
            peer_hash = await self._get_peer_block_hash(mid)

            if local_hash and peer_hash and local_hash == peer_hash:
                low = mid  # This height matches, fork is higher
            else:
                high = mid - 1  # This height differs, fork is lower

        logger.info(f"Chain sync: fork point found at height {low}")
        return low

    def _get_deepest_checkpoint(self) -> int:
        """Get the highest checkpoint height that protects blocks from rollback."""
        if not self._checkpoints:
            return -1
        return max(self._checkpoints.keys())

    def _validate_reorg(self, fork_point: int, local_height: int, peer_height: int) -> tuple[bool, str]:
        """Validate that a reorg is safe to perform.

        Checks:
        1. Reorg depth is within MAX_REORG_DEPTH
        2. Fork point is above all checkpoints
        3. Peer chain is actually longer (has more work)

        Returns:
            (is_valid, reason)
        """
        reorg_depth = local_height - fork_point

        # Check 1: Depth limit — prevents deep rewrite attacks
        if reorg_depth > MAX_REORG_DEPTH:
            return False, (
                f"Reorg depth {reorg_depth} exceeds MAX_REORG_DEPTH ({MAX_REORG_DEPTH}). "
                f"This looks like a 51% attack or incompatible chain. "
                f"Fork point: {fork_point}, local tip: {local_height}. "
                f"Manual intervention required."
            )

        # Check 2: Checkpoint protection — finalized blocks are immutable
        deepest_checkpoint = self._get_deepest_checkpoint()
        if fork_point < deepest_checkpoint:
            return False, (
                f"Fork point {fork_point} is below checkpoint at {deepest_checkpoint}. "
                f"Cannot roll back past checkpoints. This chain fork is rejected."
            )

        # Check 3: Peer must have a longer chain
        if peer_height <= local_height:
            return False, (
                f"Peer chain ({peer_height}) is not longer than local ({local_height}). "
                f"No reorg needed — local chain wins."
            )

        # Check 4: Peer's chain extension must be meaningful
        # (peer must have at least 2 more blocks than we'd lose)
        peer_extension = peer_height - fork_point
        local_orphans = local_height - fork_point
        if peer_extension <= local_orphans:
            return False, (
                f"Peer extension ({peer_extension} blocks) is not greater than "
                f"local orphans ({local_orphans} blocks). Not adopting shorter fork."
            )

        return True, "OK"

    async def _perform_reorg(
        self,
        fork_point: int,
        target_height: int,
        on_progress: Optional[Callable] = None,
    ) -> dict:
        """Perform a chain reorganization.

        1. Roll back local chain to fork_point
        2. Fetch and store peer's blocks from fork_point+1 to target_height
        """
        local_height = self.db.get_current_height()
        orphaned_blocks = local_height - fork_point

        logger.warning(
            f"CHAIN REORG: rolling back {orphaned_blocks} blocks "
            f"(height {local_height} → {fork_point}), "
            f"then syncing {target_height - fork_point} blocks from peer"
        )

        # Step 1: Rollback
        rollback_result = self.db.rollback_to_height(fork_point)
        logger.warning(
            f"CHAIN REORG: rollback complete — removed {rollback_result['blocks_removed']} blocks, "
            f"{rollback_result['txs_removed']} txs"
        )

        # Verify rollback worked
        new_height = self.db.get_current_height()
        if new_height != fork_point:
            return {
                "status": "error",
                "error": f"Rollback failed: expected height {fork_point}, got {new_height}",
                "rollback": rollback_result,
            }

        # Step 2: Sync from fork_point+1 to target_height
        sync_result = await self._sync_range(
            fork_point + 1, target_height, on_progress
        )

        return {
            "status": "reorg_complete",
            "fork_point": fork_point,
            "orphaned_blocks": orphaned_blocks,
            "rollback": rollback_result,
            "sync": sync_result,
        }

    async def _sync_range(
        self,
        start_height: int,
        end_height: int,
        on_progress: Optional[Callable] = None,
    ) -> dict:
        """Fetch and store blocks **sequentially** in a height range from the peer.

        Key reliability guarantees:
        - Blocks are fetched and stored ONE AT A TIME in ascending order
        - Each block is retried up to SYNC_FETCH_RETRIES times before giving up
        - On first failure that can't be retried, sync stops (no gaps in chain)
        - Progress is tracked by actual stored height, not batch pointer
        """
        start_time = time.time()
        synced = 0
        failed = 0
        skipped = 0
        gap = end_height - start_height + 1
        consecutive_failures = 0

        current = start_height
        while current <= end_height:
            # Fetch ONE block at a time with retries — no concurrent batches
            block = await self._fetch_block_with_retry(current)

            if block is None:
                consecutive_failures += 1
                if consecutive_failures >= SYNC_MAX_CONSECUTIVE_FAILURES:
                    logger.error(
                        f"Chain sync: {consecutive_failures} consecutive fetch failures "
                        f"at height {current}. Stopping sync."
                    )
                    failed += 1
                    break
                logger.warning(
                    f"Chain sync: failed to fetch block {current} "
                    f"(attempt {consecutive_failures}/{SYNC_MAX_CONSECUTIVE_FAILURES}), "
                    f"will retry on next sync cycle"
                )
                failed += 1
                break  # Stop — cannot leave gaps in chain

            consecutive_failures = 0

            try:
                # Validate block chain linkage
                prev_block = self.db.get_block(block.height - 1)
                if prev_block is None and block.height > 0:
                    logger.warning(
                        f"Chain sync: missing prev block {block.height - 1}, "
                        f"cannot validate block {block.height}. Stopping."
                    )
                    failed += 1
                    break  # Stop — chain is broken

                # Light validation — check prev_hash linkage
                if prev_block:
                    expected_prev = prev_block.block_hash or prev_block.calculate_hash()
                    if block.prev_hash != expected_prev:
                        logger.warning(
                            f"Chain sync: block {block.height} prev_hash mismatch "
                            f"(got {block.prev_hash[:16]}, expected {expected_prev[:16]}). "
                            f"Possible fork — stopping sync."
                        )
                        failed += 1
                        break  # Stop — fork detected mid-sync

                # Store the block
                self.db.store_block(block)
                synced += 1
                current += 1  # Only advance after successful store

                # Update supply tracking
                if block.transactions:
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

                # Process knowledge periodically
                if self.aether and synced % 100 == 0:
                    try:
                        self.aether.process_block_knowledge(block)
                    except Exception:
                        pass

            except Exception as e:
                if 'already exists' in str(e).lower() or 'uniqueviolation' in str(e).lower():
                    skipped += 1
                    current += 1  # Block exists — safe to advance
                else:
                    logger.error(f"Chain sync: failed to store block {block.height}: {e}")
                    failed += 1
                    break  # Stop — don't leave gaps

            # Progress logging every 10 blocks
            if synced > 0 and synced % 10 == 0 and gap > 0:
                progress = (current - start_height) / gap * 100
                elapsed = time.time() - start_time
                bps = synced / elapsed if elapsed > 0 else 0
                eta = (end_height - current) / bps if bps > 0 else 0
                logger.info(
                    f"Chain sync: {progress:.1f}% — block {current}/{end_height} "
                    f"({bps:.1f} blocks/s, ETA {eta:.0f}s)"
                )

            if on_progress:
                try:
                    on_progress(current, end_height)
                except Exception:
                    pass

        elapsed = time.time() - start_time
        return {
            "synced": synced,
            "failed": failed,
            "skipped": skipped,
            "from_height": start_height,
            "to_height": end_height,
            "last_synced": current - 1,
            "elapsed_seconds": round(elapsed, 1),
            "blocks_per_second": round(synced / elapsed, 1) if elapsed > 0 else 0,
        }

    # ── Main Sync Entry Point ────────────────────────────────────────────

    async def sync_from_peer(
        self,
        peer_url: str,
        target_height: Optional[int] = None,
        on_progress: Optional[Callable] = None,
    ) -> dict:
        """
        Fetch and store missing blocks from a peer. Handles forks automatically.

        Logic:
        1. If peer is behind us → do nothing
        2. If peer is ahead and chains agree → append new blocks
        3. If peer is ahead but chains diverged → find fork point, rollback, resync
        4. If genesis differs → reject (incompatible chain)
        5. If reorg too deep → reject (possible 51% attack)

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
        mining_was_running = False

        try:
            # Pause mining during sync to prevent fork creation
            if self._mining and hasattr(self._mining, 'is_mining') and self._mining.is_mining:
                mining_was_running = True
                logger.info("Chain sync: pausing mining during sync")
                self._mining.stop()

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
                # Check if we're on the same chain even though heights match
                if target_height == local_height:
                    local_hash = self._get_local_block_hash(local_height)
                    peer_hash = await self._get_peer_block_hash(target_height)
                    if local_hash and peer_hash and local_hash != peer_hash:
                        logger.warning(
                            f"Chain sync: same height ({local_height}) but different tip hashes! "
                            f"Fork detected."
                        )
                        # Fall through to fork detection below
                    else:
                        return {
                            "status": "up_to_date",
                            "local_height": local_height,
                            "peer_height": target_height,
                        }
                else:
                    return {
                        "status": "up_to_date",
                        "local_height": local_height,
                        "peer_height": target_height,
                    }

            # ── Genesis Check ────────────────────────────────────────
            if local_height >= 0:
                local_genesis_hash = self._get_local_block_hash(0)
                peer_genesis_hash = await self._get_peer_block_hash(0)
                if local_genesis_hash and peer_genesis_hash:
                    if local_genesis_hash != peer_genesis_hash:
                        logger.error(
                            f"Chain sync: GENESIS MISMATCH! "
                            f"local={local_genesis_hash[:16]}... "
                            f"peer={peer_genesis_hash[:16]}... "
                            f"These are incompatible chains."
                        )
                        return {
                            "status": "error",
                            "error": "Genesis block mismatch — incompatible chains",
                            "local_genesis": local_genesis_hash,
                            "peer_genesis": peer_genesis_hash,
                        }

            # ── Fork Detection ───────────────────────────────────────
            # Check if our tip matches the peer's block at our height.
            # If not, we've forked and need to find where.
            needs_reorg = False
            if local_height > 0:
                local_tip_hash = self._get_local_block_hash(local_height)
                peer_at_our_height = await self._get_peer_block_hash(local_height)

                if local_tip_hash and peer_at_our_height:
                    if local_tip_hash != peer_at_our_height:
                        needs_reorg = True
                        logger.warning(
                            f"Chain sync: FORK DETECTED at height {local_height}! "
                            f"local={local_tip_hash[:16]}... "
                            f"peer={peer_at_our_height[:16]}..."
                        )

            if needs_reorg:
                # Find fork point via binary search
                fork_point = await self._find_fork_point(local_height, target_height)

                if fork_point < 0:
                    return {
                        "status": "error",
                        "error": "Cannot find fork point — genesis mismatch",
                    }

                # Validate the reorg is safe
                valid, reason = self._validate_reorg(fork_point, local_height, target_height)
                if not valid:
                    logger.error(f"Chain sync: REORG REJECTED — {reason}")
                    return {
                        "status": "reorg_rejected",
                        "error": reason,
                        "fork_point": fork_point,
                        "local_height": local_height,
                        "peer_height": target_height,
                        "reorg_depth": local_height - fork_point,
                    }

                # Perform the reorg
                result = await self._perform_reorg(fork_point, target_height, on_progress)
                elapsed = time.time() - start_time
                result["elapsed_seconds"] = round(elapsed, 1)
                logger.info(f"Chain sync reorg complete: {result}")
                return result

            # ── No Fork — Simple Append ──────────────────────────────
            gap = target_height - local_height

            # Try IPFS snapshot restore first if gap is large (>500 blocks)
            if gap > 500:
                try:
                    snapshot_cid = await self._get_peer_snapshot_cid()
                    if snapshot_cid:
                        logger.info(f"Chain sync: large gap ({gap} blocks), trying IPFS snapshot restore (CID: {snapshot_cid})")
                        from ..storage.snapshot_scheduler import SnapshotScheduler
                        scheduler = SnapshotScheduler()
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

            sync_result = await self._sync_range(
                local_height + 1, target_height, on_progress
            )

            elapsed = time.time() - start_time
            result = {
                "status": "complete",
                **sync_result,
                "elapsed_seconds": round(elapsed, 1),
            }
            logger.info(f"Chain sync complete: {result}")
            return result

        except Exception as e:
            logger.error(f"Chain sync failed: {e}", exc_info=True)
            return {
                "status": "error",
                "error": str(e),
            }
        finally:
            self._syncing = False
            # Resume mining if it was running before sync
            if mining_was_running and self._mining:
                logger.info("Chain sync: resuming mining after sync")
                try:
                    self._mining.start()
                except Exception as e:
                    logger.error(f"Chain sync: failed to resume mining: {e}")

    async def _fetch_block_with_retry(self, height: int) -> Optional[Block]:
        """Fetch a single block from the peer with retries.

        Returns the Block or None if all retries exhausted.
        """
        for attempt in range(1, SYNC_FETCH_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(f"{self._peer_url}/block/{height}")
                    if resp.status_code == 200:
                        return _block_from_peer_dict(resp.json())
                    elif resp.status_code == 429:
                        # Rate limited — back off
                        delay = SYNC_RETRY_DELAY * attempt
                        logger.warning(
                            f"Chain sync: rate limited fetching block {height}, "
                            f"retry {attempt}/{SYNC_FETCH_RETRIES} in {delay}s"
                        )
                        await asyncio.sleep(delay)
                        continue
                    elif resp.status_code == 404:
                        logger.debug(f"Chain sync: block {height} not found on peer (404)")
                        return None  # Block doesn't exist — no point retrying
                    else:
                        logger.warning(
                            f"Chain sync: block {height} returned HTTP {resp.status_code}, "
                            f"retry {attempt}/{SYNC_FETCH_RETRIES}"
                        )
            except httpx.TimeoutException:
                delay = SYNC_RETRY_DELAY * attempt
                logger.warning(
                    f"Chain sync: timeout fetching block {height}, "
                    f"retry {attempt}/{SYNC_FETCH_RETRIES} in {delay}s"
                )
                await asyncio.sleep(delay)
            except Exception as e:
                logger.warning(
                    f"Chain sync: error fetching block {height}: {e}, "
                    f"retry {attempt}/{SYNC_FETCH_RETRIES}"
                )
                await asyncio.sleep(SYNC_RETRY_DELAY)

        logger.error(f"Chain sync: failed to fetch block {height} after {SYNC_FETCH_RETRIES} retries")
        return None

    async def _fetch_batch(self, heights: list[int]) -> list[Block]:
        """Fetch a batch of blocks concurrently from the peer.

        Note: _sync_range now uses _fetch_block_with_retry (sequential).
        This method is kept for bulk operations like IPFS gap-fill.
        """
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
        Handles both simple catch-up and fork reorganization.
        """
        if self._syncing:
            return

        local_height = self.db.get_current_height()
        gap = peer_block_height - local_height

        if gap < AUTO_SYNC_THRESHOLD:
            # Even if gap is small, check for fork at same height
            if gap <= 0:
                return
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

        # Run sync in background — this handles both append and reorg
        self._sync_task = asyncio.create_task(
            self.sync_from_peer(peer_url, target_height=peer_block_height)
        )
