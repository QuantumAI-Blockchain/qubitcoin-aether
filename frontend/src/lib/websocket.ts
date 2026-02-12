import { WS_URL } from "./constants";

type MessageHandler = (data: Record<string, unknown>) => void;

/** Lightweight WebSocket client for real-time chain events. */
export class ChainSocket {
  private ws: WebSocket | null = null;
  private handlers: Map<string, Set<MessageHandler>> = new Map();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;
    try {
      this.ws = new WebSocket(WS_URL);
      this.ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);
          const type: string = msg.type ?? "unknown";
          this.handlers.get(type)?.forEach((h) => h(msg));
          this.handlers.get("*")?.forEach((h) => h(msg));
        } catch { /* ignore malformed */ }
      };
      this.ws.onclose = () => this.scheduleReconnect();
      this.ws.onerror = () => this.ws?.close();
    } catch { /* env without WebSocket */ }
  }

  on(type: string, handler: MessageHandler): () => void {
    if (!this.handlers.has(type)) this.handlers.set(type, new Set());
    this.handlers.get(type)!.add(handler);
    return () => this.handlers.get(type)?.delete(handler);
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3300); // reconnect after 3.3s (phi timing)
  }
}
