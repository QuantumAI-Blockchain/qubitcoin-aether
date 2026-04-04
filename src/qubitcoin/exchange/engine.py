"""
QBC Exchange Engine — In-memory order book matching engine.

Supports spot trading pairs with limit/market orders.
Provides deep liquidity seeding from mint wallets.
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(str, Enum):
    OPEN = "open"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"


@dataclass
class Order:
    id: str
    pair: str
    side: Side
    order_type: OrderType
    price: Decimal
    size: Decimal
    filled: Decimal = Decimal("0")
    address: str = ""
    timestamp: float = 0.0
    status: OrderStatus = OrderStatus.OPEN

    @property
    def remaining(self) -> Decimal:
        return self.size - self.filled

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pair": self.pair,
            "side": self.side.value,
            "type": self.order_type.value,
            "price": float(self.price),
            "size": float(self.size),
            "filled": float(self.filled),
            "remaining": float(self.remaining),
            "address": self.address,
            "timestamp": self.timestamp,
            "status": self.status.value,
        }


@dataclass
class Trade:
    id: str
    pair: str
    price: Decimal
    size: Decimal
    side: Side
    maker_order_id: str
    taker_order_id: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "pair": self.pair,
            "price": float(self.price),
            "size": float(self.size),
            "side": self.side.value,
            "maker_order_id": self.maker_order_id,
            "taker_order_id": self.taker_order_id,
            "timestamp": self.timestamp,
        }


@dataclass
class MarketConfig:
    pair: str
    base: str
    quote: str
    tick_size: Decimal = Decimal("0.0001")
    min_order: Decimal = Decimal("0.001")
    maker_fee: Decimal = Decimal("0.0002")  # 0.02%
    taker_fee: Decimal = Decimal("0.0005")  # 0.05%


class OrderBook:
    """Single-pair order book with price-time priority matching."""

    def __init__(self, config: MarketConfig) -> None:
        self.config = config
        self.bids: list[Order] = []  # sorted by price DESC, time ASC
        self.asks: list[Order] = []  # sorted by price ASC, time ASC
        self._trades: list[Trade] = []
        self._all_orders: dict[str, Order] = {}

    def _sort_bids(self) -> None:
        self.bids.sort(key=lambda o: (-o.price, o.timestamp))

    def _sort_asks(self) -> None:
        self.asks.sort(key=lambda o: (o.price, o.timestamp))

    def add_order(self, order: Order) -> list[Trade]:
        """Add order and match against resting orders. Returns fills."""
        fills: list[Trade] = []
        self._all_orders[order.id] = order

        if order.order_type == OrderType.MARKET:
            fills = self._match_market(order)
        else:
            fills = self._match_limit(order)

        # If order still has remaining size and is limit, add to book
        if order.remaining > 0 and order.order_type == OrderType.LIMIT:
            if order.side == Side.BUY:
                self.bids.append(order)
                self._sort_bids()
            else:
                self.asks.append(order)
                self._sort_asks()
            if order.filled > 0:
                order.status = OrderStatus.PARTIAL

        return fills

    def _match_limit(self, taker: Order) -> list[Trade]:
        fills: list[Trade] = []
        book = self.asks if taker.side == Side.BUY else self.bids

        i = 0
        while i < len(book) and taker.remaining > 0:
            maker = book[i]
            # Price check
            if taker.side == Side.BUY and maker.price > taker.price:
                break
            if taker.side == Side.SELL and maker.price < taker.price:
                break

            fill_size = min(taker.remaining, maker.remaining)
            fill_price = maker.price  # maker gets their price

            taker.filled += fill_size
            maker.filled += fill_size

            trade = Trade(
                id=str(uuid.uuid4())[:8],
                pair=taker.pair,
                price=fill_price,
                size=fill_size,
                side=taker.side,
                maker_order_id=maker.id,
                taker_order_id=taker.id,
                timestamp=time.time(),
            )
            fills.append(trade)
            self._trades.append(trade)

            if maker.remaining <= 0:
                maker.status = OrderStatus.FILLED
                book.pop(i)
            else:
                maker.status = OrderStatus.PARTIAL
                i += 1

        if taker.remaining <= 0:
            taker.status = OrderStatus.FILLED

        return fills

    def _match_market(self, taker: Order) -> list[Trade]:
        fills: list[Trade] = []
        book = self.asks if taker.side == Side.BUY else self.bids

        while book and taker.remaining > 0:
            maker = book[0]
            fill_size = min(taker.remaining, maker.remaining)
            fill_price = maker.price

            taker.filled += fill_size
            maker.filled += fill_size

            trade = Trade(
                id=str(uuid.uuid4())[:8],
                pair=taker.pair,
                price=fill_price,
                size=fill_size,
                side=taker.side,
                maker_order_id=maker.id,
                taker_order_id=taker.id,
                timestamp=time.time(),
            )
            fills.append(trade)
            self._trades.append(trade)

            if maker.remaining <= 0:
                maker.status = OrderStatus.FILLED
                book.pop(0)
            else:
                maker.status = OrderStatus.PARTIAL

        if taker.remaining <= 0:
            taker.status = OrderStatus.FILLED

        return fills

    def cancel_order(self, order_id: str, owner_address: str = "") -> bool:
        order = self._all_orders.get(order_id)
        if not order or order.status in (OrderStatus.FILLED, OrderStatus.CANCELLED):
            return False
        if owner_address and order.address != owner_address:
            return False

        order.status = OrderStatus.CANCELLED
        self.bids = [o for o in self.bids if o.id != order_id]
        self.asks = [o for o in self.asks if o.id != order_id]
        return True

    def get_orderbook(self, depth: int = 20) -> dict[str, Any]:
        bids = []
        asks = []

        # Aggregate by price level
        bid_levels: dict[float, float] = {}
        for o in self.bids[:depth * 5]:
            p = float(o.price)
            bid_levels[p] = bid_levels.get(p, 0) + float(o.remaining)
        for p in sorted(bid_levels, reverse=True)[:depth]:
            bids.append({"price": p, "size": bid_levels[p]})

        ask_levels: dict[float, float] = {}
        for o in self.asks[:depth * 5]:
            p = float(o.price)
            ask_levels[p] = ask_levels.get(p, 0) + float(o.remaining)
        for p in sorted(ask_levels)[:depth]:
            asks.append({"price": p, "size": ask_levels[p]})

        best_bid = bids[0]["price"] if bids else 0
        best_ask = asks[0]["price"] if asks else 0
        spread = best_ask - best_bid if best_bid and best_ask else 0
        mid = (best_bid + best_ask) / 2 if best_bid and best_ask else 0

        return {
            "pair": self.config.pair,
            "bids": bids,
            "asks": asks,
            "spread": spread,
            "midPrice": mid,
            "bestBid": best_bid,
            "bestAsk": best_ask,
        }

    def get_recent_trades(self, limit: int = 50) -> list[dict]:
        return [t.to_dict() for t in self._trades[-limit:]]

    def get_market_summary(self) -> dict[str, Any]:
        trades_24h = [t for t in self._trades if t.timestamp > time.time() - 86400]
        volume = sum(float(t.size * t.price) for t in trades_24h)
        last_price = float(trades_24h[-1].price) if trades_24h else 0
        high = max((float(t.price) for t in trades_24h), default=0)
        low = min((float(t.price) for t in trades_24h), default=0)

        ob = self.get_orderbook(1)
        best_bid = ob["bestBid"]
        best_ask = ob["bestAsk"]

        # If no trades, use mid price
        if not last_price and best_bid and best_ask:
            last_price = (best_bid + best_ask) / 2

        first_price = float(trades_24h[0].price) if trades_24h else last_price
        change = ((last_price - first_price) / first_price * 100) if first_price else 0

        return {
            "pair": self.config.pair,
            "base": self.config.base,
            "quote": self.config.quote,
            "lastPrice": last_price,
            "bestBid": best_bid,
            "bestAsk": best_ask,
            "high24h": high,
            "low24h": low,
            "volume24h": volume,
            "change24h": round(change, 2),
            "trades24h": len(trades_24h),
        }


class ExchangeEngine:
    """Multi-pair exchange engine with balance management."""

    # Only markets where we control both sides (mintable assets)
    # Synthetic pairs (sBTC, sETH, etc.) are added dynamically via add_synthetic_market()
    MARKETS = [
        MarketConfig(pair="QBC/QUSD", base="QBC", quote="QUSD", tick_size=Decimal("0.0001"), min_order=Decimal("1")),
        MarketConfig(pair="wQBC/QUSD", base="wQBC", quote="QUSD", tick_size=Decimal("0.0001"), min_order=Decimal("1")),
    ]

    # Top 50 synthetic asset definitions — oracle-priced, QUSD-collateralized
    SYNTHETIC_ASSETS: list[dict[str, Any]] = [
        {"symbol": "sBTC",  "name": "Synthetic Bitcoin",    "coingecko_id": "bitcoin",          "decimals": 8},
        {"symbol": "sETH",  "name": "Synthetic Ethereum",   "coingecko_id": "ethereum",         "decimals": 8},
        {"symbol": "sBNB",  "name": "Synthetic BNB",        "coingecko_id": "binancecoin",      "decimals": 8},
        {"symbol": "sSOL",  "name": "Synthetic Solana",     "coingecko_id": "solana",           "decimals": 8},
        {"symbol": "sXRP",  "name": "Synthetic XRP",        "coingecko_id": "ripple",           "decimals": 8},
        {"symbol": "sADA",  "name": "Synthetic Cardano",    "coingecko_id": "cardano",          "decimals": 8},
        {"symbol": "sDOGE", "name": "Synthetic Dogecoin",   "coingecko_id": "dogecoin",         "decimals": 8},
        {"symbol": "sAVAX", "name": "Synthetic Avalanche",  "coingecko_id": "avalanche-2",      "decimals": 8},
        {"symbol": "sDOT",  "name": "Synthetic Polkadot",   "coingecko_id": "polkadot",         "decimals": 8},
        {"symbol": "sTRX",  "name": "Synthetic Tron",       "coingecko_id": "tron",             "decimals": 8},
        {"symbol": "sLINK", "name": "Synthetic Chainlink",  "coingecko_id": "chainlink",        "decimals": 8},
        {"symbol": "sMATIC","name": "Synthetic Polygon",    "coingecko_id": "matic-network",    "decimals": 8},
        {"symbol": "sSHIB", "name": "Synthetic Shiba Inu",  "coingecko_id": "shiba-inu",        "decimals": 8},
        {"symbol": "sTON",  "name": "Synthetic Toncoin",    "coingecko_id": "the-open-network", "decimals": 8},
        {"symbol": "sLTC",  "name": "Synthetic Litecoin",   "coingecko_id": "litecoin",         "decimals": 8},
        {"symbol": "sBCH",  "name": "Synthetic Bitcoin Cash","coingecko_id": "bitcoin-cash",    "decimals": 8},
        {"symbol": "sUNI",  "name": "Synthetic Uniswap",    "coingecko_id": "uniswap",          "decimals": 8},
        {"symbol": "sATOM", "name": "Synthetic Cosmos",     "coingecko_id": "cosmos",           "decimals": 8},
        {"symbol": "sXLM",  "name": "Synthetic Stellar",    "coingecko_id": "stellar",          "decimals": 8},
        {"symbol": "sNEAR", "name": "Synthetic NEAR",       "coingecko_id": "near",             "decimals": 8},
        {"symbol": "sAPT",  "name": "Synthetic Aptos",      "coingecko_id": "aptos",            "decimals": 8},
        {"symbol": "sICP",  "name": "Synthetic ICP",        "coingecko_id": "internet-computer","decimals": 8},
        {"symbol": "sFIL",  "name": "Synthetic Filecoin",   "coingecko_id": "filecoin",         "decimals": 8},
        {"symbol": "sETC",  "name": "Synthetic Ethereum Classic","coingecko_id": "ethereum-classic","decimals": 8},
        {"symbol": "sARB",  "name": "Synthetic Arbitrum",   "coingecko_id": "arbitrum",         "decimals": 8},
        {"symbol": "sOP",   "name": "Synthetic Optimism",   "coingecko_id": "optimism",         "decimals": 8},
        {"symbol": "sIMX",  "name": "Synthetic Immutable X","coingecko_id": "immutable-x",      "decimals": 8},
        {"symbol": "sINJ",  "name": "Synthetic Injective",  "coingecko_id": "injective-protocol","decimals": 8},
        {"symbol": "sVET",  "name": "Synthetic VeChain",    "coingecko_id": "vechain",          "decimals": 8},
        {"symbol": "sHBAR", "name": "Synthetic Hedera",     "coingecko_id": "hedera-hashgraph", "decimals": 8},
        {"symbol": "sSUI",  "name": "Synthetic Sui",        "coingecko_id": "sui",              "decimals": 8},
        {"symbol": "sMKR",  "name": "Synthetic Maker",      "coingecko_id": "maker",            "decimals": 8},
        {"symbol": "sAAVE", "name": "Synthetic Aave",       "coingecko_id": "aave",             "decimals": 8},
        {"symbol": "sRENDER","name": "Synthetic Render",    "coingecko_id": "render-token",     "decimals": 8},
        {"symbol": "sGRT",  "name": "Synthetic The Graph",  "coingecko_id": "the-graph",        "decimals": 8},
        {"symbol": "sFTM",  "name": "Synthetic Fantom",     "coingecko_id": "fantom",           "decimals": 8},
        {"symbol": "sALGO", "name": "Synthetic Algorand",   "coingecko_id": "algorand",         "decimals": 8},
        {"symbol": "sTHETA","name": "Synthetic Theta",      "coingecko_id": "theta-token",      "decimals": 8},
        {"symbol": "sFLOW", "name": "Synthetic Flow",       "coingecko_id": "flow",             "decimals": 8},
        {"symbol": "sSAND", "name": "Synthetic Sandbox",    "coingecko_id": "the-sandbox",      "decimals": 8},
        {"symbol": "sAXS",  "name": "Synthetic Axie Infinity","coingecko_id": "axie-infinity",  "decimals": 8},
        {"symbol": "sMANA", "name": "Synthetic Decentraland","coingecko_id": "decentraland",    "decimals": 8},
        {"symbol": "sSEI",  "name": "Synthetic Sei",        "coingecko_id": "sei-network",      "decimals": 8},
        {"symbol": "sSTX",  "name": "Synthetic Stacks",     "coingecko_id": "blockstack",       "decimals": 8},
        {"symbol": "sEGLD", "name": "Synthetic MultiversX", "coingecko_id": "elrond-erd-2",     "decimals": 8},
        {"symbol": "sQNT",  "name": "Synthetic Quant",      "coingecko_id": "quant-network",    "decimals": 8},
        {"symbol": "sPEPE", "name": "Synthetic Pepe",       "coingecko_id": "pepe",             "decimals": 8},
        {"symbol": "sWLD",  "name": "Synthetic Worldcoin",  "coingecko_id": "worldcoin-wld",    "decimals": 8},
    ]

    def __init__(self, db_manager: Any = None) -> None:
        self.books: dict[str, OrderBook] = {}
        self.balances: dict[str, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        self._order_count = 0
        self.oracle_prices: dict[str, float] = {}  # symbol -> USD price
        self._oracle_last_fetch: float = 0.0
        self._synthetic_registry: dict[str, dict] = {}  # symbol -> asset info
        self._collateral_ratio = Decimal("1.5")  # 150% collateralization for synths
        self._db: Any = db_manager  # DatabaseManager — used for on-chain balance verification

        # Initialize real markets (QBC/QUSD only)
        for mc in self.MARKETS:
            self.books[mc.pair] = OrderBook(mc)

        # Register all synthetic assets and create their markets
        for asset in self.SYNTHETIC_ASSETS:
            sym = asset["symbol"]
            pair = f"{sym}/QUSD"
            self._synthetic_registry[sym] = asset
            mc = MarketConfig(
                pair=pair, base=sym, quote="QUSD",
                tick_size=Decimal("0.01"), min_order=Decimal("0.001"),
            )
            self.books[pair] = OrderBook(mc)

        logger.info(f"ExchangeEngine initialized: {len(self.MARKETS)} real + {len(self.SYNTHETIC_ASSETS)} synthetic = {len(self.books)} markets")

    def _normalize_pair(self, pair: str) -> str:
        """Normalize pair name: QBC-QUSD -> QBC/QUSD."""
        if "/" not in pair and "-" in pair:
            pair = pair.replace("-", "/", 1)
        return pair

    def deposit(self, address: str, asset: str, amount: float) -> dict[str, Any]:
        """Credit exchange balance after verifying sufficient on-chain balance.

        For QBC deposits: verifies the depositor holds at least `amount` QBC on the
        L1 UTXO/account layer before crediting their exchange balance.  This prevents
        phantom deposits where a user claims more balance than they own on-chain.

        The custodial model still requires the user to first send QBC to the exchange
        treasury address (node's miner address) on-chain.  This check ensures the
        deposited amount does not exceed their actual on-chain holdings at call time.
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        dec_amount = Decimal(str(amount))

        # On-chain balance verification for QBC (real L1 asset)
        if asset == "QBC" and self._db is not None:
            try:
                on_chain = self._db.get_balance(address)
                if on_chain < dec_amount:
                    raise ValueError(
                        f"Insufficient on-chain QBC balance: address has {on_chain} QBC, "
                        f"attempted deposit of {dec_amount} QBC"
                    )
            except Exception as e:
                # Re-raise value errors (insufficient balance); log other DB errors
                if isinstance(e, ValueError):
                    raise
                logger.warning(f"Exchange deposit: on-chain balance check failed for {address[:12]}...: {e}")

        self.balances[address][asset] += dec_amount
        logger.info(f"Exchange deposit: {address[:12]}... +{amount} {asset}")
        return {
            "status": "deposited",
            "address": address,
            "asset": asset,
            "amount": amount,
            "balance": float(self.balances[address][asset]),
        }

    def withdraw(self, address: str, asset: str, amount: float) -> dict[str, Any]:
        """Deduct exchange balance and, for QBC withdrawals, create a real on-chain UTXO tx.

        For QBC withdrawals: after deducting the exchange balance, calls
        `_send_qbc_on_chain` which selects UTXOs from the node treasury (miner address),
        marks them spent, creates a change UTXO, and records the transaction in the DB.
        This makes withdrawals real — funds actually move on-chain.

        For non-QBC assets (QUSD, synthetic tokens): balance-only update (these assets
        settle through their own smart-contract mechanisms).
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        dec_amount = Decimal(str(amount))
        if self.balances[address][asset] < dec_amount:
            raise ValueError(f"Insufficient exchange balance: have {self.balances[address][asset]}, need {dec_amount}")

        self.balances[address][asset] -= dec_amount

        tx_hash: str | None = None
        if asset == "QBC" and self._db is not None:
            try:
                tx_hash = self._send_qbc_on_chain(to_address=address, amount=dec_amount)
            except Exception as e:
                # Rollback exchange balance deduction on tx failure
                self.balances[address][asset] += dec_amount
                raise ValueError(f"On-chain QBC transfer failed: {e}") from e

        result: dict[str, Any] = {
            "status": "withdrawn",
            "address": address,
            "asset": asset,
            "amount": amount,
            "balance": float(self.balances[address][asset]),
        }
        if tx_hash:
            result["tx_hash"] = tx_hash
        return result

    def _send_qbc_on_chain(self, to_address: str, amount: Decimal) -> str:
        """Create and commit a real L1 UTXO transaction from the node treasury to `to_address`.

        Selects UTXOs belonging to the node's miner address (Config.ADDRESS), marks them
        spent in a single DB transaction (SELECT FOR UPDATE to prevent TOCTOU races),
        creates a change UTXO if needed, and records the transaction row.

        Returns the deterministic tx_hash (sha256 of inputs+outputs).
        Raises ValueError if the treasury has insufficient UTXOs.
        """
        import hashlib
        import json as _json
        import time as _time
        from sqlalchemy import text as sa_text
        from ..config import Config

        treasury = Config.ADDRESS
        if not treasury:
            raise ValueError("Exchange treasury address (Config.ADDRESS) is not configured")

        to_addr = to_address.replace("0x", "").lower()

        with self._db.get_session() as session:
            # Two-phase UTXO selection: estimate first (no lock), then lock only what we need
            estimate_rows = session.execute(
                sa_text("""
                    SELECT txid, vout, amount FROM utxos
                    WHERE address = :addr AND spent = false
                    ORDER BY amount DESC
                    LIMIT 500
                """),
                {"addr": treasury},
            ).fetchall()

            if not estimate_rows:
                raise ValueError("Exchange treasury has no UTXOs available for withdrawal")

            needed = 0
            running = Decimal("0")
            for r in estimate_rows:
                needed += 1
                running += Decimal(str(r[2]))
                if running >= amount:
                    break

            if running < amount:
                raise ValueError(
                    f"Exchange treasury has insufficient UTXOs: have {running} QBC in top-500, need {amount}"
                )

            lock_limit = min(needed + 5, len(estimate_rows))
            rows = session.execute(
                sa_text("""
                    SELECT txid, vout, amount FROM utxos
                    WHERE address = :addr AND spent = false
                    ORDER BY amount DESC
                    LIMIT :lim
                    FOR UPDATE
                """),
                {"addr": treasury, "lim": lock_limit},
            ).fetchall()

            selected: list[tuple] = []
            total = Decimal("0")
            for r in rows:
                selected.append(r)
                total += Decimal(str(r[2]))
                if total >= amount:
                    break

            if total < amount:
                raise ValueError(f"Exchange treasury insufficient after lock: have {total}, need {amount}")

            change = total - amount

            # Deterministic txid
            input_nonce = ":".join(f"{r[0]}:{r[1]}" for r in selected)
            tx_hash = hashlib.sha256(
                f"{treasury}:{to_addr}:{amount}:{input_nonce}".encode()
            ).hexdigest()

            # Mark UTXOs spent (batch UPDATE)
            pair_clauses = " OR ".join(
                f"(txid = '{r[0]}' AND vout = {r[1]})" for r in selected
            )
            result = session.execute(
                sa_text(
                    f"UPDATE utxos SET spent = true, spent_by = :txid "
                    f"WHERE ({pair_clauses}) AND spent = false"
                ),
                {"txid": tx_hash},
            )
            if result.rowcount != len(selected):
                raise ValueError(
                    f"UTXO conflict during withdrawal: expected {len(selected)} updates, got {result.rowcount}"
                )

            # Change UTXO back to treasury
            if change > 0:
                session.execute(
                    sa_text("""
                        INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                        VALUES (:txid, 0, :amt, :addr, '{}', :h, false)
                    """),
                    {
                        "txid": tx_hash,
                        "amt": str(change),
                        "addr": treasury,
                        "h": self._db.get_current_height(),
                    },
                )

            # Create recipient UTXO
            session.execute(
                sa_text("""
                    INSERT INTO utxos (txid, vout, amount, address, proof, block_height, spent)
                    VALUES (:txid, 1, :amt, :addr, '{}', :h, false)
                """),
                {
                    "txid": tx_hash,
                    "amt": str(amount),
                    "addr": to_addr,
                    "h": self._db.get_current_height(),
                },
            )

            # Record transaction
            outputs = [{"address": to_addr, "amount": str(amount)}]
            if change > 0:
                outputs.append({"address": treasury, "amount": str(change)})
            session.execute(
                sa_text("""
                    INSERT INTO transactions (txid, inputs, outputs, fee, signature, public_key,
                                              timestamp, status, tx_type, to_address, data,
                                              gas_limit, gas_price, nonce)
                    VALUES (:txid, CAST(:inputs AS jsonb), CAST(:outputs AS jsonb), 0, '', '',
                            :ts, 'confirmed', 'exchange_withdrawal', :to_addr, '', 0, 0, 0)
                    ON CONFLICT (txid) DO NOTHING
                """),
                {
                    "txid": tx_hash,
                    "inputs": _json.dumps([{"txid": r[0], "vout": r[1]} for r in selected]),
                    "outputs": _json.dumps(outputs),
                    "ts": _time.time(),
                    "to_addr": to_addr,
                },
            )
            session.commit()

        logger.info(
            f"Exchange withdrawal: treasury→{to_addr[:12]}... {amount} QBC (tx={tx_hash[:12]})"
        )
        return tx_hash

    def get_user_balance(self, address: str) -> dict[str, Any]:
        bals = {k: float(v) for k, v in self.balances[address].items() if v > 0}
        return {"address": address, "balances": bals}

    def place_order(self, pair: str, side: str, order_type: str, price: float, size: float, address: str = "") -> dict[str, Any]:
        pair = self._normalize_pair(pair)
        book = self.books.get(pair)
        if not book:
            raise ValueError(f"Unknown pair: {pair}")

        side_enum = Side(side)
        type_enum = OrderType(order_type)
        dec_price = Decimal(str(price)) if price else Decimal("0")
        dec_size = Decimal(str(size))

        if dec_size < book.config.min_order:
            raise ValueError(f"Min order size is {book.config.min_order} {book.config.base}")

        # Check balance for the order
        if address:
            if side_enum == Side.BUY:
                required_asset = book.config.quote
                required_amount = dec_price * dec_size if type_enum == OrderType.LIMIT else dec_size * Decimal("999999")
            else:
                required_asset = book.config.base
                required_amount = dec_size

            available = self.balances[address].get(required_asset, Decimal("0"))
            if available < required_amount and type_enum == OrderType.LIMIT:
                raise ValueError(f"Insufficient {required_asset}: have {available}, need {required_amount}")

        self._order_count += 1
        order = Order(
            id=f"ord-{self._order_count:08d}",
            pair=pair,
            side=side_enum,
            order_type=type_enum,
            price=dec_price,
            size=dec_size,
            address=address,
            timestamp=time.time(),
        )

        fills = book.add_order(order)

        # Update balances for fills
        for fill in fills:
            self._settle_fill(book.config, fill)

        return {
            "order": order.to_dict(),
            "fills": [f.to_dict() for f in fills],
            "filled_size": float(order.filled),
            "remaining_size": float(order.remaining),
        }

    def _settle_fill(self, config: MarketConfig, trade: Trade) -> None:
        """Settle a trade between maker and taker."""
        maker = None
        taker = None
        for book in self.books.values():
            if trade.maker_order_id in book._all_orders:
                maker = book._all_orders[trade.maker_order_id]
            if trade.taker_order_id in book._all_orders:
                taker = book._all_orders[trade.taker_order_id]

        if not maker or not taker:
            return

        quote_amount = trade.price * trade.size

        if trade.side == Side.BUY:
            # Taker buys base, pays quote
            if taker.address:
                self.balances[taker.address][config.quote] -= quote_amount
                self.balances[taker.address][config.base] += trade.size
            if maker.address:
                self.balances[maker.address][config.base] -= trade.size
                self.balances[maker.address][config.quote] += quote_amount
        else:
            # Taker sells base, receives quote
            if taker.address:
                self.balances[taker.address][config.base] -= trade.size
                self.balances[taker.address][config.quote] += quote_amount
            if maker.address:
                self.balances[maker.address][config.quote] -= quote_amount
                self.balances[maker.address][config.base] += trade.size

    def cancel_order(self, pair: str, order_id: str, owner_address: str = "") -> bool:
        pair = self._normalize_pair(pair)
        book = self.books.get(pair)
        if not book:
            return False
        return book.cancel_order(order_id, owner_address)

    def cancel_order_any_pair(self, order_id: str, owner_address: str = "") -> bool:
        for book in self.books.values():
            if order_id in book._all_orders:
                return book.cancel_order(order_id, owner_address)
        return False

    def get_markets(self) -> list[dict]:
        return [book.get_market_summary() for book in self.books.values()]

    def get_orderbook(self, pair: str, depth: int = 20) -> dict[str, Any]:
        pair = self._normalize_pair(pair)
        book = self.books.get(pair)
        if not book:
            return {"pair": pair, "bids": [], "asks": [], "spread": 0, "midPrice": 0}
        return book.get_orderbook(depth)

    def get_recent_trades(self, pair: str, limit: int = 50) -> list[dict]:
        pair = self._normalize_pair(pair)
        book = self.books.get(pair)
        if not book:
            return []
        return book.get_recent_trades(limit)

    def get_user_orders(self, address: str) -> list[dict]:
        orders = []
        for book in self.books.values():
            for o in book.bids + book.asks:
                if o.address == address and o.status in (OrderStatus.OPEN, OrderStatus.PARTIAL):
                    orders.append(o.to_dict())
        return orders

    def get_engine_stats(self) -> dict[str, Any]:
        total_orders = sum(len(b._all_orders) for b in self.books.values())
        total_trades = sum(len(b._trades) for b in self.books.values())
        open_orders = sum(len(b.bids) + len(b.asks) for b in self.books.values())
        return {
            "pairs": len(self.books),
            "total_orders": total_orders,
            "total_trades": total_trades,
            "open_orders": open_orders,
            "markets": list(self.books.keys()),
        }

    def get_synthetic_assets(self) -> list[dict[str, Any]]:
        """Return all registered synthetic assets with current oracle prices."""
        assets = []
        for sym, info in self._synthetic_registry.items():
            assets.append({
                **info,
                "pair": f"{sym}/QUSD",
                "oracle_price": self.oracle_prices.get(sym, 0),
            })
        return assets
