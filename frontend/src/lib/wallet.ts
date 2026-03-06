import { BrowserProvider, JsonRpcSigner } from "ethers";
import { CHAIN_CONFIG, CHAIN_ID } from "./constants";

/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Detect if we're inside a Telegram WebApp (no browser extensions available).
 */
export function isTelegramWebApp(): boolean {
  if (typeof window === "undefined") return false;
  return !!(window as any).Telegram?.WebApp;
}

/**
 * Find the real MetaMask provider, handling multi-wallet environments.
 * Phantom injects itself as window.ethereum with isMetaMask=true,
 * so we must check the providers array and exclude Phantom.
 */
function getMetaMaskProvider(): any | undefined {
  if (typeof window === "undefined") return undefined;
  const ethereum = (window as any).ethereum;
  if (!ethereum) return undefined;

  // Multi-wallet: window.ethereum.providers is an array of injected providers
  if (Array.isArray(ethereum.providers)) {
    const mm = ethereum.providers.find(
      (p: any) => p.isMetaMask && !p.isPhantom && !p.isBraveWallet
    );
    if (mm) return mm;
  }

  // Single provider: verify it's actually MetaMask (not Phantom pretending)
  if (ethereum.isMetaMask && !ethereum.isPhantom) return ethereum;

  return undefined;
}

/** Get any available EVM provider (MetaMask preferred, fallback to raw). */
function getEthereum(): any | undefined {
  if (typeof window === "undefined") return undefined;
  // Prefer the real MetaMask provider
  const mm = getMetaMaskProvider();
  if (mm) return mm;
  // Fallback to raw window.ethereum (could be Coinbase, Brave, etc.)
  return (window as any).ethereum;
}
/* eslint-enable @typescript-eslint/no-explicit-any */

/** Connect to MetaMask and return signer + address. */
export async function connectWallet(): Promise<{
  provider: BrowserProvider;
  signer: JsonRpcSigner;
  address: string;
}> {
  if (isTelegramWebApp()) {
    throw new Error(
      "MetaMask browser extensions are not available in Telegram. " +
      "Please open qbc.network in your mobile browser (Chrome/Safari) with MetaMask installed, " +
      "or use MetaMask's built-in browser."
    );
  }

  const ethereum = getEthereum();
  if (!ethereum) throw new Error("MetaMask not installed. Please install MetaMask from metamask.io");

  const provider = new BrowserProvider(ethereum);
  await provider.send("eth_requestAccounts", []);

  // Switch / add chain if needed
  try {
    await provider.send("wallet_switchEthereumChain", [
      { chainId: CHAIN_CONFIG.chainId },
    ]);
  } catch {
    await provider.send("wallet_addEthereumChain", [CHAIN_CONFIG]);
  }

  const signer = await provider.getSigner();
  const address = await signer.getAddress();
  return { provider, signer, address };
}

/** Check if already connected. */
export async function getConnectedAddress(): Promise<string | null> {
  const ethereum = getEthereum();
  if (!ethereum) return null;
  const provider = new BrowserProvider(ethereum);
  const network = await provider.getNetwork().catch(() => null);
  if (!network || Number(network.chainId) !== CHAIN_ID) return null;
  const accounts: string[] = await provider.send("eth_accounts", []);
  return accounts[0] ?? null;
}
