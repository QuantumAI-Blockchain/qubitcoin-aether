"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";

const SUSYSimulator = dynamic(
  () => import("@/components/antigravity/susy-simulator").then((m) => m.SUSYSimulator),
  { ssr: false, loading: () => <SimulatorSkeleton /> },
);

function SimulatorSkeleton() {
  return (
    <div className="space-y-8">
      <div className="h-[500px] rounded-2xl border border-gray-800 bg-[#0d0d14] animate-pulse" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl border border-gray-800 bg-[#0d0d14] animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export default function AntigravityPage() {
  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Hero Header */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,58,237,0.08),transparent_60%)]" />
        <div className="relative max-w-7xl mx-auto px-4 pt-16 pb-8">
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center space-y-4"
          >
            <p className="text-[#7c3aed] text-sm font-mono tracking-widest uppercase">
              N=2 Broken Supergravity with Phase-Controlled Bimetric Coupling
            </p>
            <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
              <span className="text-[#00d4ff]">SUSY</span>{" "}
              <span className="text-white">Antigravity</span>
            </h1>
            <p className="text-gray-400 max-w-2xl mx-auto text-lg leading-relaxed">
              Interactive numerical verification of a supersymmetric gravitational coupling
              modulation mechanism. Explore the parameter space, run the verification suite,
              and examine the mathematical framework.
            </p>
            <div className="flex justify-center gap-6 text-xs font-mono text-gray-600 pt-2">
              <span>Mathematical Consistency: <span className="text-green-400">9/10</span></span>
              <span>Patentability: <span className="text-yellow-400">7/10</span></span>
              <span>Physical Reality: <span className="text-red-400">Speculative</span></span>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Simulator */}
      <div className="max-w-7xl mx-auto px-4 pb-20">
        <SUSYSimulator />
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 text-center text-xs text-gray-600 font-mono">
        <p>
          SUSY Antigravity Framework | Patent-Pending | QuantumAI Blockchain
        </p>
        <p className="mt-1">
          Mathematical verification only. Physical realizability is speculative.
          See whitepaper for full derivation.
        </p>
      </footer>
    </main>
  );
}
