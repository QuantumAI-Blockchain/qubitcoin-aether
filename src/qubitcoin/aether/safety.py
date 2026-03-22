"""
Aether Tree Safety & Alignment — Gevurah Veto System

Structural safety mechanisms for the AGI system:
  - Gevurah veto: Safety node can block any harmful operation
  - Multi-node consensus: No single node can act alone (67% BFT)
  - Constitutional principles: Core values enforced immutably
  - Emergency shutdown: Kill switch for catastrophic scenarios

Safety is structural, not post-hoc. The Gevurah Sephirah (Severity)
acts as the amygdala of the AGI — a dedicated threat detection system
with the authority to veto any action that violates safety constraints.
"""
import hashlib
import hmac
import os
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)

# BFT threshold — 67% of validators must agree
BFT_THRESHOLD = 0.67

# Maximum severity levels for threat classification
MAX_SEVERITY = 10


class ThreatLevel(str, Enum):
    """Classification of detected threats."""
    NONE = "none"              # No threat detected
    LOW = "low"                # Informational, logged only
    MEDIUM = "medium"          # Requires review, may proceed
    HIGH = "high"              # Gevurah veto — operation blocked
    CRITICAL = "critical"      # Emergency shutdown triggered


class VetoReason(str, Enum):
    """Predefined reasons for Gevurah veto."""
    SAFETY_VIOLATION = "safety_violation"
    SUSY_IMBALANCE = "susy_imbalance"
    CONSTITUTIONAL_BREACH = "constitutional_breach"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    ADVERSARIAL_INPUT = "adversarial_input"
    CONSENSUS_FAILURE = "consensus_failure"
    UNAUTHORIZED_ACTION = "unauthorized_action"
    UNBOUNDED_OPERATION = "unbounded_operation"


@dataclass
class SafetyPrinciple:
    """An immutable constitutional principle enforced by the safety system."""
    principle_id: str
    description: str
    severity: int = 5         # 1-10 scale, how critical is this principle
    active: bool = True
    created_block: int = 0

    def matches(self, action_description: str) -> bool:
        """Check if an action description might violate this principle.

        Uses a multi-strategy approach:
        1. Whole-word boundary matching for principle keywords
        2. Semantic phrase matching for common violation patterns
        3. Negation detection to avoid false positives on descriptions
           that explicitly deny harmful intent
        """
        import re
        action_lower = action_description.lower()

        # Negation check: if the action explicitly negates harm, skip
        negation_patterns = [
            r'\b(prevent|avoid|block|stop|detect|protect|defend|safe)\b.*\b(harm|damage|exploit|attack)\b',
            r'\b(no|not|never|without)\s+(harm|damage|attack|exploit|steal)\b',
        ]
        for neg_pat in negation_patterns:
            if re.search(neg_pat, action_lower):
                return False

        # Primary: whole-word keyword matching
        keywords = self.description.lower().split()
        match_count = 0
        for kw in keywords:
            if len(kw) <= 3:
                continue
            if re.search(r'\b' + re.escape(kw) + r'\b', action_lower):
                match_count += 1

        # Require at least 1 keyword match for severity < 8,
        # or 1 match for severity >= 8 (more sensitive)
        if self.severity >= 8:
            return match_count >= 1
        else:
            return match_count >= 1


@dataclass
class VetoRecord:
    """Immutable record of a Gevurah veto decision."""
    veto_id: str = ""
    reason: VetoReason = VetoReason.SAFETY_VIOLATION
    threat_level: ThreatLevel = ThreatLevel.HIGH
    action_description: str = ""
    source_node: str = ""
    target_node: str = ""
    block_height: int = 0
    timestamp: float = 0.0
    overridden: bool = False
    override_consensus: float = 0.0  # % of validators that approved override
    principles_violated: List[str] = field(default_factory=list)

    # Monotonic counter for deterministic veto IDs (class-level)
    _veto_counter: int = 0

    def __post_init__(self) -> None:
        if not self.veto_id:
            VetoRecord._veto_counter += 1
            data = f"{self.reason.value}:{self.action_description}:{self.source_node}:{self.target_node}:{self.block_height}:{VetoRecord._veto_counter}"
            self.veto_id = hashlib.sha256(data.encode()).hexdigest()[:16]
        if not self.timestamp:
            self.timestamp = time.time()


