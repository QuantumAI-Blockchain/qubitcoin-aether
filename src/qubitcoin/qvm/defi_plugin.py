"""
DeFi Plugin — Lending, DEX, and staking primitives for QVM

Implements a QVM plugin providing decentralised finance building blocks:
  - Lending pool: deposit collateral, borrow against it, liquidation checks
  - DEX (Automated Market Maker): constant-product x*y=k pools
  - Staking: stake QBC for rewards with configurable APR
"""
import hashlib
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .plugins import QVMPlugin, HookType
from ..utils.logger import get_logger

logger = get_logger(__name__)


# ── Lending Pool ──────────────────────────────────────────────────────

@dataclass
class LendingPosition:
    """A user's position in the lending pool."""
    address: str
    collateral: float = 0.0   # QBC deposited
    borrowed: float = 0.0     # QBC borrowed
    timestamp: float = 0.0

    @property
    def collateral_ratio(self) -> float:
        if self.borrowed <= 0:
            return float('inf')
        return self.collateral / self.borrowed

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'collateral': self.collateral,
            'borrowed': self.borrowed,
            'collateral_ratio': min(self.collateral_ratio, 999.99),
            'timestamp': self.timestamp,
        }


class LendingPool:
    """Simple lending pool with collateralisation.

    Minimum collateral ratio: 150% (default).
    Liquidation threshold: 120% (default).
    """

    def __init__(self, min_collateral_ratio: float = 1.5,
                 liquidation_threshold: float = 1.2) -> None:
        self.min_collateral_ratio = min_collateral_ratio
        self.liquidation_threshold = liquidation_threshold
        self._positions: Dict[str, LendingPosition] = {}
        self._total_deposited: float = 0.0
        self._total_borrowed: float = 0.0

    def deposit(self, address: str, amount: float) -> LendingPosition:
        """Deposit collateral into the pool."""
        if amount <= 0:
            raise ValueError("Deposit amount must be positive")
        pos = self._positions.get(address)
        if not pos:
            pos = LendingPosition(address=address, timestamp=time.time())
            self._positions[address] = pos
        pos.collateral += amount
        self._total_deposited += amount
        return pos

    def borrow(self, address: str, amount: float) -> bool:
        """Borrow against deposited collateral."""
        pos = self._positions.get(address)
        if not pos or amount <= 0:
            return False
        new_borrowed = pos.borrowed + amount
        if pos.collateral / new_borrowed < self.min_collateral_ratio:
            return False  # Insufficient collateral
        pos.borrowed = new_borrowed
        self._total_borrowed += amount
        return True

    def repay(self, address: str, amount: float) -> bool:
        """Repay borrowed amount."""
        pos = self._positions.get(address)
        if not pos or amount <= 0:
            return False
        actual = min(amount, pos.borrowed)
        pos.borrowed -= actual
        self._total_borrowed -= actual
        return True

    def withdraw(self, address: str, amount: float) -> bool:
        """Withdraw collateral (if collateral ratio remains safe)."""
        pos = self._positions.get(address)
        if not pos or amount <= 0:
            return False
        if amount > pos.collateral:
            return False
        new_collateral = pos.collateral - amount
        if pos.borrowed > 0 and new_collateral / pos.borrowed < self.min_collateral_ratio:
            return False
        pos.collateral = new_collateral
        self._total_deposited -= amount
        return True

    def check_liquidation(self, address: str) -> bool:
        """Check if a position is below liquidation threshold."""
        pos = self._positions.get(address)
        if not pos or pos.borrowed <= 0:
            return False
        return pos.collateral_ratio < self.liquidation_threshold

    def get_position(self, address: str) -> Optional[LendingPosition]:
        return self._positions.get(address)

    def get_stats(self) -> dict:
        return {
            'total_deposited': self._total_deposited,
            'total_borrowed': self._total_borrowed,
            'positions': len(self._positions),
            'utilization': self._total_borrowed / self._total_deposited if self._total_deposited > 0 else 0.0,
        }


# ── DEX (Automated Market Maker) ─────────────────────────────────────

