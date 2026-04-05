"""
Inter-Sephirot Adversarial Debate Protocol — Structured Cognitive Conflict

Implements a multi-round debate between Chesed (expansion/exploration) and
Gevurah (constraint/safety), with Tiferet as arbiter/integrator.

This is Improvement #5: raw reasoning can be biased.  Structured adversarial
debate forces the system to consider both sides of every inference, producing
more robust and balanced conclusions.

v2 enhancements:
- Real adversarial counter-evidence search (numeric opposites, low-confidence
  weakeners, temporal contradictions)
- Independent judge scoring based on source diversity, confidence distribution,
  and causal strength
- Post-debate confidence updates on topic nodes
- Adjacency index usage (O(degree) instead of O(|E|))
- Vector index semantic search for supporting evidence

v3 enhancements:
- N-party debate with coalition formation (MultiPartyDebate)
- Parties with similar positions automatically form coalitions
- Coalition strength = sum of member confidences
- Strongest coalition's position wins after all rounds
"""
import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Set, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DebatePosition:
    """A single position (argument) in a debate round."""
    role: str  # 'proposer' (Chesed) or 'critic' (Gevurah)
    argument: str
    confidence: float
    evidence_node_ids: List[int] = field(default_factory=list)
    evidence_quality: float = 0.0
    round_num: int = 0


@dataclass
class Coalition:
    """A group of debate parties with similar positions."""
    members: List[str]
    position: str
    strength: float


@dataclass
class MultiPartyDebateResult:
    """Outcome of a completed multi-party debate."""
    topic: str
    rounds: int
    winner: str
    coalitions: List[Coalition]
    rounds_log: List[Dict[str, Any]]
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            'topic': self.topic,
            'rounds': self.rounds,
            'winner': self.winner,
            'coalitions': [
                {'members': c.members, 'position': c.position,
                 'strength': round(c.strength, 4)}
                for c in self.coalitions
            ],
            'rounds_log': self.rounds_log,
        }