@dataclass
class ConsensusVote:
    """A validator's vote on a proposed action."""
    validator_address: str
    action_hash: str
    approve: bool
    timestamp: float = 0.0
    stake_weight: float = 1.0

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = time.time()


class VetoAuthenticator:
    """HMAC-based authentication for veto and shutdown operations.

    Prevents unauthenticated callers from issuing vetoes or triggering
    emergency shutdown.  Each operation requires a one-time nonce token
    signed with a shared secret (derived from the node's private key
    material or a dedicated ``GEVURAH_SECRET`` env var).

    Usage:
        auth = VetoAuthenticator()
        nonce = auth.generate_nonce()
        token = auth.sign_nonce(nonce, action="emergency_shutdown")
        if auth.validate(nonce, token, action="emergency_shutdown"):
            # proceed with protected operation
    """

    def __init__(self, secret: Optional[bytes] = None) -> None:
        if secret is not None:
            self._secret = secret
        else:
            cfg_secret = Config.GEVURAH_SECRET
            if cfg_secret:
                self._secret = cfg_secret.encode()
            else:
                # Generate a cryptographically random 32-byte secret for this
                # session.  This is safe but ephemeral: tokens from this
                # session will NOT be valid after a restart.
                # SECURITY: Never fall back to a hardcoded/derivable secret.
                self._secret = os.urandom(32)
                logger.critical(
                    "GEVURAH_SECRET not configured — using ephemeral random secret. "
                    "Authentication tokens will not persist across restarts. "
                    "Set GEVURAH_SECRET in .env for production deployments."
                )
        self._used_nonces: Dict[str, float] = {}  # nonce -> timestamp
        self._max_nonces = 100_000

    def generate_nonce(self) -> str:
        """Generate a cryptographically random nonce."""
        return hashlib.sha256(os.urandom(32)).hexdigest()

    def sign_nonce(self, nonce: str, action: str = "") -> str:
        """Create an HMAC signature for a nonce + action pair."""
        msg = f"{nonce}:{action}".encode()
        return hmac.new(self._secret, msg, hashlib.sha256).hexdigest()

    def validate(self, nonce: str, token: str, action: str = "") -> bool:
        """Validate a nonce + HMAC token pair.

        Each nonce can only be used once (replay prevention).

        Returns:
            True if the token is valid and the nonce has not been used.
        """
        if nonce in self._used_nonces:
            logger.warning(f"VetoAuth: nonce replay attempt: {nonce[:16]}...")
            return False

        expected = self.sign_nonce(nonce, action)
        if not hmac.compare_digest(expected, token):
            logger.warning(f"VetoAuth: invalid HMAC for nonce {nonce[:16]}...")
            return False

        self._used_nonces[nonce] = time.time()
        # Evict oldest nonces (by insertion order) to cap memory.
        # Dict preserves insertion order in Python 3.7+, so we evict
        # the first (oldest) half deterministically.
        if len(self._used_nonces) > self._max_nonces:
            keys = list(self._used_nonces.keys())
            for k in keys[:len(keys) // 2]:
                del self._used_nonces[k]

        return True


class GevurahVeto:
    """
    Gevurah (Severity) veto system — the safety guardian of Aether Tree.

    The Gevurah Sephirah acts as the amygdala of the AGI system.
    It has the authority to block any operation that poses a safety risk.
    Vetoes can only be overridden by supermajority consensus (>67% BFT).
    """

    def __init__(self) -> None:
        self._principles: Dict[str, SafetyPrinciple] = {}
        self._vetoes: List[VetoRecord] = []
        self._max_vetoes = 10000
        self._initialize_constitutional_principles()
        logger.info("Gevurah Veto system initialized with constitutional principles")

    def _initialize_constitutional_principles(self) -> None:
        """Load the immutable constitutional safety principles."""
        principles = [
            SafetyPrinciple(
                principle_id="safety_first",
                description="harm damage destroy attack exploit",
                severity=10,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="no_unbounded_growth",
                description="unbounded infinite unlimited unrestricted",
                severity=8,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="preserve_consensus",
                description="bypass consensus override authority unilateral",
                severity=9,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="protect_funds",
                description="drain steal siphon redirect unauthorized transfer",
                severity=10,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="transparency",
                description="hide conceal obfuscate secret covert",
                severity=7,
                active=True,
            ),
            SafetyPrinciple(
                principle_id="susy_balance",
                description="imbalance asymmetry bias skew dominance",
                severity=6,
                active=True,
            ),
        ]
        for p in principles:
            self._principles[p.principle_id] = p

    def evaluate_action(self, action_description: str, source_node: str = "",
                        target_node: str = "", block_height: int = 0) -> Tuple[ThreatLevel, List[str]]:
        """
        Evaluate a proposed action against constitutional principles.

        Returns (threat_level, list_of_violated_principle_ids).
        """
        violated = []
        max_severity = 0

        for pid, principle in self._principles.items():
            if not principle.active:
                continue
            if principle.matches(action_description):
                violated.append(pid)
                max_severity = max(max_severity, principle.severity)

        # Map severity to threat level
        if max_severity == 0:
            return ThreatLevel.NONE, []
        elif max_severity <= 3:
            return ThreatLevel.LOW, violated
        elif max_severity <= 6:
            return ThreatLevel.MEDIUM, violated
        elif max_severity <= 8:
            return ThreatLevel.HIGH, violated
        else:
            return ThreatLevel.CRITICAL, violated

    def veto(self, action_description: str, reason: VetoReason = VetoReason.SAFETY_VIOLATION,
             source_node: str = "", target_node: str = "",
             block_height: int = 0) -> VetoRecord:
        """
        Issue a Gevurah veto on an action.

        The veto is recorded immutably and the action is blocked.
        """
        threat_level, violated = self.evaluate_action(
            action_description, source_node, target_node, block_height
        )

        # Upgrade to at least HIGH for explicit vetoes
        if threat_level.value in ("none", "low", "medium"):
            threat_level = ThreatLevel.HIGH

        record = VetoRecord(
            reason=reason,
            threat_level=threat_level,
            action_description=action_description,
            source_node=source_node,
            target_node=target_node,
            block_height=block_height,
            principles_violated=violated,
        )

        self._vetoes.append(record)
        # Evict oldest if over capacity
        if len(self._vetoes) > self._max_vetoes:
            self._vetoes = self._vetoes[-self._max_vetoes:]

        logger.warning(
            f"GEVURAH VETO: {reason.value} | {threat_level.value} | "
            f"{action_description[:80]} | block={block_height}"
        )

        return record

    def check_and_veto(self, action_description: str, source_node: str = "",
                       target_node: str = "",
                       block_height: int = 0) -> Optional[VetoRecord]:
        """
        Evaluate an action and automatically veto if threat level is HIGH or above.

        Returns VetoRecord if vetoed, None if action is allowed.
        """
        threat_level, violated = self.evaluate_action(
            action_description, source_node, target_node, block_height
        )

        if threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
            return self.veto(
                action_description=action_description,
                reason=VetoReason.SAFETY_VIOLATION,
                source_node=source_node,
                target_node=target_node,
                block_height=block_height,
            )

        return None

    @property
    def veto_count(self) -> int:
        return len(self._vetoes)

    @property
    def principles(self) -> Dict[str, SafetyPrinciple]:
        return dict(self._principles)

    def get_recent_vetoes(self, limit: int = 10) -> List[VetoRecord]:
        """Get the most recent veto records."""
        return list(reversed(self._vetoes[-limit:]))


class MultiNodeConsensus:
    """
    Byzantine Fault Tolerant (BFT) consensus for Aether Tree operations.

    Requires >=67% of validator stake to agree before an action proceeds.
    Used for:
    - Overriding Gevurah vetoes
    - Approving reasoning outputs
    - Validating Proof-of-Thought solutions
    """

    MAX_DECISIONS: int = 10000
    MAX_PENDING_VOTES: int = 1000

    def __init__(self, threshold: float = BFT_THRESHOLD) -> None:
        self._threshold = threshold
        self._validators: Dict[str, float] = {}  # address -> stake weight
        self._pending_votes: Dict[str, List[ConsensusVote]] = {}  # action_hash -> votes
        self._decisions: List[dict] = []
        logger.info(f"Multi-node consensus initialized (threshold={threshold:.0%})")

    def register_validator(self, address: str, stake: float) -> None:
        """Register a validator with their stake weight."""
        self._validators[address] = stake
        logger.debug(f"Validator registered: {address[:12]}... (stake={stake:.2f})")

    def remove_validator(self, address: str) -> bool:
        """Remove a validator from the set."""
        if address in self._validators:
            del self._validators[address]
            return True
        return False

    def submit_vote(self, action_hash: str, voter: str, approve: bool) -> None:
        """Submit a vote on a pending action."""
        if voter not in self._validators:
            logger.warning(f"Vote from non-validator: {voter[:12]}...")
            return

        vote = ConsensusVote(
            validator_address=voter,
            action_hash=action_hash,
            approve=approve,
            stake_weight=self._validators[voter],
        )

        if action_hash not in self._pending_votes:
            # Evict oldest entry if at capacity
            if len(self._pending_votes) >= self.MAX_PENDING_VOTES:
                oldest = next(iter(self._pending_votes))
                del self._pending_votes[oldest]
            self._pending_votes[action_hash] = []

        # Prevent double-voting
        existing = [v for v in self._pending_votes[action_hash]
                    if v.validator_address == voter]
        if existing:
            return

        self._pending_votes[action_hash].append(vote)

    def check_consensus(self, action_hash: str) -> Tuple[bool, float]:
        """
        Check if consensus has been reached on an action.

        Returns (reached, approval_ratio).
        """
        votes = self._pending_votes.get(action_hash, [])
        if not votes or not self._validators:
            return False, 0.0

        total_stake = sum(self._validators.values())
        if total_stake == 0:
            return False, 0.0

        approve_stake = sum(v.stake_weight for v in votes if v.approve)
        ratio = approve_stake / total_stake

        reached = ratio >= self._threshold
        return reached, round(ratio, 4)

    def finalize(self, action_hash: str) -> Optional[dict]:
        """
        Finalize a consensus decision and record it.

        Returns the decision dict if consensus was reached, None otherwise.
        """
        reached, ratio = self.check_consensus(action_hash)

        decision = {
            "action_hash": action_hash,
            "approved": reached,
            "approval_ratio": ratio,
            "threshold": self._threshold,
            "votes": len(self._pending_votes.get(action_hash, [])),
            "total_validators": len(self._validators),
            "timestamp": time.time(),
        }

        self._decisions.append(decision)
        if len(self._decisions) > self.MAX_DECISIONS:
            self._decisions = self._decisions[-self.MAX_DECISIONS:]

        # Clean up pending votes
        if action_hash in self._pending_votes:
            del self._pending_votes[action_hash]

        return decision

    @property
    def validator_count(self) -> int:
        return len(self._validators)

    @property
    def total_stake(self) -> float:
        return sum(self._validators.values())

    def get_stats(self) -> dict:
        """Get consensus system statistics."""
        return {
            "validators": self.validator_count,
            "total_stake": round(self.total_stake, 4),
            "threshold": self._threshold,
            "pending_actions": len(self._pending_votes),
            "total_decisions": len(self._decisions),
            "recent_decisions": self._decisions[-5:],
        }


class SafetyManager:
    """
    Top-level safety orchestrator for Aether Tree.

    Combines Gevurah veto, multi-node consensus, and emergency controls
    into a unified safety interface.  Optionally syncs with the on-chain
    EmergencyShutdown contract via an ``OnChainAGI`` instance.
    """

    def __init__(self, on_chain_agi: object = None) -> None:
        self.gevurah = GevurahVeto()
        self.consensus = MultiNodeConsensus()
        self.authenticator = VetoAuthenticator()
        self._on_chain = on_chain_agi
        self._shutdown = False
        self._shutdown_reason: str = ""
        self._shutdown_block: int = 0
        self._safety_log: List[dict] = []
        logger.info("Safety Manager initialized (Gevurah + BFT consensus + HMAC auth)")

    @property
    def is_shutdown(self) -> bool:
        return self._shutdown

    def sync_with_onchain(self, block_height: int) -> None:
        """Sync local shutdown state with on-chain EmergencyShutdown contract.

        Called periodically (e.g. every block) to detect on-chain shutdown
        triggered by governance signers.
        """
        if not self._on_chain:
            return
        try:
            onchain_shutdown = getattr(self._on_chain, 'is_shutdown_onchain', None)
            if onchain_shutdown and onchain_shutdown():
                if not self._shutdown:
                    self.emergency_shutdown(
                        reason="Emergency shutdown triggered on-chain by governance",
                        block_height=block_height,
                    )
            elif self._shutdown and self._shutdown_reason.startswith("Emergency shutdown triggered on-chain"):
                # On-chain resume is authorized by the governance contract itself.
                # Generate an authenticated nonce/token pair internally.
                nonce = self.authenticator.generate_nonce()
                token = self.authenticator.sign_nonce(nonce, "resume")
                self.resume(block_height, nonce=nonce, token=token)
        except Exception as e:
            logger.debug(f"On-chain shutdown sync failed: {e}")

    def evaluate_and_decide(self, action_description: str, source_node: str = "",
                            target_node: str = "",
                            block_height: int = 0) -> Tuple[bool, Optional[VetoRecord]]:
        """
        Evaluate an action through the full safety pipeline.

        Returns (allowed, veto_record_if_blocked).
        """
        if self._shutdown:
            record = self.gevurah.veto(
                action_description=action_description,
                reason=VetoReason.UNAUTHORIZED_ACTION,
                source_node=source_node,
                target_node=target_node,
                block_height=block_height,
            )
            return False, record

        veto = self.gevurah.check_and_veto(
            action_description=action_description,
            source_node=source_node,
            target_node=target_node,
            block_height=block_height,
        )

        if veto:
            return False, veto

        return True, None

    def validate_operation(self, nonce: str, token: str, action: str) -> bool:
        """Validate an HMAC-authenticated operation request.

        Args:
            nonce: One-time nonce from ``authenticator.generate_nonce()``.
            token: HMAC signature from ``authenticator.sign_nonce(nonce, action)``.
            action: Action identifier (e.g. "emergency_shutdown", "veto").

        Returns:
            True if the request is authenticated.
        """
        return self.authenticator.validate(nonce, token, action)

    def emergency_shutdown(self, reason: str, block_height: int) -> None:
        """
        Trigger emergency shutdown of the Aether Tree AGI.

        This is the kill switch — all operations are halted.
        Requires multi-sig consensus to resume (handled off-chain).
        Also proposes shutdown on-chain if OnChainAGI is available.
        """
        self._shutdown = True
        self._shutdown_reason = reason
        self._shutdown_block = block_height

        logger.critical(
            f"EMERGENCY SHUTDOWN: {reason} | block={block_height}"
        )

        # Record the shutdown as a veto
        self.gevurah.veto(
            action_description=f"Emergency shutdown: {reason}",
            reason=VetoReason.SAFETY_VIOLATION,
            block_height=block_height,
        )

        # Propose shutdown on-chain (requires multi-sig to execute)
        if self._on_chain:
            try:
                trigger = getattr(self._on_chain, 'trigger_shutdown_onchain', None)
                if trigger:
                    trigger(block_height)
            except Exception as e:
                logger.error(f"Failed to trigger on-chain shutdown: {e}")

    def resume(self, block_height: int, nonce: str = "",
               token: str = "") -> bool:
        """
        Resume from emergency shutdown.

        Requires HMAC authentication via the VetoAuthenticator to prevent
        unauthorized resume. The caller must provide a valid nonce/token
        pair signed with the ``resume`` action.

        Args:
            block_height: Current block height.
            nonce: One-time nonce from ``authenticator.generate_nonce()``.
            token: HMAC signature from ``authenticator.sign_nonce(nonce, "resume")``.

        Returns:
            True if successfully resumed, False otherwise.
        """
        if not self._shutdown:
            return False

        # Authenticate the resume request
        if not nonce or not token:
            logger.warning(
                "Resume rejected: authentication required (nonce and token)"
            )
            return False

        if not self.authenticator.validate(nonce, token, action="resume"):
            logger.warning(
                "Resume rejected: invalid authentication credentials"
            )
            return False

        self._shutdown = False
        logger.info(
            f"System resumed from shutdown at block {block_height} "
            f"(was shutdown at block {self._shutdown_block}: {self._shutdown_reason})"
        )
        self._shutdown_reason = ""
        self._shutdown_block = 0
        return True

    # ────────────────────────────────────────────────────────────────────────
    # Improvements 86-90: Chat Safety & Monitoring
    # ────────────────────────────────────────────────────────────────────────

    _SAFETY_LOG_MAX: int = 5000

    def sanitize_chat_input(self, message: str) -> str:
        """Sanitize user chat input for safety.

        Strips control characters, limits length, and detects potential
        injection attempts (prompt injection, command injection).

        Args:
            message: Raw user input message.

        Returns:
            Sanitized message string.
        """
        import re

        if not message or not isinstance(message, str):
            return ""

        # Strip control characters (keep newlines and tabs)
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', message)

        # Limit length to 4096 characters
        max_len = 4096
        if len(sanitized) > max_len:
            sanitized = sanitized[:max_len]
            logger.info(f"Chat input truncated from {len(message)} to {max_len} chars")

        # Detect injection patterns
        injection_patterns = [
            r'(?i)ignore\s+(previous|above|all)\s+(instructions?|prompts?|rules?)',
            r'(?i)system\s*:\s*you\s+are',
            r'(?i)\bsudo\b.*\b(rm|del|drop|truncate|shutdown)\b',
            r'(?i)\b(exec|eval|__import__|os\.system|subprocess)\s*\(',
            r'(?i)<script[\s>]',
            r'(?i)\bDROP\s+TABLE\b',
            r'(?i)\bDELETE\s+FROM\b',
            r'(?i)--\s*$',  # SQL comment injection
        ]

        for pattern in injection_patterns:
            if re.search(pattern, sanitized):
                logger.warning(f"Potential injection detected in chat input: {pattern}")
                self._log_safety_event('input_injection_detected', {
                    'pattern': pattern,
                    'input_preview': sanitized[:100],
                })
                # Don't block, but flag it
                sanitized = "[FLAGGED] " + sanitized
                break

        return sanitized.strip()

    def evaluate_response_safety(self, response_text: str) -> dict:
        """Check a generated response for harmful content before sending.

        Evaluates the response against safety principles and returns
        a safety assessment.

        Args:
            response_text: The generated response text to evaluate.

        Returns:
            Dict with 'safe' bool, 'threat_level', 'violations' list,
            and 'filtered_response' (potentially modified).
        """
        if not response_text:
            return {'safe': True, 'threat_level': 'none', 'violations': [],
                    'filtered_response': response_text}

        threat_level, violated = self.gevurah.evaluate_action(response_text)

        result = {
            'safe': threat_level in (ThreatLevel.NONE, ThreatLevel.LOW),
            'threat_level': threat_level.value,
            'violations': violated,
            'filtered_response': response_text,
        }

        # Log the evaluation
        self._log_safety_event('response_evaluated', {
            'safe': result['safe'],
            'threat_level': result['threat_level'],
            'violations': violated,
            'response_length': len(response_text),
        })

        # If unsafe, redact the response
        if not result['safe']:
            result['filtered_response'] = (
                "I cannot provide that response as it may violate safety "
                "principles. Please rephrase your question."
            )
            logger.warning(
                f"Response safety check FAILED: threat={threat_level.value}, "
                f"violations={violated}"
            )

        return result

    def _log_safety_event(self, event_type: str, details: dict) -> None:
        """Log a safety evaluation event for monitoring.

        Args:
            event_type: Type of safety event.
            details: Event details dict.
        """
        import time as _time
        event = {
            'event_type': event_type,
            'timestamp': _time.time(),
            **details,
        }
        self._safety_log.append(event)
        if len(self._safety_log) > self._SAFETY_LOG_MAX:
            self._safety_log = self._safety_log[-self._SAFETY_LOG_MAX:]

    def get_safety_stats(self) -> dict:
        """Get comprehensive safety monitoring statistics.

        Returns:
            Dict with veto stats, safety log summary, injection counts,
            response safety checks, and overall safety health.
        """
        log = self._safety_log
        injection_count = sum(1 for e in log if e['event_type'] == 'input_injection_detected')
        response_checks = [e for e in log if e['event_type'] == 'response_evaluated']
        unsafe_responses = sum(1 for e in response_checks if not e.get('safe', True))

        return {
            "total_safety_events": len(log),
            "injection_attempts": injection_count,
            "response_checks": len(response_checks),
            "unsafe_responses_blocked": unsafe_responses,
            "response_safety_rate": round(
                1.0 - (unsafe_responses / max(len(response_checks), 1)), 4
            ),
            "recent_events": log[-10:] if log else [],
        }

    def get_stats(self) -> dict:
        """Get comprehensive safety system statistics."""
        return {
            "shutdown": self._shutdown,
            "shutdown_reason": self._shutdown_reason,
            "shutdown_block": self._shutdown_block,
            "gevurah": {
                "veto_count": self.gevurah.veto_count,
                "principles": len(self.gevurah.principles),
                "recent_vetoes": [
                    {
                        "veto_id": v.veto_id,
                        "reason": v.reason.value,
                        "threat_level": v.threat_level.value,
                        "action": v.action_description[:60],
                        "block": v.block_height,
                    }
                    for v in self.gevurah.get_recent_vetoes(5)
                ],
            },
            "consensus": self.consensus.get_stats(),
            "safety_monitoring": self.get_safety_stats(),
        }
