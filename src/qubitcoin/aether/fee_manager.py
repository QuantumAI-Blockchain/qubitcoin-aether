"""
Aether Tree Fee Manager

Dynamic QBC fee pricing for Aether Tree chat interactions.
Supports three pricing modes:
  - qusd_peg: QBC fee auto-adjusts to match a USD target via QUSD oracle
  - fixed_qbc: Fixed QBC amount (no price adjustment)
  - direct_usd: USD target via external price feed (fallback if QUSD fails)

All parameters loaded from Config (editable via .env / Admin API).
"""
from decimal import Decimal
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class AetherFeeManager:
    """Manage dynamic fee pricing for Aether Tree interactions."""

    def __init__(self, oracle_provider: Optional[object] = None) -> None:
        """
        Args:
            oracle_provider: Optional oracle for QBC/USD price. Must implement
                get_qbc_usd_price() -> Optional[Decimal].
        """
        self._oracle = oracle_provider
        self._last_qbc_price: Optional[Decimal] = None
        self._last_update_block: int = 0
        self._cached_fee: Optional[Decimal] = None

    def _get_qbc_usd_price(self) -> Optional[Decimal]:
        """Get current QBC/USD price from oracle."""
        if self._oracle and hasattr(self._oracle, 'get_qbc_usd_price'):
            try:
                price = self._oracle.get_qbc_usd_price()
                if price and price > 0:
                    self._last_qbc_price = price
                    return price
            except Exception as e:
                logger.warning(f"Oracle price fetch failed: {e}")
        return self._last_qbc_price

    def get_chat_fee(self, is_deep_query: bool = False,
                     current_block: int = 0) -> Decimal:
        """Calculate the current fee for a chat message in QBC.

        Args:
            is_deep_query: If True, apply deep query multiplier.
            current_block: Current block height for update interval checks.

        Returns:
            Fee in QBC.
        """
        mode = Config.AETHER_FEE_PRICING_MODE

        if mode == 'qusd_peg':
            fee = self._qusd_peg_fee(current_block)
        elif mode == 'direct_usd':
            fee = self._direct_usd_fee()
        else:
            # fixed_qbc or unknown mode
            fee = Config.AETHER_CHAT_FEE_QBC

        if is_deep_query:
            fee = fee * Decimal(str(Config.AETHER_QUERY_FEE_MULTIPLIER))

        # Clamp to bounds
        fee = max(Config.AETHER_FEE_MIN_QBC, min(fee, Config.AETHER_FEE_MAX_QBC))

        return fee.quantize(Decimal('0.00000001'))

    def _qusd_peg_fee(self, current_block: int) -> Decimal:
        """Calculate fee using QUSD-pegged pricing."""
        # Check if we need to refresh the price
        blocks_since_update = current_block - self._last_update_block
        if self._cached_fee and blocks_since_update < Config.AETHER_FEE_UPDATE_INTERVAL:
            return self._cached_fee

        price = self._get_qbc_usd_price()
        if price and price > 0:
            fee = Decimal(str(Config.AETHER_CHAT_FEE_USD_TARGET)) / price
            self._cached_fee = fee
            self._last_update_block = current_block
            return fee

        # Fallback to fixed QBC if oracle unavailable
        logger.debug("QUSD oracle unavailable, falling back to fixed_qbc pricing")
        return Config.AETHER_CHAT_FEE_QBC

    def _direct_usd_fee(self) -> Decimal:
        """Calculate fee using direct USD pricing (external oracle)."""
        price = self._get_qbc_usd_price()
        if price and price > 0:
            return Decimal(str(Config.AETHER_CHAT_FEE_USD_TARGET)) / price
        return Config.AETHER_CHAT_FEE_QBC

    def get_fee_info(self, session_messages_sent: int = 0,
                     is_deep_query: bool = False,
                     current_block: int = 0) -> dict:
        """Get comprehensive fee information for API responses.

        Args:
            session_messages_sent: Number of messages already sent in session.
            is_deep_query: Whether this is a deep reasoning query.
            current_block: Current block height.

        Returns:
            Dict with fee breakdown.
        """
        free_remaining = max(0, Config.AETHER_FREE_TIER_MESSAGES - session_messages_sent)
        is_free = free_remaining > 0

        if is_free:
            fee = Decimal('0')
        else:
            fee = self.get_chat_fee(is_deep_query, current_block)

        return {
            'fee_qbc': str(fee),
            'is_free': is_free,
            'free_remaining': free_remaining,
            'is_deep_query': is_deep_query,
            'pricing_mode': Config.AETHER_FEE_PRICING_MODE,
            'usd_target': Config.AETHER_CHAT_FEE_USD_TARGET,
            'qbc_price': str(self._last_qbc_price) if self._last_qbc_price else None,
            'treasury_address': Config.AETHER_FEE_TREASURY_ADDRESS or None,
        }

    def update_oracle(self, oracle_provider: object) -> None:
        """Hot-swap the oracle provider (e.g., after QUSD comes online)."""
        self._oracle = oracle_provider
        self._cached_fee = None
        self._last_update_block = 0
        logger.info("Aether fee oracle updated")
