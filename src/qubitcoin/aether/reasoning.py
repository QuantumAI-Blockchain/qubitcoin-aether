"""
Reasoning Engine - Logical Inference for Aether Tree
Supports deductive, inductive, and abductive reasoning over the knowledge graph.
Generates new KeterNodes from existing knowledge through logical inference.
"""
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional

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

    def to_dict(self) -> dict:
        return {
            'operation_type': self.operation_type,
            'premise_ids': self.premise_ids,
            'conclusion_node_id': self.conclusion_node_id,
            'confidence': self.confidence,
            'chain': [s.to_dict() for s in self.chain],
            'success': self.success,
            'explanation': self.explanation,
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

        If premise A supports premise B, and B supports C,
        then we can derive a path-based conclusion with compounded confidence.
        """
        chain = []
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

        # Find common conclusions: nodes reachable from all premises
        reachable_sets = []
        for premise in premises:
            neighbors = self.kg.get_neighbors(premise.node_id, 'out')
            reachable = {n.node_id for n in neighbors}
            # Extend to depth 2
            for n in neighbors:
                for nn in self.kg.get_neighbors(n.node_id, 'out'):
                    reachable.add(nn.node_id)
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
            combined = {
                'type': 'deduction',
                'from_premises': [p.content for p in premises],
                'rule': rule_content or {'operation': 'conjunction'},
            }
            # Confidence: product of premise confidences (certainty preserving)
            conf = 1.0
            for p in premises:
                conf *= p.confidence
            # Boost confidence when premises are grounded in external truth
            conf *= self._grounding_boost(premise_ids)
            conf = min(1.0, conf)

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
                explanation=f"Deduced new conclusion from {len(premises)} premises",
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

            result = ReasoningResult(
                operation_type='deductive',
                premise_ids=premise_ids,
                conclusion_node_id=best_id,
                confidence=conf,
                chain=chain,
                success=True,
                explanation=f"Found existing conclusion node {best_id}",
            )

        # Protect axiom confidence floor (Improvement 35)
        for pid in premise_ids:
            node = self.kg.get_node(pid)
            if node and node.node_type == 'axiom' and node.confidence < 0.8:
                node.confidence = 0.8

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
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
        if hasattr(self.kg, 'nodes'):
            for nid, node in self.kg.nodes.items():
                if nid == conclusion_id:
                    continue
                if node.confidence <= 0.7:
                    continue

                # Same domain check
                node_domain = node.content.get('type', '')
                if not node_domain:
                    node_domain = node.node_type
                if node_domain != conclusion_domain:
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

        # Find common node types among observations
        type_counts: Dict[str, int] = {}
        for obs in observations:
            nt = obs.node_type
            type_counts[nt] = type_counts.get(nt, 0) + 1

        dominant_type = max(type_counts, key=type_counts.get)

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

        generalization = {
            'type': 'generalization',
            'pattern': f"Pattern from {n} obs: {', '.join(pattern_parts)}",
            'observation_count': n,
            'dominant_type': dominant_type,
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
            explanation=f"Induced generalization from {n} observations (conf: {inductive_conf:.4f})",
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
                        'bh': 0,
                    }
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Failed to store reasoning operation: {e}")

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

        for depth in range(max_depth):
            # Stop if confidence drops below floor (prevents meaningless chains)
            if overall_confidence < confidence_floor:
                logger.debug(
                    f"Chain-of-thought stopped at depth {depth}: "
                    f"confidence {overall_confidence:.4f} < floor {confidence_floor}"
                )
                break

            next_frontier: List[int] = []

            # Explore neighbors of current frontier
            context_nodes: List[int] = []
            for nid in frontier:
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

            # Try deductive step if we have enough context
            if len(context_nodes) >= 2:
                deduction = self.deduce(context_nodes)
                if deduction.success and deduction.conclusion_node_id:
                    chain.append(ReasoningStep(
                        step_type='conclusion',
                        node_id=deduction.conclusion_node_id,
                        content={'type': 'deductive_step', 'depth': depth},
                        confidence=deduction.confidence,
                    ))
                    overall_confidence *= deduction.confidence
                    conclusion_id = deduction.conclusion_node_id
                    next_frontier.append(deduction.conclusion_node_id)

            # Try abductive step for unexplained observations (Improvement 40)
            unexplained = [
                nid for nid in context_nodes
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
            if len(context_nodes) >= 3:
                induction = self.induce(context_nodes)
                if induction.success and induction.conclusion_node_id:
                    chain.append(ReasoningStep(
                        step_type='conclusion',
                        node_id=induction.conclusion_node_id,
                        content={'type': 'inductive_step', 'depth': depth},
                        confidence=induction.confidence,
                    ))
                    next_frontier.append(induction.conclusion_node_id)

            # Expand frontier for next iteration
            for nid in frontier:
                node = self.kg.get_node(nid)
                if node:
                    for neighbor_id in node.edges_out:
                        if neighbor_id not in visited:
                            next_frontier.append(neighbor_id)

            frontier = next_frontier
            if not frontier:
                break  # No more nodes to explore

        # If no conclusion found via deduction, try abduction (Improvement 40)
        if conclusion_id is None and frontier:
            abd_result = self.abduce(frontier[0])
            if abd_result.success:
                chain.extend(abd_result.chain)
                conclusion_id = abd_result.conclusion_node_id
                overall_confidence *= abd_result.confidence

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

        # Find candidates in other domains
        source_domain = source.domain or ''
        candidates = [
            n for n in self.kg.nodes.values()
            if n.node_id != source_node_id
            and (n.domain != source_domain or not source_domain)
            and (not target_domain or n.domain == target_domain)
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

            if similarity >= 0.5 and common >= 2:
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
                                (operation_type, confidence, block_height, premises, conclusion, is_summary)
                                VALUES (:otype, :conf, :block,
                                        CAST(:premises AS jsonb), CAST(:conclusion AS jsonb), true)
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
                                'conclusion': json.dumps({
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
                          AND (is_summary IS NULL OR is_summary = false)
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
                     max_backtrack: int = 3) -> ReasoningResult:
        """Chain-of-thought reasoning with contradiction-driven backtracking.

        Builds a reasoning chain step-by-step from the query nodes.  At each
        depth level the method:

        1. Gathers context nodes from the current frontier.
        2. Selects the best reasoning operation for the context:
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
            if obs_count >= 2:
                op_order = ['inductive', 'deductive', 'abductive']
            elif inf_count >= 2:
                op_order = ['deductive', 'inductive', 'abductive']
            else:
                op_order = ['abductive', 'inductive', 'deductive']

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

            overall_confidence *= max(result.confidence, 0.01)
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

        nodes_a = [n for n in self.kg.nodes.values() if n.domain == domain_a]
        nodes_b = [n for n in self.kg.nodes.values() if n.domain == domain_b]

        if not nodes_a or not nodes_b:
            return []

        analogies: List[dict] = []

        for node_a in nodes_a[:50]:  # cap to prevent O(n^2) explosion
            pattern_a = self._get_edge_pattern(node_a.node_id)
            if not pattern_a:
                continue

            for node_b in nodes_b[:50]:
                pattern_b = self._get_edge_pattern(node_b.node_id)
                if not pattern_b:
                    continue

                # Jaccard similarity of edge patterns
                common = len(pattern_a & pattern_b)
                total = len(pattern_a | pattern_b)
                if total == 0:
                    continue
                similarity = common / total

                if similarity >= 0.4 and common >= 1:
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
