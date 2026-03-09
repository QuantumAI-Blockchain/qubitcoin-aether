"use client";

import Link from "next/link";
import { motion } from "framer-motion";

export function PrivacyBanner() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="relative overflow-hidden rounded-2xl border border-quantum-violet/20 bg-gradient-to-br from-quantum-violet/10 via-transparent to-glow-cyan/5 p-8 md:p-12"
      >
        {/* Decorative grid */}
        <div className="pointer-events-none absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage:
              "linear-gradient(rgba(124,58,237,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(124,58,237,0.5) 1px, transparent 1px)",
            backgroundSize: "40px 40px",
          }}
        />

        <div className="relative flex flex-col items-center gap-6 text-center md:flex-row md:text-left md:gap-10">
          {/* Shield icon */}
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl border border-quantum-violet/30 bg-quantum-violet/10">
            <svg
              width="36"
              height="36"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-quantum-violet"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M9 12l2 2 4-4" />
            </svg>
          </div>

          {/* Text */}
          <div className="flex-1">
            <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-text-primary">
              Privacy-First Transactions
            </h2>
            <p className="mt-2 max-w-xl text-sm leading-relaxed text-text-secondary">
              SUSY Swaps provide opt-in confidential transactions with Pedersen commitments,
              Bulletproofs range proofs, and stealth addresses. Hide amounts and addresses
              while maintaining full cryptographic verifiability. Your choice, every transaction.
            </p>
          </div>

          {/* CTA */}
          <Link
            href="/wallet"
            className="group inline-flex shrink-0 items-center gap-2.5 rounded-xl border border-quantum-violet/30 bg-quantum-violet/15 px-7 py-3.5 font-[family-name:var(--font-display)] text-sm font-bold text-quantum-violet transition-all hover:border-quantum-violet/50 hover:bg-quantum-violet/25"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="transition-transform group-hover:-translate-y-0.5"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            </svg>
            SUSY Swap Wallet
          </Link>
        </div>
      </motion.div>
    </section>
  );
}
