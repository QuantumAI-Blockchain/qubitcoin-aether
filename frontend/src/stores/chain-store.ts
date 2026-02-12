import { create } from "zustand";
import type { ChainInfo, PhiData } from "@/lib/api";

interface ChainState {
  chain: ChainInfo | null;
  phi: PhiData | null;
  setChain: (info: ChainInfo) => void;
  setPhi: (data: PhiData) => void;
}

export const useChainStore = create<ChainState>((set) => ({
  chain: null,
  phi: null,
  setChain: (info) => set({ chain: info }),
  setPhi: (data) => set({ phi: data }),
}));
