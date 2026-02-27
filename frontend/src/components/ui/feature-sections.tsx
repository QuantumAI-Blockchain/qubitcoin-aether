"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
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

export function FeatureSections() {
  const t = useTranslations("features");

  return (
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
  );
}
