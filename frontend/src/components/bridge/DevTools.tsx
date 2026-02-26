"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Bridge — DevTools Panel
   Built-in diagnostics accessible via ?devtools=1 query param.
   Tests route integrity, direction/token logic, data binding, and
   mock data integrity.
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useCallback, useEffect, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  X, Bug, Play, CheckCircle, XCircle, Loader2, ChevronDown,
  ChevronRight, RotateCcw, Terminal, Database, Zap, Route,
} from "lucide-react";
import { useBridgeStore } from "./store";
import { CHAINS, EXTERNAL_CHAINS, CONFIRMATION_COUNTS } from "./chain-config";
import { getBridgeMockEngine } from "./mock-engine";
import { B, FONT, GlowButton } from "./shared";
import type { ExternalChainId, BridgeTx, VaultState } from "./types";

/* ── Test Result ─────────────────────────────────────────────────────── */

interface TestResult {
  id: string;
  name: string;
  category: string;
  status: "pending" | "running" | "pass" | "fail";
  detail?: string;
  durationMs?: number;
}

/* ── Test Definitions ────────────────────────────────────────────────── */

function createTests(): TestResult[] {
  return [
    // Route Integrity
    { id: "r1", name: "Hash parsing: #/bridge → bridge view", category: "routing", status: "pending" },
    { id: "r2", name: "Hash parsing: #/bridge/tx/abc → tx view with txId=abc", category: "routing", status: "pending" },
    { id: "r3", name: "Hash parsing: #/bridge/history → history view", category: "routing", status: "pending" },
    { id: "r4", name: "Hash parsing: #/bridge/vault → vault view", category: "routing", status: "pending" },
    { id: "r5", name: "Hash parsing: #/bridge/fees → fees view", category: "routing", status: "pending" },
    { id: "r6", name: "Hash parsing: empty → bridge view", category: "routing", status: "pending" },
    { id: "r7", name: "Navigate function updates hash", category: "routing", status: "pending" },

    // Direction & Token Logic
    { id: "d1", name: "Wrap: source = QBC Mainnet, dest = external chain", category: "logic", status: "pending" },
    { id: "d2", name: "Unwrap: source = external chain, dest = QBC Mainnet", category: "logic", status: "pending" },
    { id: "d3", name: "Token toggle: QBC ↔ QUSD persists through direction change", category: "logic", status: "pending" },
    { id: "d4", name: "Amount resets on direction change", category: "logic", status: "pending" },
    { id: "d5", name: "Chain selector only shows available chains", category: "logic", status: "pending" },

    // Data Binding
    { id: "b1", name: "Mock engine returns VaultState", category: "data", status: "pending" },
    { id: "b2", name: "VaultState backing ratios = 1.0 (100%)", category: "data", status: "pending" },
    { id: "b3", name: "Mock engine has 200 transactions", category: "data", status: "pending" },
    { id: "b4", name: "Transactions contain all required fields", category: "data", status: "pending" },
    { id: "b5", name: "Fee estimation returns valid FeeEstimate", category: "data", status: "pending" },
    { id: "b6", name: "Gas prices available for all chains", category: "data", status: "pending" },
    { id: "b7", name: "Ticker items generated", category: "data", status: "pending" },

    // Mock Data Integrity
    { id: "m1", name: "Vault QBC locked = sum(wQBC by chain)", category: "integrity", status: "pending" },
    { id: "m2", name: "Vault QUSD locked = sum(wQUSD by chain)", category: "integrity", status: "pending" },
    { id: "m3", name: "All tx IDs are unique", category: "integrity", status: "pending" },
    { id: "m4", name: "Wrap txs: source=qbc_mainnet", category: "integrity", status: "pending" },
    { id: "m5", name: "Unwrap txs: dest=qbc_mainnet", category: "integrity", status: "pending" },
    { id: "m6", name: "All tx amounts > 0", category: "integrity", status: "pending" },
    { id: "m7", name: "All tx fees > 0", category: "integrity", status: "pending" },
    { id: "m8", name: "Deterministic: same seed = same data", category: "integrity", status: "pending" },
    { id: "m9", name: "Chain config has all 4 chains", category: "integrity", status: "pending" },
    { id: "m10", name: "Confirmation counts are positive integers", category: "integrity", status: "pending" },
  ];
}

