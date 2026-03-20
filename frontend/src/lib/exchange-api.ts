/**
 * Exchange API Service Layer
 *
 * Typed fetch functions for the Qubitcoin DEX.
 * Switches between mock data and real backend API via NEXT_PUBLIC_EXCHANGE_MOCK.
 *
 * Default: live mode (USE_MOCK = false). Set NEXT_PUBLIC_EXCHANGE_MOCK=true
 * to use mock data during frontend-only development.
 */

import { RPC_URL } from "./constants";

// ---------------------------------------------------------------------------
// Environment switch — defaults to live backend
// ---------------------------------------------------------------------------

const USE_MOCK = process.env.NEXT_PUBLIC_EXCHANGE_MOCK === "true";

// ---------------------------------------------------------------------------
// Types (backend-aligned, simpler than the full frontend exchange types)
// ---------------------------------------------------------------------------

export interface Market {
  pair: string;
  base: string;
  quote: string;
  lastPrice: number;
  change24h: number;
  volume24h: number;
  high24h: number;
  low24h: number;
  tradeCount24h: number;
  bidCount: number;
  askCount: number;
  bestBid: number;
  bestAsk: number;
  trades24h: number;
  oraclePrice: number;
}

export interface OrderBookEntry {
  price: number;
  size: number;
  total: number;
  orderCount: number;
}

export interface OrderBookData {
  pair: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  spread: number;
  spreadPct: number;
  midPrice: number;
  updatedAt: number;
}

export interface TradeEntry {
  id: string;
  pair: string;
  price: number;
  size: number;
  side: "buy" | "sell";
  maker_order_id: string;
  taker_order_id: string;
  maker_address: string;
  taker_address: string;
  timestamp: number;
}

export interface OrderEntry {
  id: string;
  pair: string;
  side: "buy" | "sell";
  type: "limit" | "market";
  price: number;
  size: number;
  filled: number;
  remaining: number;
  status: "open" | "partial" | "filled" | "cancelled";
  address: string;
  timestamp: number;
}

export interface NewOrder {
  pair: string;
  side: "buy" | "sell";
  type: "limit" | "market";
  price: number;
  size: number;
  address: string;
}

export interface PlaceOrderResult {
  order: OrderEntry;
  fills: TradeEntry[];
  fillCount: number;
}

export interface BalanceEntry {
  asset: string;
  total: number;
  available: number;
  inOrders: number;
}

export interface UserBalance {
  address: string;
  balances: BalanceEntry[];
}

export interface ExchangeStats {
  pairs: number;
  pair_list: string[];
  total_bid_orders: number;
  total_ask_orders: number;
  total_trades: number;
  total_users: number;
}

// ---------------------------------------------------------------------------
// Fetch helper (real backend)
// ---------------------------------------------------------------------------

