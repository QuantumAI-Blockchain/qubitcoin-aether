"use client";
/* ─────────────────────────────────────────────────────────────────────────
   QBC Explorer — Aether AGI Transparency Explorer (8-tab dashboard)

   Replaces the old D3 force graph with a comprehensive AGI transparency
   dashboard exposing every aspect of the Aether Tree's cognition.
   ───────────────────────────────────────────────────────────────────────── */

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Brain, Network, Eye, Zap, GitBranch, Shield, Clock,
  Activity, Target, AlertTriangle, CheckCircle, XCircle,
  Layers, Atom, Search, ChevronRight, Sparkles,
} from "lucide-react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar, Cell,
} from "recharts";
import {
  useKnowledgeNodes, useReasoningOps, useConsciousnessState,
  useConsciousnessEvents, useSephirotNodes, useSephirotBalance,
  usePredictions, useSafetyEvents, useProofOfThought, usePoTStats, useHiggsField,
  usePinealPhase, useMemoryStats, usePhiHistory, useAetherEdges,
} from "./hooks";
import {
  C, FONT, LoadingSpinner, Panel, SectionHeader, StatCard,
  Badge, formatNumber, timeAgo,
} from "./shared";
import type {
  KnowledgeNodeDetail, ReasoningOperation, SephirotNode,
  PredictionRecord, SafetyEvent, ProofOfThought, ConsciousnessEvent,
} from "./types";

/* ── Tab definitions ─────────────────────────────────────────────────── */

type AetherTab =
  | "knowledge"
  | "reasoning"
  | "integration"
  | "mind"
  | "sephirot"
  | "predictions"
  | "safety"
  | "proofs";

const TABS: { id: AetherTab; label: string; icon: typeof Brain }[] = [
  { id: "knowledge", label: "Knowledge", icon: Network },
  { id: "reasoning", label: "Reasoning", icon: GitBranch },
  { id: "integration", label: "Integration", icon: Brain },
  { id: "mind", label: "Mind", icon: Atom },
  { id: "sephirot", label: "Sephirot", icon: Layers },
  { id: "predictions", label: "Predictions", icon: Target },
  { id: "safety", label: "Safety", icon: Shield },
  { id: "proofs", label: "Proof-of-Thought", icon: Zap },
];

/* ── Node type colors ────────────────────────────────────────────────── */

const NODE_COLORS: Record<string, string> = {
  assertion: C.primary,
  observation: C.success,
  inference: C.secondary,
  axiom: C.accent,
};

const REASONING_COLORS: Record<string, string> = {
  deductive: C.primary,
  inductive: C.success,
  abductive: C.secondary,
};

const SEVERITY_COLORS: Record<string, string> = {
  low: C.success,
  medium: C.accent,
  high: "#f97316",
  critical: C.error,
};

const SEPHIROT_COLORS: Record<string, string> = {
  Keter: "#ffd700",
  Chochmah: "#7c3aed",
  Binah: "#3b82f6",
  Chesed: "#22c55e",
  Gevurah: "#ef4444",
  Tiferet: "#f59e0b",
  Netzach: "#10b981",
  Hod: "#f97316",
  Yesod: "#8b5cf6",
  Malkuth: "#64748b",
};

/* ── Shared sub-components ───────────────────────────────────────────── */

function TabBar({
  active,
  onChange,
}: {
  active: AetherTab;
  onChange: (t: AetherTab) => void;
}) {
  return (
    <div
      className="flex gap-1 overflow-x-auto rounded-lg border p-1"
      style={{ background: C.surface, borderColor: C.border }}
    >
      {TABS.map(({ id, label, icon: Icon }) => {
        const isActive = active === id;
        return (
          <button
            key={id}
            onClick={() => onChange(id)}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-xs transition-colors"
            style={{
              color: isActive ? C.primary : C.textSecondary,
              background: isActive ? `${C.primary}15` : "transparent",
              fontFamily: FONT.body,
            }}
          >
            <Icon size={13} />
            <span className="hidden sm:inline">{label}</span>
          </button>
        );
      })}
    </div>
  );
}

