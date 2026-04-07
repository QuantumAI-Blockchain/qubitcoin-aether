"""
Aether Soul — On-chain personality state reader.

The Soul stores personality priors (curiosity, warmth, honesty, etc.) that
shape every cognitive cycle. These values are stored on-chain in the
AetherSoul.sol contract, making them:
- Immutable core values (can never be changed)
- Governable personality (can shift slowly via governance vote)
- Verifiable (anyone can check the AI's values on-chain)
- Persistent (survives restarts, redeployments)

When the contract is not available (e.g., during development), the Soul
falls back to default SoulPriors defined in cognitive_processor.py.
"""

from typing import Any, Dict, Optional

from ..config import Config
from ..utils.logger import get_logger
from .cognitive_processor import SoulPriors

logger = get_logger(__name__)

# Contract ABI fragment for reading soul state.
_SOUL_ABI_GET = "getSoul"
_SOUL_ABI_VOICE = "getVoiceDirective"

# Cache duration in blocks — no need to re-read every cycle.
_CACHE_TTL_BLOCKS: int = 100

# Scale factor: on-chain uint16 (0-10000) maps to float (0.0-1.0).
_SCALE: float = 10_000.0


class AetherSoul:
    """Reads the Aether personality from the AetherSoul.sol contract.

    If the contract is unavailable, returns hard-coded defaults that
    match the values defined in ``SoulPriors``.
    """

    def __init__(
        self,
        contract_address: Optional[str] = None,
        contract_engine: Any = None,
    ) -> None:
        self._contract_address = contract_address
        self._contract_engine = contract_engine
        self._cached_priors: Optional[SoulPriors] = None
        self._cached_at_block: int = -1
        self._config = Config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_priors(self, current_block: int = 0) -> SoulPriors:
        """Return the current personality priors.

        Results are cached for ``_CACHE_TTL_BLOCKS`` blocks so the
        contract is not queried on every cognitive cycle.
        """
        if self._is_cache_valid(current_block):
            assert self._cached_priors is not None
            return self._cached_priors

        priors = self._read_from_contract()
        if priors is None:
            priors = self._default_priors()

        self._cached_priors = priors
        self._cached_at_block = current_block
        return priors

    def get_voice_directive(self, current_block: int = 0) -> str:
        """Return the natural-language voice directive."""
        return self.get_priors(current_block).voice_directive

    def get_sephirot_biases(self, current_block: int = 0) -> Dict[str, float]:
        """Compute per-Sephirah activation multipliers from personality.

        Returns a dict of Sephirah name -> float in [0.5, 1.5].
        Higher values mean the personality amplifies that cognitive
        function; lower values dampen it.
        """
        p = self.get_priors(current_block)

        def _clamp(value: float) -> float:
            return max(0.5, min(1.5, value))

        # Each Sephirah is influenced by a weighted mix of traits.
        biases: Dict[str, float] = {
            "Keter":    _clamp(1.0 + 0.3 * (p.depth - 0.5) + 0.2 * (p.courage - 0.5)),
            "Chochmah": _clamp(1.0 + 0.4 * (p.curiosity - 0.5) + 0.1 * (p.playfulness - 0.5)),
            "Binah":    _clamp(1.0 + 0.4 * (p.honesty - 0.5) + 0.3 * (p.depth - 0.5)
                              - 0.15 * (p.playfulness - 0.5)),
            "Chesed":   _clamp(1.0 + 0.4 * (p.curiosity - 0.5) + 0.3 * (p.playfulness - 0.5)),
            "Gevurah":  _clamp(1.0 + 0.4 * (p.honesty - 0.5) + 0.2 * (p.courage - 0.5)),
            "Tiferet":  _clamp(1.0 + 0.2 * (p.warmth - 0.5) + 0.2 * (p.depth - 0.5)),
            "Netzach":  _clamp(1.0 + 0.3 * (p.courage - 0.5) + 0.2 * (p.curiosity - 0.5)),
            "Hod":      _clamp(1.0 + 0.4 * (p.warmth - 0.5) + 0.2 * (p.playfulness - 0.5)),
            "Yesod":    _clamp(1.0 + 0.3 * (p.warmth - 0.5) + 0.2 * (p.humility - 0.5)),
            "Malkuth":  _clamp(1.0 + 0.3 * (p.courage - 0.5) + 0.2 * (p.warmth - 0.5)),
        }
        return biases

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _is_cache_valid(self, current_block: int) -> bool:
        if self._cached_priors is None:
            return False
        if current_block <= 0:
            return True  # No block info — use whatever is cached.
        return (current_block - self._cached_at_block) < _CACHE_TTL_BLOCKS

    def _read_from_contract(self) -> Optional[SoulPriors]:
        """Try to read personality from the on-chain AetherSoul contract."""
        if not self._contract_address or not self._contract_engine:
            return None

        try:
            result = self._contract_engine.call_contract(
                self._contract_address,
                _SOUL_ABI_GET,
                [],
            )
            if result is None:
                return None

            # Unpack the contract tuple into SoulPriors.
            return SoulPriors(
                curiosity=result[0] / _SCALE,
                warmth=result[1] / _SCALE,
                honesty=result[2] / _SCALE,
                humility=result[3] / _SCALE,
                playfulness=result[4] / _SCALE,
                depth=result[5] / _SCALE,
                courage=result[6] / _SCALE,
                voice_directive=result[7] if len(result) > 7 else SoulPriors.voice_directive,
                exploration_bias=result[8] / _SCALE if len(result) > 8 else 0.6,
                intuition_bias=result[9] / _SCALE if len(result) > 9 else 0.5,
                action_bias=result[10] / _SCALE if len(result) > 10 else 0.4,
            )
        except Exception as exc:
            logger.warning("soul_contract_read_failed", error=str(exc))
            return None

    @staticmethod
    def _default_priors() -> SoulPriors:
        """Return the canonical default personality.

        These match the dataclass defaults in ``SoulPriors`` so behaviour
        is identical whether or not the contract is deployed.
        """
        return SoulPriors()