@dataclass
class LiquidityPool:
    """Constant-product AMM pool."""
    token_a: str
    token_b: str
    reserve_a: float = 0.0
    reserve_b: float = 0.0
    total_lp_tokens: float = 0.0
    fee_rate: float = 0.003  # 0.3%
    lp_holders: Dict[str, float] = field(default_factory=dict)

    @property
    def k(self) -> float:
        return self.reserve_a * self.reserve_b

    @property
    def price_a_in_b(self) -> float:
        if self.reserve_a <= 0:
            return 0.0
        return self.reserve_b / self.reserve_a

    def to_dict(self) -> dict:
        return {
            'token_a': self.token_a,
            'token_b': self.token_b,
            'reserve_a': self.reserve_a,
            'reserve_b': self.reserve_b,
            'total_lp_tokens': self.total_lp_tokens,
            'price_a_in_b': self.price_a_in_b,
            'fee_rate': self.fee_rate,
        }


class DEX:
    """Automated Market Maker with constant-product formula."""

    def __init__(self) -> None:
        self._pools: Dict[str, LiquidityPool] = {}

    def create_pool(self, token_a: str, token_b: str,
                    fee_rate: float = 0.003) -> LiquidityPool:
        """Create a new liquidity pool."""
        pair_id = _pair_id(token_a, token_b)
        if pair_id in self._pools:
            raise ValueError(f"Pool {pair_id} already exists")
        pool = LiquidityPool(
            token_a=token_a, token_b=token_b, fee_rate=fee_rate,
        )
        self._pools[pair_id] = pool
        return pool

    def add_liquidity(self, token_a: str, token_b: str,
                      amount_a: float, amount_b: float,
                      provider: str) -> float:
        """Add liquidity and receive LP tokens."""
        pair_id = _pair_id(token_a, token_b)
        pool = self._pools.get(pair_id)
        if not pool:
            raise ValueError(f"Pool {pair_id} does not exist")

        if pool.total_lp_tokens == 0:
            lp_tokens = math.sqrt(amount_a * amount_b)
        else:
            ratio_a = amount_a / pool.reserve_a if pool.reserve_a > 0 else 0
            ratio_b = amount_b / pool.reserve_b if pool.reserve_b > 0 else 0
            lp_tokens = min(ratio_a, ratio_b) * pool.total_lp_tokens

        pool.reserve_a += amount_a
        pool.reserve_b += amount_b
        pool.total_lp_tokens += lp_tokens
        pool.lp_holders[provider] = pool.lp_holders.get(provider, 0) + lp_tokens
        return lp_tokens

    def swap(self, token_in: str, token_out: str,
             amount_in: float) -> float:
        """Swap tokens using constant-product formula.

        Returns the output amount (after fee deduction).
        """
        pair_id = _pair_id(token_in, token_out)
        pool = self._pools.get(pair_id)
        if not pool:
            raise ValueError(f"Pool {pair_id} does not exist")

        # Determine which reserve is in / out
        if token_in == pool.token_a:
            reserve_in, reserve_out = pool.reserve_a, pool.reserve_b
        else:
            reserve_in, reserve_out = pool.reserve_b, pool.reserve_a

        fee = amount_in * pool.fee_rate
        amount_in_after_fee = amount_in - fee
        # x * y = k → new_reserve_out = k / (reserve_in + amount_in_after_fee)
        new_reserve_in = reserve_in + amount_in_after_fee
        amount_out = reserve_out - (reserve_in * reserve_out) / new_reserve_in

        if amount_out <= 0:
            return 0.0

        # Update reserves
        if token_in == pool.token_a:
            pool.reserve_a += amount_in
            pool.reserve_b -= amount_out
        else:
            pool.reserve_b += amount_in
            pool.reserve_a -= amount_out

        return amount_out

    def get_pool(self, token_a: str, token_b: str) -> Optional[LiquidityPool]:
        return self._pools.get(_pair_id(token_a, token_b))

    def get_quote(self, token_in: str, token_out: str,
                  amount_in: float) -> float:
        """Get a price quote without executing the swap."""
        pair_id = _pair_id(token_in, token_out)
        pool = self._pools.get(pair_id)
        if not pool:
            return 0.0
        if token_in == pool.token_a:
            reserve_in, reserve_out = pool.reserve_a, pool.reserve_b
        else:
            reserve_in, reserve_out = pool.reserve_b, pool.reserve_a
        fee = amount_in * pool.fee_rate
        amount_in_af = amount_in - fee
        new_ri = reserve_in + amount_in_af
        return reserve_out - (reserve_in * reserve_out) / new_ri

    def list_pools(self) -> List[dict]:
        return [p.to_dict() for p in self._pools.values()]


# ── Staking ───────────────────────────────────────────────────────────

