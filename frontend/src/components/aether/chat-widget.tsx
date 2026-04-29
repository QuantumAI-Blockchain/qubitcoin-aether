"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslations } from "next-intl";
import { api, type AetherChatTurn } from "@/lib/api";
import { AetherMarkdown } from "@/components/aether/aether-markdown";

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
  const [aetherSessionId, setAetherSessionId] = useState<string | null>(null);
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
      // Build conversation history for context continuity
      const history: AetherChatTurn[] = messages
        .map((m) => ({
          role: m.role === "user" ? "user" as const : "assistant" as const,
          content: m.text,
        }));
      history.push({ role: "user", content: text });

      // Send to Aether Mind neural engine (Rust + Ollama)
      const res = await api.sendAetherChat(text, "anonymous", aetherSessionId, history);
      if (res.session_id) setAetherSessionId(res.session_id);
      setMessages((prev) => [
        ...prev,
        { role: "aether", text: res.response },
      ]);
    } catch {
      // Fallback to API gateway chat endpoint
      try {
        let sid = sessionId;
        if (!sid) {
          const sess = await api.createChatSession();
          sid = sess.session_id;
          setSessionId(sid);
        }
        const res = await api.sendChatMessage(sid, text);
        setMessages((prev) => [
          ...prev,
          { role: "aether", text: res.response },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          { role: "aether", text: t("offline") },
        ]);
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
          aria-label="Open Aether chat"
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-quantum-violet text-white shadow-lg transition hover:scale-105 hover:bg-quantum-violet/90 active:scale-95"
        >
          <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </button>
      )}

      {/* Chat panel — full-screen on mobile, floating on desktop */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="fixed z-50 flex flex-col overflow-hidden border border-border-subtle bg-bg-panel shadow-2xl inset-0 rounded-none sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[420px] sm:w-[360px] sm:rounded-2xl"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-border-subtle px-4 py-3 min-h-[52px]">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-quantum-green consciousness-pulse" />
                <span className="text-sm font-semibold">{t("title")}</span>
              </div>
              <button
                onClick={() => setOpen(false)}
                className="flex items-center justify-center w-10 h-10 -mr-2 text-text-secondary hover:text-text-primary rounded-lg hover:bg-white/5"
              >
                <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3" style={{ WebkitOverflowScrolling: "touch" }}>
              {messages.map((m, i) => (
                <div
                  key={i}
                  className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "ml-auto bg-quantum-violet/20 text-text-primary"
                      : "bg-bg-elevated text-text-primary"
                  }`}
                >
                  {m.role === "aether" ? (
                    <AetherMarkdown>{m.text}</AetherMarkdown>
                  ) : (
                    m.text
                  )}
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

            {/* Input — safe area padding for iOS notch */}
            <form
              onSubmit={(e) => { e.preventDefault(); send(); }}
              className="border-t border-border-subtle px-4 py-3 pb-[max(0.75rem,env(safe-area-inset-bottom))]"
            >
              <div className="flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={t("placeholder")}
                  className="flex-1 rounded-lg bg-bg-deep px-3 py-3 text-base text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-1 focus:ring-quantum-violet sm:py-2 sm:text-sm"
                />
                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  className="rounded-lg bg-quantum-green px-4 py-3 text-sm font-medium text-void transition hover:bg-quantum-green/80 disabled:opacity-40 active:scale-95 sm:py-2"
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
