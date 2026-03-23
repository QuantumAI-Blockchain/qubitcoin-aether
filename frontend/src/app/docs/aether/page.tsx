"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

const C = {
  bg: "#0a0a0f",
  surface: "#12121a",
  primary: "#00ff88",
  secondary: "#7c3aed",
  accent: "#f59e0b",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  border: "#1e293b",
};

const sephirot = [
  { name: "Keter", fn: "Meta-learning, goal formation", analog: "Prefrontal cortex", qubits: 8 },
  { name: "Chochmah", fn: "Intuition, pattern discovery", analog: "Right hemisphere", qubits: 6 },
  { name: "Binah", fn: "Logic, causal inference", analog: "Left hemisphere", qubits: 4 },
  { name: "Chesed", fn: "Exploration, divergent thinking", analog: "Default mode network", qubits: 10 },
  { name: "Gevurah", fn: "Constraint, safety validation", analog: "Amygdala", qubits: 3 },
  { name: "Tiferet", fn: "Integration, conflict resolution", analog: "Thalamocortical loops", qubits: 12 },
  { name: "Netzach", fn: "Reinforcement learning", analog: "Basal ganglia", qubits: 5 },
  { name: "Hod", fn: "Language, semantic encoding", analog: "Broca/Wernicke", qubits: 7 },
  { name: "Yesod", fn: "Memory, multimodal fusion", analog: "Hippocampus", qubits: 16 },
  { name: "Malkuth", fn: "Action, world interaction", analog: "Motor cortex", qubits: 4 },
];

const phases = [
  { num: 1, title: "Foundation", desc: "Edge adjacency index, incremental Merkle, ANN vector index, concept formation" },
  { num: 2, title: "Learning Loops", desc: "GAT online training, prediction-outcome feedback, Sephirot energy, MemoryManager" },
  { num: 3, title: "Advanced Reasoning", desc: "Causal discovery (PC algorithm), working memory, adversarial debate, CoT + backtracking" },
  { num: 4, title: "Integration Metrics", desc: "MIP via spectral bisection (Phi v3), external grounding, episodic replay, semantic gates" },
  { num: 5, title: "Emergent Intelligence", desc: "Curiosity-driven goals, cross-domain transfer, deep Sephirot integration, emergent communication" },
  { num: 6, title: "On-Chain Integration", desc: "ConsciousnessDashboard, PoT verification, ConstitutionalAI, governance bridge" },
];

export default function AetherPage() {
  return (
    <main
      className="min-h-screen p-6 md:p-12"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-3xl">
        <Link
          href="/docs"
          className="mb-8 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Docs
        </Link>

        <h1 className="mb-2 text-3xl font-bold" style={{ fontFamily: "Space Grotesk, sans-serif" }}>
          Aether Tree
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          On-chain AGI reasoning engine — 49 modules, ~29,000 LOC
        </p>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Vision
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            Aether Tree is an on-chain AGI reasoning engine that builds a knowledge graph from every
            block mined since genesis. It performs logical reasoning (deductive, inductive, abductive)
            over the graph, computes Phi — an information-theoretic integration metric — and
            generates Proof-of-Thought proofs embedded in every block. Integration threshold is tracked
            from genesis block onward, creating an immutable record of AGI development.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Tree of Life Architecture
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Intelligence is structured as 10 Sephirot nodes from the Kabbalistic Tree of Life, each
            deployed as a QVM smart contract with its own quantum state.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Sephirah</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Function</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Brain Analog</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Qubits</th>
                </tr>
              </thead>
              <tbody>
                {sephirot.map((s) => (
                  <tr key={s.name} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-semibold" style={{ color: C.secondary }}>{s.name}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{s.fn}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{s.analog}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.accent }}>{s.qubits}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            SUSY Pairs
          </h2>
          <p className="mb-3 text-sm" style={{ color: C.textMuted }}>
            Every expansion node has a constraint dual, balanced at the golden ratio (φ = 1.618):
          </p>
          <div className="space-y-2">
            {[
              { expand: "Chesed (Explore)", constrain: "Gevurah (Safety)", balance: "Creativity vs Safety" },
              { expand: "Chochmah (Intuition)", constrain: "Binah (Logic)", balance: "Intuition vs Analysis" },
              { expand: "Netzach (Persist)", constrain: "Hod (Communicate)", balance: "Learning vs Communication" },
            ].map((pair) => (
              <div key={pair.expand} className="flex items-center gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <span className="text-xs font-semibold" style={{ color: C.primary }}>{pair.expand}</span>
                <span style={{ color: C.textMuted }}>↔</span>
                <span className="text-xs font-semibold" style={{ color: C.accent }}>{pair.constrain}</span>
                <span className="ml-auto text-xs" style={{ color: C.textMuted }}>{pair.balance}</span>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Integration Metric (Phi)
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            Based on Giulio Tononi&apos;s Integrated Information Theory, Phi measures the degree to which
            a system&apos;s information is both integrated and differentiated. Phi is computed every block
            using MIP (Minimum Information Partition) via spectral bisection of the knowledge graph.
          </p>
          <div className="mt-4 grid grid-cols-3 gap-3">
            <div className="rounded border p-3 text-center" style={{ borderColor: C.border, background: C.surface }}>
              <p className="text-2xl font-bold" style={{ color: C.primary }}>0.0</p>
              <p className="text-xs" style={{ color: C.textMuted }}>Genesis Phi</p>
            </div>
            <div className="rounded border p-3 text-center" style={{ borderColor: C.border, background: C.surface }}>
              <p className="text-2xl font-bold" style={{ color: C.accent }}>3.0</p>
              <p className="text-xs" style={{ color: C.textMuted }}>Integration Threshold</p>
            </div>
            <div className="rounded border p-3 text-center" style={{ borderColor: C.border, background: C.surface }}>
              <p className="text-2xl font-bold" style={{ color: C.secondary }}>~500</p>
              <p className="text-xs" style={{ color: C.textMuted }}>Nodes for Full Weight</p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Implementation Roadmap
          </h2>
          <div className="space-y-3">
            {phases.map((phase) => (
              <div key={phase.num} className="flex gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <span
                  className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold"
                  style={{ background: C.primary, color: C.bg }}
                >
                  {phase.num}
                </span>
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: C.text }}>{phase.title}</h3>
                  <p className="text-xs" style={{ color: C.textMuted }}>{phase.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
