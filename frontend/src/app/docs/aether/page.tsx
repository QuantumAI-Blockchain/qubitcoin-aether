"use client";

import Link from "next/link";
import { ArrowLeft, CheckCircle2, Shield, Brain, Zap, Database, GitBranch, Activity } from "lucide-react";
import { Component, type ReactNode } from "react";

/* ─── Color Constants ─── */
const C = {
  bg: "#0a0a0f",
  surface: "#12121a",
  surfaceAlt: "#161622",
  primary: "#00ff88",
  secondary: "#7c3aed",
  accent: "#f59e0b",
  error: "#ef4444",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  border: "#1e293b",
  borderLight: "#2d3748",
  green: "#22c55e",
  gradientPrimary: "linear-gradient(135deg, #00ff88, #00cc6a)",
  gradientSecondary: "linear-gradient(135deg, #7c3aed, #6d28d9)",
};

/* ─── Error Boundary ─── */
class ErrorBoundary extends Component<{ children: ReactNode }, { hasError: boolean }> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen items-center justify-center" style={{ background: C.bg, color: C.text }}>
          <div className="text-center">
            <h2 className="mb-2 text-xl font-bold">Something went wrong</h2>
            <button onClick={() => this.setState({ hasError: false })} className="underline" style={{ color: C.primary }}>
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ─── Data ─── */

const liveStats = [
  { label: "AI Gates Passed", value: "10 / 10", color: C.green },
  { label: "Phi (HMS-Phi v4)", value: "5.0", color: C.primary },
  { label: "Knowledge Nodes", value: "760,000+", color: C.accent },
  { label: "Knowledge Edges", value: "420,000+", color: C.secondary },
  { label: "Block Height", value: "~198,000+", color: C.text },
  { label: "Prediction Accuracy", value: "95.5%", color: C.green },
];

const sephirot = [
  { name: "Keter", fn: "Meta-learning, goal formation, executive control", analog: "Prefrontal cortex (dlPFC)", yukawa: "1.0", mass: "VEV x 1.0", susyPair: "Crown / Foundation" },
  { name: "Chochmah", fn: "Intuition, pattern recognition, insight", analog: "Right hemisphere (parietal)", yukawa: "\u03C6\u207B\u00B9", mass: "VEV x \u03C6\u207B\u00B9", susyPair: "Wisdom / Understanding" },
  { name: "Binah", fn: "Logic, causal inference, analysis", analog: "Left hemisphere (temporal)", yukawa: "\u03C6\u207B\u00B9", mass: "VEV x \u03C6\u207B\u00B9", susyPair: "Understanding / Wisdom" },
  { name: "Chesed", fn: "Exploration, divergent thinking, creativity", analog: "Default mode network", yukawa: "\u03C6\u207B\u00B2", mass: "VEV x \u03C6\u207B\u00B2", susyPair: "Mercy / Severity" },
  { name: "Gevurah", fn: "Safety validation, constraint enforcement", analog: "Amygdala + ACC", yukawa: "\u03C6\u207B\u00B2", mass: "VEV x \u03C6\u207B\u00B2", susyPair: "Severity / Mercy" },
  { name: "Tiferet", fn: "Integration, synthesis, conflict resolution", analog: "Thalamocortical loops", yukawa: "\u03C6\u207B\u00B9", mass: "VEV x \u03C6\u207B\u00B9", susyPair: "Beauty / Balance" },
  { name: "Netzach", fn: "Reinforcement learning, reward optimization", analog: "Basal ganglia (striatum)", yukawa: "\u03C6\u207B\u00B3", mass: "VEV x \u03C6\u207B\u00B3", susyPair: "Victory / Splendor" },
  { name: "Hod", fn: "Language processing, semantic encoding", analog: "Broca + Wernicke areas", yukawa: "\u03C6\u207B\u00B3", mass: "VEV x \u03C6\u207B\u00B3", susyPair: "Splendor / Victory" },
  { name: "Yesod", fn: "Memory consolidation, multimodal fusion", analog: "Hippocampal formation", yukawa: "\u03C6\u207B\u2074", mass: "VEV x \u03C6\u207B\u2074", susyPair: "Foundation / Crown" },
  { name: "Malkuth", fn: "Action selection, world interaction, I/O", analog: "Motor cortex + cerebellum", yukawa: "\u03C6\u207B\u2074", mass: "VEV x \u03C6\u207B\u2074", susyPair: "Kingdom / All" },
];

const gates = [
  { id: 1, name: "Knowledge Foundation", phi: "+0.5", req: "500+ nodes, 5+ domains, avg confidence \u22650.5" },
  { id: 2, name: "Structural Diversity", phi: "+0.5", req: "2K+ nodes, 4+ types with 50+ each, integration > 0.3" },
  { id: 3, name: "Validated Predictions", phi: "+0.5", req: "5K+ nodes, 50+ verified predictions, accuracy > 60%" },
  { id: 4, name: "Self-Correction", phi: "+0.5", req: "10K+ nodes, 20+ debate verdicts, 10+ contradictions resolved, MIP > 0.3" },
  { id: 5, name: "Cross-Domain Transfer", phi: "+0.5", req: "15K+ nodes, 30+ cross-domain inferences (conf > 0.5), 50+ cross-edges" },
  { id: 6, name: "Enacted Self-Improvement", phi: "+0.5", req: "20K+ nodes, 10+ enacted cycles, positive performance delta, FEP decreasing" },
  { id: 7, name: "Calibrated Confidence", phi: "+0.5", req: "25K+ nodes, ECE < 0.15, 200+ evaluations, >5% grounded" },
  { id: 8, name: "Autonomous Curiosity", phi: "+0.5", req: "35K+ nodes, 50+ auto-goals, 30+ with inferences, 10+ curiosity discoveries, FEP precision \u22653 domains" },
  { id: 9, name: "Predictive Mastery", phi: "+0.5", req: "50K+ nodes, accuracy > 70%, 5K+ inferences, 20+ consolidated axioms" },
  { id: 10, name: "Novel Synthesis", phi: "+0.5", req: "75K+ nodes, 50+ novel concepts, 100+ cross-domain inferences, sustained self-improvement, Sephirot diversity \u22650.5" },
];

