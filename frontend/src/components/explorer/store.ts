/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Zustand Store + Hash Router
   ───────────────────────────────────────────────────────────────────────── */

import { create } from "zustand";
import type { ViewType, ExplorerRoute } from "./types";

/* ── Route parser ─────────────────────────────────────────────────────── */

function parseHash(hash: string): ExplorerRoute {
  const raw = hash.replace(/^#\/?/, "");
  if (!raw) return { view: "dashboard", params: {} };

  const [path, qs] = raw.split("?");
  const parts = path.split("/");
  const params: Record<string, string> = {};

  if (qs) {
    for (const pair of qs.split("&")) {
      const [k, v] = pair.split("=");
      if (k) params[decodeURIComponent(k)] = decodeURIComponent(v ?? "");
    }
  }

  const view = (parts[0] || "dashboard") as ViewType;

  // e.g. #/block/42 → { view: "block", params: { id: "42" } }
  if (parts.length > 1) params.id = parts.slice(1).join("/");

  return { view, params };
}

function buildHash(view: ViewType, params?: Record<string, string>): string {
  let h = `#/${view}`;
  if (params?.id) h += `/${params.id}`;
  const rest = Object.entries(params ?? {}).filter(([k]) => k !== "id");
  if (rest.length > 0) {
    h += "?" + rest.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
  }
  return h;
}

/* ── Store ────────────────────────────────────────────────────────────── */

interface ExplorerState {
  /* navigation */
  route: ExplorerRoute;
  history: ExplorerRoute[];

  /* search */
  searchQuery: string;
  searchOpen: boolean;

  /* devtools */
  devToolsOpen: boolean;
  devToolsTab: "state" | "network" | "perf";

  /* theme */
  compactMode: boolean;

  /* actions */
  navigate: (view: ViewType, params?: Record<string, string>) => void;
  goBack: () => void;
  setSearchQuery: (q: string) => void;
  setSearchOpen: (open: boolean) => void;
  toggleDevTools: () => void;
  setDevToolsTab: (tab: "state" | "network" | "perf") => void;
  toggleCompactMode: () => void;
  syncFromHash: () => void;
}

export const useExplorerStore = create<ExplorerState>((set, get) => ({
  route: parseHash(typeof window !== "undefined" ? window.location.hash : ""),
  history: [],
  searchQuery: "",
  searchOpen: false,
  devToolsOpen: false,
  devToolsTab: "state",
  compactMode: false,

  navigate: (view, params) => {
    const newRoute: ExplorerRoute = { view, params: params ?? {} };
    const hash = buildHash(view, params);
    window.history.pushState(null, "", hash);
    set((s) => ({
      route: newRoute,
      history: [...s.history, s.route],
      searchOpen: false,
    }));
  },

  goBack: () => {
    const { history } = get();
    if (history.length === 0) {
      get().navigate("dashboard");
      return;
    }
    const prev = history[history.length - 1];
    const hash = buildHash(prev.view, prev.params);
    window.history.pushState(null, "", hash);
    set({ route: prev, history: history.slice(0, -1) });
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setSearchOpen: (open) => set({ searchOpen: open }),
  toggleDevTools: () => set((s) => ({ devToolsOpen: !s.devToolsOpen })),
  setDevToolsTab: (tab) => set({ devToolsTab: tab }),
  toggleCompactMode: () => set((s) => ({ compactMode: !s.compactMode })),

  syncFromHash: () => {
    set({ route: parseHash(window.location.hash) });
  },
}));
