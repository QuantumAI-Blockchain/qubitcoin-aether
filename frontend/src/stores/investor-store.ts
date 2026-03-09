import { create } from "zustand";
import type {
  RoundInfo,
  InvestorStatus,
  VestingInfo,
  RevenueInfo,
} from "@/lib/investor-api";

interface InvestorState {
  // Round
  round: RoundInfo | null;
  setRound: (info: RoundInfo) => void;

  // Investor status
  status: InvestorStatus | null;
  setStatus: (status: InvestorStatus) => void;

  // QBC address binding
  qbcAddress: string;
  setQbcAddress: (addr: string) => void;
  checkPhrase: string;
  setCheckPhrase: (phrase: string) => void;
  addressValidated: boolean;
  setAddressValidated: (v: boolean) => void;

  // Vesting
  vesting: VestingInfo | null;
  setVesting: (info: VestingInfo) => void;

  // Revenue
  revenue: RevenueInfo | null;
  setRevenue: (info: RevenueInfo) => void;

  // UI
  selectedToken: "ETH" | "USDC" | "USDT" | "DAI";
  setSelectedToken: (t: "ETH" | "USDC" | "USDT" | "DAI") => void;
  investAmount: string;
  setInvestAmount: (amt: string) => void;

  // Reset
  reset: () => void;
}

export const useInvestorStore = create<InvestorState>((set) => ({
  round: null,
  setRound: (round) => set({ round }),

  status: null,
  setStatus: (status) => set({ status }),

  qbcAddress: "",
  setQbcAddress: (qbcAddress) => set({ qbcAddress }),
  checkPhrase: "",
  setCheckPhrase: (checkPhrase) => set({ checkPhrase }),
  addressValidated: false,
  setAddressValidated: (addressValidated) => set({ addressValidated }),

  vesting: null,
  setVesting: (vesting) => set({ vesting }),

  revenue: null,
  setRevenue: (revenue) => set({ revenue }),

  selectedToken: "ETH",
  setSelectedToken: (selectedToken) => set({ selectedToken }),
  investAmount: "",
  setInvestAmount: (investAmount) => set({ investAmount }),

  reset: () =>
    set({
      round: null,
      status: null,
      qbcAddress: "",
      checkPhrase: "",
      addressValidated: false,
      vesting: null,
      revenue: null,
      selectedToken: "ETH",
      investAmount: "",
    }),
}));
