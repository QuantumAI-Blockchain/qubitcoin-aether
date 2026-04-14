import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface NativeWallet {
  address: string;
  publicKeyHex: string;
  label: string;
  createdAt: number;
  securityLevel?: number; // 2, 3, or 5
  checkPhrase?: string; // e.g. "tiger-ocean-marble"
  nistName?: string; // e.g. "ML-DSA-87"
}

interface WalletState {
  // MetaMask
  address: string | null;
  balance: number | null;
  connected: boolean;
  connect: (address: string) => void;
  disconnect: () => void;
  setBalance: (b: number) => void;

  // Native wallets
  nativeWallets: NativeWallet[];
  activeNativeWallet: string | null;
  addNativeWallet: (w: NativeWallet) => void;
  removeNativeWallet: (address: string) => void;
  setActiveNativeWallet: (address: string | null) => void;

  // Wallet mode
  walletTab: "metamask" | "native" | "sephirot";
  setWalletTab: (tab: "metamask" | "native" | "sephirot") => void;

  // Auth (JWT)
  authToken: string | null;
  authExpiry: number | null; // unix ms
  authAddress: string | null; // address the token was issued for
  setAuth: (token: string, expiresAt: number, address: string) => void;
  clearAuth: () => void;
  /** True if a valid (non-expired) JWT is stored. */
  isAuthenticated: () => boolean;
}

/** Return the stored auth token if valid, or null. */
export function getAuthToken(): string | null {
  const state = useWalletStore.getState();
  if (!state.authToken || !state.authExpiry) return null;
  // Expire 60s early to avoid edge-case clock skew
  if (Date.now() > state.authExpiry - 60_000) {
    state.clearAuth();
    return null;
  }
  return state.authToken;
}

export const useWalletStore = create<WalletState>()(
  persist(
    (set, get) => ({
      // MetaMask
      address: null,
      balance: null,
      connected: false,
      connect: (address) => set({ address, connected: true }),
      disconnect: () => {
        set({ address: null, balance: null, connected: false });
        // Clear auth when disconnecting MetaMask
        set({ authToken: null, authExpiry: null, authAddress: null });
      },
      setBalance: (b) => set({ balance: b }),

      // Native wallets
      nativeWallets: [],
      activeNativeWallet: null,
      addNativeWallet: (w) =>
        set((s) => ({
          nativeWallets: [...s.nativeWallets, w],
          activeNativeWallet: s.activeNativeWallet ?? w.address,
        })),
      removeNativeWallet: (address) =>
        set((s) => ({
          nativeWallets: s.nativeWallets.filter((w) => w.address !== address),
          activeNativeWallet:
            s.activeNativeWallet === address ? null : s.activeNativeWallet,
        })),
      setActiveNativeWallet: (address) => set({ activeNativeWallet: address }),

      // Tab
      walletTab: "metamask",
      setWalletTab: (tab) => set({ walletTab: tab }),

      // Auth (JWT)
      authToken: null,
      authExpiry: null,
      authAddress: null,
      setAuth: (token, expiresAt, address) =>
        set({ authToken: token, authExpiry: expiresAt * 1000, authAddress: address }),
      clearAuth: () =>
        set({ authToken: null, authExpiry: null, authAddress: null }),
      isAuthenticated: () => {
        const s = get();
        return !!s.authToken && !!s.authExpiry && Date.now() < s.authExpiry - 60_000;
      },
    }),
    {
      name: "qbc-wallet",
      partialize: (state) => ({
        nativeWallets: state.nativeWallets,
        activeNativeWallet: state.activeNativeWallet,
        walletTab: state.walletTab,
        // Persist auth token across page reloads
        authToken: state.authToken,
        authExpiry: state.authExpiry,
        authAddress: state.authAddress,
      }),
    },
  ),
);
