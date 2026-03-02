"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Built-in DevTools Panel
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, Database, Activity, Gauge, ChevronDown, ChevronRight } from "lucide-react";
import { useExplorerStore } from "./store";
import { useNetworkStats } from "./hooks";
// eslint-disable-next-line @typescript-eslint/no-require-imports
const getMockEngine = () => (require("./mock-engine") as typeof import("./mock-engine")).getMockEngine();
import { C, FONT } from "./shared";

/* ── State Tab ────────────────────────────────────────────────────────── */

function StateTab() {
  const store = useExplorerStore();
  const engine = getMockEngine();

  const stateData = useMemo(
    () => ({
      route: store.route,
      historyLength: store.history.length,
      searchQuery: store.searchQuery,
      searchOpen: store.searchOpen,
      compactMode: store.compactMode,
      mockEngine: {
        blocks: engine.blocks.length,
        transactions: engine.transactions.length,
        contracts: engine.contracts.length,
        aetherNodes: engine.aetherNodes.length,
        aetherEdges: engine.aetherEdges.length,
        miners: engine.miners.length,
      },
    }),
    [store.route, store.history.length, store.searchQuery, store.searchOpen, store.compactMode, engine]
  );

  return (
    <div className="space-y-2 text-[10px]" style={{ fontFamily: FONT.mono }}>
      <JsonTree data={stateData} label="Explorer State" />
    </div>
  );
}

/* ── Network Tab ──────────────────────────────────────────────────────── */

function NetworkTab() {
  const { data: stats } = useNetworkStats();

  return (
    <div className="space-y-2 text-[10px]" style={{ fontFamily: FONT.mono }}>
      {stats ? (
        <JsonTree data={stats} label="Network Stats" />
      ) : (
        <span style={{ color: C.textMuted }}>Loading...</span>
      )}
      <div className="mt-3 border-t pt-2" style={{ borderColor: `${C.border}60` }}>
        <span style={{ color: C.textMuted }}>API Endpoint: </span>
        <span style={{ color: C.primary }}>MockDataEngine (client-side)</span>
      </div>
      <div>
        <span style={{ color: C.textMuted }}>Data Source: </span>
        <span style={{ color: C.accent }}>Deterministic PRNG (seed: 3301)</span>
      </div>
    </div>
  );
}

/* ── Perf Tab ─────────────────────────────────────────────────────────── */

