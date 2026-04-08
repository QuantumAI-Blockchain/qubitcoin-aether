"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslations } from "next-intl";
import { api } from "@/lib/api";

interface Message {
  role: "user" | "aether";
  text: string;
  dominantEmotion?: string;
}

export function ChatWidget() {
  const t = useTranslations("chat");
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "aether", text: t("greeting") },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo(0, scrollRef.current.scrollHeight);
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    try {
      // Stream tokens from Aether Engine (Rust) for instant response
      let fullResponse = "";
      const streamIdx = messages.length + 1; // Index of the new aether message

      // Add placeholder message that will be updated with streaming tokens
      setMessages((prev) => [...prev, { role: "aether", text: "" }]);

      for await (const chunk of api.streamChat(text)) {
        if (chunk.done) {
          break;
        }
        fullResponse += chunk.token;
        const captured = fullResponse;
        setMessages((prev) => {
          const updated = [...prev];
          if (updated[streamIdx]) {
            updated[streamIdx] = { ...updated[streamIdx], text: captured };
          }
          return updated;
        });
      }

      // If streaming returned nothing, remove the empty placeholder
      if (!fullResponse) {
        setMessages((prev) => prev.filter((_, i) => i !== streamIdx));
        throw new Error("Empty response");
      }
    } catch {
      // Fallback to Python node chat if Rust engine is unavailable
      try {
        let sid = sessionId;
        if (!sid) {
          const sess = await api.createChatSession();
          sid = sess.session_id;
          setSessionId(sid);
        }
        const res = await api.sendChatMessage(sid, text);
        const dominant = res.emotional_state
          ? Object.entries(res.emotional_state).sort(([, a], [, b]) => b - a)[0]?.[0]
          : undefined;
        setMessages((prev) => {
          // Remove the streaming placeholder if it exists
          const filtered = prev.filter((m) => !(m.role === "aether" && m.text === ""));
          return [...filtered, { role: "aether", text: res.response, dominantEmotion: dominant }];
        });
      } catch {
        setMessages((prev) => {
          const filtered = prev.filter((m) => !(m.role === "aether" && m.text === ""));
          return [...filtered, { role: "aether", text: t("offline") }];
        });
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Toggle */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-quantum-violet text-white shadow-lg transition hover:scale-105 hover:bg-quantum-violet/90"
        >
          <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      )}

      {/* Chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed bottom-6 right-6 z-50 flex h-[420px] w-[360px] flex-col overflow-hidden rounded-2xl border border-border-subtle bg-bg-panel shadow-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-quantum-green consciousness-pulse" />
                <span className="text-sm font-semibold">{t("title")}</span>
              </div>
              <button onClick={() => setOpen(false)} className="text-text-secondary hover:text-text-primary">
                <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "ml-auto bg-quantum-violet/20 text-text-primary"
                      : "bg-bg-elevated text-text-primary"
                  }`}
                >
                  {m.text}
                  {m.role === "aether" && m.dominantEmotion && (
                    <p className="mt-1 text-[10px] text-quantum-violet/60">
                      Feeling {m.dominantEmotion}
                    </p>
                  )}
                </div>
              ))}
              {loading && (
                <div className="max-w-[85%] rounded-lg bg-bg-elevated px-3 py-2 text-sm text-text-secondary">
                  {t("reasoning")}
                </div>
              )}
            </div>

            {/* Input */}
            <form
              onSubmit={(e) => { e.preventDefault(); send(); }}
              className="border-t border-border-subtle px-4 py-3"
            >
              <div className="flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={t("placeholder")}
                  className="flex-1 rounded-lg bg-bg-deep px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-1 focus:ring-quantum-violet"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="rounded-lg bg-quantum-green px-3 py-2 text-sm font-medium text-void transition hover:bg-quantum-green/80 disabled:opacity-40"
                >
                  {t("send")}
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
