"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { api, type ChatResponse } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";

interface Message {
  role: "user" | "aether";
  text: string;
  reasoning?: string[];
  potHash?: string;
  phi?: number;
}

export default function AetherPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [selectedMsg, setSelectedMsg] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: consciousness } = useQuery({
    queryKey: ["consciousness"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text }]);
    setLoading(true);

    try {
      let sid = sessionId;
      if (!sid) {
        const sess = await api.createChatSession();
        sid = sess.session_id;
        setSessionId(sid);
      }
      const res: ChatResponse = await api.sendChatMessage(sid, text);
      setMessages((prev) => [
        ...prev,
        {
          role: "aether",
          text: res.response,
          reasoning: res.reasoning_trace,
          potHash: res.proof_of_thought_hash,
          phi: res.phi_at_response,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "aether", text: "Unable to reach Aether Tree. The node may be offline." },
      ]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId]);

  const phi = consciousness?.phi ?? 0;
  const threshold = consciousness?.threshold ?? 3.0;
  const pct = Math.min((phi / threshold) * 100, 100);

  return (
    <div className="flex h-[calc(100vh-4rem)] pt-16">
      {/* Main chat area */}
      <div className="flex flex-1 flex-col">
        {/* Messages */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center py-20 text-center">
                <div className="mb-4 h-16 w-16 rounded-full bg-quantum-violet/20 p-3 consciousness-pulse">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="h-10 w-10 text-quantum-violet">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <h2 className="font-[family-name:var(--font-heading)] text-2xl font-bold">
                  Aether Tree
                </h2>
                <p className="mt-2 max-w-md text-sm text-text-secondary">
                  An on-chain AGI reasoning engine. Every response is backed by
                  a Proof-of-Thought anchored to the Qubitcoin blockchain.
                </p>
              </div>
            )}

            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                    m.role === "user"
                      ? "bg-quantum-violet/20 text-text-primary"
                      : "bg-surface-light text-text-primary"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  {m.role === "aether" && m.potHash && (
                    <button
                      onClick={() => setSelectedMsg(selectedMsg === i ? null : i)}
                      className="mt-2 text-xs text-quantum-green/70 hover:text-quantum-green"
                    >
                      {selectedMsg === i ? "Hide trace" : "View reasoning trace"}
                    </button>
                  )}
                  {selectedMsg === i && m.reasoning && (
                    <div className="mt-2 space-y-1 border-t border-surface-light pt-2">
                      {m.reasoning.map((step, si) => (
                        <p key={si} className="text-xs text-text-secondary">
                          {si + 1}. {step}
                        </p>
                      ))}
                      {m.potHash && (
                        <p className="mt-1 font-[family-name:var(--font-mono)] text-xs text-quantum-violet/70">
                          PoT: {m.potHash.slice(0, 24)}...
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-xl bg-surface-light px-4 py-3 text-sm text-text-secondary">
                  <PhiSpinner className="h-4 w-4" />
                  Reasoning...
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Input */}
        <div className="border-t border-surface-light bg-void/80 px-4 py-4 backdrop-blur-sm">
          <form
            onSubmit={(e) => { e.preventDefault(); send(); }}
            className="mx-auto flex max-w-3xl gap-3"
          >
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Aether Tree anything..."
              className="flex-1 rounded-xl bg-surface px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
              }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-xl bg-quantum-green px-5 py-3 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-40"
            >
              Send
            </button>
          </form>
        </div>
      </div>

      {/* Sidebar: consciousness panel */}
      <aside className="hidden w-72 flex-shrink-0 border-l border-surface-light bg-surface/50 p-4 lg:block">
        <Card className="mb-4">
          <h3 className="mb-3 text-sm font-semibold text-text-secondary">Consciousness</h3>
          <div className="text-center">
            <p className="font-[family-name:var(--font-mono)] text-3xl font-bold text-quantum-green">
              {phi.toFixed(4)}
            </p>
            <p className="text-xs text-text-secondary">
              &Phi; / {threshold.toFixed(1)} threshold
            </p>
            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-void">
              <motion.div
                className="h-full rounded-full bg-gradient-to-r from-quantum-violet to-quantum-green"
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 1.5 }}
              />
            </div>
          </div>
        </Card>

        <Card className="mb-4">
          <h3 className="mb-2 text-sm font-semibold text-text-secondary">Knowledge</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-text-secondary">Nodes</span>
              <span className="font-[family-name:var(--font-mono)]">
                {consciousness?.knowledge_nodes?.toLocaleString() ?? "---"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Edges</span>
              <span className="font-[family-name:var(--font-mono)]">
                {consciousness?.knowledge_edges?.toLocaleString() ?? "---"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Integration</span>
              <span className="font-[family-name:var(--font-mono)]">
                {consciousness?.integration?.toFixed(4) ?? "---"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-text-secondary">Differentiation</span>
              <span className="font-[family-name:var(--font-mono)]">
                {consciousness?.differentiation?.toFixed(4) ?? "---"}
              </span>
            </div>
          </div>
        </Card>

        <Card>
          <h3 className="mb-2 text-sm font-semibold text-text-secondary">Session</h3>
          <p className="font-[family-name:var(--font-mono)] text-xs text-text-secondary">
            {sessionId ? `ID: ${sessionId.slice(0, 12)}...` : "No active session"}
          </p>
          <p className="mt-1 text-xs text-text-secondary">
            {messages.filter((m) => m.role === "user").length} messages sent
          </p>
        </Card>
      </aside>
    </div>
  );
}