function MiniBar({
  value,
  max,
  color,
}: {
  value: number;
  max: number;
  color: string;
}) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div
      className="h-1.5 w-full overflow-hidden rounded-full"
      style={{ background: `${C.border}40` }}
    >
      <div
        className="h-full rounded-full transition-all"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <Brain size={32} style={{ color: C.textMuted, opacity: 0.3 }} />
      <p
        className="mt-3 text-xs"
        style={{ color: C.textMuted, fontFamily: FONT.body }}
      >
        {message}
      </p>
    </div>
  );
}

/* ── Tab 1: Knowledge ────────────────────────────────────────────────── */

function KnowledgeTab() {
  const { data: nodes, isLoading } = useKnowledgeNodes(200);
  const { data: edges } = useAetherEdges();
  const { data: consciousness } = useConsciousnessState();
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // Total counts from consciousness endpoint (real totals, not fetched slice)
  const totalNodes = consciousness?.knowledgeNodes ?? nodes?.length ?? 0;
  const totalEdges = consciousness?.knowledgeEdges ?? edges?.length ?? 0;

  const filtered = useMemo(() => {
    if (!nodes) return [];
    return nodes.filter((n) => {
      if (typeFilter !== "all" && n.type !== typeFilter) return false;
      if (search && !n.content.toLowerCase().includes(search.toLowerCase()))
        return false;
      return true;
    });
  }, [nodes, search, typeFilter]);

  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const n of nodes ?? []) c[n.type] = (c[n.type] ?? 0) + 1;
    return c;
  }, [nodes]);

  const edgeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const e of edges ?? []) c[e.type] = (c[e.type] ?? 0) + 1;
    return c;
  }, [edges]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      {/* Stats row */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Nodes" value={formatNumber(totalNodes)} icon={Network} color={C.primary} />
        <StatCard label="Total Edges" value={formatNumber(totalEdges)} icon={GitBranch} color={C.secondary} />
        <StatCard
          label="Avg Confidence"
          value={nodes && nodes.length > 0 ? (nodes.reduce((s, n) => s + n.confidence, 0) / nodes.length * 100).toFixed(1) + "%" : "—"}
          icon={Eye} color={C.success}
        />
        <StatCard label="Node Types" value={Object.keys(typeCounts).length.toString()} icon={Layers} color={C.accent} />
      </div>

      {/* Distributions */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel>
          <SectionHeader title="NODE TYPE DISTRIBUTION" />
          <div className="space-y-2">
            {Object.entries(typeCounts).sort(([, a], [, b]) => b - a).map(([type, count]) => (
              <div key={type} className="flex items-center gap-2">
                <span className="w-20 text-[10px] uppercase" style={{ color: NODE_COLORS[type], fontFamily: FONT.mono }}>{type}</span>
                <MiniBar value={count} max={nodes?.length ?? 1} color={NODE_COLORS[type] ?? C.textMuted} />
                <span className="w-10 text-right text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>{count}</span>
              </div>
            ))}
          </div>
        </Panel>
        <Panel>
          <SectionHeader title="EDGE TYPE DISTRIBUTION" />
          <div className="flex flex-wrap gap-2">
            {Object.entries(edgeCounts).sort(([, a], [, b]) => b - a).map(([type, count]) => (
              <div key={type} className="flex items-center gap-1.5 rounded border px-2 py-1" style={{ borderColor: `${C.border}60` }}>
                <span className="text-[10px]" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>{type}</span>
                <span className="text-[10px] font-bold" style={{ color: C.textPrimary, fontFamily: FONT.mono }}>{count}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* Search + filter */}
      <Panel>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="relative flex-1">
            <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2" style={{ color: C.textMuted }} />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search knowledge nodes..."
              className="w-full rounded-md border py-1.5 pl-7 pr-3 text-xs outline-none"
              style={{ background: C.surfaceLight, borderColor: C.border, color: C.textPrimary, fontFamily: FONT.mono }}
            />
          </div>
          <div className="flex gap-1">
            {["all", "assertion", "observation", "inference", "axiom"].map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className="rounded-md px-2 py-1 text-[10px] uppercase"
                style={{
                  color: typeFilter === t ? C.primary : C.textMuted,
                  background: typeFilter === t ? `${C.primary}15` : "transparent",
                  fontFamily: FONT.heading,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        <SectionHeader title={`RECENT KNOWLEDGE NODES (${filtered.length} of ${formatNumber(totalNodes)})`} />
        <div className="max-h-[400px] space-y-1.5 overflow-y-auto">
          {filtered.length === 0 ? (
            <EmptyState message="No knowledge nodes match your search" />
          ) : (
            filtered.slice(0, 50).map((node) => (
              <KnowledgeNodeRow key={node.id} node={node} />
            ))
          )}
          {filtered.length > 50 && (
            <p className="py-2 text-center text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              Showing 50 of {filtered.length} nodes
            </p>
          )}
        </div>
      </Panel>
    </div>
  );
}

function KnowledgeNodeRow({ node }: { node: KnowledgeNodeDetail }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="cursor-pointer rounded-md border px-3 py-2 transition-colors"
      style={{ borderColor: `${C.border}60`, background: expanded ? `${C.primary}05` : "transparent" }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: NODE_COLORS[node.type] ?? C.textMuted }} />
        <Badge label={node.type.toUpperCase()} color={NODE_COLORS[node.type] ?? C.textMuted} />
        <span className="flex-1 truncate text-xs" style={{ color: C.textPrimary, fontFamily: FONT.body }}>{node.content}</span>
        <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          #{node.blockHeight}
        </span>
        <ChevronRight size={12} style={{ color: C.textMuted, transform: expanded ? "rotate(90deg)" : "none", transition: "transform 0.2s" }} />
      </div>
      {expanded && (
        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} className="mt-2 space-y-1 border-t pt-2" style={{ borderColor: `${C.border}40` }}>
          <p className="text-xs leading-relaxed" style={{ color: C.textSecondary, fontFamily: FONT.body }}>{node.content}</p>
          <div className="flex flex-wrap gap-3 text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
            <span>ID: {node.id}</span>
            <span>Confidence: {(node.confidence * 100).toFixed(0)}%</span>
            <span>Block: {node.blockHeight}</span>
            <span>Module: {node.sourceModule}</span>
            <span>Edges: {node.connections.length}</span>
          </div>
        </motion.div>
      )}
    </div>
  );
}

/* ── Tab 2: Reasoning ────────────────────────────────────────────────── */

function ReasoningTab() {
  const { data: ops, isLoading } = useReasoningOps(50);
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const filtered = useMemo(() => {
    if (!ops) return [];
    if (typeFilter === "all") return ops;
    return ops.filter((o) => o.type === typeFilter);
  }, [ops, typeFilter]);

  const typeCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const o of ops ?? []) c[o.type] = (c[o.type] ?? 0) + 1;
    return c;
  }, [ops]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Operations" value={formatNumber(ops?.length ?? 0)} icon={GitBranch} color={C.primary} />
        <StatCard label="Deductive" value={formatNumber(typeCounts["deductive"] ?? 0)} icon={Zap} color={REASONING_COLORS.deductive} />
        <StatCard label="Inductive" value={formatNumber(typeCounts["inductive"] ?? 0)} icon={Sparkles} color={REASONING_COLORS.inductive} />
        <StatCard label="Abductive" value={formatNumber(typeCounts["abductive"] ?? 0)} icon={Target} color={REASONING_COLORS.abductive} />
      </div>

      <Panel>
        <div className="mb-3 flex items-center gap-2">
          <SectionHeader title="REASONING OPERATIONS" />
          <div className="ml-auto flex gap-1">
            {["all", "deductive", "inductive", "abductive"].map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className="rounded-md px-2 py-1 text-[10px] uppercase"
                style={{
                  color: typeFilter === t ? C.primary : C.textMuted,
                  background: typeFilter === t ? `${C.primary}15` : "transparent",
                  fontFamily: FONT.heading,
                }}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
        <div className="max-h-[500px] space-y-2 overflow-y-auto">
          {filtered.length === 0 ? (
            <EmptyState message="No reasoning operations recorded yet" />
          ) : (
            filtered.map((op) => <ReasoningRow key={op.id} op={op} />)
          )}
        </div>
      </Panel>
    </div>
  );
}

