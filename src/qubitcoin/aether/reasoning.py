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

        self._store_operation(result)
        self._operations.append(result)
        if len(self._operations) > self._max_operations:
            self._operations = self._operations[-self._max_operations:]
        return result

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

        # Create generalization node
        generalization = {
            'type': 'generalization',
            'pattern': f"Generalized from {n} {dominant_type} observations",
            'observation_count': n,
            'dominant_type': dominant_type,
        }

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

        if not explanations:
            # No existing explanations — generate hypothesis
            hypothesis = {
                'type': 'hypothesis',
                'explains': observation.content,
                'method': 'abductive_inference',
            }
            hyp_node = self.kg.add_node(
                node_type='inference',
                content=hypothesis,
                confidence=0.3,  # Low confidence for hypotheses
                source_block=observation.source_block,
            )
            self.kg.add_edge(hyp_node.node_id, observation_id, 'derives')

            chain.append(ReasoningStep(
                step_type='conclusion',
                node_id=hyp_node.node_id,
                content=hypothesis,
                confidence=0.3,
            ))

            result = ReasoningResult(
                operation_type='abductive',
                premise_ids=[observation_id],
                conclusion_node_id=hyp_node.node_id,
                confidence=0.3,
                chain=chain,
                success=True,
                explanation='Generated hypothesis to explain observation',
            )
        else:
            # Rank explanations by confidence
            best = max(explanations, key=lambda n: n.confidence)
            chain.append(ReasoningStep(
                step_type='conclusion',
                node_id=best.node_id,
                content=best.content,
                confidence=best.confidence * observation.confidence,
            ))

            result = ReasoningResult(
                operation_type='abductive',
                premise_ids=[observation_id],
                conclusion_node_id=best.node_id,
                confidence=best.confidence * observation.confidence,
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
        for depth in range(max_depth):
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

            # Try abductive step for unexplained observations
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
