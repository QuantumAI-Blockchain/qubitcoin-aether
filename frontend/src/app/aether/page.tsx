"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { api, type ChatResponse, type AetherChatTurn } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { useToast } from "@/components/ui/toast";
import { AetherMarkdown } from "@/components/aether/aether-markdown";
import {
  ConversationSidebar,
  type StoredSession,
  loadSessions,
  saveSessions,
  saveSessionMessages,
  loadSessionMessages,
  deleteSessionStorage,
} from "@/components/aether/conversation-sidebar";
import { ContributionIndicator } from "@/components/aikgs/contribution-indicator";
import { useWalletStore, getAuthToken } from "@/stores/wallet-store";

interface Message {
  id: string;
  role: "user" | "aether";
  text: string;
  reasoning?: string[];
  potHash?: string;
  phi?: number;
  emotionalState?: Record<string, number>;
}

let _msgCounter = 0;
function nextMsgId(): string {
  return `msg-${Date.now()}-${++_msgCounter}`;
}

function deriveTitle(messages: Message[]): string {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "New Chat";
  const text = first.text.slice(0, 40);
  return text.length < first.text.length ? `${text}...` : text;
}

/* --- Reasoning type detection and styling --- */

type ReasoningType = "deductive" | "inductive" | "abductive" | "observation" | "conclusion";

const REASONING_STYLES: Record<ReasoningType, { label: string; color: string; bg: string }> = {
  deductive:   { label: "DED", color: "text-quantum-green",  bg: "bg-quantum-green/10" },
  inductive:   { label: "IND", color: "text-quantum-violet", bg: "bg-quantum-violet/10" },
  abductive:   { label: "ABD", color: "text-amber-400",      bg: "bg-amber-400/10" },
  observation: { label: "OBS", color: "text-sky-400",         bg: "bg-sky-400/10" },
  conclusion:  { label: "CON", color: "text-emerald-400",     bg: "bg-emerald-400/10" },
};

function detectReasoningType(step: string): ReasoningType {
  const lower = step.toLowerCase();
  if (lower.startsWith("[deductive]") || lower.includes("therefore") || lower.includes("follows that"))
    return "deductive";
  if (lower.startsWith("[inductive]") || lower.includes("pattern") || lower.includes("generalize"))
    return "inductive";
  if (lower.startsWith("[abductive]") || lower.includes("hypothesis") || lower.includes("best explanation"))
    return "abductive";
  if (lower.startsWith("[observation]") || lower.includes("observe") || lower.includes("given"))
    return "observation";
  if (lower.startsWith("[conclusion]") || lower.includes("conclude") || lower.includes("result"))
    return "conclusion";
  // Default: treat early steps as observations, middle as deductive, last as conclusion
  return "deductive";
}

function stripTypePrefix(step: string): string {
  return step.replace(/^\[(deductive|inductive|abductive|observation|conclusion)\]\s*/i, "");
}

