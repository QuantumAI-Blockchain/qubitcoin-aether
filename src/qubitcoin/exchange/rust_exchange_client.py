"""
Python gRPC client for Rust Exchange Engine.
Bridges Python blockchain node with Rust exchange matching engine.

Supports:
- Orders: PlaceOrder, CancelOrder, GetOrderBook, GetUserOrders
- Markets: GetMarkets, GetRecentTrades, GetMarketSummary
- Balances: Deposit, Withdraw, GetBalance
- Synthetics: MintSynthetic, BurnSynthetic, GetSyntheticAssets, GetCollateralPosition
- Oracle: GetOraclePrices
- Engine: GetEngineStats, HealthCheck
"""
import os
import sys
from typing import Any, Optional

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Import gRPC and generated protobuf files
try:
    import grpc
    import grpc.aio

    exchange_proto_path = os.path.join(
        os.path.dirname(__file__), "../../../qbc-exchange/src/bridge"
    )
    exchange_proto_path = os.path.abspath(exchange_proto_path)
    if exchange_proto_path not in sys.path:
        sys.path.insert(0, exchange_proto_path)

    import exchange_pb2
    import exchange_pb2_grpc

    GRPC_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Exchange gRPC not available: {e}")
    grpc = None  # type: ignore[assignment]
    exchange_pb2 = None
    exchange_pb2_grpc = None
    GRPC_AVAILABLE = False


