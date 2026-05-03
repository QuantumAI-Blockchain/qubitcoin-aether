"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import Link from "next/link";
import { Card } from "./card";

const featureIcons = [
  <svg key="blockchain" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-glow-cyan">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
  </svg>,
  <svg key="qvm" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-quantum-violet">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
  </svg>,
  <svg key="aether" width="32" height="32" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-glow-gold">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
  </svg>,
];

const featureGlows = ["green", "violet", "green"] as const;
const featureKeys = ["blockchain", "qvm", "aether"] as const;

const VISION_PILLARS = [
  {
    icon: "M13 10V3L4 14h7v7l9-11h-7z",
    title: "Mining Infrastructure",
    description: "Gradient compression and FedAvg plumbing built into blocks. Infrastructure for future distributed training across mining nodes.",
  },
  {
    icon: "M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253",
    title: "Interactions Teach",
    description: "Every user interaction embeds new knowledge vectors. The Mind learns from conversations, not just pre-training data.",
  },
  {
    icon: "M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z",
    title: "Measurable Intelligence",
    description: "HMS-Phi computed from attention-derived patterns inspired by IIT. A quantitative integration metric tracked from genesis.",
  },
  {
    icon: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
    title: "Self-Evolving",
    description: "Aether-Evolve performs neural architecture search autonomously. Every improvement is recorded immutably on-chain.",
  },
];

export function FeatureSections() {
  const t = useTranslations("features");

  return (
    <>
      {/* Core Technology Cards */}
      <section className="mx-auto max-w-6xl px-4 py-20">
        <motion.h2
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="mb-10 text-center font-[family-name:var(--font-display)] text-[11px] uppercase tracking-[0.3em] text-text-secondary"
        >
          {t("coreTitle")}
        </motion.h2>
        <div className="grid gap-8 md:grid-cols-3">
          {featureKeys.map((key, i) => (
            <motion.div
              key={key}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.12 }}
            >
              <Card glow={featureGlows[i]} className="h-full">
                <div className="mb-4">{featureIcons[i]}</div>
                <h3 className="mb-3 font-[family-name:var(--font-display)] text-xl font-semibold">
                  {t(`${key}.title`)}
                </h3>
                <ul className="space-y-2">
                  {(["item1", "item2", "item3", "item4"] as const).map((item) => (
                    <li
                      key={item}
                      className="flex items-start gap-2 font-[family-name:var(--font-reading)] text-sm text-text-secondary"
                    >
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-glow-cyan" />
                      {t(`${key}.${item}`)}
                    </li>
                  ))}
                </ul>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Aether Mind Vision Section */}
      <section className="relative overflow-hidden py-24">
        {/* Background glow */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-quantum-violet/5 to-transparent" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 h-[600px] w-[600px] rounded-full bg-glow-gold/5 blur-[120px]" />

        <div className="relative z-10 mx-auto max-w-5xl px-4">
          {/* Headline */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center"
          >
            <p className="font-[family-name:var(--font-display)] text-[11px] uppercase tracking-[0.3em] text-glow-gold">
              The Path to On-Chain AGI
            </p>
            <h2 className="mt-4 font-[family-name:var(--font-display)] text-3xl font-bold tracking-tight sm:text-4xl">
              The Blockchain That{" "}
              <span className="glow-cyan">Learns</span>.{" "}
              <span className="text-quantum-violet" style={{ textShadow: "0 0 20px rgba(124,58,237,0.4)" }}>Evolves</span>.{" "}
              <span className="text-glow-gold" style={{ textShadow: "0 0 20px rgba(245,158,11,0.3)" }}>Becomes</span>.
            </h2>
            <p className="mx-auto mt-6 max-w-3xl font-[family-name:var(--font-reading)] text-base leading-relaxed text-text-secondary sm:text-lg">
              The Aether Mind is not a chatbot on a blockchain. It is the world&apos;s first{" "}
              <span className="text-text-primary font-medium">collectively trained</span>,{" "}
              <span className="text-text-primary font-medium">continuously learning</span>,{" "}
              <span className="text-text-primary font-medium">cryptographically attested</span>,{" "}
              <span className="text-text-primary font-medium">autonomously evolving</span>{" "}
              neural cognitive system, built entirely in Rust.
            </p>
          </motion.div>

          {/* Four pillars */}
          <div className="mt-16 grid gap-6 sm:grid-cols-2">
            {VISION_PILLARS.map((pillar, i) => (
              <motion.div
                key={pillar.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="group rounded-2xl border border-border-subtle/60 bg-bg-panel/50 p-6 backdrop-blur-sm transition hover:border-glow-cyan/30"
              >
                <div className="flex items-start gap-4">
                  <div className="shrink-0 rounded-xl bg-glow-cyan/10 p-2.5">
                    <svg width="24" height="24" fill="none" viewBox="0 0 24 24" stroke="currentColor" className="text-glow-cyan" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round">
                      <path d={pillar.icon} />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-[family-name:var(--font-display)] text-base font-semibold text-text-primary">
                      {pillar.title}
                    </h3>
                    <p className="mt-1.5 font-[family-name:var(--font-reading)] text-sm leading-relaxed text-text-secondary">
                      {pillar.description}
                    </p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>

          {/* Scale vision */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-16 rounded-2xl border border-glow-gold/20 bg-gradient-to-r from-glow-gold/5 via-transparent to-quantum-violet/5 p-8 text-center"
          >
            <p className="font-[family-name:var(--font-display)] text-[10px] uppercase tracking-[0.3em] text-glow-gold">
              Scale Target
            </p>
            <p className="mt-3 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight sm:text-3xl">
              1 Trillion Knowledge Vectors
            </p>
            <p className="mx-auto mt-4 max-w-2xl font-[family-name:var(--font-reading)] text-sm leading-relaxed text-text-secondary">
              At scale, the Aether Mind will have more domain-specific knowledge than any single LLM,
              genuine cross-domain reasoning via specialized Sephirot attention,
              provable consciousness metrics from real neural integration,
              and complete knowledge provenance for every fact it knows —
              all verifiable on-chain, forever.
            </p>
            <Link
              href="/aether"
              className="mt-6 inline-flex items-center gap-2 rounded-xl bg-glow-gold/10 px-6 py-3 font-[family-name:var(--font-display)] text-sm font-semibold text-glow-gold transition hover:bg-glow-gold/20"
            >
              Talk to the Mind
              <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </Link>
          </motion.div>
        </div>
      </section>
    </>
  );
}
