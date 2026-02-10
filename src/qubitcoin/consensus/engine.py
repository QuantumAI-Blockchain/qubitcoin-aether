"""
Consensus engine for Qubitcoin
Handles difficulty adjustment, golden ratio rewards, and validation
"""
from decimal import Decimal
from typing import Tuple, Optional
import time
import asyncio
from ..config import Config
from ..database.models import Block, Transaction
from ..quantum.engine import QuantumEngine
from ..quantum.crypto import CryptoManager
from ..utils.logger import get_logger

logger = get_logger(__name__)

class ConsensusEngine:
    """Manages consensus rules and validation"""

    def __init__(self, quantum_engine: QuantumEngine, db_manager, p2p_network):
        """Initialize consensus engine"""
        logger.info("🔍 ConsensusEngine.__init__ starting...")
        logger.info("🔍 Setting quantum reference...")
        self.quantum = quantum_engine

        logger.info("🔍 Initializing CryptoManager...")
        self.crypto = CryptoManager()
        logger.info("✅ CryptoManager initialized")

        logger.info("🔍 Setting db reference...")
        self.db = db_manager

        logger.info("🔍 Setting p2p reference...")
        self.p2p = p2p_network

        logger.info("🔍 Creating difficulty cache...")
        self.difficulty_cache = {}

        logger.info("✅ Consensus engine initialized (SUSY Economics)")

    def calculate_reward(self, height: int, total_supply: Decimal) -> Decimal:
        """Calculate block reward with golden ratio halvings"""
        PHI = Decimal('1.618033988749895')
        era = height // Config.HALVING_INTERVAL
        base_reward = Config.INITIAL_REWARD / (PHI ** era)
        remaining = Config.MAX_SUPPLY - total_supply
        reward = min(base_reward, remaining)

        if reward <= 0:
            logger.warning(f"Max supply reached at height {height}")
            return Decimal(0)

        logger.debug(f"Block {height}: Era {era}, Reward {reward:.8f} QBC")
        return reward

    def calculate_difficulty(self, height: int, db_manager) -> float:
        """
        Calculate difficulty with periodic adjustment
        Optimized to avoid timeouts at adjustment intervals
        """
        if height < Config.DIFFICULTY_ADJUSTMENT_INTERVAL:
            return Config.INITIAL_DIFFICULTY

        adjustment_height = (height // Config.DIFFICULTY_ADJUSTMENT_INTERVAL) * Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        if adjustment_height in self.difficulty_cache:
            return self.difficulty_cache[adjustment_height]

        try:
            prev_adjustment = db_manager.get_block(adjustment_height - Config.DIFFICULTY_ADJUSTMENT_INTERVAL)
            last_block = db_manager.get_block(adjustment_height - 1)

            if not prev_adjustment or not last_block:
                logger.warning(f"Missing blocks for difficulty calc at {height}, using default")
                return Config.INITIAL_DIFFICULTY

            # Extract timestamps and difficulty - safely handle any data structure
            if isinstance(last_block, dict):
                last_time = float(last_block.get('created_at', 0) or 0)
                # Safely extract difficulty, handling nested dicts
                diff_val = last_block.get('difficulty', Config.INITIAL_DIFFICULTY)
                if isinstance(diff_val, (dict, object)):
                    try:
                        prev_difficulty = float(diff_val.get('difficulty', Config.INITIAL_DIFFICULTY) if isinstance(diff_val, dict) else getattr(diff_val, 'difficulty', Config.INITIAL_DIFFICULTY))
                    except:
                        prev_difficulty = Config.INITIAL_DIFFICULTY
                else:
                    prev_difficulty = float(diff_val)
            else:
                last_time = float(getattr(last_block, 'created_at', getattr(last_block, 'timestamp', 0)) or 0)
                diff_val = getattr(last_block, 'difficulty', Config.INITIAL_DIFFICULTY)
                try:
                    prev_difficulty = float(diff_val)
                except (TypeError, ValueError):
                    prev_difficulty = Config.INITIAL_DIFFICULTY

            if isinstance(prev_adjustment, dict):
                prev_time = float(prev_adjustment.get('created_at', 0) or 0)
            else:
                prev_time = float(getattr(prev_adjustment, 'created_at', getattr(prev_adjustment, 'timestamp', 0)) or 0)

            if last_time <= prev_time or prev_time == 0 or last_time == 0:
                logger.warning(f"Invalid timestamps for difficulty calc, using previous")
                return prev_difficulty

            actual_time = last_time - prev_time
            expected_time = Config.TARGET_BLOCK_TIME * Config.DIFFICULTY_ADJUSTMENT_INTERVAL

            ratio = expected_time / actual_time
            ratio = max(0.25, min(4.0, ratio))

            new_difficulty = prev_difficulty * ratio
            new_difficulty = max(0.1, min(1.0, new_difficulty))

            self.difficulty_cache[adjustment_height] = new_difficulty

            logger.info(
                f"Difficulty adjusted at height {height}: "
                f"{prev_difficulty:.6f} -> {new_difficulty:.6f} "
                f"(ratio: {ratio:.2f}, time: {actual_time:.1f}s vs {expected_time:.1f}s)"
            )

            return new_difficulty

        except Exception as e:
            logger.error(f"Error calculating difficulty at height {height}: {e}", exc_info=True)
            if adjustment_height > Config.DIFFICULTY_ADJUSTMENT_INTERVAL:
                return self.difficulty_cache.get(
                    adjustment_height - Config.DIFFICULTY_ADJUSTMENT_INTERVAL,
                    Config.INITIAL_DIFFICULTY
                )
            return Config.INITIAL_DIFFICULTY

    def validate_block(self, block: Block, prev_block: Optional[Block], db_manager) -> Tuple[bool, str]:
        """Comprehensive block validation"""
        try:
            expected_height = (prev_block.height + 1) if prev_block else 0
            if block.height != expected_height:
                return False, f"Invalid height: {block.height} != {expected_height}"

            expected_prev_hash = prev_block.block_hash if prev_block else '0' * 64
            if block.prev_hash != expected_prev_hash:
                return False, "Invalid prev_hash"

            expected_difficulty = self.calculate_difficulty(block.height, db_manager)
            if abs(block.difficulty - expected_difficulty) > 0.001:
                return False, f"Invalid difficulty: {block.difficulty} != {expected_difficulty}"

            proof = block.proof_data
            valid, reason = self.quantum.validate_proof(
                params=proof['params'],
                hamiltonian=proof['challenge'],
                claimed_energy=proof['energy'],
                difficulty=block.difficulty
            )
            if not valid:
                return False, f"Invalid quantum proof: {reason}"

            pk = bytes.fromhex(proof['public_key'])
            msg = str(proof['params']).encode()
            sig = bytes.fromhex(proof['signature'])
            from ..quantum.crypto import Dilithium2
            if not Dilithium2.verify(pk, msg, sig):
                return False, "Invalid proof signature"

            total_fees = Decimal(0)
            coinbase_count = 0
            for tx in block.transactions:
                if len(tx.inputs) == 0:
                    coinbase_count += 1
                    if coinbase_count > 1:
                        return False, "Multiple coinbase transactions"
                    total_supply = db_manager.get_total_supply()
                    expected_reward = self.calculate_reward(block.height, total_supply)
                    coinbase_amount = sum(Decimal(o['amount']) for o in tx.outputs)
                    if coinbase_amount > expected_reward + total_fees:
                        return False, f"Excessive coinbase: {coinbase_amount}"
                    continue
                if not self.validate_transaction(tx, db_manager):
                    return False, f"Invalid transaction: {tx.txid}"
                total_fees += tx.fee

            if coinbase_count == 0:
                return False, "No coinbase transaction"
            if block.timestamp > time.time() + 7200:
                return False, "Block timestamp too far in future"

            logger.debug(f"Block {block.height} validated successfully")
            return True, "Valid"
        except Exception as e:
            logger.error(f"Block validation error: {e}")
            return False, f"Validation exception: {str(e)}"

    def validate_transaction(self, tx: Transaction, db_manager) -> bool:
        """Validate transaction"""
        try:
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

            input_total = Decimal(0)
            for inp in tx.inputs:
                utxos = db_manager.get_utxos(inp.get('address', ''))
                utxo = next((u for u in utxos if u.txid == inp['txid'] and u.vout == inp['vout']), None)
                if not utxo or utxo.spent:
                    return False
                input_total += utxo.amount

            output_total = sum(Decimal(o['amount']) for o in tx.outputs)
            if input_total < output_total + tx.fee:
                return False
            return True
        except Exception as e:
            logger.error(f"Transaction validation error: {e}")
            return False

    async def resolve_fork(self, new_block: Block, sender_id: str):
        """Resolve fork by adopting longer valid chain"""
        current_height = self.db.get_current_height()
        if new_block.height <= current_height:
            return

        logger.info(f"Resolving fork: Peer {sender_id} has higher chain")
        for height in range(current_height + 1, new_block.height + 1):
            await self.p2p.send_message(sender_id, 'get_block', {'height': height})
            await asyncio.sleep(0.1)

        with self.db.get_session() as session:
            from sqlalchemy import text
            fork_height = current_height
            session.execute(text("DELETE FROM blocks WHERE height > :fork"), {'fork': fork_height})
            session.execute(text("DELETE FROM transactions WHERE block_height > :fork"), {'fork': fork_height})
            session.execute(text("UPDATE utxos SET spent = false WHERE block_height > :fork"), {'fork': fork_height})
            session.commit()

        logger.info(f"Fork resolved to height {new_block.height}")