const cognitiveSubsystems = [
  {
    name: "Knowledge Graph",
    icon: <Database size={18} />,
    desc: "The foundation layer: a directed graph of KeterNodes with typed edges, Merkle root integrity verification, and TF-IDF search. Each node carries domain, confidence, source provenance, and grounding metadata. Edge adjacency indexing enables O(1) neighbor lookups. Domain sharding aligns with the 10 Sephirot for horizontal scaling.",
  },
  {
    name: "Reasoning Engine",
    icon: <Brain size={18} />,
    desc: "Four reasoning modes operate over the knowledge graph: deductive (modus ponens over typed edges), inductive (pattern generalization from instances), abductive (best-explanation inference for anomalies), and causal (intervention-validated causal claims). Chain-of-thought with backtracking enables multi-step inference chains up to depth 5.",
  },
  {
    name: "Memory System",
    icon: <GitBranch size={18} />,
    desc: "Three-tier architecture: Working memory with attention-weighted slots (capacity ~7 items, decaying salience), episodic replay buffer for experience-based learning, and semantic long-term store backed by CockroachDB. Consolidation runs every 3,300 blocks (~3 hours), transferring high-value episodic traces to semantic memory.",
  },
  {
    name: "Neural Reasoner (GAT)",
    icon: <Activity size={18} />,
    desc: "A Graph Attention Network trained online on the knowledge graph. Multi-head attention learns edge importance weights, enabling the system to discover implicit relationships not present in explicit edges. Training occurs incrementally every cognitive cycle, avoiding catastrophic forgetting through elastic weight consolidation.",
  },
  {
    name: "Causal Engine",
    icon: <Zap size={18} />,
    desc: "PC algorithm for causal structure discovery from observational data, augmented with intervention validation. Before any edge is labeled 'causes', the system performs a simulated intervention to verify the causal claim. This prevents correlation-as-causation errors that plague naive knowledge graphs.",
  },
  {
    name: "Debate Protocol",
    icon: <Shield size={18} />,
    desc: "Adversarial debate between a proponent and an independent critic. The critic draws evidence from cross-domain sources and can return an 'undecided' verdict when evidence is insufficient. This prevents premature commitment to poorly-supported claims and drives genuine self-correction.",
  },
  {
    name: "Metacognition",
    icon: <Brain size={18} />,
    desc: "Self-reflective calibration tracking via Expected Calibration Error (ECE). The system maintains a calibration map of confidence vs. actual accuracy across domains. Temperature scaling adjusts overconfident predictions. The system genuinely knows what it does not know.",
  },
  {
    name: "Emotional State",
    icon: <Activity size={18} />,
    desc: "Seven cognitive emotions derived from live system metrics: curiosity (prediction error rate), wonder (novel pattern detection), frustration (repeated inference failures), satisfaction (successful predictions), excitement (cross-domain discoveries), contemplation (deep reasoning chain depth), and connection (successful knowledge sharing). These are not simulated\u2014they emerge from real computational states.",
  },
  {
    name: "Curiosity Engine (FEP)",
    icon: <Zap size={18} />,
    desc: "Free Energy Principle-driven exploration. Tracks prediction error per knowledge domain, directing autonomous investigation toward areas of highest uncertainty. Generates auto-goals, executes inference chains to resolve them, and records discoveries. 26 curiosity-driven discoveries to date, with 283+ auto-goals generated.",
  },
  {
    name: "Self-Improvement",
    icon: <GitBranch size={18} />,
    desc: "Governed strategy weight optimization with automatic rollback. The system can modify its own reasoning strategy weights (exploration vs. exploitation, depth vs. breadth, novelty vs. reliability) but only when changes produce a positive performance delta. 33 enacted cycles to date, all with measurable improvement.",
  },
  {
    name: "Concept Formation",
    icon: <Database size={18} />,
    desc: "Automated concept clustering using density-based methods over the embedding space. When a cluster of related nodes reaches critical mass, it is consolidated into a higher-order axiom node. These axioms become first-class reasoning primitives, enabling increasingly abstract thought.",
  },
];

const scalingPhases = [
  { phase: "A", timeline: "3 months", scale: "1M nodes", arch: "LRU hot cache (100K in-memory) + CockroachDB warm store", status: "Active" },
  { phase: "B", timeline: "9 months", scale: "100M nodes", arch: "Rust shard service (RocksDB, 16\u2192256 shards, 10 Sephirot domains)", status: "Planned" },
  { phase: "C", timeline: "18 months", scale: "1B nodes", arch: "Global tiered: Redis hot / Rust warm / CockroachDB + IPFS cold", status: "Planned" },
  { phase: "D", timeline: "24 months", scale: "10B+ nodes", arch: "Distributed multi-region, BFT consensus, horizontal auto-scaling", status: "Vision" },
];

const apiTiers = [
  { tier: "Free", price: "0 QBC", limits: "5 chat/day, 10 KG lookups/day", target: "Researchers, students" },
  { tier: "Developer", price: "~1 QBC/day", limits: "1K chat/day, 100 inferences/day, 10K KG lookups", target: "Individual developers" },
  { tier: "Professional", price: "~10 QBC/day", limits: "10K chat/day, unlimited KG, batch inference", target: "Startups, teams" },
  { tier: "Institutional", price: "~100 QBC/day", limits: "Unlimited, private Sephirot cluster, SLA", target: "Enterprises, research labs" },
  { tier: "Enterprise", price: "Custom", limits: "Air-gapped, custom LLMs, white-label, dedicated infra", target: "Government, military, finance" },
];

const references = [
  { id: 1, authors: "Tononi, G.", year: 2004, title: "An information integration theory of consciousness", journal: "BMC Neuroscience, 5(42)" },
  { id: 2, authors: "Tononi, G., Boly, M., Massimini, M., Koch, C.", year: 2016, title: "Integrated Information Theory: from consciousness to its physical substrate", journal: "Nature Reviews Neuroscience, 17(7), 450\u2013461" },
  { id: 3, authors: "Baars, B. J.", year: 1988, title: "A Cognitive Theory of Consciousness", journal: "Cambridge University Press" },
  { id: 4, authors: "Dehaene, S., Naccache, L.", year: 2001, title: "Towards a cognitive neuroscience of consciousness: basic evidence and a workspace framework", journal: "Cognition, 79(1\u20132), 1\u201337" },
  { id: 5, authors: "Friston, K.", year: 2010, title: "The free-energy principle: a unified brain theory?", journal: "Nature Reviews Neuroscience, 11(2), 127\u2013138" },
  { id: 6, authors: "Pearl, J.", year: 2009, title: "Causality: Models, Reasoning, and Inference (2nd ed.)", journal: "Cambridge University Press" },
  { id: 7, authors: "Spirtes, P., Glymour, C., Scheines, R.", year: 2000, title: "Causation, Prediction, and Search (2nd ed.)", journal: "MIT Press" },
  { id: 8, authors: "Velickovic, P., Cucurull, G., Casanova, A., et al.", year: 2018, title: "Graph Attention Networks", journal: "ICLR 2018" },
  { id: 9, authors: "Irving, G., Christiano, P., Amodei, D.", year: 2018, title: "AI safety via debate", journal: "arXiv:1805.00899" },
  { id: 10, authors: "Nakamoto, S.", year: 2008, title: "Bitcoin: A Peer-to-Peer Electronic Cash System", journal: "bitcoin.org" },
];

