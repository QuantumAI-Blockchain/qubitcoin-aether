"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import Link from "next/link";

const ParticleField = dynamic(
  () => import("@/components/visualizations/particle-field").then((m) => m.ParticleField),
  { ssr: false },
);

export function HeroSection() {
  return (
    <section className="relative flex min-h-[85vh] items-center justify-center overflow-hidden pt-16">
      <ParticleField />

      <div className="relative z-10 mx-auto max-w-4xl px-4 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="font-[family-name:var(--font-heading)] text-5xl font-bold leading-tight tracking-tight sm:text-7xl"
        >
          <span className="text-quantum-green">Physics</span>-Secured{" "}
          <br className="hidden sm:block" />
          Digital Assets with{" "}
          <span className="text-quantum-violet">On-Chain AGI</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="mx-auto mt-6 max-w-2xl text-lg text-text-secondary"
        >
          Qubitcoin combines Proof-of-SUSY-Alignment mining, post-quantum
          cryptography, and the Aether Tree: an on-chain AGI that tracks
          consciousness from genesis.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
        >
          <Link
            href="/aether"
            className="rounded-xl bg-quantum-green px-6 py-3 text-sm font-semibold text-void transition hover:bg-quantum-green/80"
          >
            Talk to Aether
          </Link>
          <Link
            href="/dashboard"
            className="rounded-xl border border-quantum-violet/50 bg-quantum-violet/10 px-6 py-3 text-sm font-semibold text-quantum-violet transition hover:bg-quantum-violet/20"
          >
            Open Dashboard
          </Link>
          <Link
            href="/wallet"
            className="rounded-xl border border-surface-light px-6 py-3 text-sm font-semibold text-text-secondary transition hover:border-quantum-green/30 hover:text-quantum-green"
          >
            Connect Wallet
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