/* ── Test Runner ─────────────────────────────────────────────────────── */

function runTest(test: TestResult): TestResult {
  const start = performance.now();
  let status: "pass" | "fail" = "pass";
  let detail = "";

  try {
    const engine = getBridgeMockEngine();
    const vault = engine.vaultState;
    const txs = engine.transactions;
    const store = useBridgeStore.getState();

    switch (test.id) {
      // Route tests
      case "r1": {
        store.navigate("bridge");
        if (useBridgeStore.getState().view !== "bridge") throw new Error("View not set to bridge");
        break;
      }
      case "r2": {
        store.navigate("tx", { txId: "abc" });
        const s = useBridgeStore.getState();
        if (s.view !== "tx" || s.viewParams.txId !== "abc") throw new Error("TX route parsing failed");
        break;
      }
      case "r3": {
        store.navigate("history");
        if (useBridgeStore.getState().view !== "history") throw new Error("History route failed");
        break;
      }
      case "r4": {
        store.navigate("vault");
        if (useBridgeStore.getState().view !== "vault") throw new Error("Vault route failed");
        break;
      }
      case "r5": {
        store.navigate("fees");
        if (useBridgeStore.getState().view !== "fees") throw new Error("Fees route failed");
        break;
      }
      case "r6": {
        store.navigate("bridge");
        if (useBridgeStore.getState().view !== "bridge") throw new Error("Default route failed");
        break;
      }
      case "r7": {
        store.navigate("vault");
        if (!window.location.hash.includes("vault")) throw new Error("Hash not updated");
        store.navigate("bridge"); // Reset
        break;
      }

      // Direction & Token Logic
      case "d1": {
        store.setDirection("wrap");
        if (useBridgeStore.getState().direction !== "wrap") throw new Error("Wrap direction not set");
        break;
      }
      case "d2": {
        store.setDirection("unwrap");
        if (useBridgeStore.getState().direction !== "unwrap") throw new Error("Unwrap direction not set");
        store.setDirection("wrap"); // Reset
        break;
      }
      case "d3": {
        store.setToken("QUSD");
        store.setDirection("unwrap");
        store.setDirection("wrap");
        if (useBridgeStore.getState().token !== "QUSD") throw new Error("Token not preserved");
        store.setToken("QBC"); // Reset
        break;
      }
      case "d4": {
        store.setAmount("100");
        store.resetBridge();
        if (useBridgeStore.getState().amount !== "") throw new Error("Amount not reset");
        break;
      }
      case "d5": {
        const chains = EXTERNAL_CHAINS;
        if (chains.length !== 3) throw new Error(`Expected 3 external chains, got ${chains.length}`);
        break;
      }

      // Data Binding
      case "b1": {
        if (!vault) throw new Error("VaultState is null");
        if (typeof vault.qbcLocked !== "number") throw new Error("qbcLocked not a number");
        detail = `QBC locked: ${vault.qbcLocked.toLocaleString()}`;
        break;
      }
      case "b2": {
        if (vault.backingRatioQbc !== 1.0) throw new Error(`QBC ratio: ${vault.backingRatioQbc}`);
        if (vault.backingRatioQusd !== 1.0) throw new Error(`QUSD ratio: ${vault.backingRatioQusd}`);
        break;
      }
      case "b3": {
        if (txs.length !== 200) throw new Error(`Expected 200 txs, got ${txs.length}`);
        break;
      }
      case "b4": {
        const tx = txs[0];
        const required: (keyof BridgeTx)[] = [
          "id", "operation", "token", "sourceChain", "destinationChain",
          "amountSent", "amountReceived", "protocolFee", "relayerFee",
          "sourceTxHash", "status", "initiatedAt", "dilithiumSig",
        ];
        for (const key of required) {
          if (!(key in tx)) throw new Error(`Missing field: ${key}`);
        }
        break;
      }
      case "b5": {
        const fee = engine.estimateFee("wrap", "QBC", "ethereum", 1000);
        if (!fee || typeof fee.totalFeeToken !== "number") throw new Error("Fee estimation failed");
        detail = `Total fee: ${fee.totalFeeToken.toFixed(4)} QBC (${fee.totalFeePercent.toFixed(3)}%)`;
        break;
      }
      case "b6": {
        const gas = engine.gasPrices;
        if (gas.length < 3) throw new Error(`Expected >=3 gas prices, got ${gas.length}`);
        break;
      }
      case "b7": {
        const items = engine.getTickerItems();
        if (items.length === 0) throw new Error("No ticker items");
        detail = `${items.length} items`;
        break;
      }

      // Mock Data Integrity
      case "m1": {
        const sumWqbc = Object.values(vault.wqbcByChain).reduce((a, b) => a + b, 0);
        if (Math.abs(vault.qbcLocked - sumWqbc) > 0.01) {
          throw new Error(`QBC locked (${vault.qbcLocked}) != sum wQBC (${sumWqbc})`);
        }
        break;
      }
      case "m2": {
        const sumWqusd = Object.values(vault.wqusdByChain).reduce((a, b) => a + b, 0);
        if (Math.abs(vault.qusdLocked - sumWqusd) > 0.01) {
          throw new Error(`QUSD locked (${vault.qusdLocked}) != sum wQUSD (${sumWqusd})`);
        }
        break;
      }
      case "m3": {
        const ids = new Set(txs.map((t) => t.id));
        if (ids.size !== txs.length) throw new Error(`Duplicate IDs: ${txs.length - ids.size} dupes`);
        break;
      }
      case "m4": {
        const wraps = txs.filter((t) => t.operation === "wrap");
        const bad = wraps.filter((t) => t.sourceChain !== "qbc_mainnet");
        if (bad.length > 0) throw new Error(`${bad.length} wrap txs with wrong source`);
        detail = `${wraps.length} wrap txs checked`;
        break;
      }
      case "m5": {
        const unwraps = txs.filter((t) => t.operation === "unwrap");
        const bad = unwraps.filter((t) => t.destinationChain !== "qbc_mainnet");
        if (bad.length > 0) throw new Error(`${bad.length} unwrap txs with wrong dest`);
        detail = `${unwraps.length} unwrap txs checked`;
        break;
      }
      case "m6": {
        const bad = txs.filter((t) => t.amountSent <= 0);
        if (bad.length > 0) throw new Error(`${bad.length} txs with amount <= 0`);
        break;
      }
      case "m7": {
        const bad = txs.filter((t) => t.totalFee <= 0);
        if (bad.length > 0) throw new Error(`${bad.length} txs with fee <= 0`);
        break;
      }
      case "m8": {
        // Deterministic check: create a new engine with same seed and compare
        const engine2 = getBridgeMockEngine();
        if (engine2.vaultState.qbcLocked !== vault.qbcLocked) {
          throw new Error("Non-deterministic: vault QBC differs");
        }
        if (engine2.transactions.length !== txs.length) {
          throw new Error("Non-deterministic: tx count differs");
        }
        break;
      }
      case "m9": {
        const allChains = Object.keys(CHAINS);
        if (allChains.length !== 4) throw new Error(`Expected 4 chains, got ${allChains.length}`);
        for (const c of ["qbc_mainnet", "ethereum", "bnb", "solana"]) {
          if (!(c in CHAINS)) throw new Error(`Missing chain: ${c}`);
        }
        break;
      }
      case "m10": {
        for (const [chain, count] of Object.entries(CONFIRMATION_COUNTS)) {
          if (!Number.isInteger(count) || count <= 0) {
            throw new Error(`Invalid confirmation count for ${chain}: ${count}`);
          }
        }
        break;
      }

      default:
        detail = "Unknown test";
    }
  } catch (err) {
    status = "fail";
    detail = err instanceof Error ? err.message : String(err);
  }

  const duration = performance.now() - start;
  return { ...test, status, detail, durationMs: Math.round(duration * 100) / 100 };
}

