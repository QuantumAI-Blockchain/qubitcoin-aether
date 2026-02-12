import { BrowserProvider, JsonRpcSigner } from "ethers";
import { CHAIN_CONFIG, CHAIN_ID } from "./constants";

/** Get the MetaMask (EIP-1193) provider if available. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getEthereum(): any | undefined {
  if (typeof window === "undefined") return undefined;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (window as any).ethereum;
}

/** Connect to MetaMask and return signer + address. */
export async function connectWallet(): Promise<{
  provider: BrowserProvider;
  signer: JsonRpcSigner;
  address: string;
}> {
  const ethereum = getEthereum();
  if (!ethereum) throw new Error("MetaMask not installed");

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
