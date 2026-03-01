/** Telegram Web App state management */
import { create } from "zustand";

export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
}

interface TelegramState {
  /** Whether running inside Telegram Mini App */
  isTWA: boolean;
  setIsTWA: (v: boolean) => void;

  /** Telegram user data from WebApp.initDataUnsafe */
  user: TelegramUser | null;
  setUser: (u: TelegramUser | null) => void;

  /** Start parameter (deep link referral code) */
  startParam: string;
  setStartParam: (p: string) => void;

  /** Theme from Telegram */
  colorScheme: "light" | "dark";
  setColorScheme: (c: "light" | "dark") => void;

  /** Viewport height */
  viewportHeight: number;
  setViewportHeight: (h: number) => void;

  /** Back button visible */
  backButtonVisible: boolean;
  setBackButtonVisible: (v: boolean) => void;

  /** Linked QBC wallet address */
  linkedWallet: string;
  setLinkedWallet: (addr: string) => void;
}

export const useTelegramStore = create<TelegramState>()((set) => ({
  isTWA: false,
  setIsTWA: (v) => set({ isTWA: v }),

  user: null,
  setUser: (u) => set({ user: u }),

  startParam: "",
  setStartParam: (p) => set({ startParam: p }),

  colorScheme: "dark",
  setColorScheme: (c) => set({ colorScheme: c }),

  viewportHeight: 0,
  setViewportHeight: (h) => set({ viewportHeight: h }),

  backButtonVisible: false,
  setBackButtonVisible: (v) => set({ backButtonVisible: v }),

  linkedWallet: "",
  setLinkedWallet: (addr) => set({ linkedWallet: addr }),
}));