@dataclass
class StakePosition:
    """A user's staking position."""
    address: str
    amount: float
    staked_at: float
    last_reward_claim: float
    accumulated_rewards: float = 0.0

    def to_dict(self) -> dict:
        return {
            'address': self.address,
            'amount': self.amount,
            'staked_at': self.staked_at,
            'accumulated_rewards': self.accumulated_rewards,
        }


class StakingPool:
    """Simple staking pool with configurable APR."""

    def __init__(self, annual_rate: float = 0.05) -> None:
        self.annual_rate = annual_rate  # 5% default APR
        self._stakes: Dict[str, StakePosition] = {}
        self._total_staked: float = 0.0

    def stake(self, address: str, amount: float) -> StakePosition:
        if amount <= 0:
            raise ValueError("Stake amount must be positive")
        now = time.time()
        pos = self._stakes.get(address)
        if pos:
            # Accrue existing rewards before adding more stake
            self._accrue_rewards(address)
            pos.amount += amount
        else:
            pos = StakePosition(
                address=address, amount=amount,
                staked_at=now, last_reward_claim=now,
            )
            self._stakes[address] = pos
        self._total_staked += amount
        return pos

    def unstake(self, address: str, amount: float) -> bool:
        pos = self._stakes.get(address)
        if not pos or amount <= 0 or amount > pos.amount:
            return False
        self._accrue_rewards(address)
        pos.amount -= amount
        self._total_staked -= amount
        if pos.amount <= 0:
            del self._stakes[address]
        return True

    def claim_rewards(self, address: str) -> float:
        pos = self._stakes.get(address)
        if not pos:
            return 0.0
        self._accrue_rewards(address)
        rewards = pos.accumulated_rewards
        pos.accumulated_rewards = 0.0
        return rewards

    def get_pending_rewards(self, address: str) -> float:
        pos = self._stakes.get(address)
        if not pos:
            return 0.0
        elapsed = time.time() - pos.last_reward_claim
        seconds_per_year = 365.25 * 86400
        return pos.amount * self.annual_rate * (elapsed / seconds_per_year)

    def get_position(self, address: str) -> Optional[StakePosition]:
        return self._stakes.get(address)

    def get_stats(self) -> dict:
        return {
            'total_staked': self._total_staked,
            'positions': len(self._stakes),
            'annual_rate': self.annual_rate,
        }

    def _accrue_rewards(self, address: str) -> None:
        pos = self._stakes.get(address)
        if not pos:
            return
        now = time.time()
        elapsed = now - pos.last_reward_claim
        seconds_per_year = 365.25 * 86400
        reward = pos.amount * self.annual_rate * (elapsed / seconds_per_year)
        pos.accumulated_rewards += reward
        pos.last_reward_claim = now


# ── DeFi Plugin ───────────────────────────────────────────────────────

class DeFiPlugin(QVMPlugin):
    """DeFi plugin for QVM — lending, DEX, and staking."""

    def __init__(self) -> None:
        self.lending = LendingPool()
        self.dex = DEX()
        self.staking = StakingPool()
        self._started: bool = False

    def name(self) -> str:
        return 'defi'

    def version(self) -> str:
        return '0.1.0'

    def description(self) -> str:
        return 'DeFi primitives — lending pool, AMM DEX, staking'

    def author(self) -> str:
        return 'Qubitcoin Core'

    def on_load(self) -> None:
        logger.info("DeFi plugin loaded")

    def on_start(self) -> None:
        self._started = True
        logger.info("DeFi plugin started")

    def on_stop(self) -> None:
        self._started = False
        logger.info("DeFi plugin stopped")

    def hooks(self) -> Dict[int, Callable]:
        return {
            HookType.POST_EXECUTE: self._post_execute_hook,
        }

    def _post_execute_hook(self, context: dict) -> Optional[dict]:
        """Track DeFi operations in post-execution."""
        defi_op = context.get('defi_operation')
        if not defi_op:
            return None
        return {'defi_processed': True, 'defi_operation': defi_op}

    def get_stats(self) -> dict:
        return {
            'lending': self.lending.get_stats(),
            'dex_pools': len(self.dex.list_pools()),
            'staking': self.staking.get_stats(),
            'started': self._started,
        }


# ── Helpers ───────────────────────────────────────────────────────────

def _pair_id(token_a: str, token_b: str) -> str:
    """Canonical pair ID (alphabetically sorted)."""
    a, b = sorted([token_a, token_b])
    return f"{a}/{b}"


def create_plugin() -> QVMPlugin:
    """Factory function for dynamic loading."""
    return DeFiPlugin()
