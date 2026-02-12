"""
Contract Deployment Fee Calculator

Computes fees for deploying and executing contracts on QVM.
Fee structure:
  deploy_fee = base_fee + (bytecode_size_kb * per_kb_fee)
  execute_fee = execute_base_fee * gas_multiplier

Fees are dynamically pegged to QUSD when available, with fallback to fixed QBC.
All parameters are loaded from Config (editable via .env / Admin API).
"""
from decimal import Decimal
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContractFeeCalculator:
    """Calculate fees for contract deployment and execution."""

    def __init__(self, oracle_provider: Optional[object] = None) -> None:
        """
        Args:
            oracle_provider: Optional oracle for QBC/USD price. Must implement
                get_qbc_usd_price() -> Optional[Decimal].
        """
        self._oracle = oracle_provider
        self._last_qbc_price: Optional[Decimal] = None
        self._last_update_block: int = 0

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

    def calculate_deploy_fee(self, bytecode_size_bytes: int,
                             is_template: bool = False) -> Decimal:
        """Calculate the fee for deploying a contract.

        Args:
            bytecode_size_bytes: Size of the contract bytecode in bytes.
            is_template: If True, apply template discount.

        Returns:
            Fee in QBC.
        """
        mode = Config.CONTRACT_FEE_PRICING_MODE

        if mode == 'qusd_peg':
            price = self._get_qbc_usd_price()
            if price and price > 0:
                base_fee = Decimal(str(Config.CONTRACT_DEPLOY_FEE_USD_TARGET)) / price
                per_kb_fee = (Decimal(str(Config.CONTRACT_DEPLOY_FEE_USD_TARGET)) / 50) / price
            else:
                # Fallback to fixed QBC
                base_fee = Config.CONTRACT_DEPLOY_BASE_FEE_QBC
                per_kb_fee = Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC
        elif mode == 'fixed_qbc':
            base_fee = Config.CONTRACT_DEPLOY_BASE_FEE_QBC
            per_kb_fee = Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC
        else:
            base_fee = Config.CONTRACT_DEPLOY_BASE_FEE_QBC
            per_kb_fee = Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC

        size_kb = Decimal(bytecode_size_bytes) / Decimal(1024)
        fee = base_fee + (size_kb * per_kb_fee)

        if is_template:
            discount = Decimal(str(Config.CONTRACT_TEMPLATE_DISCOUNT))
            fee = fee * (Decimal(1) - discount)

        # Clamp to reasonable bounds
        fee = max(Decimal('0.001'), fee)
        return fee.quantize(Decimal('0.00000001'))

    def calculate_execute_fee(self, gas_used: int) -> Decimal:
        """Calculate the fee for executing a contract call.

        Args:
            gas_used: Amount of gas consumed by the execution.

        Returns:
            Fee in QBC.
        """
        base_fee = Config.CONTRACT_EXECUTE_BASE_FEE_QBC
        gas_fee = Decimal(gas_used) * Config.DEFAULT_GAS_PRICE
        return (base_fee + gas_fee).quantize(Decimal('0.00000001'))

    def estimate_deploy_fee(self, bytecode_hex: str,
                            is_template: bool = False) -> dict:
        """Estimate deployment fee from hex bytecode.

        Returns dict with fee breakdown for API responses.
        """
        bytecode_size = len(bytecode_hex) // 2 if bytecode_hex else 0
        fee = self.calculate_deploy_fee(bytecode_size, is_template)
        return {
            'bytecode_size_bytes': bytecode_size,
            'bytecode_size_kb': round(bytecode_size / 1024, 2),
            'is_template': is_template,
            'template_discount': float(Config.CONTRACT_TEMPLATE_DISCOUNT) if is_template else 0,
            'fee_qbc': str(fee),
            'pricing_mode': Config.CONTRACT_FEE_PRICING_MODE,
            'base_fee_qbc': str(Config.CONTRACT_DEPLOY_BASE_FEE_QBC),
            'per_kb_fee_qbc': str(Config.CONTRACT_DEPLOY_PER_KB_FEE_QBC),
        }
