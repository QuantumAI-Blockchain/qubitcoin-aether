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
 * Detect mobile device (phone or tablet).
 */
export function isMobile(): boolean {
  if (typeof window === "undefined") return false;
  return /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(
    navigator.userAgent,
  );
}

/**
 * Detect if we're inside MetaMask's in-app browser.
 */
export function isMetaMaskBrowser(): boolean {
  if (typeof window === "undefined") return false;
  const ethereum = (window as any).ethereum;
  return !!(ethereum?.isMetaMask);
}

/**
 * Check if any EVM provider is available (works on desktop + MetaMask in-app browser).
 */
export function hasInjectedProvider(): boolean {
  if (typeof window === "undefined") return false;
  return !!(window as any).ethereum;
}

/**
 * Open the current page in MetaMask's in-app browser via deep link.
 * On iOS, uses metamask:// scheme. On Android, uses https://metamask.app.link.
 */
export function openInMetaMask(): void {
  const dappUrl = window.location.host + window.location.pathname;
  // metamask.app.link works on both iOS and Android
  window.location.href = `https://metamask.app.link/dapp/${dappUrl}`;
}

/**
 * Get the MetaMask install URL appropriate for the platform.
 */
export function getMetaMaskInstallUrl(): string {
  if (typeof window === "undefined") return "https://metamask.io/download/";
  const ua = navigator.userAgent;
  if (/iPhone|iPad|iPod/i.test(ua)) {
    return "https://apps.apple.com/app/metamask/id1438144202";
  }
  if (/Android/i.test(ua)) {
    return "https://play.google.com/store/apps/details?id=io.metamask";
  }
  return "https://metamask.io/download/";
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

  // On mobile without injected provider, deep-link to MetaMask
  if (!ethereum && isMobile()) {
    openInMetaMask();
    throw new Error("METAMASK_DEEPLINK");
  }

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
