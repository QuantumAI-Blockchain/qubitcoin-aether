"""
Knowledge Gap Detector — Identify what the KG doesn't know.

Detects missing domains, stale knowledge, disconnected islands,
prediction failures, and low-confidence regions, then suggests
exploration queries.

AGI Roadmap Item #59.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class KnowledgeGap:
    """A detected gap in the knowledge graph."""
    gap_type: str  # missing_domain, stale_knowledge, disconnected_island, prediction_failure, low_confidence
    severity: float  # 0.0 to 1.0
    description: str
    suggested_action: str
    domain: str = "general"
    node_ids: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class GapDetector:
    """Autonomous knowledge gap detection for the Aether Tree KG."""

    # All domains the AGI should cover
    EXPECTED_DOMAINS = [
        "blockchain", "quantum_physics", "economics", "technology",
        "cryptography", "mathematics", "philosophy", "science",
    ]

    def __init__(self, stale_threshold_blocks: int = 5000,
                 low_confidence_threshold: float = 0.5,
                 min_domain_nodes: int = 5) -> None:
        self._stale_threshold: int = stale_threshold_blocks
        self._low_conf_threshold: float = low_confidence_threshold
        self._min_domain_nodes: int = min_domain_nodes
        self._detections: int = 0
        self._total_gaps_found: int = 0
        self._gap_history: List[dict] = []
        self._max_history: int = 500

    def detect_gaps(self, knowledge_graph: Any,
                    current_block: int = 0) -> List[KnowledgeGap]:
        """Detect all types of knowledge gaps.

        Args:
            knowledge_graph: The KG instance with .nodes and .edges attributes.
            current_block: Current block height for staleness calculation.

        Returns:
            List of detected KnowledgeGap instances.
        """
        if knowledge_graph is None:
            return []

        self._detections += 1
        gaps: List[KnowledgeGap] = []

        gaps.extend(self._detect_missing_domains(knowledge_graph))
        gaps.extend(self._detect_stale_knowledge(knowledge_graph, current_block))
        gaps.extend(self._detect_disconnected_islands(knowledge_graph))
        gaps.extend(self._detect_low_confidence_regions(knowledge_graph))
        gaps.extend(self._detect_prediction_failures(knowledge_graph))

        self._total_gaps_found += len(gaps)
        if len(self._gap_history) < self._max_history:
            self._gap_history.append({
                "block": current_block,
                "gaps_found": len(gaps),
                "types": [g.gap_type for g in gaps],
            })

        if gaps:
            logger.debug(
                f"Gap detection found {len(gaps)} gaps at block {current_block}: "
                f"{[g.gap_type for g in gaps[:5]]}"
            )

        return gaps

    def _detect_missing_domains(self, kg: Any) -> List[KnowledgeGap]:
        """Find domains with too few nodes."""
        gaps = []
        domain_counts: Dict[str, int] = {}
        for node in kg.nodes.values():
            content = getattr(node, "content", {})
            domain = content.get("domain", "general") if isinstance(content, dict) else "general"
            domain_counts[domain] = domain_counts.get(domain, 0) + 1

        for domain in self.EXPECTED_DOMAINS:
            count = domain_counts.get(domain, 0)
            if count < self._min_domain_nodes:
                severity = 1.0 - (count / max(self._min_domain_nodes, 1))
                gaps.append(KnowledgeGap(
                    gap_type="missing_domain",
                    severity=severity,
                    description=f"Domain '{domain}' has only {count} nodes (min={self._min_domain_nodes})",
                    suggested_action=f"Explore and add knowledge about {domain}",
                    domain=domain,
                    metadata={"count": count, "minimum": self._min_domain_nodes},
                ))
        return gaps

    def _detect_stale_knowledge(self, kg: Any, current_block: int) -> List[KnowledgeGap]:
        """Find nodes that haven't been updated in a long time."""
        if current_block < self._stale_threshold:
            return []

        gaps = []
        stale_cutoff = current_block - self._stale_threshold
        stale_nodes: List[str] = []

        for nid, node in kg.nodes.items():
            source_block = getattr(node, "source_block", 0)
            if source_block < stale_cutoff:
                stale_nodes.append(nid)

        if stale_nodes:
            severity = min(len(stale_nodes) / max(len(kg.nodes), 1), 1.0)
            gaps.append(KnowledgeGap(
                gap_type="stale_knowledge",
                severity=severity,
                description=f"{len(stale_nodes)} nodes not updated since block {stale_cutoff}",
                suggested_action="Re-evaluate stale knowledge nodes for relevance",
                node_ids=stale_nodes[:50],
                metadata={"stale_count": len(stale_nodes), "cutoff_block": stale_cutoff},
            ))
        return gaps

    def _detect_disconnected_islands(self, kg: Any) -> List[KnowledgeGap]:
        """Find unreachable subgraphs (nodes with no edges)."""
        gaps = []
        connected: Set[str] = set()

        for edge in kg.edges.values():
            src = getattr(edge, "source_id", None) or (edge.get("source_id") if isinstance(edge, dict) else None)
            tgt = getattr(edge, "target_id", None) or (edge.get("target_id") if isinstance(edge, dict) else None)
            if src:
                connected.add(src)
            if tgt:
                connected.add(tgt)

        disconnected = [nid for nid in kg.nodes if nid not in connected]
        if disconnected and len(kg.nodes) > 5:
            ratio = len(disconnected) / len(kg.nodes)
            if ratio > 0.1:
                gaps.append(KnowledgeGap(
                    gap_type="disconnected_island",
                    severity=min(ratio, 1.0),
                    description=f"{len(disconnected)} nodes ({ratio:.0%}) have no connections",
                    suggested_action="Connect isolated nodes to related knowledge or prune",
                    node_ids=disconnected[:50],
                    metadata={"disconnected_count": len(disconnected), "ratio": ratio},
                ))
        return gaps

    def _detect_low_confidence_regions(self, kg: Any) -> List[KnowledgeGap]:
        """Find regions where average confidence is below threshold."""
        gaps = []
        domain_confs: Dict[str, List[float]] = {}

        for node in kg.nodes.values():
            conf = getattr(node, "confidence", 0.5)
            content = getattr(node, "content", {})
            domain = content.get("domain", "general") if isinstance(content, dict) else "general"
            if domain not in domain_confs:
                domain_confs[domain] = []
            domain_confs[domain].append(conf)

        for domain, confs in domain_confs.items():
            if not confs:
                continue
            avg_conf = sum(confs) / len(confs)
            if avg_conf < self._low_conf_threshold and len(confs) >= 3:
                gaps.append(KnowledgeGap(
                    gap_type="low_confidence",
                    severity=1.0 - avg_conf,
                    description=f"Domain '{domain}' has avg confidence {avg_conf:.3f} (threshold={self._low_conf_threshold})",
                    suggested_action=f"Gather stronger evidence for {domain} claims",
                    domain=domain,
                    metadata={"avg_confidence": avg_conf, "node_count": len(confs)},
                ))
        return gaps

    def _detect_prediction_failures(self, kg: Any) -> List[KnowledgeGap]:
        """Detect domains with low prediction accuracy from node metadata."""
        gaps = []
        domain_accuracy: Dict[str, List[float]] = {}

        for node in kg.nodes.values():
            content = getattr(node, "content", {})
            if not isinstance(content, dict):
                continue
            accuracy = content.get("prediction_accuracy")
            if accuracy is not None:
                domain = content.get("domain", "general")
                if domain not in domain_accuracy:
                    domain_accuracy[domain] = []
                domain_accuracy[domain].append(float(accuracy))

        for domain, accs in domain_accuracy.items():
            if not accs:
                continue
            avg_acc = sum(accs) / len(accs)
            if avg_acc < 0.4 and len(accs) >= 3:
                gaps.append(KnowledgeGap(
                    gap_type="prediction_failure",
                    severity=1.0 - avg_acc,
                    description=f"Domain '{domain}' has prediction accuracy {avg_acc:.3f}",
                    suggested_action=f"Retrain models or revise theories for {domain}",
                    domain=domain,
                    metadata={"avg_accuracy": avg_acc, "sample_count": len(accs)},
                ))
        return gaps

    def prioritize_gaps(self, gaps: List[KnowledgeGap]) -> List[KnowledgeGap]:
        """Sort gaps by severity, highest first."""
        return sorted(gaps, key=lambda g: g.severity, reverse=True)

    def generate_exploration_queries(self, gap: KnowledgeGap) -> List[str]:
        """Generate exploration queries to address a knowledge gap."""
        queries = []
        if gap.gap_type == "missing_domain":
            queries = [
                f"What are the fundamental concepts in {gap.domain}?",
                f"How does {gap.domain} relate to blockchain?",
                f"What are recent developments in {gap.domain}?",
            ]
        elif gap.gap_type == "stale_knowledge":
            queries = [
                "What has changed since the stale knowledge was recorded?",
                "Are the original assumptions still valid?",
                "Should outdated nodes be pruned or updated?",
            ]
        elif gap.gap_type == "disconnected_island":
            queries = [
                "What relationships connect these isolated nodes to the main graph?",
                "Are these nodes redundant with existing knowledge?",
                "What shared concepts could bridge these islands?",
            ]
        elif gap.gap_type == "low_confidence":
            queries = [
                f"What additional evidence supports claims in {gap.domain}?",
                f"Are there contradictions reducing confidence in {gap.domain}?",
                f"What authoritative sources can ground {gap.domain} knowledge?",
            ]
        elif gap.gap_type == "prediction_failure":
            queries = [
                f"Why are predictions failing for {gap.domain}?",
                f"What confounders affect {gap.domain} predictions?",
                f"Should the prediction model for {gap.domain} be restructured?",
            ]
        return queries

    def get_stats(self) -> dict:
        """Return gap detector statistics."""
        return {
            "detections": self._detections,
            "total_gaps_found": self._total_gaps_found,
            "history_size": len(self._gap_history),
            "avg_gaps_per_detection": (
                self._total_gaps_found / max(self._detections, 1)
            ),
        }
