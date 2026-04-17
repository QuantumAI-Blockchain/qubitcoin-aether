"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "@/lib/api";
import type { SephirotNode, SephirotCognitiveNode } from "@/lib/api";
import type { SephirotStatusNode, SUSYPair, SephirotStatus } from "@/lib/api";

/* ---- Per-node colour gradients (Tailwind classes) ---- */
const NODE_COLORS: Record<number, string> = {
  0: "from-purple-500/20 to-purple-900/10 border-purple-500/30",
  1: "from-blue-500/20 to-blue-900/10 border-blue-500/30",
  2: "from-pink-500/20 to-pink-900/10 border-pink-500/30",
  3: "from-green-500/20 to-green-900/10 border-green-500/30",
  4: "from-red-500/20 to-red-900/10 border-red-500/30",
  5: "from-yellow-500/20 to-yellow-900/10 border-yellow-500/30",
  6: "from-emerald-500/20 to-emerald-900/10 border-emerald-500/30",
  7: "from-orange-500/20 to-orange-900/10 border-orange-500/30",
  8: "from-indigo-500/20 to-indigo-900/10 border-indigo-500/30",
  9: "from-teal-500/20 to-teal-900/10 border-teal-500/30",
};

const NODE_DOT_COLORS: Record<number, string> = {
  0: "bg-purple-400",
  1: "bg-blue-400",
  2: "bg-pink-400",
  3: "bg-green-400",
  4: "bg-red-400",
  5: "bg-yellow-400",
  6: "bg-emerald-400",
  7: "bg-orange-400",
  8: "bg-indigo-400",
  9: "bg-teal-400",
};

/* ---- Metadata for the 10 Sephirot ---- */
const SEPHIROT_META: Record<
  string,
  { title: string; brain: string; fn: string; qubits: number }
> = {
  Keter:    { title: "Crown",        brain: "Prefrontal cortex",    fn: "Meta-learning, goal formation",         qubits: 8 },
  Chochmah: { title: "Wisdom",       brain: "Right hemisphere",     fn: "Intuition, pattern discovery",          qubits: 6 },
  Binah:    { title: "Understanding", brain: "Left hemisphere",     fn: "Logic, causal inference",               qubits: 4 },
  Chesed:   { title: "Kindness",     brain: "Default mode network", fn: "Exploration, divergent thinking",        qubits: 10 },
  Gevurah:  { title: "Severity",     brain: "Amygdala, inhibitory", fn: "Constraint, safety validation",         qubits: 3 },
  Tiferet:  { title: "Beauty",       brain: "Thalamocortical loops", fn: "Integration, conflict resolution",     qubits: 12 },
  Netzach:  { title: "Victory",      brain: "Basal ganglia",        fn: "Reinforcement learning, habits",        qubits: 5 },
  Hod:      { title: "Splendor",     brain: "Broca/Wernicke",       fn: "Language, semantic encoding",           qubits: 7 },
  Yesod:    { title: "Foundation",   brain: "Hippocampus",          fn: "Memory, multimodal fusion",             qubits: 16 },
  Malkuth:  { title: "Kingdom",      brain: "Motor cortex",         fn: "Action, world interaction",             qubits: 4 },
};

const SEPHIROT_ORDER = [
  "Keter", "Chochmah", "Binah", "Chesed", "Gevurah",
  "Tiferet", "Netzach", "Hod", "Yesod", "Malkuth",
];

/* ---- Main component ---- */

