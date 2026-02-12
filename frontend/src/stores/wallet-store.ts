import { create } from "zustand";

interface WalletState {
  address: string | null;
  balance: number | null;
  connected: boolean;
  connect: (address: string) => void;
  disconnect: () => void;
  setBalance: (b: number) => void;
}

export const useWalletStore = create<WalletState>((set) => ({
  address: null,
  balance: null,
  connected: false,
  connect: (address) => set({ address, connected: true }),
  disconnect: () => set({ address: null, balance: null, connected: false }),
  setBalance: (b) => set({ balance: b }),
}));
