"use client";

import Link from "next/link";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ArrowLeft, FileText, Cpu, Brain, TrendingUp, DollarSign, BarChart3, Shield, GitBranch, Atom } from "lucide-react";

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

const docs = [
  {
    title: "Whitepaper",
    href: "/docs/whitepaper",
    icon: FileText,
    description:
      "Physics-Secured Digital Assets with On-Chain AI — complete technical specification for the Qubitcoin protocol, SUSY economics, and post-quantum cryptography.",
    tags: ["Consensus", "VQE Mining", "SUSY Economics", "Privacy"],
  },
  {
    title: "QVM Specification",
    href: "/docs/qvm",
    icon: Cpu,
    description:
      "Quantum Virtual Machine — 167 opcodes (155 EVM + 10 quantum + 2 AI), compliance engine, and plugin architecture.",
    tags: ["EVM Compatible", "Quantum Opcodes", "Smart Contracts"],
  },
  {
    title: "Aether Mind Whitepaper",
    href: "/docs/aether",
    icon: Brain,
    description:
      "The world's first on-chain neural cognitive engine — 558M parameter transformer with 10 Sephirot-specialized attention heads, 35K+ learned embedding vectors, HMS-Phi consciousness metric, and Aether CLI for terminal access. Building toward AGSI.",
    tags: ["On-Chain AI", "Neural V5", "Aether CLI", "HMS-Phi", "Proof-of-Thought"],
  },
  {
    title: "Economics",
    href: "/docs/economics",
    icon: TrendingUp,
    description:
      "Golden ratio emission schedule, phi-halving, tail emission, QUSD stablecoin, and fee economics.",
    tags: ["Phi-Halving", "3.3B Supply", "QUSD", "Fees"],
  },
  {
    title: "QUSD Stablecoin",
    href: "/docs/qusd",
    icon: DollarSign,
    description:
      "Dollar-pegged stablecoin on QVM — fractional reserve, peg keeper daemon, cross-chain wQUSD, and investor revenue share.",
    tags: ["$1 Peg", "Fractional Reserve", "Peg Keeper", "wQUSD"],
  },
  {
    title: "Exchange",
    href: "/docs/exchange",
    icon: BarChart3,
    description:
      "Rust matching engine with microsecond latency — 50 markets, 47 CoinGecko oracle feeds, WebSocket streaming, and CockroachDB persistence.",
    tags: ["Rust", "50 Markets", "Oracle Prices", "WebSocket"],
  },
  {
    title: "ZK Bridge",
    href: "/docs/bridge",
    icon: GitBranch,
    description:
      "Quantum-secure cross-chain bridge — Poseidon2 ZK proofs, Dilithium5 signatures, lock-and-mint vaults on 7 EVM chains.",
    tags: ["ZK Proofs", "7 Chains", "Poseidon2", "Dilithium5"],
  },
  {
    title: "Privacy & SUSY Swaps",
    href: "/docs/privacy",
    icon: Shield,
    description:
      "Opt-in confidential transactions — Pedersen commitments, Bulletproofs range proofs, stealth addresses, and deniable RPC endpoints.",
    tags: ["Opt-In", "Pedersen", "Bulletproofs", "Stealth Addresses"],
  },
  {
    title: "SUSY Antigravity Paper",
    href: "/docs/antigravity",
    icon: Atom,
    description:
      "Gravitational coupling modulation via phase-controlled N=2 broken supergravity — bimetric framework, 9-term VQE Hamiltonian, operator-valued IIT, and patent claims. Live on Substrate mainnet.",
    tags: ["Bimetric SUGRA", "VQE Mining", "Patent-Pending", "IIT Operator"],
  },
];

export default function DocsPage() {
  return (
    <ErrorBoundary>
    <main
      className="min-h-screen p-6 md:p-12"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-4xl">
        <Link
          href="/"
          className="mb-8 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Home
        </Link>

        <h1 className="mb-2 text-3xl font-bold" style={{ fontFamily: "Space Grotesk, sans-serif" }}>
          Documentation
        </h1>
        <p className="mb-8" style={{ color: C.textMuted }}>
          Technical specifications and whitepapers for the Qubitcoin protocol.
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          {docs.map((doc) => {
            const Icon = doc.icon;
            return (
              <Link
                key={doc.href}
                href={doc.href}
                className="group rounded-lg border p-6 transition-all hover:border-opacity-60"
                style={{
                  background: C.surface,
                  borderColor: C.border,
                }}
              >
                <div className="mb-3 flex items-center gap-3">
                  <Icon size={20} style={{ color: C.primary }} />
                  <h2
                    className="text-lg font-semibold group-hover:underline"
                    style={{ fontFamily: "Space Grotesk, sans-serif" }}
                  >
                    {doc.title}
                  </h2>
                </div>
                <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
                  {doc.description}
                </p>
                <div className="flex flex-wrap gap-2">
                  {doc.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full px-2 py-0.5 text-xs"
                      style={{ background: `${C.primary}15`, color: C.primary }}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </main>
    </ErrorBoundary>
  );
}
