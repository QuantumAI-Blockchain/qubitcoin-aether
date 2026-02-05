"""
Consensus engine for Qubitcoin
Handles difficulty adjustment, golden ratio rewards, and validation
"""
from decimal import Decimal
from typing import Tuple, Optional
import time
import asyncio  # Added for async pull loop
from ..config import Config
from ..database.models import Block, Transaction
from ..quantum.engine import QuantumEngine
from ..quantum.crypto import CryptoManager
from ..utils.logger import get_logger
logger = get_logger(__name__)
class ConsensusEngine:
    """Manages consensus rules and validation"""
    def __init__(self, quantum_engine: QuantumEngine, db_manager, p2p_network):  # p2p for queries
        """Initialize consensus engine"""
        self.quantum = quantum_engine
        self.crypto = CryptoManager()
        self.db = db_manager
        self.p2p = p2p_network  # For send_message in pull
        self.difficulty_cache = {}
        logger.info("✅ Consensus engine initialized (SUSY Economics)")
    def calculate_reward(self, height: int, total_supply: Decimal) -> Decimal:
        """
        Calculate block reward with golden ratio halvings (SUSY Economics)
        Uses φ (phi) = 1.618033988749895 for halvings
        Era 0: 15.27 QBC
        Era 1: 9.437 QBC (15.27 ÷ 1.618)
        Era 2: 5.833 QBC (9.437 ÷ 1.618)
        Args:
            height: Block height
            total_supply: Current total supply
        Returns:
            Reward amount
        """
        # Golden ratio constant (φ) - fundamental to SUSY Economics
        PHI = Decimal('1.618033988749895')
        # Calculate which era (halving epoch) we're in
        era = height // Config.HALVING_INTERVAL
        # Base reward with golden ratio halvings
        base_reward = Config.INITIAL_REWARD / (PHI ** era)
        # Ensure we don't exceed max supply
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
        Args:
            height: Current block height
            db_manager: Database manager instance
        Returns:
            Difficulty value
        """
        # Genesis or early blocks
        if height < Config.DIFFICULTY_ADJUSTMENT_INTERVAL:
            return Config.INITIAL_DIFFICULTY
        # Check cache
        adjustment_height = (height // Config.DIFFICULTY_ADJUSTMENT_INTERVAL) * Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        if adjustment_height in self.difficulty_cache:
            return self.difficulty_cache[adjustment_height]
        # Get blocks for time calculation
        prev_adjustment = db_manager.get_block(
            adjustment_height - Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        )
        last_block = db_manager.get_block(adjustment_height - 1)
        if not prev_adjustment or not last_block:
            return Config.INITIAL_DIFFICULTY
        # Calculate actual time taken
        actual_time = last_block.timestamp - prev_adjustment.timestamp
        expected_time = Config.TARGET_BLOCK_TIME * Config.DIFFICULTY_ADJUSTMENT_INTERVAL
        # Get previous difficulty
        prev_difficulty = last_block.difficulty
        # Adjust difficulty (limit to 4x change)
        ratio = expected_time / actual_time
        ratio = max(0.25, min(4.0, ratio))
        new_difficulty = prev_difficulty * ratio
        new_difficulty = max(0.1, min(1.0, new_difficulty))
        # Cache result
        self.difficulty_cache[adjustment_height] = new_difficulty
        logger.info(
            f"Difficulty adjusted at {height}: "
            f"{prev_difficulty:.4f} -> {new_difficulty:.4f} (ratio: {ratio:.2f})"
        )
        return new_difficulty
    def validate_block(self, block: Block, prev_block: Optional[Block],
                      db_manager) -> Tuple[bool, str]:
        """
        Comprehensive block validation
        Args:
            block: Block to validate
            prev_block: Previous block (None for genesis)
            db_manager: Database manager
        Returns:
            (is_valid, reason)
        """
        try:
            # Validate height sequence
            expected_height = (prev_block.height + 1) if prev_block else 0
            if block.height != expected_height:
                return False, f"Invalid height: {block.height} != {expected_height}"
            # Validate prev_hash - USE STORED HASH
            expected_prev_hash = prev_block.block_hash if prev_block else '0' * 64
            if block.prev_hash != expected_prev_hash:
                return False, "Invalid prev_hash"
            # Validate difficulty
            expected_difficulty = self.calculate_difficulty(block.height, db_manager)
            if abs(block.difficulty - expected_difficulty) > 0.001:
                return False, f"Invalid difficulty: {block.difficulty} != {expected_difficulty}"
            # Validate quantum proof
            proof = block.proof_data
            valid, reason = self.quantum.validate_proof(
                params=proof['params'],
                hamiltonian=proof['challenge'],
                claimed_energy=proof['energy'],
                difficulty=block.difficulty
            )
            if not valid:
                return False, f"Invalid quantum proof: {reason}"
            # Validate proof signature
            pk = bytes.fromhex(proof['public_key'])
            msg = str(proof['params']).encode()
            sig = bytes.fromhex(proof['signature'])
            from ..quantum.crypto import Dilithium2
            if not Dilithium2.verify(pk, msg, sig):
                return False, "Invalid proof signature"
            # Validate transactions
            total_fees = Decimal(0)
            coinbase_count = 0
            for tx in block.transactions:
                # Check for coinbase
                if len(tx.inputs) == 0:
                    coinbase_count += 1
                    if coinbase_count > 1:
                        return False, "Multiple coinbase transactions"
                    # Validate coinbase amount
                    total_supply = db_manager.get_total_supply()
                    expected_reward = self.calculate_reward(block.height, total_supply)
                    coinbase_amount = sum(Decimal(o['amount']) for o in tx.outputs)
                    if coinbase_amount > expected_reward + total_fees:
                        return False, f"Excessive coinbase: {coinbase_amount}"
                    continue
                # Validate regular transaction
                if not self.validate_transaction(tx, db_manager):
                    return False, f"Invalid transaction: {tx.txid}"
                total_fees += tx.fee
            # Ensure coinbase exists
            if coinbase_count == 0:
                return False, "No coinbase transaction"
            # Validate timestamp (not too far in future)
            if block.timestamp > time.time() + 7200: # 2 hours
                return False, "Block timestamp too far in future"
            logger.debug(f"Block {block.height} validated successfully")
            return True, "Valid"
        except Exception as e:
            logger.error(f"Block validation error: {e}")
            return False, f"Validation exception: {str(e)}"
    def validate_transaction(self, tx: Transaction, db_manager) -> bool:
        """
        Validate transaction
        Args:
            tx: Transaction to validate
            db_manager: Database manager
        Returns:
            True if valid
        """
        try:
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
            # Verify inputs exist and sum
            input_total = Decimal(0)
            for inp in tx.inputs:
                utxos = db_manager.get_utxos(inp.get('address', ''))
                utxo = next((u for u in utxos if u.txid == inp['txid'] and u.vout == inp['vout']), None)
                if not utxo or utxo.spent:
                    return False
                input_total += utxo.amount
            # Verify outputs
            output_total = sum(Decimal(o['amount']) for o in tx.outputs)
            # Verify fee
            if input_total < output_total + tx.fee:
                return False
            return True
        except Exception as e:
            logger.error(f"Transaction validation error: {e}")
            return False
    async def resolve_fork(self, new_block: Block, sender_id: str):
        """
        Resolve fork by adopting longer valid chain from peer
        Args:
            new_block: Received block from peer (tip of longer chain)
            sender_id: Sending peer ID (for requesting chain)
        """
        current_height = self.db.get_current_height()
        if new_block.height <= current_height:
            return
        logger.info(f"Resolving fork: Peer {sender_id} has higher chain ({new_block.height} > {current_height})")
        # Pull and store blocks sequentially from current+1 to peer_height
        for height in range(current_height + 1, new_block.height + 1):
            # Request block
            await self.p2p.send_message(sender_id, 'get_block', {'height': height})
            # Await response (handled in _handle_message 'block'—validates/stores)
            await asyncio.sleep(0.1)  # Rate limit/await handling; adjust for perf
        # After pull, reorg local if needed (rollback above new common ancestor)
        with self.db.get_session() as session:
            fork_height = current_height  # Assume full pull; refine with hash check if needed
            session.execute(text("DELETE FROM blocks WHERE height > :fork"), {'fork': fork_height})
            session.execute(text("DELETE FROM transactions WHERE block_height > :fork"), {'fork': fork_height})
            session.execute(text("UPDATE utxos SET spent = false, spent_by = NULL WHERE block_height > :fork"), {'fork': fork_height})
            session.commit()
        logger.info(f"Fork resolved: Adopted chain to height {new_block.height}")
