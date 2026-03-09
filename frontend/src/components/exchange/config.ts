// ─── QBC EXCHANGE — Market & Chain Configuration ─────────────────────────────
// Admin-extensible: add new tokens/markets by updating TOKENS and MARKET_CONFIGS.

import type { MarketId, MarketType, AdminTokenConfig, AdminMarketConfig } from "./types";

// ─── TOKEN REGISTRY (Admin-extensible) ──────────────────────────────────────
// To add a new cross-chain token:
// 1. Add entry to TOKENS array below
// 2. Add NEXT_PUBLIC_QBC_{SYMBOL}_ADDR env var
// 3. Add market(s) to MARKET_CONFIGS
// 4. Restart frontend

export const TOKENS: AdminTokenConfig[] = [
  { symbol: "QBC", name: "Qubitcoin", chainSource: "qbc", contractAddress: "native", wrappedSymbol: "QBC", decimals: 8, icon: "Q", enabled: true },
  { symbol: "QUSD", name: "QUSD Stablecoin", chainSource: "qbc", contractAddress: "native", wrappedSymbol: "QUSD", decimals: 8, icon: "$", enabled: true },
  { symbol: "wETH", name: "Wrapped Ether", chainSource: "ethereum", contractAddress: process.env.NEXT_PUBLIC_QBC_WETH_ADDR ?? "", wrappedSymbol: "wETH", decimals: 18, icon: "E", enabled: true },
  { symbol: "wBNB", name: "Wrapped BNB", chainSource: "bnb", contractAddress: process.env.NEXT_PUBLIC_QBC_WBNB_ADDR ?? "", wrappedSymbol: "wBNB", decimals: 18, icon: "B", enabled: true },
  { symbol: "wSOL", name: "Wrapped SOL", chainSource: "solana", contractAddress: process.env.NEXT_PUBLIC_QBC_WSOL_ADDR ?? "", wrappedSymbol: "wSOL", decimals: 9, icon: "S", enabled: true },
  { symbol: "wBTC", name: "Wrapped BTC", chainSource: "ethereum", contractAddress: process.env.NEXT_PUBLIC_QBC_WBTC_ADDR ?? "", wrappedSymbol: "wBTC", decimals: 8, icon: "B", enabled: true },
  { symbol: "wQBC", name: "Wrapped QBC (Return)", chainSource: "qbc", contractAddress: process.env.NEXT_PUBLIC_QBC_WQBC_ADDR ?? "", wrappedSymbol: "wQBC", decimals: 8, icon: "W", enabled: true },
  { symbol: "wUSDT", name: "Wrapped USDT", chainSource: "ethereum", contractAddress: process.env.NEXT_PUBLIC_QBC_WUSDT_ADDR ?? "", wrappedSymbol: "wUSDT", decimals: 6, icon: "T", enabled: true },
  { symbol: "wUSDC", name: "Wrapped USDC", chainSource: "ethereum", contractAddress: process.env.NEXT_PUBLIC_QBC_WUSDC_ADDR ?? "", wrappedSymbol: "wUSDC", decimals: 6, icon: "C", enabled: true },
];

// ─── MARKET CONFIGS (Admin-extensible) ──────────────────────────────────────

