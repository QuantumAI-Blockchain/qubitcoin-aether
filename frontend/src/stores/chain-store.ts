import { create } from "zustand";
import type { ChainInfo, PhiData } from "@/lib/api";
import type { ConnectionState } from "@/lib/websocket";

// ---------------------------------------------------------------------------
// Block data pushed over WebSocket (new_block events)
// ---------------------------------------------------------------------------

export interface WSBlockData {
  height: number;
  hash: string;
  timestamp: number;
  transactions: number;
  miner: string;
  reward: number;
  difficulty: number;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Transaction data pushed over WebSocket (new_transaction events)
// ---------------------------------------------------------------------------

export interface WSTransactionData {
  txid: string;
  sender: string;
  recipient: string;
  amount: number;
  fee: number;
  timestamp: number;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Phi data pushed over WebSocket (phi_update events)
// ---------------------------------------------------------------------------

export interface WSPhiData {
  phi: number;
  integration: number;
  differentiation: number;
  knowledge_nodes: number;
  knowledge_edges: number;
  above_threshold: boolean;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

interface ChainState {
  // -- REST-fetched data (existing) ----------------------------------------
  chain: ChainInfo | null;
  phi: PhiData | null;
  setChain: (info: ChainInfo) => void;
  setPhi: (data: PhiData) => void;

  // -- WebSocket-streamed data (new) ---------------------------------------

  /** Connection state of the shared WebSocket. */
  wsState: ConnectionState;
  setWsState: (state: ConnectionState) => void;

  /** Most recent block received via WebSocket. */
  latestBlock: WSBlockData | null;
  setLatestBlock: (block: WSBlockData) => void;

  /** Most recent transaction received via WebSocket. */
  latestTransaction: WSTransactionData | null;
  setLatestTransaction: (tx: WSTransactionData) => void;

  /** Most recent Phi update received via WebSocket. */
  latestPhi: WSPhiData | null;
  setLatestPhi: (phi: WSPhiData) => void;

  /** Rolling count of blocks received since the page loaded. */
  blocksReceivedCount: number;

  /** Rolling count of transactions received since the page loaded. */
  txReceivedCount: number;
}

export const useChainStore = create<ChainState>((set) => ({
  // REST-fetched
  chain: null,
  phi: null,
  setChain: (info) => set({ chain: info }),
  setPhi: (data) => set({ phi: data }),

  // WebSocket-streamed
  wsState: "disconnected",
  setWsState: (wsState) => set({ wsState }),

  latestBlock: null,
  setLatestBlock: (block) =>
    set((s) => ({
      latestBlock: block,
      blocksReceivedCount: s.blocksReceivedCount + 1,
      // Also update chain height if we have chain data
      chain: s.chain
        ? { ...s.chain, height: Math.max(s.chain.height, block.height) }
        : s.chain,
    })),

  latestTransaction: null,
  setLatestTransaction: (tx) =>
    set((s) => ({
      latestTransaction: tx,
      txReceivedCount: s.txReceivedCount + 1,
    })),

  latestPhi: null,
  setLatestPhi: (phi) =>
    set((s) => ({
      latestPhi: phi,
      // Also update the main phi store field to keep REST + WS in sync
      phi: s.phi
        ? {
            ...s.phi,
            phi: phi.phi,
            integration: phi.integration,
            differentiation: phi.differentiation,
            knowledge_nodes: phi.knowledge_nodes,
            knowledge_edges: phi.knowledge_edges,
            above_threshold: phi.above_threshold,
          }
        : s.phi,
    })),

  blocksReceivedCount: 0,
  txReceivedCount: 0,
}));