@dataclass
class DebateResult:
    """Outcome of a completed debate."""
    topic: str
    rounds: int
    proposer_final_confidence: float
    critic_final_confidence: float
    verdict: str  # 'accepted', 'rejected', 'modified', 'undecided'
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
                 'confidence': round(p.confidence, 4),
                 'evidence_quality': round(p.evidence_quality, 4),
                 'round': p.round_num}
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
    5. Tiferet synthesizes a final verdict using independent quality metrics

    The debate creates 'inference' nodes in the knowledge graph with the
    final synthesis, improving the quality of automated reasoning.
    """

    # Confidence adjustment constants
    _ACCEPTED_BOOST: float = 0.05
    _REJECTED_PENALTY: float = 0.1
    # Low-confidence threshold for weakening evidence
    _LOW_CONFIDENCE_THRESHOLD: float = 0.35

    def __init__(self, knowledge_graph=None) -> None:
        self.kg = knowledge_graph
        self._debates_run: int = 0
        self._accepted: int = 0
        self._rejected: int = 0
        self._modified: int = 0
        self._undecided: int = 0
        self._debate_log: List[dict] = []

    def debate(self, topic_node_ids: List[int],
               max_rounds: int = 3,
               convergence_threshold: float = 0.1) -> DebateResult:
        """
        Run a structured debate about the given topic nodes.

        Pro agent (Chesed): Uses adjacency-indexed supporting evidence + vector
        index semantic search for similar supporting nodes.
        Con agent (Gevurah): Uses enhanced counter-evidence search (contradicts
        edges, numeric opposites, low-confidence weakeners) + generated
        counterarguments (temporal contradictions, weakened support).
        Judge (Tiferet): Scores each side by evidence quality (source diversity,
        confidence consistency, causal strength) rather than raw confidence.

        After the debate, topic node confidence is updated based on the verdict.

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
        for tid in topic_node_ids:
            self._debate_log.append({'topic_id': tid})

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
        # Critic starts as adversary, but with a minimum of 0.35 to ensure
        # competitive debates even when topic confidence is very high.
        critic_conf = max(0.35, 1.0 - proposer_conf)

        positions: List[DebatePosition] = []
        round_num = 0

        for round_num in range(max_rounds):
            # Add exploration randomness for diverse reasoning (Improvement: debate diversity)
            import random
            exploration_noise = random.uniform(-0.05, 0.05)

            # --- Chesed proposes (with vector-index semantic support) ---
            support_evidence = self._find_supporting_evidence(topic_node_ids)
            # Augment with semantically similar nodes from vector index
            semantic_support = self._find_semantic_support(topic_node_ids, exclude=set(support_evidence))
            all_support = list(set(support_evidence + semantic_support))
            proposer_strength = self._compute_evidence_strength(all_support)
            proposer_quality = self._score_evidence_quality(all_support)
            # Add exploration noise for diverse debate outcomes
            proposer_conf = min(1.0, max(0.0, proposer_conf * 0.7 + proposer_strength * 0.3 + exploration_noise))

            positions.append(DebatePosition(
                role='proposer',
                argument=f"Round {round_num + 1}: {len(all_support)} supporting nodes "
                         f"(strength {proposer_strength:.3f}, quality {proposer_quality:.3f})",
                confidence=proposer_conf,
                evidence_node_ids=all_support[:5],
                evidence_quality=proposer_quality,
                round_num=round_num,
            ))

            # --- Gevurah critiques (independent adversarial search) ---
            counter_evidence = self._find_counter_evidence(topic_node_ids)
            # Cross-domain evidence: look in domains the proposer did NOT use
            cross_domain = self._find_cross_domain_counter(topic_node_ids, set(all_support))
            counter_evidence = list(set(counter_evidence + cross_domain))
            # Generate counterarguments: temporal contradictions, weakened support
            counterarg = self._generate_counterargument(topic_node_ids)
            if counterarg:
                counter_evidence = list(set(
                    counter_evidence + counterarg.evidence_node_ids
                ))
            critic_strength = self._compute_evidence_strength(counter_evidence)
            critic_quality = self._score_evidence_quality(counter_evidence)

            # Safety check: look for nodes that flag risks
            safety_concerns = self._check_safety_concerns(topic_node_ids)
            if safety_concerns:
                critic_strength = min(1.0, critic_strength + 0.2)

            # Counterargument gives an independent strength boost
            if counterarg and counterarg.confidence > 0.0:
                critic_strength = min(1.0, critic_strength + counterarg.confidence * 0.15)

            critic_conf = min(1.0, max(0.0, critic_conf * 0.6 + critic_strength * 0.4 - exploration_noise))

            counterarg_text = f", counterarg: '{counterarg.argument[:60]}'" if counterarg else ""
            positions.append(DebatePosition(
                role='critic',
                argument=f"Round {round_num + 1}: {len(counter_evidence)} counter-nodes, "
                         f"{len(safety_concerns)} safety concerns "
                         f"(strength {critic_strength:.3f}, quality {critic_quality:.3f})"
                         f"{counterarg_text}",
                confidence=critic_conf,
                evidence_node_ids=counter_evidence[:5],
                evidence_quality=critic_quality,
                round_num=round_num,
            ))

            # Check convergence
            delta = abs(proposer_conf - critic_conf)
            if delta < convergence_threshold:
                break

        # --- Tiferet synthesizes verdict (independent quality-based judging) ---
        # Collect all proposer and critic evidence across rounds
        all_pro_evidence: List[int] = []
        all_con_evidence: List[int] = []
        for pos in positions:
            if pos.role == 'proposer':
                all_pro_evidence.extend(pos.evidence_node_ids)
            else:
                all_con_evidence.extend(pos.evidence_node_ids)
        all_pro_evidence = list(set(all_pro_evidence))
        all_con_evidence = list(set(all_con_evidence))

        pro_quality = self._score_evidence_quality(all_pro_evidence)
        con_quality = self._score_evidence_quality(all_con_evidence)

        # Tiferet judges by blending confidence delta with evidence quality
        # Quality-adjusted scores: raw confidence weighted by quality
        pro_adjusted = proposer_conf * (0.5 + 0.5 * pro_quality)
        con_adjusted = critic_conf * (0.5 + 0.5 * con_quality)

        # Compute debate independence: how different are evidence sources?
        independence_score = self._compute_independence_score(
            all_pro_evidence, all_con_evidence
        )

        if abs(proposer_conf - critic_conf) <= 0.05 and abs(pro_adjusted - con_adjusted) <= 0.02:
            # Genuinely balanced evidence — neither side wins
            verdict = 'undecided'
            self._undecided += 1
            synthesis_conf = (proposer_conf + critic_conf) / 2.0
        elif pro_adjusted > con_adjusted + 0.02:
            verdict = 'accepted'
            self._accepted += 1
            synthesis_conf = proposer_conf * 0.8 + (1.0 - critic_conf) * 0.2
        elif con_adjusted > pro_adjusted + 0.02:
            verdict = 'rejected'
            self._rejected += 1
            synthesis_conf = (1.0 - proposer_conf) * 0.5
        else:
            verdict = 'modified'
            self._modified += 1
            # Weighted synthesis: blend proposer and critic insights proportional to quality
            if pro_quality + con_quality > 0:
                pro_weight = pro_quality / (pro_quality + con_quality)
            else:
                pro_weight = 0.5
            synthesis_conf = proposer_conf * pro_weight + (1.0 - critic_conf) * (1.0 - pro_weight)

        # Generate richer synthesis content
        synthesis_text = self._generate_synthesis_text(
            verdict, proposer_conf, critic_conf, pro_quality, con_quality,
            all_pro_evidence, all_con_evidence, topic_text
        )

        synthesis = {
            'type': 'debate_synthesis',
            'topic': topic_text[:200],
            'verdict': verdict,
            'proposer_final': round(proposer_conf, 4),
            'critic_final': round(critic_conf, 4),
            'pro_quality': round(pro_quality, 4),
            'con_quality': round(con_quality, 4),
            'debate_independence_score': round(independence_score, 4),
            'rounds': round_num + 1,
            'source': 'debate_protocol_v3',
            'synthesis_text': synthesis_text,
        }

        # --- Update topic node confidence based on verdict ---
        self._apply_verdict_to_topics(topic_node_ids, verdict, synthesis_conf)

        # Create conclusion node in knowledge graph
        conclusion_id = None
        if self.kg:
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

            # When verdict modifies or rejects, record a contradiction resolution
            if verdict in ('modified', 'rejected'):
                resolution = self.kg.add_node(
                    node_type='inference',
                    content={
                        'type': 'contradiction_resolution',
                        'original_topic': topic_text[:200],
                        'verdict': verdict,
                        'resolution': synthesis_text[:300],
                    },
                    confidence=max(0.3, synthesis_conf),
                    source_block=block,
                )
                if resolution:
                    for nid in topic_node_ids:
                        self.kg.add_edge(nid, resolution.node_id, 'contradicts')

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
                f"proQ={pro_quality:.3f}, conQ={con_quality:.3f}, "
                f"rounds={round_num + 1})"
            )

        return result

    # ------------------------------------------------------------------
    # Evidence gathering (Pro / Chesed)
    # ------------------------------------------------------------------

    def _find_supporting_evidence(self, topic_node_ids: List[int]) -> List[int]:
        """Find nodes that support the topic nodes via adjacency index.

        Uses get_edges_to() and get_edges_from() for O(degree) lookup
        instead of scanning all edges.
        """
        supporters: Set[int] = set()
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if not node:
                continue
            # Incoming edges: nodes that support/derive this topic
            for edge in self.kg.get_edges_to(nid):
                if edge.edge_type in ('supports', 'derives', 'causes'):
                    if edge.from_node_id in self.kg.nodes:
                        supporters.add(edge.from_node_id)
            # Outgoing edges: nodes this topic supports (bidirectional support)
            for edge in self.kg.get_edges_from(nid):
                if edge.edge_type == 'supports':
                    if edge.to_node_id in self.kg.nodes:
                        supporters.add(edge.to_node_id)
        # Exclude the topic nodes themselves
        supporters -= set(topic_node_ids)
        return list(supporters)

    def _find_semantic_support(self, topic_node_ids: List[int],
                               exclude: Optional[Set[int]] = None,
                               top_k: int = 10) -> List[int]:
        """Find semantically similar nodes via vector index that could support the topic.

        Searches for nodes with high semantic similarity to the topic nodes'
        content. Only returns nodes not already in the exclude set and that
        have reasonably high confidence (>0.4).

        Args:
            topic_node_ids: Nodes defining the topic.
            exclude: Node IDs to exclude from results.
            top_k: Maximum results to return.

        Returns:
            List of node IDs of semantically similar supporting nodes.
        """
        if not hasattr(self.kg, 'vector_index'):
            return []

        exclude_set = exclude or set()
        exclude_set |= set(topic_node_ids)

        # Build a query text from topic nodes
        query_parts: List[str] = []
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if node:
                text = str(node.content.get('text', node.content.get('type', '')))
                if text:
                    query_parts.append(text[:200])
        if not query_parts:
            return []

        query_text = ' '.join(query_parts)
        try:
            results = self.kg.vector_index.query(query_text, top_k=top_k * 2)
        except Exception:
            return []

        semantic_ids: List[int] = []
        for nid, score in results:
            if nid in exclude_set:
                continue
            if score < 0.3:
                continue
            node = self.kg.nodes.get(nid)
            if node and node.confidence >= 0.4:
                semantic_ids.append(nid)
            if len(semantic_ids) >= top_k:
                break
        return semantic_ids

    # ------------------------------------------------------------------
    # Counter-evidence gathering (Con / Gevurah)
    # ------------------------------------------------------------------

    def _find_counter_evidence(self, topic_node_ids: List[int]) -> List[int]:
        """Find nodes that contradict or weaken the topic nodes.

        Enhanced to search beyond just 'contradicts' edges:
        1. Direct contradiction edges (via adjacency index)
        2. Nodes with opposite numeric values in the same content field
        3. Low-confidence nodes in the same domain that weaken the proposition

        Args:
            topic_node_ids: Nodes defining the topic.

        Returns:
            List of counter-evidence node IDs.
        """
        counter: Set[int] = set()
        topic_set = set(topic_node_ids)

        # --- 1. Direct contradiction edges (via adjacency index) ---
        for nid in topic_node_ids:
            # Outgoing contradicts from topic
            for edge in self.kg.get_edges_from(nid):
                if edge.edge_type == 'contradicts' and edge.to_node_id in self.kg.nodes:
                    counter.add(edge.to_node_id)
            # Incoming contradicts to topic
            for edge in self.kg.get_edges_to(nid):
                if edge.edge_type == 'contradicts' and edge.from_node_id in self.kg.nodes:
                    counter.add(edge.from_node_id)

        # --- 2. Numeric opposition: find nodes with different numbers for same subject ---
        topic_numbers = self._extract_numeric_profile(topic_node_ids)
        if topic_numbers:
            topic_domains = set()
            topic_words: Set[str] = set()
            for nid in topic_node_ids:
                node = self.kg.nodes.get(nid)
                if node:
                    if node.domain:
                        topic_domains.add(node.domain)
                    text = str(node.content.get('text', '')).lower()
                    topic_words.update(text.split())

            # Search same-domain nodes for numeric conflicts
            checked = 0
            for candidate in self.kg.nodes.values():
                if candidate.node_id in topic_set or candidate.node_id in counter:
                    continue
                if candidate.domain and topic_domains and candidate.domain not in topic_domains:
                    continue
                cand_text = str(candidate.content.get('text', '')).lower()
                if not cand_text:
                    continue
                cand_words = set(cand_text.split())
                # Require some word overlap (same subject)
                overlap = len(topic_words & cand_words)
                total = len(topic_words | cand_words)
                if total == 0 or overlap / total < 0.3:
                    continue
                # Extract numbers and check for conflict
                cand_numbers = set(re.findall(r'\b\d+\.?\d*\b', cand_text))
                if (cand_numbers and topic_numbers
                        and cand_numbers != topic_numbers
                        and len(cand_numbers & topic_numbers) == 0):
                    counter.add(candidate.node_id)
                checked += 1
                if checked >= 30 or len(counter) >= 15:
                    break

        # --- 3. Low-confidence nodes in same domain that weaken the proposition ---
        topic_domains_for_weak: Set[str] = set()
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if node and node.domain:
                topic_domains_for_weak.add(node.domain)

        if topic_domains_for_weak:
            weak_count = 0
            for candidate in self.kg.nodes.values():
                if candidate.node_id in topic_set or candidate.node_id in counter:
                    continue
                if candidate.domain not in topic_domains_for_weak:
                    continue
                if candidate.confidence < self._LOW_CONFIDENCE_THRESHOLD:
                    # Low-confidence node in same domain = potential weakener
                    # Check if it has any edge connection to topic (even indirect)
                    has_connection = False
                    for edge in self.kg.get_edges_from(candidate.node_id):
                        if edge.to_node_id in topic_set:
                            has_connection = True
                            break
                    if not has_connection:
                        for edge in self.kg.get_edges_to(candidate.node_id):
                            if edge.from_node_id in topic_set:
                                has_connection = True
                                break
                    if has_connection:
                        counter.add(candidate.node_id)
                        weak_count += 1
                if weak_count >= 5:
                    break

        counter -= topic_set

        # --- 4. Temporal diversity: alternative perspectives from different epochs ---
        # When no direct counter-evidence found, use nodes from the same domain at
        # very different source_blocks as "epistemic humility" evidence.  The critic's
        # argument: "the system reasoned differently about this domain at other times,
        # so the current inference may not generalise."
        if not counter and topic_node_ids:
            topic_domains_td: Set[str] = set()
            topic_blocks_td: List[int] = []
            for nid in topic_node_ids:
                node = self.kg.nodes.get(nid)
                if node:
                    if node.domain:
                        topic_domains_td.add(node.domain)
                    topic_blocks_td.append(node.source_block)

            if topic_domains_td and topic_blocks_td:
                max_block = max(topic_blocks_td)
                temporal_found = 0
                for candidate in self.kg.nodes.values():
                    if candidate.node_id in topic_set:
                        continue
                    if candidate.domain not in topic_domains_td:
                        continue
                    # Significantly older node (at least 5000 blocks earlier) = different epoch
                    if max_block - candidate.source_block >= 5000:
                        counter.add(candidate.node_id)
                        temporal_found += 1
                    if temporal_found >= 5:
                        break

        counter -= topic_set
        return list(counter)

    def _find_cross_domain_counter(self, topic_node_ids: List[int],
                                       proposer_ids: Set[int],
                                       max_results: int = 10) -> List[int]:
        """Find counter-evidence from domains NOT used by the proposer.

        Ensures Gevurah reasons independently by sourcing evidence from
        different knowledge domains than Chesed used.

        Args:
            topic_node_ids: Nodes defining the topic.
            proposer_ids: Node IDs already used by the proposer.
            max_results: Maximum nodes to return.

        Returns:
            List of cross-domain counter-evidence node IDs.
        """
        if not self.kg:
            return []

        # Determine domains used by proposer
        proposer_domains: Set[str] = set()
        for nid in proposer_ids:
            node = self.kg.nodes.get(nid)
            if node and node.domain:
                proposer_domains.add(node.domain)
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if node and node.domain:
                proposer_domains.add(node.domain)

        if not proposer_domains:
            return []

        # Find nodes in OTHER domains with low confidence or contradicting edges
        cross: List[int] = []
        exclude = set(topic_node_ids) | proposer_ids
        for candidate in self.kg.nodes.values():
            if candidate.node_id in exclude:
                continue
            if candidate.domain in proposer_domains or not candidate.domain:
                continue
            # Prefer low-confidence cross-domain nodes (different perspective)
            if candidate.confidence < 0.5:
                cross.append(candidate.node_id)
            if len(cross) >= max_results:
                break
        return cross

    def _compute_independence_score(self, pro_ids: List[int],
                                    con_ids: List[int]) -> float:
        """Compute how independent the proposer and critic evidence sources are.

        Score of 1.0 = completely different sources (high independence).
        Score of 0.0 = identical sources (no independence).

        Args:
            pro_ids: Proposer evidence node IDs.
            con_ids: Critic evidence node IDs.

        Returns:
            Float in [0, 1] measuring evidence source independence.
        """
        if not pro_ids and not con_ids:
            return 0.0
        pro_set = set(pro_ids)
        con_set = set(con_ids)
        union = pro_set | con_set
        if not union:
            return 0.0
        overlap = pro_set & con_set
        # Jaccard distance: 1 - (intersection / union)
        independence = 1.0 - len(overlap) / len(union)

        # Boost if domains are different
        if self.kg:
            pro_domains: Set[str] = set()
            con_domains: Set[str] = set()
            for nid in pro_ids:
                node = self.kg.nodes.get(nid)
                if node and node.domain:
                    pro_domains.add(node.domain)
            for nid in con_ids:
                node = self.kg.nodes.get(nid)
                if node and node.domain:
                    con_domains.add(node.domain)
            if pro_domains and con_domains:
                domain_overlap = pro_domains & con_domains
                domain_union = pro_domains | con_domains
                domain_independence = 1.0 - len(domain_overlap) / len(domain_union)
                independence = independence * 0.6 + domain_independence * 0.4

        return round(independence, 4)

    def _generate_counterargument(self, topic_node_ids: List[int]) -> Optional[DebatePosition]:
        """Generate an active counterargument against the topic.

        Searches for:
        1. Nodes with similar content but different conclusions (same domain,
           different node_type — e.g., an 'observation' vs the topic's 'inference')
        2. Temporal contradictions: predictions that were falsified by later
           observations
        3. Weakened support: supporting evidence whose confidence has dropped
           below 0.4 since the inference was made

        Args:
            topic_node_ids: Nodes defining the topic.

        Returns:
            A DebatePosition with the strongest counterargument, or None if
            no meaningful counter was found.
        """
        if not self.kg:
            return None

        topic_set = set(topic_node_ids)
        counter_ids: List[int] = []
        reasons: List[str] = []

        # Collect topic metadata
        topic_types: Set[str] = set()
        topic_domains: Set[str] = set()
        topic_blocks: List[int] = []
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if node:
                topic_types.add(node.node_type)
                if node.domain:
                    topic_domains.add(node.domain)
                topic_blocks.append(node.source_block)

        max_topic_block = max(topic_blocks) if topic_blocks else 0

        # --- 1. Different conclusions in same domain ---
        # Look for nodes with same domain but different node_type
        alt_types = {'assertion', 'observation', 'inference', 'prediction'} - topic_types
        if topic_domains and alt_types:
            found = 0
            for candidate in self.kg.nodes.values():
                if candidate.node_id in topic_set:
                    continue
                if candidate.domain not in topic_domains:
                    continue
                if candidate.node_type not in alt_types:
                    continue
                if candidate.confidence >= 0.4:
                    counter_ids.append(candidate.node_id)
                    found += 1
                if found >= 5:
                    break
            if found > 0:
                reasons.append(f"{found} alternative conclusions in same domain")

        # --- 2. Temporal contradictions: predictions falsified by later observations ---
        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if not node or node.node_type != 'prediction':
                continue
            # Look for observations that came after this prediction
            for edge in self.kg.get_edges_from(nid):
                target = self.kg.nodes.get(edge.to_node_id)
                if (target
                        and target.node_type == 'observation'
                        and target.source_block > node.source_block
                        and edge.edge_type == 'contradicts'):
                    if target.node_id not in topic_set:
                        counter_ids.append(target.node_id)
                        reasons.append(f"prediction falsified at block {target.source_block}")
            for edge in self.kg.get_edges_to(nid):
                target = self.kg.nodes.get(edge.from_node_id)
                if (target
                        and target.node_type == 'observation'
                        and target.source_block > node.source_block
                        and edge.edge_type == 'contradicts'):
                    if target.node_id not in topic_set:
                        counter_ids.append(target.node_id)
                        reasons.append(f"prediction falsified at block {target.source_block}")

        # --- 3. Weakened support: supporting evidence that has decayed ---
        for nid in topic_node_ids:
            for edge in self.kg.get_edges_to(nid):
                if edge.edge_type not in ('supports', 'derives'):
                    continue
                supporter = self.kg.nodes.get(edge.from_node_id)
                if not supporter or supporter.node_id in topic_set:
                    continue
                # If the supporter's confidence has fallen below 0.4, the
                # support is weak — this is evidence AGAINST the topic
                if supporter.confidence < 0.4:
                    counter_ids.append(supporter.node_id)
                    reasons.append(
                        f"support node {supporter.node_id} weakened "
                        f"(conf={supporter.confidence:.2f})"
                    )

        counter_ids = list(set(counter_ids) - topic_set)

        if not counter_ids:
            return None

        # Score the counterargument
        counter_conf = self._compute_evidence_strength(counter_ids)
        reason_text = '; '.join(reasons[:3]) if reasons else "alternative evidence found"

        return DebatePosition(
            role='critic',
            argument=f"Counterargument: {reason_text}",
            confidence=counter_conf,
            evidence_node_ids=counter_ids[:10],
            evidence_quality=self._score_evidence_quality(counter_ids),
            round_num=-1,  # Synthetic position, not tied to a round
        )

    # ------------------------------------------------------------------
    # Evidence quality scoring (Judge / Tiferet)
    # ------------------------------------------------------------------

    def _score_evidence_quality(self, evidence_node_ids: List[int]) -> float:
        """Score a set of evidence nodes on quality metrics.

        Enhanced metrics:
        - Source diversity: unique source_blocks / total evidence nodes
        - Avg confidence: mean confidence of evidence nodes
        - Causal strength: fraction of causal vs support edges
        - Recency bonus: more recent evidence gets higher quality
        - Grounding bonus: evidence with grounding_source gets extra credit

        Args:
            evidence_node_ids: List of evidence node IDs.

        Returns:
            Quality score in [0.0, 1.0].
        """
        if not evidence_node_ids or not self.kg:
            return 0.0

        valid_nodes = []
        source_blocks: Set[int] = set()
        total_confidence = 0.0

        for nid in evidence_node_ids:
            node = self.kg.nodes.get(nid)
            if node:
                valid_nodes.append(node)
                source_blocks.add(node.source_block)
                total_confidence += node.confidence

        if not valid_nodes:
            return 0.0

        n = len(valid_nodes)

        # --- Source diversity: unique blocks / node count (1.0 = every node from different block) ---
        source_diversity = len(source_blocks) / n

        # --- Average confidence ---
        avg_confidence = total_confidence / n

        # --- Confidence consistency: 1 - std_dev (penalize wildly varying confidence) ---
        mean_conf = avg_confidence
        if n > 1:
            variance = sum((nd.confidence - mean_conf) ** 2 for nd in valid_nodes) / n
            std_dev = variance ** 0.5
            conf_consistency = max(0.0, 1.0 - std_dev)
        else:
            conf_consistency = 1.0

        # --- Causal strength: fraction of related edges that are 'causes' ---
        causal_edges = 0
        support_edges = 0
        for nid in evidence_node_ids:
            for edge in self.kg.get_edges_from(nid):
                if edge.edge_type == 'causes':
                    causal_edges += 1
                elif edge.edge_type == 'supports':
                    support_edges += 1
            for edge in self.kg.get_edges_to(nid):
                if edge.edge_type == 'causes':
                    causal_edges += 1
                elif edge.edge_type == 'supports':
                    support_edges += 1

        total_relevant_edges = causal_edges + support_edges
        if total_relevant_edges > 0:
            causal_strength = causal_edges / total_relevant_edges
        else:
            causal_strength = 0.0

        # --- Grounding bonus: evidence with verified grounding sources ---
        grounded_count = sum(
            1 for nd in valid_nodes
            if hasattr(nd, 'grounding_source') and nd.grounding_source
        )
        grounding_score = grounded_count / n if n > 0 else 0.0

        # Weighted blend with grounding bonus
        quality = (
            0.20 * source_diversity
            + 0.25 * avg_confidence
            + 0.15 * conf_consistency
            + 0.25 * causal_strength
            + 0.15 * grounding_score
        )

        return max(0.0, min(1.0, quality))

    # ------------------------------------------------------------------
    # Verdict application
    # ------------------------------------------------------------------

    def _apply_verdict_to_topics(self, topic_node_ids: List[int],
                                 verdict: str,
                                 synthesis_conf: float) -> None:
        """Update topic node confidence based on the debate verdict.

        - 'accepted': boost confidence by _ACCEPTED_BOOST (capped at 1.0)
        - 'rejected': reduce confidence by _REJECTED_PENALTY (floored at 0.0)
        - 'modified': set confidence to synthesis_conf

        Args:
            topic_node_ids: Nodes to update.
            verdict: The debate verdict.
            synthesis_conf: The synthesis confidence (used for 'modified').
        """
        if not self.kg:
            return

        for nid in topic_node_ids:
            node = self.kg.nodes.get(nid)
            if not node:
                continue

            old_conf = node.confidence
            if verdict == 'accepted':
                node.confidence = min(1.0, node.confidence + self._ACCEPTED_BOOST)
            elif verdict == 'rejected':
                node.confidence = max(0.0, node.confidence - self._REJECTED_PENALTY)
            elif verdict == 'modified':
                node.confidence = max(0.0, min(1.0, synthesis_conf))

            if node.confidence != old_conf:
                logger.debug(
                    f"Debate verdict '{verdict}' updated node {nid} confidence: "
                    f"{old_conf:.4f} -> {node.confidence:.4f}"
                )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _extract_numeric_profile(self, node_ids: List[int]) -> Set[str]:
        """Extract all numeric values from the content of the given nodes.

        Args:
            node_ids: Nodes to extract numbers from.

        Returns:
            Set of numeric string tokens found in node content.
        """
        numbers: Set[str] = set()
        for nid in node_ids:
            node = self.kg.nodes.get(nid)
            if node:
                text = str(node.content.get('text', '')).lower()
                numbers.update(re.findall(r'\b\d+\.?\d*\b', text))
        return numbers

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

    # ------------------------------------------------------------------
    # Periodic and stats
    # ------------------------------------------------------------------

    def _generate_synthesis_text(self, verdict: str,
                                 proposer_conf: float, critic_conf: float,
                                 pro_quality: float, con_quality: float,
                                 pro_evidence: List[int], con_evidence: List[int],
                                 topic_text: str) -> str:
        """Generate a natural language synthesis of the debate outcome.

        Args:
            verdict: The debate verdict.
            proposer_conf/critic_conf: Final confidence scores.
            pro_quality/con_quality: Evidence quality scores.
            pro_evidence/con_evidence: Evidence node IDs.
            topic_text: Topic description.

        Returns:
            Human-readable synthesis string.
        """
        parts: List[str] = []

        if verdict == 'accepted':
            parts.append(
                f"The proposition regarding '{topic_text[:80]}' was ACCEPTED. "
                f"Supporting evidence ({len(pro_evidence)} nodes, quality {pro_quality:.2f}) "
                f"outweighed counter-evidence ({len(con_evidence)} nodes, quality {con_quality:.2f})."
            )
        elif verdict == 'rejected':
            parts.append(
                f"The proposition regarding '{topic_text[:80]}' was REJECTED. "
                f"Counter-evidence ({len(con_evidence)} nodes, quality {con_quality:.2f}) "
                f"successfully challenged the proposition "
                f"(proposer conf: {proposer_conf:.2f}, critic conf: {critic_conf:.2f})."
            )
        else:
            parts.append(
                f"The proposition regarding '{topic_text[:80]}' was MODIFIED. "
                f"Both sides presented compelling evidence "
                f"(pro quality: {pro_quality:.2f}, con quality: {con_quality:.2f}). "
                f"The conclusion incorporates insights from both perspectives."
            )

        # Confidence assessment
        conf_diff = abs(proposer_conf - critic_conf)
        if conf_diff < 0.1:
            parts.append("The debate was closely contested.")
        elif conf_diff > 0.3:
            parts.append(f"One side held a significant advantage (delta: {conf_diff:.2f}).")

        return ' '.join(parts)

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

        # Find inference nodes with moderate-to-high confidence that haven't
        # been debated yet.  Prefer recent nodes but fall back to older ones
        # so that debates always have candidates.
        debated_ids = {
            d.get('topic_id')
            for d in getattr(self, '_debate_log', [])
            if isinstance(d, dict)
        }
        candidates = [
            n for n in self.kg.nodes.values()
            if n.node_type == 'inference'
            and n.confidence >= 0.5
            and n.node_id not in debated_ids
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
            'undecided': self._undecided,
            'acceptance_rate': round(
                self._accepted / max(1, self._debates_run), 4
            ),
        }