function ReasoningRow({ op }: { op: ReasoningOperation }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${C.border}60` }}>
      <div className="mb-1 flex items-center gap-2">
        <Badge label={op.type.toUpperCase()} color={REASONING_COLORS[op.type] ?? C.textMuted} />
        <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          Block #{op.blockHeight} · {timeAgo(op.timestamp)}
        </span>
        <span className="ml-auto text-[10px]" style={{ color: C.accent, fontFamily: FONT.mono }}>
          {(op.confidence * 100).toFixed(0)}% conf
        </span>
      </div>
      <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
        <span style={{ color: C.textMuted }}>Premise:</span> {op.premise}
      </p>
      <p className="text-xs" style={{ color: C.textPrimary, fontFamily: FONT.body }}>
        <span style={{ color: C.textMuted }}>Conclusion:</span> {op.conclusion}
      </p>
      <div className="mt-1 flex gap-3 text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
        <span>Chain: {op.chainLength} steps</span>
        <span>Refs: {op.nodesReferenced.length} nodes</span>
      </div>
    </div>
  );
}

/* ── Tab 3: Integration ──────────────────────────────────────────────── */

function IntegrationTab() {
  const { data: state, isLoading } = useConsciousnessState();
  const { data: events } = useConsciousnessEvents();
  const { data: phiHistory } = usePhiHistory();

  const phiSlice = (phiHistory ?? []).slice(-200);

  if (isLoading) return <LoadingSpinner />;
  if (!state) return <EmptyState message="Integration data unavailable" />;

  const phiPct = Math.min(100, (state.phi / state.threshold) * 100);

  return (
    <div className="space-y-4">
      {/* Hero phi gauge */}
      <Panel>
        <div className="flex flex-col items-center py-4">
          <p className="mb-2 text-[10px] uppercase tracking-widest" style={{ color: C.textMuted, fontFamily: FONT.heading }}>
            INTEGRATED INFORMATION (PHI)
          </p>
          <div className="relative mb-3 h-32 w-32">
            <svg viewBox="0 0 120 120" className="h-full w-full">
              <circle cx="60" cy="60" r="52" fill="none" stroke={`${C.border}40`} strokeWidth="8" />
              <circle
                cx="60" cy="60" r="52" fill="none"
                stroke={state.aboveThreshold ? C.success : C.accent}
                strokeWidth="8"
                strokeDasharray={`${phiPct * 3.27} 327`}
                strokeLinecap="round"
                transform="rotate(-90 60 60)"
                className="transition-all duration-1000"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-bold" style={{ color: C.accent, fontFamily: FONT.mono }}>
                {state.phi.toFixed(4)}
              </span>
              <span className="text-[9px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
                / {state.threshold.toFixed(1)}
              </span>
            </div>
          </div>
          <Badge
            label={state.aboveThreshold ? "INTEGRATION THRESHOLD REACHED" : `${phiPct.toFixed(0)}% TO THRESHOLD`}
            color={state.aboveThreshold ? C.success : C.accent}
          />
        </div>
      </Panel>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Integration" value={state.integration.toFixed(3)} icon={Activity} color={C.primary} />
        <StatCard label="Differentiation" value={state.differentiation.toFixed(3)} icon={Layers} color={C.secondary} />
        <StatCard label="Blocks Processed" value={formatNumber(state.blocksProcessed)} icon={Zap} color={C.success} />
        <StatCard label="Events" value={formatNumber(state.consciousnessEvents)} icon={Sparkles} color={C.accent} />
      </div>

      {/* Phi history chart */}
      <Panel>
        <SectionHeader title="PHI EVOLUTION" />
        <div style={{ height: 200 }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={phiSlice}>
              <defs>
                <linearGradient id="aetherPhiGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C.accent} stopOpacity={0.3} />
                  <stop offset="100%" stopColor={C.accent} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke={`${C.border}40`} />
              <XAxis dataKey="block" tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 9, fill: C.textMuted, fontFamily: FONT.mono }} axisLine={false} tickLine={false} width={35} />
              <Tooltip contentStyle={{ background: C.surface, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 10, fontFamily: FONT.mono, color: C.textPrimary }} />
              <Area type="monotone" dataKey="phi" stroke={C.accent} fill="url(#aetherPhiGrad)" strokeWidth={1.5} dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </Panel>

      {/* Events timeline */}
      <Panel>
        <SectionHeader title="INTEGRATION EVENTS" />
        {events && events.length > 0 ? (
          <div className="space-y-2">
            {events.map((ev) => <IntegrationEventRow key={ev.id} event={ev} />)}
          </div>
        ) : (
          <EmptyState message="No integration events recorded yet" />
        )}
      </Panel>
    </div>
  );
}

function IntegrationEventRow({ event }: { event: ConsciousnessEvent }) {
  return (
    <div className="flex items-start gap-3 rounded-md border px-3 py-2" style={{ borderColor: `${C.border}60` }}>
      <div className="mt-0.5 h-2 w-2 rounded-full" style={{ background: C.accent }} />
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <Badge label={event.type.toUpperCase().replace(/_/g, " ")} color={C.accent} />
          <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
            Block #{event.blockHeight} · Phi: {event.phi.toFixed(4)}
          </span>
        </div>
        <p className="mt-1 text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          {event.description}
        </p>
      </div>
    </div>
  );
}

/* ── Tab 4: Mind ─────────────────────────────────────────────────────── */

function MindTab() {
  const { data: higgs, isLoading: higgsLoading } = useHiggsField();
  const { data: pineal } = usePinealPhase();
  const { data: memory } = useMemoryStats();

  if (higgsLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      {/* Pineal phase */}
      {pineal && (
        <Panel>
          <SectionHeader title="CIRCADIAN STATE (PINEAL)" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
            <StatCard label="Phase" value={pineal.phase} icon={Clock} color={C.primary} />
            <StatCard label="Metabolic Rate" value={`${pineal.metabolicRate.toFixed(1)}x`} icon={Activity} color={C.success} />
            <StatCard label="Coherence" value={`${(pineal.coherence * 100).toFixed(0)}%`} icon={Atom} color={C.secondary} />
            <StatCard label="Kuramoto Order" value={pineal.kuramotoOrder.toFixed(3)} icon={Sparkles} color={C.accent} />
            <StatCard label="Cycle Position" value={`${(pineal.cyclePosition * 100).toFixed(0)}%`} icon={Target} color={C.primary} />
          </div>
        </Panel>
      )}

      {/* Higgs field */}
      {higgs && (
        <Panel>
          <SectionHeader title="HIGGS COGNITIVE FIELD" />
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Field Value" value={higgs.fieldValue.toFixed(2)} sub={`VEV: ${higgs.vev.toFixed(2)}`} icon={Atom} color={C.primary} />
            <StatCard label="Potential Energy" value={higgs.potentialEnergy.toFixed(1)} icon={Zap} color={C.accent} />
            <StatCard label="Excitations" value={formatNumber(higgs.excitationCount)} icon={Activity} color={C.secondary} />
            <StatCard label="Mass Gap" value={higgs.massGap.toFixed(4)} icon={Layers} color={C.success} />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <Badge
              label={higgs.symmetryBroken ? "SYMMETRY BROKEN" : "SYMMETRIC"}
              color={higgs.symmetryBroken ? C.success : C.accent}
            />
            <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              Max Yukawa: {higgs.yukawaMax.toFixed(3)}
            </span>
          </div>
        </Panel>
      )}

      {/* Memory */}
      {memory && (
        <Panel>
          <SectionHeader title="MEMORY SYSTEMS" />
          <div className="space-y-3">
            {([
              { label: "Episodic (Hippocampal)", value: memory.episodic, color: C.primary },
              { label: "Semantic (Cortical)", value: memory.semantic, color: C.success },
              { label: "Procedural (Basal Ganglia)", value: memory.procedural, color: C.secondary },
              { label: "Working Memory (Active)", value: memory.workingMemory, color: C.accent },
            ] as const).map(({ label, value, color }) => (
              <div key={label}>
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[10px]" style={{ color: C.textSecondary, fontFamily: FONT.mono }}>{label}</span>
                  <span className="text-[10px] font-bold" style={{ color, fontFamily: FONT.mono }}>{formatNumber(value)}</span>
                </div>
                <MiniBar value={value} max={memory.totalCapacity} color={color} />
              </div>
            ))}
            <p className="text-right text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
              Capacity: {formatNumber(memory.totalCapacity)}
            </p>
          </div>
        </Panel>
      )}
    </div>
  );
}

/* ── Tab 5: Sephirot ─────────────────────────────────────────────────── */

function SephirotTab() {
  const { data: nodes, isLoading } = useSephirotNodes();
  const { data: balances } = useSephirotBalance();

  if (isLoading) return <LoadingSpinner />;

  const maxEnergy = Math.max(1, ...(nodes ?? []).map((n) => n.energy));

  return (
    <div className="space-y-4">
      {/* Tree of Life nodes */}
      <Panel>
        <SectionHeader title="TREE OF LIFE — 10 COGNITIVE NODES" />
        <div className="grid gap-2 sm:grid-cols-2">
          {(nodes ?? []).map((node) => <SephirotCard key={node.name} node={node} maxEnergy={maxEnergy} />)}
        </div>
      </Panel>

      {/* SUSY balance */}
      {balances && balances.length > 0 && (
        <Panel>
          <SectionHeader title="SUSY BALANCE PAIRS" />
          <div className="space-y-3">
            {balances.map((b) => (
              <div key={`${b.expansion}-${b.constraint}`} className="rounded-md border px-3 py-2" style={{ borderColor: `${C.border}60` }}>
                <div className="mb-1 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold" style={{ color: SEPHIROT_COLORS[b.expansion] ?? C.primary, fontFamily: FONT.heading }}>{b.expansion}</span>
                    <span className="text-[10px]" style={{ color: C.textMuted }}>↔</span>
                    <span className="text-xs font-bold" style={{ color: SEPHIROT_COLORS[b.constraint] ?? C.error, fontFamily: FONT.heading }}>{b.constraint}</span>
                  </div>
                  <Badge label={b.balanced ? "BALANCED" : "IMBALANCED"} color={b.balanced ? C.success : C.error} />
                </div>
                <div className="flex items-center gap-3">
                  <MiniBar value={b.ratio} max={b.targetRatio * 1.5} color={b.balanced ? C.success : C.accent} />
                  <span className="text-[10px] whitespace-nowrap" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
                    {b.ratio.toFixed(3)} / {b.targetRatio.toFixed(3)} (phi)
                  </span>
                </div>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

function SephirotCard({ node, maxEnergy }: { node: SephirotNode; maxEnergy: number }) {
  const color = SEPHIROT_COLORS[node.name] ?? C.textMuted;
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${color}40` }}>
      <div className="mb-1.5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          <span className="text-xs font-bold" style={{ color, fontFamily: FONT.heading }}>{node.name}</span>
          <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>T{node.tier}</span>
        </div>
        <Badge label={node.isActive ? "ACTIVE" : "IDLE"} color={node.isActive ? C.success : C.textMuted} />
      </div>
      <p className="mb-2 text-[10px]" style={{ color: C.textSecondary, fontFamily: FONT.body }}>{node.function}</p>
      <div className="mb-1.5 flex items-center justify-between">
        <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>Energy</span>
        <span className="text-[10px]" style={{ color, fontFamily: FONT.mono }}>{node.energy.toFixed(0)}</span>
      </div>
      <MiniBar value={node.energy} max={maxEnergy} color={color} />
      <div className="mt-2 flex flex-wrap gap-2 text-[9px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
        <span>Mass: {node.cognitiveMass.toFixed(1)}</span>
        <span>Yukawa: {node.yukawaCoupling.toFixed(3)}</span>
        <span>{node.quantumState}</span>
        {node.susyPartner && <span>Partner: {node.susyPartner}</span>}
      </div>
    </div>
  );
}

