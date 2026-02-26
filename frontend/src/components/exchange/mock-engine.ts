// ─── QBC EXCHANGE — Mock Data Engine ─────────────────────────────────────────
// Deterministic seeded PRNG. All data types. Zero empty states.

import type {
  MarketId, Market, OHLCBar, OrderBook, OrderBookLevel, Trade, Order,
  Position, Balance, FundingPayment, LiquidationLevel, EquitySnapshot,
  SusySignal, VqeOracle, ValidatorStatus, QeviData, Timeframe,
} from "./types";
import { MARKET_CONFIGS, BASE_PRICES, ASSET_VOLATILITY, getBasePrice } from "./config";

// ─── SEEDED PRNG (mulberry32) ───────────────────────────────────────────────

function mulberry32(seed: number) {
  return function () {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ─── SINGLETON ──────────────────────────────────────────────────────────────

class MockDataEngine {
  private rng: () => number;
  private markets: Map<MarketId, Market> = new Map();
  private ohlcCache: Map<string, OHLCBar[]> = new Map();
  private orderBooks: Map<MarketId, OrderBook> = new Map();
  private trades: Map<MarketId, Trade[]> = new Map();
  private tickCounter = 0;

  constructor(seed = 42) {
    this.rng = mulberry32(seed);
    this.initMarkets();
    this.initOrderBooks();
    this.initTrades();
  }

  // ─── MARKET GENERATION ──────────────────────────────────────────────────

  private initMarkets() {
    for (const cfg of MARKET_CONFIGS) {
      if (!cfg.enabled) continue;
      const basePrice = getBasePrice(cfg.baseAsset);
      const vol = ASSET_VOLATILITY[cfg.baseAsset] ?? 0.05;
      const change24h = (this.rng() - 0.45) * vol * 2;
      const open = basePrice / (1 + change24h);
      const high = basePrice * (1 + this.rng() * vol * 0.3);
      const low = basePrice * (1 - this.rng() * vol * 0.3);
      const volume = this.randomRange(100000, 20000000);
      const fundingRate = cfg.type === "perp" ? (this.rng() - 0.4) * 0.005 : 0;

      const market: Market = {
        id: cfg.id as MarketId,
        baseAsset: cfg.baseAsset,
        quoteAsset: "QUSD",
        type: cfg.type,
        displayName: cfg.type === "perp" ? cfg.baseAsset + "-PERP" : cfg.baseAsset + "/QUSD",
        lastPrice: basePrice,
        indexPrice: basePrice * (1 + (this.rng() - 0.5) * 0.002),
        markPrice: basePrice * (1 + (this.rng() - 0.5) * 0.001),
        fundingRate,
        nextFundingTs: Date.now() + Math.floor(this.rng() * 3600000),
        openInterest: cfg.type === "perp" ? this.randomRange(500000, 15000000) : 0,
        price24hOpen: open,
        price24hHigh: Math.max(high, basePrice),
        price24hLow: Math.min(low, basePrice),
        volume24h: volume,
        volume24hUsd: volume * basePrice,
        priceChange24h: basePrice - open,
        priceChangePct24h: change24h * 100,
        maxLeverage: cfg.maxLeverage,
        minOrderSize: cfg.minOrderSize,
        tickSize: cfg.tickSize,
        stepSize: cfg.stepSize,
        decimals: cfg.tickSize < 0.001 ? 4 : 2,
        sizeDecimals: cfg.stepSize < 0.01 ? 4 : 2,
        baseIcon: cfg.baseAsset.charAt(0),
        marketCap: basePrice * this.randomRange(1e8, 1e10),
      };
      this.markets.set(cfg.id as MarketId, market);
    }
  }

  // ─── OHLC GENERATION ────────────────────────────────────────────────────

  generateOHLC(marketId: MarketId, timeframe: Timeframe): OHLCBar[] {
    const key = `${marketId}_${timeframe}`;
    if (this.ohlcCache.has(key)) return this.ohlcCache.get(key)!;

    const market = this.markets.get(marketId);
    if (!market) return [];

    const rng = mulberry32(this.hashStr(key));
    const vol = ASSET_VOLATILITY[market.baseAsset] ?? 0.05;
    const bars: OHLCBar[] = [];
    const count = 500;
    const intervalMs = this.tfToMs(timeframe);
    const now = Date.now();

    let price = market.lastPrice * (0.85 + rng() * 0.3);

    for (let i = 0; i < count; i++) {
      const time = Math.floor((now - (count - i) * intervalMs) / 1000);
      const dailyVol = vol * Math.sqrt(intervalMs / 86400000);
      const drift = (rng() - 0.48) * dailyVol;
      const open = price;
      const close = open * (1 + drift);
      const wick1 = open * (1 + Math.abs(rng() - 0.5) * dailyVol * 0.5);
      const wick2 = open * (1 - Math.abs(rng() - 0.5) * dailyVol * 0.5);
      const high = Math.max(open, close, wick1);
      const low = Math.min(open, close, wick2);
      const volume = this.randomRangeSeeded(rng, 10000, 2000000) * (1 + Math.abs(drift) * 10);

      bars.push({ time, open, high, low, close, volume });
      price = close;
    }

    // Adjust last bar to match current market price
    if (bars.length > 0) {
      const last = bars[bars.length - 1];
      last.close = market.lastPrice;
      last.high = Math.max(last.high, last.close);
      last.low = Math.min(last.low, last.close);
    }

    this.ohlcCache.set(key, bars);
    return bars;
  }

  // ─── ORDER BOOK GENERATION ──────────────────────────────────────────────

  private initOrderBooks() {
    for (const [id, market] of this.markets) {
      this.orderBooks.set(id, this.generateOrderBook(market));
    }
  }

  private generateOrderBook(market: Market): OrderBook {
    const mid = market.lastPrice;
    const tick = market.tickSize;
    const rng = mulberry32(this.hashStr(market.id + "_ob"));
    const levels = 50;

    const bids: OrderBookLevel[] = [];
    const asks: OrderBookLevel[] = [];
    let bidTotal = 0;
    let askTotal = 0;

    for (let i = 0; i < levels; i++) {
      const bidPrice = mid - tick * (i + 1);
      const askPrice = mid + tick * (i + 1);
      // More size near mid-price, larger at round numbers
      const baseSz = this.randomRangeSeeded(rng, 500, 50000);
      const roundBonus = this.isRoundNumber(bidPrice, tick * 10) ? 2.5 : 1;
      const distFactor = 1 / (1 + i * 0.03);

      const bidSize = Math.round(baseSz * roundBonus * distFactor);
      const askSize = Math.round(this.randomRangeSeeded(rng, 500, 50000) * roundBonus * distFactor);

      bidTotal += bidSize;
      askTotal += askSize;

      bids.push({ price: bidPrice, size: bidSize, total: bidTotal, orderCount: Math.ceil(rng() * 8) + 1, myOrderSize: 0 });
      asks.push({ price: askPrice, size: askSize, total: askTotal, orderCount: Math.ceil(rng() * 8) + 1, myOrderSize: 0 });
    }

    const spread = asks[0].price - bids[0].price;
    return {
      marketId: market.id,
      bids,
      asks,
      spread,
      spreadPct: (spread / mid) * 100,
      midPrice: mid,
      updatedAt: Date.now(),
    };
  }

  // ─── TRADE GENERATION ───────────────────────────────────────────────────

  private initTrades() {
    for (const [id, market] of this.markets) {
      const rng = mulberry32(this.hashStr(id + "_trades"));
      const trds: Trade[] = [];
      for (let i = 0; i < 100; i++) {
        const price = market.lastPrice * (1 + (rng() - 0.5) * 0.005);
        const size = this.randomRangeSeeded(rng, market.minOrderSize, market.minOrderSize * 10000);
        trds.push({
          id: this.hexId(rng),
          marketId: id,
          price,
          size: Math.round(size * 100) / 100,
          side: rng() > 0.5 ? "buy" : "sell",
          timestamp: Date.now() - i * (1000 + Math.floor(rng() * 5000)),
          txHash: "0xqbc" + this.hexId(rng) + this.hexId(rng),
          isLarge: rng() > 0.95,
        });
      }
      this.trades.set(id, trds);
    }
  }

  // ─── POSITIONS ──────────────────────────────────────────────────────────

  generatePositions(): Position[] {
    const positions: Position[] = [];
    const perpMarkets = Array.from(this.markets.values()).filter((m) => m.type === "perp");

    // Generate 2-3 demo positions
    for (let i = 0; i < Math.min(3, perpMarkets.length); i++) {
      const market = perpMarkets[i];
      const side = i % 2 === 0 ? "long" : "short" as const;
      const leverage = Math.ceil(this.rng() * 10) + 1;
      const size = this.randomRange(1000, 50000);
      const entryDeviation = (this.rng() - 0.5) * 0.08;
      const entryPrice = market.lastPrice * (1 + entryDeviation);
      const mark = market.markPrice;
      const notional = size * mark;
      const initialMargin = notional / leverage;
      const maintenanceMargin = notional * 0.005;
      const unrealisedPnl = side === "long"
        ? (mark - entryPrice) * size
        : (entryPrice - mark) * size;
      const liqPrice = side === "long"
        ? entryPrice * (1 - 1 / leverage + 0.005)
        : entryPrice * (1 + 1 / leverage - 0.005);
      const equity = initialMargin + unrealisedPnl;
      const marginRatio = equity > 0 ? maintenanceMargin / equity : 1;

      positions.push({
        marketId: market.id,
        side,
        size,
        entryPrice,
        markPrice: mark,
        liquidationPrice: liqPrice,
        leverage,
        notionalValue: notional,
        initialMargin,
        maintenanceMargin,
        unrealisedPnl,
        unrealisedPnlPct: (unrealisedPnl / initialMargin) * 100,
        realisedPnl: this.randomRange(-50, 200),
        fundingPaid: this.randomRange(-5, 0),
        marginRatio,
        openedAt: Date.now() - Math.floor(this.rng() * 86400000 * 3),
        openTxHash: "0xqbc" + this.hexId(this.rng),
        openBlockHeight: 18000 + Math.floor(this.rng() * 2000),
        takeProfitPrice: null,
        stopLossPrice: null,
      });
    }
    return positions;
  }

  // ─── ORDERS ─────────────────────────────────────────────────────────────

  generateOpenOrders(): Order[] {
    const orders: Order[] = [];
    const spotMarkets = Array.from(this.markets.values()).filter((m) => m.type === "spot");

    for (let i = 0; i < 3; i++) {
      const market = spotMarkets[i % spotMarkets.length];
      const side = i % 2 === 0 ? "buy" : "sell" as const;
      const price = side === "buy"
        ? market.lastPrice * (1 - this.rng() * 0.03)
        : market.lastPrice * (1 + this.rng() * 0.03);
      const size = this.randomRange(100, 10000);

      orders.push({
        id: this.hexId(this.rng),
        marketId: market.id,
        side,
        type: "limit",
        status: "open",
        price,
        triggerPrice: null,
        size,
        filledSize: 0,
        remainingSize: size,
        avgFillPrice: null,
        fee: 0,
        tif: "gtc",
        reduceOnly: false,
        postOnly: false,
        createdAt: Date.now() - Math.floor(this.rng() * 3600000),
        updatedAt: Date.now(),
        txHash: "0xqbc" + this.hexId(this.rng),
        dilithiumSig: "0x4c9e" + this.hexId(this.rng) + this.hexId(this.rng),
      });
    }
    return orders;
  }

  // ─── TRADE HISTORY (My Fills) ───────────────────────────────────────────

  generateMyFills(): Order[] {
    const fills: Order[] = [];
    for (let i = 0; i < 15; i++) {
      const markets = Array.from(this.markets.values());
      const market = markets[Math.floor(this.rng() * markets.length)];
      const side = this.rng() > 0.5 ? "buy" : "sell" as const;
      const size = this.randomRange(50, 5000);
      const price = market.lastPrice * (1 + (this.rng() - 0.5) * 0.01);
      const fee = size * price * (this.rng() > 0.5 ? 0.0002 : 0.0005);

      fills.push({
        id: this.hexId(this.rng),
        marketId: market.id,
        side,
        type: this.rng() > 0.6 ? "limit" : "market",
        status: "filled",
        price,
        triggerPrice: null,
        size,
        filledSize: size,
        remainingSize: 0,
        avgFillPrice: price,
        fee,
        tif: "gtc",
        reduceOnly: false,
        postOnly: false,
        createdAt: Date.now() - Math.floor(this.rng() * 86400000),
        updatedAt: Date.now() - Math.floor(this.rng() * 86400000),
        txHash: "0xqbc" + this.hexId(this.rng),
        dilithiumSig: "0x4c9e" + this.hexId(this.rng),
      });
    }
    return fills.sort((a, b) => b.createdAt - a.createdAt);
  }

  // ─── BALANCES ───────────────────────────────────────────────────────────

  generateBalances(): Balance[] {
    return [
      { asset: "QUSD", total: 8421.847, available: 5621.85, inOrders: 2800.0, usedAsMargin: 0, usdValue: 8421.85, decimals: 6 },
      { asset: "QBC", total: 4281.44, available: 4281.44, inOrders: 0, usedAsMargin: 0, usdValue: 4281.44 * 0.2847, decimals: 8 },
      { asset: "wETH", total: 0.8421, available: 0.8421, inOrders: 0, usedAsMargin: 0, usdValue: 0.8421 * 3421, decimals: 6 },
      { asset: "wBNB", total: 8.42, available: 8.42, inOrders: 0, usedAsMargin: 0, usdValue: 8.42 * 412.8, decimals: 4 },
      { asset: "wSOL", total: 10.5, available: 10.5, inOrders: 0, usedAsMargin: 0, usdValue: 10.5 * 172.4, decimals: 4 },
    ];
  }

  // ─── FUNDING PAYMENTS ───────────────────────────────────────────────────

  generateFundingPayments(marketId: MarketId): FundingPayment[] {
    const market = this.markets.get(marketId);
    if (!market || market.type !== "perp") return [];

    const payments: FundingPayment[] = [];
    let cumulative = 0;
    for (let i = 0; i < 48; i++) {
      const rate = (this.rng() - 0.4) * 0.005;
      const posSize = 10000;
      const payment = -(posSize * market.markPrice * rate);
      cumulative += payment;
      payments.push({
        marketId,
        timestamp: Date.now() - i * 3600000,
        positionSize: posSize,
        fundingRate: rate,
        payment,
        cumulative,
      });
    }
    return payments;
  }

  // ─── LIQUIDATION LEVELS ─────────────────────────────────────────────────

  generateLiquidationLevels(marketId: MarketId): LiquidationLevel[] {
    const market = this.markets.get(marketId);
    if (!market) return [];
    const rng = mulberry32(this.hashStr(marketId + "_liq"));
    const levels: LiquidationLevel[] = [];
    const price = market.lastPrice;

    for (let i = 1; i <= 50; i++) {
      const priceLong = price * (1 - i * 0.006);
      const priceShort = price * (1 + i * 0.006);
      const densityFactor = Math.exp(-i * 0.05);
      const roundBonus = i % 5 === 0 ? 3 : 1;

      levels.push({
        price: priceLong,
        totalSize: Math.round(this.randomRangeSeeded(rng, 5000, 200000) * densityFactor * roundBonus),
        positionCount: Math.ceil(rng() * 20 * densityFactor * roundBonus),
        side: "long",
      });
      levels.push({
        price: priceShort,
        totalSize: Math.round(this.randomRangeSeeded(rng, 5000, 200000) * densityFactor * roundBonus),
        positionCount: Math.ceil(rng() * 20 * densityFactor * roundBonus),
        side: "short",
      });
    }
    return levels;
  }

  // ─── EQUITY HISTORY ─────────────────────────────────────────────────────

  generateEquityHistory(): EquitySnapshot[] {
    const snapshots: EquitySnapshot[] = [];
    let equity = 11000;
    for (let i = 30; i >= 0; i--) {
      const change = (this.rng() - 0.45) * 400;
      equity += change;
      equity = Math.max(equity, 5000);
      snapshots.push({
        timestamp: Date.now() - i * 86400000,
        totalEquity: equity,
        realisedPnl: (this.rng() - 0.3) * 100,
        unrealisedPnl: (this.rng() - 0.4) * 200,
      });
    }
    return snapshots;
  }

  // ─── QUANTUM INTELLIGENCE ───────────────────────────────────────────────

  generateSusySignal(): SusySignal {
    const score = 0.85 + this.rng() * 0.12;
    const label = score >= 0.95 ? "STRONG BULLISH" : score >= 0.80 ? "BULLISH" : score >= 0.65 ? "NEUTRAL" : "BEARISH";
    const history: SusySignal["history"] = [];
    let s = score - 0.1;
    for (let i = 168; i >= 0; i--) {
      s += (this.rng() - 0.48) * 0.01;
      s = Math.max(0.5, Math.min(1, s));
      history.push({
        time: Date.now() - i * 3600000,
        score: s,
        price: 0.2847 * (1 + (this.rng() - 0.5) * 0.02),
      });
    }
    return {
      score,
      label,
      interpretation: score >= 0.80
        ? "High SUSY alignment historically correlates with reduced volatility and upward price momentum for QBC"
        : "Current SUSY alignment suggests neutral market conditions — trade cautiously",
      history,
    };
  }

  generateVqeOracle(): VqeOracle {
    const marketPrice = 0.2847;
    const deviation = (this.rng() - 0.45) * 0.005;
    const fairValue = marketPrice * (1 + deviation);
    const history: VqeOracle["history"] = [];
    let fv = fairValue - 0.01;
    let mp = marketPrice - 0.01;
    for (let i = 48; i >= 0; i--) {
      fv += (this.rng() - 0.48) * 0.001;
      mp += (this.rng() - 0.48) * 0.001;
      history.push({ time: Date.now() - i * 1800000, fairValue: fv, marketPrice: mp });
    }
    return {
      fairValue,
      marketPrice,
      deviation: fairValue - marketPrice,
      deviationPct: ((fairValue - marketPrice) / marketPrice) * 100,
      oracleSources: 11,
      oracleTotal: 11,
      confidence: 96 + this.rng() * 4,
      lastBlock: 19247,
      lastBlockAge: Math.floor(this.rng() * 120),
      history,
    };
  }

  generateValidators(): ValidatorStatus[] {
    const names = ["Keter", "Chochmah", "Binah", "Chesed", "Gevurah", "Tiferet", "Netzach", "Hod", "Yesod", "Malkuth", "Oracle"];
    return names.map((name) => ({
      name,
      status: this.rng() > 0.08 ? "online" : this.rng() > 0.5 ? "degraded" : "offline",
      lastSeen: Date.now() - Math.floor(this.rng() * 60000),
    }));
  }

  generateQevi(): QeviData {
    const entropy = 0.00000342;
    const score = 20 + this.rng() * 15;
    const regime = score <= 30 ? "LOW VOLATILITY" : score <= 60 ? "MODERATE" : score <= 80 ? "ELEVATED" : "EXTREME";
    const history: QeviData["history"] = [];
    let q = score;
    for (let i = 168; i >= 0; i--) {
      q += (this.rng() - 0.48) * 3;
      q = Math.max(5, Math.min(95, q));
      history.push({ time: Date.now() - i * 3600000, qevi: q, realizedVol: q * 0.8 + this.rng() * 10 });
    }
    return { entropy, score, regime, history };
  }

  // ─── TICK SIMULATION ────────────────────────────────────────────────────

  tick(): void {
    this.tickCounter++;
    for (const [id, market] of this.markets) {
      const vol = ASSET_VOLATILITY[market.baseAsset] ?? 0.05;
      const tickVol = vol * 0.001;
      const change = (this.rng() - 0.5) * tickVol * market.lastPrice * 2;
      market.lastPrice = Math.max(market.lastPrice * 0.5, market.lastPrice + change);
      market.markPrice = market.lastPrice * (1 + (this.rng() - 0.5) * 0.001);
      market.indexPrice = market.lastPrice * (1 + (this.rng() - 0.5) * 0.002);
      market.price24hHigh = Math.max(market.price24hHigh, market.lastPrice);
      market.price24hLow = Math.min(market.price24hLow, market.lastPrice);
      market.priceChange24h = market.lastPrice - market.price24hOpen;
      market.priceChangePct24h = (market.priceChange24h / market.price24hOpen) * 100;

      // Refresh order book around new price
      const ob = this.orderBooks.get(id);
      if (ob) {
        this.adjustOrderBook(ob, market);
      }
    }
  }

  private adjustOrderBook(ob: OrderBook, market: Market): void {
    const mid = market.lastPrice;
    const tick = market.tickSize;
    ob.midPrice = mid;

    let bidTotal = 0;
    let askTotal = 0;
    for (let i = 0; i < ob.bids.length; i++) {
      ob.bids[i].price = mid - tick * (i + 1);
      ob.bids[i].size = Math.max(100, ob.bids[i].size + Math.round((this.rng() - 0.5) * 200));
      bidTotal += ob.bids[i].size;
      ob.bids[i].total = bidTotal;
    }
    for (let i = 0; i < ob.asks.length; i++) {
      ob.asks[i].price = mid + tick * (i + 1);
      ob.asks[i].size = Math.max(100, ob.asks[i].size + Math.round((this.rng() - 0.5) * 200));
      askTotal += ob.asks[i].size;
      ob.asks[i].total = askTotal;
    }
    ob.spread = ob.asks[0].price - ob.bids[0].price;
    ob.spreadPct = (ob.spread / mid) * 100;
    ob.updatedAt = Date.now();
  }

  // ─── ACCESSORS ──────────────────────────────────────────────────────────

  getMarket(id: MarketId): Market | undefined {
    return this.markets.get(id);
  }

  getAllMarkets(): Market[] {
    return Array.from(this.markets.values());
  }

  getOrderBook(id: MarketId): OrderBook | undefined {
    return this.orderBooks.get(id);
  }

  getTrades(id: MarketId): Trade[] {
    return this.trades.get(id) ?? [];
  }

  addTrade(id: MarketId): Trade | null {
    const market = this.markets.get(id);
    if (!market) return null;
    const trade: Trade = {
      id: this.hexId(this.rng),
      marketId: id,
      price: market.lastPrice,
      size: Math.round(this.randomRange(market.minOrderSize, market.minOrderSize * 5000) * 100) / 100,
      side: this.rng() > 0.5 ? "buy" : "sell",
      timestamp: Date.now(),
      txHash: "0xqbc" + this.hexId(this.rng),
      isLarge: this.rng() > 0.95,
    };
    const trds = this.trades.get(id) ?? [];
    trds.unshift(trade);
    if (trds.length > 100) trds.pop();
    this.trades.set(id, trds);
    return trade;
  }

  // ─── UTILITIES ──────────────────────────────────────────────────────────

  private randomRange(min: number, max: number): number {
    return min + this.rng() * (max - min);
  }

  private randomRangeSeeded(rng: () => number, min: number, max: number): number {
    return min + rng() * (max - min);
  }

  private hexId(rng: () => number): string {
    return Math.floor(rng() * 0xffffff).toString(16).padStart(6, "0");
  }

  private hashStr(s: string): number {
    let h = 0;
    for (let i = 0; i < s.length; i++) {
      h = ((h << 5) - h + s.charCodeAt(i)) | 0;
    }
    return Math.abs(h);
  }

  private isRoundNumber(price: number, granularity: number): boolean {
    return Math.abs(price % granularity) < granularity * 0.1;
  }

  private tfToMs(tf: Timeframe): number {
    const map: Record<Timeframe, number> = {
      "1m": 60000, "5m": 300000, "15m": 900000,
      "1h": 3600000, "4h": 14400000, "1D": 86400000, "1W": 604800000,
    };
    return map[tf];
  }
}

// Export singleton
export const mockEngine = new MockDataEngine(42);
