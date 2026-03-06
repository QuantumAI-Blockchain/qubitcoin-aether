/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — Chain Configuration (env-var loaded, graceful unavailable)
   ───────────────────────────────────────────────────────────────────────── */

import type { ChainId, ChainInfo, ExternalChainId } from "./types";

function env(key: string): string | null {
  if (typeof window === "undefined") return null;
  // Support both NEXT_PUBLIC_ and VITE_ prefixes
  return (
    (process.env as Record<string, string | undefined>)[`NEXT_PUBLIC_${key}`] ??
    (process.env as Record<string, string | undefined>)[`VITE_${key}`] ??
    null
  );
}

function buildChain(
  id: ChainId,
  name: string,
  shortName: string,
  chainIdHex: string,
  rpcKey: string,
  wqbcKey: string,
  wqusdKey: string,
  explorerUrl: string,
  explorerTxPath: string,
  nativeSymbol: string,
  confirmations: number,
  color: string,
  walletType: "evm" | "solana" | "qbc"
): ChainInfo {
  const rpcUrl = env(rpcKey);
  const wqbcAddr = env(wqbcKey);
  const wqusdAddr = env(wqusdKey);

  return {
    id,
    name,
    shortName,
    chainIdHex,
    rpcUrl,
    wqbcAddr,
    wqusdAddr,
    explorerUrl,
    explorerTxPath,
    nativeSymbol,
    available: !!(rpcUrl && wqbcAddr && wqusdAddr),
    confirmations,
    color,
    walletType,
  };
}

export const CHAINS: Record<ChainId, ChainInfo> = {
  qbc_mainnet: {
    id: "qbc_mainnet",
    name: "Qubitcoin Mainnet",
    shortName: "QBC",
    chainIdHex: "0xce5",
    rpcUrl: env("QBC_RPC_URL") ?? "http://localhost:5000",
    wqbcAddr: null,
    wqusdAddr: null,
    explorerUrl: "",
    explorerTxPath: "#/transaction/",
    nativeSymbol: "QBC",
    available: true,
    confirmations: 20,
    color: "#00d4ff",
    walletType: "qbc",
  },
  ethereum: {
    id: "ethereum" as ChainId,
    name: "Ethereum Mainnet",
    shortName: "ETH",
    chainIdHex: "0x1",
    rpcUrl: env("ETH_RPC_URL") ?? "https://rpc.mevblocker.io",
    wqbcAddr: env("ETH_WQBC_ADDR") ?? "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wqusdAddr: env("ETH_WQUSD_ADDR") ?? "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorerUrl: "https://etherscan.io",
    explorerTxPath: "/tx/",
    nativeSymbol: "ETH",
    available: true,
    confirmations: 12,
    color: "#627eea",
    walletType: "evm" as const,
  },
  bnb: {
    id: "bnb" as ChainId,
    name: "BNB Smart Chain",
    shortName: "BNB",
    chainIdHex: "0x38",
    rpcUrl: env("BSC_RPC_URL") ?? "https://bsc-dataseed1.binance.org",
    wqbcAddr: env("BSC_WQBC_ADDR") ?? "0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147",
    wqusdAddr: env("BSC_WQUSD_ADDR") ?? "0xD137C89ed83d1D54802d07487bf1AF6e0b409BE3",
    explorerUrl: "https://bscscan.com",
    explorerTxPath: "/tx/",
    nativeSymbol: "BNB",
    available: true,
    confirmations: 15,
    color: "#f3ba2f",
    walletType: "evm" as const,
  },
  solana: buildChain(
    "solana",
    "Solana Mainnet",
    "SOL",
    "",
    "SOL_RPC_URL",
    "SOL_WQBC_ADDR",
    "SOL_WQUSD_ADDR",
    "https://solscan.io",
    "/tx/",
    "SOL",
    32,
    "#9945ff",
    "solana"
  ),
  polygon: buildChain(
    "polygon",
    "Polygon PoS",
    "MATIC",
    "0x89",
    "POLYGON_RPC_URL",
    "POLYGON_WQBC_ADDR",
    "POLYGON_WQUSD_ADDR",
    "https://polygonscan.com",
    "/tx/",
    "MATIC",
    128,
    "#8247e5",
    "evm"
  ),
  avalanche: buildChain(
    "avalanche",
    "Avalanche C-Chain",
    "AVAX",
    "0xa86a",
    "AVAX_RPC_URL",
    "AVAX_WQBC_ADDR",
    "AVAX_WQUSD_ADDR",
    "https://snowtrace.io",
    "/tx/",
    "AVAX",
    20,
    "#e84142",
    "evm"
  ),
  arbitrum: buildChain(
    "arbitrum",
    "Arbitrum One",
    "ARB",
    "0xa4b1",
    "ARB_RPC_URL",
    "ARB_WQBC_ADDR",
    "ARB_WQUSD_ADDR",
    "https://arbiscan.io",
    "/tx/",
    "ETH",
    12,
    "#28a0f0",
    "evm"
  ),
  optimism: buildChain(
    "optimism",
    "OP Mainnet",
    "OP",
    "0xa",
    "OP_RPC_URL",
    "OP_WQBC_ADDR",
    "OP_WQUSD_ADDR",
    "https://optimistic.etherscan.io",
    "/tx/",
    "ETH",
    12,
    "#ff0420",
    "evm"
  ),
  base: buildChain(
    "base",
    "Base",
    "BASE",
    "0x2105",
    "BASE_RPC_URL",
    "BASE_WQBC_ADDR",
    "BASE_WQUSD_ADDR",
    "https://basescan.org",
    "/tx/",
    "ETH",
    12,
    "#0052ff",
    "evm"
  ),
};