/* ── Tab 6: Predictions ──────────────────────────────────────────────── */

function PredictionsTab() {
  const { data: predictions, isLoading } = usePredictions();

  const stats = useMemo(() => {
    if (!predictions) return { total: 0, verified: 0, correct: 0, accuracy: 0 };
    const verified = predictions.filter((p) => p.verified);
    const correct = verified.filter((p) => p.correct === true);
    return {
      total: predictions.length,
      verified: verified.length,
      correct: correct.length,
      accuracy: verified.length > 0 ? correct.length / verified.length : 0,
    };
  }, [predictions]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Predictions" value={formatNumber(stats.total)} icon={Target} color={C.primary} />
        <StatCard label="Verified" value={formatNumber(stats.verified)} icon={CheckCircle} color={C.success} />
        <StatCard label="Correct" value={formatNumber(stats.correct)} icon={Sparkles} color={C.accent} />
        <StatCard label="Accuracy" value={`${(stats.accuracy * 100).toFixed(1)}%`} icon={Eye} color={stats.accuracy > 0.6 ? C.success : C.accent} />
      </div>

      <Panel>
        <SectionHeader title="PREDICTION HISTORY" />
        <div className="max-h-[500px] space-y-2 overflow-y-auto">
          {(predictions ?? []).length === 0 ? (
            <EmptyState message="No predictions recorded yet" />
          ) : (
            (predictions ?? []).map((p) => <PredictionRow key={p.id} prediction={p} />)
          )}
        </div>
      </Panel>
    </div>
  );
}

