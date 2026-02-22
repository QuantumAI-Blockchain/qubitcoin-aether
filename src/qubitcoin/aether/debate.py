"""
Inter-Sephirot Adversarial Debate Protocol — Structured Cognitive Conflict

Implements a multi-round debate between Chesed (expansion/exploration) and
Gevurah (constraint/safety), with Tiferet as arbiter/integrator.

This is Improvement #5: raw reasoning can be biased.  Structured adversarial
debate forces the system to consider both sides of every inference, producing
more robust and balanced conclusions.
"""
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DebatePosition:
    """A single position (argument) in a debate round."""
    role: str  # 'proposer' (Chesed) or 'critic' (Gevurah)
    argument: str
    confidence: float
    evidence_node_ids: List[int] = field(default_factory=list)
    round_num: int = 0


@dataclass
class DebateResult:
    """Outcome of a completed debate."""
    topic: str
    rounds: int
    proposer_final_confidence: float
    critic_final_confidence: float
    verdict: str  # 'accepted', 'rejected', 'modified'
    synthesis: dict = field(default_factory=dict)
    positions: List[DebatePosition] = field(default_factory=list)
    conclusion_node_id: Optional[int] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'topic': self.topic,
            'rounds': self.rounds,
            'proposer_final_confidence': round(self.proposer_final_confidence, 4),
            'critic_final_confidence': round(self.critic_final_confidence, 4),
            'verdict': self.verdict,
            'synthesis': self.synthesis,
            'positions': [
                {'role': p.role, 'argument': p.argument,
                 'confidence': round(p.confidence, 4), 'round': p.round_num}
                for p in self.positions
            ],
            'conclusion_node_id': self.conclusion_node_id,
        }