export function SephirotExplorer() {
  const [expandedNode, setExpandedNode] = useState<string | null>(null);

  const { data: nodesData } = useQuery({
    queryKey: ["sephirotNodes"],
    queryFn: api.getSephirotNodes,
    refetchInterval: 15_000,
  });

  const { data: statusData } = useQuery({
    queryKey: ["sephirotStatus"],
    queryFn: () => api.getSephirotStatus(),
    refetchInterval: 15_000,
  });

  const { data: cognitiveData } = useQuery({
    queryKey: ["sephirotCognitiveNodes"],
    queryFn: () => api.getSephirotCognitiveNodes().catch(() => ({ nodes: [] })),
    refetchInterval: 15_000,
    retry: false,
  });

  const nodes = nodesData?.nodes ?? [];
  const cognitiveNodes = cognitiveData?.nodes ?? [];
  const status = statusData as SephirotStatus | undefined;

  // Build cognitive node lookup by role name
  const cognitiveByRole: Record<string, SephirotCognitiveNode> = {};
  for (const cn of cognitiveNodes) {
    cognitiveByRole[cn.role] = cn;
  }
  const susyPairs = status?.susy_pairs ?? [];
  const coherence = status?.coherence ?? 0;
  const totalViolations = status?.total_violations ?? 0;

  // Build a quick lookup from staking nodes by name
  const nodeByName: Record<string, SephirotNode> = {};
  for (const n of nodes) {
    nodeByName[n.name] = n;
  }

  // Count active nodes from status
  const activeCount = SEPHIROT_ORDER.filter((name) => {
    const s = status?.[name.toLowerCase()] as SephirotStatusNode | undefined;
    return s?.active;
  }).length;

  const totalStaked = nodes.reduce(
    (sum, n) => sum + parseFloat(n.total_staked || "0"),
    0,
  );

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      {/* Header */}
      <div className="mb-1">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Tree of Life — Cognitive Architecture
        </h3>
        <p className="mt-1 text-xs text-text-secondary">
          10 Sephirot nodes forming the AI neural network
        </p>
      </div>

      {/* Summary stats */}
      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MiniStat label="Active Nodes" value={`${activeCount}/10`} />
        <MiniStat
          label="Coherence"
          value={typeof coherence === "number" ? coherence.toFixed(3) : "---"}
        />
        <MiniStat
          label="Total Staked"
          value={totalStaked > 0 ? `${totalStaked.toLocaleString()} QBC` : "---"}
        />
        <MiniStat
          label="SUSY Violations"
          value={totalViolations.toString()}
          warn={totalViolations > 0}
        />
      </div>

      {/* Node grid */}
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {SEPHIROT_ORDER.map((name, idx) => {
          const meta = SEPHIROT_META[name];
          const staking = nodeByName[name];
          const nodeStatus = status?.[name.toLowerCase()] as
            | SephirotStatusNode
            | undefined;
          const isExpanded = expandedNode === name;

          return (
            <motion.button
              key={name}
              onClick={() => setExpandedNode(isExpanded ? null : name)}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: idx * 0.04 }}
              className={`group relative cursor-pointer rounded-xl border bg-gradient-to-b p-4 text-left transition-all hover:scale-[1.02] ${
                NODE_COLORS[idx] ?? ""
              } ${isExpanded ? "ring-1 ring-quantum-green/40" : ""}`}
            >
              {/* Status dot */}
              <div className="mb-2 flex items-center justify-between">
                <span
                  className={`inline-block h-2 w-2 rounded-full ${
                    nodeStatus?.active
                      ? "bg-quantum-green shadow-[0_0_6px_rgba(0,255,136,0.5)]"
                      : NODE_DOT_COLORS[idx] + " opacity-40"
                  }`}
                />
                <span className="font-[family-name:var(--font-code)] text-[10px] text-text-secondary">
                  {meta.qubits}q
                </span>
              </div>

              {/* Name + title */}
              <p className="text-sm font-semibold text-text-primary">{name}</p>
              <p className="text-[10px] text-text-secondary">{meta.title}</p>

              {/* Brain analog pill */}
              <span className="mt-2 inline-block rounded-full bg-bg-deep/60 px-2 py-0.5 text-[9px] text-text-secondary">
                {meta.brain}
              </span>

              {/* Energy bar */}
              {nodeStatus?.energy != null && (
                <div className="mt-2">
                  <div className="h-1 w-full overflow-hidden rounded-full bg-bg-deep">
                    <div
                      className="h-full rounded-full bg-quantum-green/60"
                      style={{
                        width: `${Math.min(nodeStatus.energy * 100, 100)}%`,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Staking mini-stats */}
              {staking && (
                <div className="mt-2 flex items-center justify-between text-[10px] text-text-secondary">
                  <span>{staking.current_stakers} stakers</span>
                  <span>{staking.apy_estimate}% APY</span>
                </div>
              )}
            </motion.button>
          );
        })}
      </div>

      {/* Expanded node detail */}
      <AnimatePresence>
        {expandedNode && (
          <motion.div
            key={expandedNode}
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <NodeDetail
              name={expandedNode}
              meta={SEPHIROT_META[expandedNode]}
              staking={nodeByName[expandedNode]}
              status={
                status?.[expandedNode.toLowerCase()] as
                  | SephirotStatusNode
                  | undefined
              }
              cognitive={cognitiveByRole[expandedNode]}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* SUSY Pairs */}
      {susyPairs.length > 0 && (
        <div className="mt-6">
          <h4 className="mb-3 text-sm font-semibold text-text-secondary">
            SUSY Pairs — Golden Ratio Balance
          </h4>
          <div className="space-y-2">
            {susyPairs.map((pair) => (
              <SUSYPairRow key={`${pair.expansion}-${pair.constraint}`} pair={pair} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ---- Sub-components ---- */

function MiniStat({
  label,
  value,
  warn = false,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div className="rounded-lg bg-bg-deep/50 px-3 py-2">
      <p className="text-[10px] text-text-secondary">{label}</p>
      <p
        className={`mt-0.5 font-[family-name:var(--font-code)] text-sm font-semibold ${
          warn ? "text-red-400" : "text-text-primary"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function NodeDetail({
  name,
  meta,
  staking,
  status,
  cognitive,
}: {
  name: string;
  meta: { title: string; brain: string; fn: string; qubits: number };
  staking?: SephirotNode;
  status?: SephirotStatusNode;
  cognitive?: SephirotCognitiveNode;
}) {
  return (
    <div className="mt-4 rounded-xl border border-border-subtle/50 bg-bg-deep/30 p-5">
      <div className="flex items-start justify-between">
        <div>
          <h4 className="text-base font-semibold text-text-primary">
            {name}{" "}
            <span className="text-sm font-normal text-text-secondary">
              — {meta.title}
            </span>
          </h4>
          <p className="mt-1 text-sm text-text-secondary">{meta.fn}</p>
        </div>
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
            status?.active
              ? "bg-quantum-green/15 text-quantum-green"
              : "bg-bg-panel-light text-text-secondary"
          }`}
        >
          {status?.active ? "Active" : "Inactive"}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <DetailStat label="Qubits" value={meta.qubits.toString()} />
        <DetailStat label="Brain Analog" value={meta.brain} />
        <DetailStat
          label="Messages"
          value={status?.messages_processed?.toLocaleString() ?? "---"}
        />
        <DetailStat
          label="Reasoning Ops"
          value={status?.reasoning_ops?.toLocaleString() ?? "---"}
        />
      </div>

      {cognitive && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <DetailStat
            label="Cognitive Mass"
            value={cognitive.cognitive_mass.toFixed(2)}
          />
          <DetailStat
            label="Yukawa Coupling"
            value={cognitive.yukawa_coupling.toFixed(4)}
          />
          <DetailStat
            label="Energy"
            value={cognitive.energy.toFixed(3)}
          />
          <DetailStat
            label="QBC Stake"
            value={cognitive.qbc_stake.toLocaleString()}
          />
        </div>
      )}

      {staking && (
        <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <DetailStat
            label="Total Staked"
            value={`${parseFloat(staking.total_staked || "0").toLocaleString()} QBC`}
          />
          <DetailStat label="Stakers" value={staking.current_stakers.toString()} />
          <DetailStat label="Min Stake" value={`${staking.min_stake} QBC`} />
          <DetailStat label="APY" value={`${staking.apy_estimate}%`} />
        </div>
      )}
    </div>
  );
}

function DetailStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[10px] text-text-secondary">{label}</p>
      <p className="font-[family-name:var(--font-code)] text-xs text-text-primary">
        {value}
      </p>
    </div>
  );
}

function SUSYPairRow({ pair }: { pair: SUSYPair }) {
  const PHI = 1.618;
  const ratio = pair.ratio ?? 0;
  const target = pair.target_ratio ?? PHI;

  // How far from target: within 20% tolerance = green, 40% = amber, beyond = red
  const deviation = target > 0 ? Math.abs(ratio - target) / target : 1;
  const color =
    deviation < 0.2
      ? "bg-quantum-green"
      : deviation < 0.4
        ? "bg-golden-amber"
        : "bg-red-400";
  const textColor =
    deviation < 0.2
      ? "text-quantum-green"
      : deviation < 0.4
        ? "text-golden-amber"
        : "text-red-400";

  // Bar width: map ratio in [0, 2*target] to [0%, 100%]
  const barPct = Math.min((ratio / (target * 2)) * 100, 100);
  // Target marker position
  const targetPct = 50; // target is always at center since we map [0, 2*target]

  return (
    <div className="flex items-center gap-3 rounded-lg bg-bg-deep/40 px-3 py-2">
      <span className="w-20 shrink-0 text-right text-xs font-medium text-text-primary">
        {pair.expansion}
      </span>

      {/* Ratio bar */}
      <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-bg-deep">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${barPct}%` }}
        />
        {/* Target marker */}
        <div
          className="absolute top-0 h-full w-px bg-text-secondary/50"
          style={{ left: `${targetPct}%` }}
        />
      </div>

      <span className="w-20 shrink-0 text-xs font-medium text-text-primary">
        {pair.constraint}
      </span>

      <span className={`w-14 shrink-0 text-right font-[family-name:var(--font-code)] text-[10px] ${textColor}`}>
        {ratio.toFixed(3)}
      </span>
    </div>
  );
}
