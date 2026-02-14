"""
QVM Compliance Engine — Programmable Compliance Policies (PCP)

Provides a registry of compliance policies that the QCOMPLIANCE opcode
and RPC endpoints can query.  Policies define per-address KYC level,
AML monitoring, sanctions screening, and daily transaction limits.

Architecture:
    CompliancePolicy   — dataclass representing a single policy rule
    SanctionsList      — OFAC / UN / EU sanctions list manager
    ComplianceEngine   — in-memory + DB-backed policy registry
"""
import hashlib
import time
from dataclasses import dataclass, field, asdict
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Set

from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── KYC Levels ────────────────────────────────────────────────────────
class KYCLevel(IntEnum):
    """KYC verification tiers (per CLAUDE.md §7.6)."""
    NONE = 0
    BASIC = 1       # Email + phone
    ENHANCED = 2    # Government ID
    FULL = 3        # Full institutional due-diligence


# ── AML Status ────────────────────────────────────────────────────────
class AMLStatus(IntEnum):
    CLEAR = 0
    MONITORING = 1
    FLAGGED = 2
    BLOCKED = 3


# ── Compliance-as-a-Service tiers ─────────────────────────────────────
class ComplianceTier(IntEnum):
    RETAIL = 0          # Free, $10K/day
    PROFESSIONAL = 1    # $500/mo, $1M/day
    INSTITUTIONAL = 2   # $5K/mo, unlimited
    SOVEREIGN = 3       # $50K/mo, custom


TIER_DAILY_LIMITS: Dict[int, float] = {
    ComplianceTier.RETAIL: 10_000.0,
    ComplianceTier.PROFESSIONAL: 1_000_000.0,
    ComplianceTier.INSTITUTIONAL: float('inf'),
    ComplianceTier.SOVEREIGN: float('inf'),
}


# ── Policy dataclass ──────────────────────────────────────────────────
@dataclass
class CompliancePolicy:
    """A single compliance policy applied to an address or address group."""
    policy_id: str
    address: str                           # Target address (or '*' for global)
    kyc_level: int = KYCLevel.BASIC
    aml_status: int = AMLStatus.CLEAR
    sanctions_checked: bool = False
    daily_limit: float = 10_000.0          # QBC per day
    is_blocked: bool = False
    tier: int = ComplianceTier.RETAIL
    jurisdiction: str = ''
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


# ── Circuit breaker ───────────────────────────────────────────────────
@dataclass
class CircuitBreaker:
    """Auto-circuit breaker that halts operations above a risk threshold."""
    threshold: float = 80.0     # Risk score 0-100
    is_tripped: bool = False
    tripped_at: Optional[float] = None
    cooldown_seconds: float = 300.0   # 5 minutes

    def check(self, risk_score: float) -> bool:
        """Return True if operations should be halted."""
        if risk_score >= self.threshold:
            self.is_tripped = True
            self.tripped_at = time.time()
            logger.warning(
                f"Circuit breaker TRIPPED: risk={risk_score:.1f} >= threshold={self.threshold}"
            )
            return True
        # Auto-reset after cooldown
        if self.is_tripped and self.tripped_at:
            elapsed = time.time() - self.tripped_at
            if elapsed >= self.cooldown_seconds:
                self.is_tripped = False
                self.tripped_at = None
                logger.info("Circuit breaker RESET after cooldown")
        return self.is_tripped

    def reset(self) -> None:
        self.is_tripped = False
        self.tripped_at = None

    def to_dict(self) -> dict:
        return {
            'threshold': self.threshold,
            'is_tripped': self.is_tripped,
            'tripped_at': self.tripped_at,
            'cooldown_seconds': self.cooldown_seconds,
        }


# ── Sanctions List Sources ────────────────────────────────────────────
class SanctionsSource(Enum):
    """Supported sanctions list sources."""
    OFAC = "ofac"       # US Treasury OFAC SDN list
    UN = "un"           # United Nations Security Council
    EU = "eu"           # European Union consolidated list


@dataclass
class SanctionsEntry:
    """A single entry on a sanctions list."""
    address: str
    source: SanctionsSource
    reason: str = ""
    added_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "source": self.source.value,
            "reason": self.reason,
            "added_at": self.added_at,
        }


