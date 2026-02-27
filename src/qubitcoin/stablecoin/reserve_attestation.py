"""
Reserve Attestation — Chainlink-style Proof of Reserve for QUSD

Generates cryptographic attestations that prove the QUSD stablecoin's
reserve ratio at specific block heights. Third-party verifiers can
independently verify these attestations against on-chain state.

Similar to Chainlink Proof of Reserve but adapted for QBC's architecture.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ReserveAttestation:
    """A cryptographic attestation of reserve state at a specific block."""
    attestation_id: str
    block_height: int
    timestamp: float
    total_qusd_supply: Decimal
    total_reserve_value: Decimal
    reserve_ratio: float
    reserve_breakdown: Dict[str, Decimal]
    attestation_hash: str
    attester: str
    is_healthy: bool
    deviations: List[str] = field(default_factory=list)


class ReserveAttestationEngine:
    """Generates and verifies QUSD reserve attestations.

    Periodically produces signed attestations proving the reserve
    backing of QUSD at specific block heights. These attestations
    are stored on-chain and can be verified by any third party.
    """

    def __init__(self, stablecoin_engine: Optional[object] = None) -> None:
        self._engine = stablecoin_engine
        self._attestations: List[ReserveAttestation] = []
        self._last_attestation_block: int = 0
        self._attestation_interval: int = int(
            Config.RESERVE_ATTESTATION_INTERVAL
            if hasattr(Config, 'RESERVE_ATTESTATION_INTERVAL')
            else 1000
        )

    def generate_attestation(
        self,
        block_height: int,
        total_supply: Decimal,
        reserve_value: Decimal,
        reserve_breakdown: Optional[Dict[str, Decimal]] = None,
        attester: str = "system",
    ) -> ReserveAttestation:
        """Generate a reserve attestation for the current state.

        Args:
            block_height: The block height this attestation covers.
            total_supply: Total QUSD in circulation.
            reserve_value: Total reserve value in USD equivalent.
            reserve_breakdown: Per-asset reserve breakdown.
            attester: Address or identifier of the attester.

        Returns:
            ReserveAttestation with cryptographic hash.
        """
        if reserve_breakdown is None:
            reserve_breakdown = {"qbc": reserve_value}

        ratio = float(reserve_value / total_supply) if total_supply > 0 else 0.0
        is_healthy = ratio >= Config.RESERVE_MIN_RATIO if hasattr(Config, 'RESERVE_MIN_RATIO') else ratio >= 1.0

        deviations: List[str] = []
        if ratio < 1.0:
            deviations.append(f"Under-collateralized: {ratio:.4f} < 1.0")
        if ratio < 0.9:
            deviations.append(f"Critical: reserve ratio {ratio:.4f} below 90%")

        # Build attestation data for hashing
        attestation_data = {
            "block_height": block_height,
            "total_supply": str(total_supply),
            "reserve_value": str(reserve_value),
            "reserve_ratio": ratio,
            "breakdown": {k: str(v) for k, v in reserve_breakdown.items()},
            "attester": attester,
            "timestamp": time.time(),
        }

        attestation_hash = hashlib.sha256(
            json.dumps(attestation_data, sort_keys=True).encode()
        ).hexdigest()

        attestation_id = f"attest-{block_height}-{attestation_hash[:8]}"

        attestation = ReserveAttestation(
            attestation_id=attestation_id,
            block_height=block_height,
            timestamp=attestation_data["timestamp"],
            total_qusd_supply=total_supply,
            total_reserve_value=reserve_value,
            reserve_ratio=ratio,
            reserve_breakdown=reserve_breakdown,
            attestation_hash=attestation_hash,
            attester=attester,
            is_healthy=is_healthy,
            deviations=deviations,
        )

        self._attestations.append(attestation)
        self._last_attestation_block = block_height

        # Keep only last 1000 attestations in memory
        if len(self._attestations) > 1000:
            self._attestations = self._attestations[-1000:]

        logger.info(
            f"Reserve attestation generated at block {block_height}: "
            f"ratio={ratio:.4f}, healthy={is_healthy}, hash={attestation_hash[:16]}..."
        )

        return attestation

    def should_attest(self, current_block: int) -> bool:
        """Check if it's time to generate a new attestation.

        Args:
            current_block: Current block height.

        Returns:
            True if attestation interval has elapsed.
        """
        return (current_block - self._last_attestation_block) >= self._attestation_interval

    def verify_attestation(self, attestation: ReserveAttestation) -> bool:
        """Verify an attestation's hash matches its data.

        Args:
            attestation: The attestation to verify.

        Returns:
            True if the hash is valid.
        """
        attestation_data = {
            "block_height": attestation.block_height,
            "total_supply": str(attestation.total_qusd_supply),
            "reserve_value": str(attestation.total_reserve_value),
            "reserve_ratio": attestation.reserve_ratio,
            "breakdown": {k: str(v) for k, v in attestation.reserve_breakdown.items()},
            "attester": attestation.attester,
            "timestamp": attestation.timestamp,
        }

        expected_hash = hashlib.sha256(
            json.dumps(attestation_data, sort_keys=True).encode()
        ).hexdigest()

        return expected_hash == attestation.attestation_hash

    def get_latest_attestation(self) -> Optional[ReserveAttestation]:
        """Get the most recent attestation."""
        return self._attestations[-1] if self._attestations else None

    def get_attestation_by_block(self, block_height: int) -> Optional[ReserveAttestation]:
        """Get attestation closest to a specific block height."""
        if not self._attestations:
            return None

        closest = min(
            self._attestations,
            key=lambda a: abs(a.block_height - block_height),
        )
        return closest

    def get_attestation_history(self, limit: int = 100) -> List[Dict]:
        """Get recent attestation history.

        Args:
            limit: Maximum number of attestations to return.

        Returns:
            List of attestation summaries.
        """
        recent = self._attestations[-limit:]
        return [
            {
                "attestation_id": a.attestation_id,
                "block_height": a.block_height,
                "timestamp": a.timestamp,
                "reserve_ratio": a.reserve_ratio,
                "is_healthy": a.is_healthy,
                "attestation_hash": a.attestation_hash,
                "deviations": a.deviations,
            }
            for a in reversed(recent)
        ]

    def get_stats(self) -> Dict:
        """Get attestation engine statistics."""
        total = len(self._attestations)
        healthy = sum(1 for a in self._attestations if a.is_healthy)
        unhealthy = total - healthy

        avg_ratio = 0.0
        if total > 0:
            avg_ratio = sum(a.reserve_ratio for a in self._attestations) / total

        latest = self.get_latest_attestation()

        return {
            "total_attestations": total,
            "healthy_attestations": healthy,
            "unhealthy_attestations": unhealthy,
            "average_reserve_ratio": round(avg_ratio, 4),
            "attestation_interval_blocks": self._attestation_interval,
            "last_attestation_block": self._last_attestation_block,
            "latest_ratio": latest.reserve_ratio if latest else None,
            "latest_hash": latest.attestation_hash if latest else None,
        }

    def auto_attest(self, block_height: int) -> Optional[ReserveAttestation]:
        """Auto-generate attestation from StablecoinEngine if available.

        Called per-block from the node loop. Generates an attestation
        if the interval has elapsed and StablecoinEngine is available.

        Args:
            block_height: Current block height.

        Returns:
            Attestation if generated, None otherwise.
        """
        if not self.should_attest(block_height):
            return None

        if self._engine is None:
            return None

        try:
            health = self._engine.get_system_health()
            total_supply = Decimal(str(health.get('total_qusd', 0)))
            reserve = Decimal(str(health.get('reserve_backing', 0)))

            if total_supply <= 0:
                return None

            return self.generate_attestation(
                block_height=block_height,
                total_supply=total_supply,
                reserve_value=reserve,
                attester="auto",
            )
        except Exception as e:
            logger.debug(f"Auto-attestation failed at block {block_height}: {e}")
            return None
