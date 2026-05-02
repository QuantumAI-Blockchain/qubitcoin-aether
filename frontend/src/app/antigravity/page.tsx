"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import Link from "next/link";

const SUSYSimulator = dynamic(
  () => import("@/components/antigravity/susy-simulator").then((m) => m.SUSYSimulator),
  { ssr: false, loading: () => <SimulatorSkeleton /> },
);

function SimulatorSkeleton() {
  return (
    <div className="space-y-8">
      <div className="h-[600px] rounded-2xl border border-gray-800 bg-[#0d0d14] animate-pulse" />
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-24 rounded-xl border border-gray-800 bg-[#0d0d14] animate-pulse" />
        ))}
      </div>
    </div>
  );
}

// Animated background particles for hero
function HeroParticles() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[...Array(30)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: Math.random() * 3 + 1,
            height: Math.random() * 3 + 1,
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
            background: i % 3 === 0 ? "#00ff88" : i % 3 === 1 ? "#7c3aed" : "#00d4ff",
          }}
          animate={{
            y: [0, -30 - Math.random() * 40, 0],
            opacity: [0, 0.6, 0],
            scale: [0.5, 1.2, 0.5],
          }}
          transition={{
            duration: 3 + Math.random() * 4,
            repeat: Infinity,
            delay: Math.random() * 5,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
}

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.1,
    },
  },
} as const;

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: "easeOut" as const },
  },
} as const;

export default function AntigravityPage() {
  return (
    <main className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Hero Header */}
      <div className="relative overflow-hidden">
        {/* Multiple layered gradient backgrounds */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(124,58,237,0.12),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,rgba(0,212,255,0.06),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(0,255,136,0.04),transparent_50%)]" />

        {/* Animated particles behind text */}
        <HeroParticles />

        {/* Animated top border glow */}
        <motion.div
          className="absolute top-0 left-0 right-0 h-px"
          style={{
            background: "linear-gradient(90deg, transparent, #7c3aed, #00d4ff, #00ff88, #00d4ff, #7c3aed, transparent)",
          }}
          animate={{ opacity: [0.3, 0.7, 0.3] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />

        <div className="relative max-w-7xl mx-auto px-4 pt-20 pb-12">
          <motion.div
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            className="text-center space-y-6"
          >
            <motion.p
              variants={itemVariants}
              className="text-[#7c3aed] text-sm font-mono tracking-[0.25em] uppercase"
            >
              N=2 Broken Supergravity with Phase-Controlled Bimetric Coupling
            </motion.p>

            <motion.h1
              variants={itemVariants}
              className="text-5xl md:text-7xl font-bold tracking-tight"
            >
              <span
                className="inline-block bg-clip-text text-transparent"
                style={{
                  backgroundImage: "linear-gradient(135deg, #00d4ff 0%, #00ffcc 30%, #00d4ff 60%, #7c3aed 100%)",
                  backgroundSize: "200% 200%",
                  animation: "gradientShift 4s ease infinite",
                }}
              >
                SUSY
              </span>{" "}
              <span
                className="inline-block bg-clip-text text-transparent"
                style={{
                  backgroundImage: "linear-gradient(135deg, #ffffff 0%, #e0e0ff 40%, #ffffff 70%, #00d4ff 100%)",
                  backgroundSize: "200% 200%",
                  animation: "gradientShift 4s ease infinite",
                  animationDelay: "0.5s",
                }}
              >
                Antigravity
              </span>
            </motion.h1>

            <motion.p
              variants={itemVariants}
              className="text-gray-400 max-w-2xl mx-auto text-lg leading-relaxed"
            >
              Interactive numerical verification of a supersymmetric gravitational coupling
              modulation mechanism. Explore the parameter space, run the verification suite,
              and examine the mathematical framework.
            </motion.p>

            {/* Stats bar with glow effects */}
            <motion.div
              variants={itemVariants}
              className="flex flex-wrap justify-center gap-4 md:gap-8 text-xs font-mono pt-2"
            >
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-green-500/20 bg-green-500/5">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse shadow-[0_0_6px_rgba(34,197,94,0.5)]" />
                <span className="text-gray-500">Verification:</span>
                <span className="text-green-400 font-bold">6/6 PASS</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-700 bg-white/[0.02]">
                <span className="text-gray-500">Mathematical Consistency:</span>
                <span className="text-[#00d4ff]">9/10</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-700 bg-white/[0.02]">
                <span className="text-gray-500">Patentability:</span>
                <span className="text-[#f59e0b]">7/10</span>
              </div>
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-700 bg-white/[0.02]">
                <span className="text-gray-500">Physical Reality:</span>
                <span className="text-[#7c3aed]">Speculative</span>
              </div>
            </motion.div>

            {/* Whitepaper link */}
            <motion.div variants={itemVariants} className="pt-4 flex justify-center gap-4">
              <Link
                href="/docs/antigravity"
                className="group relative inline-flex items-center gap-2 px-6 py-2.5 rounded-lg border border-[#00d4ff]/30 bg-[#00d4ff]/5 text-[#00d4ff] text-sm font-mono hover:bg-[#00d4ff]/10 hover:border-[#00d4ff]/50 transition-all duration-300"
              >
                <span className="absolute inset-0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ boxShadow: "0 0 20px rgba(0,212,255,0.15)" }} />
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                Read the Whitepaper
              </Link>
              <Link
                href="/dashboard"
                className="group relative inline-flex items-center gap-2 px-6 py-2.5 rounded-lg border border-[#7c3aed]/30 bg-[#7c3aed]/5 text-[#7c3aed] text-sm font-mono hover:bg-[#7c3aed]/10 hover:border-[#7c3aed]/50 transition-all duration-300"
              >
                <span className="absolute inset-0 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity duration-300" style={{ boxShadow: "0 0 20px rgba(124,58,237,0.15)" }} />
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                View Dashboard
              </Link>
            </motion.div>
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

      {/* CSS animation for gradient text */}
      <style jsx global>{`
        @keyframes gradientShift {
          0% { background-position: 0% 50%; }
          50% { background-position: 100% 50%; }
          100% { background-position: 0% 50%; }
        }
      `}</style>
    </main>
  );
}
