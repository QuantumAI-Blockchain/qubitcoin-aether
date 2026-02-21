"""
Mining engine for Proof-of-SUSY-Alignment
Handles block creation and mining loop with SUSY Economics
"""
import threading
import time
import hashlib
import json
import asyncio
from decimal import Decimal
import numpy as np
from ..config import Config
from ..database.models import Transaction, Block
from ..quantum.engine import QuantumEngine
from ..quantum.crypto import Dilithium2
from ..consensus.engine import ConsensusEngine
from ..utils.logger import get_logger
from ..utils.metrics import blocks_mined, mining_attempts, current_height_metric

logger = get_logger(__name__)


class MiningEngine:
    """Manages mining operations"""

    def __init__(self, quantum_engine: QuantumEngine, consensus_engine: ConsensusEngine,
                 db_manager, console, state_manager=None, aether_engine=None):
        """Initialize mining engine"""
        self.quantum = quantum_engine
        self.consensus = consensus_engine
        self.db = db_manager
        self.console = console
        self.state_manager = state_manager
        self.aether = aether_engine
        self.node = None
        self.is_mining = False
        self.mining_thread = None
        self._lock = threading.Lock()
        self.stats = {
            'blocks_found': 0,
            'total_attempts': 0,
            'current_difficulty': Config.INITIAL_DIFFICULTY
        }
        logger.info("Mining engine initialized (SUSY Economics + QVM)")

    def start(self):
        """Start mining"""
        if self.is_mining:
            logger.warning("Mining already running")
            return
        self.is_mining = True
        self.mining_thread = threading.Thread(
            target=self._mine_loop,
            daemon=True,
            name="MiningThread"
        )
        self.mining_thread.start()
        logger.info("Mining started")

    def stop(self):
        """Stop mining"""
        if not self.is_mining:
            return
        self.is_mining = False
        if self.mining_thread:
            self.mining_thread.join(timeout=5)
        logger.info("Mining stopped")

    def _mine_loop(self):
        """Main mining loop"""
        while self.is_mining:
            try:
                self._mine_block()
            except Exception as e:
                logger.error(f"Mining error: {e}", exc_info=True)
                time.sleep(Config.MINING_INTERVAL)

    def _mine_block(self):
        """Attempt to mine a single block"""
        current_height = self.db.get_current_height()
        next_height = current_height + 1
        difficulty = self.consensus.calculate_difficulty(next_height, self.db)
        self.stats['current_difficulty'] = difficulty

        # Pre-check if height exists (from P2P sync)
        if self.db.get_block(next_height):
            logger.debug(f"Block {next_height} already exists from P2P, skipping")
            time.sleep(Config.MINING_INTERVAL)
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
            if not self.is_mining:
                return

            # Check if someone else found this block
            if self.db.get_block(next_height):
                logger.info(f"Block {next_height} found by peer during mining, stopping")
                return

            try:
                params, energy = self.quantum.optimize_vqe(hamiltonian)
            except Exception as e:
                logger.error(f"VQE optimization failed (attempt {attempt+1}): {e}")
                continue

            self.stats['total_attempts'] += 1
            mining_attempts.inc()

            if energy < difficulty:
                logger.info(f"Solution found! energy={energy:.6f} < difficulty={difficulty:.6f} (attempt {attempt+1})")
                break

            logger.debug(f"Attempt {attempt+1}/{max_attempts}: energy {energy:.6f} >= difficulty {difficulty:.6f}")
        else:
            # All attempts exhausted
            logger.debug(f"No solution in {max_attempts} attempts, retrying next round")
            time.sleep(Config.MINING_INTERVAL)
            return

        # Build proof with chain binding
        proof_data = self._create_proof(hamiltonian, params, energy, prev_hash, next_height)
        total_supply = self.db.get_total_supply()
        reward = self.consensus.calculate_reward(next_height, total_supply)
        coinbase = self._create_coinbase(next_height, reward, pending_txs)

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
            block, self.db.get_block(current_height), self.db
        )
        if not valid:
            logger.error(f"Self-validation failed: {reason}")
            return

        # Store block, supply, and hamiltonian atomically in one session
        try:
            with self._lock:
                with self.db.get_session() as session:
                    # Check again under lock
                    from sqlalchemy import text
                    existing = session.execute(
                        text("SELECT 1 FROM blocks WHERE height = :h"),
                        {'h': next_height}
                    ).first()
                    if existing:
                        logger.warning(f"Block {next_height} appeared during mining, skipping")
                        return

                    self.db.store_block(block, session=session)
                    self.db.update_supply(reward, session)
                    self.db.store_hamiltonian(
                        hamiltonian=hamiltonian,
                        params=params.tolist(),
                        energy=float(energy),
                        miner_address=Config.ADDRESS,
                        block_height=next_height,
                        session=session
                    )
                    session.commit()

            self.stats['blocks_found'] += 1
            blocks_mined.inc()
            current_height_metric.set(next_height)
            self._display_success(block, energy, reward)

            # Process block knowledge for Aether Tree
            if self.aether:
                try:
                    self.aether.process_block_knowledge(block)
                except Exception as e:
                    logger.debug(f"Aether knowledge processing: {e}")

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
                    self.aether.phi_calculator.downsample_phi_measurements()
                except Exception as e:
                    logger.debug(f"Phi downsample: {e}")

            if next_height % Config.PRUNE_INTERVAL_BLOCKS == 0 and self.aether:
                try:
                    kg = self.aether.knowledge_graph
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

        time.sleep(Config.MINING_INTERVAL)

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

    def _create_proof(self, hamiltonian, params, energy,
                      prev_hash: str, height: int) -> dict:
        """Create quantum proof data with chain binding"""
        pk_bytes = bytes.fromhex(Config.PRIVATE_KEY_HEX)
        # Sign params + prev_hash + height for chain binding
        msg = str(params.tolist()).encode() + prev_hash.encode() + str(height).encode()
        signature = Dilithium2.sign(pk_bytes, msg)
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
                        pending_txs: list) -> Transaction:
        """Create coinbase transaction"""
        total_fees = sum(tx.fee for tx in pending_txs)
        total_reward = reward + total_fees
        coinbase_txid = hashlib.sha256(
            f"coinbase-{height}-{time.time()}".encode()
        ).hexdigest()
        return Transaction(
            txid=coinbase_txid,
            inputs=[],
            outputs=[{
                'address': Config.ADDRESS,
                'amount': total_reward
            }],
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
            table.add_row("Hash", block.block_hash[:16] + "...")
            self.console.print(Panel(table))
        except Exception:
            pass
        logger.info(f"Block {block.height} mined: {block.block_hash[:16]}...")
