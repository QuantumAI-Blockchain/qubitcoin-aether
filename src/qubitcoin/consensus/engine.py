"""
Consensus engine for Qubitcoin
Handles difficulty adjustment, golden ratio rewards, and validation
"""
from decimal import Decimal
from typing import Tuple, Optional, Dict
import time
import asyncio
from ..config import Config
from ..database.models import Block, Transaction, UTXO
from ..quantum.engine import QuantumEngine
from ..quantum.crypto import CryptoManager
from ..utils.logger import get_logger
from ..utils.metrics import block_validation_time

logger = get_logger(__name__)


class ConsensusEngine:
    """Manages consensus rules and validation"""

    def __init__(self, quantum_engine: QuantumEngine, db_manager, p2p_network):
        """Initialize consensus engine"""
        self.quantum = quantum_engine
        self.crypto = CryptoManager()
        self.db = db_manager
        self.p2p = p2p_network
        self.state_manager = None  # Injected by node after StateManager init
        self.aether = None  # Injected by node after AetherEngine init
        self.difficulty_cache = {}
        logger.info("Consensus engine initialized (SUSY Economics + QVM + Aether)")

    def calculate_reward(self, height: int, total_supply: Decimal) -> Decimal:
        """Calculate block reward with golden ratio halvings + tail emission.

        Reward schedule:
        1. Phi-halving: reward = INITIAL_REWARD / PHI^era (decreasing each era)
        2. When phi-halving reward drops below TAIL_EMISSION_REWARD, switch to
           the fixed tail emission rate.
        3. Tail emission continues until MAX_SUPPLY is reached.
        4. Once MAX_SUPPLY is reached, reward = 0.
        """
        PHI = Decimal('1.618033988749895')
        era = height // Config.HALVING_INTERVAL
        phi_reward = Config.INITIAL_REWARD / (PHI ** era)

        # Use tail emission when phi-halving drops below the threshold
        if phi_reward >= Config.TAIL_EMISSION_REWARD:
            base_reward = phi_reward
        else:
            base_reward = Config.TAIL_EMISSION_REWARD

        remaining = Config.MAX_SUPPLY - total_supply
        reward = min(base_reward, remaining)

        if reward <= 0:
            logger.warning(f"Max supply reached at height {height}")
            return Decimal(0)

        logger.debug(f"Block {height}: Era {era}, Reward {reward:.8f} QBC"
                      f"{' (tail)' if phi_reward < Config.TAIL_EMISSION_REWARD else ''}")
        return reward

    # Height at which the difficulty ratio formula was corrected.
    # Blocks before this used inverted ratio (expected/actual) which caused a
    # death spiral — lowering difficulty when blocks were slow made VQE harder.
    # Blocks at or after this height use corrected ratio (actual/expected) so
    # that slow blocks raise the threshold, making mining easier.
    DIFFICULTY_FIX_HEIGHT = 724

    # Height at which the meaningful-max clamp was added.  Before this,
    # difficulty ran away to 1000 because the ceiling was raised but
    # there was no check for "already trivially easy".  Reset to
    # INITIAL_DIFFICULTY at this height to recover.
    DIFFICULTY_CEILING_FIX_HEIGHT = 2750

    # Height at which difficulty dropped below the Hamiltonian ground state
    # (0.0798 < 0.182), making mining impossible.  Reset + ground state
    # energy check added to prevent this permanently.
    DIFFICULTY_GROUND_STATE_FIX_HEIGHT = 167

    def calculate_difficulty(self, height: int, db_manager) -> float:
        """Calculate difficulty using per-block adjustment with 144-block lookback window.

        In VQE mining, energy must be BELOW the difficulty threshold to mine a
        block.  Therefore higher difficulty = easier mining.

        Algorithm:
          1. Look back DIFFICULTY_WINDOW (144) blocks.
          2. actual_time = timestamp(head) - timestamp(head - window).
          3. expected_time = DIFFICULTY_WINDOW * TARGET_BLOCK_TIME.
          4. ratio = actual_time / expected_time
             (>1 means blocks too slow → raise difficulty to make mining easier,
              <1 means blocks too fast → lower difficulty to make mining harder).
          5. Clamp ratio to ±MAX_DIFFICULTY_CHANGE (10%) per adjustment.
          6. new_difficulty = prev_difficulty * clamped_ratio.
        """
        if height in self.difficulty_cache:
            return self.difficulty_cache[height]

        window = Config.DIFFICULTY_WINDOW  # 144

        if height < window:
            return Config.INITIAL_DIFFICULTY

        # One-time difficulty reset at fix height to escape death-spiral
        if height == self.DIFFICULTY_FIX_HEIGHT:
            self.difficulty_cache[height] = Config.INITIAL_DIFFICULTY
            logger.info(f"Difficulty reset to {Config.INITIAL_DIFFICULTY} at fork height {height}")
            return Config.INITIAL_DIFFICULTY

        # One-time reset to recover from ceiling runaway (difficulty hit 1000
        # because compute-time bottleneck wasn't accounted for)
        if height == self.DIFFICULTY_CEILING_FIX_HEIGHT:
            self.difficulty_cache[height] = Config.INITIAL_DIFFICULTY
            logger.info(f"Difficulty reset to {Config.INITIAL_DIFFICULTY} at ceiling-fix height {height}")
            return Config.INITIAL_DIFFICULTY

        # One-time reset — difficulty dropped below Hamiltonian ground state
        if height == self.DIFFICULTY_GROUND_STATE_FIX_HEIGHT:
            self.difficulty_cache[height] = Config.INITIAL_DIFFICULTY
            logger.info(f"Difficulty reset to {Config.INITIAL_DIFFICULTY} at ground-state-fix height {height}")
            return Config.INITIAL_DIFFICULTY

        try:
            head_block = db_manager.get_block(height - 1)
            window_start_block = db_manager.get_block(height - window)

            if not head_block or not window_start_block:
                logger.warning(f"Missing blocks for difficulty calc at {height}, using default")
                return Config.INITIAL_DIFFICULTY

            head_time = float(head_block.timestamp or 0)
            start_time = float(window_start_block.timestamp or 0)
            prev_difficulty = float(head_block.difficulty) if head_block.difficulty else Config.INITIAL_DIFFICULTY

            if head_time <= start_time or start_time == 0 or head_time == 0:
                logger.warning(f"Invalid timestamps for difficulty calc at {height}, using previous")
                return prev_difficulty

            actual_time = head_time - start_time
            expected_time = Config.TARGET_BLOCK_TIME * window

            # Pre-fix blocks used inverted ratio; post-fix uses corrected ratio
            if height < self.DIFFICULTY_FIX_HEIGHT:
                ratio = expected_time / actual_time  # Legacy (inverted)
            else:
                ratio = actual_time / expected_time  # Corrected: slow → raise, fast → lower

            # Clamp to ±MAX_DIFFICULTY_CHANGE (default ±10%)
            max_change = Config.MAX_DIFFICULTY_CHANGE
            ratio = max(1.0 - max_change, min(1.0 + max_change, ratio))

            # When difficulty is already trivially easy (well above typical
            # VQE energies of -5 to +5), blocks are slow due to compute time,
            # not puzzle hardness.  Only allow upward adjustment when difficulty
            # is still in the meaningful range; once above the meaningful
            # threshold, hold steady so we don't run away to the ceiling.
            if ratio > 1.0 and prev_difficulty > Config.DIFFICULTY_MEANINGFUL_MAX:
                ratio = 1.0  # Hold steady — can't mine faster than VQE allows

            new_difficulty = prev_difficulty * ratio
            new_difficulty = max(Config.DIFFICULTY_FLOOR, min(Config.DIFFICULTY_CEILING, new_difficulty))

            # LAYER 2 SAFETY: Ensure difficulty > Hamiltonian ground state.
            # The Hamiltonian is deterministic from (prev_hash, height) so
            # every node computes the same result.  For 4 qubits this is a
            # 16×16 matrix diagonalization — microseconds.
            try:
                prev_hash = head_block.block_hash
                ham = self.quantum.generate_hamiltonian(prev_hash=prev_hash, height=height)
                ground_state = self.quantum.compute_exact_ground_state(ham)
                min_difficulty = ground_state + Config.ENERGY_MARGIN
                if new_difficulty < min_difficulty:
                    logger.info(
                        f"Difficulty {new_difficulty:.6f} below ground state "
                        f"{ground_state:.6f} + margin {Config.ENERGY_MARGIN}, "
                        f"raising to {min_difficulty:.6f} at height {height}"
                    )
                    new_difficulty = min_difficulty
            except Exception as e:
                logger.warning(f"Ground state check failed at height {height}: {e}")

            # Cache to avoid re-computation (evict old entries to bound memory)
            self.difficulty_cache[height] = new_difficulty
            if len(self.difficulty_cache) > Config.DIFFICULTY_WINDOW * 2:
                oldest = min(self.difficulty_cache)
                del self.difficulty_cache[oldest]

            if abs(ratio - 1.0) > 0.001:
                logger.info(
                    f"Difficulty adjusted at height {height}: "
                    f"{prev_difficulty:.6f} -> {new_difficulty:.6f} "
                    f"(ratio: {ratio:.4f}, actual: {actual_time:.1f}s vs expected: {expected_time:.1f}s)"
                )

            return new_difficulty

        except Exception as e:
            logger.error(f"Error calculating difficulty at height {height}: {e}", exc_info=True)
            return Config.INITIAL_DIFFICULTY

    def validate_block(self, block: Block, prev_block: Optional[Block], db_manager) -> Tuple[bool, str]:
        """Comprehensive block validation"""
        validation_start = time.time()
        try:
            expected_height = (prev_block.height + 1) if prev_block else 0
            if block.height != expected_height:
                return False, f"Invalid height: {block.height} != {expected_height}"

            expected_prev_hash = prev_block.block_hash if prev_block else '0' * 64
            if block.prev_hash != expected_prev_hash:
                return False, "Invalid prev_hash"

            # Verify block hash matches contents
            if block.block_hash:
                computed_hash = block.calculate_hash()
                if block.block_hash != computed_hash:
                    return False, f"Block hash mismatch: {block.block_hash[:16]} != {computed_hash[:16]}"

            # Timestamp validation (using validation_start to avoid TOCTOU)
            if block.timestamp > validation_start + Config.MAX_FUTURE_BLOCK_TIME:
                return False, f"Block timestamp too far in future: {block.timestamp}"
            if prev_block and block.timestamp <= prev_block.timestamp:
                return False, (
                    f"Block timestamp not increasing: {block.timestamp:.6f} "
                    f"<= prev {prev_block.timestamp:.6f}"
                )

            expected_difficulty = self.calculate_difficulty(block.height, db_manager)
            if abs(block.difficulty - expected_difficulty) > 0.001:
                return False, f"Invalid difficulty: {block.difficulty} != {expected_difficulty}"

            proof = block.proof_data
            if not proof or not isinstance(proof, dict):
                return False, "Missing or invalid proof data"

            # RE-DERIVE the Hamiltonian from chain state and verify
            # the miner's proof is against the correct challenge
            valid, reason = self.quantum.validate_proof(
                params=proof.get('params', []),
                hamiltonian=proof.get('challenge', []),
                claimed_energy=proof.get('energy', 0),
                difficulty=block.difficulty,
                prev_hash=block.prev_hash,
                height=block.height
            )
            if not valid:
                return False, f"Invalid quantum proof: {reason}"

            # Verify proof signature (includes chain binding)
            pk_hex = proof.get('public_key', '')
            sig_hex = proof.get('signature', '')
            if pk_hex and sig_hex:
                pk = bytes.fromhex(pk_hex)
                # Message includes params + prev_hash + height (chain binding)
                msg = (str(proof.get('params', [])).encode()
                       + block.prev_hash.encode()
                       + str(block.height).encode())
                sig = bytes.fromhex(sig_hex)
                from ..quantum.crypto import Dilithium2
                if not Dilithium2.verify(pk, msg, sig):
                    return False, "Invalid proof signature"

            # Validate transactions - calculate fees BEFORE checking coinbase
            total_fees = Decimal(0)
            coinbase_count = 0
            coinbase_tx = None
            for tx in block.transactions:
                if len(tx.inputs) == 0:
                    coinbase_count += 1
                    coinbase_tx = tx
                    if coinbase_count > 1:
                        return False, "Multiple coinbase transactions"
                    continue
                if not self.validate_transaction(tx, db_manager, current_height=block.height):
                    return False, f"Invalid transaction: {tx.txid}"
                total_fees += tx.fee

            if coinbase_count == 0:
                return False, "No coinbase transaction"

            # Validate coinbase amount AFTER accumulating all fees
            # Apply fee burn — miners only receive (1 - burn_pct) of fees
            total_supply = db_manager.get_total_supply()
            expected_reward = self.calculate_reward(block.height, total_supply)
            burn_pct = Decimal(str(Config.FEE_BURN_PERCENTAGE))
            burned_fees = (total_fees * burn_pct).quantize(Decimal('0.00000001'))
            miner_fees = total_fees - burned_fees
            coinbase_amount = sum(Decimal(str(o['amount'])) for o in coinbase_tx.outputs)
            expected_coinbase = expected_reward + miner_fees
            # Genesis block includes the premine allocation
            if block.height == 0 and Config.GENESIS_PREMINE > 0:
                expected_coinbase += Config.GENESIS_PREMINE
            if coinbase_amount > expected_coinbase:
                return False, f"Excessive coinbase: {coinbase_amount} > {expected_coinbase}"

            # ── Susy Swap (confidential tx) block-level validation ────
            # Individual private tx validation is handled by validate_transaction
            # above (routing to _validate_private_transaction). This block-level
            # check ensures cross-transaction invariants: key image uniqueness
            # across all transactions in the block, commitment consistency,
            # and range proof verification for any confidential outputs.
            susy_valid, susy_reason = self._validate_block_susy_swaps(
                block, db_manager
            )
            if not susy_valid:
                return False, susy_reason

            # (Timestamp validation already done above — single check, no duplicate)

            # Validate state root (if QVM is active and block has state root)
            if self.state_manager and block.state_root:
                try:
                    state_root, receipts_root = self.state_manager.execute_block_transactions(block)
                    if block.state_root != state_root:
                        return False, f"Invalid state_root: {block.state_root[:16]} != {state_root[:16]}"
                    if block.receipts_root and block.receipts_root != receipts_root:
                        return False, f"Invalid receipts_root: {block.receipts_root[:16]} != {receipts_root[:16]}"
                except Exception as e:
                    logger.warning(f"State root validation skipped: {e}")

            # Validate thought proof (Aether Tree PoT) if present
            if block.thought_proof and isinstance(block.thought_proof, dict):
                pot_data = block.thought_proof
                if pot_data.get('phi_value', 0) < 0:
                    return False, "Invalid thought proof: negative phi value"
                if self.aether:
                    from ..database.models import ProofOfThought
                    try:
                        pot = ProofOfThought(
                            thought_hash=pot_data.get('thought_hash', ''),
                            reasoning_steps=pot_data.get('reasoning_steps', []),
                            phi_value=pot_data.get('phi_value', 0),
                            knowledge_root=pot_data.get('knowledge_root', ''),
                            validator_address=pot_data.get('validator_address', ''),
                            signature=pot_data.get('signature', ''),
                            timestamp=pot_data.get('timestamp', 0),
                        )
                        valid_pot, pot_reason = self.aether.validate_thought_proof(pot, block)
                        if not valid_pot:
                            return False, f"Invalid thought proof: {pot_reason}"
                    except Exception as e:
                        logger.debug(f"Thought proof validation error: {e}")

            logger.debug(f"Block {block.height} validated successfully")
            block_validation_time.observe(time.time() - validation_start)
            return True, "Valid"
        except Exception as e:
            logger.error(f"Block validation error: {e}", exc_info=True)
            block_validation_time.observe(time.time() - validation_start)
            return False, f"Validation exception: {str(e)}"

    def validate_transaction(self, tx: Transaction, db_manager,
                             current_height: Optional[int] = None) -> bool:
        """Validate transaction with proper UTXO lookup and coinbase maturity.

        Args:
            tx: Transaction to validate.
            db_manager: Database manager for UTXO lookups.
            current_height: Height of the block containing this tx. Used for
                coinbase maturity checks. If None, uses chain tip.
        """
        try:
            # Route to privacy-specific validation if tx is confidential
            if getattr(tx, 'is_private', False):
                return self._validate_private_transaction(tx, db_manager, current_height)

            # Verify signature
            pk = bytes.fromhex(tx.public_key)
            msg = str({
                'inputs': tx.inputs,
                'outputs': [{'address': o['address'], 'amount': str(o['amount'])} for o in tx.outputs],
                'fee': str(tx.fee),
                'timestamp': tx.timestamp
            }).encode()
            sig = bytes.fromhex(tx.signature)
            from ..quantum.crypto import Dilithium2
            if not Dilithium2.verify(pk, msg, sig):
                return False

            if current_height is None:
                current_height = db_manager.get_current_height()

            # Validate inputs - look up UTXOs by txid/vout
            input_total = Decimal(0)
            spent_utxos = set()
            for inp in tx.inputs:
                utxo_key = (inp['txid'], inp['vout'])
                # Check for intra-block double spend
                if utxo_key in spent_utxos:
                    logger.warning(f"Double spend detected in tx {tx.txid}")
                    return False
                spent_utxos.add(utxo_key)

                # Look up UTXO directly by txid/vout
                utxo = db_manager.get_utxo(inp['txid'], inp['vout'])
                if not utxo or utxo.spent:
                    logger.warning(f"UTXO not found or spent: {inp['txid']}:{inp['vout']}")
                    return False

                # Coinbase maturity: coinbase UTXOs can't be spent for COINBASE_MATURITY blocks
                if self._is_coinbase_utxo(utxo, db_manager):
                    if utxo.block_height is not None:
                        confirmations = current_height - utxo.block_height
                        if confirmations < Config.COINBASE_MATURITY:
                            logger.warning(
                                f"Immature coinbase UTXO: {utxo.txid}:{utxo.vout} "
                                f"({confirmations} < {Config.COINBASE_MATURITY} required)"
                            )
                            return False

                input_total += utxo.amount

            output_total = sum(Decimal(str(o['amount'])) for o in tx.outputs)
            if input_total < output_total + tx.fee:
                return False
            return True
        except Exception as e:
            logger.error(f"Transaction validation error: {e}")
            return False

    def _validate_private_transaction(self, tx: Transaction, db_manager,
                                      current_height: Optional[int] = None) -> bool:
        """Validate a Susy Swap (confidential) transaction.

        Privacy transactions use Pedersen commitments instead of plaintext amounts.
        Validation checks:
        1. Signature verification (same as public tx)
        2. Key image uniqueness (no double-spend of confidential outputs)
        3. Range proof verification (all committed values are non-negative)
        4. Fee is explicitly visible and non-negative
        """
        try:
            # 0. Reject private tx with no inputs (invalid state)
            if not tx.inputs:
                logger.warning(f"Private tx {tx.txid}: no inputs")
                return False

            # 1. Verify signature
            pk = bytes.fromhex(tx.public_key)
            msg = str({
                'inputs': tx.inputs,
                'outputs': [{'address': o.get('address', o.get('one_time_address', '')),
                             'amount': str(o.get('amount', '0'))} for o in tx.outputs],
                'fee': str(tx.fee),
                'timestamp': tx.timestamp
            }).encode()
            sig = bytes.fromhex(tx.signature)
            from ..quantum.crypto import Dilithium2
            if not Dilithium2.verify(pk, msg, sig):
                logger.warning(f"Private tx {tx.txid}: invalid signature")
                return False

            # 2. Key image uniqueness — prevent double-spend of confidential outputs
            key_images = []
            for inp in tx.inputs:
                ki = inp.get('key_image')
                if not ki:
                    logger.warning(f"Private tx {tx.txid}: input missing key_image")
                    return False
                if ki in key_images:
                    logger.warning(f"Private tx {tx.txid}: duplicate key image in same tx")
                    return False
                key_images.append(ki)
                # Check against spent key images in DB
                if self._is_key_image_spent(ki, db_manager):
                    logger.warning(f"Private tx {tx.txid}: key image already spent: {ki[:32]}...")
                    return False

            # 3. Range proof verification — each output must prove value >= 0
            for i, out in enumerate(tx.outputs):
                range_proof = out.get('range_proof')
                if range_proof:
                    try:
                        from ..privacy.range_proofs import RangeProofVerifier, RangeProof
                        proof_obj = RangeProof(
                            commitment=range_proof.get('commitment', b''),
                            A=range_proof.get('A', b''),
                            S=range_proof.get('S', b''),
                            T1=range_proof.get('T1', b''),
                            T2=range_proof.get('T2', b''),
                            tau_x=range_proof.get('tau_x', 0),
                            mu=range_proof.get('mu', 0),
                            t_hat=range_proof.get('t_hat', 0),
                            l_vec=range_proof.get('l_vec', []),
                            r_vec=range_proof.get('r_vec', []),
                        )
                        if not RangeProofVerifier.verify(proof_obj):
                            logger.warning(f"Private tx {tx.txid}: range proof failed for output {i}")
                            return False
                    except Exception as e:
                        logger.warning(f"Private tx {tx.txid}: range proof error for output {i}: {e}")
                        return False

            # 4. Fee must be explicit and non-negative
            if tx.fee < 0:
                logger.warning(f"Private tx {tx.txid}: negative fee")
                return False

            logger.debug(f"Private tx {tx.txid} validated successfully")
            return True
        except Exception as e:
            logger.error(f"Private transaction validation error: {e}")
            return False

    def _is_key_image_spent(self, key_image: str, db_manager) -> bool:
        """Check if a key image has been used in a previous transaction."""
        try:
            with db_manager.get_session() as session:
                from sqlalchemy import text
                result = session.execute(
                    text("SELECT 1 FROM key_images WHERE key_image = :ki LIMIT 1"),
                    {'ki': key_image}
                ).fetchone()
                return result is not None
        except Exception as e:
            err_msg = str(e).lower()
            if 'does not exist' in err_msg or 'no such table' in err_msg:
                # Table not created yet — allow through (pre-privacy-deploy)
                logger.debug("key_images table not yet created, skipping check")
                return False
            # Any other DB error should reject the tx for safety
            logger.error(f"Key image check failed (rejecting tx): {e}")
            return True

    def _is_coinbase_utxo(self, utxo: UTXO, db_manager) -> bool:
        """Check if a UTXO came from a coinbase transaction (no inputs)."""
        try:
            with db_manager.get_session() as session:
                from sqlalchemy import text
                result = session.execute(
                    text("SELECT inputs FROM transactions WHERE txid = :txid"),
                    {'txid': utxo.txid}
                ).fetchone()
                if not result:
                    return False
                inputs = result[0]
                if isinstance(inputs, str):
                    import json
                    inputs = json.loads(inputs)
                return isinstance(inputs, list) and len(inputs) == 0
        except Exception:
            return False

    def _validate_block_susy_swaps(self, block: Block, db_manager) -> Tuple[bool, str]:
        """Validate all Susy Swap (confidential) transactions at the block level.

        Performs cross-transaction checks that individual tx validation cannot:
          1. Key image uniqueness across ALL transactions in the block
             (individual tx validation only checks within a single tx and DB)
          2. Commitment consistency for confidential outputs
          3. Range proof verification for any confidential outputs

        Args:
            block: The block to validate.
            db_manager: Database manager for lookups.

        Returns:
            (True, "Valid") on success, (False, reason) on failure.
        """
        try:
            # Collect all key images across every private tx in the block
            block_key_images: Dict[str, str] = {}  # key_image → txid

            for tx in block.transactions:
                # Skip coinbase transactions (no inputs)
                if len(tx.inputs) == 0:
                    continue

                is_private = getattr(tx, 'is_private', False)
                if not is_private:
                    # Also check if any output has susy_data / confidential markers
                    has_confidential_data = any(
                        out.get('range_proof') or out.get('commitment')
                        for out in tx.outputs
                    )
                    if not has_confidential_data:
                        continue

                # ── 1. Cross-tx key image uniqueness ──────────────────
                for inp in tx.inputs:
                    ki = inp.get('key_image')
                    if not ki:
                        continue
                    if ki in block_key_images:
                        conflicting_txid = block_key_images[ki]
                        return False, (
                            f"Duplicate key image across block transactions: "
                            f"key_image={ki[:32]}... in tx {tx.txid[:16]} "
                            f"and tx {conflicting_txid[:16]}"
                        )
                    block_key_images[ki] = tx.txid

                # ── 2. Commitment consistency check ───────────────────
                # Verify that each output with a commitment has well-formed data
                for i, out in enumerate(tx.outputs):
                    commitment_hex = out.get('commitment')
                    if commitment_hex:
                        try:
                            if isinstance(commitment_hex, str):
                                commitment_bytes = bytes.fromhex(commitment_hex)
                                # Compressed EC point: 33 bytes (02/03 prefix + 32 bytes x)
                                if len(commitment_bytes) != 33:
                                    return False, (
                                        f"Invalid commitment size in tx {tx.txid[:16]} "
                                        f"output {i}: {len(commitment_bytes)} bytes (expected 33)"
                                    )
                                if commitment_bytes[0] not in (0x02, 0x03):
                                    return False, (
                                        f"Invalid commitment prefix in tx {tx.txid[:16]} "
                                        f"output {i}: 0x{commitment_bytes[0]:02x}"
                                    )
                        except (ValueError, TypeError) as e:
                            return False, (
                                f"Malformed commitment in tx {tx.txid[:16]} output {i}: {e}"
                            )

                # ── 3. Range proof verification ───────────────────────
                for i, out in enumerate(tx.outputs):
                    range_proof_data = out.get('range_proof')
                    if not range_proof_data:
                        continue
                    try:
                        from ..privacy.range_proofs import RangeProofVerifier, RangeProof
                        if isinstance(range_proof_data, dict):
                            proof_obj = RangeProof(
                                commitment=range_proof_data.get('commitment', b''),
                                A=range_proof_data.get('A', b''),
                                S=range_proof_data.get('S', b''),
                                T1=range_proof_data.get('T1', b''),
                                T2=range_proof_data.get('T2', b''),
                                tau_x=range_proof_data.get('tau_x', 0),
                                mu=range_proof_data.get('mu', 0),
                                t_hat=range_proof_data.get('t_hat', 0),
                                l_vec=range_proof_data.get('l_vec', []),
                                r_vec=range_proof_data.get('r_vec', []),
                            )
                            if not RangeProofVerifier.verify(proof_obj):
                                return False, (
                                    f"Range proof verification failed in tx "
                                    f"{tx.txid[:16]} output {i}"
                                )
                    except ImportError:
                        logger.debug("Privacy module not available for range proof verification")
                    except Exception as e:
                        return False, (
                            f"Range proof error in tx {tx.txid[:16]} output {i}: {e}"
                        )

            return True, "Valid"

        except ImportError as e:
            # Privacy module not installed — skip Susy Swap validation
            logger.warning(f"Privacy module unavailable, skipping Susy validation: {e}")
            return True, "Valid (susy validation skipped — privacy module missing)"
        except Exception as e:
            # Any other error is a validation failure — do NOT allow block through
            logger.error(f"Susy Swap block validation error (rejecting block): {e}")
            return False, f"Susy Swap validation error: {e}"

    async def resolve_fork(self, new_block: Block, sender_id: str):
        """Resolve fork by adopting longer valid chain"""
        current_height = self.db.get_current_height()
        if new_block.height <= current_height:
            return

        # In Rust P2P mode self.p2p is None; fork resolution requires the
        # Python P2P layer to request missing blocks from peers.
        if self.p2p is None:
            logger.warning(
                f"Cannot resolve fork to height {new_block.height}: "
                f"P2P network is None (Rust P2P mode). "
                f"Fork resolution requires Python P2P layer."
            )
            return

        logger.info(f"Resolving fork: Peer {sender_id} has block at height {new_block.height}")

        # Request missing blocks first, collect them
        missing_blocks = []
        for height in range(current_height + 1, new_block.height + 1):
            await self.p2p.send_message(sender_id, 'get_block', {'height': height})
            await asyncio.sleep(0.1)

        # Wait for blocks to arrive (handled by P2P message handlers)
        await asyncio.sleep(2.0)

        # Check if blocks were received and stored by the P2P handler
        new_height = self.db.get_current_height()
        if new_height >= new_block.height:
            logger.info(f"Fork resolved: chain now at height {new_height}")
            return

        # If we still don't have the blocks, do a proper reorg
        fork_height = current_height
        logger.info(f"Performing chain reorg from height {fork_height}")

        with self.db.get_session() as session:
            from sqlalchemy import text
            # Delete UTXOs created after fork point
            session.execute(
                text("DELETE FROM utxos WHERE block_height > :fork"),
                {'fork': fork_height}
            )
            # Un-spend UTXOs that were spent by transactions after fork
            session.execute(
                text("""UPDATE utxos SET spent = false, spent_by = NULL
                        WHERE spent_by IN (
                            SELECT txid FROM transactions WHERE block_height > :fork
                        )"""),
                {'fork': fork_height}
            )
            # Delete QVM state created after fork point
            session.execute(
                text("DELETE FROM transaction_receipts WHERE block_height > :fork"),
                {'fork': fork_height}
            )
            session.execute(
                text("DELETE FROM event_logs WHERE block_height > :fork"),
                {'fork': fork_height}
            )
            session.execute(
                text("DELETE FROM contract_storage WHERE block_height > :fork"),
                {'fork': fork_height}
            )
            # Delete transactions and blocks after fork
            session.execute(
                text("DELETE FROM transactions WHERE block_height > :fork"),
                {'fork': fork_height}
            )
            session.execute(
                text("DELETE FROM blocks WHERE height > :fork"),
                {'fork': fork_height}
            )
            # Revert supply: recalculate from coinbase rewards up to fork height
            # (NOT from UTXOs, since we just reset spent flags above which
            # would inflate the count)
            session.execute(
                text("""UPDATE supply SET total_minted = (
                            SELECT COALESCE(SUM(t.amount), 0) FROM (
                                SELECT SUM(
                                    (jsonb_array_elements(outputs)->>'amount')::DECIMAL
                                ) AS amount
                                FROM transactions
                                WHERE block_height <= :fork
                                  AND (inputs IS NULL OR inputs = '[]'::jsonb)
                            ) t
                        ) WHERE id = 1"""),
                {'fork': fork_height}
            )
            session.commit()

        # Invalidate difficulty cache entries above fork height
        self.difficulty_cache = {
            k: v for k, v in self.difficulty_cache.items() if k <= fork_height
        }

        logger.info(f"Fork resolved: reverted to height {fork_height}")

    def get_emission_stats(self, db_manager) -> Dict:
        """Get current emission statistics including tail emission info."""
        height = db_manager.get_current_height()
        supply = db_manager.get_total_supply()
        era = height // Config.HALVING_INTERVAL if height >= 0 else 0
        current_reward = self.calculate_reward(max(0, height), supply)
        blocks_until_halving = Config.HALVING_INTERVAL - (height % Config.HALVING_INTERVAL) if height >= 0 else Config.HALVING_INTERVAL

        # Determine if we are in tail emission phase
        PHI = Decimal('1.618033988749895')
        phi_reward = Config.INITIAL_REWARD / (PHI ** era) if era >= 0 else Config.INITIAL_REWARD
        in_tail_emission = phi_reward < Config.TAIL_EMISSION_REWARD

        return {
            'current_height': height,
            'total_supply': float(supply),
            'supply_cap': float(Config.MAX_SUPPLY),
            'current_reward': float(current_reward),
            'current_era': era,
            'percent_emitted': float(supply / Config.MAX_SUPPLY * 100) if Config.MAX_SUPPLY > 0 else 0,
            'blocks_until_halving': blocks_until_halving,
            'hours_until_halving': (blocks_until_halving * Config.TARGET_BLOCK_TIME) / 3600,
            'halving_interval': Config.HALVING_INTERVAL,
            'phi': Config.PHI,
            'target_block_time': Config.TARGET_BLOCK_TIME,
            'tail_emission_reward': float(Config.TAIL_EMISSION_REWARD),
            'in_tail_emission': in_tail_emission,
        }