async function exchangeFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${RPC_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Exchange API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

function mockMarkets(): Market[] {
  const pairs = [
    { pair: "QBC/QUSD", base: "QBC", last: 1.0, change: 3.42, vol: 1_284_521, high: 1.05, low: 0.95, oracle: 1.0 },
    { pair: "wQBC/QUSD", base: "wQBC", last: 1.0, change: 3.38, vol: 421_800, high: 1.04, low: 0.96, oracle: 1.0 },
    { pair: "sBTC/QUSD", base: "sBTC", last: 70000, change: -1.28, vol: 8_421_000, high: 71000, low: 69000, oracle: 70000 },
    { pair: "sETH/QUSD", base: "sETH", last: 2140, change: 0.87, vol: 2_142_300, high: 2180, low: 2100, oracle: 2140 },
    { pair: "sSOL/QUSD", base: "sSOL", last: 89, change: 5.21, vol: 4_821_700, high: 92, low: 86, oracle: 89 },
  ];
  return pairs.map((p) => ({
    pair: p.pair,
    base: p.base,
    quote: "QUSD",
    lastPrice: p.last,
    change24h: p.change,
    volume24h: p.vol,
    high24h: p.high,
    low24h: p.low,
    tradeCount24h: Math.floor(p.vol / (p.last * 50)),
    bidCount: 30 + Math.floor(Math.random() * 20),
    askCount: 30 + Math.floor(Math.random() * 20),
    bestBid: 0,
    bestAsk: 0,
    trades24h: 0,
    oraclePrice: p.oracle,
  }));
}

function mockOrderBook(pair: string): OrderBookData {
  const basePrices: Record<string, number> = {
    QBC_QUSD: 0.2847,
    WETH_QUSD: 3421.0,
    WBNB_QUSD: 412.8,
    WSOL_QUSD: 172.4,
    WQBC_QUSD: 0.2844,
  };
  const mid = basePrices[pair] ?? 1.0;
  const tick = mid < 1 ? 0.0001 : mid < 100 ? 0.01 : 0.1;

  const bids: OrderBookEntry[] = [];
  const asks: OrderBookEntry[] = [];
  let bidTotal = 0;
  let askTotal = 0;

  for (let i = 0; i < 20; i++) {
    const bidSize = Math.round((500 + Math.random() * 50000) / (1 + i * 0.03));
    const askSize = Math.round((500 + Math.random() * 50000) / (1 + i * 0.03));
    bidTotal += bidSize;
    askTotal += askSize;
    bids.push({
      price: mid - tick * (i + 1),
      size: bidSize,
      total: bidTotal,
      orderCount: 1 + Math.floor(Math.random() * 8),
    });
    asks.push({
      price: mid + tick * (i + 1),
      size: askSize,
      total: askTotal,
      orderCount: 1 + Math.floor(Math.random() * 8),
    });
  }

  const spread = asks[0].price - bids[0].price;
  return {
    pair,
    bids,
    asks,
    spread,
    spreadPct: (spread / mid) * 100,
    midPrice: mid,
    updatedAt: Date.now() / 1000,
  };
}

function mockTrades(pair: string, limit: number): TradeEntry[] {
  const basePrices: Record<string, number> = {
    QBC_QUSD: 0.2847,
    WETH_QUSD: 3421.0,
    WBNB_QUSD: 412.8,
    WSOL_QUSD: 172.4,
    WQBC_QUSD: 0.2844,
  };
  const mid = basePrices[pair] ?? 1.0;
  const trades: TradeEntry[] = [];
  const now = Date.now() / 1000;

  for (let i = 0; i < limit; i++) {
    const price = mid * (1 + (Math.random() - 0.5) * 0.005);
    trades.push({
      id: Math.random().toString(36).slice(2, 18),
      pair,
      price,
      size: Math.round(Math.random() * 10000 * 100) / 100,
      side: Math.random() > 0.5 ? "buy" : "sell",
      maker_order_id: Math.random().toString(36).slice(2, 18),
      taker_order_id: Math.random().toString(36).slice(2, 18),
      maker_address: "qbc1mock" + Math.random().toString(36).slice(2, 10),
      taker_address: "qbc1mock" + Math.random().toString(36).slice(2, 10),
      timestamp: now - i * (1 + Math.random() * 5),
    });
  }
  return trades;
}

function mockUserOrders(address: string): OrderEntry[] {
  const pairs = ["QBC_QUSD", "WETH_QUSD", "WSOL_QUSD"];
  const basePrices: Record<string, number> = {
    QBC_QUSD: 0.2847,
    WETH_QUSD: 3421.0,
    WSOL_QUSD: 172.4,
  };
  return pairs.slice(0, 3).map((pair, i) => {
    const mid = basePrices[pair] ?? 1.0;
    const side = i % 2 === 0 ? ("buy" as const) : ("sell" as const);
    const price =
      side === "buy" ? mid * (1 - Math.random() * 0.03) : mid * (1 + Math.random() * 0.03);
    const size = Math.round(100 + Math.random() * 10000);
    return {
      id: Math.random().toString(36).slice(2, 18),
      pair,
      side,
      type: "limit" as const,
      price,
      size,
      filled: 0,
      remaining: size,
      status: "open" as const,
      address,
      timestamp: Date.now() / 1000 - Math.random() * 3600,
    };
  });
}

function mockUserBalance(address: string): UserBalance {
  return {
    address,
    balances: [
      { asset: "QUSD", total: 8421.85, available: 5621.85, inOrders: 2800.0 },
      { asset: "QBC", total: 4281.44, available: 4281.44, inOrders: 0 },
      { asset: "wETH", total: 0.8421, available: 0.8421, inOrders: 0 },
      { asset: "wBNB", total: 8.42, available: 8.42, inOrders: 0 },
      { asset: "wSOL", total: 10.5, available: 10.5, inOrders: 0 },
    ],
  };
}

function mockPlaceOrder(order: NewOrder): PlaceOrderResult {
  const now = Date.now() / 1000;
  return {
    order: {
      id: Math.random().toString(36).slice(2, 18),
      pair: order.pair,
      side: order.side,
      type: order.type,
      price: order.price,
      size: order.size,
      filled: 0,
      remaining: order.size,
      status: "open",
      address: order.address,
      timestamp: now,
    },
    fills: [],
    fillCount: 0,
  };
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Get all active trading pairs with summary statistics. */
export async function getMarkets(): Promise<Market[]> {
  if (USE_MOCK) return mockMarkets();
  const res = await exchangeFetch<{ markets: Market[] }>("/exchange/markets");
  return res.markets;
}

/** Get order book for a specific pair. */
export async function getOrderBook(pair: string, depth = 20): Promise<OrderBookData> {
  if (USE_MOCK) return mockOrderBook(pair);
  return exchangeFetch<OrderBookData>(`/exchange/orderbook/${pair}?depth=${depth}`);
}

/** Get recent trades for a specific pair. */
export async function getRecentTrades(pair: string, limit = 50): Promise<TradeEntry[]> {
  if (USE_MOCK) return mockTrades(pair, limit);
  const res = await exchangeFetch<{ trades: TradeEntry[] }>(
    `/exchange/trades/${pair}?limit=${limit}`,
  );
  return res.trades;
}

/** Get all open orders for a user address across all pairs. */
export async function getUserOrders(address: string): Promise<OrderEntry[]> {
  if (USE_MOCK) return mockUserOrders(address);
  const res = await exchangeFetch<{ orders: OrderEntry[] }>(`/exchange/orders/${address}`);
  return res.orders;
}

/** Place a new order (limit or market). */
export async function placeOrder(order: NewOrder): Promise<PlaceOrderResult> {
  if (USE_MOCK) return mockPlaceOrder(order);
  return exchangeFetch<PlaceOrderResult>("/exchange/order", {
    method: "POST",
    body: JSON.stringify(order),
  });
}

/** Cancel an open order by ID. Optionally specify pair for faster lookup. */
export async function cancelOrder(orderId: string, pair?: string): Promise<void> {
  if (USE_MOCK) return;
  const qs = pair ? `?pair=${pair}` : "";
  await exchangeFetch<{ status: string; order_id: string }>(
    `/exchange/order/${orderId}${qs}`,
    { method: "DELETE" },
  );
}

/** Get a user's exchange balances (deposited funds). */
export async function getUserBalance(address: string): Promise<UserBalance> {
  if (USE_MOCK) return mockUserBalance(address);
  return exchangeFetch<UserBalance>(`/exchange/balance/${address}`);
}

/** Deposit funds into the exchange. */
export async function deposit(
  address: string,
  asset: string,
  amount: number,
): Promise<UserBalance> {
  if (USE_MOCK) return mockUserBalance(address);
  return exchangeFetch<UserBalance>("/exchange/deposit", {
    method: "POST",
    body: JSON.stringify({ address, asset, amount }),
  });
}

/** Withdraw funds from the exchange. */
export async function withdraw(
  address: string,
  asset: string,
  amount: number,
): Promise<UserBalance> {
  if (USE_MOCK) return mockUserBalance(address);
  return exchangeFetch<UserBalance>("/exchange/withdraw", {
    method: "POST",
    body: JSON.stringify({ address, asset, amount }),
  });
}

/** Get overall exchange engine statistics. */
export async function getExchangeStats(): Promise<ExchangeStats> {
  if (USE_MOCK) {
    return {
      pairs: 5,
      pair_list: ["QBC_QUSD", "WETH_QUSD", "WBNB_QUSD", "WSOL_QUSD", "WQBC_QUSD"],
      total_bid_orders: 150,
      total_ask_orders: 150,
      total_trades: 500,
      total_users: 42,
    };
  }
  return exchangeFetch<ExchangeStats>("/exchange/stats");
}

/** Convenience object grouping all exchange API functions. */
export const exchangeApi = {
  getMarkets,
  getOrderBook,
  getRecentTrades,
  getUserOrders,
  placeOrder,
  cancelOrder,
  getUserBalance,
  deposit,
  withdraw,
  getExchangeStats,
} as const;