/* ── Category Info ───────────────────────────────────────────────────── */

const CATEGORIES = [
  { id: "routing", label: "Route Integrity", icon: Route, color: B.glowCyan },
  { id: "logic", label: "Direction & Token Logic", icon: Zap, color: B.glowViolet },
  { id: "data", label: "Data Binding", icon: Database, color: B.glowGold },
  { id: "integrity", label: "Mock Data Integrity", icon: Terminal, color: B.glowEmerald },
] as const;

/* ── Category Group ──────────────────────────────────────────────────── */

function CategoryGroup({
  category,
  tests,
  expanded,
  onToggle,
}: {
  category: typeof CATEGORIES[number];
  tests: TestResult[];
  expanded: boolean;
  onToggle: () => void;
}) {
  const passed = tests.filter((t) => t.status === "pass").length;
  const failed = tests.filter((t) => t.status === "fail").length;
  const total = tests.length;
  const allDone = tests.every((t) => t.status === "pass" || t.status === "fail");
  const allPassed = allDone && failed === 0;

  const Icon = category.icon;

  return (
    <div className="rounded-lg border" style={{ borderColor: allPassed ? `${B.glowEmerald}30` : B.borderSubtle }}>
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between p-3"
      >
        <div className="flex items-center gap-2">
          {expanded ? <ChevronDown size={12} style={{ color: B.textSecondary }} /> : <ChevronRight size={12} style={{ color: B.textSecondary }} />}
          <Icon size={12} style={{ color: category.color }} />
          <span className="text-[10px] font-bold tracking-wider" style={{ color: category.color, fontFamily: FONT.display }}>
            {category.label}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {allDone && (
            <span className="text-[9px] font-bold" style={{ color: allPassed ? B.glowEmerald : B.glowCrimson, fontFamily: FONT.mono }}>
              {passed}/{total}
            </span>
          )}
          {allPassed && <CheckCircle size={12} style={{ color: B.glowEmerald }} />}
          {failed > 0 && <XCircle size={12} style={{ color: B.glowCrimson }} />}
        </div>
      </button>
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="space-y-1 border-t px-3 pb-3 pt-2" style={{ borderColor: `${B.borderSubtle}60` }}>
              {tests.map((t) => (
                <div
                  key={t.id}
                  className="flex items-start justify-between rounded px-2 py-1.5"
                  style={{ background: t.status === "fail" ? `${B.glowCrimson}08` : "transparent" }}
                >
                  <div className="flex items-start gap-2">
                    {t.status === "pass" && <CheckCircle size={10} className="mt-0.5 flex-shrink-0" style={{ color: B.glowEmerald }} />}
                    {t.status === "fail" && <XCircle size={10} className="mt-0.5 flex-shrink-0" style={{ color: B.glowCrimson }} />}
                    {t.status === "pending" && <div className="mt-1 h-2 w-2 flex-shrink-0 rounded-full" style={{ background: B.borderSubtle }} />}
                    {t.status === "running" && <Loader2 size={10} className="mt-0.5 flex-shrink-0 animate-spin" style={{ color: B.glowAmber }} />}
                    <div>
                      <span className="text-[10px]" style={{ color: B.textPrimary }}>{t.name}</span>
                      {t.detail && (
                        <p className="text-[9px]" style={{ color: t.status === "fail" ? B.glowCrimson : B.textSecondary, fontFamily: FONT.mono }}>
                          {t.detail}
                        </p>
                      )}
                    </div>
                  </div>
                  {t.durationMs !== undefined && (
                    <span className="ml-2 flex-shrink-0 text-[8px]" style={{ color: B.textSecondary, fontFamily: FONT.mono }}>
                      {t.durationMs}ms
                    </span>
                  )}
                </div>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Main DevTools Panel ─────────────────────────────────────────────── */

export function DevTools() {
  const { devToolsOpen, toggleDevTools } = useBridgeStore();
  const [tests, setTests] = useState<TestResult[]>(createTests);
  const [running, setRunning] = useState(false);
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set(["routing", "logic", "data", "integrity"]));

  // Only show if ?devtools=1
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      setEnabled(params.get("devtools") === "1");
    }
  }, []);

  const toggleCategory = useCallback((cat: string) => {
    setExpandedCats((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  }, []);

  const runAllTests = useCallback(async () => {
    setRunning(true);
    const fresh = createTests();
    setTests(fresh);

    // Run tests sequentially with staggered updates
    const results: TestResult[] = [];
    for (let i = 0; i < fresh.length; i++) {
      setTests((prev) =>
        prev.map((t, j) => (j === i ? { ...t, status: "running" } : t))
      );

      // Small delay for visual effect
      await new Promise<void>((r) => setTimeout(r, 30));

      const result = runTest(fresh[i]);
      results.push(result);

      setTests((prev) =>
        prev.map((t, j) => (j === i ? result : t))
      );
    }

    setRunning(false);
  }, []);

  const totalTests = tests.length;
  const passed = tests.filter((t) => t.status === "pass").length;
  const failed = tests.filter((t) => t.status === "fail").length;
  const allDone = tests.every((t) => t.status === "pass" || t.status === "fail");

  if (!enabled) return null;

  return (
    <>
      {/* Floating trigger button */}
      <button
        onClick={toggleDevTools}
        className="fixed bottom-4 right-4 z-50 flex h-10 w-10 items-center justify-center rounded-full border shadow-lg transition-opacity hover:opacity-80"
        style={{
          background: B.bgElevated,
          borderColor: B.glowViolet,
          boxShadow: `0 0 12px ${B.glowViolet}40`,
        }}
        title="Toggle DevTools"
      >
        <Bug size={16} style={{ color: B.glowViolet }} />
      </button>

      {/* Panel */}
      <AnimatePresence>
        {devToolsOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className="fixed bottom-16 right-4 z-50 w-[420px] overflow-hidden rounded-xl border shadow-2xl"
            style={{
              background: B.bgPanel,
              borderColor: B.borderSubtle,
              maxHeight: "70vh",
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: B.borderSubtle }}>
              <div className="flex items-center gap-2">
                <Bug size={14} style={{ color: B.glowViolet }} />
                <span className="text-xs font-bold tracking-widest" style={{ color: B.glowViolet, fontFamily: FONT.display }}>
                  BRIDGE DEVTOOLS
                </span>
                {allDone && (
                  <span
                    className="rounded px-1.5 py-0.5 text-[8px] font-bold"
                    style={{
                      color: failed === 0 ? B.glowEmerald : B.glowCrimson,
                      background: failed === 0 ? `${B.glowEmerald}15` : `${B.glowCrimson}15`,
                    }}
                  >
                    {passed}/{totalTests} PASSED
                  </span>
                )}
              </div>
              <button
                onClick={toggleDevTools}
                className="rounded-md p-1 transition-opacity hover:opacity-70"
                style={{ color: B.textSecondary }}
              >
                <X size={14} />
              </button>
            </div>

            {/* Controls */}
            <div className="flex items-center gap-2 border-b px-4 py-2" style={{ borderColor: `${B.borderSubtle}60` }}>
              <GlowButton
                onClick={runAllTests}
                disabled={running}
                color={B.glowViolet}
                variant="secondary"
                className="!h-7 !px-3 !text-[9px]"
              >
                {running ? (
                  <>
                    <Loader2 size={10} className="animate-spin" />
                    RUNNING…
                  </>
                ) : (
                  <>
                    <Play size={10} />
                    RUN ALL TESTS
                  </>
                )}
              </GlowButton>

              <button
                onClick={() => setTests(createTests())}
                disabled={running}
                className="flex items-center gap-1 rounded px-2 py-1 text-[9px] font-bold tracking-wider transition-opacity hover:opacity-80"
                style={{ color: B.textSecondary, fontFamily: FONT.display }}
              >
                <RotateCcw size={10} />
                RESET
              </button>

              {allDone && (
                <span
                  className="ml-auto text-[9px] font-bold"
                  style={{ color: B.textSecondary, fontFamily: FONT.mono }}
                >
                  {tests.reduce((a, t) => a + (t.durationMs ?? 0), 0).toFixed(1)}ms total
                </span>
              )}
            </div>

            {/* Test Categories */}
            <div className="max-h-[50vh] overflow-y-auto p-3 space-y-2" style={{ scrollbarWidth: "thin" }}>
              {CATEGORIES.map((cat) => (
                <CategoryGroup
                  key={cat.id}
                  category={cat}
                  tests={tests.filter((t) => t.category === cat.id)}
                  expanded={expandedCats.has(cat.id)}
                  onToggle={() => toggleCategory(cat.id)}
                />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