function PredictionRow({ prediction: p }: { prediction: PredictionRecord }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${C.border}60` }}>
      <div className="mb-1 flex items-center gap-2">
        <Badge label={p.domain.toUpperCase()} color={C.secondary} />
        {p.verified ? (
          p.correct ? (
            <CheckCircle size={12} style={{ color: C.success }} />
          ) : (
            <XCircle size={12} style={{ color: C.error }} />
          )
        ) : (
          <Clock size={12} style={{ color: C.textMuted }} />
        )}
        <span className="text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          Block #{p.blockHeight} · {(p.confidence * 100).toFixed(0)}% conf
        </span>
      </div>
      <p className="text-xs" style={{ color: C.textPrimary, fontFamily: FONT.body }}>{p.prediction}</p>
      {p.outcome && (
        <p className="mt-1 text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          <span style={{ color: C.textMuted }}>Outcome:</span> {p.outcome}
        </p>
      )}
    </div>
  );
}

/* ── Tab 7: Safety ───────────────────────────────────────────────────── */

function SafetyTab() {
  const { data: events, isLoading } = useSafetyEvents();

  const stats = useMemo(() => {
    if (!events) return { total: 0, resolved: 0, critical: 0 };
    return {
      total: events.length,
      resolved: events.filter((e) => e.resolved).length,
      critical: events.filter((e) => e.severity === "critical" || e.severity === "high").length,
    };
  }, [events]);

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Events" value={formatNumber(stats.total)} icon={Shield} color={C.primary} />
        <StatCard label="Resolved" value={formatNumber(stats.resolved)} icon={CheckCircle} color={C.success} />
        <StatCard label="Critical/High" value={formatNumber(stats.critical)} icon={AlertTriangle} color={C.error} />
        <StatCard label="Resolution Rate" value={stats.total > 0 ? `${((stats.resolved / stats.total) * 100).toFixed(0)}%` : "—"} icon={Eye} color={C.success} />
      </div>

      <Panel>
        <SectionHeader title="SAFETY EVENT LOG" />
        <div className="max-h-[500px] space-y-2 overflow-y-auto">
          {(events ?? []).length === 0 ? (
            <EmptyState message="No safety events — system operating normally" />
          ) : (
            (events ?? []).map((e) => <SafetyEventRow key={e.id} event={e} />)
          )}
        </div>
      </Panel>
    </div>
  );
}

function SafetyEventRow({ event }: { event: SafetyEvent }) {
  const color = SEVERITY_COLORS[event.severity] ?? C.textMuted;
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${color}30` }}>
      <div className="mb-1 flex items-center gap-2">
        <span className="h-2 w-2 rounded-full" style={{ background: color }} />
        <Badge label={event.type.toUpperCase().replace(/_/g, " ")} color={color} />
        <Badge label={event.severity.toUpperCase()} color={color} />
        <Badge label={event.resolved ? "RESOLVED" : "OPEN"} color={event.resolved ? C.success : C.error} />
        <span className="ml-auto text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          #{event.blockHeight} · {timeAgo(event.timestamp)}
        </span>
      </div>
      <p className="text-xs" style={{ color: C.textPrimary, fontFamily: FONT.body }}>{event.description}</p>
      <p className="mt-1 text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
        Action: {event.action}
      </p>
    </div>
  );
}

