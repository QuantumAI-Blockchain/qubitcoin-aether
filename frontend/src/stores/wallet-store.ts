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
}

export const useWalletStore = create<WalletState>()(
  persist(
    (set) => ({
      // MetaMask
      address: null,
      balance: null,
      connected: false,
      connect: (address) => set({ address, connected: true }),
      disconnect: () => set({ address: null, balance: null, connected: false }),
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
    }),
    {
      name: "qbc-wallet",
      partialize: (state) => ({
        nativeWallets: state.nativeWallets,
        activeNativeWallet: state.activeNativeWallet,
        walletTab: state.walletTab,
      }),
    },
  ),
);