class RustExchangeClient:
    """
    Client for Rust Exchange Engine via gRPC.
    Handles order matching, synthetic assets, oracle pricing.
    """

    def __init__(self, grpc_addr: str = "127.0.0.1:50053") -> None:
        self.grpc_addr = grpc_addr
        self.channel = None
        self.stub = None
        self.connected = False

        if not GRPC_AVAILABLE:
            logger.warning("Exchange gRPC not available - Rust exchange client disabled")

    def connect(self) -> bool:
        """Connect to Rust Exchange gRPC server."""
        if not GRPC_AVAILABLE:
            logger.error("Exchange gRPC proto not available - cannot connect")
            return False

        try:
            self.channel = grpc.insecure_channel(self.grpc_addr)
            self.stub = exchange_pb2_grpc.ExchangeStub(self.channel)

            # Test connection with health check
            health = self.health_check()
            if health is not None:
                self.connected = True
                logger.info(f"Connected to Rust Exchange at {self.grpc_addr}")
                logger.info(f"Markets: {health.get('markets', 0)}, Oracle: {health.get('oracle_active', False)}")
                return True
            else:
                logger.error("Failed to get health from Rust Exchange")
                return False

        except Exception as e:
            logger.error(f"Failed to connect to Rust Exchange: {e}")
            self.connected = False
            return False

    # ── Order Management ───────────────────────────────────────────────

    def place_order(
        self,
        pair: str,
        side: str,
        order_type: str,
        price: float,
        size: float,
        address: str = "",
    ) -> Optional[dict[str, Any]]:
        """Place a limit or market order."""
        if not self.connected or not self.stub:
            return None

        try:
            side_enum = 0 if side.lower() == "buy" else 1
            type_enum = 0 if order_type.lower() == "limit" else 1

            request = exchange_pb2.PlaceOrderRequest(
                pair=pair,
                side=side_enum,
                order_type=type_enum,
                price=price,
                size=size,
                address=address,
            )
            response = self.stub.PlaceOrder(request, timeout=5.0)

            if response.success:
                order = response.order
                fills = [
                    {
                        "id": f.id,
                        "pair": f.pair,
                        "price": f.price,
                        "size": f.size,
                        "side": f.side,
                        "maker_order_id": f.maker_order_id,
                        "taker_order_id": f.taker_order_id,
                        "timestamp": f.timestamp,
                    }
                    for f in response.fills
                ]
                return {
                    "order": {
                        "id": order.id,
                        "pair": order.pair,
                        "side": order.side,
                        "type": order.order_type,
                        "price": order.price,
                        "size": order.size,
                        "filled": order.filled,
                        "remaining": order.remaining,
                        "address": order.address,
                        "timestamp": order.timestamp,
                        "status": order.status,
                    },
                    "fills": fills,
                    "filled_size": response.filled_size,
                    "remaining_size": response.remaining_size,
                }
            else:
                logger.warning(f"PlaceOrder failed: {response.error}")
                return {"error": response.error}

        except grpc.RpcError as e:
            logger.error(f"gRPC error placing order: {e.code()}: {e.details()}")
            return None
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None

    def cancel_order(self, pair: str, order_id: str, address: str = "") -> bool:
        """Cancel an open order."""
        if not self.connected or not self.stub:
            return False

        try:
            request = exchange_pb2.CancelOrderRequest(
                pair=pair, order_id=order_id, address=address
            )
            response = self.stub.CancelOrder(request, timeout=3.0)
            return response.success

        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False

    def get_orderbook(self, pair: str, depth: int = 20) -> Optional[dict[str, Any]]:
        """Get order book for a pair."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.GetOrderBookRequest(pair=pair, depth=depth)
            response = self.stub.GetOrderBook(request, timeout=3.0)

            return {
                "pair": response.pair,
                "bids": [{"price": l.price, "size": l.size} for l in response.bids],
                "asks": [{"price": l.price, "size": l.size} for l in response.asks],
                "spread": response.spread,
                "midPrice": response.mid_price,
                "bestBid": response.best_bid,
                "bestAsk": response.best_ask,
            }

        except Exception as e:
            logger.error(f"Error getting orderbook: {e}")
            return None

    def get_user_orders(self, address: str) -> list[dict]:
        """Get open orders for an address."""
        if not self.connected or not self.stub:
            return []

        try:
            request = exchange_pb2.GetUserOrdersRequest(address=address)
            response = self.stub.GetUserOrders(request, timeout=3.0)
            return [
                {
                    "id": o.id,
                    "pair": o.pair,
                    "side": o.side,
                    "type": o.order_type,
                    "price": o.price,
                    "size": o.size,
                    "filled": o.filled,
                    "remaining": o.remaining,
                    "status": o.status,
                }
                for o in response.orders
            ]

        except Exception as e:
            logger.error(f"Error getting user orders: {e}")
            return []

    # ── Market Data ────────────────────────────────────────────────────

    def get_markets(self) -> list[dict]:
        """Get all market summaries."""
        if not self.connected or not self.stub:
            return []

        try:
            request = exchange_pb2.GetMarketsRequest()
            response = self.stub.GetMarkets(request, timeout=5.0)
            return [
                {
                    "pair": m.pair,
                    "base": m.base,
                    "quote": m.quote,
                    "lastPrice": m.last_price,
                    "bestBid": m.best_bid,
                    "bestAsk": m.best_ask,
                    "high24h": m.high_24h,
                    "low24h": m.low_24h,
                    "volume24h": m.volume_24h,
                    "change24h": m.change_24h,
                    "trades24h": m.trades_24h,
                    "oraclePrice": m.oracle_price,
                }
                for m in response.markets
            ]

        except Exception as e:
            logger.error(f"Error getting markets: {e}")
            return []

    def get_recent_trades(self, pair: str, limit: int = 50) -> list[dict]:
        """Get recent trades for a pair."""
        if not self.connected or not self.stub:
            return []

        try:
            request = exchange_pb2.GetRecentTradesRequest(pair=pair, limit=limit)
            response = self.stub.GetRecentTrades(request, timeout=3.0)
            return [
                {
                    "id": t.id,
                    "pair": t.pair,
                    "price": t.price,
                    "size": t.size,
                    "side": t.side,
                    "timestamp": t.timestamp,
                }
                for t in response.trades
            ]

        except Exception as e:
            logger.error(f"Error getting recent trades: {e}")
            return []

    # ── Balance Management ─────────────────────────────────────────────

    def deposit(self, address: str, asset: str, amount: float) -> Optional[dict[str, Any]]:
        """Deposit asset into exchange."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.DepositRequest(
                address=address, asset=asset, amount=amount
            )
            response = self.stub.Deposit(request, timeout=3.0)
            if response.success:
                return {
                    "status": "deposited",
                    "address": response.address,
                    "asset": response.asset,
                    "amount": response.amount,
                    "balance": response.balance,
                }
            return {"error": response.error}

        except Exception as e:
            logger.error(f"Error depositing: {e}")
            return None

    def withdraw(self, address: str, asset: str, amount: float) -> Optional[dict[str, Any]]:
        """Withdraw asset from exchange."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.WithdrawRequest(
                address=address, asset=asset, amount=amount
            )
            response = self.stub.Withdraw(request, timeout=3.0)
            if response.success:
                return {
                    "status": "withdrawn",
                    "address": response.address,
                    "asset": response.asset,
                    "amount": response.amount,
                    "balance": response.balance,
                }
            return {"error": response.error}

        except Exception as e:
            logger.error(f"Error withdrawing: {e}")
            return None

    def get_balance(self, address: str) -> Optional[dict[str, Any]]:
        """Get all balances for an address."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.GetBalanceRequest(address=address)
            response = self.stub.GetBalance(request, timeout=3.0)
            return {
                "address": response.address,
                "balances": dict(response.balances),
            }

        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return None

    # ── Synthetic Assets ───────────────────────────────────────────────

    def mint_synthetic(
        self, address: str, symbol: str, qusd_amount: float
    ) -> Optional[dict[str, Any]]:
        """Mint synthetic tokens by depositing QUSD collateral."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.MintSyntheticRequest(
                address=address, symbol=symbol, qusd_amount=qusd_amount
            )
            response = self.stub.MintSynthetic(request, timeout=5.0)
            if response.success:
                return {
                    "symbol": response.symbol,
                    "minted_amount": response.minted_amount,
                    "collateral_locked": response.collateral_locked,
                    "oracle_price": response.oracle_price,
                    "collateral_ratio": response.collateral_ratio,
                }
            return {"error": response.error}

        except Exception as e:
            logger.error(f"Error minting synthetic: {e}")
            return None

    def burn_synthetic(
        self, address: str, symbol: str, amount: float
    ) -> Optional[dict[str, Any]]:
        """Burn synthetic tokens and return QUSD collateral."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.BurnSyntheticRequest(
                address=address, symbol=symbol, amount=amount
            )
            response = self.stub.BurnSynthetic(request, timeout=5.0)
            if response.success:
                return {
                    "symbol": response.symbol,
                    "burned_amount": response.burned_amount,
                    "qusd_returned": response.qusd_returned,
                    "fee": response.fee,
                }
            return {"error": response.error}

        except Exception as e:
            logger.error(f"Error burning synthetic: {e}")
            return None

    def get_synthetic_assets(self) -> list[dict]:
        """Get all synthetic asset definitions with oracle prices."""
        if not self.connected or not self.stub:
            return []

        try:
            request = exchange_pb2.GetSyntheticAssetsRequest()
            response = self.stub.GetSyntheticAssets(request, timeout=3.0)
            return [
                {
                    "symbol": a.symbol,
                    "name": a.name,
                    "coingecko_id": a.coingecko_id,
                    "pair": a.pair,
                    "oracle_price": a.oracle_price,
                    "total_supply": a.total_supply,
                    "total_collateral": a.total_collateral,
                }
                for a in response.assets
            ]

        except Exception as e:
            logger.error(f"Error getting synthetic assets: {e}")
            return []

    def get_collateral_position(
        self, address: str, symbol: str = ""
    ) -> list[dict]:
        """Get collateral positions for an address."""
        if not self.connected or not self.stub:
            return []

        try:
            request = exchange_pb2.GetCollateralPositionRequest(
                address=address, symbol=symbol
            )
            response = self.stub.GetCollateralPosition(request, timeout=3.0)
            return [
                {
                    "symbol": p.symbol,
                    "address": p.address,
                    "synthetic_amount": p.synthetic_amount,
                    "collateral_locked": p.collateral_locked,
                    "collateral_ratio": p.collateral_ratio,
                    "liquidation_price": p.liquidation_price,
                    "is_liquidatable": p.is_liquidatable,
                }
                for p in response.positions
            ]

        except Exception as e:
            logger.error(f"Error getting collateral position: {e}")
            return []

    # ── Oracle ─────────────────────────────────────────────────────────

    def get_oracle_prices(self) -> Optional[dict[str, Any]]:
        """Get all oracle prices."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.GetOraclePricesRequest()
            response = self.stub.GetOraclePrices(request, timeout=3.0)
            return {
                "prices": dict(response.prices),
                "last_updated": response.last_updated,
            }

        except Exception as e:
            logger.error(f"Error getting oracle prices: {e}")
            return None

    # ── Engine Stats ───────────────────────────────────────────────────

    def get_engine_stats(self) -> Optional[dict[str, Any]]:
        """Get exchange engine statistics."""
        if not self.connected or not self.stub:
            return None

        try:
            request = exchange_pb2.GetEngineStatsRequest()
            response = self.stub.GetEngineStats(request, timeout=3.0)
            return {
                "pairs": response.total_pairs,
                "total_orders": response.total_orders,
                "total_trades": response.total_trades,
                "open_orders": response.open_orders,
                "markets": list(response.markets),
                "synthetic_assets": response.synthetic_assets,
                "total_collateral_locked": response.total_collateral_locked,
            }

        except Exception as e:
            logger.error(f"Error getting engine stats: {e}")
            return None

    def health_check(self) -> Optional[dict[str, Any]]:
        """Check health of Rust Exchange Engine."""
        if not self.stub:
            return None

        try:
            request = exchange_pb2.HealthCheckRequest()
            response = self.stub.HealthCheck(request, timeout=3.0)
            return {
                "healthy": response.healthy,
                "version": response.version,
                "uptime_seconds": response.uptime_seconds,
                "markets": response.markets,
                "oracle_active": response.oracle_active,
            }

        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return None

    def disconnect(self) -> None:
        """Close gRPC connection."""
        if self.channel:
            self.channel.close()
            self.channel = None
        self.stub = None
        self.connected = False
        logger.info("Disconnected from Rust Exchange")
