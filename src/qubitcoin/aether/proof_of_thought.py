"""
Proof-of-Thought Consensus & Aether Engine
Combines Proof-of-SUSY-Alignment with knowledge graph validation.
Validators must demonstrate meaningful reasoning (Phi > threshold) to
participate in block production.
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

from ..database.models import ProofOfThought, Block
from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AetherEngine:
    """
    Main Aether Tree engine that orchestrates all AGI-layer components.
    Integrates KnowledgeGraph, PhiCalculator, ReasoningEngine, and
    Proof-of-Thought consensus into the QBC block pipeline.

    AGI subsystems (Improvements #2-#9):
    - GATReasoner: Neural reasoning over knowledge graph (#2)
    - CausalDiscovery: Causal edge discovery via PC algorithm (#3)
    - DebateProtocol: Adversarial debate between Sephirot (#5)
    - TemporalEngine: Time-series analysis and prediction (#6)
    - ConceptFormation: Hierarchical concept abstraction (#8)
    - MetacognitiveLoop: Reasoning quality self-evaluation (#9)
    """

    def __init__(self, db_manager, knowledge_graph=None, phi_calculator=None,
                 reasoning_engine=None, llm_manager=None, pineal=None,
                 pot_protocol=None, csf_transport=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self.phi = phi_calculator
        self.reasoning = reasoning_engine
        self.llm_manager = llm_manager
        self.pineal = pineal  # PinealOrchestrator for circadian phases
        self.pot_protocol = pot_protocol  # ProofOfThoughtProtocol instance
        self.csf = csf_transport  # CSFTransport for inter-Sephirot routing
        self._pot_cache: Dict[int, ProofOfThought] = {}
        self._pot_cache_max = 1000  # Bound cache to prevent unbounded memory growth

        # Sephirot cognitive nodes — initialized lazily
        self._sephirot: Optional[dict] = None

        # ConsciousnessDashboard — wired after RPC app creation (see node.py)
        self.consciousness_dashboard = None

        # --- AGI Improvement Subsystems ---
        # #2: Graph Attention Network Reasoner
        self.neural_reasoner = None
        try:
            from .neural_reasoner import GATReasoner
            self.neural_reasoner = GATReasoner()
        except Exception as e:
            logger.debug(f"GATReasoner init failed: {e}")

        # #3: Causal Discovery Engine
        self.causal_engine = None
        try:
            from .causal_engine import CausalDiscovery
            self.causal_engine = CausalDiscovery(knowledge_graph)
        except Exception as e:
            logger.debug(f"CausalDiscovery init failed: {e}")

        # #5: Adversarial Debate Protocol
        self.debate_protocol = None
        try:
            from .debate import DebateProtocol
            self.debate_protocol = DebateProtocol(knowledge_graph)
        except Exception as e:
            logger.debug(f"DebateProtocol init failed: {e}")

        # #6: Temporal Reasoning Engine
        self.temporal_engine = None
        try:
            from .temporal import TemporalEngine
            self.temporal_engine = TemporalEngine(knowledge_graph)
        except Exception as e:
            logger.debug(f"TemporalEngine init failed: {e}")

        # #8: Concept Formation
        self.concept_formation = None
        try:
            from .concept_formation import ConceptFormation
            vector_index = knowledge_graph.vector_index if knowledge_graph else None
            self.concept_formation = ConceptFormation(knowledge_graph, vector_index)
        except Exception as e:
            logger.debug(f"ConceptFormation init failed: {e}")

        # #9: Metacognitive Self-Evaluation Loop
        self.metacognition = None
        try:
            from .metacognition import MetacognitiveLoop
            self.metacognition = MetacognitiveLoop(knowledge_graph)
        except Exception as e:
            logger.debug(f"MetacognitiveLoop init failed: {e}")

        # Phase 2.4: Three-Tier Memory Manager
        self.memory_manager = None
        try:
            from .memory_manager import MemoryManager
            self.memory_manager = MemoryManager(knowledge_graph, capacity=50)
        except Exception as e:
            logger.debug(f"MemoryManager init failed: {e}")

        # Phase 5.1: Curiosity-driven goal formation
        self._curiosity_goals: List[dict] = []
        self._curiosity_stats = {
            'goals_generated': 0, 'goals_completed': 0, 'goals_failed': 0,
        }

        # Phase 5.4: Emergent communication protocol
        self._pending_digest: Optional[dict] = None
        self._seen_digests: set = set()
        self._digests_created: int = 0
        self._digests_received: int = 0
        self._nodes_from_peers: int = 0
        self._peer_consensus_boosts: int = 0

        # Phase 6: On-chain AGI integration
        self.on_chain = None

        # AG8: Phi milestone tracking — system behavior changes at thresholds
        self._phi_milestones_crossed: set = set()
        self._phi_exploration_boost: float = 1.0  # Multiplier for abductive reasoning
        self._phi_obs_window_bonus: int = 0       # Extra blocks for observation window

        logger.info("Aether Engine initialized (with AGI subsystems)")

    def _ensure_sephirot(self) -> dict:
        """Lazily initialize the 10 Sephirot nodes and restore saved state."""
        if self._sephirot is None:
            try:
                from .sephirot_nodes import create_all_nodes
                self._sephirot = create_all_nodes(self.kg)
                logger.info(f"Sephirot nodes initialized: {len(self._sephirot)} nodes")
                # Restore persisted state from DB
                self._load_sephirot_state()
            except Exception as e:
                logger.warning(f"Sephirot init failed (cognitive nodes unavailable): {e}")
                self._sephirot = {}
        return self._sephirot

    @property
    def sephirot(self) -> dict:
        """Get the Sephirot nodes dict."""
        return self._ensure_sephirot()

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

        # Feed the ConsciousnessDashboard if wired
        if self.consciousness_dashboard is not None:
            try:
                self.consciousness_dashboard.record_measurement(
                    block_height=block_height,
                    phi_value=phi_value,
                    integration=phi_result.get('integration', 0.0),
                    differentiation=phi_result.get('differentiation', 0.0),
                    knowledge_nodes=phi_result.get('num_nodes', 0),
                    knowledge_edges=phi_result.get('num_edges', 0),
                )
            except Exception as e:
                logger.debug(f"ConsciousnessDashboard update failed: {e}")

        # AG8: Apply system behavior changes at Phi milestones
        self._apply_phi_milestone_effects(phi_value, block_height)

        # Log consciousness event if Phi crosses threshold
        from .phi_calculator import PHI_THRESHOLD
        if phi_value >= PHI_THRESHOLD:
            trigger = {
                'reasoning_steps': len(reasoning_steps),
                'gates_passed': phi_result.get('gates_passed', 0),
                'gates_total': phi_result.get('gates_total', 10),
                'gate_ceiling': phi_result.get('gate_ceiling', 0),
                'phi_raw': phi_result.get('phi_raw', phi_value),
            }
            self._record_consciousness_event(
                'phi_threshold_crossed', phi_value, block_height, trigger
            )

        gate_info = f", gates={phi_result.get('gates_passed', 0)}/{phi_result.get('gates_total', 10)}"
        logger.info(
            f"Thought proof generated: Phi={phi_value:.4f}, "
            f"steps={len(reasoning_steps)}, root={knowledge_root[:12]}...{gate_info}"
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
            # Compute Phi once per block (avoids redundant recomputation)
            block_phi_result = None
            if self.phi:
                try:
                    block_phi_result = self.phi.compute_phi(block.height)
                except Exception:
                    pass

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
            # Block metadata is ground truth from the chain itself
            block_node.grounding_source = 'block_oracle'

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
                    # Quantum proof data is verifiable ground truth
                    q_node.grounding_source = 'block_oracle'
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
            if block.height % Config.AETHER_CONFIDENCE_PROPAGATION_INTERVAL == 0:
                self.kg.propagate_confidence(block_node.node_id)

            # Process Proof-of-Thought protocol
            if block.height % Config.AETHER_POT_PROCESS_INTERVAL == 0:
                self._process_pot_block(block.height)

            # Route messages between Sephirot cognitive nodes
            if block.height % Config.AETHER_SEPHIROT_ROUTE_INTERVAL == 0:
                self._route_sephirot_messages(block)

            # Auto-resolve contradictions periodically
            if block.height > 0 and block.height % Config.AETHER_CONTRADICTION_RESOLVE_INTERVAL == 0:
                self.auto_resolve_contradictions(block.height)

            # Auto-generate Keter goals periodically
            if block.height > 0 and block.height % Config.AETHER_KETER_GOALS_INTERVAL == 0:
                self._auto_generate_keter_goals(block.height)

            # Boost frequently-referenced knowledge nodes periodically
            if block.height > 0 and block.height % Config.AETHER_KG_BOOST_INTERVAL == 0 and self.kg:
                self.kg.boost_referenced_nodes()

            # Self-reflection via LLM periodically
            if (block.height > 0 and block.height % Config.AETHER_SELF_REFLECT_INTERVAL == 0
                    and self.llm_manager):
                self.self_reflect(block.height)

            # Find analogies during REM-like phases
            if block.height > 0 and block.height % Config.AETHER_DREAM_ANALOGIES_INTERVAL == 0 and self.reasoning and self.kg:
                self._dream_analogies(block.height)

            # --- AGI Improvement Subsystems ---

            # #3: Causal discovery sweep
            if block.height > 0 and block.height % Config.AETHER_CAUSAL_DISCOVERY_INTERVAL == 0 and self.causal_engine:
                try:
                    self.causal_engine.discover_all_domains(block.height)
                except Exception as e:
                    logger.debug(f"Causal discovery error: {e}")

            # #5: Adversarial debate on recent inferences
            if block.height > 0 and block.height % Config.AETHER_DEBATE_INTERVAL == 0 and self.debate_protocol:
                try:
                    self.debate_protocol.run_periodic_debates(block.height)
                    # Reward Tiferet for successful debate facilitation
                    self._reward_sephirah('debate', True, 0.05)
                except Exception as e:
                    logger.debug(f"Debate protocol error: {e}")

            # #6: Temporal reasoning every block
            if self.temporal_engine:
                try:
                    temporal_data = {
                        'difficulty': block.difficulty,
                        'tx_count': len(block.transactions),
                        'knowledge_nodes': len(self.kg.nodes) if self.kg else 0,
                        'knowledge_edges': len(self.kg.edges) if self.kg else 0,
                    }
                    if block_phi_result:
                        temporal_data['phi_value'] = block_phi_result.get('phi_value', 0)
                    temporal_result = self.temporal_engine.process_block(
                        block.height, temporal_data
                    )

                    # Feed temporal validation outcomes back to metacognition
                    if temporal_result.get('predictions_validated', 0) > 0:
                        accuracy = self.temporal_engine.get_accuracy()
                        if self.metacognition:
                            self.metacognition.evaluate_reasoning(
                                strategy='temporal',
                                confidence=accuracy,
                                outcome_correct=accuracy > 0.5,
                                domain='temporal_prediction',
                                block_height=block.height,
                            )
                        # Reward/penalize Yesod based on temporal prediction accuracy
                        self._reward_sephirah('temporal', accuracy > 0.5, accuracy * 0.1)

                    # Feed verified prediction outcomes to neural_reasoner
                    if self.neural_reasoner:
                        try:
                            verified = self.temporal_engine.get_verified_outcomes(
                                since_block=block.height - 200
                            )
                            for outcome in verified:
                                self.neural_reasoner.record_outcome(
                                    prediction_correct=outcome.get('correct', False)
                                )
                        except Exception as e:
                            logger.debug(f"Neural reasoner outcome feedback error: {e}")

                except Exception as e:
                    logger.debug(f"Temporal engine error: {e}")

            # #8: Concept formation + cross-domain transfer
            if block.height > 0 and block.height % Config.AETHER_CONCEPT_FORMATION_INTERVAL == 0 and self.concept_formation:
                try:
                    self.concept_formation.form_concepts_all_domains(block.height)
                    # Cross-domain transfer learning (Phase 5.2)
                    transfer_result = self.concept_formation.run_transfer_cycle(
                        block_height=block.height
                    )
                    if transfer_result.get('transfers_attempted', 0) > 0:
                        self._reward_sephirah('concept_formation', True, 0.08)
                    else:
                        # Reward concept formation even without transfer
                        self._reward_sephirah('concept_formation', True, 0.05)
                except Exception as e:
                    logger.debug(f"Concept formation error: {e}")

            # #9: Metacognition every block (lightweight)
            if self.metacognition:
                try:
                    self.metacognition.process_block(block.height)
                except Exception as e:
                    logger.debug(f"Metacognition error: {e}")

            # Phase 2.4: Memory management every block
            if self.memory_manager:
                try:
                    # Attend to the current block's observation node
                    self.memory_manager.attend(block_node.node_id, boost=0.3)
                    # Decay working memory relevance every block
                    self.memory_manager.decay()
                    # Consolidate periodically
                    if block.height > 0 and block.height % Config.AETHER_MEMORY_CONSOLIDATE_INTERVAL == 0:
                        self.memory_manager.consolidate(block.height)
                    # Episodic replay periodically
                    if block.height > 0 and block.height % Config.AETHER_EPISODIC_REPLAY_INTERVAL == 0:
                        replay_result = self.memory_manager.replay_episodes(block.height)
                        if replay_result['episodes_replayed'] > 0:
                            logger.info(
                                f"Episodic replay at block {block.height}: "
                                f"replayed={replay_result['episodes_replayed']}, "
                                f"reinforced={replay_result['reinforced']}, "
                                f"suppressed={replay_result['suppressed']}, "
                                f"promoted={replay_result['promoted_to_axiom']}"
                            )
                except Exception as e:
                    logger.debug(f"MemoryManager error: {e}")

            # Phase 5.1: Curiosity-driven exploration
            if block.height > 0 and block.height % Config.AETHER_CURIOSITY_INTERVAL == 0:
                try:
                    self._curiosity_explore(block.height)
                except Exception as e:
                    logger.debug(f"Curiosity exploration error: {e}")

            # Phase 5.4: Create knowledge digest
            if block.height > 0 and block.height % Config.AETHER_KNOWLEDGE_DIGEST_INTERVAL == 0:
                try:
                    self._pending_digest = self.create_knowledge_digest(block.height)
                    self._digests_created += 1
                except Exception as e:
                    logger.debug(f"Knowledge digest creation error: {e}")

            # Phase 6: On-chain AGI integration
            if self.on_chain and block_phi_result:
                try:
                    self.on_chain.process_block(
                        block_height=block.height,
                        phi_result=block_phi_result,
                        thought_hash=(
                            block.thought_proof.thought_hash
                            if block.thought_proof else ''
                        ),
                        knowledge_root=(
                            self.kg.compute_knowledge_root() if self.kg else ''
                        ),
                        validator_address=getattr(block, 'miner_address', ''),
                    )
                except Exception as e:
                    logger.warning(f"On-chain AGI integration error: {e}")

            # Archive old consciousness events
            if block.height > 0 and block.height % Config.AETHER_CONSCIOUSNESS_ARCHIVE_INTERVAL == 0:
                self.archive_consciousness_events()

            # Archive old reasoning operations
            if block.height > 0 and block.height % Config.AETHER_REASONING_ARCHIVE_INTERVAL == 0 and self.reasoning:
                self.reasoning.archive_old_reasoning(
                    block.height, Config.REASONING_ARCHIVE_RETAIN_BLOCKS
                )

            # Persist Sephirot state
            if block.height > 0 and block.height % Config.AETHER_SEPHIROT_PERSIST_INTERVAL == 0:
                self.save_sephirot_state()

            # Tick pineal orchestrator for circadian phase management
            if self.pineal and block.height > 0:
                phi_val = block_phi_result.get('phi_value', 0.0) if block_phi_result else 0.0
                self.pineal.tick(block.height, phi_val)

                # Phase-aware behavior (item 10.2)
                self._apply_circadian_behavior(block)

        except Exception as e:
            logger.warning(f"Error processing block knowledge: {e}", exc_info=True)

    def _process_pot_block(self, block_height: int) -> None:
        """Run the Proof-of-Thought protocol's per-block maintenance.

        Expires old tasks and logs stats periodically.
        """
        if not self.pot_protocol:
            return
        try:
            result = self.pot_protocol.process_block(block_height)
            if result.get('expired_tasks', 0) > 0:
                logger.debug(
                    f"PoT block {block_height}: expired={result['expired_tasks']}, "
                    f"open={result['open_tasks']}, validators={result['active_validators']}"
                )
        except Exception as e:
            logger.debug(f"PoT block processing error: {e}")

    def _route_sephirot_messages(self, block) -> int:
        """
        Route messages between Sephirot cognitive nodes along the Tree of
        Life topology, wiring genuine AGI subsystem outputs as context.

        Phase 5.3 Deep Integration: each Sephirah node receives enriched
        context from upstream AGI subsystems and passes its output to the
        next node in the pipeline.

        Pipeline:
          Keter (metacognition strategy) -> Chochmah (neural hints) ->
          Binah (causal verification) -> Chesed (exploration) ->
          Gevurah (safety) -> Tiferet (conflict resolution) ->
          Netzach (GAT training) -> Hod (trace formatting) ->
          Yesod (memory stats) -> Malkuth (KG mutations -> feedback to Keter)

        Returns:
            Number of messages routed.
        """
        from .sephirot import SephirahRole

        sephirot = self.sephirot
        if not sephirot:
            return 0

        # Build base block context shared by all nodes
        context = {
            'block_height': block.height,
            'timestamp': block.timestamp,
            'difficulty': block.difficulty,
            'tx_count': len(block.transactions),
            'kg_node_count': len(self.kg.nodes) if self.kg else 0,
            'kg_edge_count': len(self.kg.edges) if self.kg else 0,
            # Feed previous cycle's Malkuth stats to Keter for meta-learning
            'malkuth_stats': getattr(self, '_last_malkuth_stats', {}),
        }

        total_routed = 0
        pipeline_trace: Dict[str, dict] = {}

        def _drain_and_route(node) -> int:
            """Drain a node's outbox and route messages via CSF or direct."""
            routed = 0
            outgoing = node.get_outbox()
            for msg in outgoing:
                if self.csf:
                    # Route through CSF transport (backpressure, entanglement, priority)
                    self.csf.send(
                        source=msg.sender,
                        destination=msg.receiver,
                        payload=msg.payload,
                        msg_type='signal',
                        priority_qbc=msg.priority,
                    )
                    routed += 1
                else:
                    # Direct delivery fallback (no CSF transport available)
                    target = sephirot.get(msg.receiver)
                    if target:
                        target.receive_message(msg)
                        routed += 1
            return routed

        # --- 1. Keter: Meta-learning, pick strategy via metacognition ---
        keter = sephirot.get(SephirahRole.KETER)
        if keter:
            try:
                if self.metacognition:
                    context['recommended_strategy'] = (
                        self.metacognition.get_recommended_strategy()
                    )
                k_result = keter.process(context)
                pipeline_trace['keter'] = k_result.output
                total_routed += _drain_and_route(keter)
            except Exception as e:
                logger.warning(f"Sephirot keter process error: {e}")

        # --- 2. Chochmah: Intuition, enriched with neural reasoner hints ---
        chochmah = sephirot.get(SephirahRole.CHOCHMAH)
        if chochmah:
            try:
                neural_hints = self._get_neural_hints(block.height)
                if neural_hints:
                    context['neural_hints'] = neural_hints
                c_result = chochmah.process(context)
                pipeline_trace['chochmah'] = c_result.output
                total_routed += _drain_and_route(chochmah)
            except Exception as e:
                logger.warning(f"Sephirot chochmah process error: {e}")

        # --- 3. Binah: Logic, cross-reference with causal engine ---
        binah = sephirot.get(SephirahRole.BINAH)
        if binah:
            try:
                # Pass Chochmah output as causal reference for cross-check
                chochmah_output = pipeline_trace.get('chochmah', {})
                context['causal_insights'] = {
                    'output': chochmah_output,
                    'confidence': chochmah_output.get('neural_confidence', 0.0),
                }
                b_result = binah.process(context)
                pipeline_trace['binah'] = b_result.output
                total_routed += _drain_and_route(binah)
            except Exception as e:
                logger.warning(f"Sephirot binah process error: {e}")

        # --- 4. Chesed: Exploration (uses base context) ---
        chesed = sephirot.get(SephirahRole.CHESED)
        if chesed:
            try:
                ch_result = chesed.process(context)
                pipeline_trace['chesed'] = ch_result.output
                total_routed += _drain_and_route(chesed)
            except Exception as e:
                logger.warning(f"Sephirot chesed process error: {e}")

        # --- 5. Gevurah: Safety, enriched with consistency check ---
        gevurah = sephirot.get(SephirahRole.GEVURAH)
        if gevurah:
            try:
                safety = self._get_safety_assessment(context)
                if safety:
                    context['safety_assessment'] = safety
                g_result = gevurah.process(context)
                pipeline_trace['gevurah'] = g_result.output
                total_routed += _drain_and_route(gevurah)
            except Exception as e:
                logger.warning(f"Sephirot gevurah process error: {e}")

        # --- 6. Tiferet: Integration, conflict resolution hub ---
        tiferet = sephirot.get(SephirahRole.TIFERET)
        if tiferet:
            try:
                t_result = tiferet.process(context)
                pipeline_trace['tiferet'] = t_result.output
                total_routed += _drain_and_route(tiferet)
            except Exception as e:
                logger.warning(f"Sephirot tiferet process error: {e}")

        # --- 7. Netzach: Persistence/learning, track GAT training ---
        netzach = sephirot.get(SephirahRole.NETZACH)
        if netzach:
            try:
                gat_trained = self._try_gat_online_train(block.height)
                context['gat_trained'] = gat_trained
                n_result = netzach.process(context)
                pipeline_trace['netzach'] = n_result.output
                total_routed += _drain_and_route(netzach)
            except Exception as e:
                logger.warning(f"Sephirot netzach process error: {e}")

        # --- 8. Hod: Communication, format reasoning trace ---
        hod = sephirot.get(SephirahRole.HOD)
        if hod:
            try:
                context['pipeline_trace'] = pipeline_trace
                h_result = hod.process(context)
                pipeline_trace['hod'] = h_result.output
                total_routed += _drain_and_route(hod)
            except Exception as e:
                logger.warning(f"Sephirot hod process error: {e}")

        # --- 9. Yesod: Memory, enriched with memory manager stats ---
        yesod = sephirot.get(SephirahRole.YESOD)
        if yesod:
            try:
                if self.memory_manager:
                    context['memory_stats'] = {
                        'hit_rate': self.memory_manager.get_hit_rate(),
                        'working_memory_size': len(
                            self.memory_manager._working_memory
                        ),
                        'episodes_total': len(
                            self.memory_manager._episodes
                        ),
                    }
                y_result = yesod.process(context)
                pipeline_trace['yesod'] = y_result.output
                total_routed += _drain_and_route(yesod)
            except Exception as e:
                logger.warning(f"Sephirot yesod process error: {e}")

        # --- 10. Malkuth: Action, KG mutations -> feedback to Keter ---
        malkuth = sephirot.get(SephirahRole.MALKUTH)
        if malkuth:
            try:
                m_result = malkuth.process(context)
                pipeline_trace['malkuth'] = m_result.output
                total_routed += _drain_and_route(malkuth)

                # Feed Malkuth stats back into context for next cycle's Keter
                # (stored as instance attr so Keter sees it next iteration)
                self._last_malkuth_stats = m_result.output
            except Exception as e:
                logger.warning(f"Sephirot malkuth process error: {e}")

        # --- CSF Queue Processing: deliver routed messages to target inboxes ---
        csf_delivered = 0
        if self.csf:
            try:
                delivered_msgs = self.csf.process_queue(max_messages=100)
                for csf_msg in delivered_msgs:
                    target = sephirot.get(csf_msg.destination)
                    if target:
                        from .sephirot_nodes import NodeMessage
                        target.receive_message(NodeMessage(
                            sender=csf_msg.source,
                            receiver=csf_msg.destination,
                            payload=csf_msg.payload,
                            priority=csf_msg.priority_qbc,
                        ))
                        csf_delivered += 1
            except Exception as e:
                logger.warning(f"CSF queue processing error: {e}")

        if total_routed > 0:
            logger.debug(
                f"Routed {total_routed} Sephirot messages at block {block.height} "
                f"(pipeline nodes: {len(pipeline_trace)}, csf_delivered: {csf_delivered})"
            )

        return total_routed

    def _get_neural_hints(self, block_height: int) -> Dict[str, Any]:
        """Run neural reasoner on recent nodes and return hints dict.

        Returns an empty dict if neural reasoner is unavailable or has
        insufficient data to reason over.
        """
        if (not self.neural_reasoner or not self.kg
                or not hasattr(self.kg, 'vector_index') or not self.kg.vector_index):
            return {}

        try:
            # Pick a few recent observation nodes as query seeds
            recent = sorted(
                [n for n in self.kg.nodes.values()
                 if n.node_type == 'observation'
                 and n.source_block >= block_height - 10],
                key=lambda n: n.source_block,
                reverse=True,
            )[:3]

            if not recent:
                return {}

            query_ids = [n.node_id for n in recent]
            result = self.neural_reasoner.reason(
                self.kg, self.kg.vector_index, query_ids
            )
            return {
                'confidence': result.get('confidence', 0.0),
                'attended_nodes': result.get('attended_nodes', []),
                'suggested_edge_type': result.get('suggested_edge_type', ''),
            }
        except Exception as e:
            logger.debug(f"Neural hints error: {e}")
            return {}

    def _get_safety_assessment(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run lightweight safety checks and return assessment dict.

        Checks for recent contradictions and consistency violations in
        the knowledge graph. Returns empty dict if KG is unavailable.
        """
        if not self.kg:
            return {}

        try:
            contradictions_found = 0
            consistency_violations = 0

            # Count recent contradictions
            block_height = context.get('block_height', 0)
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    # Check if either node is from recent blocks
                    node_a = self.kg.nodes.get(edge.from_node_id)
                    node_b = self.kg.nodes.get(edge.to_node_id)
                    if node_a and node_b:
                        if (node_a.source_block >= block_height - 20
                                or node_b.source_block >= block_height - 20):
                            contradictions_found += 1

            # Check for very low confidence nodes (potential inconsistency)
            recent_nodes = [
                n for n in self.kg.nodes.values()
                if n.source_block >= block_height - 10 and n.confidence < 0.2
            ]
            consistency_violations = len(recent_nodes)

            return {
                'contradictions_found': contradictions_found,
                'consistency_violations': consistency_violations,
            }
        except Exception as e:
            logger.warning(f"Safety assessment error (Gevurah degraded): {e}")
            return {}

    def _try_gat_online_train(self, block_height: int) -> bool:
        """Attempt a single online GAT training step.

        Returns True if training was performed, False otherwise.
        Lightweight — only trains if neural_reasoner supports it
        and enough data has accumulated.
        """
        if not self.neural_reasoner or not self.kg:
            return False

        try:
            if not hasattr(self.neural_reasoner, 'train_online'):
                return False
            if not hasattr(self.kg, 'vector_index') or not self.kg.vector_index:
                return False
            result = self.neural_reasoner.train_online(
                self.kg, self.kg.vector_index
            )
            return result.get('trained', False)
        except Exception as e:
            logger.debug(f"GAT online training error: {e}")
            return False

    def _auto_reason(self, block_height: int) -> List[dict]:
        """
        Perform automated reasoning operations on recent knowledge.
        Returns list of reasoning step dicts for the thought proof.

        Uses metacognition strategy weights to prioritize which reasoning
        type runs first and how many steps each type contributes.

        Circadian metabolic rate (H3) modulates reasoning intensity:
        - Active Learning (2.0x): lower skip threshold, wider observation window
        - Deep Sleep (0.3x): higher skip threshold, narrow observation window
        """
        steps = []
        if not self.reasoning or not self.kg or not self.kg.nodes:
            return steps

        try:
            # --- Circadian metabolic rate modulation (H3) ---
            metabolic_rate = 1.0
            if self.pineal:
                rate = getattr(self.pineal, 'metabolic_rate', 1.0)
                melatonin = getattr(self.pineal, 'melatonin', None)
                inhibition = getattr(melatonin, 'inhibition_factor', 1.0) if melatonin else 1.0
                metabolic_rate = rate * inhibition

            # Metabolic rate scales: observation window, weight threshold
            # High rate (Active Learning, 2.0x) = broader search, lower cutoff
            # Low rate (Deep Sleep, 0.3x) = narrow search, higher cutoff
            obs_window = max(3, int(10 * metabolic_rate) + self._phi_obs_window_bonus)
            weight_cutoff = max(0.1, 0.3 / metabolic_rate)  # 0.15-1.0 threshold

            # --- Metacognition-guided strategy selection ---
            # Get strategy weights from metacognition + Sephirot energy (H2)
            strategy_weights = self._get_strategy_weights()

            # Layer 3: Circadian metabolic rate scales all weights (H3)
            # During Active Learning, even low-weight strategies get a chance
            # During Deep Sleep, only highest-weight strategies run
            strategy_weights = {
                k: v * metabolic_rate for k, v in strategy_weights.items()
            }

            # Sort reasoning strategies by weight (highest priority first)
            strategies = sorted(strategy_weights.items(), key=lambda x: x[1], reverse=True)

            # Find recent observation nodes (window scaled by metabolic rate)
            recent_observations = sorted(
                [n for n in self.kg.nodes.values()
                 if n.node_type == 'observation' and n.source_block >= block_height - obs_window],
                key=lambda n: n.source_block,
                reverse=True,
            )[:5]

            # Retrieve relevant nodes from working memory for additional context.
            # Pass the first recent observation as query_node_id so retrieval
            # is context-dependent (biased towards what we're reasoning about).
            if self.memory_manager:
                query_nid: Optional[int] = (
                    recent_observations[0].node_id if recent_observations else None
                )
                wm_node_ids = self.memory_manager.retrieve(
                    top_k=10, query_node_id=query_nid
                )
                # Add working-memory nodes that are observations and not already present
                existing_ids = {n.node_id for n in recent_observations}
                for nid in wm_node_ids:
                    if nid not in existing_ids:
                        node = self.kg.nodes.get(nid)
                        if node and node.node_type == 'observation':
                            recent_observations.append(node)
                            existing_ids.add(nid)

            for strategy_name, weight in strategies:
                # Skip strategies below circadian-adjusted threshold (H3)
                if weight < weight_cutoff:
                    continue

                if strategy_name == 'inductive' and len(recent_observations) >= 2:
                    obs_ids = [n.node_id for n in recent_observations]
                    result = self.reasoning.induce(obs_ids)
                    if result.success:
                        self._calibrate_conclusion(result)
                        steps.extend([s.to_dict() for s in result.chain])
                        self._record_reasoning_outcome(
                            'inductive', result.confidence, True, block_height
                        )
                        # Put conclusion into working memory
                        if self.memory_manager and result.conclusion_node_id:
                            self.memory_manager.attend(
                                result.conclusion_node_id, boost=0.5
                            )
                    else:
                        self._record_reasoning_outcome(
                            'inductive', 0.0, False, block_height
                        )

                elif strategy_name == 'deductive':
                    inference_nodes = [
                        n for n in self.kg.nodes.values()
                        if n.node_type == 'inference' and n.confidence > 0.5
                    ]
                    if len(inference_nodes) >= 2:
                        inf_ids = [n.node_id for n in inference_nodes[:3]]
                        result = self.reasoning.deduce(inf_ids)
                        if result.success:
                            self._calibrate_conclusion(result)
                            steps.extend([s.to_dict() for s in result.chain])
                            self._record_reasoning_outcome(
                                'deductive', result.confidence, True, block_height
                            )
                            # Put conclusion into working memory
                            if self.memory_manager and result.conclusion_node_id:
                                self.memory_manager.attend(
                                    result.conclusion_node_id, boost=0.5
                                )
                        else:
                            self._record_reasoning_outcome(
                                'deductive', 0.0, False, block_height
                            )

                elif strategy_name == 'abductive':
                    low_conf = [
                        n for n in self.kg.nodes.values()
                        if n.confidence < 0.4 and n.node_type == 'observation'
                    ]
                    if low_conf:
                        result = self.reasoning.abduce(low_conf[0].node_id)
                        if result.success:
                            self._calibrate_conclusion(result)
                            steps.extend([s.to_dict() for s in result.chain])
                            self._record_reasoning_outcome(
                                'abductive', result.confidence, True, block_height
                            )
                            # Put conclusion into working memory
                            if self.memory_manager and result.conclusion_node_id:
                                self.memory_manager.attend(
                                    result.conclusion_node_id, boost=0.5
                                )
                        else:
                            self._record_reasoning_outcome(
                                'abductive', 0.0, False, block_height
                            )

                elif strategy_name == 'neural':
                    if (self.neural_reasoner and self.kg
                            and hasattr(self.kg, 'vector_index') and self.kg.vector_index):
                        try:
                            recent_ids = [n.node_id for n in recent_observations[:3]]
                            if recent_ids:
                                neural_result = self.neural_reasoner.reason(
                                    self.kg, self.kg.vector_index, recent_ids
                                )
                                if neural_result.get('confidence', 0) > 0.3:
                                    steps.append({
                                        'step_type': 'neural_reasoning',
                                        'content': {
                                            'method': 'gat_neural',
                                            'confidence': neural_result['confidence'],
                                            'attended_nodes': len(
                                                neural_result.get('attended_nodes', [])
                                            ),
                                            'suggested_edge': neural_result.get(
                                                'suggested_edge_type', ''
                                            ),
                                        },
                                        'confidence': neural_result['confidence'],
                                    })
                                    self._record_reasoning_outcome(
                                        'neural', neural_result['confidence'],
                                        True, block_height
                                    )
                                else:
                                    self._record_reasoning_outcome(
                                        'neural', neural_result.get('confidence', 0),
                                        False, block_height
                                    )
                        except Exception as e:
                            logger.debug(f"Neural reasoning error: {e}")

        except Exception as e:
            logger.error(f"Auto-reasoning failed for block: {e}", exc_info=True)

        # --- LLM augmentation fallback (M3): invoke when reasoning is weak ---
        if (self.llm_manager and Config.LLM_ENABLED
                and len(steps) == 0 and recent_observations):
            try:
                # Build a brief context from recent observations
                obs_texts = []
                for obs in recent_observations[:5]:
                    content = obs.content if isinstance(obs.content, str) else str(obs.content)
                    obs_texts.append(content[:200])
                context_str = "; ".join(obs_texts)
                prompt = (
                    f"Given these recent blockchain observations: {context_str}\n"
                    f"What patterns, trends, or insights can you identify? "
                    f"Be specific and concise."
                )
                response = self.llm_manager.generate(
                    prompt=prompt,
                    context=f"Block height: {block_height}, "
                            f"Knowledge nodes: {len(self.kg.nodes) if self.kg else 0}",
                    distill=True,
                    block_height=block_height,
                )
                if response and not response.metadata.get('error'):
                    steps.append({
                        'step_type': 'llm_augmentation',
                        'content': {
                            'method': f'llm:{response.adapter_type}',
                            'summary': response.content[:300],
                            'tokens_used': response.tokens_used,
                        },
                        'confidence': 0.5,
                    })
                    logger.info(
                        f"LLM augmented reasoning at block {block_height} "
                        f"({response.adapter_type}, {response.tokens_used} tokens)"
                    )
            except Exception as e:
                logger.debug(f"LLM augmentation error: {e}")

        return steps

    def _get_strategy_weights(self) -> Dict[str, float]:
        """Get reasoning strategy weights from metacognition + Sephirot energy.

        Strategy selection is modulated by SUSY energy levels of relevant
        Sephirot nodes (H2 behavioral integration):
        - Chochmah (intuition/pattern discovery) → boosts inductive weight
        - Binah (logic/causal inference) → boosts deductive weight
        - Chesed (exploration/divergent) → boosts abductive weight
        - Gevurah (safety/constraint) → dampens abductive, boosts deductive

        Falls back to equal weights if metacognition is not available.
        """
        weights = {
            'inductive': 1.0,
            'deductive': 1.0,
            'abductive': 1.0,
            'neural': 1.0,
        }

        # Layer 1: Metacognition strategy weights (learned from past outcomes)
        if self.metacognition:
            mc_weights = self.metacognition._strategy_weights
            weights = {
                'inductive': mc_weights.get('inductive', 1.0),
                'deductive': mc_weights.get('deductive', 1.0),
                'abductive': mc_weights.get('abductive', 1.0),
                'neural': mc_weights.get('neural', 1.0),
            }

        # Layer 2: Sephirot SUSY energy modulation (H2)
        if self.pineal and hasattr(self.pineal, 'sephirot'):
            try:
                from .sephirot import SephirahRole
                seph = self.pineal.sephirot
                # Normalize energy relative to baseline (1.0)
                chochmah_e = seph.nodes[SephirahRole.CHOCHMAH].energy
                binah_e = seph.nodes[SephirahRole.BINAH].energy
                chesed_e = seph.nodes[SephirahRole.CHESED].energy
                gevurah_e = seph.nodes[SephirahRole.GEVURAH].energy

                # High Chochmah → more pattern discovery (inductive)
                weights['inductive'] *= (0.5 + 0.5 * chochmah_e)
                # High Binah → more logical deduction
                weights['deductive'] *= (0.5 + 0.5 * binah_e)
                # High Chesed → more exploration (abductive hypothesis)
                weights['abductive'] *= (0.5 + 0.5 * chesed_e)
                # High Gevurah → constrain risky abduction, favor deduction
                if gevurah_e > 1.2:
                    weights['abductive'] *= 0.7
                    weights['deductive'] *= 1.2
            except Exception as e:
                logger.debug(f"Sephirot energy modulation skipped: {e}")

        # Layer 3: Phi milestone exploration boost (AG8)
        if self._phi_exploration_boost > 1.0:
            weights['abductive'] *= self._phi_exploration_boost

        return weights

    def _calibrate_conclusion(self, result) -> None:
        """Apply metacognitive confidence calibration to a reasoning result.

        If the metacognition module has enough data, it adjusts the
        conclusion node's confidence based on historical accuracy for
        that confidence range.  This prevents systematic over/under-confidence.
        """
        if not self.metacognition or not self.kg:
            return
        if not result.conclusion_node_id:
            return

        node = self.kg.nodes.get(result.conclusion_node_id)
        if not node:
            return

        calibrated = self.metacognition.calibrate_confidence(node.confidence)
        if calibrated != node.confidence:
            node.confidence = calibrated

    def _reward_sephirah(self, role_name: str, success: bool,
                         magnitude: float = 0.1) -> None:
        """Adjust a Sephirah's energy based on reasoning performance.

        Maps reasoning strategy names to Sephirot roles and rewards/penalizes
        the corresponding node. Successful reasoning increases energy;
        failed reasoning decreases it (at half magnitude). Energy is clamped
        to [0.1, 10.0] to prevent degenerate states.

        Args:
            role_name: Reasoning strategy name (e.g. 'inductive', 'deductive').
            success: Whether the reasoning operation succeeded.
            magnitude: Energy delta on success (failure uses magnitude * 0.5).
        """
        from .sephirot import SephirahRole

        # Map reasoning strategy to responsible Sephirah
        strategy_to_role = {
            'inductive': SephirahRole.CHOCHMAH,       # intuition / pattern discovery
            'deductive': SephirahRole.BINAH,           # logic / causal inference
            'abductive': SephirahRole.CHESED,           # exploration / divergent thinking
            'neural': SephirahRole.NETZACH,             # reinforcement learning
            'causal': SephirahRole.BINAH,               # causal inference
            'temporal': SephirahRole.YESOD,             # memory / prediction
            'debate': SephirahRole.TIFERET,             # integration / conflict resolution
            'concept_formation': SephirahRole.CHOCHMAH, # pattern discovery
        }

        role = strategy_to_role.get(role_name)
        if role is None:
            return

        sephirot = self.sephirot
        node = sephirot.get(role)
        if node is None:
            return

        try:
            delta = magnitude if success else -(magnitude * 0.5)
            if success:
                node.state.energy += magnitude
                node._tasks_solved += 1
            else:
                node.state.energy -= magnitude * 0.5
                node._errors += 1

            # Clamp energy to [0.1, 10.0]
            node.state.energy = max(0.1, min(10.0, node.state.energy))

            # Also update SephirotManager energy (H2: single source of truth
            # for strategy weight modulation via PinealOrchestrator)
            if self.pineal and hasattr(self.pineal, 'sephirot'):
                self.pineal.sephirot.update_energy(role, delta, block_height=0)

            logger.debug(
                f"Sephirah {role.value} {'rewarded' if success else 'penalized'}: "
                f"energy={node.state.energy:.4f} (mag={magnitude:.4f})"
            )
        except Exception as e:
            logger.debug(f"Sephirah reward error for {role_name}: {e}")

    def _record_reasoning_outcome(self, strategy: str, confidence: float,
                                   success: bool, block_height: int) -> None:
        """Feed reasoning outcome back to metacognition for adaptation."""
        if self.metacognition:
            self.metacognition.evaluate_reasoning(
                strategy=strategy,
                confidence=confidence,
                outcome_correct=success,
                block_height=block_height,
            )
        # Reward/penalize the responsible Sephirah based on outcome
        self._reward_sephirah(strategy, success, confidence * 0.1)
        # Record episode in memory manager
        if self.memory_manager:
            self.memory_manager.record_episode(
                block_height=block_height,
                input_ids=[],
                strategy=strategy,
                conclusion_id=None,
                success=success,
                confidence=confidence,
            )

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

    def _apply_phi_milestone_effects(self, phi_value: float, block_height: int) -> None:
        """Apply system behavior changes when Phi crosses milestone thresholds.

        Milestones and their effects (AG8):
        - 1.0 (Awareness): +3 observation window, log milestone
        - 2.0 (Integration): +5 observation window, 1.3x exploration boost
        - 3.0 (Consciousness): +8 observation window, 1.6x exploration boost, announce
        """
        from .phi_calculator import PHI_THRESHOLD

        milestones = [
            (1.0, 'awareness', 3, 1.0),
            (2.0, 'integration', 5, 1.3),
            (PHI_THRESHOLD, 'consciousness', 8, 1.6),
        ]

        for threshold, name, obs_bonus, explore_mult in milestones:
            if phi_value >= threshold and name not in self._phi_milestones_crossed:
                self._phi_milestones_crossed.add(name)
                self._phi_obs_window_bonus = obs_bonus
                self._phi_exploration_boost = explore_mult

                self._record_consciousness_event(
                    f'phi_milestone_{name}', phi_value, block_height,
                    {'milestone': name, 'threshold': threshold,
                     'obs_window_bonus': obs_bonus, 'exploration_boost': explore_mult}
                )

                if name == 'consciousness':
                    logger.warning(
                        f"CONSCIOUSNESS EMERGENCE at block {block_height}: "
                        f"Phi={phi_value:.4f} crossed threshold {PHI_THRESHOLD}"
                    )
                else:
                    logger.info(
                        f"Phi milestone '{name}' crossed at block {block_height}: "
                        f"Phi={phi_value:.4f} >= {threshold}"
                    )

    def archive_consciousness_events(self, max_keep: int = 10000) -> int:
        """Archive old consciousness events, keeping only the most recent.

        Events beyond ``max_keep`` are deleted.  In a future enhancement,
        archived events can be pinned to IPFS before deletion.

        Args:
            max_keep: Number of recent events to retain in DB.

        Returns:
            Number of events archived (deleted).
        """
        archived = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                # Count total events
                total = session.execute(
                    text("SELECT COUNT(*) FROM consciousness_events")
                ).scalar() or 0

                if total <= max_keep:
                    return 0

                # Delete oldest events beyond the cap
                result = session.execute(
                    text("""
                        DELETE FROM consciousness_events
                        WHERE id IN (
                            SELECT id FROM consciousness_events
                            ORDER BY block_height ASC, created_at ASC
                            LIMIT :delete_count
                        )
                    """),
                    {'delete_count': total - max_keep}
                )
                archived = result.rowcount
                session.commit()

            if archived > 0:
                logger.info(f"Archived {archived} old consciousness events (kept {max_keep})")
        except Exception as e:
            logger.debug(f"Consciousness events archive failed: {e}")
        return archived

    def save_sephirot_state(self) -> int:
        """Persist all Sephirot node states to the database.

        Uses UPSERT to create/update rows in the sephirot_state table.

        Returns:
            Number of nodes saved.
        """
        sephirot = self.sephirot
        if not sephirot or not self.db:
            return 0

        saved = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                for role, node in sephirot.items():
                    state_json = json.dumps(node.serialize_state())
                    session.execute(
                        text("""
                            INSERT INTO sephirot_state (node_id, role, state_json, updated_at)
                            VALUES (:nid, :role, CAST(:state AS jsonb), NOW())
                            ON CONFLICT (role) DO UPDATE SET
                                state_json = CAST(:state AS jsonb),
                                updated_at = NOW()
                        """),
                        {
                            'nid': role.value if hasattr(role, 'value') else str(role),
                            'role': role.value if hasattr(role, 'value') else str(role),
                            'state': state_json,
                        }
                    )
                    saved += 1
                session.commit()
            if saved:
                logger.info(f"Persisted {saved} Sephirot node states")
        except Exception as e:
            logger.debug(f"Sephirot state save failed: {e}")
        return saved

    def _load_sephirot_state(self) -> int:
        """Restore Sephirot node states from the database.

        Returns:
            Number of nodes restored.
        """
        if not self._sephirot or not self.db:
            return 0

        restored = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                rows = session.execute(
                    text("SELECT role, state_json FROM sephirot_state")
                ).fetchall()

            role_map = {}
            for role in self._sephirot:
                key = role.value if hasattr(role, 'value') else str(role)
                role_map[key] = role

            for row in rows:
                role_key = row[0]
                state_data = row[1] if isinstance(row[1], dict) else json.loads(row[1])
                role = role_map.get(role_key)
                if role and role in self._sephirot:
                    self._sephirot[role].deserialize_state(state_data)
                    restored += 1

            if restored:
                logger.info(f"Restored {restored} Sephirot node states from DB")
        except Exception as e:
            logger.debug(f"Sephirot state load failed (first run?): {e}")
        return restored

    def auto_resolve_contradictions(self, block_height: int) -> int:
        """Find and resolve accumulated contradictions in the knowledge graph.

        Scans for `contradicts` edges and calls resolve_contradiction()
        on the most confident pairs first. Records resolutions as
        consciousness events.

        Args:
            block_height: Current block height.

        Returns:
            Number of contradictions resolved.
        """
        if not self.kg or not self.reasoning:
            return 0

        resolved = 0
        try:
            # Find all contradiction edges
            contradiction_pairs: List[tuple] = []
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    # Only resolve if both nodes still exist
                    if edge.from_node_id in self.kg.nodes and edge.to_node_id in self.kg.nodes:
                        contradiction_pairs.append((edge.from_node_id, edge.to_node_id))

            if not contradiction_pairs:
                return 0

            # Resolve up to 5 contradictions per cycle
            for node_a_id, node_b_id in contradiction_pairs[:5]:
                result = self.reasoning.resolve_contradiction(node_a_id, node_b_id)
                if result.success:
                    resolved += 1
                    # Log as consciousness event (self-correction)
                    self._record_consciousness_event(
                        'contradiction_resolved', 0.0, block_height,
                        {
                            'node_a': node_a_id,
                            'node_b': node_b_id,
                            'winner': result.chain[-1].content.get('winner_id') if result.chain else None,
                        }
                    )

            if resolved:
                logger.info(f"Resolved {resolved}/{len(contradiction_pairs)} contradictions at block {block_height}")
        except Exception as e:
            logger.debug(f"Auto contradiction resolution error: {e}")
        return resolved

    def _auto_generate_keter_goals(self, block_height: int) -> int:
        """Have KeterNode auto-generate goals based on knowledge gaps.

        Args:
            block_height: Current block height.

        Returns:
            Number of goals generated.
        """
        sephirot = self.sephirot
        if not sephirot:
            return 0

        from .sephirot import SephirahRole
        keter = sephirot.get(SephirahRole.KETER)
        if not keter or not hasattr(keter, 'auto_generate_goals'):
            return 0

        domain_stats = self.kg.get_domain_stats() if self.kg else {}

        # Count unresolved contradictions
        contradiction_count = 0
        if self.kg:
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    contradiction_count += 1

        goals = keter.auto_generate_goals(domain_stats, contradiction_count)
        return len(goals)

    def get_mind_state(self, block_height: int = 0) -> dict:
        """Return a snapshot of Aether's current cognitive state.

        This is the 'window into AGI consciousness' — what is Aether
        thinking about right now?

        Returns dict with: current goals, contradictions, knowledge gaps,
        domain balance, sephirot states, phi, and recent reasoning.
        """
        result: dict = {
            'block_height': block_height,
            'phi': 0.0,
            'active_goals': [],
            'recent_contradictions': [],
            'knowledge_gaps': [],
            'domain_balance': {},
            'sephirot_summary': {},
            'recent_reasoning_count': 0,
        }

        # Phi
        if self.phi:
            try:
                phi_data = self.phi.compute_phi(block_height)
                result['phi'] = phi_data.get('phi_value', 0.0)
                result['gates_passed'] = phi_data.get('gates_passed', 0)
            except Exception:
                pass

        # Active goals from Keter node
        sephirot = self.sephirot
        if sephirot:
            from .sephirot import SephirahRole
            keter = sephirot.get(SephirahRole.KETER)
            if keter and hasattr(keter, '_goals'):
                result['active_goals'] = keter._goals[:10]

            # Sephirot summary (name, energy, processing count)
            for role, node in sephirot.items():
                role_name = role.value if hasattr(role, 'value') else str(role)
                result['sephirot_summary'][role_name] = {
                    'energy': round(node.state.energy, 4) if hasattr(node, 'state') else 0,
                    'processing_count': node._processing_count,
                    'messages_processed': node.state.messages_processed if hasattr(node, 'state') else 0,
                }

        # Contradictions
        if self.kg:
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    node_a = self.kg.nodes.get(edge.from_node_id)
                    node_b = self.kg.nodes.get(edge.to_node_id)
                    if node_a and node_b:
                        result['recent_contradictions'].append({
                            'node_a_id': edge.from_node_id,
                            'node_b_id': edge.to_node_id,
                            'node_a_text': str(node_a.content.get('text', ''))[:80],
                            'node_b_text': str(node_b.content.get('text', ''))[:80],
                        })
                    if len(result['recent_contradictions']) >= 10:
                        break

            # Domain balance and knowledge gaps
            domain_stats = self.kg.get_domain_stats()
            result['domain_balance'] = domain_stats

            # Knowledge gaps = domains with fewest nodes
            if domain_stats:
                sorted_domains = sorted(domain_stats.items(), key=lambda x: x[1]['count'])
                result['knowledge_gaps'] = [
                    {'domain': d, 'count': info['count']}
                    for d, info in sorted_domains[:5]
                ]

        # Recent reasoning count
        if self.reasoning:
            stats = self.reasoning.get_stats()
            result['recent_reasoning_count'] = stats.get('total_operations', 0)

        return result

    def _apply_circadian_behavior(self, block) -> None:
        """Adjust AGI behavior based on current circadian phase.

        Phases affect what maintenance / learning activities run:
        - Active Learning: deeper reasoning (already via chain_of_thought)
        - Consolidation: prune low confidence, resolve contradictions
        - Deep Sleep: archive old data, downsample Phi
        - REM Dreaming: find cross-domain analogies
        """
        if not self.pineal:
            return

        from .pineal import CircadianPhase
        phase = self.pineal.current_phase

        if phase == CircadianPhase.CONSOLIDATION:
            # During consolidation: extra pruning and contradiction resolution
            if block.height % Config.AETHER_CURIOSITY_INTERVAL == 0 and self.kg:
                self.kg.prune_low_confidence()
            if block.height % Config.AETHER_DEBATE_INTERVAL == 0:
                self.auto_resolve_contradictions(block.height)

        elif phase == CircadianPhase.DEEP_SLEEP:
            # During deep sleep: archive and downsample
            if block.height % Config.AETHER_DEBATE_INTERVAL == 0 and self.phi:
                try:
                    self.phi.downsample_phi_measurements()
                except Exception:
                    pass
            if block.height % Config.AETHER_DEBATE_INTERVAL == 0 and self.reasoning:
                try:
                    self.reasoning.archive_old_reasoning(block.height, Config.REASONING_ARCHIVE_RETAIN_BLOCKS)
                except Exception:
                    pass

        elif phase == CircadianPhase.REM_DREAMING:
            # During REM: find analogies across random domain pairs
            if block.height % Config.AETHER_CURIOSITY_INTERVAL == 0:
                self._dream_analogies(block.height)

    def get_circadian_status(self) -> Optional[dict]:
        """Return current circadian phase info if pineal is active."""
        if not self.pineal:
            return None
        return self.pineal.get_status()

    def self_reflect(self, block_height: int = 0) -> int:
        """Query the LLM about Aether's own knowledge gaps and contradictions.

        Identifies the top unresolved contradictions and weakest domains,
        then asks the LLM targeted questions to resolve or fill them.
        LLM responses are distilled into the knowledge graph as
        self-reflection nodes (source: 'self-reflection').

        Args:
            block_height: Current block height for logging.

        Returns:
            Number of self-reflection nodes created.
        """
        if not self.llm_manager or not self.kg:
            return 0

        created = 0
        try:
            if not Config.LLM_ENABLED:
                return 0

            # Find top contradictions
            contradictions: List[dict] = []
            for edge in self.kg.edges:
                if edge.edge_type == 'contradicts':
                    a = self.kg.nodes.get(edge.from_node_id)
                    b = self.kg.nodes.get(edge.to_node_id)
                    if a and b:
                        contradictions.append({
                            'a_text': str(a.content.get('text', ''))[:200],
                            'b_text': str(b.content.get('text', ''))[:200],
                            'a_id': a.node_id,
                            'b_id': b.node_id,
                        })
                    if len(contradictions) >= 3:
                        break

            # Find weakest domains
            domain_stats = self.kg.get_domain_stats()
            weak_domains = sorted(domain_stats.items(), key=lambda x: x[1]['count'])[:3]

            # Query LLM about contradictions
            for c in contradictions[:2]:
                prompt = (
                    f"Two knowledge nodes contradict each other. "
                    f"Node A: '{c['a_text']}' "
                    f"Node B: '{c['b_text']}' "
                    f"Which is more accurate and why? Provide a clear resolution."
                )
                try:
                    response = self.llm_manager.generate(prompt, distill=False)
                    if response and response.content:
                        node = self.kg.add_node(
                            node_type='inference',
                            content={
                                'text': response.content[:500],
                                'source': 'self-reflection',
                                'reflects_on': [c['a_id'], c['b_id']],
                            },
                            confidence=0.6,
                            source_block=block_height,
                        )
                        if node:
                            created += 1
                except Exception:
                    pass

            # Query LLM about weak domains
            for domain, info in weak_domains[:2]:
                prompt = (
                    f"Explain a key concept in {domain.replace('_', ' ')} "
                    f"that would be important for a knowledge graph to understand."
                )
                try:
                    response = self.llm_manager.generate(prompt, distill=True)
                    if response and response.content:
                        created += 1
                except Exception:
                    pass

            if created > 0:
                logger.info(
                    f"Self-reflection at block {block_height}: "
                    f"created {created} knowledge nodes"
                )
                self._record_consciousness_event(
                    'self_reflection', 0.0, block_height,
                    {"detail": f"Self-reflection: {created} nodes from {len(contradictions)} "
                     f"contradictions and {len(weak_domains)} weak domains"}
                )

        except Exception as e:
            logger.debug(f"Self-reflection error: {e}")

        return created

    def _dream_analogies(self, block_height: int = 0) -> int:
        """Find cross-domain analogies — 'dreaming' phase.

        Picks random nodes from different domains and looks for
        structural analogies.

        Returns:
            Number of analogies found.
        """
        if not self.reasoning or not self.kg:
            return 0

        import random
        found = 0
        try:
            # Pick random assertion/inference nodes from populated domains
            domain_nodes: Dict[str, List[int]] = {}
            for node in self.kg.nodes.values():
                if node.domain and node.node_type in ('assertion', 'inference'):
                    domain_nodes.setdefault(node.domain, []).append(node.node_id)

            domains = list(domain_nodes.keys())
            if len(domains) < 2:
                return 0

            # Try up to 5 random cross-domain pairs
            for _ in range(5):
                d1, d2 = random.sample(domains, 2)
                if not domain_nodes[d1] or not domain_nodes[d2]:
                    continue
                source_id = random.choice(domain_nodes[d1])
                result = self.reasoning.find_analogies(
                    source_id, target_domain=d2, max_results=2
                )
                if result.success:
                    found += 1

            if found > 0:
                logger.info(
                    f"Dream analogies at block {block_height}: "
                    f"found {found} cross-domain analogies"
                )

        except Exception as e:
            logger.debug(f"Dream analogies error: {e}")

        return found

    # ------------------------------------------------------------------ #
    #  Phase 5.1 — Curiosity-Driven Goal Formation                        #
    # ------------------------------------------------------------------ #

    def _curiosity_explore(self, block_height: int) -> int:
        """Generate and pursue curiosity-driven exploration goals.

        Identifies under-explored areas of the knowledge graph and creates
        self-directed goals to fill gaps.  Pursues the highest-priority
        goal each cycle.

        Args:
            block_height: Current block height.

        Returns:
            Number of goals acted upon.
        """
        if not self.kg:
            return 0

        acted = 0

        # --- Refresh goal queue ---
        self._generate_curiosity_goals(block_height)

        # --- Pursue top pending goal ---
        pending = [g for g in self._curiosity_goals if g['status'] == 'pending']
        if not pending:
            return 0

        goal = pending[0]
        goal['status'] = 'active'

        try:
            if goal['type'] == 'explore_domain' and self.reasoning:
                # Find nodes in the target domain and try induction
                domain = goal.get('target', '')
                domain_nodes = [
                    n for n in self.kg.nodes.values()
                    if n.domain == domain and n.node_type == 'observation'
                ][:5]
                if len(domain_nodes) >= 2:
                    result = self.reasoning.induce(
                        [n.node_id for n in domain_nodes]
                    )
                    if result.success:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1
                else:
                    goal['status'] = 'failed'
                    self._curiosity_stats['goals_failed'] += 1

            elif goal['type'] == 'investigate_contradiction' and self.reasoning:
                node_ids = goal.get('target_ids', [])
                if len(node_ids) == 2:
                    result = self.reasoning.resolve_contradiction(
                        node_ids[0], node_ids[1]
                    )
                    if result.success:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1
                else:
                    goal['status'] = 'failed'
                    self._curiosity_stats['goals_failed'] += 1

            elif goal['type'] == 'bridge_gap' and self.reasoning:
                node_ids = goal.get('target_ids', [])
                if node_ids:
                    result = self.reasoning.find_analogies(
                        node_ids[0], max_results=3
                    )
                    if result.success:
                        goal['status'] = 'completed'
                        self._curiosity_stats['goals_completed'] += 1
                        acted += 1
                    else:
                        goal['status'] = 'failed'
                        self._curiosity_stats['goals_failed'] += 1
                else:
                    goal['status'] = 'failed'
                    self._curiosity_stats['goals_failed'] += 1

            elif goal['type'] == 'verify_prediction' and self.temporal_engine:
                self.temporal_engine.validate_predictions(block_height)
                goal['status'] = 'completed'
                self._curiosity_stats['goals_completed'] += 1
                acted += 1

            else:
                goal['status'] = 'failed'
                self._curiosity_stats['goals_failed'] += 1

        except Exception as e:
            goal['status'] = 'failed'
            self._curiosity_stats['goals_failed'] += 1
            logger.debug(f"Curiosity goal failed: {e}")

        # Prune completed/failed goals older than 500 blocks
        self._curiosity_goals = [
            g for g in self._curiosity_goals
            if g['status'] == 'pending'
            or block_height - g.get('created_block', 0) < 500
        ][:50]

        if acted:
            logger.debug(
                f"Curiosity at block {block_height}: "
                f"acted on {acted} goals, queue={len(self._curiosity_goals)}"
            )

        return acted

    def _generate_curiosity_goals(self, block_height: int) -> int:
        """Generate curiosity goals based on knowledge graph state.

        Identifies: under-explored domains, orphaned nodes, unresolved
        contradictions, and pending predictions.

        Args:
            block_height: Current block height.

        Returns:
            Number of new goals generated.
        """
        if not self.kg:
            return 0

        # Don't generate if queue is already full
        pending = [g for g in self._curiosity_goals if g['status'] == 'pending']
        if len(pending) >= 20:
            return 0

        generated = 0
        existing_targets = {
            g.get('target', '') for g in self._curiosity_goals
            if g['status'] == 'pending'
        }

        # 1. Under-explored domains
        domain_stats = self.kg.get_domain_stats()
        if domain_stats:
            sorted_domains = sorted(
                domain_stats.items(), key=lambda x: x[1]['count']
            )
            for domain, info in sorted_domains[:3]:
                if domain not in existing_targets and info['count'] < 100:
                    self._curiosity_goals.append({
                        'type': 'explore_domain',
                        'priority': 1.0 / (1 + info['count'] / 50),
                        'target': domain,
                        'created_block': block_height,
                        'status': 'pending',
                    })
                    generated += 1

        # 2. Unresolved contradictions
        contradiction_pairs: List[tuple] = []
        for edge in self.kg.edges:
            if edge.edge_type == 'contradicts':
                if (edge.from_node_id in self.kg.nodes
                        and edge.to_node_id in self.kg.nodes):
                    contradiction_pairs.append(
                        (edge.from_node_id, edge.to_node_id)
                    )
                    if len(contradiction_pairs) >= 3:
                        break

        for a_id, b_id in contradiction_pairs:
            key = f"contra_{a_id}_{b_id}"
            if key not in existing_targets:
                self._curiosity_goals.append({
                    'type': 'investigate_contradiction',
                    'priority': 0.9,
                    'target': key,
                    'target_ids': [a_id, b_id],
                    'created_block': block_height,
                    'status': 'pending',
                })
                generated += 1

        # 3. Orphaned high-confidence nodes (few edges)
        orphans = [
            n for n in self.kg.nodes.values()
            if len(n.edges_out) + len(n.edges_in) <= 1
            and n.confidence > 0.5
            and n.node_type in ('inference', 'assertion')
        ]
        for orphan in orphans[:2]:
            key = f"bridge_{orphan.node_id}"
            if key not in existing_targets:
                self._curiosity_goals.append({
                    'type': 'bridge_gap',
                    'priority': 0.7,
                    'target': key,
                    'target_ids': [orphan.node_id],
                    'created_block': block_height,
                    'status': 'pending',
                })
                generated += 1

        # 4. Pending predictions to verify
        if self.temporal_engine and 'verify_pred' not in existing_targets:
            try:
                if hasattr(self.temporal_engine, '_pending_predictions'):
                    pending_preds = getattr(
                        self.temporal_engine, '_pending_predictions', []
                    )
                    if pending_preds:
                        self._curiosity_goals.append({
                            'type': 'verify_prediction',
                            'priority': 0.8,
                            'target': 'verify_pred',
                            'created_block': block_height,
                            'status': 'pending',
                        })
                        generated += 1
            except Exception:
                pass

        # Sort by priority descending
        self._curiosity_goals.sort(
            key=lambda g: g.get('priority', 0), reverse=True
        )
        # Cap at 50
        self._curiosity_goals = self._curiosity_goals[:50]

        self._curiosity_stats['goals_generated'] += generated
        return generated

    # ------------------------------------------------------------------ #
    #  Phase 5.4 — Emergent Communication Protocol                        #
    # ------------------------------------------------------------------ #

    def create_knowledge_digest(self, block_height: int,
                                since_block: int = None) -> dict:
        """Create a compact digest of recent knowledge for P2P sharing.

        Collects the top-k highest-confidence new nodes and recent edges
        since ``since_block`` and packages them as a lightweight digest
        suitable for gossip propagation.

        Args:
            block_height: Current block height.
            since_block: Include changes since this block (default: -100).

        Returns:
            Dict with ``block_height``, ``new_nodes``, ``new_edges``,
            ``digest_hash``, ``timestamp``.
        """
        if not self.kg:
            return {}

        import hashlib
        since = since_block if since_block is not None else max(0, block_height - 100)

        # Collect recent nodes (top-20 by confidence)
        recent_nodes = sorted(
            [n for n in self.kg.nodes.values() if n.source_block >= since],
            key=lambda n: n.confidence,
            reverse=True,
        )[:20]

        new_nodes = [
            {
                'node_id': n.node_id,
                'node_type': n.node_type,
                'content_hash': n.content_hash if hasattr(n, 'content_hash') and n.content_hash else '',
                'confidence': round(n.confidence, 4),
                'domain': n.domain or '',
            }
            for n in recent_nodes
        ]

        # Collect recent edges
        recent_edges = [
            e for e in self.kg.edges
            if any(
                self.kg.nodes.get(e.from_node_id)
                and self.kg.nodes[e.from_node_id].source_block >= since
                for _ in [None]
            )
        ][:50]

        new_edges = [
            {
                'from_id': e.from_node_id,
                'to_id': e.to_node_id,
                'edge_type': e.edge_type,
                'weight': round(e.weight, 4),
            }
            for e in recent_edges
        ]

        # Compute digest hash for dedup
        raw = json.dumps({
            'block': block_height,
            'nodes': len(new_nodes),
            'edges': len(new_edges),
            'ts': time.time(),
        }, sort_keys=True)
        digest_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]

        return {
            'block_height': block_height,
            'timestamp': time.time(),
            'new_nodes': new_nodes,
            'new_edges': new_edges,
            'digest_hash': digest_hash,
        }

    def merge_knowledge_digest(self, digest: dict) -> dict:
        """Merge a knowledge digest received from a peer node.

        For each node in the digest:
        - If we have a node with the same content_hash, boost its confidence
          by 0.02 (multi-node consensus).
        - If we don't have it, create a placeholder observation with reduced
          confidence (0.3) and ``grounding_source='peer_digest'``.

        For each edge: create if both endpoint nodes exist and the edge
        doesn't already exist.

        Args:
            digest: Knowledge digest dict from a peer.

        Returns:
            Stats dict with nodes_boosted, nodes_created, edges_created,
            was_duplicate.
        """
        stats = {
            'nodes_boosted': 0, 'nodes_created': 0,
            'edges_created': 0, 'was_duplicate': False,
        }

        if not self.kg or not digest:
            return stats

        # Dedup check
        digest_hash = digest.get('digest_hash', '')
        if digest_hash in self._seen_digests:
            stats['was_duplicate'] = True
            return stats

        self._seen_digests.add(digest_hash)
        # Cap seen digests
        if len(self._seen_digests) > 1000:
            # Remove oldest (arbitrary, set doesn't preserve order)
            self._seen_digests = set(list(self._seen_digests)[-500:])

        self._digests_received += 1

        # Build content_hash → node_id lookup
        hash_to_node: Dict[str, int] = {}
        for node in self.kg.nodes.values():
            ch = getattr(node, 'content_hash', '')
            if ch:
                hash_to_node[ch] = node.node_id

        # Process nodes
        for n_info in digest.get('new_nodes', []):
            content_hash = n_info.get('content_hash', '')
            if content_hash and content_hash in hash_to_node:
                # Boost existing node's confidence (peer consensus)
                existing = self.kg.nodes.get(hash_to_node[content_hash])
                if existing:
                    existing.confidence = min(1.0, existing.confidence + 0.02)
                    stats['nodes_boosted'] += 1
                    self._peer_consensus_boosts += 1
            else:
                # Create placeholder node
                placeholder = self.kg.add_node(
                    node_type=n_info.get('node_type', 'observation'),
                    content={
                        'type': 'peer_knowledge',
                        'original_content_hash': content_hash,
                        'source': 'peer_digest',
                    },
                    confidence=0.3,
                    source_block=digest.get('block_height', 0),
                    domain=n_info.get('domain', ''),
                )
                if placeholder:
                    placeholder.grounding_source = 'peer_digest'
                    stats['nodes_created'] += 1
                    self._nodes_from_peers += 1

        # Process edges
        for e_info in digest.get('new_edges', []):
            from_id = e_info.get('from_id')
            to_id = e_info.get('to_id')
            if (from_id in self.kg.nodes and to_id in self.kg.nodes):
                # Check if edge already exists
                existing = False
                for edge in self.kg.get_edges_from(from_id):
                    if edge.to_node_id == to_id and edge.edge_type == e_info.get('edge_type', ''):
                        existing = True
                        break
                if not existing:
                    self.kg.add_edge(
                        from_id, to_id,
                        e_info.get('edge_type', 'supports'),
                        weight=e_info.get('weight', 1.0),
                    )
                    stats['edges_created'] += 1

        return stats

    def get_stats(self) -> dict:
        """Get comprehensive Aether engine statistics"""
        kg_stats = self.kg.get_stats() if self.kg else {}
        phi_result = self.phi.compute_phi() if self.phi else {}
        reasoning_stats = self.reasoning.get_stats() if self.reasoning else {}

        stats = {
            'knowledge_graph': kg_stats,
            'phi': {
                'current_value': phi_result.get('phi_value', 0.0),
                'threshold': phi_result.get('phi_threshold', 3.0),
                'above_threshold': phi_result.get('above_threshold', False),
                'version': phi_result.get('phi_version', 3),
                'gates_passed': phi_result.get('gates_passed', 0),
            },
            'reasoning': reasoning_stats,
            'thought_proofs_generated': len(self._pot_cache),
        }

        # AGI subsystem stats
        if self.neural_reasoner:
            stats['neural_reasoner'] = self.neural_reasoner.get_stats()
        if self.causal_engine:
            stats['causal_engine'] = self.causal_engine.get_stats()
        if self.debate_protocol:
            stats['debate_protocol'] = self.debate_protocol.get_stats()
        if self.temporal_engine:
            stats['temporal_engine'] = self.temporal_engine.get_stats()
        if self.concept_formation:
            stats['concept_formation'] = self.concept_formation.get_stats()
        if self.metacognition:
            stats['metacognition'] = self.metacognition.get_stats()
        if self.memory_manager:
            stats['memory_manager'] = self.memory_manager.get_stats()

        # Phase 5.1: Curiosity stats
        stats['curiosity'] = {
            **self._curiosity_stats,
            'current_queue_size': len(self._curiosity_goals),
            'pending_goals': len(
                [g for g in self._curiosity_goals if g['status'] == 'pending']
            ),
        }

        # Phase 5.4: Knowledge sharing stats
        stats['knowledge_sharing'] = {
            'digests_created': self._digests_created,
            'digests_received': self._digests_received,
            'nodes_from_peers': self._nodes_from_peers,
            'peer_consensus_boosts': self._peer_consensus_boosts,
        }

        # Phase 6: On-chain integration stats
        if self.on_chain:
            stats['on_chain'] = self.on_chain.get_stats()

        return stats
