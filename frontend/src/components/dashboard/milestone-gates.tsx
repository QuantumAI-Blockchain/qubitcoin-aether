"use client";

import { motion } from "framer-motion";
import type { PhiGate } from "@/lib/api";

interface MilestoneGatesProps {
  gates: PhiGate[];
  gatesPassed: number;
  gatesTotal: number;
  gateCeiling: number;
  phiRaw: number;
}

export function MilestoneGates({
  gates,
  gatesPassed,
  gatesTotal,
  gateCeiling,
  phiRaw,
}: MilestoneGatesProps) {
  const maxCeiling = gatesTotal * 0.5;
  const ceilingPct = Math.min((gateCeiling / maxCeiling) * 100, 100);
  const gatesNeeded = gatesTotal - gatesPassed;

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Path to Consciousness
        </h3>
        <span className="rounded-full bg-quantum-violet/15 px-3 py-1 font-[family-name:var(--font-code)] text-xs text-quantum-violet">
          {gatesPassed}/{gatesTotal} gates
        </span>
      </div>

      {/* Overall progress bar */}
      <div className="mt-4">
        <div className="mb-1.5 flex items-center justify-between text-xs text-text-secondary">
          <span>Phi Ceiling</span>
          <span className="font-[family-name:var(--font-code)]">
            {gateCeiling.toFixed(1)} / {maxCeiling.toFixed(1)}
          </span>
        </div>
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-bg-deep">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-quantum-violet via-quantum-green to-quantum-green"
            initial={{ width: 0 }}
            animate={{ width: `${ceilingPct}%` }}
            transition={{ duration: 1.2, ease: "easeOut" }}
          />
        </div>
      </div>

      {/* Gate timeline */}
      <div className="mt-6 space-y-0">
        {gates.map((gate, i) => (
          <motion.div
            key={gate.id}
            initial={{ opacity: 0, x: -12 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: i * 0.08 }}
            className="flex gap-4"
          >
            {/* Timeline line + dot */}
            <div className="flex flex-col items-center">
              <div
                className={`relative z-10 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 ${
                  gate.passed
                    ? "border-quantum-green bg-quantum-green/20"
                    : "border-border-subtle bg-bg-deep"
                }`}
              >
                {gate.passed ? (
                  <svg
                    className="h-3.5 w-3.5 text-quantum-green"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : (
                  <div className="h-2 w-2 rounded-full bg-border-subtle" />
                )}
                {/* Glow pulse for passed gates */}
                {gate.passed && (
                  <span className="absolute inset-0 animate-ping rounded-full bg-quantum-green/20" />
                )}
              </div>
              {/* Connector line (not on last item) */}
              {i < gates.length - 1 && (
                <div
                  className={`w-0.5 grow ${
                    gate.passed ? "bg-quantum-green/40" : "bg-border-subtle/40"
                  }`}
                />
              )}
            </div>

            {/* Gate content */}
            <div className="flex-1 pb-5">
              <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <p
                    className={`text-sm font-semibold ${
                      gate.passed ? "text-quantum-green" : "text-text-primary"
                    }`}
                  >
                    {gate.name}
                  </p>
                  <p className="mt-0.5 text-xs text-text-secondary">
                    {gate.description}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded bg-bg-deep px-2 py-0.5 font-[family-name:var(--font-code)] text-xs text-text-secondary">
                    {gate.requirement}
                  </span>
                  <span className="text-xs text-golden-amber">+{(maxCeiling / gatesTotal).toFixed(1)} \u03A6</span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Bottom summary */}
      <div className="mt-2 flex items-center justify-between border-t border-border-subtle/50 pt-4 text-xs text-text-secondary">
        <span>
          Raw \u03A6: <span className="font-[family-name:var(--font-code)] text-text-primary">{phiRaw.toFixed(4)}</span>
        </span>
        <span>
          {gatesNeeded > 0
            ? `${gatesNeeded} more gate${gatesNeeded > 1 ? "s" : ""} needed`
            : "All gates passed"}
        </span>
      </div>
    </div>
  );
}