class DebateProtocol:
    """
    Structured adversarial debate between Sephirot nodes.

    Protocol:
    1. Chesed proposes a hypothesis with supporting evidence
    2. Gevurah critiques — finds contradicting evidence or safety concerns
    3. Chesed refines based on critique
    4. Repeat for max_rounds or until convergence
    5. Tiferet synthesizes a final verdict

    The debate creates 'inference' nodes in the knowledge graph with the
    final synthesis, improving the quality of automated reasoning.
    """

    def __init__(self, knowledge_graph=None) -> None:
        self.kg = knowledge_graph
        self._debates_run: int = 0
        self._accepted: int = 0
        self._rejected: int = 0
        self._modified: int = 0

    def debate(self, topic_node_ids: List[int],
               max_rounds: int = 3,
               convergence_threshold: float = 0.1) -> DebateResult:
        """
        Run a structured debate about the given topic nodes.

        Args:
            topic_node_ids: Knowledge nodes that define the debate topic.
            max_rounds: Maximum debate rounds before forced verdict.
            convergence_threshold: Stop if confidence delta < threshold.

        Returns:
            DebateResult with verdict, synthesis, and confidence scores.
        """
        if not self.kg or not topic_node_ids:
            return DebateResult(
                topic='empty', rounds=0,
                proposer_final_confidence=0.0,
                critic_final_confidence=0.0,
                verdict='rejected',
            )

        self._debates_run += 1

        # Gather topic context
        topic_nodes = [self.kg.nodes.get(nid) for nid in topic_node_ids]
        topic_nodes = [n for n in topic_nodes if n is not None]
        if not topic_nodes:
            return DebateResult(
                topic='missing', rounds=0,
                proposer_final_confidence=0.0,
                critic_final_confidence=0.0,
                verdict='rejected',
            )

        topic_text = '; '.join(
            str(n.content.get('text', n.content.get('type', '')))[:100]
            for n in topic_nodes
        )

        # Initial proposer confidence = average of topic node confidences
        proposer_conf = sum(n.confidence for n in topic_nodes) / len(topic_nodes)
        critic_conf = 1.0 - proposer_conf  # Start as adversary

        positions: List[DebatePosition] = []

        for round_num in range(max_rounds):
            # --- Chesed proposes ---
            support_evidence = self._find_supporting_evidence(topic_node_ids)
            proposer_strength = self._compute_evidence_strength(support_evidence)
            proposer_conf = min(1.0, proposer_conf * 0.7 + proposer_strength * 0.3)

            positions.append(DebatePosition(
                role='proposer',
                argument=f"Round {round_num + 1}: {len(support_evidence)} supporting nodes "
                         f"(strength {proposer_strength:.3f})",
                confidence=proposer_conf,
                evidence_node_ids=support_evidence[:5],
                round_num=round_num,
            ))

            # --- Gevurah critiques ---
            counter_evidence = self._find_counter_evidence(topic_node_ids)
            critic_strength = self._compute_evidence_strength(counter_evidence)
            # Safety check: look for nodes that flag risks
            safety_concerns = self._check_safety_concerns(topic_node_ids)
            if safety_concerns:
                critic_strength = min(1.0, critic_strength + 0.2)

            critic_conf = min(1.0, critic_conf * 0.6 + critic_strength * 0.4)

            positions.append(DebatePosition(
                role='critic',
                argument=f"Round {round_num + 1}: {len(counter_evidence)} counter-nodes, "
                         f"{len(safety_concerns)} safety concerns "
                         f"(strength {critic_strength:.3f})",
                confidence=critic_conf,
                evidence_node_ids=counter_evidence[:5],
                round_num=round_num,
            ))

            # Check convergence
            delta = abs(proposer_conf - critic_conf)
            if delta < convergence_threshold:
                break

        # --- Tiferet synthesizes verdict ---
        if proposer_conf > critic_conf + 0.15:
            verdict = 'accepted'
            self._accepted += 1
            synthesis_conf = proposer_conf * 0.8 + (1.0 - critic_conf) * 0.2
        elif critic_conf > proposer_conf + 0.15:
            verdict = 'rejected'
            self._rejected += 1
            synthesis_conf = (1.0 - proposer_conf) * 0.5
        else:
            verdict = 'modified'
            self._modified += 1
            synthesis_conf = (proposer_conf + (1.0 - critic_conf)) / 2.0

        synthesis = {
            'type': 'debate_synthesis',
            'topic': topic_text[:200],
            'verdict': verdict,
            'proposer_final': round(proposer_conf, 4),
            'critic_final': round(critic_conf, 4),
            'rounds': round_num + 1,
            'source': 'debate_protocol',
        }

        # Create conclusion node in knowledge graph
        conclusion_id = None
        if self.kg and verdict != 'rejected':
            block = max((n.source_block for n in topic_nodes), default=0)
            conclusion = self.kg.add_node(
                node_type='inference',
                content=synthesis,
                confidence=synthesis_conf,
                source_block=block,
            )
            if conclusion:
                conclusion_id = conclusion.node_id
                for nid in topic_node_ids:
                    self.kg.add_edge(nid, conclusion.node_id, 'derives')

        result = DebateResult(
            topic=topic_text[:200],
            rounds=round_num + 1,
            proposer_final_confidence=proposer_conf,
            critic_final_confidence=critic_conf,
            verdict=verdict,
            synthesis=synthesis,
            positions=positions,
            conclusion_node_id=conclusion_id,
        )

        if conclusion_id:
            logger.info(
                f"Debate '{topic_text[:50]}...': {verdict} "
                f"(prop={proposer_conf:.3f}, crit={critic_conf:.3f}, "
                f"rounds={round_num + 1})"
            )

        return result

    def _find_supporting_evidence(self, topic_node_ids: List[int]) -> List[int]:
        """Find nodes that support the topic nodes."""
        supporters = []
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if not node:
                continue
            for edge in self.kg.edges:
                if edge.to_node_id == nid and edge.edge_type in ('supports', 'derives'):
                    if edge.from_node_id in self.kg.nodes:
                        supporters.append(edge.from_node_id)
                if edge.from_node_id == nid and edge.edge_type == 'supports':
                    if edge.to_node_id in self.kg.nodes:
                        supporters.append(edge.to_node_id)
        return list(set(supporters))

    def _find_counter_evidence(self, topic_node_ids: List[int]) -> List[int]:
        """Find nodes that contradict or weaken the topic nodes."""
        counter = []
        topic_set = set(topic_node_ids)
        for edge in self.kg.edges:
            if edge.edge_type == 'contradicts':
                if edge.from_node_id in topic_set and edge.to_node_id in self.kg.nodes:
                    counter.append(edge.to_node_id)
                if edge.to_node_id in topic_set and edge.from_node_id in self.kg.nodes:
                    counter.append(edge.from_node_id)
        return list(set(counter))

    def _check_safety_concerns(self, topic_node_ids: List[int]) -> List[int]:
        """Check if any topic nodes have low confidence or safety flags."""
        concerns = []
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if node and node.confidence < 0.3:
                concerns.append(nid)
        return concerns

    def _compute_evidence_strength(self, evidence_node_ids: List[int]) -> float:
        """Compute aggregate evidence strength from a set of nodes."""
        if not evidence_node_ids:
            return 0.0
        total_conf = 0.0
        count = 0
        for nid in evidence_node_ids:
            node = self.kg.nodes.get(nid)
            if node:
                total_conf += node.confidence
                count += 1
        if count == 0:
            return 0.0
        # Strength scales with both average confidence and evidence count
        avg_conf = total_conf / count
        # More evidence = stronger (asymptotic)
        count_factor = 1.0 - 1.0 / (count + 1)
        return avg_conf * count_factor

    def run_periodic_debates(self, block_height: int,
                             max_debates: int = 3) -> int:
        """Run debates on recent high-confidence inference nodes.

        Called periodically (e.g., every 100 blocks) to stress-test
        recent conclusions.

        Args:
            block_height: Current block height.
            max_debates: Max debates to run per call.

        Returns:
            Number of debates run.
        """
        if not self.kg:
            return 0

        # Find recent inference nodes with moderate-to-high confidence
        candidates = [
            n for n in self.kg.nodes.values()
            if n.node_type == 'inference'
            and n.confidence >= 0.5
            and n.source_block >= block_height - 500
        ]
        candidates.sort(key=lambda n: n.source_block, reverse=True)

        debates_run = 0
        for node in candidates[:max_debates]:
            self.debate([node.node_id])
            debates_run += 1

        return debates_run

    def get_stats(self) -> dict:
        return {
            'total_debates': self._debates_run,
            'accepted': self._accepted,
            'rejected': self._rejected,
            'modified': self._modified,
            'acceptance_rate': round(
                self._accepted / max(1, self._debates_run), 4
            ),
        }
