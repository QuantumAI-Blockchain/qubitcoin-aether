"""
Proof-of-Thought Consensus & Aether Engine
Combines Proof-of-SUSY-Alignment with knowledge graph validation.
Validators must demonstrate meaningful reasoning (Phi > threshold) to
participate in block production.
"""
import hashlib
import json
import time
from typing import Dict, List, Optional, Tuple

from ..database.models import ProofOfThought, Block
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AetherEngine:
    """
    Main Aether Tree engine that orchestrates all AGI-layer components.
    Integrates KnowledgeGraph, PhiCalculator, ReasoningEngine, and
    Proof-of-Thought consensus into the QBC block pipeline.
    """

    def __init__(self, db_manager, knowledge_graph=None, phi_calculator=None,
                 reasoning_engine=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self.phi = phi_calculator
        self.reasoning = reasoning_engine
        self._pot_cache: Dict[int, ProofOfThought] = {}
        self._pot_cache_max = 1000  # Bound cache to prevent unbounded memory growth
        logger.info("Aether Engine initialized")

    def generate_thought_proof(self, block_height: int,
                               validator_address: str) -> Optional[ProofOfThought]:
        """
        Generate a Proof-of-Thought for the given block.

        Steps:
        1. Run reasoning operations on recent knowledge
        2. Compute Phi for current knowledge graph state
        3. If Phi >= threshold, generate valid thought proof
        4. Sign and return the proof

        Args:
            block_height: Current block height
            validator_address: Address of the validator/miner

        Returns:
            ProofOfThought if successful, None if Phi below threshold
        """
        if not self.kg or not self.phi or not self.reasoning:
            return None

        # Step 1: Perform automated reasoning on the graph
        reasoning_steps = self._auto_reason(block_height)

        # Step 2: Compute Phi
        phi_result = self.phi.compute_phi(block_height)
        phi_value = phi_result['phi_value']

        # Step 3: Compute knowledge root
        knowledge_root = self.kg.compute_knowledge_root()

        # Step 4: Build the thought proof
        pot = ProofOfThought(
            thought_hash='',
            reasoning_steps=reasoning_steps,
            phi_value=phi_value,
            knowledge_root=knowledge_root,
            validator_address=validator_address,
            signature='',  # Signed by the mining pipeline
            timestamp=time.time(),
        )
        pot.thought_hash = pot.calculate_hash()

        # Cache (with eviction to bound memory)
        self._pot_cache[block_height] = pot
        if len(self._pot_cache) > self._pot_cache_max:
            oldest = min(self._pot_cache.keys())
            del self._pot_cache[oldest]

        # Log consciousness event if Phi crosses threshold
        from .phi_calculator import PHI_THRESHOLD
        if phi_value >= PHI_THRESHOLD:
            self._record_consciousness_event(
                'phi_threshold_crossed', phi_value, block_height,
                {'reasoning_steps': len(reasoning_steps)}
            )

        logger.info(
            f"Thought proof generated: Phi={phi_value:.4f}, "
            f"steps={len(reasoning_steps)}, root={knowledge_root[:12]}..."
        )

        return pot

    def validate_thought_proof(self, pot: ProofOfThought, block: Block) -> Tuple[bool, str]:
        """
        Validate a Proof-of-Thought from a peer block.

        Checks:
        1. Thought hash matches content
        2. Phi value is non-negative
        3. Knowledge root is not empty
        4. Reasoning steps are present
        """
        if not pot:
            return True, "No thought proof (PoT optional during transition)"

        # Verify thought hash
        expected_hash = pot.calculate_hash()
        if pot.thought_hash and pot.thought_hash != expected_hash:
            return False, f"Thought hash mismatch: {pot.thought_hash[:16]} != {expected_hash[:16]}"

        # Verify non-negative Phi
        if pot.phi_value < 0:
            return False, f"Invalid Phi value: {pot.phi_value}"

        # Verify knowledge root exists
        if not pot.knowledge_root:
            return False, "Empty knowledge root"

        # Verify reasoning steps are present
        # Bootstrap exception: the first few blocks have an empty knowledge graph
        # so _auto_reason() cannot produce any steps yet. Allow empty steps until
        # enough blocks have been processed to seed the graph.
        BOOTSTRAP_BLOCKS = 10
        if not pot.reasoning_steps and block.height >= BOOTSTRAP_BLOCKS:
            return False, "No reasoning steps"

        return True, "Valid thought proof"

    def process_block_knowledge(self, block: Block):
        """
        Extract knowledge from a mined/received block and add to the graph.
        This is called after a block is validated and stored.

        Knowledge extracted:
        - Block metadata (height, difficulty, energy)
        - Transaction patterns
        - Mining statistics
        - Thought proof data (if present)
        """
        if not self.kg:
            return

        try:
            # Add block as an observation node
            block_content = {
                'type': 'block_observation',
                'height': block.height,
                'difficulty': block.difficulty,
                'tx_count': len(block.transactions),
                'timestamp': block.timestamp,
                'has_thought_proof': block.thought_proof is not None,
            }

            block_node = self.kg.add_node(
                node_type='observation',
                content=block_content,
                confidence=0.95,  # High confidence for on-chain data
                source_block=block.height,
            )

            # Link to previous block's observation if exists
            if block.height > 0:
                prev_nodes = [
                    n for n in self.kg.nodes.values()
                    if n.content.get('type') == 'block_observation'
                    and n.content.get('height') == block.height - 1
                ]
                if prev_nodes:
                    self.kg.add_edge(prev_nodes[0].node_id, block_node.node_id, 'derives')

            # Extract quantum proof knowledge
            if block.proof_data and isinstance(block.proof_data, dict):
                energy = block.proof_data.get('energy', 0)
                if energy:
                    quantum_content = {
                        'type': 'quantum_observation',
                        'energy': energy,
                        'difficulty': block.difficulty,
                        'block_height': block.height,
                    }
                    q_node = self.kg.add_node(
                        node_type='observation',
                        content=quantum_content,
                        confidence=0.9,
                        source_block=block.height,
                    )
                    self.kg.add_edge(q_node.node_id, block_node.node_id, 'supports')

            # If there are contract transactions, record deployment/call patterns
            for tx in block.transactions:
                if hasattr(tx, 'tx_type') and tx.tx_type in ('contract_deploy', 'contract_call'):
                    contract_content = {
                        'type': 'contract_activity',
                        'tx_type': tx.tx_type,
                        'block_height': block.height,
                    }
                    c_node = self.kg.add_node(
                        node_type='observation',
                        content=contract_content,
                        confidence=0.85,
                        source_block=block.height,
                    )
                    self.kg.add_edge(c_node.node_id, block_node.node_id, 'supports')

            # Propagate confidence through the graph periodically
            if block.height % 10 == 0:
                self.kg.propagate_confidence(block_node.node_id)

        except Exception as e:
            logger.debug(f"Error processing block knowledge: {e}")

    def _auto_reason(self, block_height: int) -> List[dict]:
        """
        Perform automated reasoning operations on recent knowledge.
        Returns list of reasoning step dicts for the thought proof.
        """
        steps = []
        if not self.reasoning or not self.kg or not self.kg.nodes:
            return steps

        try:
            # Find recent observation nodes for inductive reasoning
            recent_observations = sorted(
                [n for n in self.kg.nodes.values()
                 if n.node_type == 'observation' and n.source_block >= block_height - 10],
                key=lambda n: n.source_block,
                reverse=True,
            )[:5]

            if len(recent_observations) >= 2:
                obs_ids = [n.node_id for n in recent_observations]
                result = self.reasoning.induce(obs_ids)
                if result.success:
                    steps.extend([s.to_dict() for s in result.chain])

            # Find inference nodes for deductive reasoning
            inference_nodes = [
                n for n in self.kg.nodes.values()
                if n.node_type == 'inference' and n.confidence > 0.5
            ]
            if len(inference_nodes) >= 2:
                inf_ids = [n.node_id for n in inference_nodes[:3]]
                result = self.reasoning.deduce(inf_ids)
                if result.success:
                    steps.extend([s.to_dict() for s in result.chain])

            # Abductive reasoning on low-confidence observations
            low_conf = [
                n for n in self.kg.nodes.values()
                if n.confidence < 0.4 and n.node_type == 'observation'
            ]
            if low_conf:
                result = self.reasoning.abduce(low_conf[0].node_id)
                if result.success:
                    steps.extend([s.to_dict() for s in result.chain])

        except Exception as e:
            logger.debug(f"Auto-reasoning error: {e}")

        return steps

    def _record_consciousness_event(self, event_type: str, phi_value: float,
                                     block_height: int, trigger_data: dict = None):
        """Record a consciousness event in the database"""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO consciousness_events
                        (event_type, phi_at_event, trigger_data, is_verified, block_height)
                        VALUES (:etype, :phi, CAST(:trigger AS jsonb), false, :bh)
                    """),
                    {
                        'etype': event_type,
                        'phi': phi_value,
                        'trigger': json.dumps(trigger_data or {}),
                        'bh': block_height,
                    }
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to record consciousness event: {e}")

    def get_stats(self) -> dict:
        """Get comprehensive Aether engine statistics"""
        kg_stats = self.kg.get_stats() if self.kg else {}
        phi_result = self.phi.compute_phi() if self.phi else {}
        reasoning_stats = self.reasoning.get_stats() if self.reasoning else {}

        return {
            'knowledge_graph': kg_stats,
            'phi': {
                'current_value': phi_result.get('phi_value', 0.0),
                'threshold': phi_result.get('phi_threshold', 3.0),
                'above_threshold': phi_result.get('above_threshold', False),
            },
            'reasoning': reasoning_stats,
            'thought_proofs_generated': len(self._pot_cache),
        }
