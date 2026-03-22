"""
KG Summarizer — Template-based summarization of knowledge graph subgraphs

Item #46: Natural language summaries of KG subgraphs, blocks, and topics.
Aggregates by domain, highlights key stats, trends, and anomalies.
"""
import time
from typing import Any, Dict, List, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Node type → summary template
# ---------------------------------------------------------------------------

_NODE_TEMPLATES: Dict[str, str] = {
    "block_observation": "Block {height} observed at difficulty {difficulty} with {tx_count} transaction(s).",
    "quantum_observation": "Quantum measurement at block {block_height}: energy={energy}, difficulty={difficulty}.",
    "contract_activity": "Contract {tx_type} activity detected at block {block_height}.",
    "prediction": "Prediction for {metric}: expected {predicted_value} (confidence {confidence}).",
    "inference": "Inference ({operation_type}): {explanation}",
    "axiom": "Established fact: {description}",
    "concept": "Concept '{name}' formed from {member_count} observations in domain '{domain}'.",
    "hypothesis": "Hypothesis: {description} (confidence {confidence}).",
    "causal_edge": "Causal link: {cause} → {effect} (strength {strength}).",
    "milestone": "Chain milestone at block {height}: {tx_count} transactions.",
    "difficulty_shift": "Difficulty shift at block {height}: new difficulty {difficulty}.",
}

_EDGE_TEMPLATES: Dict[str, str] = {
    "derives": "{source} derives from {target}.",
    "supports": "{source} supports {target}.",
    "contradicts": "{source} contradicts {target}.",
    "causes": "{source} causes {target}.",
    "correlates": "{source} correlates with {target}.",
    "generalizes": "{source} generalizes {target}.",
    "subsumes": "{source} subsumes {target}.",
}

# Domain → human-readable name
_DOMAIN_NAMES: Dict[str, str] = {
    "blockchain": "Blockchain",
    "economics": "Economics",
    "quantum_physics": "Quantum Physics",
    "technology": "Technology",
    "general": "General",
    "consciousness": "Consciousness",
    "governance": "Governance",
    "security": "Security",
}


def _fill_template(template: str, data: dict) -> str:
    """Fill a template string with data dict values."""
    try:
        result = template
        for key, val in data.items():
            placeholder = "{" + str(key) + "}"
            if placeholder in result:
                if isinstance(val, float):
                    result = result.replace(placeholder, f"{val:.4f}")
                else:
                    result = result.replace(placeholder, str(val))
        # Remove any unfilled placeholders
        import re
        result = re.sub(r'\{[a-z_]+\}', '?', result)
        return result
    except Exception:
        return str(data)


def _node_to_text(node: Any) -> str:
    """Convert a KG node to a summary sentence."""
    content = getattr(node, 'content', None) or {}
    if isinstance(content, str):
        return content

    if not isinstance(content, dict):
        return str(content)

    node_type = content.get('type', '')

    # Try matching template
    template = _NODE_TEMPLATES.get(node_type)
    if template:
        return _fill_template(template, content)

    # Fallback: describe key fields
    desc = content.get('description') or content.get('text') or content.get('explanation')
    if desc:
        return str(desc)

    # Generic fallback
    domain = getattr(node, 'domain', 'general')
    conf = getattr(node, 'confidence', 0)
    return f"{node_type or 'node'} in {domain} domain (confidence {conf:.2f})"


