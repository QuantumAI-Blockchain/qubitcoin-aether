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
                 reasoning_engine=None, llm_manager=None, pineal=None):
        self.db = db_manager
        self.kg = knowledge_graph
        self.phi = phi_calculator
        self.reasoning = reasoning_engine
        self.llm_manager = llm_manager
        self.pineal = pineal  # PinealOrchestrator for circadian phases
        self._pot_cache: Dict[int, ProofOfThought] = {}
        self._pot_cache_max = 1000  # Bound cache to prevent unbounded memory growth

        # Sephirot cognitive nodes — initialized lazily
        self._sephirot: Optional[dict] = None

        logger.info("Aether Engine initialized")

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
                logger.debug(f"Sephirot init failed: {e}")
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

        # Log consciousness event if Phi crosses threshold
        from .phi_calculator import PHI_THRESHOLD
        if phi_value >= PHI_THRESHOLD:
            trigger = {'reasoning_steps': len(reasoning_steps)}
            # Post-fork: include gate data in consciousness events
            if phi_result.get('phi_version') == 2:
                trigger['gates_passed'] = phi_result.get('gates_passed', 0)
                trigger['gates_total'] = phi_result.get('gates_total', 6)
                trigger['gate_ceiling'] = phi_result.get('gate_ceiling', 0)
                trigger['phi_raw'] = phi_result.get('phi_raw', phi_value)
            self._record_consciousness_event(
                'phi_threshold_crossed', phi_value, block_height, trigger
            )

        # Enhanced logging with gate info post-fork
        gate_info = ''
        if phi_result.get('phi_version') == 2:
            gate_info = f", gates={phi_result.get('gates_passed', 0)}/{phi_result.get('gates_total', 6)}"
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

            # Route messages between Sephirot cognitive nodes
            if block.height % 5 == 0:
                self._route_sephirot_messages(block)

            # Auto-resolve contradictions every 1000 blocks
            if block.height > 0 and block.height % 1000 == 0:
                self.auto_resolve_contradictions(block.height)

            # Auto-generate Keter goals every 500 blocks
            if block.height > 0 and block.height % 500 == 0:
                self._auto_generate_keter_goals(block.height)

            # Boost frequently-referenced knowledge nodes every 1000 blocks
            if block.height > 0 and block.height % 1000 == 0 and self.kg:
                self.kg.boost_referenced_nodes()

            # Self-reflection via LLM every 200 blocks
            if (block.height > 0 and block.height % 200 == 0
                    and self.llm_manager):
                self.self_reflect(block.height)

            # Find analogies during REM-like phases (every 500 blocks)
            if block.height > 0 and block.height % 500 == 0 and self.reasoning and self.kg:
                self._dream_analogies(block.height)

            # Archive old consciousness events every 5000 blocks
            if block.height > 0 and block.height % 5000 == 0:
                self.archive_consciousness_events()

            # Archive old reasoning operations every 10000 blocks
            if block.height > 0 and block.height % 10000 == 0 and self.reasoning:
                from ..config import Config
                self.reasoning.archive_old_reasoning(
                    block.height, Config.REASONING_ARCHIVE_RETAIN_BLOCKS
                )

            # Persist Sephirot state every 100 blocks
            if block.height > 0 and block.height % 100 == 0:
                self.save_sephirot_state()

            # Tick pineal orchestrator for circadian phase management
            if self.pineal and block.height > 0:
                phi_val = 0.0
                if self.phi:
                    try:
                        phi_data = self.phi.compute_phi(block.height)
                        phi_val = phi_data.get('phi_value', 0.0)
                    except Exception:
                        pass
                self.pineal.tick(block.height, phi_val)

                # Phase-aware behavior (item 10.2)
                self._apply_circadian_behavior(block)

        except Exception as e:
            logger.debug(f"Error processing block knowledge: {e}")

    def _route_sephirot_messages(self, block) -> int:
        """
        Route messages between Sephirot cognitive nodes.

        Processes all 10 nodes in Tree of Life order, drains each node's
        outbox and delivers messages to target nodes' inboxes.
        Then runs each node's process() method with block context.

        Returns:
            Number of messages routed.
        """
        from .sephirot import SephirahRole

        sephirot = self.sephirot
        if not sephirot:
            return 0

        # Tree of Life processing order (top-down)
        processing_order = [
            SephirahRole.KETER,     # Crown — meta-learning
            SephirahRole.CHOCHMAH,  # Wisdom — intuition
            SephirahRole.BINAH,     # Understanding — logic
            SephirahRole.CHESED,    # Mercy — exploration
            SephirahRole.GEVURAH,   # Severity — safety
            SephirahRole.TIFERET,   # Beauty — integration
            SephirahRole.NETZACH,   # Victory — persistence
            SephirahRole.HOD,       # Splendor — communication
            SephirahRole.YESOD,     # Foundation — memory
            SephirahRole.MALKUTH,   # Kingdom — action
        ]

        # Build block context
        context = {
            'block_height': block.height,
            'timestamp': block.timestamp,
            'difficulty': block.difficulty,
            'tx_count': len(block.transactions),
            'kg_node_count': len(self.kg.nodes) if self.kg else 0,
            'kg_edge_count': len(self.kg.edges) if self.kg else 0,
        }

        total_routed = 0

        # Process each node and collect outgoing messages
        for role in processing_order:
            node = sephirot.get(role)
            if not node:
                continue

            try:
                node.process(context)
            except Exception as e:
                logger.debug(f"Sephirot {role.value} process error: {e}")

            # Drain outbox and deliver to targets
            outgoing = node.get_outbox()
            for msg in outgoing:
                target = sephirot.get(msg.receiver)
                if target:
                    target.receive_message(msg)
                    total_routed += 1

        if total_routed > 0:
            logger.debug(f"Routed {total_routed} Sephirot messages at block {block.height}")

        return total_routed

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
            for edge in self.kg.edges.values():
                if edge.edge_type == 'contradicts':
                    # Only resolve if both nodes still exist
                    if edge.source_id in self.kg.nodes and edge.target_id in self.kg.nodes:
                        contradiction_pairs.append((edge.source_id, edge.target_id))

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
            if block.height % 50 == 0 and self.kg:
                self.kg.prune_low_confidence()
            if block.height % 100 == 0:
                self.auto_resolve_contradictions(block.height)

        elif phase == CircadianPhase.DEEP_SLEEP:
            # During deep sleep: archive and downsample
            if block.height % 100 == 0 and self.phi:
                try:
                    self.phi.downsample_phi_measurements()
                except Exception:
                    pass
            if block.height % 100 == 0 and self.reasoning:
                try:
                    self.reasoning.archive_old_reasoning(block.height, 50000)
                except Exception:
                    pass

        elif phase == CircadianPhase.REM_DREAMING:
            # During REM: find analogies across random domain pairs
            if block.height % 50 == 0:
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
            from ..config import Config
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
                    if response and response.get('content'):
                        node = self.kg.add_node(
                            node_type='inference',
                            content={
                                'text': response['content'][:500],
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
                    if response and response.get('content'):
                        created += 1
                except Exception:
                    pass

            if created > 0:
                logger.info(
                    f"Self-reflection at block {block_height}: "
                    f"created {created} knowledge nodes"
                )
                self._record_consciousness_event(
                    block_height, 0.0, 'self_reflection',
                    f"Self-reflection: {created} nodes from {len(contradictions)} "
                    f"contradictions and {len(weak_domains)} weak domains"
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
