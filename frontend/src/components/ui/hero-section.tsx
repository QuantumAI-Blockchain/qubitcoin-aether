"use client";

import dynamic from "next/dynamic";
import { motion } from "framer-motion";
import Link from "next/link";
import { useTranslations } from "next-intl";

const ParticleField = dynamic(
  () => import("@/components/visualizations/particle-field").then((m) => m.ParticleField),
  { ssr: false },
);

export function HeroSection() {
  const t = useTranslations("hero");

  return (
    <section className="relative flex min-h-[85vh] items-center justify-center overflow-hidden pt-16">
      <ParticleField />

      <div className="relative z-10 mx-auto max-w-4xl px-4 text-center">
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7 }}
          className="font-[family-name:var(--font-display)] text-3xl font-bold leading-tight tracking-tight sm:text-5xl"
        >
          {t("heading1")} <span className="text-quantum-violet" style={{ textShadow: "0 0 20px rgba(124,58,237,0.4)" }}>{t("supersymmetric")}</span> {t("heading2")}{" "}
          <br className="hidden sm:block" />
          <span className="glow-cyan">{t("heading3")}</span> {t("heading4")}{" "}
          <br className="hidden sm:block" />
          {t("heading5")}
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.15 }}
          className="mx-auto mt-6 max-w-2xl font-[family-name:var(--font-reading)] text-lg text-text-secondary"
        >
          {t("subtitle")}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.3 }}
          className="mt-10 flex flex-wrap items-center justify-center gap-4"
        >
          <Link
            href="/aether"
            className="rounded-xl bg-glow-cyan px-6 py-3 font-[family-name:var(--font-display)] text-sm font-semibold text-bg-deep transition hover:bg-glow-cyan/80"
            style={{ boxShadow: "0 0 20px rgba(0,212,255,0.3), 0 0 60px rgba(0,212,255,0.1)" }}
          >
            {t("talkToAether")}
          </Link>
          <Link
            href="/dashboard"
            className="rounded-xl border border-quantum-violet/50 bg-quantum-violet/10 px-6 py-3 font-[family-name:var(--font-display)] text-sm font-semibold text-quantum-violet transition hover:bg-quantum-violet/20"
            style={{ boxShadow: "0 0 15px rgba(124,58,237,0.2)" }}
          >
            {t("openDashboard")}
          </Link>
          <Link
            href="/wallet"
            className="rounded-xl border border-border-subtle px-6 py-3 font-[family-name:var(--font-display)] text-sm font-semibold text-text-secondary transition hover:border-glow-cyan/30 hover:text-glow-cyan"
          >
            {t("connectWallet")}
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
