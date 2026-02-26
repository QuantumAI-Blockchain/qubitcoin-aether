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
  ethereum: buildChain(
    "ethereum",
    "Ethereum Mainnet",
    "ETH",
    "0x1",
    "ETH_RPC_URL",
    "ETH_WQBC_ADDR",
    "ETH_WQUSD_ADDR",
    "https://etherscan.io",
    "/tx/",
    "ETH",
    12,
    "#627eea",
    "evm"
  ),
  bnb: buildChain(
    "bnb",
    "BNB Smart Chain",
    "BNB",
    "0x38",
    "BSC_RPC_URL",
    "BSC_WQBC_ADDR",
    "BSC_WQUSD_ADDR",
    "https://bscscan.com",
    "/tx/",
    "BNB",
    15,
    "#f3ba2f",
    "evm"
  ),
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
};

export const EXTERNAL_CHAINS: ExternalChainId[] = ["ethereum", "bnb", "solana"];

export const VAULT_ADDRS = {
  qbc: env("QBC_WQBC_VAULT_ADDR"),
  qusd: env("QBC_WQUSD_VAULT_ADDR"),
};

export const CONFIRMATION_COUNTS: Record<ChainId, number> = {
  qbc_mainnet: 20,
  ethereum: 12,
  bnb: 15,
  solana: 32,
};

export function getExplorerTxUrl(chain: ChainInfo, hash: string): string {
  if (chain.id === "qbc_mainnet") return `#/transaction/${hash}`;
  return `${chain.explorerUrl}${chain.explorerTxPath}${hash}`;
}

export function isEvmChain(id: ChainId): boolean {
  return id === "ethereum" || id === "bnb";
}
