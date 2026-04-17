"""
#70: Self-Evaluation Against Ground Truth

Tests AI predictions against known answers.  Generates self-test
questions from the knowledge graph and tracks accuracy trends.

Numpy-only implementation (no PyTorch).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TestQuestion:
    """A self-generated test question."""
    question: str
    expected_answer: str
    domain: str
    difficulty: str  # easy, medium, hard
    node_ids: List[str] = field(default_factory=list)
    question_id: str = ''

    def __post_init__(self) -> None:
        if not self.question_id:
            h = hashlib.sha256(self.question.encode()[:200]).hexdigest()[:10]
            self.question_id = f"tq_{h}"


@dataclass
class EvalReport:
    """Evaluation report comparing predictions against ground truth."""
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    calibration_error: float = 0.0
    per_domain_scores: Dict[str, float] = field(default_factory=dict)
    total_evaluated: int = 0
    timestamp: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class SelfEvaluator:
    """Test AI predictions against ground truth and track accuracy."""

    def __init__(self, history_cap: int = 200) -> None:
        self._history_cap = history_cap
        self._reports: List[EvalReport] = []
        self._accuracy_history: List[float] = []
        self._total_evaluations: int = 0
        self._total_questions_generated: int = 0

        logger.info("SelfEvaluator initialized")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        predictions: List[dict],
        ground_truth: List[dict],
    ) -> EvalReport:
        """Evaluate predictions against ground truth.

        Each dict should have:
            - 'answer': str or float
            - 'domain': str (optional)
            - 'confidence': float (optional, for calibration)
        """
        n = min(len(predictions), len(ground_truth))
        if n == 0:
            return EvalReport()

        correct = 0
        tp = 0
        fp = 0
        fn = 0
        domain_correct: Dict[str, int] = {}
        domain_total: Dict[str, int] = {}
        confidences: List[float] = []
        outcomes: List[float] = []

        for i in range(n):
            pred = predictions[i]
            truth = ground_truth[i]
            pred_ans = str(pred.get('answer', '')).strip().lower()
            true_ans = str(truth.get('answer', '')).strip().lower()
            domain = truth.get('domain', pred.get('domain', 'general'))

            is_correct = self._match(pred_ans, true_ans)
            if is_correct:
                correct += 1
                tp += 1
            else:
                fp += 1
                fn += 1

            domain_total[domain] = domain_total.get(domain, 0) + 1
            if is_correct:
                domain_correct[domain] = domain_correct.get(domain, 0) + 1

            # For calibration
            conf = float(pred.get('confidence', 0.5))
            confidences.append(conf)
            outcomes.append(1.0 if is_correct else 0.0)

        accuracy = correct / n
        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)

        # Expected Calibration Error (ECE)
        cal_error = self._compute_ece(
            np.array(confidences), np.array(outcomes), n_bins=10,
        )

        per_domain = {
            d: domain_correct.get(d, 0) / max(domain_total[d], 1)
            for d in domain_total
        }

        report = EvalReport(
            accuracy=round(accuracy, 4),
            precision=round(precision, 4),
            recall=round(recall, 4),
            f1=round(f1, 4),
            calibration_error=round(cal_error, 4),
            per_domain_scores=per_domain,
            total_evaluated=n,
        )

        self._reports.append(report)
        if len(self._reports) > self._history_cap:
            self._reports = self._reports[-self._history_cap:]

        self._accuracy_history.append(accuracy)
        if len(self._accuracy_history) > self._history_cap:
            self._accuracy_history = self._accuracy_history[-self._history_cap:]

        self._total_evaluations += n
        return report

    def generate_test_questions(self, kg: Any, max_questions: int = 20) -> List[TestQuestion]:
        """Generate self-test questions from the knowledge graph.

        Difficulty levels:
            - easy: direct lookup (node content)
            - medium: 1-hop (follow one edge)
            - hard: multi-hop (2+ edges)
        """
        if not kg or not hasattr(kg, 'nodes'):
            return []

        questions: List[TestQuestion] = []
        nodes_list = list(kg.nodes.values())[:500]

        # Easy: direct lookup questions
        for node in nodes_list[:max_questions // 3]:
            content = getattr(node, 'content', {})
            if isinstance(content, dict) and content.get('type'):
                q = f"What type is the knowledge node at block {content.get('height', '?')}?"
                a = str(content['type'])
                questions.append(TestQuestion(
                    question=q,
                    expected_answer=a,
                    domain=content.get('domain', 'general'),
                    difficulty='easy',
                    node_ids=[getattr(node, 'node_id', '')],
                ))

        # Medium: 1-hop questions
        if hasattr(kg, 'edges'):
            edge_list = list(kg.edges.values())[:200]
            for edge in edge_list[:max_questions // 3]:
                src_id = getattr(edge, 'source_id', '') if not isinstance(edge, dict) else edge.get('source_id', '')
                tgt_id = getattr(edge, 'target_id', '') if not isinstance(edge, dict) else edge.get('target_id', '')
                rel = getattr(edge, 'relation', '') if not isinstance(edge, dict) else edge.get('relation', '')
                if src_id and tgt_id and rel:
                    q = f"What node is connected to {src_id[:12]} via '{rel}'?"
                    questions.append(TestQuestion(
                        question=q,
                        expected_answer=tgt_id[:20],
                        domain='graph',
                        difficulty='medium',
                        node_ids=[src_id, tgt_id],
                    ))
                if len(questions) >= max_questions:
                    break

        # Hard: multi-hop (2+ edges)
        if hasattr(kg, 'edges') and hasattr(kg, 'adjacency'):
            adj = getattr(kg, 'adjacency', {})
            for src, targets in list(adj.items())[:50]:
                if len(targets) >= 2:
                    first_hop = list(targets.keys())[0] if isinstance(targets, dict) else targets[0]
                    second_targets = adj.get(first_hop, {})
                    if second_targets:
                        second_hop = list(second_targets.keys())[0] if isinstance(second_targets, dict) else second_targets[0] if isinstance(second_targets, list) and second_targets else None
                        if second_hop:
                            q = f"What is 2 hops from {str(src)[:12]} via {str(first_hop)[:12]}?"
                            questions.append(TestQuestion(
                                question=q,
                                expected_answer=str(second_hop)[:20],
                                domain='graph',
                                difficulty='hard',
                                node_ids=[str(src), str(first_hop), str(second_hop)],
                            ))
                if len(questions) >= max_questions:
                    break

        self._total_questions_generated += len(questions)
        return questions[:max_questions]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _match(self, pred: str, truth: str) -> bool:
        """Fuzzy match: exact match or substring containment."""
        if pred == truth:
            return True
        if len(truth) > 3 and truth in pred:
            return True
        if len(pred) > 3 and pred in truth:
            return True
        return False

    def _compute_ece(
        self, confidences: np.ndarray, outcomes: np.ndarray, n_bins: int = 10,
    ) -> float:
        """Expected Calibration Error."""
        if len(confidences) == 0:
            return 0.0
        bin_boundaries = np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        for i in range(n_bins):
            mask = (confidences >= bin_boundaries[i]) & (confidences < bin_boundaries[i + 1])
            if mask.sum() == 0:
                continue
            bin_conf = confidences[mask].mean()
            bin_acc = outcomes[mask].mean()
            ece += mask.sum() / len(confidences) * abs(bin_acc - bin_conf)
        return float(ece)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        recent_acc = (
            float(np.mean(self._accuracy_history[-20:]))
            if self._accuracy_history else 0.0
        )
        return {
            'total_evaluations': self._total_evaluations,
            'total_questions_generated': self._total_questions_generated,
            'reports_stored': len(self._reports),
            'recent_accuracy': round(recent_acc, 4),
            'accuracy_trend_len': len(self._accuracy_history),
        }
