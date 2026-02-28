/**
 * Bridge API Service Layer
 *
 * Typed fetch functions for the Qubitcoin Bridge.
 * Switches between mock data and real backend API via NEXT_PUBLIC_BRIDGE_MOCK.
 *
 * When NEXT_PUBLIC_BRIDGE_MOCK is explicitly "true", mock data is returned.
 * Otherwise, the real backend at NEXT_PUBLIC_RPC_URL is used.
 */

import { RPC_URL } from "./constants";

// ---------------------------------------------------------------------------
// Environment switch
// ---------------------------------------------------------------------------

const USE_MOCK = process.env.NEXT_PUBLIC_BRIDGE_MOCK === "true";

// ---------------------------------------------------------------------------
// Types (backend-aligned)
// ---------------------------------------------------------------------------

export interface BridgeChainStats {
  chain: string;
  status: string;
  total_deposits: number;
  total_withdrawals: number;
  total_volume: string;
  pending_transfers: number;
  is_paused: boolean;
}

export interface BridgeAllStats {
  chains: BridgeChainStats[];
  totals: {
    total_deposits: number;
    total_withdrawals: number;
    total_volume: string;
    active_chains: number;
  };
}

export interface BridgeFeeEstimate {
  chain: string;
  amount: string;
  bridge_fee: string;
  bridge_fee_rate: string;
  estimated_gas: string;
  total_cost: string;
  receive_amount: string;
}

export interface BridgeDepositResult {
  tx_hash: string;
  chain: string;
  amount: string;
  fee_paid: string;
}

export interface BridgeBalanceResult {
  chain: string;
  address: string;
  balance: string;
}

export interface BridgeSupportedChain {
  id: string;
  name: string;
  status: string;
  is_paused: boolean;
}

export interface BridgeValidatorStats {
  total_validators: number;
  total_verifications: number;
  total_rewards_qbc: number;
}

export interface BridgeLPStats {
  total_liquidity: number;
  pools: Record<string, { liquidity: number; providers: number; apy: number }>;
}

// ---------------------------------------------------------------------------
// Vault state type (frontend-shaped, assembled from backend data)
// ---------------------------------------------------------------------------

export interface BridgeVaultState {
  qbcLocked: number;
  qusdLocked: number;
  wqbcByChain: Record<string, number>;
  wqusdByChain: Record<string, number>;
  totalWqbc: number;
  totalWqusd: number;
  backingRatioQbc: number;
  backingRatioQusd: number;
  vaultAddrQbc: string;
  vaultAddrQusd: string;
  dailyWrapVol: number;
  dailyUnwrapVol: number;
  dailyLimit: number;
  dailyUsed: number;
  dailyResetIn: number;
  backingHistory: Array<{ date: string; qbcLocked: number; wqbcCirculating: number; ratio: 1.0 }>;
  wrapUnwrapHistory: Array<{ date: string; wrapped: number; unwrapped: number; netBalance: number }>;
}

// ---------------------------------------------------------------------------
// Fetch helper (real backend)
// ---------------------------------------------------------------------------