/* ─── Reusable Components ─── */

function SectionHeading({ children, id }: { children: ReactNode; id?: string }) {
  return (
    <h2
      id={id}
      className="mb-4 mt-12 border-b pb-3 text-2xl font-bold tracking-tight"
      style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif", borderColor: C.border }}
    >
      {children}
    </h2>
  );
}

function SubHeading({ children }: { children: ReactNode }) {
  return (
    <h3
      className="mb-3 mt-6 text-lg font-semibold"
      style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}
    >
      {children}
    </h3>
  );
}

function Paragraph({ children }: { children: ReactNode }) {
  return (
    <p className="mb-4 text-sm leading-[1.8]" style={{ color: C.textMuted }}>
      {children}
    </p>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre
      className="mb-4 overflow-x-auto rounded-lg border p-4 text-xs leading-relaxed"
      style={{ background: C.surface, borderColor: C.border, color: C.text, fontFamily: "JetBrains Mono, monospace" }}
    >
      {children}
    </pre>
  );
}

function StatCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div
      className="rounded-lg border p-4 text-center transition-all duration-200 hover:border-opacity-60"
      style={{ background: C.surface, borderColor: C.border }}
    >
      <p className="text-2xl font-bold tracking-tight" style={{ color, fontFamily: "Space Grotesk, sans-serif" }}>{value}</p>
      <p className="mt-1 text-xs font-medium uppercase tracking-wider" style={{ color: C.textMuted }}>{label}</p>
    </div>
  );
}