# ======================================================================
# N-Party Debate with Coalition Formation
# ======================================================================


@dataclass
class _DebateParty:
    """Internal representation of a party in a multi-party debate."""
    name: str
    position: str
    confidence: float


class MultiPartyDebate:
    """N-party debate protocol with coalition formation.

    Extends the 2-party adversarial model to support an arbitrary number
    of participants.  Each party holds a position string and a confidence
    float.  During debate rounds every party evaluates all other arguments,
    adjusting confidence based on argument strength.  After evaluation,
    parties whose positions are textually similar (above a configurable
    threshold) form coalitions.  The coalition with the highest aggregate
    strength (sum of member confidences) wins after all rounds complete.

    Usage::

        debate = MultiPartyDebate()
        debate.add_party("Alice", "Quantum supremacy is near", 0.8)
        debate.add_party("Bob", "Quantum supremacy is near term", 0.6)
        debate.add_party("Eve", "Classical computers will suffice", 0.7)
        result = debate.run_debate("Quantum computing future", rounds=3)
        # result.winner == "Quantum supremacy is near" (Alice+Bob coalition)
    """

    # How much a party's confidence shifts per evaluation round
    _EVAL_SHIFT: float = 0.05
    # Default similarity threshold for coalition formation
    _DEFAULT_COALITION_THRESHOLD: float = 0.7

    def __init__(self) -> None:
        self._parties: List[_DebateParty] = []
        self._debates_run: int = 0

    # ------------------------------------------------------------------
    # Party management
    # ------------------------------------------------------------------

    def add_party(self, name: str, position: str,
                  initial_confidence: float) -> None:
        """Register a new debate participant.

        Args:
            name: Unique identifier for the party.
            position: The party's stance (free-text).
            initial_confidence: Starting confidence in [0.0, 1.0].

        Raises:
            ValueError: If *name* is empty, *position* is empty, or a
                party with the same *name* already exists.
        """
        if not name:
            raise ValueError("Party name must not be empty")
        if not position:
            raise ValueError("Party position must not be empty")
        if any(p.name == name for p in self._parties):
            raise ValueError(f"Party '{name}' already exists")
        clamped = max(0.0, min(1.0, initial_confidence))
        self._parties.append(_DebateParty(
            name=name, position=position, confidence=clamped,
        ))
        logger.debug(
            "MultiPartyDebate: added party '%s' (confidence=%.3f)",
            name, clamped,
        )

    # ------------------------------------------------------------------
    # Core debate loop
    # ------------------------------------------------------------------

    def run_debate(self, topic: str,
                   rounds: int = 3) -> MultiPartyDebateResult:
        """Execute an N-party debate and return the result.

        Protocol per round:
        1. Each party *presents* an argument derived from its position.
        2. Every other party *evaluates* each argument — if the argument
           is similar to the evaluator's own position the evaluator's
           confidence increases slightly; otherwise it decreases.
        3. After all evaluations, coalitions are formed from parties
           whose positions exceed the similarity threshold.

        After the final round the strongest coalition wins.

        Args:
            topic: Free-text topic of the debate.
            rounds: Number of debate rounds (min 1).

        Returns:
            MultiPartyDebateResult with winner, coalitions, and per-round
            log entries.
        """
        if len(self._parties) < 2:
            logger.warning(
                "MultiPartyDebate: need >= 2 parties, got %d",
                len(self._parties),
            )
            winner = self._parties[0].position if self._parties else ""
            return MultiPartyDebateResult(
                topic=topic, rounds=0, winner=winner,
                coalitions=[], rounds_log=[],
            )

        rounds = max(1, rounds)
        self._debates_run += 1
        rounds_log: List[Dict[str, Any]] = []

        for round_num in range(rounds):
            round_entry: Dict[str, Any] = {
                'round': round_num + 1,
                'arguments': [],
                'evaluations': [],
            }

            # --- 1. Each party presents an argument ---
            arguments: Dict[str, str] = {}
            for party in self._parties:
                arg = self._generate_argument(party, topic, round_num)
                arguments[party.name] = arg
                round_entry['arguments'].append({
                    'party': party.name,
                    'argument': arg,
                    'confidence': round(party.confidence, 4),
                })

            # --- 2. Each party evaluates every other party's argument ---
            for evaluator in self._parties:
                for presenter in self._parties:
                    if evaluator.name == presenter.name:
                        continue
                    similarity = self._position_similarity(
                        evaluator.position, presenter.position,
                    )
                    old_conf = evaluator.confidence
                    if similarity > 0.5:
                        # Similar position reinforces confidence
                        evaluator.confidence = min(
                            1.0,
                            evaluator.confidence
                            + self._EVAL_SHIFT * similarity,
                        )
                    else:
                        # Opposing position erodes confidence slightly
                        evaluator.confidence = max(
                            0.0,
                            evaluator.confidence
                            - self._EVAL_SHIFT * (1.0 - similarity),
                        )
                    round_entry['evaluations'].append({
                        'evaluator': evaluator.name,
                        'presenter': presenter.name,
                        'similarity': round(similarity, 4),
                        'confidence_delta': round(
                            evaluator.confidence - old_conf, 4,
                        ),
                    })

            # --- 3. Form coalitions at end of round ---
            coalitions = self.form_coalitions()
            round_entry['coalitions'] = [
                {'members': c.members, 'position': c.position,
                 'strength': round(c.strength, 4)}
                for c in coalitions
            ]
            rounds_log.append(round_entry)

        # --- Final verdict: strongest coalition wins ---
        final_coalitions = self.form_coalitions()
        if final_coalitions:
            best = max(final_coalitions, key=lambda c: c.strength)
            winner = best.position
        else:
            # Fallback: party with highest confidence
            best_party = max(self._parties, key=lambda p: p.confidence)
            winner = best_party.position

        result = MultiPartyDebateResult(
            topic=topic,
            rounds=rounds,
            winner=winner,
            coalitions=final_coalitions,
            rounds_log=rounds_log,
        )

        logger.info(
            "MultiPartyDebate on '%s': %d parties, %d rounds, "
            "winner='%s', %d coalitions",
            topic[:60], len(self._parties), rounds,
            winner[:60], len(final_coalitions),
        )

        return result

    # ------------------------------------------------------------------
    # Coalition formation
    # ------------------------------------------------------------------

    def form_coalitions(self,
                        threshold: float = 0.7) -> List[Coalition]:
        """Group parties into coalitions by position similarity.

        Uses a simple greedy clustering: iterate through parties and
        assign each to the first existing coalition whose representative
        position has similarity >= *threshold*.  If no match, start a
        new coalition.

        Args:
            threshold: Minimum similarity (0.0-1.0) for two positions
                to be considered "same coalition".  Defaults to 0.7.

        Returns:
            List of Coalition objects sorted by strength (descending).
        """
        coalitions: List[Coalition] = []

        for party in self._parties:
            placed = False
            for coalition in coalitions:
                sim = self._position_similarity(
                    party.position, coalition.position,
                )
                if sim >= threshold:
                    coalition.members.append(party.name)
                    coalition.strength += party.confidence
                    placed = True
                    break
            if not placed:
                coalitions.append(Coalition(
                    members=[party.name],
                    position=party.position,
                    strength=party.confidence,
                ))

        # Sort strongest first
        coalitions.sort(key=lambda c: c.strength, reverse=True)
        return coalitions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _position_similarity(pos_a: str, pos_b: str) -> float:
        """Compute textual similarity between two positions.

        Uses :class:`difflib.SequenceMatcher` ratio which returns a
        float in [0.0, 1.0].

        Args:
            pos_a: First position string.
            pos_b: Second position string.

        Returns:
            Similarity score in [0.0, 1.0].
        """
        if not pos_a or not pos_b:
            return 0.0
        return SequenceMatcher(
            None, pos_a.lower(), pos_b.lower(),
        ).ratio()

    @staticmethod
    def _generate_argument(party: '_DebateParty', topic: str,
                           round_num: int) -> str:
        """Generate a textual argument for a party in a given round.

        In a production system this would call into the reasoning engine
        or an LLM.  Here we produce a deterministic summary suitable for
        logging and testing.

        Args:
            party: The presenting party.
            topic: Debate topic.
            round_num: Zero-based round number.

        Returns:
            Argument string.
        """
        return (
            f"[{party.name}] Round {round_num + 1} on '{topic[:40]}': "
            f"position='{party.position[:60]}' "
            f"(confidence={party.confidence:.3f})"
        )

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for this debate instance."""
        return {
            'total_debates': self._debates_run,
            'num_parties': len(self._parties),
            'parties': [
                {'name': p.name, 'position': p.position,
                 'confidence': round(p.confidence, 4)}
                for p in self._parties
            ],
        }