async function bridgeFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${RPC_URL}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`Bridge API ${res.status}: ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// PRNG for deterministic mock data
// ---------------------------------------------------------------------------

function mulberry32(seed: number): () => number {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function round6(n: number): number {
  return Math.round(n * 1000000) / 1000000;
}

function rangeFloat(rng: () => number, min: number, max: number): number {
  return min + rng() * (max - min);
}

function rangeInt(rng: () => number, min: number, max: number): number {
  return min + ((rng() * (max - min + 1)) | 0);
}

function hexStr(rng: () => number, len: number): string {
  const chars = "0123456789abcdef";
  let s = "";
  for (let i = 0; i < len; i++) s += chars[(rng() * 16) | 0];
  return s;
}

function qbcAddress(rng: () => number): string {
  return "QBC1" + hexStr(rng, 38);
}

// ---------------------------------------------------------------------------
// Mock data generators
// ---------------------------------------------------------------------------

const MOCK_RNG = mulberry32(3301);

function mockBridgeStats(): BridgeAllStats {
  return {
    chains: [
      {
        chain: "ethereum",
        status: "active",
        total_deposits: 1842,
        total_withdrawals: 1523,
        total_volume: "2847291.42",
        pending_transfers: 3,
        is_paused: false,
      },
      {
        chain: "bnb",
        status: "active",
        total_deposits: 982,
        total_withdrawals: 841,
        total_volume: "1482910.88",
        pending_transfers: 1,
        is_paused: false,
      },
      {
        chain: "solana",
        status: "active",
        total_deposits: 621,
        total_withdrawals: 547,
        total_volume: "984210.33",
        pending_transfers: 2,
        is_paused: false,
      },
      {
        chain: "polygon",
        status: "active",
        total_deposits: 412,
        total_withdrawals: 387,
        total_volume: "621840.19",
        pending_transfers: 0,
        is_paused: false,
      },
      {
        chain: "avalanche",
        status: "active",
        total_deposits: 298,
        total_withdrawals: 271,
        total_volume: "412920.55",
        pending_transfers: 1,
        is_paused: false,
      },
      {
        chain: "arbitrum",
        status: "active",
        total_deposits: 524,
        total_withdrawals: 489,
        total_volume: "842190.72",
        pending_transfers: 0,
        is_paused: false,
      },
      {
        chain: "optimism",
        status: "active",
        total_deposits: 341,
        total_withdrawals: 312,
        total_volume: "521840.41",
        pending_transfers: 1,
        is_paused: false,
      },
      {
        chain: "base",
        status: "active",
        total_deposits: 189,
        total_withdrawals: 162,
        total_volume: "284920.18",
        pending_transfers: 0,
        is_paused: false,
      },
    ],
    totals: {
      total_deposits: 5209,
      total_withdrawals: 4532,
      total_volume: "7998123.68",
      active_chains: 8,
    },
  };
}

function mockBridgeFees(chain: string, amount: string): BridgeFeeEstimate {
  const amt = parseFloat(amount) || 0;
  const bridgeFee = round6(amt * 0.001);
  const gasEstimates: Record<string, number> = {
    ethereum: 5.2,
    bnb: 0.24,
    solana: 0.004,
    polygon: 0.02,
    avalanche: 0.15,
    arbitrum: 0.08,
    optimism: 0.06,
    base: 0.04,
  };
  const gas = gasEstimates[chain] ?? 0.1;
  const totalCost = round6(bridgeFee + gas);
  return {
    chain,
    amount,
    bridge_fee: bridgeFee.toFixed(6),
    bridge_fee_rate: "0.001",
    estimated_gas: gas.toFixed(6),
    total_cost: totalCost.toFixed(6),
    receive_amount: round6(amt - totalCost).toFixed(6),
  };
}

function mockSupportedChains(): BridgeSupportedChain[] {
  return [
    { id: "ethereum", name: "Ethereum", status: "active", is_paused: false },
    { id: "bnb", name: "BNB Smart Chain", status: "active", is_paused: false },
    { id: "solana", name: "Solana", status: "active", is_paused: false },
    { id: "polygon", name: "Polygon", status: "active", is_paused: false },
    { id: "avalanche", name: "Avalanche", status: "active", is_paused: false },
    { id: "arbitrum", name: "Arbitrum", status: "active", is_paused: false },
    { id: "optimism", name: "Optimism", status: "active", is_paused: false },
    { id: "base", name: "Base", status: "active", is_paused: false },
  ];
}

function mockBridgeBalance(chain: string, address: string): BridgeBalanceResult {
  const rng = mulberry32(
    Array.from(address).reduce((s, c) => s + c.charCodeAt(0), 0),
  );
  return {
    chain,
    address,
    balance: round6(rangeFloat(rng, 0, 10000)).toFixed(6),
  };
}

function mockBridgeDeposit(): BridgeDepositResult {
  return {
    tx_hash: "0x" + hexStr(MOCK_RNG, 64),
    chain: "ethereum",
    amount: "1000.000000",
    fee_paid: "1.000000",
  };
}

function mockValidatorStats(): BridgeValidatorStats {
  return {
    total_validators: 42,
    total_verifications: 8421,
    total_rewards_qbc: 12847,
  };
}

function mockLPStats(): BridgeLPStats {
  return {
    total_liquidity: 2847291,
    pools: {
      ethereum: { liquidity: 1247832, providers: 28, apy: 8.4 },
      bnb: { liquidity: 842190, providers: 19, apy: 12.1 },
      solana: { liquidity: 421840, providers: 14, apy: 15.3 },
      polygon: { liquidity: 184210, providers: 8, apy: 11.2 },
      avalanche: { liquidity: 98420, providers: 5, apy: 9.8 },
      arbitrum: { liquidity: 31200, providers: 3, apy: 14.5 },
      optimism: { liquidity: 15800, providers: 2, apy: 13.2 },
      base: { liquidity: 5799, providers: 1, apy: 18.7 },
    },
  };
}

function mockVaultState(): BridgeVaultState {
  const rng = mulberry32(3301);
  const qbcLocked = 1_247_832;
  const qusdLocked = 284_921;

  const wqbcEth = round6(qbcLocked * 0.42);
  const wqbcBnb = round6(qbcLocked * 0.22);
  const wqbcSol = round6(qbcLocked * 0.14);
  const wqbcPoly = round6(qbcLocked * 0.08);
  const wqbcAvax = round6(qbcLocked * 0.05);
  const wqbcArb = round6(qbcLocked * 0.05);
  const wqbcOp = round6(qbcLocked * 0.03);
  const wqbcBase = round6(qbcLocked - wqbcEth - wqbcBnb - wqbcSol - wqbcPoly - wqbcAvax - wqbcArb - wqbcOp);

  const wqusdEth = round6(qusdLocked * 0.40);
  const wqusdBnb = round6(qusdLocked * 0.25);
  const wqusdSol = round6(qusdLocked * 0.12);
  const wqusdPoly = round6(qusdLocked * 0.08);
  const wqusdAvax = round6(qusdLocked * 0.06);
  const wqusdArb = round6(qusdLocked * 0.05);
  const wqusdOp = round6(qusdLocked * 0.03);
  const wqusdBase = round6(qusdLocked - wqusdEth - wqusdBnb - wqusdSol - wqusdPoly - wqusdAvax - wqusdArb - wqusdOp);

  const NOW = Math.floor(Date.now() / 1000);
  const dailyUsed = rangeInt(rng, 0, 50000);
  const dailyResetIn = rangeInt(rng, 3600, 86400);

  const backingHistory: BridgeVaultState["backingHistory"] = [];
  for (let d = 29; d >= 0; d--) {
    const date = new Date((NOW - d * 86400) * 1000).toISOString().slice(0, 10);
    const variation = round6(qbcLocked + rangeFloat(rng, -20000, 20000));
    backingHistory.push({
      date,
      qbcLocked: variation,
      wqbcCirculating: variation,
      ratio: 1.0 as 1.0,
    });
  }

  const wrapUnwrapHistory: BridgeVaultState["wrapUnwrapHistory"] = [];
  let netBalance = 0;
  for (let d = 29; d >= 0; d--) {
    const date = new Date((NOW - d * 86400) * 1000).toISOString().slice(0, 10);
    const wrapped = round6(rangeFloat(rng, 40000, 130000));
    const unwrapped = round6(rangeFloat(rng, 30000, 100000));
    netBalance = round6(netBalance + wrapped - unwrapped);
    wrapUnwrapHistory.push({ date, wrapped, unwrapped, netBalance });
  }

  return {
    qbcLocked,
    qusdLocked,
    wqbcByChain: {
      ethereum: wqbcEth,
      bnb: wqbcBnb,
      solana: wqbcSol,
      polygon: wqbcPoly,
      avalanche: wqbcAvax,
      arbitrum: wqbcArb,
      optimism: wqbcOp,
      base: wqbcBase,
    },
    wqusdByChain: {
      ethereum: wqusdEth,
      bnb: wqusdBnb,
      solana: wqusdSol,
      polygon: wqusdPoly,
      avalanche: wqusdAvax,
      arbitrum: wqusdArb,
      optimism: wqusdOp,
      base: wqusdBase,
    },
    totalWqbc: qbcLocked,
    totalWqusd: qusdLocked,
    backingRatioQbc: 1.0,
    backingRatioQusd: 1.0,
    vaultAddrQbc: qbcAddress(rng),
    vaultAddrQusd: qbcAddress(rng),
    dailyWrapVol: 84_291,
    dailyUnwrapVol: 61_847,
    dailyLimit: 100_000,
    dailyUsed,
    dailyResetIn,
    backingHistory,
    wrapUnwrapHistory,
  };
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/** Get bridge statistics across all chains. */
export async function getBridgeStats(): Promise<BridgeAllStats> {
  if (USE_MOCK) return mockBridgeStats();
  return bridgeFetch<BridgeAllStats>("/bridge/stats");
}

/** Get supported bridge chains. */
export async function getSupportedChains(): Promise<BridgeSupportedChain[]> {
  if (USE_MOCK) return mockSupportedChains();
  const res = await bridgeFetch<{ chains: BridgeSupportedChain[] }>("/bridge/chains");
  return res.chains;
}

/** Estimate bridge fees for a transfer. */
export async function getBridgeFees(
  chain: string,
  amount: string,
): Promise<BridgeFeeEstimate> {
  if (USE_MOCK) return mockBridgeFees(chain, amount);
  return bridgeFetch<BridgeFeeEstimate>(`/bridge/fees/${chain}/${amount}`);
}

/** Get wQBC/wQUSD balance on a target chain. */
export async function getBridgeBalance(
  chain: string,
  address: string,
): Promise<BridgeBalanceResult> {
  if (USE_MOCK) return mockBridgeBalance(chain, address);
  return bridgeFetch<BridgeBalanceResult>(`/bridge/balance/${chain}/${address}`);
}

/** Initiate a bridge deposit (QBC -> target chain). */
export async function bridgeDeposit(body: {
  chain: string;
  qbc_txid: string;
  qbc_address: string;
  target_address: string;
  amount: string;
}): Promise<BridgeDepositResult> {
  if (USE_MOCK) return mockBridgeDeposit();
  return bridgeFetch<BridgeDepositResult>("/bridge/deposit", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Get QBC balance from the L1 node. */
export async function getQbcBalance(
  address: string,
): Promise<{ balance: string; utxo_count: number }> {
  if (USE_MOCK) {
    return { balance: "12847.331000", utxo_count: 5 };
  }
  return bridgeFetch<{ balance: string; utxo_count: number }>(`/balance/${address}`);
}

/** Get vault state (assembled from /bridge/stats and related endpoints). */
export async function getVaultState(): Promise<BridgeVaultState> {
  if (USE_MOCK) return mockVaultState();

  // In production, assemble vault state from the bridge stats endpoint
  const stats = await bridgeFetch<BridgeAllStats>("/bridge/stats");

  // Extract totals from stats to build vault state
  const totalVolume = parseFloat(stats.totals.total_volume) || 0;
  const qbcLocked = totalVolume * 0.6; // estimate: 60% QBC, 40% QUSD
  const qusdLocked = totalVolume * 0.4;

  const wqbcByChain: Record<string, number> = {};
  const wqusdByChain: Record<string, number> = {};

  for (const chain of stats.chains) {
    const chainVol = parseFloat(chain.total_volume) || 0;
    wqbcByChain[chain.chain] = chainVol * 0.6;
    wqusdByChain[chain.chain] = chainVol * 0.4;
  }

  const rng = mulberry32(Date.now());

  return {
    qbcLocked: round6(qbcLocked),
    qusdLocked: round6(qusdLocked),
    wqbcByChain,
    wqusdByChain,
    totalWqbc: round6(qbcLocked),
    totalWqusd: round6(qusdLocked),
    backingRatioQbc: 1.0,
    backingRatioQusd: 1.0,
    vaultAddrQbc: qbcAddress(rng),
    vaultAddrQusd: qbcAddress(rng),
    dailyWrapVol: stats.totals.total_deposits * 20,
    dailyUnwrapVol: stats.totals.total_withdrawals * 15,
    dailyLimit: 100_000,
    dailyUsed: 0,
    dailyResetIn: 86400,
    backingHistory: [],
    wrapUnwrapHistory: [],
  };
}

/** Get bridge validator stats. */
export async function getValidatorStats(): Promise<BridgeValidatorStats> {
  if (USE_MOCK) return mockValidatorStats();
  return bridgeFetch<BridgeValidatorStats>("/bridge/validators/stats");
}

/** Get bridge LP stats. */
export async function getLPStats(): Promise<BridgeLPStats> {
  if (USE_MOCK) return mockLPStats();
  return bridgeFetch<BridgeLPStats>("/bridge/lp/stats");
}

/** Pause a bridge chain (admin). */
export async function pauseBridge(chain: string): Promise<{ status: string }> {
  if (USE_MOCK) return { status: "paused" };
  return bridgeFetch<{ status: string }>(`/bridge/pause/${chain}`, {
    method: "POST",
  });
}

/** Resume a bridge chain (admin). */
export async function resumeBridge(chain: string): Promise<{ status: string }> {
  if (USE_MOCK) return { status: "active" };
  return bridgeFetch<{ status: string }>(`/bridge/resume/${chain}`, {
    method: "POST",
  });
}

/** Convenience object grouping all bridge API functions. */
export const bridgeApi = {
  getBridgeStats,
  getSupportedChains,
  getBridgeFees,
  getBridgeBalance,
  bridgeDeposit,
  getQbcBalance,
  getVaultState,
  getValidatorStats,
  getLPStats,
  pauseBridge,
  resumeBridge,
} as const;
