"""
Mining engine for Proof-of-SUSY-Alignment
Handles block creation and mining loop with SUSY Economics
"""
import threading
import time
import hashlib
from decimal import Decimal
from ..config import Config
from ..database.models import Transaction, Block
from ..quantum.engine import QuantumEngine
from ..quantum.crypto import DilithiumSigner, _KEY_SIZES
from ..consensus.engine import ConsensusEngine
from ..utils.logger import get_logger
from ..utils.metrics import blocks_mined, mining_attempts, current_height_metric, vqe_optimization_time, total_fees_burned_metric

logger = get_logger(__name__)


class MiningEngine:
    """Manages mining operations"""

    def __init__(self, quantum_engine: QuantumEngine, consensus_engine: ConsensusEngine,
                 db_manager, console, state_manager=None, aether_engine=None,
                 substrate_bridge=None):
        """Initialize mining engine"""
        self.quantum = quantum_engine
        self.consensus = consensus_engine
        self.db = db_manager
        self.console = console
        self.state_manager = state_manager
        self.aether = aether_engine
        self.substrate_bridge = substrate_bridge
        self.node = None
        self.circulation_tracker = None  # Wired from node.py after RPC app creation
        # AIKGS reward outputs removed — rewards now disbursed as treasury
        # transactions by the Rust AIKGS sidecar (not in coinbase).
        self.is_mining = False
        self.mining_thread = None
        self._lock = threading.Lock()
        self._mining_start_time: float | None = None
        self._stop_event = threading.Event()
        self._abort_event = threading.Event()   # Signals: abandon current block
        self._sync_complete = threading.Event()  # Signals: initial sync finished
        self.stats = {
            'blocks_found': 0,
            'total_attempts': 0,
            'current_difficulty': Config.INITIAL_DIFFICULTY,
            'uptime': 0,
            'best_energy': None,
            'alignment_score': None,
            'total_burned': 0.0,
        }
        logger.info("Mining engine initialized (SUSY Economics + QVM)")

    def start(self) -> None:
        """Start mining (thread-safe)."""
        with self._lock:
            if self.is_mining:
                logger.warning("Mining already running")
                return
            self.is_mining = True
            self._stop_event.clear()
            self._mining_start_time = time.time()
            self.mining_thread = threading.Thread(
                target=self._mine_loop,
                daemon=True,
                name="MiningThread"
            )
            self.mining_thread.start()
            logger.info("Mining started")

    def stop(self) -> None:
        """Stop mining (thread-safe)."""
        with self._lock:
            if not self.is_mining:
                return
            self.is_mining = False
            self._stop_event.set()
            self._abort_event.set()  # Also unblock any VQE wait
        # Join outside the lock to avoid deadlock with mine loop
        if self.mining_thread:
            self.mining_thread.join(timeout=5)
        logger.info("Mining stopped")

    def abort_current_block(self) -> None:
        """Signal the mining thread to abandon its current block attempt.

        Called by the P2P handler when a peer block arrives at the same or
        next height, making the current VQE computation obsolete.  The
        ``_mine_block`` loop checks this event between VQE attempts and
        before expensive post-solution work (QVM, Aether).
        """
        self._abort_event.set()
        logger.debug("Mining abort signal sent — current block attempt will be abandoned")

    def set_sync_complete(self) -> None:
        """Signal that initial chain sync has finished and mining may begin."""
        self._sync_complete.set()
        logger.info("Mining sync gate opened — mining enabled")

    def get_stats_snapshot(self) -> dict:
        """Return a thread-safe copy of mining stats."""
        with self._lock:
            return dict(self.stats)

    def _mine_loop(self):
        """Main mining loop.

        Uses ``_stop_event`` for responsive shutdown instead of polling
        a bare boolean, preventing races between start/stop calls.
        """
        # ── Sync gate: block mining until initial chain sync completes ──
        # NO TIMEOUT — mining MUST NOT start until sync is explicitly
        # completed via set_sync_complete(). A timeout here caused nodes
        # to mine independent chains when sync was slow or peers were
        # unreachable. The gate is opened by node.py only after sync
        # succeeds or genesis validation passes.
        if not self._sync_complete.is_set():
            logger.info("Mining: waiting for initial sync to complete before mining...")
            while not self._sync_complete.is_set():
                if self._stop_event.is_set():
                    return
                self._sync_complete.wait(timeout=30)
                if not self._sync_complete.is_set():
                    logger.info("Mining: still waiting for sync gate (will NOT mine until sync completes)...")

        while not self._stop_event.is_set():
            try:
                if self._mining_start_time is not None:
                    with self._lock:
                        self.stats['uptime'] = int(time.time() - self._mining_start_time)
                self._mine_block()
            except Exception as e:
                # Broad catch is intentional: the mining loop must never crash
                # the node process.  Any unhandled exception (DB hiccup, numpy
                # error, transient quantum backend failure) is logged with full
                # traceback and mining retries after a cooldown interval.
                logger.error(f"Mining error: {e}", exc_info=True)
                # Use event-based wait instead of sleep for faster shutdown
                self._stop_event.wait(timeout=Config.MINING_INTERVAL)

    def _mine_block(self):
        """Attempt to mine a single block"""
        # Clear abort event at the start of each block attempt
        self._abort_event.clear()

        current_height = self.db.get_current_height()
        next_height = current_height + 1

        # ── GENESIS GUARD: Block 0 is NEVER mined via VQE ──────────────
        # Genesis is a fixed constant. Fresh nodes MUST sync from the
        # network instead of mining their own genesis. This prevents
        # independent chains from forming.
        if next_height == 0:
            if not Config.ALLOW_GENESIS_MINE:
                logger.error(
                    "GENESIS GUARD: Cannot mine block 0 — this node has no chain. "
                    "It must sync from an existing peer first. "
                    "Set SYNC_PEER_URL in .env and restart, or set "
                    "ALLOW_GENESIS_MINE=true if this is the very first node."
                )
                self._stop_event.wait(timeout=10)
                return
            else:
                logger.warning(
                    "ALLOW_GENESIS_MINE=true — creating canonical genesis block. "
                    "This should only happen for the FIRST node in the network."
                )
                self._create_canonical_genesis()
                return

        difficulty = self.consensus.calculate_difficulty(next_height, self.db)
        with self._lock:
            self.stats['current_difficulty'] = difficulty

        # Pre-check if height exists (from P2P sync)
        if self.db.get_block(next_height):
            logger.debug(f"Block {next_height} already exists from P2P, skipping")
            self._stop_event.wait(timeout=Config.MINING_INTERVAL)
            return

        prev_hash = self._get_prev_hash(current_height)
        pending_txs = self.db.get_pending_transactions(limit=100)

        # DETERMINISTIC: Derive Hamiltonian from chain state
        # Every miner gets the SAME puzzle for this (prev_hash, height)
        hamiltonian = self.quantum.generate_hamiltonian(
            prev_hash=prev_hash,
            height=next_height
        )

        logger.info(f"Mining block {next_height} (difficulty: {difficulty:.4f}, prev: {prev_hash[:12]}...)")

        # NONCE GRINDING: Try different random initial VQE params
        # until we find one that converges to energy < difficulty
        max_attempts = 50
        for attempt in range(max_attempts):
            if self._stop_event.is_set() or self._abort_event.is_set():
                return

            # Check if someone else found this block
            if self.db.get_block(next_height):
                logger.info(f"Block {next_height} found by peer during mining, stopping")
                return

            try:
                vqe_start = time.time()
                params, energy = self.quantum.optimize_vqe(hamiltonian)
                vqe_optimization_time.observe(time.time() - vqe_start)
            except Exception as e:
                logger.error(f"VQE optimization failed (attempt {attempt+1}): {e}")
                continue

            with self._lock:
                self.stats['total_attempts'] += 1
                # Track best energy and alignment score across all attempts
                if self.stats['best_energy'] is None or energy < self.stats['best_energy']:
                    self.stats['best_energy'] = float(energy)
                if difficulty != 0:
                    score = float(energy / difficulty)
                    if self.stats['alignment_score'] is None or score < self.stats['alignment_score']:
                        self.stats['alignment_score'] = score
            mining_attempts.inc()

            if energy < difficulty:
                logger.info(f"Solution found! energy={energy:.6f} < difficulty={difficulty:.6f} (attempt {attempt+1})")
                break

            logger.debug(f"Attempt {attempt+1}/{max_attempts}: energy {energy:.6f} >= difficulty {difficulty:.6f}")
        else:
            # All attempts exhausted
            logger.debug(f"No solution in {max_attempts} attempts, retrying next round")
            self._stop_event.wait(timeout=Config.MINING_INTERVAL)
            return

        # ── SUBSTRATE MODE: submit proof as extrinsic, skip local block creation ──
        if self.substrate_bridge:
            try:
                from ..substrate_codec import python_vqe_to_substrate
                vqe_proof = python_vqe_to_substrate(
                    params=params.tolist(),
                    energy=float(energy),
                    prev_hash=prev_hash,
                    n_qubits=4,
                )
                # Submit mining proof from sync thread via event loop
                import asyncio as _asyncio
                loop = _asyncio.new_event_loop()
                tx_hash = loop.run_until_complete(
                    self.substrate_bridge.submit_mining_proof(vqe_proof)
                )
                loop.close()
                if tx_hash:
                    with self._lock:
                        self.stats['blocks_found'] += 1
                    blocks_mined.inc()
                    logger.info(
                        f"Mining proof submitted to Substrate: "
                        f"energy={energy:.6f}, tx={tx_hash}"
                    )
                else:
                    logger.warning("Mining proof submission returned no hash")
            except Exception as e:
                logger.error(f"Substrate mining proof submission failed: {e}", exc_info=True)
            self._stop_event.wait(timeout=Config.MINING_INTERVAL)
            return

        # ── STANDALONE MODE: create block locally ──

        # ── Abort / duplicate check BEFORE expensive QVM + Aether work ──
        if self._abort_event.is_set():
            logger.info(f"Block {next_height} abandoned (abort signal after VQE solution)")
            return
        if self.db.get_block(next_height):
            logger.info(f"Block {next_height} appeared from peer after VQE, skipping")
            return

        # Build proof with chain binding
        proof_data = self._create_proof(hamiltonian, params, energy, prev_hash, next_height)
        # Read supply and calculate reward.  This is an initial read;
        # the value is verified atomically inside the storage lock below.
        total_supply = self.db.get_total_supply()
        reward = self.consensus.calculate_reward(next_height, total_supply)
        coinbase = self._create_coinbase(next_height, reward, pending_txs, prev_hash)

        block = Block(
            height=next_height,
            prev_hash=prev_hash,
            proof_data=proof_data,
            transactions=[coinbase] + pending_txs,
            timestamp=time.time(),
            difficulty=difficulty
        )

        # Execute QVM transactions and compute state/receipts roots
        if self.state_manager:
            try:
                state_root, receipts_root = self.state_manager.execute_block_transactions(block)
                block.state_root = state_root
                block.receipts_root = receipts_root
            except Exception as e:
                logger.error(f"QVM execution failed for block {next_height}: {e}", exc_info=True)

        # Generate Aether Tree thought proof
        if self.aether:
            try:
                pot = self.aether.generate_thought_proof(next_height, Config.ADDRESS)
                if pot:
                    block.thought_proof = pot.to_dict()
            except Exception as e:
                logger.debug(f"Thought proof generation skipped: {e}")

        block.block_hash = block.calculate_hash()

        valid, reason = self.consensus.validate_block(
            block, self.db.get_block(current_height), self.db, skip_qvm=True, skip_pot=True
        )
        if not valid:
            logger.error(f"Self-validation failed: {reason}")
            return

        # Store block, supply, and hamiltonian atomically in one session
        try:
            with self._lock:
                with self.db.get_session() as session:
                    # Check again under lock — prevents double-insert race
                    from sqlalchemy import text
                    existing = session.execute(
                        text("SELECT 1 FROM blocks WHERE height = :h"),
                        {'h': next_height}
                    ).first()
                    if existing:
                        logger.warning(f"Block {next_height} appeared during mining, skipping")
                        return

                    # ── Atomic supply verification ──
                    # Re-read supply INSIDE the lock to prevent the race
                    # where a peer block increments supply between our
                    # initial read and this store.
                    locked_supply = self.db.get_total_supply()
                    if locked_supply != total_supply:
                        logger.warning(
                            f"Supply changed during mining "
                            f"({total_supply} → {locked_supply}), recalculating reward"
                        )
                        reward = self.consensus.calculate_reward(next_height, locked_supply)
                        # Rebuild coinbase with corrected reward
                        coinbase = self._create_coinbase(next_height, reward, pending_txs, prev_hash)
                        block.transactions = [coinbase] + pending_txs
                        block.block_hash = block.calculate_hash()

                    self.db.store_block(block, session=session)
                    # AIKGS rewards are NOT new supply — they come from the
                    # pre-allocated reward pool (part of genesis premine).
                    # Only the mining reward and genesis premine are new supply.
                    supply_amount = reward + (Config.GENESIS_PREMINE if next_height == 0 else Decimal(0))
                    self.db.update_supply(supply_amount, session)
                    self.db.store_hamiltonian(
                        hamiltonian=hamiltonian,
                        params=params.tolist(),
                        energy=float(energy),
                        miner_address=Config.ADDRESS,
                        block_height=next_height,
                        session=session
                    )
                    session.commit()

                    # Update stats inside the same lock scope as block storage
                    # to prevent data races between mining and stats readers.
                    self.stats['blocks_found'] += 1

            blocks_mined.inc()
            current_height_metric.set(next_height)
            self._display_success(block, energy, reward)

            # Feed CirculationTracker with the new block
            if self.circulation_tracker is not None:
                try:
                    total_fees = sum(tx.fee for tx in pending_txs)
                    self.circulation_tracker.record_block(
                        block_height=next_height,
                        block_timestamp=block.timestamp,
                        fees_in_block=total_fees,
                    )
                except Exception as e:
                    logger.debug(f"Circulation tracking: {e}")

            # Process block knowledge for Aether Tree
            if self.aether:
                try:
                    self.aether.process_block_knowledge(block)
                except Exception as e:
                    logger.debug(f"Aether knowledge processing: {e}")

            # Higgs Cognitive Field per-block tick
            if self.node and getattr(self.node, 'higgs_field', None):
                try:
                    self.node.higgs_field.tick(next_height)
                except Exception as e:
                    logger.debug(f"Higgs field tick: {e}")

            # Higgs-aware SUSY enforcement (replaces flat rebalancing)
            if self.node and getattr(self.node, 'higgs_susy', None):
                try:
                    corrections = self.node.higgs_susy.enforce_susy_balance_with_mass(next_height)
                    if corrections > 0:
                        logger.debug(f"Higgs SUSY corrections: {corrections} at block {next_height}")
                except Exception as e:
                    logger.debug(f"Higgs SUSY enforcement: {e}")

            # Process matured Sephirot unstaking requests (7-day lock)
            try:
                withdrawn = self.db.process_unstakes(next_height)
                if withdrawn > 0:
                    logger.info(f"Processed {withdrawn} matured unstake(s) at block {next_height}")
            except Exception as e:
                logger.debug(f"Unstake processing: {e}")

            # Distribute staking rewards every N blocks
            if next_height % Config.SEPHIROT_REWARD_INTERVAL == 0:
                try:
                    self._distribute_staking_rewards(reward, next_height)
                except Exception as e:
                    logger.debug(f"Staking reward distribution: {e}")

            # Periodic DB maintenance
            if next_height % Config.PHI_DOWNSAMPLE_INTERVAL == 0 and self.aether:
                try:
                    self.aether.phi.downsample_phi_measurements()
                except Exception as e:
                    logger.debug(f"Phi downsample: {e}")

            if next_height % Config.PRUNE_INTERVAL_BLOCKS == 0 and self.aether:
                try:
                    kg = self.aether.kg
                    if kg:
                        pruned = kg.prune_low_confidence(Config.PRUNE_CONFIDENCE_THRESHOLD)
                        if pruned > 0:
                            kg.persist_confidence_updates()
                except Exception as e:
                    logger.debug(f"KG prune: {e}")

            # Broadcast mined block to P2P network via node (handles Rust/Python P2P)
            if self.node and hasattr(self.node, 'on_block_mined'):
                try:
                    self.node.on_block_mined(block.to_dict())
                except Exception as e:
                    logger.debug(f"Could not broadcast block: {e}")

        except Exception as e:
            logger.error(f"Failed to store block: {e}", exc_info=True)

        self._stop_event.wait(timeout=Config.MINING_INTERVAL)

    def _distribute_staking_rewards(self, block_reward: Decimal, block_height: int) -> None:
        """
        Distribute staking rewards to all 10 Sephirot nodes' stakers,
        weighted by each node's performance.

        Called every SEPHIROT_REWARD_INTERVAL blocks. Allocates a share of
        the accumulated block rewards. Active nodes earn more; idle nodes
        still get a baseline.
        """
        share_ratio = Decimal(str(Config.SEPHIROT_STAKER_SHARE_RATIO))
        interval = Config.SEPHIROT_REWARD_INTERVAL
        total_pool = block_reward * share_ratio * Decimal(str(interval))

        if total_pool <= 0:
            return

        # Collect performance weights from Sephirot nodes
        weights: dict = {}
        if self.aether and self.aether._sephirot:
            from ..aether.sephirot import SephirahRole
            for i, role in enumerate(SephirahRole):
                node = self.aether._sephirot.get(role)
                if node:
                    weights[i] = node.get_performance_weight()
                else:
                    weights[i] = 1.0
        else:
            # Fallback: equal weight
            for i in range(10):
                weights[i] = 1.0

        sum_weights = sum(weights.values())
        if sum_weights <= 0:
            sum_weights = 10.0

        distributed = 0
        for node_id in range(10):
            try:
                per_node = total_pool * Decimal(str(weights.get(node_id, 1.0))) / Decimal(str(sum_weights))
                if per_node > 0:
                    self.db.distribute_rewards(node_id, per_node)
                    distributed += 1
            except Exception as e:
                logger.debug(f"Reward distribution for node {node_id}: {e}")

        # Periodic stake-energy sync: update qbc_stake and energy from DB
        self._sync_all_stake_energy(block_height)

        if distributed > 0:
            logger.info(
                f"Distributed staking rewards at block {block_height}: "
                f"{total_pool:.4f} QBC (performance-weighted across {distributed} nodes)"
            )

    def _sync_all_stake_energy(self, block_height: int) -> None:
        """Read DB stake totals for all 10 nodes and update in-memory energy."""
        if not self.aether or not self.aether._sephirot:
            return
        try:
            import math
            from ..aether.sephirot import SephirahRole
            factor = Config.SEPHIROT_STAKE_ENERGY_FACTOR if hasattr(Config, 'SEPHIROT_STAKE_ENERGY_FACTOR') else 0.5
            for i, role in enumerate(SephirahRole):
                node = self.aether._sephirot.get(role)
                if not node:
                    continue
                total_stake = float(self.db.get_node_total_stake(i))
                node.state.qbc_stake = total_stake
                node.state.energy = 1.0 + factor * math.log2(1.0 + total_stake / 100.0)
        except Exception as e:
            logger.debug(f"Stake energy sync at block {block_height}: {e}")

    def _get_prev_hash(self, current_height: int) -> str:
        """Get previous block hash"""
        if current_height < 0:
            return '0' * 64
        prev_block = self.db.get_block(current_height)
        if prev_block and prev_block.block_hash:
            return prev_block.block_hash
        logger.error(f"Block {current_height} exists but has no stored hash!")
        return '0' * 64

    def _create_canonical_genesis(self) -> None:
        """Create the canonical genesis block (deterministic, not VQE-mined).

        The genesis block is a fixed constant — identical on every node.
        This prevents independent chains from forming when nodes start fresh.
        """
        import json as _json

        genesis_timestamp = Config.CANONICAL_GENESIS_TIMESTAMP
        prev_hash = '0' * 64
        proof_data = {
            'energy': 0.0,
            'hamiltonian': 'genesis',
            'type': 'genesis',
            'vqe_params': [],
        }

        # Fixed coinbase: premine + block reward to genesis_miner
        reward = Config.INITIAL_REWARD
        total_genesis = reward + Config.GENESIS_PREMINE
        coinbase = Transaction(
            txid=Config.CANONICAL_GENESIS_COINBASE_TXID,
            inputs=[],
            outputs=[{
                'address': 'genesis_miner',
                'amount': total_genesis,
            }],
            fee=Decimal(0),
            signature='genesis',
            public_key='genesis',
            timestamp=genesis_timestamp,
            block_height=0,
            status='confirmed',
            tx_type='coinbase',
        )

        block = Block(
            height=0,
            prev_hash=prev_hash,
            proof_data=proof_data,
            transactions=[coinbase],
            timestamp=genesis_timestamp,
            difficulty=1.0,
        )

        # Verify hash matches canonical
        computed_hash = block.calculate_hash()
        if computed_hash != Config.CANONICAL_GENESIS_HASH:
            logger.error(
                f"GENESIS HASH MISMATCH: computed={computed_hash} "
                f"expected={Config.CANONICAL_GENESIS_HASH}. "
                f"Genesis block definition has drifted from canonical."
            )
            # Store it anyway but warn — the droplet's stored hash is all-zeros
            # so we use the computed hash as the block_hash
            logger.warning("Proceeding with computed hash (droplet stores all-zeros for genesis)")

        block.block_hash = computed_hash
        block.cumulative_weight = 1.0

        # Store genesis block
        supply_amount = reward + Config.GENESIS_PREMINE
        self.db.store_block(block, supply_amount)

        with self._lock:
            self.stats['blocks_found'] += 1
        blocks_mined.inc()
        current_height.set(0)
        total_supply.set(float(supply_amount))

        logger.info(
            f"GENESIS BLOCK created: hash={computed_hash[:16]}... "
            f"(reward={reward} + premine={Config.GENESIS_PREMINE:,} QBC)"
        )

    def _create_proof(self, hamiltonian, params, energy,
                      prev_hash: str, height: int) -> dict:
        """Create quantum proof data with chain binding"""
        sk_bytes = bytes.fromhex(Config.PRIVATE_KEY_HEX)
        # Validate sk length against configured security level
        level = Config.get_security_level()
        expected_sk = _KEY_SIZES[level]['sk']
        if len(sk_bytes) != expected_sk:
            raise ValueError(
                f"Invalid Dilithium private key length: {len(sk_bytes)} bytes "
                f"(expected {expected_sk} for {level.name}). "
                f"Regenerate keys with scripts/setup/generate_keys.py --level {level.value}"
            )
        # Sign params + prev_hash + height for chain binding.
        # Uses canonical JSON serialization for params to ensure deterministic
        # byte representation that matches the verification side.
        import json as _json
        msg = (_json.dumps(params.tolist(), sort_keys=True,
                           separators=(',', ':')).encode()
               + prev_hash.encode() + str(height).encode())
        signer = DilithiumSigner(level)
        signature = signer.sign(sk_bytes, msg)
        return {
            'challenge': hamiltonian,
            'params': params.tolist(),
            'energy': float(energy),
            'prev_hash': prev_hash,
            'height': height,
            'signature': signature.hex(),
            'public_key': Config.PUBLIC_KEY_HEX,
            'miner_address': Config.ADDRESS
        }

    def _create_coinbase(self, height: int, reward: Decimal,
                        pending_txs: list,
                        prev_hash: str = '') -> Transaction:
        """Create coinbase transaction with base fee burning.

        A configurable percentage of transaction fees (FEE_BURN_PERCENTAGE)
        is permanently destroyed rather than paid to the miner, creating
        deflationary pressure on QBC supply.  The burned amount is tracked
        in both the ``total_burned`` stat and the Prometheus metric.
        """
        total_fees = sum(tx.fee for tx in pending_txs)

        # Apply fee burn — a percentage of fees are destroyed
        burn_pct = Decimal(str(Config.FEE_BURN_PERCENTAGE))
        burned = (total_fees * burn_pct).quantize(Decimal('0.00000001'))
        miner_fees = total_fees - burned

        if burned > 0:
            with self._lock:
                self.stats['total_burned'] = float(
                    Decimal(str(self.stats.get('total_burned', 0))) + burned
                )
                burned_total = self.stats['total_burned']
            total_fees_burned_metric.set(burned_total)
            logger.debug(
                f"Block {height}: burning {burned:.8f} QBC of {total_fees:.8f} fees "
                f"({Config.FEE_BURN_PERCENTAGE * 100:.0f}%)"
            )

        total_reward = reward + miner_fees

        # Build outputs: vout=0 is always the mining reward
        outputs = [{
            'address': Config.ADDRESS,
            'amount': total_reward
        }]

        # Genesis premine: add a second output (vout=1) at block 0
        if height == 0 and Config.GENESIS_PREMINE > 0:
            outputs.append({
                'address': Config.ADDRESS,
                'amount': Config.GENESIS_PREMINE
            })

        # Deterministic coinbase txid — same inputs always produce same txid
        coinbase_txid = hashlib.sha256(
            f"coinbase-{height}-{prev_hash}".encode()
        ).hexdigest()
        return Transaction(
            txid=coinbase_txid,
            inputs=[],
            outputs=outputs,
            fee=Decimal(0),
            signature='',
            public_key=Config.PUBLIC_KEY_HEX,
            timestamp=time.time(),
            status='pending'
        )

    def _display_success(self, block: Block, energy: float, reward: Decimal):
        """Display mining success"""
        try:
            from rich.table import Table
            from rich.panel import Panel
            table = Table(title="Block Mined!")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Height", str(block.height))
            table.add_row("Energy", f"{energy:.6f}")
            table.add_row("Difficulty", f"{block.difficulty:.6f}")
            table.add_row("Transactions", str(len(block.transactions)))
            table.add_row("Reward", f"{reward:.8f} QBC")
            if block.height == 0 and Config.GENESIS_PREMINE > 0:
                table.add_row("Genesis Premine", f"{Config.GENESIS_PREMINE:,.0f} QBC")
            table.add_row("Hash", block.block_hash[:16] + "...")
            self.console.print(Panel(table))
        except Exception as e:
            logger.debug(f"Rich console display failed: {e}")
        if block.height == 0 and Config.GENESIS_PREMINE > 0:
            logger.info(
                f"GENESIS BLOCK mined: {block.block_hash[:16]}... "
                f"(reward={reward} + premine={Config.GENESIS_PREMINE:,} QBC)"
            )
        else:
            logger.info(f"Block {block.height} mined: {block.block_hash[:16]}...")
