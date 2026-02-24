import { WS_URL } from "./constants";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Payload shape for every WS message from the backend. */
export interface WSMessage<T = Record<string, unknown>> {
  type: string;
  data: T;
}

/** Known event types emitted by the QBC node /ws endpoint. */
export type ChainEventType =
  | "new_block"
  | "new_transaction"
  | "phi_update"
  | (string & {}); // allow arbitrary strings while keeping autocomplete

/** Handler callback — receives the full message envelope. */
export type MessageHandler<T = Record<string, unknown>> = (
  msg: WSMessage<T>,
) => void;

/** Observable connection state. */
export type ConnectionState = "disconnected" | "connecting" | "connected";

/** Listener for connection state changes. */
type StateListener = (state: ConnectionState) => void;

// ---------------------------------------------------------------------------
// Reconnection constants (exponential backoff)
// ---------------------------------------------------------------------------

/** Initial delay before first reconnect attempt (ms). */
const BASE_DELAY_MS = 1_000;

/** Maximum delay between reconnect attempts (ms). */
const MAX_DELAY_MS = 30_000;

/** Multiplier applied each successive retry. */
const BACKOFF_FACTOR = 2;

/** Jitter range — random 0..JITTER_MS added to each delay to avoid thundering herd. */
const JITTER_MS = 500;

// ---------------------------------------------------------------------------
// ChainSocket — singleton-friendly WebSocket client
// ---------------------------------------------------------------------------

/**
 * WebSocket client for real-time chain events.
 *
 * Connects to the QBC node `/ws` endpoint, auto-reconnects with capped
 * exponential backoff + jitter, and dispatches parsed JSON messages to
 * registered handlers keyed by event type.
 *
 * Use `"*"` as event type to receive every message (wildcard).
 */
export class ChainSocket {
  // -- internal state -------------------------------------------------------
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private stateListeners: Set<StateListener> = new Set();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectAttempt = 0;
  private _state: ConnectionState = "disconnected";
  private intentionalClose = false;
  private url: string;

  constructor(url: string = WS_URL) {
    this.url = url;
  }

  // -- public API -----------------------------------------------------------

  /** Current connection state. */
  get state(): ConnectionState {
    return this._state;
  }

  /** Whether the socket is open and ready. */
  get connected(): boolean {
    return this._state === "connected";
  }

  /**
   * Open the WebSocket connection.
   * Safe to call multiple times — no-ops if already open or connecting.
   */
  connect(): void {
    if (
      this.ws?.readyState === WebSocket.OPEN ||
      this.ws?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    // Guard: browser/SSR environments without WebSocket
    if (typeof WebSocket === "undefined") return;

    this.intentionalClose = false;
    this.setState("connecting");

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempt = 0;
        this.setState("connected");
      };

      this.ws.onmessage = (evt: MessageEvent) => {
        try {
          const msg: WSMessage = JSON.parse(evt.data as string);
          const type: string = msg.type ?? "unknown";
          // Dispatch to type-specific handlers
          this.handlers.get(type)?.forEach((h) => h(msg));
          // Dispatch to wildcard handlers
          this.handlers.get("*")?.forEach((h) => h(msg));
        } catch {
          // Ignore malformed JSON — the backend should always send valid JSON,
          // but we never want a parse error to kill the connection.
        }
      };

      this.ws.onclose = () => {
        this.setState("disconnected");
        if (!this.intentionalClose) {
          this.scheduleReconnect();
        }
      };

      this.ws.onerror = () => {
        // The browser fires `onerror` right before `onclose` — just close
        // so the reconnect logic in onclose kicks in.
        this.ws?.close();
      };
    } catch {
      // Environment without WebSocket (SSR, test runners, etc.)
      this.setState("disconnected");
    }
  }

  /**
   * Subscribe to a specific event type.
   *
   * @param type - Event type string (e.g. `"new_block"`, `"phi_update"`) or
   *               `"*"` for all events.
   * @param handler - Callback invoked with the full `WSMessage` envelope.
   * @returns An unsubscribe function — call it to remove the handler.
   *
   * @example
   * ```ts
   * const off = chainSocket.on("new_block", (msg) => {
   *   console.log("Block height:", msg.data.height);
   * });
   * // later:
   * off();
   * ```
   */
  on<T = Record<string, unknown>>(
    type: ChainEventType | "*",
    handler: MessageHandler<T>,
  ): () => void {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set());
    }
    // Cast is safe: the generic is purely for caller convenience — the
    // underlying Set stores MessageHandler (generic erased at runtime).
    this.handlers.get(type)!.add(handler as MessageHandler);

    return () => {
      this.handlers.get(type)?.delete(handler as MessageHandler);
      // Clean up empty sets to avoid memory leaks over long sessions
      if (this.handlers.get(type)?.size === 0) {
        this.handlers.delete(type);
      }
    };
  }

  /**
   * Subscribe to connection state changes.
   *
   * @returns An unsubscribe function.
   */
  onStateChange(listener: StateListener): () => void {
    this.stateListeners.add(listener);
    return () => {
      this.stateListeners.delete(listener);
    };
  }

  /**
   * Gracefully close the WebSocket. No auto-reconnect will occur.
   * Call `connect()` again to re-establish the connection.
   */
  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    this.reconnectAttempt = 0;
    if (this.ws) {
      this.ws.onclose = null; // prevent reconnect from firing
      this.ws.close();
      this.ws = null;
    }
    this.setState("disconnected");
  }

  // -- private helpers ------------------------------------------------------

  private setState(next: ConnectionState): void {
    if (this._state === next) return;
    this._state = next;
    this.stateListeners.forEach((fn) => fn(next));
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Schedule a reconnection with exponential backoff + jitter.
   *
   * delay = min(BASE_DELAY * BACKOFF^attempt, MAX_DELAY) + random(0, JITTER)
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer !== null) return;

    const exponential = BASE_DELAY_MS * Math.pow(BACKOFF_FACTOR, this.reconnectAttempt);
    const capped = Math.min(exponential, MAX_DELAY_MS);
    const jitter = Math.random() * JITTER_MS;
    const delay = capped + jitter;

    this.reconnectAttempt += 1;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}

// ---------------------------------------------------------------------------
// Singleton instance — import this in components / hooks
// ---------------------------------------------------------------------------

/**
 * Shared `ChainSocket` instance for the entire app.
 *
 * ```ts
 * import { chainSocket } from "@/lib/websocket";
 * chainSocket.connect();
 * const off = chainSocket.on("new_block", (msg) => { ... });
 * ```
 */
export const chainSocket = new ChainSocket();