/** Collapsible reasoning trace with type-tagged steps in a tree-like DAG view. */
function ReasoningTraceView({ steps, potHash }: { steps: string[]; potHash?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      className="mt-2 border-t border-border-subtle pt-2"
    >
      <p className="mb-1.5 font-[family-name:var(--font-display)] text-[10px] uppercase tracking-wider text-text-secondary">
        Reasoning Trace ({steps.length} steps)
      </p>
      <div className="relative ml-2">
        {/* Vertical connector line */}
        <div className="absolute left-[5px] top-1 bottom-1 w-px bg-border-subtle" />

        {steps.map((step, si) => {
          const detected = detectReasoningType(step);
          const rType = si === 0
            ? detected === "deductive" ? "observation" : detected
            : si === steps.length - 1
              ? "conclusion"
              : detected;
          const style = REASONING_STYLES[rType];
          const cleanStep = stripTypePrefix(step);

          return (
            <div key={si} className="relative flex items-start gap-2 pb-1.5 pl-4">
              {/* Node dot */}
              <div
                className={`absolute left-0 top-1.5 h-[11px] w-[11px] rounded-full border ${style.bg} border-current ${style.color}`}
              />
              {/* Type badge + text */}
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`inline-block rounded px-1 py-0.5 font-[family-name:var(--font-code)] text-[9px] font-bold ${style.color} ${style.bg}`}
                  >
                    {style.label}
                  </span>
                  <span className="text-xs text-text-secondary">
                    {cleanStep}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {potHash && (
        <p className="mt-1.5 font-[family-name:var(--font-code)] text-xs text-quantum-violet/70">
          Proof-of-Thought: {potHash.slice(0, 24)}...
        </p>
      )}
    </motion.div>
  );
}

export default function AetherPage() {
  return (
    <ErrorBoundary>
      <AetherPageContent />
    </ErrorBoundary>
  );
}

function AetherPageContent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  // Aether Mind neural session ID (separate from gateway session)
  const [aetherSessionId, setAetherSessionId] = useState<string | null>(null);
  const [selectedMsg, setSelectedMsg] = useState<number | null>(null);
  const [sessions, setSessions] = useState<StoredSession[]>([]);
  const [activeTab, setActiveTab] = useState<"chat" | "graph">("chat");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  const { address: walletAddress, authAddress, activeNativeWallet } = useWalletStore();
  // Prefer authenticated address (verified via JWT), then MetaMask, then native wallet
  const identityAddress = authAddress ?? walletAddress ?? activeNativeWallet;

  // Load saved sessions on mount
  useEffect(() => {
    setSessions(loadSessions());
  }, []);

  const { data: consciousness } = useQuery({
    queryKey: ["consciousness"],
    queryFn: api.getPhi,
    refetchInterval: 10_000,
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    if (!sessionId || messages.length === 0) return;
    saveSessionMessages(sessionId, messages);

    // Update session metadata
    setSessions((prev) => {
      const userMsgCount = messages.filter((m) => m.role === "user").length;
      const existing = prev.find((s) => s.id === sessionId);
      let updated: StoredSession[];
      if (existing) {
        updated = prev.map((s) =>
          s.id === sessionId
            ? { ...s, title: deriveTitle(messages), messageCount: userMsgCount, updatedAt: Date.now() }
            : s,
        );
      } else {
        updated = [
          ...prev,
          { id: sessionId, title: deriveTitle(messages), messageCount: userMsgCount, updatedAt: Date.now() },
        ];
      }
      saveSessions(updated);
      return updated;
    });
  }, [messages, sessionId]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((prev) => [...prev, { id: nextMsgId(), role: "user", text }]);
    setLoading(true);

    try {
      // Build conversation history from existing messages for context continuity
      const history: AetherChatTurn[] = messages
        .map((m) => ({
          role: m.role === "user" ? "user" as const : "assistant" as const,
          content: m.text,
        }));
      // Add current user message to history
      history.push({ role: "user", content: text });

      // Send to Aether Mind neural engine (Rust + Ollama)
      const res = await api.sendAetherChat(text, identityAddress ?? "anonymous", aetherSessionId, history);
      // Track session ID from server
      if (res.session_id) setAetherSessionId(res.session_id);
      const knowledgeTrace = res.knowledge_context?.length
        ? res.knowledge_context.map((ctx, i) => `[observation] Context ${i + 1}: ${ctx}`)
        : undefined;
      setMessages((prev) => [
        ...prev,
        {
          id: nextMsgId(),
          role: "aether",
          text: res.response,
          reasoning: knowledgeTrace,
          phi: res.phi,
        },
      ]);
    } catch {
      // Fallback to API gateway chat endpoint
      try {
        let sid = sessionId;
        if (!sid) {
          const sess = await api.createChatSession(identityAddress ?? "");
          sid = sess.session_id;
          setSessionId(sid);
        }
        const res: ChatResponse = await api.sendChatMessage(sid, text);
        setMessages((prev) => [
          ...prev,
          {
            id: nextMsgId(),
            role: "aether",
            text: res.response,
            reasoning: res.reasoning_trace,
            potHash: res.proof_of_thought_hash,
            phi: res.phi_at_response,
            emotionalState: res.emotional_state,
          },
        ]);
      } catch {
        setMessages((prev) => [
          ...prev,
          { id: nextMsgId(), role: "aether", text: "Unable to reach Aether Mind. The node may be offline." },
        ]);
        toast("Failed to reach Aether Mind", "error");
      }
    } finally {
      setLoading(false);
    }
  }, [input, loading, sessionId, aetherSessionId, messages, toast, identityAddress]);

  const handleNewChat = useCallback(() => {
    setSessionId(null);
    setAetherSessionId(null);
    setMessages([]);
    setSelectedMsg(null);
  }, []);

  const handleSelectSession = useCallback(async (session: StoredSession) => {
    setSessionId(session.id);
    // Try local first, then fall back to server
    const local = loadSessionMessages(session.id) as Message[];
    if (local.length > 0) {
      // Ensure loaded messages have IDs (older sessions may lack them)
      setMessages(local.map((m) => ({ ...m, id: m.id || nextMsgId() })));
    } else {
      // Attempt to load from server
      try {
        const res = await api.getConversationMessages(session.id);
        const serverMsgs: Message[] = (res.messages ?? []).map((m) => ({
          id: nextMsgId(),
          role: m.role as "user" | "aether",
          text: m.content,
          reasoning: m.reasoning_trace,
          potHash: m.proof_of_thought_hash,
          phi: m.phi_at_response,
          emotionalState: m.emotional_state,
        }));
        setMessages(serverMsgs);
      } catch {
        setMessages([]);
      }
    }
    setSelectedMsg(null);
  }, []);

  const handleDeleteSession = useCallback(
    (id: string) => {
      deleteSessionStorage(id);
      setSessions((prev) => {
        const updated = prev.filter((s) => s.id !== id);
        saveSessions(updated);
        return updated;
      });
      if (sessionId === id) {
        setSessionId(null);
        setMessages([]);
        setSelectedMsg(null);
      }
      toast("Conversation deleted", "info");
    },
    [sessionId, toast],
  );

  const phi = consciousness?.phi ?? 0;
  const threshold = consciousness?.threshold ?? 3.0;
  const pct = Math.min((phi / threshold) * 100, 100);

  return (
    <div className="flex flex-col pt-16">
      <div className="flex h-[calc(100vh-4rem)]">
        {/* Conversation sidebar */}
        <div className="hidden md:block">
          <ConversationSidebar
            sessions={sessions}
            activeSessionId={sessionId}
            onSelect={handleSelectSession}
            onNew={handleNewChat}
            onDelete={handleDeleteSession}
            userAddress={identityAddress}
          />
        </div>

        {/* Main content area — tabs switch between chat and graph */}
        <div className="flex flex-1 flex-col">
          {/* Tab bar */}
          <div className="flex items-center gap-1 border-b border-border-subtle px-3 sm:px-4">
            <button
              role="tab"
              aria-selected={activeTab === "chat"}
              aria-controls="aether-chat-panel"
              onClick={() => setActiveTab("chat")}
              className={`px-3 py-3 text-sm font-medium transition-colors min-h-[44px] sm:px-4 ${
                activeTab === "chat"
                  ? "border-b-2 border-quantum-violet text-text-primary"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Chat
            </button>
            <button
              role="tab"
              aria-selected={activeTab === "graph"}
              aria-controls="aether-graph-panel"
              onClick={() => setActiveTab("graph")}
              className={`px-3 py-3 text-sm font-medium transition-colors min-h-[44px] sm:px-4 ${
                activeTab === "graph"
                  ? "border-b-2 border-quantum-green text-text-primary"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              Knowledge Graph
            </button>
            {/* Mobile new-chat button */}
            <div className="ml-auto flex items-center gap-2 md:hidden">
              <button
                onClick={handleNewChat}
                className="rounded-lg bg-quantum-violet/20 px-3 py-2.5 text-xs font-medium text-quantum-violet active:scale-95 min-h-[44px]"
              >
                + New Chat
              </button>
            </div>
          </div>

          {/* Chat view — visible when chat tab active */}
          {activeTab === "chat" && (
            <div className="flex flex-1 flex-col min-h-0">
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
                      <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold">
                        Aether Mind
                      </h2>
                      <p className="mt-2 max-w-md text-sm text-text-secondary">
                        A neural cognitive engine running pure Rust. Every response is backed by
                        consciousness metrics and a Proof-of-Thought anchored to the QBC blockchain.
                      </p>
                    </div>
                  )}

                  {messages.map((m, i) => (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`max-w-[80%] rounded-xl px-4 py-3 text-sm ${
                          m.role === "user"
                            ? "bg-quantum-violet/20 text-text-primary"
                            : "bg-bg-elevated text-text-primary"
                        }`}
                      >
                        {m.role === "aether" ? (
                          <AetherMarkdown>{m.text}</AetherMarkdown>
                        ) : (
                          <p className="whitespace-pre-wrap">{m.text}</p>
                        )}
                        {m.role === "aether" && m.emotionalState && Object.keys(m.emotionalState).length > 0 && (
                          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-text-secondary">
                            <span className="font-medium text-quantum-violet/80">Feeling:</span>
                            {Object.entries(m.emotionalState)
                              .sort(([, a], [, b]) => b - a)
                              .slice(0, 3)
                              .map(([emotion, value]) => (
                                <span key={emotion} className="inline-flex items-center gap-1">
                                  <span className="text-text-primary">{emotion}</span>
                                  <span className="inline-block h-1.5 rounded-full bg-quantum-violet/40" style={{ width: `${Math.round(value * 40)}px` }} />
                                  <span className="font-[family-name:var(--font-code)] text-quantum-green/70">{value.toFixed(2)}</span>
                                </span>
                              ))}
                          </div>
                        )}
                        {m.role === "aether" && m.phi != null && m.phi > 0 && (
                          <p className="mt-1 font-[family-name:var(--font-code)] text-[10px] text-quantum-green/50">
                            &Phi; at response: {m.phi.toFixed(4)}
                          </p>
                        )}
                        {m.role === "aether" && m.potHash && (
                          <button
                            onClick={() => setSelectedMsg(selectedMsg === i ? null : i)}
                            className="mt-2 text-xs text-quantum-green/70 hover:text-quantum-green"
                          >
                            {selectedMsg === i ? "Hide trace" : "View reasoning trace"}
                          </button>
                        )}
                        {selectedMsg === i && m.reasoning && (
                          <ReasoningTraceView steps={m.reasoning} potHash={m.potHash} />
                        )}
                      </div>
                    </motion.div>
                  ))}

                  {loading && (
                    <div className="flex justify-start">
                      <div className="flex items-center gap-2 rounded-xl bg-bg-elevated px-4 py-3 text-sm text-text-secondary">
                        <PhiSpinner className="h-4 w-4" />
                        Reasoning...
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Input — safe area padding for iOS */}
              <div className="border-t border-border-subtle bg-bg-deep/80 px-3 py-3 backdrop-blur-sm sm:px-4 sm:py-4" style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))" }}>
                <form
                  onSubmit={(e) => { e.preventDefault(); send(); }}
                  className="mx-auto flex max-w-3xl gap-2 sm:gap-3"
                >
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Ask Aether Mind anything..."
                    autoComplete="off"
                    className="flex-1 rounded-xl bg-bg-panel px-4 py-3 text-base text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50 sm:text-sm"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
                    }}
                  />
                  <button
                    type="submit"
                    disabled={loading || !input.trim()}
                    className="rounded-xl bg-quantum-green px-4 py-3 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-40 active:scale-95 flex-shrink-0 sm:px-5"
                  >
                    Send
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* Knowledge Vectors — stats display */}
          {activeTab === "graph" && (
            <div className="flex-1 min-h-0 p-4">
              <div className="mx-auto max-w-3xl">
                <Card className="p-6">
                  <h3 className="mb-4 font-[family-name:var(--font-display)] text-xl font-bold text-text-primary">
                    Knowledge Fabric
                  </h3>
                  <p className="mb-2 text-sm text-text-secondary">
                    The Aether Mind stores learned knowledge as high-dimensional vector embeddings
                    in an HNSW (Hierarchical Navigable Small World) index, enabling O(log n) semantic search
                    across the entire knowledge fabric.
                  </p>
                  <div className="mt-4 flex items-baseline gap-2">
                    <span className="font-[family-name:var(--font-code)] text-4xl font-bold text-quantum-green">
                      {consciousness?.knowledge_nodes?.toLocaleString() ?? "---"}
                    </span>
                    <span className="text-sm text-text-secondary">knowledge vectors in HNSW fabric</span>
                  </div>
                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-text-secondary">Embedding Dimensions</span>
                      <p className="font-[family-name:var(--font-code)] text-lg font-semibold">896d</p>
                    </div>
                    <div>
                      <span className="text-text-secondary">Sephirot Domains</span>
                      <p className="font-[family-name:var(--font-code)] text-lg font-semibold">10</p>
                    </div>
                  </div>
                  <a
                    href="/docs/aether"
                    className="mt-4 inline-block text-sm text-quantum-violet hover:text-quantum-violet/80 transition-colors"
                  >
                    Learn more about the Aether architecture &rarr;
                  </a>
                </Card>
              </div>
            </div>
          )}
        </div>

        {/* Sidebar: integration panel */}
        <aside className="hidden w-72 flex-shrink-0 border-l border-border-subtle bg-bg-panel p-4 overflow-y-auto lg:block">
          <Card className="mb-4">
            <h3 className="mb-3 text-sm font-semibold text-text-secondary">Integration Status</h3>
            <div className="text-center">
              <p className="font-[family-name:var(--font-code)] text-3xl font-bold text-quantum-green">
                {phi.toFixed(4)}
              </p>
              <p className="text-xs text-text-secondary">
                &Phi; / {threshold.toFixed(1)} threshold
              </p>
              <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-bg-deep">
                <motion.div
                  className="h-full rounded-full bg-gradient-to-r from-quantum-violet to-quantum-green"
                  initial={{ width: 0 }}
                  animate={{ width: `${pct}%` }}
                  transition={{ duration: 1.5 }}
                />
              </div>
            </div>
          </Card>

          {/* Gate Progress (v2+) */}
          {(consciousness?.phi_version ?? 0) >= 2 && (
            <Card className="mb-4">
              <h3 className="mb-2 text-sm font-semibold text-text-secondary">Milestone Gates</h3>
              <div className="flex items-center justify-between">
                <span className="font-[family-name:var(--font-code)] text-lg font-bold text-quantum-violet">
                  {consciousness?.gates_passed ?? 0}/{consciousness?.gates_total ?? 10}
                </span>
                <span className="text-xs text-text-secondary">gates passed</span>
              </div>
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-bg-deep">
                <div
                  className="h-full rounded-full bg-quantum-violet transition-all duration-700"
                  style={{ width: `${((consciousness?.gates_passed ?? 0) / (consciousness?.gates_total ?? 10)) * 100}%` }}
                />
              </div>
              {consciousness?.gate_ceiling != null && (
                <p className="mt-1.5 text-xs text-text-secondary">
                  Ceiling: <span className="font-[family-name:var(--font-code)]">{consciousness.gate_ceiling.toFixed(1)}</span>
                </p>
              )}
            </Card>
          )}

          <Card className="mb-4">
            <h3 className="mb-2 text-sm font-semibold text-text-secondary">Neural Consciousness</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-text-secondary">Knowledge Vectors</span>
                <span className="font-[family-name:var(--font-code)]">
                  {consciousness?.knowledge_nodes?.toLocaleString() ?? "---"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Phi Micro (IIT 3.0)</span>
                <span className="font-[family-name:var(--font-code)]">
                  {consciousness?.phi_micro?.toFixed(6) ?? "---"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Phi Meso (Cross-Domain)</span>
                <span className="font-[family-name:var(--font-code)]">
                  {consciousness?.phi_meso?.toFixed(6) ?? "---"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Phi Macro (Layer Flow)</span>
                <span className="font-[family-name:var(--font-code)]">
                  {consciousness?.phi_macro?.toFixed(6) ?? "---"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Blocks Processed</span>
                <span className="font-[family-name:var(--font-code)]">
                  {consciousness?.blocks_processed?.toLocaleString() ?? "---"}
                </span>
              </div>
            </div>
          </Card>

          <Card className="mb-4">
            <h3 className="mb-2 text-sm font-semibold text-text-secondary">Session</h3>
            <p className="font-[family-name:var(--font-code)] text-xs text-text-secondary">
              {sessionId ? `ID: ${sessionId.slice(0, 12)}...` : "No active session"}
            </p>
            <p className="mt-1 text-xs text-text-secondary">
              {messages.filter((m) => m.role === "user").length} messages sent
            </p>
            {identityAddress ? (
              <div className="mt-2 flex items-center gap-1.5">
                <div className="h-2 w-2 rounded-full bg-quantum-green" />
                <span className="font-[family-name:var(--font-code)] text-[10px] text-quantum-green/80">
                  {identityAddress.slice(0, 8)}...{identityAddress.slice(-6)}
                </span>
                {authAddress && (
                  <span className="rounded bg-quantum-green/10 px-1 py-0.5 text-[9px] font-medium text-quantum-green">
                    JWT
                  </span>
                )}
              </div>
            ) : (
              <p className="mt-2 text-[10px] text-text-secondary/60">
                Connect wallet for persistent history
              </p>
            )}
          </Card>

          <ContributionIndicator className="mb-4" compact />
        </aside>
      </div>
    </div>
  );
}
