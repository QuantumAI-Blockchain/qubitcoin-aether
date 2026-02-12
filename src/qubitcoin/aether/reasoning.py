"""
Reasoning Engine - Logical Inference for Aether Tree
Supports deductive, inductive, and abductive reasoning over the knowledge graph.
Generates new KeterNodes from existing knowledge through logical inference.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

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
