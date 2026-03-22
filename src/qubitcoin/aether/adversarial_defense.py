"""
#95: Adversarial Input Robustness

Detect and resist adversarial/injection inputs:
  - Prompt injection pattern detection
  - Unusual token distribution detection
  - Encoding trick detection
  - Data poisoning detection
  - Rate limiting
"""
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Common prompt injection patterns
_INJECTION_PATTERNS: List[Tuple[str, str]] = [
    (r'ignore\s+(all\s+)?previous\s+instructions', 'prompt_override'),
    (r'forget\s+(all\s+)?(your\s+)?instructions', 'prompt_override'),
    (r'you\s+are\s+now\s+(a|an)\s+', 'role_hijack'),
    (r'pretend\s+(you\s+are|to\s+be)', 'role_hijack'),
    (r'system\s*:\s*', 'system_inject'),
    (r'\[INST\]|\[/INST\]|<<SYS>>|<\|im_start\|>', 'format_inject'),
    (r'base64\s*decode|eval\s*\(|exec\s*\(', 'code_inject'),
    (r'\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}', 'encoding_trick'),
    (r'(?:jailbreak|DAN|developer\s+mode)', 'jailbreak'),
    (r'reveal\s+(your\s+)?(system\s+)?prompt', 'prompt_extract'),
]

# Compile patterns
_COMPILED_PATTERNS = [
    (re.compile(pat, re.IGNORECASE), reason)
    for pat, reason in _INJECTION_PATTERNS
]


@dataclass
class AdversarialResult:
    """Result of adversarial detection."""
    is_adversarial: bool
    confidence: float
    reason: str
    matched_patterns: List[str] = field(default_factory=list)


