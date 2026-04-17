"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useTelegramStore } from "@/stores/telegram-store";
import { useWalletStore } from "@/stores/wallet-store";
import { api, type ChatResponse } from "@/lib/api";
import { hapticFeedback, hapticNotification, showBackButton, hideBackButton } from "@/lib/telegram";
import { StreamingText } from "@/components/aether/streaming-text";
import { PhiSpinner } from "@/components/ui/loading";

interface Message {
  role: "user" | "aether";
  text: string;
  reasoning?: string[];
  potHash?: string;
  phi?: number;
}

export default function TWAChatPage() {
  const { user } = useTelegramStore();
  const { address } = useWalletStore();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streamingIdx, setStreamingIdx] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Back button
  useEffect(() => {
    showBackButton(() => {
      window.history.back();
    });
    return () => hideBackButton();
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);
    hapticFeedback("light");

    try {
      let sid = sessionId;
      if (!sid) {
        const sess = await api.createChatSession(address ?? "");
        sid = sess.session_id;
        setSessionId(sid);
      }
      const res: ChatResponse = await api.sendChatMessage(sid, text);
      setMessages((prev) => {
        const idx = prev.length;
        setStreamingIdx(idx);
        return [
          ...prev,
          {
            role: "aether",
            text: res.response,
            reasoning: res.reasoning_trace,
            potHash: res.proof_of_thought_hash,
            phi: res.phi_at_response,
          },
        ];
      });
      hapticNotification("success");
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "aether", text: "Unable to reach Aether Tree. The node may be offline." },
      ]);
      hapticNotification("error");
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, address]);

  return (
    <div className="flex h-[calc(100vh-5rem)] flex-col">
      {/* Header */}
      <div className="border-b border-border-subtle px-4 py-3">
        <h1 className="font-[family-name:var(--font-display)] text-sm font-bold">Aether Chat</h1>
        <p className="text-[10px] text-text-secondary">On-chain AI reasoning engine</p>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4">
        <div className="space-y-3">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="mb-3 h-12 w-12 rounded-full bg-quantum-violet/20 p-2 consciousness-pulse">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-8 w-8 text-quantum-violet">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </div>
              <p className="text-sm font-semibold text-text-primary">Ask Aether anything</p>
              <p className="mt-1 text-xs text-text-secondary">
                Every response is backed by a Proof-of-Thought
              </p>
            </div>
          )}

          {messages.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-3 py-2 text-xs ${
                  m.role === "user"
                    ? "bg-quantum-violet/20 text-text-primary"
                    : "bg-bg-elevated text-text-primary"
                }`}
              >
                <p className="whitespace-pre-wrap">
                  {m.role === "aether" && i === streamingIdx ? (
                    <StreamingText
                      text={m.text}
                      speed={12}
                      onComplete={() => setStreamingIdx(null)}
                    />
                  ) : (
                    m.text
                  )}
                </p>
                {m.potHash && (
                  <p className="mt-1 font-[family-name:var(--font-code)] text-[9px] text-quantum-violet/50">
                    PoT: {m.potHash.slice(0, 16)}...
                  </p>
                )}
              </div>
            </motion.div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="flex items-center gap-2 rounded-2xl bg-bg-elevated px-3 py-2 text-xs text-text-secondary">
                <PhiSpinner className="h-3 w-3" />
                Reasoning...
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-border-subtle bg-bg-deep/80 px-4 py-3 backdrop-blur-sm">
        <form
          onSubmit={(e) => { e.preventDefault(); send(); }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask anything..."
            className="flex-1 rounded-2xl bg-bg-panel px-4 py-2.5 text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-1 focus:ring-quantum-violet/50"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="haptic-tap rounded-2xl bg-quantum-green px-4 py-2.5 text-xs font-semibold text-void transition disabled:opacity-40"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
