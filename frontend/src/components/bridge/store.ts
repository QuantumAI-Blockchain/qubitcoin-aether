/* ---------------------------------------------------------------------------
   QBC Bridge — Zustand Store (hash-based routing, bridge operation state)
   --------------------------------------------------------------------------- */

import { create } from "zustand";
import type {
  BridgeView,
  ExternalChainId,
  OperationType,
  TokenType,
} from "./types";

// ---------------------------------------------------------------------------
// Hash Routing Helpers
// ---------------------------------------------------------------------------

/** Parse `#/bridge`, `#/bridge/tx/:txId`, `#/bridge/history`, etc. */
function parseHash(hash: string): {
  view: BridgeView;
  params: Record<string, string>;
} {
  // Strip leading "#" and optional leading "/"
  const raw = hash.replace(/^#\/?/, "");
  const segments = raw.split("/").filter(Boolean);

  // Default: #/bridge or empty
  if (segments.length === 0 || (segments.length === 1 && segments[0] === "bridge")) {
    return { view: "bridge", params: {} };
  }

  // All bridge routes start with "bridge"
  if (segments[0] !== "bridge") {
    return { view: "bridge", params: {} };
  }

  const sub = segments[1];

  switch (sub) {
    case "tx":
      return {
        view: "tx",
        params: segments[2] ? { txId: segments[2] } : {},
      };
    case "history":
      return { view: "history", params: {} };
    case "vault":
      return { view: "vault", params: {} };
    case "fees":
      return { view: "fees", params: {} };
    default:
      return { view: "bridge", params: {} };
  }
}

/** Build a hash string from a view and optional params. */
function buildHash(view: BridgeView, params?: Record<string, string>): string {
  switch (view) {
    case "bridge":
      return "#/bridge";
    case "tx":
      return params?.txId ? `#/bridge/tx/${params.txId}` : "#/bridge";
    case "history":
      return "#/bridge/history";
    case "vault":
      return "#/bridge/vault";
    case "fees":
      return "#/bridge/fees";
    default:
      return "#/bridge";
  }
}

// ---------------------------------------------------------------------------
// State Interface
// ---------------------------------------------------------------------------

interface BridgeState {
  // Navigation
  view: BridgeView;
  viewParams: Record<string, string>;

  // Bridge operation
  direction: OperationType;
  token: TokenType;
  selectedChain: ExternalChainId | null;
  amount: string;
  customReceiveAddress: string;

  // Modals
  walletModalOpen: boolean;
  preFlightOpen: boolean;
  chainSelectorOpen: boolean;
  settingsOpen: boolean;

  // TX tracking
  activeTxId: string | null;

  // DevTools
  devToolsOpen: boolean;

  // Actions
  navigate: (view: BridgeView, params?: Record<string, string>) => void;
  setDirection: (d: OperationType) => void;
  setToken: (t: TokenType) => void;
  setSelectedChain: (c: ExternalChainId | null) => void;
  setAmount: (a: string) => void;
  setCustomReceiveAddress: (a: string) => void;
  setWalletModalOpen: (open: boolean) => void;
  setPreFlightOpen: (open: boolean) => void;
  setChainSelectorOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setActiveTxId: (id: string | null) => void;
  toggleDevTools: () => void;
  resetBridge: () => void;
  syncFromHash: () => void;
}

// ---------------------------------------------------------------------------
// Initial State (derived from current hash if present)
// ---------------------------------------------------------------------------

function getInitialRouteState(): { view: BridgeView; viewParams: Record<string, string> } {
  if (typeof window === "undefined") {
    return { view: "bridge", viewParams: {} };
  }
  const parsed = parseHash(window.location.hash);
  return { view: parsed.view, viewParams: parsed.params };
}

const initialRoute = getInitialRouteState();

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useBridgeStore = create<BridgeState>((set) => ({
  // Navigation — hydrate from current hash on creation
  view: initialRoute.view,
  viewParams: initialRoute.viewParams,

  // Bridge operation defaults
  direction: "wrap",
  token: "QBC",
  selectedChain: null,
  amount: "",
  customReceiveAddress: "",

  // Modals — all closed by default
  walletModalOpen: false,
  preFlightOpen: false,
  chainSelectorOpen: false,
  settingsOpen: false,

  // TX tracking
  activeTxId: null,

  // DevTools
  devToolsOpen: false,

  // -------------------------------------------------------------------------
  // Actions
  // -------------------------------------------------------------------------

  navigate: (view, params) => {
    const merged = params ?? {};
    if (typeof window !== "undefined") {
      window.location.hash = buildHash(view, merged);
    }
    set({ view, viewParams: merged });
  },

  setDirection: (d) => set({ direction: d }),
  setToken: (t) => set({ token: t }),
  setSelectedChain: (c) => set({ selectedChain: c }),
  setAmount: (a) => set({ amount: a }),
  setCustomReceiveAddress: (a) => set({ customReceiveAddress: a }),

  setWalletModalOpen: (open) => set({ walletModalOpen: open }),
  setPreFlightOpen: (open) => set({ preFlightOpen: open }),
  setChainSelectorOpen: (open) => set({ chainSelectorOpen: open }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),

  setActiveTxId: (id) => set({ activeTxId: id }),

  toggleDevTools: () => set((s) => ({ devToolsOpen: !s.devToolsOpen })),

  resetBridge: () =>
    set({
      amount: "",
      customReceiveAddress: "",
      activeTxId: null,
      preFlightOpen: false,
    }),

  syncFromHash: () => {
    if (typeof window === "undefined") return;
    const parsed = parseHash(window.location.hash);
    set({ view: parsed.view, viewParams: parsed.params });
  },
}));
