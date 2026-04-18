"""
Reasoning Engine - Logical Inference for Aether Tree
Supports deductive, inductive, and abductive reasoning over the knowledge graph.
Generates new KeterNodes from existing knowledge through logical inference.

v2 enhancements (Improvements 36-50):
- Deeper premise chain exploration (depth 4)
- Cycle detection in reasoning chains
- Analogical reasoning method
- Multi-step chained reasoning (deduction -> induction -> abduction)
- Reasoning confidence calibration via metacognition
- Counter-argument generation via debate engine
- Per-domain success rate tracking
- Hypothesis generation from abductive reasoning
- Reasoning caching for similar queries
- Temporal context awareness (block height)
- Natural language explanation generation
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ReasoningStep:
    """A single step in a reasoning chain"""
    step_type: str  # 'premise', 'rule', 'conclusion', 'observation'
    node_id: Optional[int] = None
    content: dict = field(default_factory=dict)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            'step_type': self.step_type,
            'node_id': self.node_id,
            'content': self.content,
            'confidence': self.confidence,
        }


@dataclass
class ReasoningResult:
    """Result of a reasoning operation"""
    operation_type: str  # deductive, inductive, abductive
    premise_ids: List[int]
    conclusion_node_id: Optional[int] = None
    confidence: float = 0.0
    chain: List[ReasoningStep] = field(default_factory=list)
    success: bool = False
    explanation: str = ''
    domain: str = 'general'
    block_height: int = 0
    hypotheses: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'operation_type': self.operation_type,
            'premise_ids': self.premise_ids,
            'conclusion_node_id': self.conclusion_node_id,
            'confidence': self.confidence,
            'chain': [s.to_dict() for s in self.chain],
            'success': self.success,
            'explanation': self.explanation,
            'domain': self.domain,
            'block_height': self.block_height,
            'hypotheses': self.hypotheses,
        }


class ReasoningEngine:
    """
    Performs logical reasoning operations over the knowledge graph.

    Three modes:
    - Deductive: Given premises A and A->B, conclude B (certainty preserving)
    - Inductive: Given many observations, generalize a pattern (confidence < 1)
    - Abductive: Given observation B and rule A->B, infer A (hypothesis generation)
    """

    def __init__(self, db_manager, knowledge_graph):
        self.db = db_manager
        self.kg = knowledge_graph
        self._operations: List[ReasoningResult] = []
        self._max_operations = 10000  # Bound in-memory history to prevent unbounded growth
        # Per-domain success rate tracking (Improvement 44)
        self._domain_success: Dict[str, Dict[str, int]] = {}  # domain -> {attempts, successes}
        # Reasoning cache for similar queries (Improvement 47)
        self._reasoning_cache: Dict[str, Tuple[ReasoningResult, float]] = {}  # hash -> (result, timestamp)
        self._cache_ttl: float = 300.0  # 5 minute TTL
        self._cache_max_size: int = 200
        # Metacognition and debate engine references (set externally)
        self._metacognition: Optional[Any] = None
        self._debate_engine: Optional[Any] = None
        # Current block height context (updated externally)
        self._current_block_height: int = 0
        # Rust LogicBridge for FOL reasoning (no LLM required)
        self._logic_bridge: Optional[Any] = None
        self._logic_bridge_loaded: bool = False
        # Counters: track how many deductions used logic_bridge vs graph_traversal
        self._logic_bridge_deductions: int = 0
        self._graph_traversal_deductions: int = 0
        self._init_logic_bridge()

    def _init_logic_bridge(self) -> None:
        """Initialize the Rust LogicBridge for FOL reasoning (no LLM required)."""
        try:
            from aether_core import LogicBridge
            self._logic_bridge = LogicBridge()
            logger.info("Rust LogicBridge initialized — FOL reasoning available without LLM")
        except ImportError:
            logger.debug("Rust LogicBridge not available — using graph-traversal reasoning only")
            self._logic_bridge = None

    def refresh_logic_bridge(self, max_nodes: int = 2000) -> None:
        """Reload the knowledge graph into the Rust LogicBridge FOL KB.

        Call periodically (e.g. every N blocks) to keep the FOL KB in sync
        with the growing knowledge graph.
        """
        if self._logic_bridge is None:
            return
        try:
            self._logic_bridge.load_from_graph(self.kg, max_nodes=max_nodes)
            self._logic_bridge_loaded = True
            stats = self._logic_bridge.stats()
            logger.info(
                "LogicBridge refreshed: %d facts, %d rules",
                stats.get('facts', 0), stats.get('rules', 0),
            )
        except Exception as e:
            logger.warning("LogicBridge refresh failed: %s", e)
            self._logic_bridge_loaded = False

    def prove_relation(self, from_id: int, to_id: int, relation: str) -> Optional[Dict]:
        """Prove a relationship between two nodes via FOL backward chaining.

        Returns a dict with 'proved' (bool) and 'summary' (str), or None
        if the LogicBridge is not available.
        """
        if not self._logic_bridge or not self._logic_bridge_loaded:
            return None
        try:
            return self._logic_bridge.prove_relation(from_id, to_id, relation)
        except Exception as e:
            logger.debug("LogicBridge prove_relation failed: %s", e)
            return None

    def fol_deduce(self, premise_ids: Optional[List[int]] = None, max_steps: int = 50) -> List[Dict]:
        """Run FOL forward chaining via the Rust LogicBridge.

        Returns a list of newly derived facts (dicts with 'description' and
        'source_node_ids'). Returns empty list if LogicBridge not available.
        """
        if not self._logic_bridge or not self._logic_bridge_loaded:
            return []
        try:
            if premise_ids:
                return self._logic_bridge.deduce_from(premise_ids, max_steps)
            return self._logic_bridge.deduce(max_steps)
        except Exception as e:
            logger.debug("LogicBridge deduce failed: %s", e)
            return []

    def fol_explain(self, observation_node_id: int) -> List[Dict]:
        """Generate abductive explanations via FOL reasoning.

        Returns a list of hypotheses (dicts with 'description', 'score',
        'also_explains_count'). Returns empty list if LogicBridge not available.
        """
        if not self._logic_bridge or not self._logic_bridge_loaded:
            return []
        try:
            return self._logic_bridge.explain(observation_node_id)
        except Exception as e:
            logger.debug("LogicBridge explain failed: %s", e)
            return []

    def _grounding_boost(self, premise_ids: List[int]) -> float:
        """Compute a confidence boost factor based on how many premises are grounded.

        Premises with a non-empty ``grounding_source`` (e.g. 'block_oracle',
        'prediction_verified') contribute to a multiplicative boost, rewarding
        reasoning chains that are anchored in verifiable ground truth.

        Args:
            premise_ids: Node IDs of the premises used in the reasoning step.

        Returns:
            A boost factor in [1.0, 1.25]. Each grounded premise adds +0.05,
            capped at 1.25 (i.e. max 5 grounded premises contribute).
        """
        grounded_count = 0
        for pid in premise_ids:
            node = self.kg.get_node(pid)
            if node and node.grounding_source:
                grounded_count += 1
        return min(1.25, 1.0 + 0.05 * grounded_count)

    def deduce(self, premise_ids: List[int], rule_content: dict = None) -> ReasoningResult:
        """
        Deductive reasoning: derive certain conclusions from premises.

        Strategy:
        1. If the Rust LogicBridge is loaded, try FOL forward chaining from the
           given premises first — this is real modus-ponens deduction.
        2. Fall back to graph-traversal deduction if LogicBridge is unavailable,
           has no matching rules, or fails.
        """
        chain: List[ReasoningStep] = []
        premises = []
        for pid in premise_ids:
            node = self.kg.get_node(pid)
            if node:
                premises.append(node)
                chain.append(ReasoningStep(
                    step_type='premise',
                    node_id=pid,
                    content=node.content,
                    confidence=node.confidence,
                ))

        if len(premises) < 2:
            return ReasoningResult(
                operation_type='deductive',
                premise_ids=premise_ids,
                confidence=0.0,
                chain=chain,
                success=False,
                explanation='Need at least 2 premises for deduction',
            )

        # -----------------------------------------------------------------
        # Path 1: LogicBridge FOL deduction (real logical inference)
        # -----------------------------------------------------------------
        logic_bridge_result = self._try_logic_bridge_deduction(
            premise_ids, premises, chain, rule_content,
        )
        if logic_bridge_result is not None:
            self._logic_bridge_deductions += 1
            logger.debug(
                "Deduction via logic_bridge for premises %s (total lb=%d, gt=%d)",
                premise_ids, self._logic_bridge_deductions,
                self._graph_traversal_deductions,
            )
            self._store_operation(logic_bridge_result)
            self._operations.append(logic_bridge_result)
            if len(self._operations) > self._max_operations:
                self._operations = self._operations[-self._max_operations:]
            return logic_bridge_result

        # -----------------------------------------------------------------
        # Path 2: Graph-traversal deduction (fallback)
        # -----------------------------------------------------------------
        result = self._graph_traversal_deduction(
            premise_ids, premises, chain, rule_content,
        )
        self._graph_traversal_deductions += 1
        logger.debug(
            "Deduction via graph_traversal for premises %s (total lb=%d, gt=%d)",
            premise_ids, self._logic_bridge_deductions,
            self._graph_traversal_deductions,
        )

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    # -----------------------------------------------------------------
    # LogicBridge deduction path
    # -----------------------------------------------------------------

    def _try_logic_bridge_deduction(
        self,
        premise_ids: List[int],
        premises: list,
        chain: List[ReasoningStep],
        rule_content: Optional[dict],
    ) -> Optional[ReasoningResult]:
        """Attempt deduction via the Rust LogicBridge (FOL forward chaining).

        Returns a ReasoningResult on success, or None if the bridge is
        unavailable, not loaded, or produces no new derivations from the
        given premises.
        """
        if not self._logic_bridge or not self._logic_bridge_loaded:
            return None

        try:
            derived = self._logic_bridge.deduce_from(premise_ids, 50)
        except Exception as e:
            logger.debug("LogicBridge deduce_from failed: %s", e)
            return None

        if not derived:
            return None

        # Pick the best derived fact (most source nodes = strongest provenance)
        best = max(derived, key=lambda d: len(d.get('source_node_ids', [])))
        source_ids = best.get('source_node_ids', [])
        description = best.get('description', 'FOL-derived conclusion')

        # Confidence: minimum of premise confidences * 0.95
        # (same discipline as graph traversal, but from a proper inference)
        min_premise_conf = min(p.confidence for p in premises)
        conf = min_premise_conf * 0.95
        conf *= self._grounding_boost(premise_ids)
        conf = min(min_premise_conf, conf)

        # Detect cross-domain
        premise_domains = set(getattr(p, 'domain', '') or 'general' for p in premises)
        is_cross_domain = len(premise_domains) > 1

        combined = {
            'type': 'deduction',
            'method': 'logic_bridge',
            'from_premises': [p.content for p in premises],
            'rule': rule_content or {'operation': 'fol_forward_chain'},
            'fol_description': description,
            'fol_derived_count': len(derived),
            'cross_domain': is_cross_domain,
        }

        block_height = max(p.source_block for p in premises)
        conclusion = self.kg.add_node(
            node_type='inference',
            content=combined,
            confidence=conf,
            source_block=block_height,
        )

        # Link premises to conclusion
        for p in premises:
            self.kg.add_edge(p.node_id, conclusion.node_id, 'derives')

        # Build the chain with a rule step indicating FOL inference
        result_chain = list(chain)  # copy premise steps
        result_chain.append(ReasoningStep(
            step_type='rule',
            content={'operation': 'fol_forward_chain', 'description': description},
            confidence=1.0,
        ))
        result_chain.append(ReasoningStep(
            step_type='conclusion',
            node_id=conclusion.node_id,
            content=combined,
            confidence=conf,
        ))

        return ReasoningResult(
            operation_type='deductive',
            premise_ids=premise_ids,
            conclusion_node_id=conclusion.node_id,
            confidence=conf,
            chain=result_chain,
            success=True,
            explanation=(
                f"FOL deduction via LogicBridge from {len(premises)} premises "
                f"({len(derived)} derived facts, best: {description[:80]})"
            ),
        )

    # -----------------------------------------------------------------
    # Graph-traversal deduction path (original algorithm, kept as fallback)
    # -----------------------------------------------------------------

    def _graph_traversal_deduction(
        self,
        premise_ids: List[int],
        premises: list,
        chain: List[ReasoningStep],
        rule_content: Optional[dict],
    ) -> ReasoningResult:
        """Deduction via BFS graph reachability (fallback when LogicBridge
        is unavailable or produces no results)."""
        # Find common conclusions: nodes reachable from all premises
        # Depth 2 exploration (was 4 — reduced to cap O(n^2) blowup); max 5 premises
        reachable_sets = []
        for premise in premises[:5]:
            reachable: set = set()
            visited_in_chain: set = {premise.node_id}  # Cycle detection
            frontier = [premise.node_id]
            for _depth in range(2):  # Depth 2 (was 4)
                next_frontier: List[int] = []
                for nid in frontier[:30]:  # cap breadth per step
                    for n in self.kg.get_neighbors(nid, 'out'):
                        if n.node_id not in visited_in_chain:  # Cycle detection
                            visited_in_chain.add(n.node_id)
                            reachable.add(n.node_id)
                            next_frontier.append(n.node_id)
                frontier = next_frontier
                if not frontier:
                    break
            reachable_sets.append(reachable)

        # Intersection: nodes reachable from ALL premises
        if reachable_sets:
            common = reachable_sets[0]
            for rs in reachable_sets[1:]:
                common = common.intersection(rs)
        else:
            common = set()

        if not common:
            # No common conclusion — create a new inference node
            # Combine premise content into a deductive conclusion
            # Detect cross-domain inference (premises from different domains)
            premise_domains = set(getattr(p, 'domain', '') or 'general' for p in premises)
            is_cross_domain = len(premise_domains) > 1
            combined = {
                'type': 'deduction',
                'method': 'graph_traversal',
                'from_premises': [p.content for p in premises],
                'rule': rule_content or {'operation': 'conjunction'},
                'cross_domain': is_cross_domain,
            }
            # Confidence: minimum of premise confidences (prevents exponential
            # decay that occurs with product, more honest about chain strength)
            min_premise_conf = min(p.confidence for p in premises)
            conf = min_premise_conf * 0.95
            # Boost confidence when premises are grounded in external truth
            # but never exceed the weakest premise confidence
            conf *= self._grounding_boost(premise_ids)
            conf = min(min_premise_conf, conf)

            block_height = max(p.source_block for p in premises)
            conclusion = self.kg.add_node(
                node_type='inference',
                content=combined,
                confidence=conf,
                source_block=block_height,
            )

            # Link premises to conclusion
            for p in premises:
                self.kg.add_edge(p.node_id, conclusion.node_id, 'derives')

            chain.append(ReasoningStep(
                step_type='rule',
                content=rule_content or {'operation': 'conjunction'},
                confidence=1.0,
            ))
            chain.append(ReasoningStep(
                step_type='conclusion',
                node_id=conclusion.node_id,
                content=combined,
                confidence=conf,
            ))

            result = ReasoningResult(
                operation_type='deductive',
                premise_ids=premise_ids,
                conclusion_node_id=conclusion.node_id,
                confidence=conf,
                chain=chain,
                success=True,
                explanation=f"Deduced new conclusion from {len(premises)} premises (graph traversal)",
            )
        else:
            # Found existing common conclusion
            best_id = max(common, key=lambda nid: self.kg.get_node(nid).confidence if self.kg.get_node(nid) else 0)
            best_node = self.kg.get_node(best_id)
            conf = min(p.confidence for p in premises) * (best_node.confidence if best_node else 0.5)
            # Boost confidence when premises are grounded in external truth
            conf = min(1.0, conf * self._grounding_boost(premise_ids))

            chain.append(ReasoningStep(
                step_type='conclusion',
                node_id=best_id,
                content=best_node.content if best_node else {},
                confidence=conf,
            ))

            # Generate meaningful explanation (Improvement 46)
            best_text = ''
            if best_node and best_node.content:
                best_text = str(best_node.content.get('text', best_node.content.get('type', '')))[:100]
            premise_texts = [str(p.content.get('text', p.content.get('type', '')))[:50] for p in premises]
            expl = (
                f"Deduced from {len(premises)} premises "
                f"({', '.join(premise_texts[:3])}) -> "
                f"conclusion: {best_text or f'node {best_id}'} "
                f"(confidence: {conf:.4f}, graph traversal)"
            )

            result = ReasoningResult(
                operation_type='deductive',
                premise_ids=premise_ids,
                conclusion_node_id=best_id,
                confidence=conf,
                chain=chain,
                success=True,
                explanation=expl,
            )

        # Note: axiom confidence floor removed — axioms should be falsifiable
        # through evidence. Artificially preventing axiom confidence from
        # dropping below 0.8 creates an unfalsifiable knowledge base.

        return result

    def detect_conflicts(self, conclusion_id: int) -> List[int]:
        """Detect conflicts between a new conclusion and existing high-confidence nodes.

        Checks if the new conclusion contradicts existing nodes (confidence > 0.7)
        in the same domain. If so, adds a 'contradicts' edge.

        Args:
            conclusion_id: Node ID of the new conclusion to check.

        Returns:
            List of conflicting node IDs that had 'contradicts' edges added.
        """
        conclusion = self.kg.get_node(conclusion_id)
        if not conclusion:
            return []

        # Determine the conclusion's domain from its content
        conclusion_domain = conclusion.content.get('type', '')
        if not conclusion_domain:
            conclusion_domain = conclusion.node_type

        conflicting_ids: List[int] = []

        # Check nodes in the same domain with high confidence
        # Use domain index for O(1) lookup when available
        if hasattr(self.kg, 'nodes'):
            if hasattr(self.kg, 'get_nodes_by_domain') and conclusion_domain:
                domain_nodes = self.kg.get_nodes_by_domain(conclusion_domain, limit=200)
                candidates = {n.node_id: n for n in domain_nodes}
            else:
                candidates = {nid: n for nid, n in self.kg.nodes.items()
                              if (n.content.get('type', '') or n.node_type) == conclusion_domain}
            for nid, node in candidates.items():
                if nid == conclusion_id:
                    continue
                if node.confidence <= 0.7:
                    continue

                # Check for contradictory content (opposite conclusions about same topic)
                conclusion_content = conclusion.content
                node_content = node.content

                # Detect contradiction: both are inferences/generalizations about
                # the same premises but with significantly different confidence
                if (conclusion.node_type == 'inference' and node.node_type == 'inference'
                        and abs(conclusion.confidence - node.confidence) > 0.3):
                    # Check if they share premise lineage
                    conclusion_neighbors = {n.node_id for n in self.kg.get_neighbors(conclusion_id, 'in')}
                    node_neighbors = {n.node_id for n in self.kg.get_neighbors(nid, 'in')}
                    if conclusion_neighbors & node_neighbors:
                        self.kg.add_edge(conclusion_id, nid, 'contradicts')
                        conflicting_ids.append(nid)
                        logger.debug(
                            f"Conflict detected: node {conclusion_id} contradicts "
                            f"node {nid} (domain={conclusion_domain})"
                        )

        return conflicting_ids

    def induce(self, observation_ids: List[int]) -> ReasoningResult:
        """
        Inductive reasoning: generalize from observations.

        Finds patterns across observation nodes and creates a generalized node.
        Confidence is based on number of supporting observations and their agreement.
        """
        chain = []
        observations = []
        for oid in observation_ids:
            node = self.kg.get_node(oid)
            if node:
                observations.append(node)
                chain.append(ReasoningStep(
                    step_type='observation',
                    node_id=oid,
                    content=node.content,
                    confidence=node.confidence,
                ))

        if len(observations) < 2:
            return ReasoningResult(
                operation_type='inductive',
                premise_ids=observation_ids,
                confidence=0.0,
                chain=chain,
                success=False,
                explanation='Need at least 2 observations for induction',
            )

        # Find common node types and shared edge patterns among observations (Improvement 50)
        type_counts: Dict[str, int] = {}
        domain_counts: Dict[str, int] = {}
        shared_neighbors: Dict[int, int] = {}  # neighbor_id -> count of observations connected
        for obs in observations:
            nt = obs.node_type
            type_counts[nt] = type_counts.get(nt, 0) + 1
            if obs.domain:
                domain_counts[obs.domain] = domain_counts.get(obs.domain, 0) + 1
            # Track shared neighbors for meaningful pattern detection
            for neighbor in self.kg.get_neighbors(obs.node_id, 'out'):
                shared_neighbors[neighbor.node_id] = shared_neighbors.get(neighbor.node_id, 0) + 1

        dominant_type = max(type_counts, key=type_counts.get)
        dominant_domain = max(domain_counts, key=domain_counts.get) if domain_counts else 'general'
        # Nodes connected by multiple observations are pattern hubs
        pattern_hubs = [nid for nid, count in shared_neighbors.items() if count >= 2]

        # Confidence scales with number of observations (asymptotic to 1.0)
        n = len(observations)
        avg_conf = sum(o.confidence for o in observations) / n
        # Inductive confidence: increases with more evidence but never reaches 1.0
        inductive_conf = avg_conf * (1.0 - 1.0 / (n + 1))
        # Boost confidence when observations are grounded in external truth
        inductive_conf = min(1.0, inductive_conf * self._grounding_boost(observation_ids))

        # Create generalization node with meaningful content summary
        # Extract actual statistics from observations
        difficulty_values = [o.content.get('difficulty') for o in observations
                             if o.content.get('difficulty') is not None]
        energy_values = [o.content.get('energy') for o in observations
                         if o.content.get('energy') is not None]
        height_values = [o.content.get('height', o.content.get('block_height'))
                         for o in observations
                         if o.content.get('height') or o.content.get('block_height')]

        # Build meaningful pattern description
        pattern_parts = []
        if height_values:
            h_min, h_max = min(height_values), max(height_values)
            if h_min == h_max:
                pattern_parts.append(f"block {h_min}")
            else:
                pattern_parts.append(f"blocks {h_min}-{h_max}")
        if difficulty_values:
            avg_diff = sum(difficulty_values) / len(difficulty_values)
            pattern_parts.append(f"avg difficulty {avg_diff:.2f}")
        if energy_values:
            avg_energy = sum(energy_values) / len(energy_values)
            pattern_parts.append(f"avg energy {avg_energy:.4f}")
        if not pattern_parts:
            pattern_parts.append(f"{n} {dominant_type} observations")

        # Detect cross-domain generalization
        obs_domains = set(getattr(o, 'domain', '') or 'general' for o in observations)
        is_cross_domain = len(obs_domains) > 1
        generalization = {
            'type': 'generalization',
            'pattern': f"Pattern from {n} obs: {', '.join(pattern_parts)}",
            'observation_count': n,
            'dominant_type': dominant_type,
            'dominant_domain': dominant_domain,
            'pattern_hubs': pattern_hubs[:5],
            'type_distribution': type_counts,
            'cross_domain': is_cross_domain,
        }
        if difficulty_values:
            generalization['avg_difficulty'] = round(
                sum(difficulty_values) / len(difficulty_values), 4
            )
        if energy_values:
            generalization['avg_energy'] = round(
                sum(energy_values) / len(energy_values), 6
            )

        block_height = max(o.source_block for o in observations)
        gen_node = self.kg.add_node(
            node_type='inference',
            content=generalization,
            confidence=inductive_conf,
            source_block=block_height,
        )

        for obs in observations:
            self.kg.add_edge(obs.node_id, gen_node.node_id, 'supports')

        chain.append(ReasoningStep(
            step_type='conclusion',
            node_id=gen_node.node_id,
            content=generalization,
            confidence=inductive_conf,
        ))

        result = ReasoningResult(
            operation_type='inductive',
            premise_ids=observation_ids,
            conclusion_node_id=gen_node.node_id,
            confidence=inductive_conf,
            chain=chain,
            success=True,
            explanation=(
                f"Induced generalization from {n} {dominant_type} observations "
                f"in {dominant_domain}: {', '.join(pattern_parts[:3])}. "
                f"Confidence: {inductive_conf:.4f}, "
                f"{len(pattern_hubs)} shared structural hubs found."
            ),
        )

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def abduce(self, observation_id: int, rule_node_ids: List[int] = None) -> ReasoningResult:
        """
        Abductive reasoning: infer best explanation for an observation.

        Given an observation, find nodes that could explain it (reverse inference).
        """
        chain = []
        observation = self.kg.get_node(observation_id)
        if not observation:
            return ReasoningResult(
                operation_type='abductive',
                premise_ids=[observation_id],
                success=False,
                explanation='Observation node not found',
            )

        chain.append(ReasoningStep(
            step_type='observation',
            node_id=observation_id,
            content=observation.content,
            confidence=observation.confidence,
        ))

        # Find potential explanations: nodes that point TO this observation
        explanations = self.kg.get_neighbors(observation_id, 'in')

        # Boost confidence when the observation is grounded in external truth
        grounding_factor = self._grounding_boost([observation_id])

        if not explanations:
            # No existing explanations — generate hypothesis
            hypothesis = {
                'type': 'hypothesis',
                'explains': observation.content,
                'method': 'abductive_inference',
                'cross_domain': False,
            }
            hyp_conf = min(1.0, 0.3 * grounding_factor)
            hyp_node = self.kg.add_node(
                node_type='inference',
                content=hypothesis,
                confidence=hyp_conf,
                source_block=observation.source_block,
            )
            self.kg.add_edge(hyp_node.node_id, observation_id, 'derives')

            chain.append(ReasoningStep(
                step_type='conclusion',
                node_id=hyp_node.node_id,
                content=hypothesis,
                confidence=hyp_conf,
            ))

            result = ReasoningResult(
                operation_type='abductive',
                premise_ids=[observation_id],
                conclusion_node_id=hyp_node.node_id,
                confidence=hyp_conf,
                chain=chain,
                success=True,
                explanation='Generated hypothesis to explain observation',
            )
        else:
            # Rank explanations by confidence
            best = max(explanations, key=lambda n: n.confidence)
            abd_conf = min(1.0, best.confidence * observation.confidence * grounding_factor)
            chain.append(ReasoningStep(
                step_type='conclusion',
                node_id=best.node_id,
                content=best.content,
                confidence=abd_conf,
            ))

            result = ReasoningResult(
                operation_type='abductive',
                premise_ids=[observation_id],
                conclusion_node_id=best.node_id,
                confidence=abd_conf,
                chain=chain,
                success=True,
                explanation=f"Best explanation: node {best.node_id} (conf: {best.confidence:.4f})",
            )

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def _store_operation(self, result: ReasoningResult):
        """Persist reasoning operation to database"""
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                session.execute(
                    text("""
                        INSERT INTO reasoning_operations
                        (operation_type, premise_nodes, conclusion_node_id,
                         confidence, reasoning_chain, block_height)
                        VALUES (:otype, CAST(:premises AS jsonb), :cid,
                                :conf, CAST(:chain AS jsonb), :bh)
                    """),
                    {
                        'otype': result.operation_type,
                        'premises': json.dumps(result.premise_ids),
                        'cid': result.conclusion_node_id,
                        'conf': result.confidence,
                        'chain': json.dumps([s.to_dict() for s in result.chain]),
                        'bh': result.block_height,
                    }
                )
                session.commit()
        except Exception as e:
            logger.warning(f"Failed to store reasoning operation: {e}")

    def chain_of_thought(self, query_node_ids: List[int],
                          max_depth: int = 5) -> ReasoningResult:
        """
        Multi-step chain-of-thought reasoning.

        Starting from query nodes, performs iterative reasoning steps:
        1. Gather context from neighbors of query nodes
        2. Attempt deductive reasoning on gathered context
        3. If gaps found, attempt abductive reasoning to fill them
        4. Combine all steps into a unified reasoning trace

        Args:
            query_node_ids: Starting nodes for the reasoning chain
            max_depth: Maximum reasoning depth (steps)

        Returns:
            ReasoningResult with full chain-of-thought trace
        """
        chain: List[ReasoningStep] = []
        visited: set = set()
        frontier = list(query_node_ids)
        overall_confidence = 1.0
        conclusion_id: Optional[int] = None

        # Step 1: Gather starting context
        for nid in query_node_ids:
            node = self.kg.get_node(nid)
            if node:
                chain.append(ReasoningStep(
                    step_type='premise',
                    node_id=nid,
                    content=node.content,
                    confidence=node.confidence,
                ))
                visited.add(nid)

        if not chain:
            return ReasoningResult(
                operation_type='chain_of_thought',
                premise_ids=query_node_ids,
                success=False,
                explanation='No valid starting nodes found',
            )

        # Step 2: Iterative reasoning over expanding frontier
        # Import confidence floor from Config (Improvement 37)
        confidence_floor = 0.1
        try:
            from ..config import Config
            confidence_floor = getattr(Config, 'REASONING_CONFIDENCE_FLOOR', 0.1)
        except Exception:
            pass

        import time as _cot_time
        _cot_deadline = _cot_time.time() + 4.0  # hard 4-second budget for CoT

        for depth in range(max_depth):
            # Hard time-budget guard — never spend more than 4s total in CoT
            if _cot_time.time() > _cot_deadline:
                logger.debug(f"Chain-of-thought budget exceeded at depth {depth}, returning early")
                break

            # Stop if confidence drops below floor (prevents meaningless chains)
            if overall_confidence < confidence_floor:
                logger.debug(
                    f"Chain-of-thought stopped at depth {depth}: "
                    f"confidence {overall_confidence:.4f} < floor {confidence_floor}"
                )
                break

            next_frontier: List[int] = []

            # Explore neighbors of current frontier — cap at 10 to prevent O(n²) blowup
            context_nodes: List[int] = []
            for nid in frontier[:10]:
                if nid in visited:
                    continue
                visited.add(nid)
                node = self.kg.get_node(nid)
                if node:
                    context_nodes.append(nid)
                    chain.append(ReasoningStep(
                        step_type='observation',
                        node_id=nid,
                        content=node.content,
                        confidence=node.confidence,
                    ))

            # Limit reasoning inputs to 5 nodes — deduce does O(n) BFS per premise
            _sample = context_nodes[:5]

            # Try deductive step if we have enough context
            if len(_sample) >= 2:
                deduction = self.deduce(_sample)
                if deduction.success and deduction.conclusion_node_id:
                    chain.append(ReasoningStep(
                        step_type='conclusion',
                        node_id=deduction.conclusion_node_id,
                        content={'type': 'deductive_step', 'depth': depth},
                        confidence=deduction.confidence,
                    ))
                    overall_confidence = min(overall_confidence, deduction.confidence)
                    conclusion_id = deduction.conclusion_node_id
                    next_frontier.append(deduction.conclusion_node_id)

            # Try abductive step for unexplained observations (Improvement 40)
            unexplained = [
                nid for nid in _sample
                if self.kg.get_node(nid) and not self.kg.get_node(nid).edges_in
            ]
            if unexplained:
                abduction = self.abduce(unexplained[0])
                if abduction.success and abduction.conclusion_node_id:
                    chain.append(ReasoningStep(
                        step_type='conclusion',
                        node_id=abduction.conclusion_node_id,
                        content={'type': 'abductive_step', 'depth': depth},
                        confidence=abduction.confidence,
                    ))
                    next_frontier.append(abduction.conclusion_node_id)

            # Try inductive step if we have multiple observations (Improvement 40)
            if len(_sample) >= 3:
                induction = self.induce(_sample)
                if induction.success and induction.conclusion_node_id:
                    chain.append(ReasoningStep(
                        step_type='conclusion',
                        node_id=induction.conclusion_node_id,
                        content={'type': 'inductive_step', 'depth': depth},
                        confidence=induction.confidence,
                    ))
                    next_frontier.append(induction.conclusion_node_id)

            # Expand frontier for next iteration — cap at 20 new nodes
            added = 0
            for nid in frontier:
                if added >= 20:
                    break
                node = self.kg.get_node(nid)
                if node:
                    for neighbor_id in node.edges_out:
                        if neighbor_id not in visited and added < 20:
                            next_frontier.append(neighbor_id)
                            added += 1

            frontier = next_frontier
            if not frontier:
                break  # No more nodes to explore

        # If no conclusion found via deduction, try abduction (Improvement 40)
        if conclusion_id is None and frontier:
            abd_result = self.abduce(frontier[0])
            if abd_result.success:
                chain.extend(abd_result.chain)
                conclusion_id = abd_result.conclusion_node_id
                overall_confidence = min(overall_confidence, abd_result.confidence)

        result = ReasoningResult(
            operation_type='chain_of_thought',
            premise_ids=query_node_ids,
            conclusion_node_id=conclusion_id,
            confidence=max(0.0, min(1.0, overall_confidence)),
            chain=chain,
            success=len(chain) > len(query_node_ids),
            explanation=f"Chain-of-thought: {len(chain)} steps, depth explored",
        )

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def resolve_contradiction(self, node_a_id: int, node_b_id: int) -> ReasoningResult:
        """
        Resolve a contradiction between two knowledge nodes.

        Strategy:
        1. Compare confidence scores — higher confidence wins
        2. Check supporting evidence (count and confidence of supporters)
        3. Create a resolution node recording the outcome
        4. Reduce confidence of the losing node

        Args:
            node_a_id: First contradicting node
            node_b_id: Second contradicting node

        Returns:
            ReasoningResult with resolution trace
        """
        chain: List[ReasoningStep] = []
        node_a = self.kg.get_node(node_a_id)
        node_b = self.kg.get_node(node_b_id)

        if not node_a or not node_b:
            return ReasoningResult(
                operation_type='contradiction_resolution',
                premise_ids=[node_a_id, node_b_id],
                success=False,
                explanation='One or both nodes not found',
            )

        chain.append(ReasoningStep(
            step_type='premise', node_id=node_a_id,
            content=node_a.content, confidence=node_a.confidence,
        ))
        chain.append(ReasoningStep(
            step_type='premise', node_id=node_b_id,
            content=node_b.content, confidence=node_b.confidence,
        ))

        # Count supporting evidence for each node
        supporters_a = self.kg.get_neighbors(node_a_id, 'in')
        supporters_b = self.kg.get_neighbors(node_b_id, 'in')

        support_score_a = sum(n.confidence for n in supporters_a) + node_a.confidence
        support_score_b = sum(n.confidence for n in supporters_b) + node_b.confidence

        # Determine winner
        if support_score_a >= support_score_b:
            winner_id, loser_id = node_a_id, node_b_id
            winner_score, loser_score = support_score_a, support_score_b
        else:
            winner_id, loser_id = node_b_id, node_a_id
            winner_score, loser_score = support_score_b, support_score_a

        # Reduce confidence of the losing node
        loser = self.kg.get_node(loser_id)
        if loser:
            penalty = 0.3 * (winner_score / max(winner_score + loser_score, 0.001))
            loser.confidence = max(0.05, loser.confidence - penalty)

        # Record the contradiction edge
        self.kg.add_edge(winner_id, loser_id, 'contradicts')

        # Create resolution node
        resolution_content = {
            'type': 'contradiction_resolution',
            'winner_id': winner_id,
            'loser_id': loser_id,
            'winner_support': round(winner_score, 4),
            'loser_support': round(loser_score, 4),
        }
        resolution_node = self.kg.add_node(
            node_type='inference',
            content=resolution_content,
            confidence=winner_score / max(winner_score + loser_score, 0.001),
            source_block=max(node_a.source_block, node_b.source_block),
        )

        chain.append(ReasoningStep(
            step_type='rule',
            content={'operation': 'contradiction_resolution', 'method': 'evidence_weight'},
            confidence=1.0,
        ))
        chain.append(ReasoningStep(
            step_type='conclusion',
            node_id=resolution_node.node_id,
            content=resolution_content,
            confidence=resolution_node.confidence,
        ))

        result = ReasoningResult(
            operation_type='contradiction_resolution',
            premise_ids=[node_a_id, node_b_id],
            conclusion_node_id=resolution_node.node_id,
            confidence=resolution_node.confidence,
            chain=chain,
            success=True,
            explanation=f"Resolved: node {winner_id} wins (score {winner_score:.2f} vs {loser_score:.2f})",
        )

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def find_analogies(self, source_node_id: int,
                       target_domain: Optional[str] = None,
                       max_results: int = 5) -> ReasoningResult:
        """Find structural analogies between a source node and nodes in other domains.

        Compares the edge-type pattern around the source node with patterns
        around nodes in different domains.  Matching patterns indicate an
        analogous relationship.

        Args:
            source_node_id: Node to find analogies for.
            target_domain: If set, only search this domain. Otherwise all domains.
            max_results: Maximum analogies to return.

        Returns:
            ReasoningResult with analogy findings.
        """
        chain: List[ReasoningStep] = []
        source = self.kg.get_node(source_node_id)
        if not source:
            return ReasoningResult(
                operation_type='analogy_detection',
                premise_ids=[source_node_id],
                success=False,
                explanation='Source node not found',
            )

        # Build edge-type pattern for source (outgoing edge types sorted)
        source_pattern = self._get_edge_pattern(source_node_id)
        if not source_pattern:
            return ReasoningResult(
                operation_type='analogy_detection',
                premise_ids=[source_node_id],
                success=False,
                explanation='Source node has no edges — no pattern to match',
            )

        chain.append(ReasoningStep(
            step_type='premise', node_id=source_node_id,
            content=source.content, confidence=source.confidence,
        ))

        # Find candidates in other domains — use domain index for efficiency
        source_domain = source.domain or ''
        if target_domain and hasattr(self.kg, 'get_nodes_by_domain'):
            candidates = [
                n for n in self.kg.get_nodes_by_domain(target_domain, limit=200)
                if n.node_id != source_node_id
                and n.node_type in ('assertion', 'inference')
            ]
        elif hasattr(self.kg, 'get_domains') and source_domain:
            # Get nodes from all OTHER domains
            candidates = []
            for d in self.kg.get_domains():
                if d == source_domain:
                    continue
                candidates.extend(
                    n for n in self.kg.get_nodes_by_domain(d, limit=50)
                    if n.node_id != source_node_id
                    and n.node_type in ('assertion', 'inference')
                )
        else:
            candidates = [
                n for n in self.kg.nodes.values()
                if n.node_id != source_node_id
                and (n.domain != source_domain or not source_domain)
                and n.node_type in ('assertion', 'inference')
            ]

        analogies_found: List[dict] = []
        for candidate in candidates:
            cand_pattern = self._get_edge_pattern(candidate.node_id)
            if not cand_pattern:
                continue

            # Compare patterns: count matching edge types
            common = len(source_pattern & cand_pattern)
            total = len(source_pattern | cand_pattern)
            similarity = common / total if total > 0 else 0

            if similarity >= 0.3 and common >= 1:
                analogies_found.append({
                    'node_id': candidate.node_id,
                    'domain': candidate.domain,
                    'similarity': round(similarity, 3),
                    'common_edge_types': list(source_pattern & cand_pattern),
                })
                if len(analogies_found) >= max_results:
                    break

        # Create analogous_to edges for strong matches
        created_edges = 0
        conclusion_id = None
        for analogy in analogies_found:
            edge = self.kg.add_edge(
                source_node_id, analogy['node_id'], 'analogous_to',
                weight=analogy['similarity']
            )
            if edge:
                created_edges += 1
                chain.append(ReasoningStep(
                    step_type='conclusion',
                    node_id=analogy['node_id'],
                    content={
                        'type': 'analogy',
                        'source_domain': source_domain,
                        'target_domain': analogy['domain'],
                        'similarity': analogy['similarity'],
                        'common_patterns': analogy['common_edge_types'],
                    },
                    confidence=analogy['similarity'],
                ))
                conclusion_id = analogy['node_id']

        result = ReasoningResult(
            operation_type='analogy_detection',
            premise_ids=[source_node_id],
            conclusion_node_id=conclusion_id,
            confidence=max((a['similarity'] for a in analogies_found), default=0.0),
            chain=chain,
            success=created_edges > 0,
            explanation=f"Found {created_edges} analogies across domains",
        )
        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def _get_edge_pattern(self, node_id: int) -> set:
        """Get the set of edge types connected to a node (both in and out)."""
        pattern: set = set()
        for edge in self.kg.edges:
            if edge.from_node_id == node_id or edge.to_node_id == node_id:
                pattern.add(edge.edge_type)
        return pattern

    def archive_old_reasoning(self, current_block: int, retain_blocks: int = 50000) -> int:
        """Archive old reasoning operations to summary rows.

        Operations older than ``retain_blocks`` are aggregated by type
        into summary rows and the originals are deleted from the DB.

        Args:
            current_block: Current block height.
            retain_blocks: Keep individual operations from the last N blocks.

        Returns:
            Number of rows archived (deleted).
        """
        cutoff_block = current_block - retain_blocks
        if cutoff_block <= 0:
            return 0

        archived = 0
        try:
            from sqlalchemy import text
            with self.db.get_session() as session:
                # Aggregate old operations into summary rows
                summaries = session.execute(
                    text("""
                        SELECT operation_type, COUNT(*) as cnt,
                               AVG(confidence) as avg_conf,
                               MIN(block_height) as min_block,
                               MAX(block_height) as max_block
                        FROM reasoning_operations
                        WHERE block_height < :cutoff
                        GROUP BY operation_type
                    """),
                    {'cutoff': cutoff_block}
                ).fetchall()

                for row in summaries:
                    if row[1] > 0:  # cnt > 0
                        session.execute(
                            text("""
                                INSERT INTO reasoning_operations
                                (operation_type, confidence, block_height, premise_nodes, conclusion_node_id, reasoning_chain)
                                VALUES (:otype, :conf, :block,
                                        CAST(:premises AS jsonb), 0, CAST(:chain AS jsonb))
                                ON CONFLICT DO NOTHING
                            """),
                            {
                                'otype': f"summary_{row[0]}",
                                'conf': float(row[2] or 0),
                                'block': cutoff_block,
                                'premises': json.dumps({
                                    'count': row[1],
                                    'block_range': [row[3], row[4]],
                                }),
                                'chain': json.dumps({
                                    'archived_count': row[1],
                                    'avg_confidence': round(float(row[2] or 0), 4),
                                }),
                            }
                        )

                # Delete old individual operations
                result = session.execute(
                    text("""
                        DELETE FROM reasoning_operations
                        WHERE block_height < :cutoff
                          AND operation_type NOT LIKE 'summary_%'
                    """),
                    {'cutoff': cutoff_block}
                )
                archived = result.rowcount
                session.commit()

            if archived > 0:
                logger.info(f"Archived {archived} old reasoning operations (before block {cutoff_block})")
        except Exception as e:
            logger.debug(f"Reasoning archive failed: {e}")
        return archived

    # ------------------------------------------------------------------ #
    #  Chain-of-Thought with Backtracking (Phase 3.4)                     #
    # ------------------------------------------------------------------ #

    def _gather_context(self, frontier: List[int], visited: set) -> List[int]:
        """Get neighbor node IDs reachable from *frontier* that are not yet visited.

        Collects outgoing and incoming neighbor IDs from each frontier node,
        filtering out any IDs already in *visited*.

        Args:
            frontier: Current frontier node IDs to expand from.
            visited: Set of node IDs already processed.

        Returns:
            De-duplicated list of unvisited neighbor node IDs.
        """
        context_ids: List[int] = []
        seen: set = set()
        for nid in frontier:
            node = self.kg.get_node(nid)
            if not node:
                continue
            # Outgoing neighbors
            for neighbor_id in node.edges_out:
                if neighbor_id not in visited and neighbor_id not in seen:
                    seen.add(neighbor_id)
                    context_ids.append(neighbor_id)
            # Incoming neighbors (so we can reason backwards too)
            for neighbor_id in node.edges_in:
                if neighbor_id not in visited and neighbor_id not in seen:
                    seen.add(neighbor_id)
                    context_ids.append(neighbor_id)
        return context_ids

    def _try_operation(self, op_type: str, context: List[int],
                       visited: set) -> Optional[ReasoningResult]:
        """Attempt a single reasoning operation of the given type.

        Selects appropriate premise/observation IDs from *context* and
        delegates to :meth:`deduce`, :meth:`induce`, or :meth:`abduce`.

        Args:
            op_type: One of ``'inductive'``, ``'deductive'``, ``'abductive'``.
            context: Available node IDs for the operation.
            visited: Already-visited node IDs (used to avoid repeats).

        Returns:
            A :class:`ReasoningResult` on success, or ``None`` if the
            operation cannot be performed with the available context.
        """
        if not context:
            return None

        try:
            if op_type == 'inductive':
                # Need 2+ observation-like nodes
                obs_ids = [
                    nid for nid in context
                    if self.kg.get_node(nid) and
                    self.kg.get_node(nid).node_type in ('observation', 'assertion', 'meta_observation')
                ]
                if len(obs_ids) >= 2:
                    return self.induce(obs_ids[:5])  # cap to avoid huge ops
                return None

            elif op_type == 'deductive':
                # Need 2+ inference/assertion nodes
                inf_ids = [
                    nid for nid in context
                    if self.kg.get_node(nid) and
                    self.kg.get_node(nid).node_type in ('inference', 'assertion', 'axiom')
                ]
                if len(inf_ids) >= 2:
                    return self.deduce(inf_ids[:5])
                return None

            elif op_type == 'abductive':
                # Need at least 1 observation node
                obs_ids = [
                    nid for nid in context
                    if self.kg.get_node(nid) and
                    self.kg.get_node(nid).node_type in ('observation', 'meta_observation')
                ]
                if obs_ids:
                    return self.abduce(obs_ids[0])
                # Fall back to any node in context
                return self.abduce(context[0])

        except Exception as e:
            logger.debug(f"_try_operation({op_type}) failed: {e}")
            return None

        return None

    def _check_chain_consistency(self, chain: List[ReasoningStep],
                                 new_node_id: int) -> Optional[dict]:
        """Check whether a newly concluded node contradicts anything in *chain*.

        Two checks are performed:

        1. **Explicit contradicts edges** — if any edge of type ``'contradicts'``
           links the new node to a node already in the chain (in either direction).
        2. **Content conflict** — if the new node is an inference whose content
           directly opposes an earlier chain step (same subject with opposing
           numeric values or negation markers).

        Args:
            chain: The reasoning chain built so far.
            new_node_id: The node ID of the conclusion to check.

        Returns:
            A dict describing the contradiction if found, or ``None`` if
            the new node is consistent.
        """
        new_node = self.kg.get_node(new_node_id)
        if not new_node:
            return None

        # Collect all node IDs currently in the chain
        chain_node_ids: set = set()
        for step in chain:
            if step.node_id is not None:
                chain_node_ids.add(step.node_id)

        if not chain_node_ids:
            return None

        # Check 1: Explicit 'contradicts' edges from new_node → chain nodes
        for edge in self.kg.get_edges_from(new_node_id):
            if edge.edge_type == 'contradicts' and edge.to_node_id in chain_node_ids:
                return {
                    'type': 'explicit_contradiction',
                    'new_node_id': new_node_id,
                    'conflicting_node_id': edge.to_node_id,
                    'edge_weight': edge.weight,
                    'reason': f"Node {new_node_id} explicitly contradicts chain node {edge.to_node_id}",
                }

        # Check 2: Explicit 'contradicts' edges from chain nodes → new_node
        for edge in self.kg.get_edges_to(new_node_id):
            if edge.edge_type == 'contradicts' and edge.from_node_id in chain_node_ids:
                return {
                    'type': 'explicit_contradiction',
                    'new_node_id': new_node_id,
                    'conflicting_node_id': edge.from_node_id,
                    'edge_weight': edge.weight,
                    'reason': f"Chain node {edge.from_node_id} explicitly contradicts new node {new_node_id}",
                }

        # Check 3: Content-level conflict (same domain, opposing values)
        new_content_text = str(new_node.content.get('text', '')).lower()
        if new_content_text:
            import re
            new_numbers = set(re.findall(r'\b\d+\.?\d*\b', new_content_text))
            new_words = set(new_content_text.split())

            for step in chain:
                if step.node_id is None or step.node_id == new_node_id:
                    continue
                chain_node = self.kg.get_node(step.node_id)
                if not chain_node:
                    continue
                # Only compare same-domain nodes
                if chain_node.domain and new_node.domain and chain_node.domain != new_node.domain:
                    continue
                chain_text = str(chain_node.content.get('text', '')).lower()
                if not chain_text:
                    continue
                chain_words = set(chain_text.split())
                overlap = len(new_words & chain_words)
                total = len(new_words | chain_words)
                word_sim = overlap / total if total > 0 else 0

                if word_sim > 0.4:
                    chain_numbers = set(re.findall(r'\b\d+\.?\d*\b', chain_text))
                    if (new_numbers and chain_numbers
                            and new_numbers != chain_numbers
                            and len(new_numbers & chain_numbers) == 0):
                        return {
                            'type': 'content_conflict',
                            'new_node_id': new_node_id,
                            'conflicting_node_id': step.node_id,
                            'word_similarity': round(word_sim, 3),
                            'reason': (
                                f"Content conflict: node {new_node_id} and chain node "
                                f"{step.node_id} share {overlap}/{total} words but have "
                                f"different numeric values ({new_numbers} vs {chain_numbers})"
                            ),
                        }

        return None

    def reason_chain(self, query_node_ids: List[int], max_depth: int = 5,
                     max_backtrack: int = 3,
                     strategy_weights: Optional[Dict[str, float]] = None) -> ReasoningResult:
        """Chain-of-thought reasoning with contradiction-driven backtracking.

        Builds a reasoning chain step-by-step from the query nodes.  At each
        depth level the method:

        1. Gathers context nodes from the current frontier.
        2. Selects the best reasoning operation for the context, biased by
           strategy_weights from self-improvement if provided:
           - 2+ observation nodes → try inductive first
           - 2+ inference/assertion nodes → try deductive first
           - isolated observation → try abductive
        3. After each successful step, checks consistency with the existing
           chain (explicit ``contradicts`` edges and content conflicts).
        4. On contradiction: saves the abandoned path, restores the last
           checkpoint, marks the contradicting conclusion as visited (so
           the same dead end is not revisited), and retries.
        5. Stops when ``max_depth`` is reached, no further context is
           available, or ``max_backtrack`` backtracks have been exhausted.

        Args:
            query_node_ids: Starting node IDs for the reasoning chain.
            max_depth: Maximum number of reasoning steps.
            max_backtrack: Maximum number of backtrack attempts allowed.

        Returns:
            A :class:`ReasoningResult` containing:
            - The successful chain of reasoning steps
            - ``backtrack_count`` and ``abandoned_paths`` in the result's
              ``content`` field (serialised in ``explanation`` and the
              conclusion step's ``content``)
        """
        chain: List[ReasoningStep] = []
        visited: set = set()
        backtrack_count: int = 0
        abandoned_paths: List[dict] = []

        # Initialise chain with query nodes
        frontier: List[int] = []
        for nid in query_node_ids:
            node = self.kg.get_node(nid)
            if node:
                chain.append(ReasoningStep(
                    step_type='premise',
                    node_id=nid,
                    content=node.content,
                    confidence=node.confidence,
                ))
                visited.add(nid)
                frontier.append(nid)

        if not chain:
            return ReasoningResult(
                operation_type='reason_chain',
                premise_ids=query_node_ids,
                success=False,
                explanation='No valid starting nodes found',
            )

        # Save initial checkpoint for backtracking
        checkpoints: List[tuple] = [
            ([s for s in chain], list(frontier), set(visited))
        ]

        conclusion_id: Optional[int] = None
        overall_confidence: float = 1.0

        for depth in range(max_depth):
            # ---- 1. Gather context from frontier ----
            context = self._gather_context(frontier, visited)
            if not context:
                logger.debug(f"reason_chain depth {depth}: no new context from frontier")
                break

            # Categorise context nodes by type for operation selection
            obs_count = 0
            inf_count = 0
            for cid in context:
                cnode = self.kg.get_node(cid)
                if not cnode:
                    continue
                if cnode.node_type in ('observation', 'meta_observation'):
                    obs_count += 1
                elif cnode.node_type in ('inference', 'assertion', 'axiom'):
                    inf_count += 1

            # ---- 2. Determine operation priority order ----
            # Start with context-based defaults
            if obs_count >= 2:
                op_order = ['inductive', 'deductive', 'abductive']
            elif inf_count >= 2:
                op_order = ['deductive', 'inductive', 'abductive']
            else:
                op_order = ['abductive', 'inductive', 'deductive']

            # If strategy_weights provided by self-improvement engine,
            # re-sort operation order by weight (highest first) while
            # still respecting context feasibility as a tiebreaker
            if strategy_weights:
                # Build a score: weight * context_bonus
                context_bonus = {
                    'inductive': 1.5 if obs_count >= 2 else 0.8,
                    'deductive': 1.5 if inf_count >= 2 else 0.8,
                    'abductive': 1.2 if obs_count < 2 and inf_count < 2 else 0.8,
                }
                scored = []
                for op in op_order:
                    w = strategy_weights.get(op, 1.0)
                    bonus = context_bonus.get(op, 1.0)
                    scored.append((op, w * bonus))
                scored.sort(key=lambda x: x[1], reverse=True)
                op_order = [op for op, _ in scored]

            # ---- 3. Try operations in priority order ----
            result: Optional[ReasoningResult] = None
            for op_type in op_order:
                result = self._try_operation(op_type, context, visited)
                if result and result.success:
                    break
            else:
                result = None

            if not result or not result.success:
                logger.debug(f"reason_chain depth {depth}: no successful operation")
                break

            # ---- 4. Check for contradictions ----
            if result.conclusion_node_id is not None:
                contradiction = self._check_chain_consistency(
                    chain, result.conclusion_node_id
                )
            else:
                contradiction = None

            if contradiction:
                backtrack_count += 1
                abandoned_paths.append({
                    'depth': depth,
                    'operation': result.operation_type,
                    'contradiction': contradiction,
                    'abandoned_conclusion': result.conclusion_node_id,
                    'chain_length_at_abandon': len(chain),
                })
                logger.info(
                    f"reason_chain: contradiction at depth {depth} "
                    f"(backtrack {backtrack_count}/{max_backtrack}): "
                    f"{contradiction.get('reason', 'unknown')}"
                )

                if backtrack_count >= max_backtrack or not checkpoints:
                    logger.info(
                        f"reason_chain: stopping — backtrack limit reached "
                        f"({backtrack_count}/{max_backtrack})"
                    )
                    break

                # Restore last checkpoint
                prev_chain, prev_frontier, prev_visited = checkpoints.pop()
                chain = [s for s in prev_chain]
                frontier = list(prev_frontier)
                visited = set(prev_visited)
                # Mark the contradicting conclusion as visited so we skip it
                if result.conclusion_node_id is not None:
                    visited.add(result.conclusion_node_id)
                continue

            # ---- 5. Accept the step — extend chain ----
            # Save checkpoint before advancing
            checkpoints.append(
                ([s for s in chain], list(frontier), set(visited))
            )

            # Add the new reasoning steps (skip premises we already have)
            for step in result.chain:
                if step.node_id is not None and step.node_id in visited:
                    continue
                chain.append(ReasoningStep(
                    step_type=step.step_type,
                    node_id=step.node_id,
                    content=step.content,
                    confidence=step.confidence,
                ))
                if step.node_id is not None:
                    visited.add(step.node_id)

            overall_confidence = min(overall_confidence, max(result.confidence, 0.01))
            conclusion_id = result.conclusion_node_id

            # Advance frontier to the conclusion
            if conclusion_id is not None:
                frontier = [conclusion_id]
            else:
                frontier = context[:3]  # fallback: use first context nodes

        # ---- Build final result ----
        final_confidence = max(0.0, min(1.0, overall_confidence))

        # Attach backtracking metadata in explanation and content
        meta = {
            'backtrack_count': backtrack_count,
            'abandoned_paths': abandoned_paths,
            'total_steps': len(chain),
            'depth_reached': min(max_depth, len(chain) - len(query_node_ids)),
        }

        explanation = (
            f"reason_chain: {len(chain)} steps, "
            f"{backtrack_count} backtracks, "
            f"{len(abandoned_paths)} abandoned paths"
        )

        result = ReasoningResult(
            operation_type='reason_chain',
            premise_ids=query_node_ids,
            conclusion_node_id=conclusion_id,
            confidence=final_confidence,
            chain=chain,
            success=len(chain) > len(query_node_ids),
            explanation=explanation,
        )
        # Store backtracking metadata in the chain's final step content
        if chain:
            chain[-1].content = {
                **chain[-1].content,
                'backtracking_meta': meta,
            }

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def get_stats(self) -> dict:
        """Get reasoning engine statistics"""
        type_counts: Dict[str, int] = {}
        for op in self._operations:
            type_counts[op.operation_type] = type_counts.get(op.operation_type, 0) + 1

        return {
            'total_operations': len(self._operations),
            'operation_types': type_counts,
            'success_rate': (
                sum(1 for op in self._operations if op.success) / max(1, len(self._operations))
            ),
            'avg_confidence': (
                sum(op.confidence for op in self._operations) / max(1, len(self._operations))
            ),
            'logic_bridge_deductions': self._logic_bridge_deductions,
            'graph_traversal_deductions': self._graph_traversal_deductions,
            'logic_bridge_available': self._logic_bridge is not None,
            'logic_bridge_loaded': self._logic_bridge_loaded,
        }

    def cross_domain_infer(self, domain_a: str, domain_b: str,
                           max_analogies: int = 10) -> List[dict]:
        """Find analogies between nodes in two different domains.

        Searches for structurally similar nodes across domain_a and domain_b,
        creating 'analogous_to' edges between matches. This feeds gate 5
        (cross-domain reasoning).

        Args:
            domain_a: First domain name.
            domain_b: Second domain name.
            max_analogies: Maximum analogies to create.

        Returns:
            List of dicts describing created analogies.
        """
        if not hasattr(self.kg, 'nodes'):
            return []

        # Use domain index for O(1) lookup instead of O(N) scan
        if hasattr(self.kg, 'get_nodes_by_domain'):
            nodes_a = self.kg.get_nodes_by_domain(domain_a, limit=50)
            nodes_b = self.kg.get_nodes_by_domain(domain_b, limit=50)
        else:
            nodes_a = [n for n in self.kg.nodes.values() if n.domain == domain_a][:50]
            nodes_b = [n for n in self.kg.nodes.values() if n.domain == domain_b][:50]

        if not nodes_a or not nodes_b:
            return []

        analogies: List[dict] = []

        # Check if vector_index is available for semantic similarity
        has_vectors = (
            hasattr(self.kg, 'vector_index')
            and self.kg.vector_index
            and len(self.kg.vector_index.embeddings) > 0
        )

        for node_a in nodes_a[:50]:  # cap to prevent O(n^2) explosion
            pattern_a = self._get_edge_pattern(node_a.node_id)
            if not pattern_a:
                continue

            for node_b in nodes_b[:50]:
                pattern_b = self._get_edge_pattern(node_b.node_id)
                if not pattern_b:
                    continue

                # Jaccard similarity of edge patterns (structural)
                common = len(pattern_a & pattern_b)
                total = len(pattern_a | pattern_b)
                if total == 0:
                    continue
                structural_sim = common / total

                # Embedding cosine similarity (semantic) — require both
                # structural AND semantic similarity for robust cross-domain inference
                semantic_sim = 0.0
                if has_vectors:
                    from .vector_index import cosine_similarity as _cos_sim
                    emb_a = self.kg.vector_index.get_embedding(node_a.node_id)
                    emb_b = self.kg.vector_index.get_embedding(node_b.node_id)
                    if emb_a and emb_b:
                        semantic_sim = _cos_sim(emb_a, emb_b)

                # Combined similarity: require both structural and semantic
                # (or just structural if no embeddings available)
                if has_vectors:
                    similarity = (structural_sim + semantic_sim) / 2.0
                    passes = structural_sim >= 0.3 and semantic_sim >= 0.3 and common >= 1
                else:
                    similarity = structural_sim
                    passes = structural_sim >= 0.4 and common >= 1

                if passes:
                    self.kg.add_edge(
                        node_a.node_id, node_b.node_id, 'analogous_to',
                        weight=similarity,
                    )
                    analogies.append({
                        'source_id': node_a.node_id,
                        'target_id': node_b.node_id,
                        'source_domain': domain_a,
                        'target_domain': domain_b,
                        'similarity': round(similarity, 4),
                        'structural_similarity': round(structural_sim, 4),
                        'semantic_similarity': round(semantic_sim, 4),
                        'common_edge_types': list(pattern_a & pattern_b),
                    })
                    if len(analogies) >= max_analogies:
                        break

            if len(analogies) >= max_analogies:
                break

        if analogies:
            logger.info(
                f"Cross-domain inference: {len(analogies)} analogies "
                f"between '{domain_a}' and '{domain_b}'"
            )

        return analogies

    def get_detailed_stats(self) -> dict:
        """Get detailed reasoning statistics broken down by operation type.

        Returns:
            Dict with operations_by_type, success_rate_by_type,
            avg_confidence_by_type, cross_domain_count, total_analogies.
        """
        ops_by_type: Dict[str, int] = {}
        success_by_type: Dict[str, int] = {}
        conf_by_type: Dict[str, float] = {}
        cross_domain_count = 0
        total_analogies = 0

        for op in self._operations:
            otype = op.operation_type
            ops_by_type[otype] = ops_by_type.get(otype, 0) + 1
            if op.success:
                success_by_type[otype] = success_by_type.get(otype, 0) + 1
            conf_by_type[otype] = conf_by_type.get(otype, 0.0) + op.confidence

            if otype == 'analogy_detection':
                total_analogies += 1
                # Check if cross-domain
                for step in op.chain:
                    if step.content.get('type') == 'analogy':
                        src = step.content.get('source_domain', '')
                        tgt = step.content.get('target_domain', '')
                        if src and tgt and src != tgt:
                            cross_domain_count += 1
                            break

        success_rate_by_type: Dict[str, float] = {}
        avg_conf_by_type: Dict[str, float] = {}
        for otype, count in ops_by_type.items():
            success_rate_by_type[otype] = round(
                success_by_type.get(otype, 0) / count, 4
            )
            avg_conf_by_type[otype] = round(
                conf_by_type.get(otype, 0.0) / count, 4
            )

        return {
            'operations_by_type': ops_by_type,
            'success_rate_by_type': success_rate_by_type,
            'avg_confidence_by_type': avg_conf_by_type,
            'cross_domain_inference_count': cross_domain_count,
            'total_analogies': total_analogies,
            'total_operations': len(self._operations),
        }
    # ------------------------------------------------------------------ #
    #  v2: Advanced Reasoning Methods (Improvements 36-50)                #
    # ------------------------------------------------------------------ #

    def set_metacognition(self, metacognition: Any) -> None:
        """Set the metacognition module for confidence calibration."""
        self._metacognition = metacognition

    def set_debate_engine(self, debate_engine: Any) -> None:
        """Set the debate engine for counter-argument generation."""
        self._debate_engine = debate_engine

    def set_block_height(self, block_height: int) -> None:
        """Update the current block height context for temporal awareness."""
        self._current_block_height = block_height

    def _cache_key(self, operation: str, node_ids: List[int]) -> str:
        """Generate a cache key for a reasoning query."""
        sorted_ids = sorted(node_ids)
        raw = f"{operation}:{','.join(str(i) for i in sorted_ids)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[ReasoningResult]:
        """Retrieve a cached reasoning result if still valid."""
        if cache_key in self._reasoning_cache:
            result, ts = self._reasoning_cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return result
            else:
                del self._reasoning_cache[cache_key]
        return None

    def _set_cached(self, cache_key: str, result: ReasoningResult) -> None:
        """Cache a reasoning result."""
        if len(self._reasoning_cache) >= self._cache_max_size:
            # Evict oldest entry
            oldest_key = min(self._reasoning_cache, key=lambda k: self._reasoning_cache[k][1])
            del self._reasoning_cache[oldest_key]
        self._reasoning_cache[cache_key] = (result, time.time())

    def _track_domain_success(self, domain: str, success: bool) -> None:
        """Track reasoning success rates per domain."""
        if domain not in self._domain_success:
            self._domain_success[domain] = {'attempts': 0, 'successes': 0}
        self._domain_success[domain]['attempts'] += 1
        if success:
            self._domain_success[domain]['successes'] += 1

    def get_domain_success_rates(self) -> Dict[str, float]:
        """Get per-domain reasoning success rates."""
        rates: Dict[str, float] = {}
        for domain, stats in self._domain_success.items():
            if stats['attempts'] > 0:
                rates[domain] = round(stats['successes'] / stats['attempts'], 4)
        return rates

    def calibrate_confidence(self, raw_confidence: float) -> float:
        """Calibrate confidence using metacognition feedback.

        If metacognition module is available, uses its calibration data
        to adjust stated confidence toward observed accuracy.

        Args:
            raw_confidence: The uncalibrated confidence value.

        Returns:
            Calibrated confidence value in [0.0, 1.0].
        """
        if self._metacognition and hasattr(self._metacognition, 'calibrate_confidence'):
            return self._metacognition.calibrate_confidence(raw_confidence)
        return raw_confidence

    def reason_by_analogy(self, source_node_id: int,
                          target_domain: str,
                          max_results: int = 5) -> ReasoningResult:
        """Analogical reasoning: find structural analogies and generate inferences.

        Goes beyond simple pattern matching by:
        1. Finding structurally analogous nodes in the target domain
        2. Examining what conclusions exist for the source node
        3. Hypothesizing that similar conclusions hold for the analogous targets

        Args:
            source_node_id: Node to reason from by analogy.
            target_domain: Domain to find analogies in.
            max_results: Maximum analogies to explore.

        Returns:
            ReasoningResult with analogy-based hypotheses.
        """
        # Check cache
        cache_key = self._cache_key('analogy', [source_node_id])
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        chain: List[ReasoningStep] = []
        source = self.kg.get_node(source_node_id)
        if not source:
            return ReasoningResult(
                operation_type='analogical',
                premise_ids=[source_node_id],
                success=False,
                explanation='Source node not found',
            )

        chain.append(ReasoningStep(
            step_type='premise', node_id=source_node_id,
            content=source.content, confidence=source.confidence,
        ))

        # Step 1: Find analogies using existing method
        analogy_result = self.find_analogies(source_node_id, target_domain, max_results)

        if not analogy_result.success:
            return ReasoningResult(
                operation_type='analogical',
                premise_ids=[source_node_id],
                success=False,
                explanation='No structural analogies found in target domain',
            )

        # Step 2: Get conclusions that exist for the source node
        source_conclusions: List[dict] = []
        for neighbor in self.kg.get_neighbors(source_node_id, 'out'):
            if neighbor.node_type == 'inference':
                source_conclusions.append({
                    'node_id': neighbor.node_id,
                    'content': neighbor.content,
                    'confidence': neighbor.confidence,
                })

        # Step 3: Generate hypotheses for each analogy
        hypotheses: List[dict] = []
        conclusion_id: Optional[int] = None
        best_conf = 0.0

        for step in analogy_result.chain:
            if step.step_type != 'conclusion' or not step.node_id:
                continue

            analogy_sim = step.confidence
            target_node = self.kg.get_node(step.node_id)
            if not target_node:
                continue

            for src_conc in source_conclusions[:3]:
                hyp_conf = analogy_sim * src_conc['confidence'] * 0.7
                hyp_conf = self.calibrate_confidence(hyp_conf)

                hypothesis = {
                    'type': 'analogical_hypothesis',
                    'source_node': source_node_id,
                    'source_conclusion': src_conc['node_id'],
                    'target_node': step.node_id,
                    'analogy_similarity': round(analogy_sim, 4),
                    'hypothesis': (
                        f"By analogy with node {source_node_id} "
                        f"(similarity {analogy_sim:.2f}), "
                        f"the same conclusion pattern may hold for "
                        f"node {step.node_id} in {target_domain}"
                    ),
                    'confidence': round(hyp_conf, 4),
                    'block_height': self._current_block_height,
                }
                hypotheses.append(hypothesis)

                if hyp_conf > best_conf:
                    best_conf = hyp_conf
                    # Create hypothesis node in KG
                    hyp_node = self.kg.add_node(
                        node_type='inference',
                        content=hypothesis,
                        confidence=hyp_conf,
                        source_block=self._current_block_height,
                    )
                    if hyp_node:
                        conclusion_id = hyp_node.node_id
                        self.kg.add_edge(source_node_id, hyp_node.node_id, 'derives')
                        self.kg.add_edge(step.node_id, hyp_node.node_id, 'analogous_to')
                        chain.append(ReasoningStep(
                            step_type='conclusion',
                            node_id=hyp_node.node_id,
                            content=hypothesis,
                            confidence=hyp_conf,
                        ))

        source_domain = source.domain or 'general'
        self._track_domain_success(source_domain, len(hypotheses) > 0)

        result = ReasoningResult(
            operation_type='analogical',
            premise_ids=[source_node_id],
            conclusion_node_id=conclusion_id,
            confidence=best_conf,
            chain=chain,
            success=len(hypotheses) > 0,
            explanation=(
                f"Analogical reasoning from node {source_node_id} to {target_domain}: "
                f"found {len(hypotheses)} hypotheses from "
                f"{len(source_conclusions)} source conclusions"
            ),
            domain=source_domain,
            block_height=self._current_block_height,
            hypotheses=hypotheses,
        )

        self._set_cached(cache_key, result)
        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def generate_counter_arguments(self, conclusion_node_id: int) -> Optional[dict]:
        """Generate counter-arguments for a conclusion using the debate engine.

        Args:
            conclusion_node_id: Node ID of the conclusion to challenge.

        Returns:
            Dict with debate result and counter-arguments, or None.
        """
        if not self._debate_engine:
            return None

        try:
            debate_result = self._debate_engine.debate(
                [conclusion_node_id], max_rounds=2
            )
            return {
                'verdict': debate_result.verdict,
                'critic_confidence': debate_result.critic_final_confidence,
                'proposer_confidence': debate_result.proposer_final_confidence,
                'counter_arguments': [
                    {'argument': p.argument, 'confidence': p.confidence}
                    for p in debate_result.positions if p.role == 'critic'
                ],
            }
        except Exception as e:
            logger.debug(f"Counter-argument generation failed: {e}")
            return None

    def generate_hypotheses(self, observation_id: int,
                            max_hypotheses: int = 3) -> List[dict]:
        """Generate multiple hypotheses to explain an observation.

        Goes beyond basic abduction by generating diverse hypotheses:
        1. Direct causal hypothesis (what could have caused this?)
        2. Structural analogy hypothesis (what similar patterns exist?)
        3. Temporal hypothesis (what changed around this block height?)

        Args:
            observation_id: Node ID of the observation to explain.
            max_hypotheses: Maximum number of hypotheses to generate.

        Returns:
            List of hypothesis dicts with confidence scores.
        """
        observation = self.kg.get_node(observation_id)
        if not observation:
            return []

        hypotheses: List[dict] = []

        # 1. Direct causal hypothesis via abduction
        abd_result = self.abduce(observation_id)
        if abd_result.success and abd_result.conclusion_node_id:
            conc = self.kg.get_node(abd_result.conclusion_node_id)
            hypotheses.append({
                'type': 'causal',
                'node_id': abd_result.conclusion_node_id,
                'explanation': abd_result.explanation,
                'confidence': abd_result.confidence,
                'content': conc.content if conc else {},
            })

        # 2. Structural analogy: find similar observations and their explanations
        if hasattr(self.kg, 'nodes'):
            obs_domain = observation.domain or 'general'
            if hasattr(self.kg, 'get_nodes_by_domain') and obs_domain:
                similar_obs = [
                    n for n in self.kg.get_nodes_by_domain(obs_domain, limit=100)
                    if n.node_id != observation_id
                    and n.node_type == 'observation'
                    and n.confidence > 0.5
                ]
            else:
                similar_obs = [
                    n for n in self.kg.nodes.values()
                    if n.node_id != observation_id
                    and n.node_type == 'observation'
                    and n.domain == obs_domain
                    and n.confidence > 0.5
                ]
            # Find observations that already have explanations
            for sim_obs in similar_obs[:10]:
                explanations = self.kg.get_neighbors(sim_obs.node_id, 'in')
                for expl_node in explanations:
                    if expl_node.node_type == 'inference' and expl_node.confidence > 0.3:
                        hyp_conf = expl_node.confidence * 0.5  # Discount for analogy
                        hypotheses.append({
                            'type': 'analogical',
                            'node_id': expl_node.node_id,
                            'explanation': (
                                f"Similar observation (node {sim_obs.node_id}) was explained by "
                                f"inference node {expl_node.node_id}"
                            ),
                            'confidence': hyp_conf,
                            'source_observation': sim_obs.node_id,
                        })
                        if len(hypotheses) >= max_hypotheses:
                            break
                if len(hypotheses) >= max_hypotheses:
                    break

        # 3. Temporal hypothesis: what else happened near this block?
        # Bounded scan: only check last 2000 nodes to avoid O(N) on 100K+ graph
        if observation.source_block > 0:
            block_window = 10
            try:
                recent_nodes = list(self.kg.nodes.values())[-2000:]
            except RuntimeError:
                recent_nodes = []
            nearby_events = [
                n for n in recent_nodes
                if n.node_id != observation_id
                and abs(n.source_block - observation.source_block) <= block_window
                and n.node_type in ('observation', 'assertion')
                and n.confidence > 0.5
            ]
            if nearby_events and len(hypotheses) < max_hypotheses:
                temporal_conf = 0.3 * min(1.0, len(nearby_events) / 5.0)
                hypotheses.append({
                    'type': 'temporal',
                    'explanation': (
                        f"{len(nearby_events)} events occurred within "
                        f"{block_window} blocks of this observation "
                        f"(blocks {observation.source_block - block_window}-"
                        f"{observation.source_block + block_window})"
                    ),
                    'confidence': temporal_conf,
                    'nearby_event_count': len(nearby_events),
                    'nearby_node_ids': [n.node_id for n in nearby_events[:5]],
                })

        return hypotheses[:max_hypotheses]

    def multi_step_chain(self, query_node_ids: List[int],
                         max_depth: int = 5) -> ReasoningResult:
        """Multi-step chain-of-thought that explicitly chains deduction -> induction -> abduction.

        Unlike basic chain_of_thought which tries operations opportunistically,
        this method follows a structured pipeline:
        1. Deduction: derive certain conclusions from premises
        2. Induction: generalize patterns from the deduced conclusions + observations
        3. Abduction: generate hypotheses for any unexplained observations

        Each phase feeds results into the next, building a coherent reasoning chain.

        Args:
            query_node_ids: Starting node IDs.
            max_depth: Maximum reasoning depth per phase.

        Returns:
            ReasoningResult with the full multi-step chain.
        """
        # Check cache
        cache_key = self._cache_key('multi_step', query_node_ids)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        chain: List[ReasoningStep] = []
        all_conclusion_ids: List[int] = []
        overall_confidence = 1.0
        visited: set = set()

        # Load starting premises
        premises = []
        for nid in query_node_ids:
            node = self.kg.get_node(nid)
            if node:
                premises.append(node)
                visited.add(nid)
                chain.append(ReasoningStep(
                    step_type='premise', node_id=nid,
                    content=node.content, confidence=node.confidence,
                ))

        if not premises:
            return ReasoningResult(
                operation_type='multi_step_chain',
                premise_ids=query_node_ids,
                success=False,
                explanation='No valid starting nodes found',
            )

        # Phase 1: DEDUCTION - derive conclusions from premise pairs
        deduced_ids: List[int] = []
        premise_pairs = []
        p_ids = [p.node_id for p in premises]
        for i in range(len(p_ids)):
            for j in range(i + 1, min(len(p_ids), i + 4)):
                premise_pairs.append([p_ids[i], p_ids[j]])

        for pair in premise_pairs[:max_depth]:
            deduction = self.deduce(pair)
            if deduction.success and deduction.conclusion_node_id:
                deduced_ids.append(deduction.conclusion_node_id)
                overall_confidence = min(overall_confidence, max(deduction.confidence, 0.1))
                chain.append(ReasoningStep(
                    step_type='conclusion',
                    node_id=deduction.conclusion_node_id,
                    content={'type': 'deductive_phase', 'source_pair': pair},
                    confidence=deduction.confidence,
                ))

        # Phase 2: INDUCTION - generalize from deduced + observed nodes
        induction_candidates = deduced_ids + [
            nid for nid in query_node_ids if nid not in visited
        ]
        if len(induction_candidates) >= 2:
            induction = self.induce(induction_candidates[:8])
            if induction.success and induction.conclusion_node_id:
                all_conclusion_ids.append(induction.conclusion_node_id)
                overall_confidence = min(overall_confidence, max(induction.confidence, 0.1))
                chain.append(ReasoningStep(
                    step_type='conclusion',
                    node_id=induction.conclusion_node_id,
                    content={'type': 'inductive_phase'},
                    confidence=induction.confidence,
                ))

        # Phase 3: ABDUCTION - explain unexplained observations
        unexplained = [
            nid for nid in query_node_ids
            if self.kg.get_node(nid)
            and not self.kg.get_node(nid).edges_in
            and nid not in visited
        ]
        for obs_id in unexplained[:max_depth]:
            abduction = self.abduce(obs_id)
            if abduction.success and abduction.conclusion_node_id:
                all_conclusion_ids.append(abduction.conclusion_node_id)
                chain.append(ReasoningStep(
                    step_type='conclusion',
                    node_id=abduction.conclusion_node_id,
                    content={'type': 'abductive_phase'},
                    confidence=abduction.confidence,
                ))

        # Calibrate final confidence
        final_confidence = self.calibrate_confidence(
            max(0.0, min(1.0, overall_confidence))
        )

        conclusion_id = all_conclusion_ids[-1] if all_conclusion_ids else None

        # Determine domain from premises
        domains = [p.domain for p in premises if p.domain]
        domain = max(set(domains), key=domains.count) if domains else 'general'

        result = ReasoningResult(
            operation_type='multi_step_chain',
            premise_ids=query_node_ids,
            conclusion_node_id=conclusion_id,
            confidence=final_confidence,
            chain=chain,
            success=len(chain) > len(query_node_ids),
            explanation=(
                f"Multi-step reasoning: {len(deduced_ids)} deductions, "
                f"{len(all_conclusion_ids)} conclusions, "
                f"{len(unexplained)} abductions. "
                f"Chain: {len(chain)} steps."
            ),
            domain=domain,
            block_height=self._current_block_height,
        )

        self._track_domain_success(domain, result.success)
        self._set_cached(cache_key, result)
        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

    def explain_reasoning(self, result: ReasoningResult) -> str:
        """Generate a natural language explanation of a reasoning chain.

        Produces a human-readable narrative describing:
        - What premises were used
        - What reasoning steps were taken
        - What conclusion was reached and why
        - How confident the system is and why

        Args:
            result: A ReasoningResult to explain.

        Returns:
            Natural language explanation string.
        """
        if not result.chain:
            return f"No reasoning chain available. Operation: {result.operation_type}, success: {result.success}"

        parts: List[str] = []

        # Opening
        op_names = {
            'deductive': 'deductive reasoning (deriving conclusions from premises)',
            'inductive': 'inductive reasoning (generalizing from observations)',
            'abductive': 'abductive reasoning (inferring best explanations)',
            'chain_of_thought': 'chain-of-thought reasoning (multi-step exploration)',
            'multi_step_chain': 'multi-step chained reasoning (deduction + induction + abduction)',
            'analogical': 'analogical reasoning (finding structural parallels)',
            'reason_chain': 'backtracking chain reasoning (with contradiction detection)',
            'analogy_detection': 'analogy detection (cross-domain pattern matching)',
            'contradiction_resolution': 'contradiction resolution',
        }
        op_desc = op_names.get(result.operation_type, result.operation_type)
        parts.append(f"Using {op_desc}:")

        # Premises
        premises = [s for s in result.chain if s.step_type == 'premise']
        if premises:
            parts.append(f"\nStarting from {len(premises)} premise(s):")
            for i, p in enumerate(premises[:5], 1):
                text = str(p.content.get('text', p.content.get('type', 'unknown')))[:120]
                parts.append(f"  {i}. [{p.node_id}] {text} (confidence: {p.confidence:.2f})")

        # Observations
        observations = [s for s in result.chain if s.step_type == 'observation']
        if observations:
            parts.append(f"\nExamined {len(observations)} observation(s) along the way.")

        # Rules applied
        rules = [s for s in result.chain if s.step_type == 'rule']
        if rules:
            for r in rules[:3]:
                op = r.content.get('operation', 'inference')
                parts.append(f"\nApplied rule: {op}")

        # Conclusions
        conclusions = [s for s in result.chain if s.step_type == 'conclusion']
        if conclusions:
            parts.append(f"\nReached {len(conclusions)} conclusion(s):")
            for c in conclusions[:3]:
                text = str(c.content.get('text', c.content.get('type', 'derived')))[:120]
                parts.append(f"  -> [{c.node_id}] {text} (confidence: {c.confidence:.2f})")

        # Confidence assessment
        conf = result.confidence
        if conf >= 0.8:
            conf_desc = "high confidence"
        elif conf >= 0.5:
            conf_desc = "moderate confidence"
        elif conf >= 0.2:
            conf_desc = "low confidence"
        else:
            conf_desc = "very low confidence"
        parts.append(f"\nOverall confidence: {conf:.4f} ({conf_desc})")

        # Block height context
        if result.block_height > 0:
            parts.append(f"Reasoning performed at block height {result.block_height}.")

        # Success/failure
        if result.success:
            parts.append("\nReasoning completed successfully.")
        else:
            parts.append(f"\nReasoning did not reach a strong conclusion: {result.explanation}")

        return '\n'.join(parts)

    # ─── Bayesian Confidence Updates (Item #30) ───────────────────────────
    def bayesian_update(self, node_id: int, evidence_positive: bool,
                        likelihood_ratio: float = 2.0) -> float:
        """Apply Bayes rule to update a node's confidence given new evidence.

        P(H|E) = P(E|H) * P(H) / P(E)
        Using likelihood ratio form:
          If evidence_positive: posterior = prior * LR / (prior * LR + (1-prior))
          If evidence_negative: posterior = prior / (prior + (1-prior) * LR)

        Args:
            node_id: Node to update.
            evidence_positive: Whether the evidence supports the hypothesis.
            likelihood_ratio: How much more likely the evidence is if hypothesis
                is true vs false. Default 2.0 (mild evidence).

        Returns:
            New confidence value, or -1.0 if node not found.
        """
        node = self.kg.get_node(node_id) if self.kg else None
        if not node:
            return -1.0

        prior = node.confidence
        lr = max(likelihood_ratio, 1.01)  # Prevent degenerate ratios

        if evidence_positive:
            posterior = (prior * lr) / (prior * lr + (1.0 - prior))
        else:
            posterior = prior / (prior + (1.0 - prior) * lr)

        # Clamp to [0.01, 0.99] to prevent certainty lock
        posterior = max(0.01, min(0.99, posterior))
        node.confidence = posterior
        return posterior

    def bayesian_update_from_reasoning(self, result: 'ReasoningResult') -> None:
        """Update premise confidences based on reasoning outcome.

        If reasoning succeeded with high confidence, strengthen premises.
        If it failed or had low confidence, weaken premises proportionally.
        """
        if not result or not self.kg:
            return

        for pid in result.premise_ids:
            if result.success and result.confidence > 0.6:
                # Evidence supports these premises
                lr = 1.0 + result.confidence  # 1.6 - 2.0 range
                self.bayesian_update(pid, evidence_positive=True, likelihood_ratio=lr)
            elif not result.success:
                # Mild negative evidence
                self.bayesian_update(pid, evidence_positive=False, likelihood_ratio=1.3)

    # ─── Online Edge Weight Learning (Item #31) ──────────────────────────
    def update_edge_weight_online(self, from_id: int, to_id: int,
                                  used_successfully: bool,
                                  learning_rate: float = 0.05) -> float:
        """Update edge weight based on whether it was useful in reasoning.

        Edges that participate in successful reasoning get reinforced.
        Edges in failed reasoning get weakened. This is a simple online
        learning rule: w_new = w_old + lr * (reward - baseline).

        Args:
            from_id: Source node ID.
            to_id: Target node ID.
            used_successfully: Whether the edge contributed to correct reasoning.
            learning_rate: Step size for weight update.

        Returns:
            New edge weight, or -1.0 if edge not found.
        """
        if not self.kg:
            return -1.0

        edges = self.kg.get_edges_from(from_id)
        for edge in edges:
            if edge.to_node_id == to_id:
                reward = 1.0 if used_successfully else -0.5
                delta = learning_rate * reward
                edge.weight = max(0.1, min(5.0, edge.weight + delta))
                return edge.weight

        return -1.0

    def reinforce_reasoning_edges(self, result: 'ReasoningResult') -> int:
        """Reinforce all edges used in a reasoning chain based on outcome.

        Returns number of edges updated.
        """
        if not result or not self.kg:
            return 0

        updated = 0
        # Reinforce edges between consecutive chain steps
        prev_node_id = None
        for step in result.chain:
            if step.node_id is not None:
                if prev_node_id is not None:
                    w = self.update_edge_weight_online(
                        prev_node_id, step.node_id,
                        used_successfully=result.success
                    )
                    if w >= 0:
                        updated += 1
                prev_node_id = step.node_id

        # Also reinforce edges between premise nodes
        for i, pid1 in enumerate(result.premise_ids):
            for pid2 in result.premise_ids[i+1:]:
                self.update_edge_weight_online(pid1, pid2, result.success, 0.02)
                self.update_edge_weight_online(pid2, pid1, result.success, 0.02)
                updated += 2

        return updated