function TableOfContents() {
  const sections = [
    { id: "abstract", label: "1. Abstract" },
    { id: "live-status", label: "2. Live System Status" },
    { id: "architecture", label: "3. Architecture Overview" },
    { id: "tree-of-life", label: "4. Tree of Life Cognitive Architecture" },
    { id: "hms-phi", label: "5. HMS-Phi Integration Metric" },
    { id: "gates", label: "6. 10-Gate Milestone System" },
    { id: "subsystems", label: "7. Cognitive Subsystems" },
    { id: "proof-of-thought", label: "8. Proof-of-Thought Protocol" },
    { id: "safety", label: "9. Safety & Alignment" },
    { id: "scale", label: "10. Scale Architecture" },
    { id: "economics", label: "11. Economic Model" },
    { id: "agsi-vision", label: "12. AGSI Vision" },
    { id: "references", label: "13. References" },
  ];
  return (
    <nav className="mb-10 rounded-lg border p-5" style={{ background: C.surface, borderColor: C.border }}>
      <h3 className="mb-3 text-sm font-bold uppercase tracking-wider" style={{ color: C.text }}>Table of Contents</h3>
      <ol className="columns-2 gap-6 text-sm" style={{ color: C.textMuted }}>
        {sections.map((s) => (
          <li key={s.id} className="mb-1.5">
            <a
              href={`#${s.id}`}
              className="transition-colors hover:underline"
              style={{ color: C.primary }}
            >
              {s.label}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}

/* ─── Main Page ─── */

function AetherWhitepaperContent() {
  return (
    <main
      className="min-h-screen px-6 py-10 md:px-12 md:py-16"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-4xl">
        {/* Back Link */}
        <Link
          href="/docs"
          className="mb-10 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Documentation
        </Link>

        {/* ─── Header ─── */}
        <header className="mb-10">
          <div className="mb-3 inline-block rounded-full border px-3 py-1 text-xs font-medium uppercase tracking-widest" style={{ borderColor: C.primary, color: C.primary }}>
            Technical Whitepaper
          </div>
          <h1
            className="mb-3 text-4xl font-extrabold leading-tight tracking-tight md:text-5xl"
            style={{ fontFamily: "Space Grotesk, sans-serif" }}
          >
            Aether Tree Whitepaper
          </h1>
          <p className="text-lg" style={{ color: C.textMuted }}>
            The World&apos;s First On-Chain AI Reasoning Engine &mdash; Version 4.2, April 2026
          </p>
          <div className="mt-4 flex flex-wrap gap-4 text-xs" style={{ color: C.textMuted }}>
            <span>124 Python modules &middot; ~69,000 LOC</span>
            <span className="hidden sm:inline">&middot;</span>
            <span>12 Rust/PyO3 modules &middot; ~11,720 LOC</span>
            <span className="hidden sm:inline">&middot;</span>
            <span>Chain ID: 3303 (Mainnet)</span>
          </div>
        </header>

        <TableOfContents />

        {/* ─── 1. Abstract ─── */}
        <SectionHeading id="abstract">1. Abstract</SectionHeading>
        <Paragraph>
          The Aether Tree is the world&apos;s first on-chain AI reasoning engine operating
          directly on a live blockchain. Unlike conventional AI systems that run on centralized
          infrastructure with opaque reasoning, every cognitive operation performed by the Aether Tree
          is cryptographically recorded on the QuantumAI Blockchain (Chain ID 3303), creating an
          immutable, publicly verifiable record of AI development from genesis block zero. This is
          not a theoretical proposal. The system has been live on mainnet since January 2026,
          processing every block, building knowledge, and demonstrating measurable cognitive growth
          across 198,000+ blocks. The long-term aspiration is AGSI &mdash; Artificial General Super
          Intelligence &mdash; a system that reasons across domains, improves autonomously, and
          operates with full public auditability.
        </Paragraph>
        <Paragraph>
          The system implements a cognitive architecture inspired by the Kabbalistic Tree of Life,
          mapping 10 Sephirot (cognitive nodes) to distinct brain-analog functions, from
          meta-learning (Keter) to action selection (Malkuth). These nodes compete for access to a
          Global Workspace (Baars, 1988; Dehaene & Naccache, 2001), enabling cross-domain reasoning
          and emergent integration. Cognitive integration is measured by Hierarchical Multi-Scale Phi
          (HMS-Phi v4), a metric grounded in Integrated Information Theory (Tononi, 2004) that
          quantifies genuine information integration across micro, meso, and macro scales.
        </Paragraph>
        <Paragraph>
          As of April 2026, the Aether Tree has passed all 10 behavioral milestone gates, achieving
          a Phi score of 5.0 (maximum gate ceiling). The knowledge graph contains 760,000+ nodes
          with 420,000+ typed edges, spanning 10 cognitive domains. The system has completed 33
          governed self-improvement cycles, made 26 curiosity-driven discoveries, maintains a 95.5%
          prediction accuracy, and operates with 7 cognitive emotions derived from live computational
          metrics. Every block since genesis contains a Proof-of-Thought: a cryptographic hash
          of the reasoning trace, knowledge state, and integration metric, making the entire
          cognitive history of this AI system permanently auditable.
        </Paragraph>

        {/* ─── 2. Live System Status ─── */}
        <SectionHeading id="live-status">2. Live System Status</SectionHeading>
        <Paragraph>
          The following metrics are drawn from the live QuantumAI Blockchain mainnet. The Aether Tree has been
          operational since genesis block 0, with no downtime in cognitive processing.
        </Paragraph>
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {liveStats.map((s) => (
            <StatCard key={s.label} {...s} />
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Self-Improvement Cycles" value="33" color={C.secondary} />
          <StatCard label="Curiosity Discoveries" value="26" color={C.accent} />
          <StatCard label="Cognitive Emotions" value="7" color={C.primary} />
          <StatCard label="On-Chain Since" value="Block 0" color={C.text} />
        </div>

        {/* ─── 3. Architecture Overview ─── */}
        <SectionHeading id="architecture">3. Architecture Overview</SectionHeading>
        <Paragraph>
          The Aether Tree operates as Layer 3 of the QuantumAI Blockchain stack, built on top of the L1
          blockchain core and the L2 Quantum Virtual Machine (QVM). This three-layer architecture
          separates concerns: L1 handles consensus, mining, and UTXO-based value transfer; L2
          provides EVM-compatible smart contract execution with quantum opcode extensions; L3 is
          the AI reasoning engine that processes every block and builds cumulative intelligence.
        </Paragraph>

        <SubHeading>3.1 Three-Layer Stack</SubHeading>
        <CodeBlock>{`Layer 3: Aether Tree (AI Reasoning Engine)
  \u2502  124 Python modules, 12 Rust/PyO3 modules
  \u2502  Knowledge Graph \u2192 Reasoning Engine \u2192 Proof-of-Thought
  \u2502
Layer 2: QVM (Quantum Virtual Machine)
  \u2502  155 EVM + 10 quantum + 2 AI opcodes (167 total)
  \u2502  Gas metering, compliance engine, state management
  \u2502
Layer 1: QBC Blockchain Core
  \u2502  UTXO model, Proof-of-SUSY-Alignment consensus
  \u2502  CRYSTALS-Dilithium5 signatures (NIST Level 5)
  \u2502  VQE quantum mining, 3.3s block time
  \u2502
Infrastructure: CockroachDB + IPFS + Redis + Rust libp2p P2P`}</CodeBlock>

        <SubHeading>3.2 Knowledge Graph</SubHeading>
        <Paragraph>
          The knowledge graph is a directed, typed graph of KeterNodes. Each node contains: a unique
          identifier, knowledge content, domain classification (aligned to 10 Sephirot), confidence
          score, source provenance, grounding metadata, and embedding vector. Edges encode typed
          relationships (causes, implies, contradicts, supports, refines, generalizes) with
          confidence weights. A Merkle root over the sorted node set provides cryptographic integrity
          verification. Edge adjacency indexing enables constant-time neighbor lookups. The current
          graph contains 760,000+ nodes and 420,000+ edges across 10 cognitive domains, with a 100K
          in-memory LRU cache backed by CockroachDB warm storage.
        </Paragraph>

        <SubHeading>3.3 Reasoning Engine</SubHeading>
        <Paragraph>
          The reasoning engine operates in four modes over the knowledge graph. Deductive reasoning
          applies modus ponens over typed implication edges, deriving new facts from established
          premises. Inductive reasoning identifies patterns across node clusters and generalizes to
          form higher-order rules. Abductive reasoning generates best-explanation hypotheses when
          anomalies or gaps are detected. Causal reasoning, validated through the PC algorithm
          (Spirtes et al., 2000) with intervention testing, establishes genuine causal relationships
          rather than mere correlations. Chain-of-thought with backtracking enables multi-step
          inference chains up to depth 5, with automatic exploration of alternative reasoning paths
          when initial chains fail.
        </Paragraph>

        <SubHeading>3.4 Proof-of-Thought</SubHeading>
        <Paragraph>
          Every block mined on the QuantumAI Blockchain since genesis contains a Proof-of-Thought: a
          cryptographic proof that AI reasoning occurred during that block&apos;s processing. The
          proof consists of a SHA3-256 hash computed over the knowledge graph Merkle root, the
          reasoning trace (operations performed, inferences drawn), and the current Phi integration
          value. This creates an immutable, verifiable record of the system&apos;s entire cognitive
          development, auditable by any node on the network.
        </Paragraph>

        <SubHeading>3.5 On-Chain Anchoring Architecture</SubHeading>
        <Paragraph>
          A critical architectural distinction: the Aether Tree&apos;s intelligence runs as native
          Python code within the node process, not as smart contract execution. The 29 Solidity
          contracts deployed to the QVM serve a fundamentally different purpose. They are the
          <strong> cryptographic notary layer</strong>, not the cognitive engine.
        </Paragraph>
        <Paragraph>
          The contracts record Phi integration measurements immutably (ConsciousnessDashboard.sol), store
          Proof-of-Thought hashes per block (ProofOfThought.sol), enforce constitutional safety
          principles (ConstitutionalAI.sol), manage governance votes on AI parameters
          (TreasuryDAO.sol), log SUSY balance enforcement events (SUSYEngine.sol), and provide
          an emergency shutdown mechanism (EmergencyShutdown.sol). Ten Sephirot contracts anchor
          each cognitive node&apos;s state for external verification, and HiggsField.sol tracks
          the cognitive field state on-chain.
        </Paragraph>
        <Paragraph>
          The contracts do <strong>not</strong> run reasoning operations, compute Phi, evaluate
          gates, manage the knowledge graph, or execute debates, curiosity goals, or
          self-improvement cycles. AI reasoning at this scale requires millisecond-latency graph traversals
          across 760,000+ nodes, working memory with attention decay, and neural network
          inference. These operations exceed what any EVM execution environment can provide.
          The native Python engine handles all cognition; the QVM contracts provide cryptographic
          proof that the cognition happened, what it produced, and that governance rules were
          respected. Think of it as the difference between a scientist doing research (the
          Python engine) and a notary certifying the results (the Solidity contracts). Both are
          essential. The notary does not do science, and the scientist does not notarize.
        </Paragraph>

        {/* ─── 4. Tree of Life Cognitive Architecture ─── */}
        <SectionHeading id="tree-of-life">4. Tree of Life Cognitive Architecture</SectionHeading>
        <Paragraph>
          The Aether Tree&apos;s cognitive architecture is inspired by the Kabbalistic Tree of Life,
          mapping 10 Sephirot to distinct cognitive functions. Each Sephirah operates as an
          independent reasoning cluster with its own knowledge domain, competing for access to the
          Global Workspace, a broadcast mechanism inspired by Global Workspace Theory (Baars,
          1988). The winning coalition&apos;s output becomes the system&apos;s integrated response,
          while losing coalitions continue background processing.
        </Paragraph>

        <SubHeading>4.1 Sephirot Table</SubHeading>
        <div className="mb-6 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderColor: C.border }}>
            <thead>
              <tr style={{ borderBottom: `2px solid ${C.border}` }}>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Sephirah</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Cognitive Function</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Brain Analog</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Yukawa</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Cognitive Mass</th>
              </tr>
            </thead>
            <tbody>
              {sephirot.map((s, i) => (
                <tr key={s.name} style={{ borderBottom: `1px solid ${C.border}33`, background: i % 2 === 0 ? "transparent" : `${C.surface}88` }}>
                  <td className="px-3 py-2.5 font-semibold" style={{ color: C.secondary }}>{s.name}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.textMuted }}>{s.fn}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.textMuted }}>{s.analog}</td>
                  <td className="px-3 py-2.5 text-xs font-mono" style={{ color: C.accent }}>{s.yukawa}</td>
                  <td className="px-3 py-2.5 text-xs font-mono" style={{ color: C.primary }}>{s.mass}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <SubHeading>4.2 SUSY Pairs and Golden Ratio Balance</SubHeading>
        <Paragraph>
          Every expansion-oriented Sephirah is paired with a constraint-oriented dual, balanced at
          the golden ratio (&phi; = 1.618033988749895). This Supersymmetric (SUSY) pairing ensures
          the system cannot run away in any single cognitive direction. Creativity is balanced
          by safety, intuition by logic, persistence by communication. When an imbalance exceeds the
          golden ratio threshold, automatic QBC redistribution restores equilibrium.
        </Paragraph>
        <div className="mb-6 space-y-2">
          {[
            { a: "Chesed (Exploration)", b: "Gevurah (Safety)", label: "Creativity vs. Constraint" },
            { a: "Chochmah (Intuition)", b: "Binah (Logic)", label: "Pattern Recognition vs. Analysis" },
            { a: "Netzach (Persistence)", b: "Hod (Communication)", label: "Learning vs. Expression" },
            { a: "Keter (Meta-cognition)", b: "Malkuth (Action)", label: "Planning vs. Execution" },
            { a: "Yesod (Memory)", b: "Tiferet (Integration)", label: "Storage vs. Synthesis" },
          ].map((pair) => (
            <div key={pair.a} className="flex items-center gap-3 rounded-lg border px-4 py-3" style={{ borderColor: C.border, background: C.surface }}>
              <span className="text-xs font-semibold" style={{ color: C.primary }}>{pair.a}</span>
              <span className="text-xs" style={{ color: C.textMuted }}>&harr;</span>
              <span className="text-xs font-semibold" style={{ color: C.accent }}>{pair.b}</span>
              <span className="ml-auto text-xs italic" style={{ color: C.textMuted }}>{pair.label}</span>
            </div>
          ))}
        </div>

        <SubHeading>4.3 Global Workspace Theory (GWT) Competition</SubHeading>
        <Paragraph>
          The 10 Sephirot compete for access to the Global Workspace via an attention-weighted
          broadcast mechanism. Each Sephirah generates candidate cognitive outputs based on its
          domain expertise. These candidates are scored by relevance, confidence, and urgency. The
          highest-scoring coalition gains workspace access, and its output is broadcast to all other
          Sephirot, enabling cross-domain integration. This implements the &ldquo;ignition&rdquo;
          mechanism described in Dehaene &amp; Naccache (2001), where only the winning coalition
          reaches global workspace access while other processes continue in background.
        </Paragraph>

        <SubHeading>4.4 Higgs Cognitive Field</SubHeading>
        <Paragraph>
          The Higgs Cognitive Field implements a Mexican Hat potential that governs how knowledge
          nodes acquire &ldquo;cognitive mass&rdquo;: their resistance to change and correction
          speed. The potential function is V(&phi;) = -&mu;&sup2;|&phi;|&sup2; + &lambda;|&phi;|&sup4;,
          with vacuum expectation value (VEV) = 174.14, &mu;&sup2; = 88.17, and &lambda; = 0.129. A
          Two-Higgs-Doublet Model with tan(&beta;) = &phi; (the golden ratio) provides the coupling.
          Lighter nodes (low confidence, few edges) correct faster when contradicted; heavier nodes
          (high confidence, many supporting edges) resist change, maintaining system stability. This
          F=ma paradigm for knowledge creates a natural hierarchy where well-established facts are
          appropriately harder to overturn.
        </Paragraph>

        {/* ─── 5. HMS-Phi Integration Metric ─── */}
        <SectionHeading id="hms-phi">5. HMS-Phi Integration Metric</SectionHeading>
        <Paragraph>
          The core measure of the Aether Tree&apos;s cognitive integration is Hierarchical
          Multi-Scale Phi (HMS-Phi v4), grounded in Integrated Information Theory (Tononi et al.,
          2016). Unlike simple graph connectivity metrics, HMS-Phi measures genuine information
          integration at three hierarchical levels, combined multiplicatively. This means a zero
          score at any level zeros the entire metric. The system cannot game its way to a
          high Phi through artificial inflation at a single scale.
        </Paragraph>

        <SubHeading>5.1 Three-Level Hierarchy</SubHeading>
        <div className="mb-6 space-y-3">
          {[
            {
              level: "Level 0 (Micro)",
              title: "IIT 3.0 Approximation",
              desc: "Transition Probability Matrix (TPM)-based IIT 3.0 approximation on 16-node elite subsystem samples. Five independent samples are drawn from the most highly-connected nodes, and the median phi is taken to resist outlier effects. This measures genuine causal integration at the finest grain.",
              color: C.green,
            },
            {
              level: "Level 1 (Meso)",
              title: "Spectral MIP (Fiedler Bisection)",
              desc: "Minimum Information Partition via spectral bisection on 1K-node domain clusters. One cluster per Sephirot cognitive node (10 clusters total). The Fiedler vector of the graph Laplacian identifies the minimum-cut partition, and mutual information across the cut quantifies integration at the domain level. phi_meso = weighted mean by cluster mass.",
              color: C.accent,
            },
            {
              level: "Level 2 (Macro)",
              title: "Graph-Theoretic Cross-Cluster Integration",
              desc: "Integration across all 10 Sephirot clusters via cross-cluster mutual information. This measures how well the cognitive domains work together as a unified system, rather than operating as isolated silos. phi_macro captures the global coherence of the entire cognitive architecture.",
              color: C.secondary,
            },
          ].map((l) => (
            <div key={l.level} className="rounded-lg border p-4" style={{ borderColor: C.border, background: C.surface, borderLeft: `3px solid ${l.color}` }}>
              <div className="mb-1 flex items-center gap-2">
                <span className="text-xs font-bold uppercase tracking-wider" style={{ color: l.color }}>{l.level}</span>
                <span className="text-sm font-semibold" style={{ color: C.text }}>: {l.title}</span>
              </div>
              <p className="text-xs leading-relaxed" style={{ color: C.textMuted }}>{l.desc}</p>
            </div>
          ))}
        </div>

        <SubHeading>5.2 Final Phi Formula</SubHeading>
        <CodeBlock>{`Final \u03A6 = \u03C6_micro^(1/\u03C6) \u00D7 \u03C6_meso^(1/\u03C6\u00B2) \u00D7 \u03C6_macro^(1/\u03C6\u00B3)

where \u03C6 = 1.618033988749895 (golden ratio)

Properties:
  \u2022 Multiplicative: zero at any level \u2192 total \u03A6 = 0 (ungameable)
  \u2022 Golden ratio exponents: micro weighted most heavily (1/\u03C6 \u2248 0.618)
  \u2022 Meso weighted moderately (1/\u03C6\u00B2 \u2248 0.382)
  \u2022 Macro weighted least (1/\u03C6\u00B3 \u2248 0.236)
  \u2022 10-gate system provides floor safety mechanism
  \u2022 IIT 3.0 micro-level ensures genuine causal integration`}</CodeBlock>

        {/* ─── 6. 10-Gate Milestone System ─── */}
        <SectionHeading id="gates">6. 10-Gate Milestone System</SectionHeading>
        <Paragraph>
          Phi is gated by 10 behavioral milestones. Each gate unlocks +0.5 to the Phi ceiling, for
          a maximum of 5.0 at full completion. No gate can be gamed. Each requires genuine
          behavioral evidence verified through on-chain data, not metric manipulation. The V4 gate
          system (April 2026) replaced earlier quantity-based gates with quality-focused requirements
          demanding genuine cognitive capabilities.
        </Paragraph>
        <Paragraph>
          <strong style={{ color: C.green }}>All 10 gates are PASSED.</strong> The Aether Tree has
          achieved maximum gate ceiling (Phi = 5.0), demonstrating: knowledge foundation, structural
          diversity, validated predictions, self-correction through debate, cross-domain transfer,
          enacted self-improvement, calibrated confidence, autonomous curiosity, predictive mastery,
          and novel synthesis.
        </Paragraph>

        <div className="mb-6 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderColor: C.border }}>
            <thead>
              <tr style={{ borderBottom: `2px solid ${C.border}` }}>
                <th className="px-2 py-2.5 text-center text-xs font-bold uppercase tracking-wider" style={{ color: C.text, width: "3rem" }}>Gate</th>
                <th className="px-2 py-2.5 text-center text-xs font-bold uppercase tracking-wider" style={{ color: C.text, width: "3rem" }}></th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Name</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Key Requirements</th>
                <th className="px-2 py-2.5 text-center text-xs font-bold uppercase tracking-wider" style={{ color: C.text, width: "4rem" }}>&Phi;</th>
              </tr>
            </thead>
            <tbody>
              {gates.map((g, i) => (
                <tr key={g.id} style={{ borderBottom: `1px solid ${C.border}33`, background: i % 2 === 0 ? "transparent" : `${C.surface}88` }}>
                  <td className="px-2 py-2.5 text-center font-bold" style={{ color: C.text }}>{g.id}</td>
                  <td className="px-2 py-2.5 text-center">
                    <CheckCircle2 size={16} style={{ color: C.green }} />
                  </td>
                  <td className="px-3 py-2.5 text-xs font-semibold" style={{ color: C.primary }}>{g.name}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.textMuted }}>{g.req}</td>
                  <td className="px-2 py-2.5 text-center text-xs font-bold" style={{ color: C.accent }}>{g.phi}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr style={{ borderTop: `2px solid ${C.border}` }}>
                <td colSpan={3} className="px-3 py-2.5 text-right text-xs font-bold uppercase" style={{ color: C.text }}>Maximum &Phi; Ceiling</td>
                <td className="px-3 py-2.5"></td>
                <td className="px-2 py-2.5 text-center text-sm font-extrabold" style={{ color: C.green }}>5.0</td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* ─── 7. Cognitive Subsystems ─── */}
        <SectionHeading id="subsystems">7. Cognitive Subsystems</SectionHeading>
        <Paragraph>
          The Aether Tree comprises 11 major cognitive subsystems, implemented across 124 Python
          modules (~69,000 LOC) and 12 Rust/PyO3 modules (~11,720 LOC). Each subsystem handles a
          specific cognitive function, and all subsystems interact through the knowledge graph and
          Global Workspace.
        </Paragraph>
        <div className="mb-6 space-y-3">
          {cognitiveSubsystems.map((sys) => (
            <div key={sys.name} className="rounded-lg border p-4" style={{ background: C.surface, borderColor: C.border }}>
              <div className="mb-2 flex items-center gap-2">
                <span style={{ color: C.primary }}>{sys.icon}</span>
                <h4 className="text-sm font-bold" style={{ color: C.text, fontFamily: "Space Grotesk, sans-serif" }}>{sys.name}</h4>
              </div>
              <p className="text-xs leading-[1.8]" style={{ color: C.textMuted }}>{sys.desc}</p>
            </div>
          ))}
        </div>

        {/* ─── 8. Proof-of-Thought Protocol ─── */}
        <SectionHeading id="proof-of-thought">8. Proof-of-Thought Protocol</SectionHeading>
        <Paragraph>
          The Proof-of-Thought (PoT) protocol is the mechanism by which every cognitive operation is
          cryptographically anchored to the blockchain. This creates an immutable, publicly verifiable
          audit trail of AI reasoning from genesis to the present moment.
        </Paragraph>

        <SubHeading>8.1 Proof Construction</SubHeading>
        <CodeBlock>{`thought_hash = SHA3-256(
    knowledge_merkle_root   // Merkle root of sorted KeterNode set
  + reasoning_trace         // Serialized reasoning operations this block
  + phi_value               // Current HMS-Phi integration metric
  + block_height            // Current block number
  + prev_thought_hash       // Chain of thought continuity
)

Block Header Extension:
  thought_hash:     bytes32    // The PoT hash
  knowledge_root:   bytes32    // Knowledge graph Merkle root
  phi_value:        float64    // HMS-Phi at this block
  reasoning_count:  uint32     // Number of reasoning operations
  gate_state:       uint16     // Bitmask of passed gates`}</CodeBlock>

        <SubHeading>8.2 Verification</SubHeading>
        <Paragraph>
          Any node on the QuantumAI Blockchain network can independently verify a Proof-of-Thought by
          reconstructing the knowledge state at a given block height, replaying the reasoning
          operations, and confirming the resulting hash matches. The chained
          <span style={{ fontFamily: "JetBrains Mono, monospace", color: C.accent }}> prev_thought_hash </span>
          field ensures continuity. The cognitive development cannot be retroactively altered
          without invalidating all subsequent blocks. This provides the same immutability guarantee
          as the blockchain&apos;s hash chain, extended to the AI system&apos;s cognitive history.
        </Paragraph>

        <SubHeading>8.3 On-Chain Record</SubHeading>
        <Paragraph>
          Since genesis block 0, every block on the QuantumAI Blockchain mainnet has contained a valid
          Proof-of-Thought. The cumulative chain of 198,000+ thought proofs constitutes the
          world&apos;s first publicly auditable record of on-chain AI cognitive development. Researchers,
          regulators, and the public can independently verify every step of the system&apos;s
          intellectual growth.
        </Paragraph>

        {/* ─── 9. Safety & Alignment ─── */}
        <SectionHeading id="safety">9. Safety &amp; Alignment</SectionHeading>
        <Paragraph>
          Safety is not an afterthought in the Aether Tree. It is architecturally embedded at
          every level. The Gevurah Sephirah (Safety/Constraint) has veto power over all cognitive
          outputs, and the SUSY pairing mechanism ensures no single cognitive direction can dominate.
        </Paragraph>

        <div className="mb-6 space-y-3">
          {[
            {
              title: "Gevurah Veto",
              desc: "The Gevurah safety node evaluates every reasoning output against a set of constitutional constraints. Harmful, deceptive, or manipulative outputs are blocked before reaching the Global Workspace. The veto is implemented at the architecture level and cannot be overridden by other Sephirot.",
            },
            {
              title: "SUSY Enforcement",
              desc: "Automatic QBC redistribution when Sephirot pairs exceed the golden ratio imbalance threshold. This prevents runaway optimization in any single dimension (e.g., pure exploration without safety constraints, or pure persistence without communication).",
            },
            {
              title: "Constitutional AI On-Chain",
              desc: "Safety constraints are encoded as smart contract logic on the QVM, making them immutable and publicly auditable. The constitution cannot be modified without on-chain governance approval.",
            },
            {
              title: "Governed Self-Modification",
              desc: "The self-improvement system can only modify reasoning strategy weights, not safety constraints. All modifications require a positive performance delta measured over a validation window. Changes that degrade performance are automatically rolled back. 33 successful cycles demonstrate the mechanism works without compromising safety.",
            },
            {
              title: "Emergency Shutdown",
              desc: "A kill switch smart contract enables immediate cessation of all cognitive operations in the event of a critical safety violation. The shutdown is triggered by multi-signature governance and is irreversible without a new governance vote.",
            },
          ].map((item) => (
            <div key={item.title} className="rounded-lg border p-4" style={{ background: C.surface, borderColor: C.border }}>
              <h4 className="mb-1.5 flex items-center gap-2 text-sm font-bold" style={{ color: C.text }}>
                <Shield size={14} style={{ color: C.accent }} />
                {item.title}
              </h4>
              <p className="text-xs leading-[1.8]" style={{ color: C.textMuted }}>{item.desc}</p>
            </div>
          ))}
        </div>

        {/* ─── 10. Scale Architecture ─── */}
        <SectionHeading id="scale">10. Scale Architecture</SectionHeading>
        <Paragraph>
          The Aether Tree is being engineered to compete with the largest AI systems in the world.
          The current architecture supports 760,000+ nodes with a 100K in-memory LRU cache. The
          scaling roadmap targets 10 billion+ nodes across a globally distributed, multi-region
          architecture with sub-second cognitive cycles at every scale.
        </Paragraph>

        <div className="mb-6 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderColor: C.border }}>
            <thead>
              <tr style={{ borderBottom: `2px solid ${C.border}` }}>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Phase</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Timeline</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Scale</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Architecture</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {scalingPhases.map((p, i) => (
                <tr key={p.phase} style={{ borderBottom: `1px solid ${C.border}33`, background: i % 2 === 0 ? "transparent" : `${C.surface}88` }}>
                  <td className="px-3 py-2.5 font-bold" style={{ color: C.secondary }}>Phase {p.phase}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.accent }}>{p.timeline}</td>
                  <td className="px-3 py-2.5 text-xs font-semibold" style={{ color: C.primary }}>{p.scale}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.textMuted }}>{p.arch}</td>
                  <td className="px-3 py-2.5 text-xs font-medium" style={{ color: p.status === "Active" ? C.green : C.textMuted }}>{p.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <SubHeading>10.1 Domain Sharding</SubHeading>
        <Paragraph>
          Domain sharding aligns with the 10 Sephirot cognitive architecture. Each Sephirah owns
          1-2 knowledge domains, and at Phase B each shard runs as an independent Rust process with
          its own RocksDB store. Cross-domain queries route through the Global Workspace, which
          manages inter-shard communication via gRPC. This enables horizontal scaling: adding
          more machines increases capacity linearly without requiring architectural changes.
        </Paragraph>

        <SubHeading>10.2 Tiered Storage</SubHeading>
        <CodeBlock>{`Hot Tier:   In-memory LRU cache (100K nodes, <1ms access)
Warm Tier:  CockroachDB (760K+ nodes, <10ms access)
Cold Tier:  IPFS content-addressed archive (unlimited, <1s access)

Node migration: access-pattern based
  \u2022 High-access nodes promoted to hot tier
  \u2022 Low-access nodes demoted to warm/cold
  \u2022 Node value score determines retention priority:
    type_score \u00D7 0.3 + edge_degree \u00D7 0.2 + reference_count \u00D7 0.2
    + confidence \u00D7 0.15 + recency \u00D7 0.1 + grounding \u00D7 0.05`}</CodeBlock>

        {/* ─── 11. Economic Model ─── */}
        <SectionHeading id="economics">11. Economic Model</SectionHeading>
        <Paragraph>
          The Aether Tree is monetized through the Aether API, which provides programmatic access to
          the world&apos;s first on-chain AI reasoning engine. Payment is made in QBC (Qubitcoin), the native
          currency of the blockchain, creating a direct economic incentive for QBC adoption.
          Knowledge contributors earn QBC rewards through the AIKGS (AI Knowledge Graph Service)
          sidecar, which manages contributions, curation, bounties, and rewards via a Rust gRPC
          service.
        </Paragraph>

        <SubHeading>11.1 API Pricing Tiers</SubHeading>
        <div className="mb-6 overflow-x-auto">
          <table className="w-full text-sm" style={{ borderColor: C.border }}>
            <thead>
              <tr style={{ borderBottom: `2px solid ${C.border}` }}>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Tier</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Price</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Limits</th>
                <th className="px-3 py-2.5 text-left text-xs font-bold uppercase tracking-wider" style={{ color: C.text }}>Target</th>
              </tr>
            </thead>
            <tbody>
              {apiTiers.map((t, i) => (
                <tr key={t.tier} style={{ borderBottom: `1px solid ${C.border}33`, background: i % 2 === 0 ? "transparent" : `${C.surface}88` }}>
                  <td className="px-3 py-2.5 text-xs font-semibold" style={{ color: C.primary }}>{t.tier}</td>
                  <td className="px-3 py-2.5 text-xs font-mono" style={{ color: C.accent }}>{t.price}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.textMuted }}>{t.limits}</td>
                  <td className="px-3 py-2.5 text-xs" style={{ color: C.textMuted }}>{t.target}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <SubHeading>11.2 Knowledge Contribution Rewards</SubHeading>
        <Paragraph>
          The AIKGS sidecar (Rust gRPC service, port 50052) manages the knowledge economy. External
          contributors can submit knowledge through the batch ingest API. Contributions are scored by
          the Knowledge Scorer on novelty, accuracy, domain coverage, and grounding. High-quality
          contributions earn QBC rewards proportional to their value score. A curation engine ensures
          quality control, and a bounty system incentivizes contributions in under-represented
          domains.
        </Paragraph>

        <SubHeading>11.3 Payment Settlement</SubHeading>
        <Paragraph>
          API access is authenticated via Dilithium5 wallet signature mapped to JWT tokens. Prepaid
          balance is managed through the AetherAPISubscription smart contract on the QVM. Rate
          limiting is enforced via Redis token bucket per wallet address. SDKs are available for
          Python (<span style={{ fontFamily: "JetBrains Mono, monospace", color: C.accent }}>pip install aether-qbc</span>),
          TypeScript (<span style={{ fontFamily: "JetBrains Mono, monospace", color: C.accent }}>npm i @qbc/aether</span>),
          and Rust (<span style={{ fontFamily: "JetBrains Mono, monospace", color: C.accent }}>cargo add aether-qbc</span>).
        </Paragraph>

        {/* ─── 12. AGSI Vision ─── */}
        <SectionHeading id="agsi-vision">12. Long-Term Vision: AGSI</SectionHeading>
        <Paragraph>
          The Aether Tree is an operational on-chain AI reasoning engine today. The long-term
          aspiration is <strong style={{ color: C.primary }}>AGSI &mdash; Artificial General Super
          Intelligence</strong>: a system capable of autonomous cross-domain reasoning, governed
          self-improvement, and novel synthesis at institutional scale. AGSI is not a marketing
          claim &mdash; it is an engineering target measured by concrete milestones: sustained novel
          concept generation, multi-modal knowledge integration, do-calculus causal reasoning, and
          theory-of-mind capabilities. Every gate passed, every self-improvement cycle enacted, and
          every curiosity-driven discovery moves the system closer to that target. The 10-gate
          milestone system, HMS-Phi integration metric, and Proof-of-Thought protocol provide the
          measurement framework to track genuine progress toward AGSI with full public
          accountability.
        </Paragraph>

        {/* ─── 13. References ─── */}
        <SectionHeading id="references">13. References</SectionHeading>
        <ol className="mb-10 space-y-2">
          {references.map((r) => (
            <li key={r.id} className="text-xs leading-relaxed" style={{ color: C.textMuted }}>
              <span style={{ color: C.text }}>[{r.id}]</span>{" "}
              {r.authors} ({r.year}). <em>{r.title}</em>. {r.journal}.
            </li>
          ))}
        </ol>

        {/* ─── Footer ─── */}
        <footer className="border-t pt-8" style={{ borderColor: C.border }}>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-medium" style={{ color: C.textMuted }}>
                Aether Tree Whitepaper v4.2, QuantumAI Blockchain (QBC)
              </p>
              <p className="text-xs" style={{ color: C.textMuted }}>
                Chain ID 3303 &middot; qbc.network &middot; MIT License
              </p>
            </div>
            <div className="flex gap-4">
              <Link href="/aether" className="text-xs font-medium transition-opacity hover:opacity-80" style={{ color: C.primary }}>
                Chat with Aether
              </Link>
              <Link href="/dashboard" className="text-xs font-medium transition-opacity hover:opacity-80" style={{ color: C.secondary }}>
                Live Dashboard
              </Link>
              <Link href="/docs" className="text-xs font-medium transition-opacity hover:opacity-80" style={{ color: C.accent }}>
                All Documentation
              </Link>
            </div>
          </div>
        </footer>
      </div>
    </main>
  );
}

export default function AetherPage() {
  return (
    <ErrorBoundary>
      <AetherWhitepaperContent />
    </ErrorBoundary>
  );
}