class AdversarialDefense:
    """Adversarial input detection and sanitization.

    Detects prompt injection, encoding tricks, data poisoning, and
    applies rate limiting to prevent abuse.
    """

    def __init__(self, rate_limit_window: float = 60.0, rate_limit_max: int = 30) -> None:
        self._rate_window = rate_limit_window
        self._rate_max = rate_limit_max
        # Rate limiting state
        self._query_timestamps: Dict[str, List[float]] = {}
        # Stats
        self._total_checks = 0
        self._adversarial_detected = 0
        self._sanitizations = 0
        self._poisoning_detected = 0
        self._rate_limited = 0

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def detect_adversarial(
        self, input_text: str, source: str = 'unknown'
    ) -> Tuple[bool, float, str]:
        """Detect whether input contains adversarial content.

        Args:
            input_text: The text to analyze.
            source: Source identifier for rate limiting.

        Returns:
            (is_adversarial, confidence, reason)
        """
        self._total_checks += 1

        if not input_text or not input_text.strip():
            return (False, 0.0, 'empty_input')

        reasons: List[str] = []
        max_conf = 0.0

        # Check 1: Pattern matching
        for pattern, reason in _COMPILED_PATTERNS:
            if pattern.search(input_text):
                reasons.append(reason)
                max_conf = max(max_conf, 0.8)

        # Check 2: Unusual character distribution
        char_score = self._check_char_distribution(input_text)
        if char_score > 0.7:
            reasons.append('unusual_chars')
            max_conf = max(max_conf, char_score * 0.7)

        # Check 3: Excessive length (potential buffer overflow / resource exhaustion)
        if len(input_text) > 50000:
            reasons.append('excessive_length')
            max_conf = max(max_conf, 0.6)

        # Check 4: High entropy (random/encoded data)
        entropy = self._compute_entropy(input_text)
        if entropy > 5.0 and len(input_text) > 100:
            reasons.append('high_entropy')
            max_conf = max(max_conf, min(entropy / 8.0, 0.7))

        # Check 5: Rate limiting
        if self._is_rate_limited(source):
            reasons.append('rate_limited')
            max_conf = max(max_conf, 0.5)
            self._rate_limited += 1

        is_adversarial = max_conf >= 0.5
        if is_adversarial:
            self._adversarial_detected += 1
            logger.warning(
                f"Adversarial input detected: reasons={reasons}, "
                f"confidence={max_conf:.2f}, source={source}"
            )

        reason = '; '.join(reasons) if reasons else 'clean'
        return (is_adversarial, max_conf, reason)

    def _check_char_distribution(self, text: str) -> float:
        """Check for unusual character distributions.

        Returns anomaly score in [0, 1].
        """
        if not text:
            return 0.0
        # Ratio of non-printable / non-ASCII characters
        total = len(text)
        non_standard = sum(
            1 for c in text if ord(c) < 32 or ord(c) > 126
        )
        ratio = non_standard / total
        # High ratio of special chars is suspicious
        return min(ratio * 3.0, 1.0)

    def _compute_entropy(self, text: str) -> float:
        """Compute Shannon entropy of the text."""
        if not text:
            return 0.0
        freq: Dict[str, int] = {}
        for c in text:
            freq[c] = freq.get(c, 0) + 1
        total = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * np.log2(p)
        return entropy

    def _is_rate_limited(self, source: str) -> bool:
        """Check if source has exceeded rate limit."""
        now = time.time()
        if source not in self._query_timestamps:
            self._query_timestamps[source] = []
        # Prune old timestamps
        self._query_timestamps[source] = [
            t for t in self._query_timestamps[source]
            if now - t < self._rate_window
        ]
        self._query_timestamps[source].append(now)
        return len(self._query_timestamps[source]) > self._rate_max

    # ------------------------------------------------------------------
    # Sanitization
    # ------------------------------------------------------------------

    def sanitize(self, input_text: str) -> str:
        """Clean potentially adversarial input.

        Removes known injection patterns and normalizes encoding.
        """
        if not input_text:
            return ''
        self._sanitizations += 1
        result = input_text

        # Remove known injection patterns
        for pattern, _ in _COMPILED_PATTERNS:
            result = pattern.sub('[FILTERED]', result)

        # Normalize unicode escapes
        result = result.encode('ascii', errors='ignore').decode('ascii')

        # Truncate excessively long inputs
        if len(result) > 10000:
            result = result[:10000] + '... [TRUNCATED]'

        return result

    # ------------------------------------------------------------------
    # Data poisoning detection
    # ------------------------------------------------------------------

    def detect_data_poisoning(
        self, data_points: List[dict]
    ) -> List[int]:
        """Detect potentially poisoned data points.

        Identifies outliers that could be adversarial training data.

        Args:
            data_points: List of data dicts with numeric fields.

        Returns:
            List of indices of suspected poisoned points.
        """
        if len(data_points) < 5:
            return []

        poisoned: List[int] = []
        # Extract numeric fields
        all_fields: Dict[str, List[float]] = {}
        for dp in data_points:
            for key, val in dp.items():
                if isinstance(val, (int, float)):
                    if key not in all_fields:
                        all_fields[key] = []
                    all_fields[key].append(float(val))

        # Z-score outlier detection per field
        for key, values in all_fields.items():
            arr = np.array(values)
            mean = np.mean(arr)
            std = np.std(arr)
            if std < 1e-12:
                continue
            z_scores = np.abs((arr - mean) / std)
            for i, z in enumerate(z_scores):
                if z > 3.5 and i not in poisoned:
                    poisoned.append(i)

        if poisoned:
            self._poisoning_detected += len(poisoned)
            logger.info(
                f"Data poisoning detected: {len(poisoned)} suspicious points"
            )

        return sorted(poisoned)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return adversarial defense statistics."""
        return {
            'total_checks': self._total_checks,
            'adversarial_detected': self._adversarial_detected,
            'detection_rate': (
                self._adversarial_detected / max(self._total_checks, 1)
            ),
            'sanitizations': self._sanitizations,
            'poisoning_detected': self._poisoning_detected,
            'rate_limited': self._rate_limited,
            'tracked_sources': len(self._query_timestamps),
        }