export const EXTERNAL_CHAINS: ExternalChainId[] = [
  "ethereum",
  "bnb",
  "solana",
  "polygon",
  "avalanche",
  "arbitrum",
  "optimism",
  "base",
];

export const VAULT_ADDRS = {
  qbc: env("QBC_WQBC_VAULT_ADDR"),
  qusd: env("QBC_WQUSD_VAULT_ADDR"),
};

export const CONFIRMATION_COUNTS: Record<ChainId, number> = {
  qbc_mainnet: 20,
  ethereum: 12,
  bnb: 15,
  solana: 32,
  polygon: 128,
  avalanche: 20,
  arbitrum: 12,
  optimism: 12,
  base: 12,
};

export function getExplorerTxUrl(chain: ChainInfo, hash: string): string {
  if (chain.id === "qbc_mainnet") return `#/transaction/${hash}`;
  return `${chain.explorerUrl}${chain.explorerTxPath}${hash}`;
}

export function getExplorerTokenUrl(chain: ChainInfo, addr: string): string {
  return `${chain.explorerUrl}/token/${addr}`;
}

/** Verified contract addresses for wQBC and wQUSD on each live chain */
export const DEPLOYED_CONTRACTS = {
  ethereum: {
    wQBC: "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wQUSD: "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorer: "https://etherscan.io",
    dex: { name: "Uniswap V3", pair: "wQBC/wQUSD", fee: "0.3%" },
  },
  bnb: {
    wQBC: "0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147",
    wQUSD: "0xD137C89ed83d1D54802d07487bf1AF6e0b409BE3",
    explorer: "https://bscscan.com",
    dex: { name: "PancakeSwap V2", pair: "wQBC/wQUSD", fee: "0.25%", pairAddr: "0x3927EfB12bDaf7E2d9930A3581177a0646456abd" },
  },
} as const;

export function isEvmChain(id: ChainId): boolean {
  return (
    id === "ethereum" ||
    id === "bnb" ||
    id === "polygon" ||
    id === "avalanche" ||
    id === "arbitrum" ||
    id === "optimism" ||
    id === "base"
  );
}