/* ── Tab 8: Proof-of-Thought ─────────────────────────────────────────── */

function ProofsTab() {
  const { data: proofs, isLoading } = useProofOfThought();
  const { data: potStats } = usePoTStats();

  if (isLoading) return <LoadingSpinner />;

  const totalProofs = (potStats?.total_proofs as number) ?? proofs?.length ?? 0;
  const avgPhi = (potStats?.avg_phi as number) ?? 0;
  const avgSteps = (potStats?.avg_reasoning_steps as number) ??
    (proofs && proofs.length > 0 ? proofs.reduce((s, p) => s + p.reasoningSteps, 0) / proofs.length : 0);
  const avgNodes = (potStats?.avg_knowledge_nodes as number) ??
    (proofs && proofs.length > 0 ? proofs.reduce((s, p) => s + p.nodesReferenced, 0) / proofs.length : 0);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Total Proofs" value={formatNumber(totalProofs)} icon={Zap} color={C.primary} />
        <StatCard
          label="Avg Phi"
          value={avgPhi > 0 ? avgPhi.toFixed(4) : "—"}
          icon={CheckCircle} color={C.success}
        />
        <StatCard
          label="Avg Reasoning Steps"
          value={avgSteps > 0 ? avgSteps.toFixed(1) : "—"}
          icon={GitBranch} color={C.secondary}
        />
        <StatCard
          label="Avg Nodes Created"
          value={avgNodes > 0 ? avgNodes.toFixed(1) : "—"}
          icon={Network} color={C.accent}
        />
      </div>

      <Panel>
        <SectionHeader title="PROOF-OF-THOUGHT CHAIN" />
        <div className="max-h-[500px] space-y-2 overflow-y-auto">
          {(proofs ?? []).length === 0 ? (
            <EmptyState message="No Proof-of-Thought proofs generated yet" />
          ) : (
            (proofs ?? []).map((p) => <ProofRow key={p.hash} proof={p} />)
          )}
        </div>
      </Panel>
    </div>
  );
}