export const MARKET_CONFIGS: AdminMarketConfig[] = [
  // Spot markets
  { id: "QBC_QUSD", baseAsset: "QBC", quoteAsset: "QUSD", type: "spot", maxLeverage: 1, tickSize: 0.0001, stepSize: 0.01, minOrderSize: 1, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "WETH_QUSD", baseAsset: "wETH", quoteAsset: "QUSD", type: "spot", maxLeverage: 1, tickSize: 0.01, stepSize: 0.0001, minOrderSize: 0.001, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "WBNB_QUSD", baseAsset: "wBNB", quoteAsset: "QUSD", type: "spot", maxLeverage: 1, tickSize: 0.01, stepSize: 0.001, minOrderSize: 0.01, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "WSOL_QUSD", baseAsset: "wSOL", quoteAsset: "QUSD", type: "spot", maxLeverage: 1, tickSize: 0.01, stepSize: 0.001, minOrderSize: 0.01, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "WQBC_QUSD", baseAsset: "wQBC", quoteAsset: "QUSD", type: "spot", maxLeverage: 1, tickSize: 0.0001, stepSize: 0.01, minOrderSize: 1, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  // Perpetual markets
  { id: "QBC_PERP", baseAsset: "QBC", quoteAsset: "QUSD", type: "perp", maxLeverage: 20, tickSize: 0.0001, stepSize: 0.01, minOrderSize: 1, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "ETH_PERP", baseAsset: "ETH", quoteAsset: "QUSD", type: "perp", maxLeverage: 50, tickSize: 0.01, stepSize: 0.0001, minOrderSize: 0.001, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "BNB_PERP", baseAsset: "BNB", quoteAsset: "QUSD", type: "perp", maxLeverage: 20, tickSize: 0.01, stepSize: 0.001, minOrderSize: 0.01, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "SOL_PERP", baseAsset: "SOL", quoteAsset: "QUSD", type: "perp", maxLeverage: 20, tickSize: 0.01, stepSize: 0.001, minOrderSize: 0.01, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
  { id: "BTC_PERP", baseAsset: "BTC", quoteAsset: "QUSD", type: "perp", maxLeverage: 50, tickSize: 0.01, stepSize: 0.00001, minOrderSize: 0.0001, makerFee: 0.0002, takerFee: 0.0005, enabled: true },
];

// ─── CHAIN CONFIGS ──────────────────────────────────────────────────────────

export interface ChainConfig {
  id: string;
  name: string;
  rpcUrl: string;
  chainId: number;
  explorerUrl: string;
  nativeSymbol: string;
  blockTime: number;
  confirmations: number;
}

export const CHAINS: Record<string, ChainConfig> = {
  qbc: {
    id: "qbc",
    name: "Qubitcoin Mainnet",
    rpcUrl: process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000",
    chainId: 3303,
    explorerUrl: "",
    nativeSymbol: "QBC",
    blockTime: 3.3,
    confirmations: 1,
  },
  ethereum: {
    id: "ethereum",
    name: "Ethereum",
    rpcUrl: process.env.NEXT_PUBLIC_ETH_RPC_URL ?? "",
    chainId: 1,
    explorerUrl: "https://etherscan.io",
    nativeSymbol: "ETH",
    blockTime: 12,
    confirmations: 12,
  },
  bnb: {
    id: "bnb",
    name: "BNB Chain",
    rpcUrl: process.env.NEXT_PUBLIC_BSC_RPC_URL ?? "",
    chainId: 56,
    explorerUrl: "https://bscscan.com",
    nativeSymbol: "BNB",
    blockTime: 3,
    confirmations: 15,
  },
  solana: {
    id: "solana",
    name: "Solana",
    rpcUrl: process.env.NEXT_PUBLIC_SOL_RPC_URL ?? "",
    chainId: 0,
    explorerUrl: "https://solscan.io",
    nativeSymbol: "SOL",
    blockTime: 0.4,
    confirmations: 32,
  },
};

// ─── ASSET BASE PRICES (fallback when backend returns 0) ─────────────────────

export const BASE_PRICES: Record<string, number> = {
  QBC: 1.0,
  wQBC: 1.0,
  QUSD: 1.0,
  wETH: 3421.0,
  ETH: 3421.0,
  wBNB: 412.8,
  BNB: 412.8,
  wSOL: 172.4,
  SOL: 172.4,
  wBTC: 97420.0,
  BTC: 97420.0,
};

export const ASSET_VOLATILITY: Record<string, number> = {
  QBC: 0.08,
  wQBC: 0.08,
  wETH: 0.05,
  ETH: 0.05,
  wBNB: 0.06,
  BNB: 0.06,
  wSOL: 0.10,
  SOL: 0.10,
  wBTC: 0.04,
  BTC: 0.04,
};

// ─── FEES ───────────────────────────────────────────────────────────────────

export const FEES = {
  maker: 0.0002,
  taker: 0.0005,
  quantumSurcharge: 0.00001,
  bridgeFee: 0.0005,
};

// ─── HELPERS ────────────────────────────────────────────────────────────────

export function getMarketConfig(id: string): AdminMarketConfig | undefined {
  return MARKET_CONFIGS.find((m) => m.id === id && m.enabled);
}

export function getToken(symbol: string): AdminTokenConfig | undefined {
  return TOKENS.find((t) => t.symbol === symbol && t.enabled);
}

export function getEnabledMarkets(type?: "spot" | "perp"): AdminMarketConfig[] {
  return MARKET_CONFIGS.filter((m) => m.enabled && (!type || m.type === type));
}

export function getEnabledTokens(): AdminTokenConfig[] {
  return TOKENS.filter((t) => t.enabled);
}

export function getBasePrice(asset: string): number {
  return BASE_PRICES[asset] ?? 1;
}

export function displayName(id: string): string {
  const cfg = getMarketConfig(id);
  if (!cfg) return id;
  if (cfg.type === "perp") return cfg.baseAsset + "-PERP";
  return cfg.baseAsset + "/" + cfg.quoteAsset;
}