function PerfTab() {
  const [fps, setFps] = useState(0);
  const [memory, setMemory] = useState<{ used: number; total: number } | null>(null);

  useEffect(() => {
    let frameCount = 0;
    let lastTime = performance.now();
    let running = true;

    function tick() {
      if (!running) return;
      frameCount++;
      const now = performance.now();
      if (now - lastTime >= 1000) {
        setFps(frameCount);
        frameCount = 0;
        lastTime = now;
      }

      // Memory (Chrome only)
      const perf = performance as Performance & { memory?: { usedJSHeapSize: number; totalJSHeapSize: number } };
      if (perf.memory) {
        setMemory({
          used: perf.memory.usedJSHeapSize / 1048576,
          total: perf.memory.totalJSHeapSize / 1048576,
        });
      }

      requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
    return () => { running = false; };
  }, []);

  return (
    <div className="space-y-3 text-[10px]" style={{ fontFamily: FONT.mono }}>
      <div className="flex items-center justify-between">
        <span style={{ color: C.textMuted }}>FPS</span>
        <span
          style={{
            color: fps >= 55 ? C.success : fps >= 30 ? C.warning : C.error,
            fontWeight: "bold",
          }}
        >
          {fps}
        </span>
      </div>

      {/* FPS bar */}
      <div className="h-1.5 overflow-hidden rounded-full" style={{ background: `${C.border}40` }}>
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${Math.min(100, (fps / 60) * 100)}%`,
            background: fps >= 55 ? C.success : fps >= 30 ? C.warning : C.error,
          }}
        />
      </div>

      {memory && (
        <>
          <div className="flex items-center justify-between">
            <span style={{ color: C.textMuted }}>JS Heap</span>
            <span style={{ color: C.textPrimary }}>
              {memory.used.toFixed(1)} / {memory.total.toFixed(1)} MB
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full" style={{ background: `${C.border}40` }}>
            <div
              className="h-full rounded-full"
              style={{
                width: `${(memory.used / memory.total) * 100}%`,
                background: memory.used / memory.total > 0.8 ? C.error : C.primary,
              }}
            />
          </div>
        </>
      )}

      <div className="border-t pt-2" style={{ borderColor: `${C.border}60` }}>
        <span style={{ color: C.textMuted }}>React Version: </span>
        <span style={{ color: C.textPrimary }}>19.x</span>
      </div>
      <div>
        <span style={{ color: C.textMuted }}>Build: </span>
        <span style={{ color: C.textPrimary }}>Development (Mock Data)</span>
      </div>
    </div>
  );
}

/* ── JSON Tree Component ──────────────────────────────────────────────── */

function JsonTree({ data, label }: { data: unknown; label: string }) {
  const [open, setOpen] = useState(true);

  if (data === null || data === undefined) {
    return <span style={{ color: C.textMuted }}>null</span>;
  }

  if (typeof data !== "object") {
    const color =
      typeof data === "number"
        ? C.accent
        : typeof data === "boolean"
          ? C.secondary
          : typeof data === "string"
            ? C.success
            : C.textPrimary;
    return <span style={{ color }}>{JSON.stringify(data)}</span>;
  }

  const entries = Object.entries(data as Record<string, unknown>);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1"
        style={{ color: C.primary }}
      >
        {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        <span style={{ fontWeight: "bold" }}>{label}</span>
        <span style={{ color: C.textMuted }}>
          {Array.isArray(data) ? `[${entries.length}]` : `{${entries.length}}`}
        </span>
      </button>
      {open && (
        <div className="ml-3 border-l pl-2" style={{ borderColor: `${C.border}60` }}>
          {entries.map(([key, val]) => (
            <div key={key} className="flex items-start gap-1 py-0.5">
              <span style={{ color: C.textSecondary }}>{key}: </span>
              {typeof val === "object" && val !== null ? (
                <JsonTree data={val} label="" />
              ) : (
                <JsonTree data={val} label="" />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── DevTools Panel ───────────────────────────────────────────────────── */

export function DevToolsPanel() {
  const { devToolsOpen, toggleDevTools, devToolsTab, setDevToolsTab } =
    useExplorerStore();

  const tabs = [
    { id: "state" as const, label: "State", icon: Database },
    { id: "network" as const, label: "Network", icon: Activity },
    { id: "perf" as const, label: "Perf", icon: Gauge },
  ];

  return (
    <AnimatePresence>
      {devToolsOpen && (
        <motion.div
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ type: "spring", damping: 25, stiffness: 300 }}
          className="fixed right-0 top-0 z-[60] flex h-full w-80 flex-col border-l shadow-2xl"
          style={{ background: C.bg, borderColor: C.border }}
        >
          {/* Header */}
          <div
            className="flex items-center justify-between border-b px-3 py-2"
            style={{ borderColor: C.border }}
          >
            <span
              className="text-[10px] uppercase tracking-widest"
              style={{ color: C.textMuted, fontFamily: FONT.heading }}
            >
              DevTools
            </span>
            <button onClick={toggleDevTools}>
              <X size={14} style={{ color: C.textSecondary }} />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b" style={{ borderColor: C.border }}>
            {tabs.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setDevToolsTab(id)}
                className="flex flex-1 items-center justify-center gap-1.5 py-2 text-[10px] transition-colors"
                style={{
                  color: devToolsTab === id ? C.primary : C.textSecondary,
                  background: devToolsTab === id ? `${C.primary}10` : "transparent",
                  fontFamily: FONT.heading,
                  letterSpacing: "0.05em",
                }}
              >
                <Icon size={12} />
                {label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-3">
            {devToolsTab === "state" && <StateTab />}
            {devToolsTab === "network" && <NetworkTab />}
            {devToolsTab === "perf" && <PerfTab />}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