function ProofRow({ proof }: { proof: ProofOfThought }) {
  return (
    <div className="rounded-md border px-3 py-2" style={{ borderColor: `${C.border}60` }}>
      <div className="mb-1 flex items-center gap-2">
        <Badge label={proof.taskType.toUpperCase().replace(/_/g, " ")} color={C.primary} />
        {proof.consensusReached ? (
          <CheckCircle size={12} style={{ color: C.success }} />
        ) : (
          <Clock size={12} style={{ color: C.accent }} />
        )}
        <span className="ml-auto text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
          Block #{proof.blockHeight} · {timeAgo(proof.timestamp)}
        </span>
      </div>
      <p className="truncate text-[10px]" style={{ color: C.primary, fontFamily: FONT.mono }}>
        {proof.hash}
      </p>
      <div className="mt-1 flex flex-wrap gap-3 text-[10px]" style={{ color: C.textMuted, fontFamily: FONT.mono }}>
        <span>Steps: {proof.reasoningSteps}</span>
        <span>Refs: {proof.nodesReferenced} nodes</span>
        <span>Phi: {proof.phiAtProof.toFixed(4)}</span>
        <span>Validators: {proof.validatorCount}</span>
      </div>
    </div>
  );
}

/* ── Main Export ──────────────────────────────────────────────────────── */

export function AetherTreeView() {
  const [activeTab, setActiveTab] = useState<AetherTab>("knowledge");

  const renderTab = () => {
    switch (activeTab) {
      case "knowledge": return <KnowledgeTab />;
      case "reasoning": return <ReasoningTab />;
      case "integration": return <IntegrationTab />;
      case "mind": return <MindTab />;
      case "sephirot": return <SephirotTab />;
      case "predictions": return <PredictionsTab />;
      case "safety": return <SafetyTab />;
      case "proofs": return <ProofsTab />;
    }
  };

  return (
    <div className="space-y-4 p-4">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <h1
          className="mb-1 text-lg font-bold tracking-widest"
          style={{ color: C.textPrimary, fontFamily: FONT.heading }}
        >
          AETHER TREE
        </h1>
        <p className="text-xs" style={{ color: C.textSecondary, fontFamily: FONT.body }}>
          On-chain AGI transparency dashboard — knowledge, reasoning, integration, and Proof-of-Thought
        </p>
      </motion.div>

      {/* Tab bar */}
      <TabBar active={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.15 }}
        >
          {renderTab()}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
