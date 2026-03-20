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
    chainIdHex: "0xce7",
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
  polygon: {
    id: "polygon" as ChainId,
    name: "Polygon PoS",
    shortName: "MATIC",
    chainIdHex: "0x89",
    rpcUrl: env("POLYGON_RPC_URL") ?? "https://polygon-bor-rpc.publicnode.com",
    wqbcAddr: env("POLYGON_WQBC_ADDR") ?? "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wqusdAddr: env("POLYGON_WQUSD_ADDR") ?? "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorerUrl: "https://polygonscan.com",
    explorerTxPath: "/tx/",
    nativeSymbol: "POL",
    available: true,
    confirmations: 128,
    color: "#8247e5",
    walletType: "evm" as const,
  },
  avalanche: {
    id: "avalanche" as ChainId,
    name: "Avalanche C-Chain",
    shortName: "AVAX",
    chainIdHex: "0xa86a",
    rpcUrl: env("AVAX_RPC_URL") ?? "https://api.avax.network/ext/bc/C/rpc",
    wqbcAddr: env("AVAX_WQBC_ADDR") ?? "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wqusdAddr: env("AVAX_WQUSD_ADDR") ?? "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorerUrl: "https://snowtrace.io",
    explorerTxPath: "/tx/",
    nativeSymbol: "AVAX",
    available: true,
    confirmations: 20,
    color: "#e84142",
    walletType: "evm" as const,
  },
  arbitrum: {
    id: "arbitrum" as ChainId,
    name: "Arbitrum One",
    shortName: "ARB",
    chainIdHex: "0xa4b1",
    rpcUrl: env("ARB_RPC_URL") ?? "https://arb1.arbitrum.io/rpc",
    wqbcAddr: env("ARB_WQBC_ADDR") ?? "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wqusdAddr: env("ARB_WQUSD_ADDR") ?? "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorerUrl: "https://arbiscan.io",
    explorerTxPath: "/tx/",
    nativeSymbol: "ETH",
    available: true,
    confirmations: 12,
    color: "#28a0f0",
    walletType: "evm" as const,
  },
  optimism: {
    id: "optimism" as ChainId,
    name: "OP Mainnet",
    shortName: "OP",
    chainIdHex: "0xa",
    rpcUrl: env("OP_RPC_URL") ?? "https://mainnet.optimism.io",
    wqbcAddr: env("OP_WQBC_ADDR") ?? "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wqusdAddr: env("OP_WQUSD_ADDR") ?? "0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147",
    explorerUrl: "https://optimistic.etherscan.io",
    explorerTxPath: "/tx/",
    nativeSymbol: "ETH",
    available: true,
    confirmations: 12,
    color: "#ff0420",
    walletType: "evm" as const,
  },
  base: {
    id: "base" as ChainId,
    name: "Base",
    shortName: "BASE",
    chainIdHex: "0x2105",
    rpcUrl: env("BASE_RPC_URL") ?? "https://mainnet.base.org",
    wqbcAddr: env("BASE_WQBC_ADDR") ?? "0x14Db7C37e7284C5bb67a2d682169c9D11B7478AD",
    wqusdAddr: env("BASE_WQUSD_ADDR") ?? "0x1268ef87cC1DBB26428E4966A2C6C0Fb91877992",
    explorerUrl: "https://basescan.org",
    explorerTxPath: "/tx/",
    nativeSymbol: "ETH",
    available: true,
    confirmations: 12,
    color: "#0052ff",
    walletType: "evm" as const,
  },
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
  polygon: {
    wQBC: "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wQUSD: "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorer: "https://polygonscan.com",
  },
  avalanche: {
    wQBC: "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wQUSD: "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorer: "https://snowtrace.io",
  },
  arbitrum: {
    wQBC: "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wQUSD: "0x884867d25552b6117F85428405aeAA208A8CAdB3",
    explorer: "https://arbiscan.io",
  },
  optimism: {
    wQBC: "0xB7c8783dDfb7f72b2C27AFBDFFD2B0206046Fa67",
    wQUSD: "0xA8dAB13B55D7D5f9d140D0ec7B3772D373616147",
    explorer: "https://optimistic.etherscan.io",
  },
  base: {
    wQBC: "0x14Db7C37e7284C5bb67a2d682169c9D11B7478AD",
    wQUSD: "0x1268ef87cC1DBB26428E4966A2C6C0Fb91877992",
    explorer: "https://basescan.org",
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
