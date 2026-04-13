"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { api, type ConversationSession, type ConversationStats } from "@/lib/api";

export interface StoredSession {
  id: string;
  title: string;
  messageCount: number;
  updatedAt: number;
}

const STORAGE_KEY = "qbc-aether-sessions";

/** Read saved session list from localStorage. */
export function loadSessions(): StoredSession[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredSession[]) : [];
  } catch {
    return [];
  }
}

/** Persist session list to localStorage. */
export function saveSessions(sessions: StoredSession[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  } catch {
    /* quota exceeded -- silently ignore */
  }
}

/** Save messages for a specific session. */
export function saveSessionMessages(sessionId: string, messages: unknown[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(`qbc-chat-${sessionId}`, JSON.stringify(messages));
  } catch {
    /* quota exceeded */
  }
}

/** Load messages for a specific session. */
export function loadSessionMessages(sessionId: string): unknown[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(`qbc-chat-${sessionId}`);
    return raw ? (JSON.parse(raw) as unknown[]) : [];
  } catch {
    return [];
  }
}

/** Delete a session and its messages from localStorage. */
export function deleteSessionStorage(sessionId: string): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(`qbc-chat-${sessionId}`);
}

/** Convert a server ConversationSession to the local StoredSession shape. */
function toStoredSession(s: ConversationSession): StoredSession {
  return {
    id: s.session_id,
    title: s.title || `Session ${s.session_id.slice(0, 8)}`,
    messageCount: s.message_count,
    updatedAt: s.last_active * 1000,
  };
}

interface ConversationSidebarProps {
  sessions: StoredSession[];
  activeSessionId: string | null;
  onSelect: (session: StoredSession) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  userAddress?: string | null;
}

export function ConversationSidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNew,
  onDelete,
  userAddress,
}: ConversationSidebarProps) {
  const [historyTab, setHistoryTab] = useState<"local" | "server">("local");

  // Fetch server-side conversation history when user has an address
  const { data: serverSessions } = useQuery({
    queryKey: ["conversations", userAddress],
    queryFn: () => api.getConversations(userAddress!),
    enabled: historyTab === "server" && !!userAddress,
    refetchInterval: 30_000,
    retry: false,
  });

  // Fetch conversation stats
  const { data: stats } = useQuery({
    queryKey: ["conversationStats"],
    queryFn: api.getConversationStats,
    refetchInterval: 60_000,
    retry: false,
  });

  const localSorted = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt);
  const serverSorted = (serverSessions?.sessions ?? [])
    .map(toStoredSession)
    .sort((a, b) => b.updatedAt - a.updatedAt);

  const displaySessions = historyTab === "server" ? serverSorted : localSorted;

  return (
    <aside className="flex w-64 flex-shrink-0 flex-col border-r border-border-subtle bg-bg-panel">
      {/* New chat button */}
      <div className="border-b border-border-subtle p-3">
        <button
          onClick={onNew}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-quantum-violet/20 px-3 py-2.5 text-sm font-medium text-quantum-violet transition hover:bg-quantum-violet/30"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Tab switcher: Local / Server */}
      <div className="flex border-b border-border-subtle">
        <button
          onClick={() => setHistoryTab("local")}
          className={`flex-1 px-2 py-2 text-[10px] font-medium uppercase tracking-wider transition ${
            historyTab === "local"
              ? "border-b-2 border-quantum-violet text-quantum-violet"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          Local
        </button>
        <button
          onClick={() => setHistoryTab("server")}
          className={`flex-1 px-2 py-2 text-[10px] font-medium uppercase tracking-wider transition ${
            historyTab === "server"
              ? "border-b-2 border-quantum-green text-quantum-green"
              : "text-text-secondary hover:text-text-primary"
          }`}
        >
          History
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-2">
        {historyTab === "server" && !userAddress && (
          <p className="px-2 py-4 text-center text-xs text-text-secondary">
            Connect a wallet to view conversation history
          </p>
        )}
        {displaySessions.length === 0 && (historyTab === "local" || !!userAddress) && (
          <p className="px-2 py-4 text-center text-xs text-text-secondary">
            No conversations yet
          </p>
        )}
        {displaySessions.map((session) => {
          const active = session.id === activeSessionId;
          return (
            <motion.button
              key={session.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={() => onSelect(session)}
              className={`group mb-1 flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left text-sm transition ${
                active
                  ? "bg-glow-cyan/10 text-glow-cyan"
                  : "text-text-secondary hover:bg-bg-elevated hover:text-text-primary"
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{session.title}</p>
                <p className="mt-0.5 text-xs opacity-60">
                  {session.messageCount} msg{session.messageCount !== 1 ? "s" : ""}
                  {historyTab === "server" && (
                    <span className="ml-1">
                      {new Date(session.updatedAt).toLocaleDateString()}
                    </span>
                  )}
                </p>
              </div>
              {historyTab === "local" && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(session.id);
                  }}
                  className="ml-2 rounded p-1 text-text-secondary opacity-0 transition hover:bg-quantum-red/20 hover:text-quantum-red group-hover:opacity-100"
                  aria-label="Delete conversation"
                >
                  <svg viewBox="0 0 20 20" fill="currentColor" className="h-3.5 w-3.5">
                    <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
                  </svg>
                </button>
              )}
            </motion.button>
          );
        })}
      </div>

      {/* Stats footer */}
      <div className="border-t border-border-subtle px-3 py-2">
        {stats ? (
          <div className="space-y-1 text-center">
            <div className="flex justify-between text-[10px] text-text-secondary">
              <span>Sessions</span>
              <span className="font-[family-name:var(--font-code)] text-text-primary">
                {stats.total_sessions.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between text-[10px] text-text-secondary">
              <span>Messages</span>
              <span className="font-[family-name:var(--font-code)] text-text-primary">
                {stats.total_messages.toLocaleString()}
              </span>
            </div>
            <div className="flex justify-between text-[10px] text-text-secondary">
              <span>Users</span>
              <span className="font-[family-name:var(--font-code)] text-text-primary">
                {stats.unique_users.toLocaleString()}
              </span>
            </div>
          </div>
        ) : (
          <p className="text-center text-xs text-text-secondary/50">
            {historyTab === "local" ? "Stored locally in your browser" : "Loading stats..."}
          </p>
        )}
      </div>
    </aside>
  );
}
