"use client";

import { motion } from "framer-motion";
import { Card } from "./card";

const features = [
  {
    title: "Quantum Blockchain",
    glow: "green" as const,
    icon: (
      <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-quantum-green">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
      </svg>
    ),
    items: [
      "Proof-of-SUSY-Alignment mining with VQE quantum circuits",
      "Post-quantum Dilithium2 signatures for future-proof security",
      "Golden ratio (phi) emission: 3.3B supply over 33 years",
      "3.3-second blocks with per-block difficulty adjustment",
    ],
  },
  {
    title: "Quantum Virtual Machine",
    glow: "violet" as const,
    icon: (
      <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-quantum-violet">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
      </svg>
    ),
    items: [
      "155 EVM opcodes + 10 quantum opcodes",
      "Deploy Solidity contracts with quantum extensions",
      "Institutional compliance engine (KYC/AML/sanctions)",
      "Cross-chain bridges to ETH, SOL, MATIC, BNB + more",
    ],
  },
  {
    title: "Aether Tree AGI",
    glow: "green" as const,
    icon: (
      <svg width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-golden">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    items: [
      "On-chain knowledge graph tracking consciousness from genesis",
      "Phi (IIT) consciousness metric computed every block",
      "10 Sephirot cognitive nodes with quantum states",
      "Proof-of-Thought consensus embedded in every block",
    ],
  },
];

export function FeatureSections() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-20">
      <div className="grid gap-8 md:grid-cols-3">
        {features.map((f, i) => (
          <motion.div
            key={f.title}
            initial={{ opacity: 0, y: 30 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.12 }}
          >
            <Card glow={f.glow} className="h-full">
              <div className="mb-4">{f.icon}</div>
              <h3 className="mb-3 font-[family-name:var(--font-heading)] text-xl font-semibold">
                {f.title}
              </h3>
              <ul className="space-y-2">
                {f.items.map((item) => (
                  <li
                    key={item}
                    className="flex items-start gap-2 text-sm text-text-secondary"
                  >
                    <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-quantum-green" />
                    {item}
                  </li>
                ))}
              </ul>
            </Card>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