class SanctionsList:
    """
    Manages OFAC, UN, and EU sanctions lists for address screening.

    Addresses on any sanctions list are automatically blocked from
    transacting on the QBC chain via the compliance engine.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, SanctionsEntry] = {}  # address → entry
        self._by_source: Dict[SanctionsSource, Set[str]] = {
            s: set() for s in SanctionsSource
        }

    def add_address(
        self,
        address: str,
        source: SanctionsSource,
        reason: str = "",
    ) -> SanctionsEntry:
        """Add an address to a sanctions list."""
        addr = address.lower()
        entry = SanctionsEntry(address=addr, source=source, reason=reason)
        self._entries[addr] = entry
        self._by_source[source].add(addr)
        logger.info(
            f"Sanctions: added {addr[:16]}… to {source.value} list"
        )
        return entry

    def remove_address(self, address: str) -> bool:
        """Remove an address from all sanctions lists."""
        addr = address.lower()
        entry = self._entries.pop(addr, None)
        if entry is None:
            return False
        for addrs in self._by_source.values():
            addrs.discard(addr)
        logger.info(f"Sanctions: removed {addr[:16]}…")
        return True

    def is_sanctioned(self, address: str) -> bool:
        """Check if an address appears on any sanctions list."""
        return address.lower() in self._entries

    def get_entry(self, address: str) -> Optional[SanctionsEntry]:
        """Get the sanctions entry for an address (if any)."""
        return self._entries.get(address.lower())

    def screen_address(self, address: str) -> Dict:
        """
        Full sanctions screening result for an address.

        Returns a dict with:
          - sanctioned: bool
          - sources: list of matching list names
          - reason: combined reason string
        """
        addr = address.lower()
        entry = self._entries.get(addr)
        if entry is None:
            return {"sanctioned": False, "sources": [], "reason": ""}
        sources = [
            s.value for s, addrs in self._by_source.items() if addr in addrs
        ]
        return {
            "sanctioned": True,
            "sources": sources,
            "reason": entry.reason,
        }

    def list_by_source(self, source: SanctionsSource) -> List[str]:
        """List all addresses on a specific sanctions list."""
        return sorted(self._by_source[source])

    def bulk_add(
        self,
        addresses: List[str],
        source: SanctionsSource,
        reason: str = "",
    ) -> int:
        """Add multiple addresses at once. Returns count added."""
        count = 0
        for addr in addresses:
            self.add_address(addr, source, reason)
            count += 1
        return count

    def get_stats(self) -> Dict:
        """Sanctions list statistics."""
        return {
            "total_entries": len(self._entries),
            "by_source": {
                s.value: len(addrs)
                for s, addrs in self._by_source.items()
            },
        }


# ── Risk cache entry ─────────────────────────────────────────────────
@dataclass
class _RiskCacheEntry:
    score: float
    timestamp: float


# ── Compliance Engine ─────────────────────────────────────────────────
class ComplianceEngine:
    """In-memory + DB-backed compliance policy registry.

    Provides:
    - CRUD for compliance policies (per-address or global)
    - KYC level lookup used by QCOMPLIANCE opcode
    - Risk score caching with configurable TTL
    - Auto-circuit breaker for systemic risk
    """

    RISK_CACHE_TTL_BLOCKS: int = 10  # Cache entries expire after 10 blocks

    def __init__(self, db_manager=None) -> None:
        self.db = db_manager
        self._policies: Dict[str, CompliancePolicy] = {}   # policy_id → policy
        self._address_index: Dict[str, str] = {}            # address → policy_id
        self._risk_cache: Dict[str, _RiskCacheEntry] = {}   # address → cached score
        self._current_block: int = 0
        self.circuit_breaker = CircuitBreaker()
        self.sanctions = SanctionsList()

    # ── Policy CRUD ───────────────────────────────────────────────────

    def create_policy(self, address: str, kyc_level: int = KYCLevel.BASIC,
                      aml_status: int = AMLStatus.CLEAR,
                      sanctions_checked: bool = False,
                      daily_limit: float = 10_000.0,
                      is_blocked: bool = False,
                      tier: int = ComplianceTier.RETAIL,
                      jurisdiction: str = '') -> CompliancePolicy:
        """Create a new compliance policy for an address."""
        policy_id = hashlib.sha256(
            f"{address}:{time.time()}".encode()
        ).hexdigest()[:16]
        policy = CompliancePolicy(
            policy_id=policy_id,
            address=address,
            kyc_level=kyc_level,
            aml_status=aml_status,
            sanctions_checked=sanctions_checked,
            daily_limit=daily_limit,
            is_blocked=is_blocked,
            tier=tier,
            jurisdiction=jurisdiction,
        )
        self._policies[policy_id] = policy
        self._address_index[address] = policy_id
        self._persist_policy(policy)
        logger.info(f"Compliance policy created: {policy_id} for {address}")
        return policy

    def get_policy(self, policy_id: str) -> Optional[CompliancePolicy]:
        """Get a policy by ID."""
        return self._policies.get(policy_id)

    def get_policy_for_address(self, address: str) -> Optional[CompliancePolicy]:
        """Get the compliance policy bound to an address."""
        pid = self._address_index.get(address)
        if pid:
            return self._policies.get(pid)
        # Fallback: try global default
        pid = self._address_index.get('*')
        if pid:
            return self._policies.get(pid)
        return None

    def update_policy(self, policy_id: str, **kwargs) -> Optional[CompliancePolicy]:
        """Update fields on an existing policy."""
        policy = self._policies.get(policy_id)
        if not policy:
            return None
        allowed = {
            'kyc_level', 'aml_status', 'sanctions_checked',
            'daily_limit', 'is_blocked', 'tier', 'jurisdiction',
        }
        for key, value in kwargs.items():
            if key in allowed:
                setattr(policy, key, value)
        policy.updated_at = time.time()
        self._persist_policy(policy)
        return policy

    def delete_policy(self, policy_id: str) -> bool:
        """Remove a policy."""
        policy = self._policies.pop(policy_id, None)
        if policy:
            self._address_index.pop(policy.address, None)
            return True
        return False

    def list_policies(self) -> List[CompliancePolicy]:
        """Return all registered policies."""
        return list(self._policies.values())

    # ── Compliance check (used by QCOMPLIANCE opcode) ─────────────────

    def check_compliance(self, address: str) -> int:
        """Return KYC compliance level for an address.

        If the address has a policy, returns its kyc_level.
        If blocked, returns 0.
        Default: KYCLevel.BASIC (1).
        """
        policy = self.get_policy_for_address(address)
        if policy is None:
            return KYCLevel.BASIC
        if policy.is_blocked:
            return KYCLevel.NONE
        return policy.kyc_level

    def is_address_blocked(self, address: str) -> bool:
        """Check if an address is blocked (sanctions, AML flags, etc.)."""
        # Sanctions check first — always blocks regardless of policy
        if self.sanctions.is_sanctioned(address):
            return True
        policy = self.get_policy_for_address(address)
        if policy is None:
            return False
        return policy.is_blocked or policy.aml_status == AMLStatus.BLOCKED

    def screen_sanctions(self, address: str) -> Dict:
        """Full sanctions screening for an address (OFAC, UN, EU)."""
        return self.sanctions.screen_address(address)

    # ── Risk cache ────────────────────────────────────────────────────

    def set_block_height(self, height: int) -> None:
        """Update current block height (used for cache TTL)."""
        self._current_block = height

    def get_cached_risk(self, address: str) -> Optional[float]:
        """Return cached risk score if still valid, else None."""
        entry = self._risk_cache.get(address)
        if entry is None:
            return None
        age_blocks = self._current_block - int(entry.timestamp)
        if age_blocks > self.RISK_CACHE_TTL_BLOCKS:
            del self._risk_cache[address]
            return None
        return entry.score

    def cache_risk(self, address: str, score: float) -> None:
        """Store a risk score in the cache at current block height."""
        self._risk_cache[address] = _RiskCacheEntry(
            score=score, timestamp=float(self._current_block)
        )

    def invalidate_risk_cache(self, address: Optional[str] = None) -> int:
        """Clear risk cache entries. Returns number removed."""
        if address:
            removed = 1 if self._risk_cache.pop(address, None) else 0
        else:
            removed = len(self._risk_cache)
            self._risk_cache.clear()
        return removed

    # ── Circuit breaker ───────────────────────────────────────────────

    def check_circuit_breaker(self, systemic_risk: float) -> bool:
        """Check and potentially trip the circuit breaker.

        Returns True if operations should be halted.
        """
        return self.circuit_breaker.check(systemic_risk)

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self.circuit_breaker.reset()
        logger.info("Circuit breaker manually reset")

    # ── Persistence helpers ───────────────────────────────────────────

    def _persist_policy(self, policy: CompliancePolicy) -> None:
        if not self.db:
            return
        try:
            with self.db.get_session() as session:
                from sqlalchemy import text
                session.execute(
                    text("""
                        UPSERT INTO compliance_registry
                            (address, kyc_level, aml_status, sanctions_checked,
                             daily_limit, is_blocked, jurisdiction)
                        VALUES (:addr, :kyc, :aml, :sc, :dl, :ib, :j)
                    """),
                    {
                        'addr': policy.address,
                        'kyc': policy.kyc_level,
                        'aml': policy.aml_status,
                        'sc': policy.sanctions_checked,
                        'dl': policy.daily_limit,
                        'ib': policy.is_blocked,
                        'j': policy.jurisdiction,
                    },
                )
                session.commit()
        except Exception as e:
            logger.debug(f"Compliance persist skipped: {e}")
