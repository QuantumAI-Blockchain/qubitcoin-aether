"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import {
  chainSocket,
  type ChainEventType,
  type ConnectionState,
  type MessageHandler,
  type WSMessage,
} from "@/lib/websocket";

// ---------------------------------------------------------------------------
// useChainSocket — connect + subscribe to multiple event types
// ---------------------------------------------------------------------------

interface UseChainSocketOptions {
  /**
   * Event types to subscribe to. Pass `["*"]` for all events.
   * Changes to this array will update subscriptions automatically.
   */
  events?: ChainEventType[];

  /** Called for every matching event. */
  onMessage?: MessageHandler;

  /**
   * Whether to auto-connect on mount. Defaults to `true`.
   * Set to `false` if you want to connect manually via `chainSocket.connect()`.
   */
  autoConnect?: boolean;
}

interface UseChainSocketReturn {
  /** Current connection state. */
  state: ConnectionState;

  /** Convenience: `state === "connected"`. */
  connected: boolean;

  /** The shared ChainSocket instance (for imperative use if needed). */
  socket: typeof chainSocket;
}

/**
 * React hook that manages the shared ChainSocket lifecycle.
 *
 * - Auto-connects on mount (unless `autoConnect: false`)
 * - Subscribes to the specified event types
 * - Cleans up subscriptions on unmount or when `events` changes
 * - Tracks connection state reactively
 *
 * @example
 * ```tsx
 * function BlockCounter() {
 *   const [height, setHeight] = useState(0);
 *   const { connected } = useChainSocket({
 *     events: ["new_block"],
 *     onMessage: (msg) => setHeight(msg.data.height as number),
 *   });
 *   return <div>{connected ? `Block ${height}` : "Connecting..."}</div>;
 * }
 * ```
 */
export function useChainSocket(
  options: UseChainSocketOptions = {},
): UseChainSocketReturn {
  const { events = [], onMessage, autoConnect = true } = options;

  const [state, setState] = useState<ConnectionState>(chainSocket.state);

  // Keep onMessage in a ref so subscriptions don't re-fire when the
  // callback identity changes (common with inline arrow functions).
  const handlerRef = useRef(onMessage);
  handlerRef.current = onMessage;

  // Stable handler that delegates to the latest ref
  const stableHandler: MessageHandler = useCallback((msg) => {
    handlerRef.current?.(msg);
  }, []);

  // -- Connection state tracking -------------------------------------------
  useEffect(() => {
    // Sync initial state in case it changed between render and effect
    setState(chainSocket.state);

    const off = chainSocket.onStateChange((s) => setState(s));
    return off;
  }, []);

  // -- Auto-connect on mount -----------------------------------------------
  useEffect(() => {
    if (autoConnect) {
      chainSocket.connect();
    }
    // We intentionally do NOT disconnect on unmount — the singleton stays
    // alive for the entire app session. Only explicit disconnect() kills it.
  }, [autoConnect]);

  // -- Event subscriptions -------------------------------------------------
  useEffect(() => {
    if (events.length === 0 || !stableHandler) return;

    // Subscribe to each requested event type
    const unsubscribers = events.map((eventType) =>
      chainSocket.on(eventType, stableHandler),
    );

    return () => {
      unsubscribers.forEach((off) => off());
    };
    // Re-subscribe when the event list changes. We serialize to a string
    // to avoid reference-equality issues with array literals.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events.join(","), stableHandler]);

  return {
    state,
    connected: state === "connected",
    socket: chainSocket,
  };
}

// ---------------------------------------------------------------------------
// useChainEvent — convenience hook for a single event type
// ---------------------------------------------------------------------------

/**
 * Subscribe to a single WebSocket event type and get the latest message.
 *
 * @example
 * ```tsx
 * function PhiMeter() {
 *   const msg = useChainEvent("phi_update");
 *   if (!msg) return <div>Waiting for Phi update...</div>;
 *   return <div>Phi: {msg.data.phi as number}</div>;
 * }
 * ```
 */
export function useChainEvent<T = Record<string, unknown>>(
  eventType: ChainEventType,
): WSMessage<T> | null {
  const [latest, setLatest] = useState<WSMessage<T> | null>(null);

  useChainSocket({
    events: [eventType],
    onMessage: (msg) => setLatest(msg as WSMessage<T>),
  });

  return latest;
}

// ---------------------------------------------------------------------------
// useConnectionState — just the connection state, no event subscriptions
// ---------------------------------------------------------------------------

/**
 * Reactively track the WebSocket connection state without subscribing
 * to any events. Useful for status indicators.
 *
 * @example
 * ```tsx
 * function StatusDot() {
 *   const state = useConnectionState();
 *   const color = state === "connected" ? "green" : state === "connecting" ? "yellow" : "red";
 *   return <span style={{ color }}>{state}</span>;
 * }
 * ```
 */
export function useConnectionState(): ConnectionState {
  const { state } = useChainSocket({ events: [], autoConnect: true });
  return state;
}
