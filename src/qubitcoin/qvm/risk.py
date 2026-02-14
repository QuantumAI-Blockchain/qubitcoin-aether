"""
Risk Score Normalization — 0-100 scale risk assessment

Combines signals from:
  - AML monitor alerts
  - Transaction graph analysis
  - Compliance engine status
  - QRISK opcode raw values

into a single normalised 0-100 risk score per address.
"""
import math
from dataclasses import dataclass
from typing import Dict, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RiskBreakdown:
    """Detailed breakdown of a risk score."""
    address: str
    total_score: float          # 0-100 (clamped)
    aml_score: float = 0.0     # From AML monitor (0-100)
    graph_score: float = 0.0   # From transaction graph (0-100)
    compliance_score: float = 0.0  # From compliance status (0-100)
    raw_qrisk: float = 0.0     # Raw QRISK value (0-100)

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'total_score': round(self.total_score, 2),
            'aml_score': round(self.aml_score, 2),
            'graph_score': round(self.graph_score, 2),
            'compliance_score': round(self.compliance_score, 2),
            'raw_qrisk': round(self.raw_qrisk, 2),
            'risk_level': self.risk_level,
        }

    @property
    def risk_level(self) -> str:
        if self.total_score < 20:
            return 'low'
        elif self.total_score < 50:
            return 'medium'
        elif self.total_score < 80:
            return 'high'
        return 'critical'


class RiskNormalizer:
    """Combines multiple risk signals into a normalised 0-100 score.

    Weights are configurable and must sum to 1.0.
    """

    # Default weights for each signal source
    WEIGHT_AML: float = 0.35
    WEIGHT_GRAPH: float = 0.25
    WEIGHT_COMPLIANCE: float = 0.25
    WEIGHT_QRISK: float = 0.15

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        if weights:
            self.WEIGHT_AML = weights.get('aml', self.WEIGHT_AML)
            self.WEIGHT_GRAPH = weights.get('graph', self.WEIGHT_GRAPH)
            self.WEIGHT_COMPLIANCE = weights.get('compliance', self.WEIGHT_COMPLIANCE)
            self.WEIGHT_QRISK = weights.get('qrisk', self.WEIGHT_QRISK)

    def normalize(self, address: str,
                  aml_score: float = 0.0,
                  graph_score: float = 0.0,
                  compliance_score: float = 0.0,
                  raw_qrisk: float = 0.0) -> RiskBreakdown:
        """Compute weighted risk score.

        All input scores are expected on a 0-100 scale.
        The output is clamped to [0, 100].
        """
        # Clamp inputs
        aml = _clamp(aml_score)
        graph = _clamp(graph_score)
        compliance = _clamp(compliance_score)
        qrisk = _clamp(raw_qrisk)

        total = (
            self.WEIGHT_AML * aml
            + self.WEIGHT_GRAPH * graph
            + self.WEIGHT_COMPLIANCE * compliance
            + self.WEIGHT_QRISK * qrisk
        )
        total = _clamp(total)

        return RiskBreakdown(
            address=address,
            total_score=total,
            aml_score=aml,
            graph_score=graph,
            compliance_score=compliance,
            raw_qrisk=qrisk,
        )

    def normalize_raw_qrisk(self, raw_value: int) -> float:
        """Convert raw QRISK opcode value (uint256 scaled by 10^16) to 0-100.

        The QRISK opcode returns risk as ``score * 10^16``.
        Default low risk is ``10 * 10^16 = 10e16``.
        """
        if raw_value <= 0:
            return 0.0
        score = raw_value / (10 ** 16)
        return _clamp(score)

    def normalize_graph_metrics(self, node_count: int, edge_count: int,
                                 max_hop_reached: int,
                                 suspicious_ratio: float = 0.0) -> float:
        """Convert transaction graph metrics to a 0-100 risk score.

        Higher graph density and more connections at distance = higher risk.
        """
        # Base score from connectivity
        connectivity = min(node_count / 50.0, 1.0) * 30  # max 30 from connectivity
        # Edge density
        density = min(edge_count / 100.0, 1.0) * 20  # max 20 from density
        # Depth penalty (deeper graph = more risk)
        depth = min(max_hop_reached / 6.0, 1.0) * 20  # max 20 from depth
        # Suspicious neighbors
        suspicious = suspicious_ratio * 30  # max 30 from suspicious ratio

        return _clamp(connectivity + density + depth + suspicious)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    """Clamp a value to [low, high]."""
    return max(low, min(value, high))
