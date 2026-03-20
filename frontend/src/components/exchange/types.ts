// ─── QBC EXCHANGE — TypeScript Types ─────────────────────────────────────────
// All interfaces for the on-chain order book DEX. Strict mode. Zero `any`.

// MarketId accepts both static config IDs and dynamic pairs from the Rust exchange
// (e.g. "QBC/QUSD", "sBTC/QUSD", "QBC_QUSD", "ETH_PERP")
export type MarketId = string;

export type MarketType = "spot" | "perp";
export type OrderSide = "buy" | "sell";
export type OrderType = "limit" | "market" | "stop_limit" | "stop_market";
export type OrderStatus = "open" | "filled" | "partial" | "cancelled" | "expired";
export type PositionSide = "long" | "short";
export type TIF = "gtc" | "ioc" | "fok" | "post";
export type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1D" | "1W";
export type ExchangeView = "trading" | "portfolio";

export interface Market {
  id: MarketId;
  baseAsset: string;
  quoteAsset: string;
  type: MarketType;
  displayName: string;
  lastPrice: number;
  indexPrice: number;
  markPrice: number;
  fundingRate: number;
  nextFundingTs: number;
  openInterest: number;
  price24hOpen: number;
  price24hHigh: number;
  price24hLow: number;
  volume24h: number;
  volume24hUsd: number;
  priceChange24h: number;
  priceChangePct24h: number;
  maxLeverage: number;
  minOrderSize: number;
  tickSize: number;
  stepSize: number;
  decimals: number;
  sizeDecimals: number;
  baseIcon: string;
  marketCap: number;
}

export interface OHLCBar {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface OrderBookLevel {
  price: number;
  size: number;
  total: number;
  orderCount: number;
  myOrderSize: number;
}

export interface OrderBook {
  marketId: MarketId;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
  spread: number;
  spreadPct: number;
  midPrice: number;
  updatedAt: number;
}

export interface Trade {
  id: string;
  marketId: MarketId;
  price: number;
  size: number;
  side: OrderSide;
  timestamp: number;
  txHash: string;
  isLarge: boolean;
}

export interface Order {
  id: string;
  marketId: MarketId;
  side: OrderSide;
  type: OrderType;
  status: OrderStatus;
  price: number | null;
  triggerPrice: number | null;
  size: number;
  filledSize: number;
  remainingSize: number;
  avgFillPrice: number | null;
  fee: number;
  tif: TIF;
  reduceOnly: boolean;
  postOnly: boolean;
  createdAt: number;
  updatedAt: number;
  txHash: string;
  dilithiumSig: string;
}

export interface Position {
  marketId: MarketId;
  side: PositionSide;
  size: number;
  entryPrice: number;
  markPrice: number;
  liquidationPrice: number;
  leverage: number;
  notionalValue: number;
  initialMargin: number;
  maintenanceMargin: number;
  unrealisedPnl: number;
  unrealisedPnlPct: number;
  realisedPnl: number;
  fundingPaid: number;
  marginRatio: number;
  openedAt: number;
  openTxHash: string;
  openBlockHeight: number;
  takeProfitPrice: number | null;
  stopLossPrice: number | null;
}

export interface Balance {
  asset: string;
  total: number;
  available: number;
  inOrders: number;
  usedAsMargin: number;
  usdValue: number;
  decimals: number;
}

export interface FundingPayment {
  marketId: MarketId;
  timestamp: number;
  positionSize: number;
  fundingRate: number;
  payment: number;
  cumulative: number;
}

export interface LiquidationLevel {
  price: number;
  totalSize: number;
  positionCount: number;
  side: "long" | "short";
}

export interface EquitySnapshot {
  timestamp: number;
  totalEquity: number;
  realisedPnl: number;
  unrealisedPnl: number;
}

export interface SusySignal {
  score: number;
  label: string;
  interpretation: string;
  history: { time: number; score: number; price: number }[];
}

export interface VqeOracle {
  fairValue: number;
  marketPrice: number;
  deviation: number;
  deviationPct: number;
  oracleSources: number;
  oracleTotal: number;
  confidence: number;
  lastBlock: number;
  lastBlockAge: number;
  history: { time: number; fairValue: number; marketPrice: number }[];
}

export interface ValidatorStatus {
  name: string;
  status: "online" | "offline" | "degraded";
  lastSeen: number;
}

export interface QeviData {
  entropy: number;
  score: number;
  regime: string;
  history: { time: number; qevi: number; realizedVol: number }[];
}

export interface ExchangeSettings {
  defaultOrderType: OrderType;
  defaultTif: TIF;
  confirmOrders: boolean;
  confirmCancels: boolean;
  defaultLeverage: Record<MarketId, number>;
  currencyDisplay: "qusd" | "usd";
  candleStyle: "candle" | "hollow" | "bar" | "line";
  orderBookGrouping: number;
  orderBookRows: 10 | 20 | 50;
  timestampFormat: "relative" | "utc";
  soundEnabled: boolean;
  notifyFilled: boolean;
  notifyLiquidation: boolean;
  notifyFunding: boolean;
  rpcUrl: string;
  expertMode: boolean;
}

export interface AdminTokenConfig {
  symbol: string;
  name: string;
  chainSource: string;
  contractAddress: string;
  wrappedSymbol: string;
  decimals: number;
  icon: string;
  enabled: boolean;
}

export interface AdminMarketConfig {
  id: string;
  baseAsset: string;
  quoteAsset: string;
  type: MarketType;
  maxLeverage: number;
  tickSize: number;
  stepSize: number;
  minOrderSize: number;
  makerFee: number;
  takerFee: number;
  enabled: boolean;
}