class KGSummarizer:
    """Template-based summarizer for knowledge graph data."""

    def __init__(self) -> None:
        self._calls: int = 0
        self._total_time: float = 0.0
        self._summaries_generated: int = 0

    # ------------------------------------------------------------------
    # Subgraph summary
    # ------------------------------------------------------------------

    def summarize_subgraph(self, nodes: List[Any],
                           edges: List[Any]) -> str:
        """Generate a natural language summary of a KG subgraph.

        Args:
            nodes: List of KG node objects.
            edges: List of KG edge tuples or objects.

        Returns:
            Natural language summary string.
        """
        t0 = time.time()
        self._calls += 1

        if not nodes:
            self._total_time += time.time() - t0
            return "No knowledge nodes to summarize."

        # Group nodes by domain
        domain_groups: Dict[str, List[Any]] = {}
        for node in nodes:
            domain = getattr(node, 'domain', 'general')
            domain_groups.setdefault(domain, []).append(node)

        # Group nodes by type
        type_groups: Dict[str, int] = {}
        for node in nodes:
            content = getattr(node, 'content', {})
            ntype = content.get('type', 'unknown') if isinstance(content, dict) else 'unknown'
            type_groups[ntype] = type_groups.get(ntype, 0) + 1

        # Build summary
        parts: List[str] = []

        # Overview
        parts.append(
            f"Summary of {len(nodes)} knowledge nodes across "
            f"{len(domain_groups)} domain(s) with {len(edges)} connections."
        )

        # Domain breakdown
        for domain, group in sorted(domain_groups.items(), key=lambda x: -len(x[1])):
            domain_name = _DOMAIN_NAMES.get(domain, domain.title())
            sentences = [_node_to_text(n) for n in group[:5]]
            parts.append(f"\n**{domain_name}** ({len(group)} nodes):")
            for s in sentences:
                parts.append(f"  - {s}")
            if len(group) > 5:
                parts.append(f"  - ... and {len(group) - 5} more.")

        # Edge summary
        if edges:
            edge_types: Dict[str, int] = {}
            for edge in edges:
                if isinstance(edge, tuple) and len(edge) >= 3:
                    etype = str(edge[2]) if len(edge) > 2 else "related"
                elif hasattr(edge, 'edge_type'):
                    etype = edge.edge_type
                else:
                    etype = "related"
                edge_types[etype] = edge_types.get(etype, 0) + 1

            edge_desc = ", ".join(
                f"{count} {etype}" for etype, count in
                sorted(edge_types.items(), key=lambda x: -x[1])
            )
            parts.append(f"\nConnections: {edge_desc}.")

        # Type breakdown
        type_desc = ", ".join(
            f"{count} {ntype}" for ntype, count in
            sorted(type_groups.items(), key=lambda x: -x[1])
        )
        parts.append(f"Node types: {type_desc}.")

        # Confidence stats
        confidences = [getattr(n, 'confidence', 0) for n in nodes]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            parts.append(f"Average confidence: {avg_conf:.2f}.")

        summary = "\n".join(parts)
        self._summaries_generated += 1
        self._total_time += time.time() - t0
        return summary

    # ------------------------------------------------------------------
    # Block summary
    # ------------------------------------------------------------------

    def summarize_block(self, block_height: int, kg_data: dict) -> str:
        """Generate a natural language summary of knowledge at a block height.

        Args:
            block_height: The block height.
            kg_data: Dict with optional keys: nodes, edges, phi_value,
                     difficulty, tx_count, predictions, etc.

        Returns:
            Summary string.
        """
        t0 = time.time()
        self._calls += 1

        parts: List[str] = []

        # Header
        parts.append(f"Block {block_height} Knowledge Summary")
        parts.append("=" * 40)

        # Chain metrics
        difficulty = kg_data.get('difficulty')
        tx_count = kg_data.get('tx_count', 0)
        phi_value = kg_data.get('phi_value')
        reward = kg_data.get('reward')

        metrics: List[str] = []
        if difficulty is not None:
            metrics.append(f"difficulty={difficulty:.4f}")
        if tx_count:
            metrics.append(f"transactions={tx_count}")
        if phi_value is not None:
            metrics.append(f"phi={phi_value:.4f}")
        if reward is not None:
            metrics.append(f"reward={reward:.2f} QBC")
        if metrics:
            parts.append("Chain state: " + ", ".join(metrics) + ".")

        # Knowledge growth
        nodes = kg_data.get('nodes', [])
        edges = kg_data.get('edges', [])
        new_nodes = kg_data.get('new_nodes', 0)
        total_nodes = kg_data.get('total_nodes', len(nodes) if nodes else 0)

        if new_nodes > 0:
            parts.append(
                f"Knowledge growth: {new_nodes} new node(s) added "
                f"(total: {total_nodes})."
            )
        elif total_nodes > 0:
            parts.append(f"Knowledge graph size: {total_nodes} nodes.")

        # Predictions
        predictions = kg_data.get('predictions', [])
        if predictions:
            parts.append(f"Active predictions: {len(predictions)}.")
            for pred in predictions[:3]:
                if isinstance(pred, dict):
                    metric = pred.get('metric', 'unknown')
                    val = pred.get('predicted_value', '?')
                    parts.append(f"  - {metric}: predicted {val}")

        # Anomalies
        anomalies = kg_data.get('anomalies', [])
        if anomalies:
            parts.append(f"Anomalies detected: {len(anomalies)}.")
            for anomaly in anomalies[:3]:
                if isinstance(anomaly, str):
                    parts.append(f"  - {anomaly}")
                elif isinstance(anomaly, dict):
                    parts.append(f"  - {anomaly.get('description', str(anomaly))}")

        # Trends
        trends = kg_data.get('trends', [])
        if trends:
            parts.append("Trends:")
            for trend in trends[:3]:
                if isinstance(trend, str):
                    parts.append(f"  - {trend}")
                elif isinstance(trend, dict):
                    parts.append(f"  - {trend.get('description', str(trend))}")

        summary = "\n".join(parts)
        self._summaries_generated += 1
        self._total_time += time.time() - t0
        return summary

    # ------------------------------------------------------------------
    # Topic summary
    # ------------------------------------------------------------------

    def summarize_topic(self, topic: str,
                        related_nodes: List[Any]) -> str:
        """Summarize knowledge about a specific topic.

        Args:
            topic: The topic string.
            related_nodes: KG nodes related to this topic.

        Returns:
            Summary string.
        """
        t0 = time.time()
        self._calls += 1

        if not related_nodes:
            self._total_time += time.time() - t0
            return f"No knowledge available about '{topic}'."

        parts: List[str] = []
        parts.append(f"Knowledge about '{topic}' ({len(related_nodes)} nodes):")

        # Sort by confidence descending
        sorted_nodes = sorted(
            related_nodes,
            key=lambda n: getattr(n, 'confidence', 0),
            reverse=True,
        )

        # Top findings (bullet points)
        for node in sorted_nodes[:10]:
            text = _node_to_text(node)
            conf = getattr(node, 'confidence', 0)
            parts.append(f"  - [{conf:.2f}] {text}")

        if len(related_nodes) > 10:
            parts.append(f"  - ... and {len(related_nodes) - 10} more nodes.")

        # Domain distribution
        domain_counts: Dict[str, int] = {}
        for node in related_nodes:
            d = getattr(node, 'domain', 'general')
            domain_counts[d] = domain_counts.get(d, 0) + 1
        if domain_counts:
            dist = ", ".join(
                f"{_DOMAIN_NAMES.get(d, d)}: {c}"
                for d, c in sorted(domain_counts.items(), key=lambda x: -x[1])
            )
            parts.append(f"Domain distribution: {dist}.")

        # Confidence range
        confs = [getattr(n, 'confidence', 0) for n in related_nodes]
        if confs:
            parts.append(
                f"Confidence range: {min(confs):.2f} – {max(confs):.2f} "
                f"(avg {sum(confs)/len(confs):.2f})."
            )

        # Time range
        blocks = [
            getattr(n, 'source_block', None) for n in related_nodes
            if getattr(n, 'source_block', None) is not None
        ]
        if blocks:
            parts.append(f"Block range: {min(blocks)} – {max(blocks)}.")

        summary = "\n".join(parts)
        self._summaries_generated += 1
        self._total_time += time.time() - t0
        return summary

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return summarizer statistics."""
        return {
            "calls": self._calls,
            "summaries_generated": self._summaries_generated,
            "total_time_s": round(self._total_time, 4),
            "avg_time_per_call_ms": (
                round(self._total_time / self._calls * 1000, 2)
                if self._calls else 0.0
            ),
        }
