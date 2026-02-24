"use client";

import { useEffect } from "react";
import { chainSocket } from "@/lib/websocket";
import { useChainStore } from "@/stores/chain-store";
import type { WSBlockData, WSTransactionData, WSPhiData } from "@/stores/chain-store";
import type { WSMessage } from "@/lib/websocket";

/**
 * Headless provider that connects the shared ChainSocket to the Zustand
 * chain store. Mount once at the app root (inside Providers).
 *
 * It:
 * 1. Connects the WebSocket on mount
 * 2. Subscribes to `new_block`, `new_transaction`, and `phi_update` events
 * 3. Dispatches incoming data into `useChainStore`
 * 4. Tracks connection state in the store for UI indicators
 *
 * Renders nothing visible — just wires plumbing.
 */
export function ChainSocketProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  useEffect(() => {
    const store = useChainStore.getState();

    // -- Track connection state in the store --------------------------------
    const offState = chainSocket.onStateChange((state) => {
      useChainStore.getState().setWsState(state);
    });

    // -- Subscribe to chain events ------------------------------------------

    const offBlock = chainSocket.on<WSBlockData>("new_block", (msg: WSMessage<WSBlockData>) => {
      useChainStore.getState().setLatestBlock(msg.data);
    });

    const offTx = chainSocket.on<WSTransactionData>(
      "new_transaction",
      (msg: WSMessage<WSTransactionData>) => {
        useChainStore.getState().setLatestTransaction(msg.data);
      },
    );

    const offPhi = chainSocket.on<WSPhiData>("phi_update", (msg: WSMessage<WSPhiData>) => {
      useChainStore.getState().setLatestPhi(msg.data);
    });

    // -- Connect ------------------------------------------------------------
    // Sync initial state before connect in case it is already connected
    store.setWsState(chainSocket.state);
    chainSocket.connect();

    // -- Cleanup on unmount (full app teardown) -----------------------------
    return () => {
      offState();
      offBlock();
      offTx();
      offPhi();
      chainSocket.disconnect();
    };
  }, []);

  return <>{children}</>;
}
