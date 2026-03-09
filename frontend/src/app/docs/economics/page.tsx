"use client";

import Link from "next/link";
import { ArrowLeft } from "lucide-react";

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

const eras = [
  { era: 0, reward: "15.27", years: "0 – 1.6", pctMined: "~6.0%" },
  { era: 1, reward: "9.44", years: "1.6 – 3.2", pctMined: "~9.7%" },
  { era: 2, reward: "5.83", years: "3.2 – 4.9", pctMined: "~12.0%" },
  { era: 3, reward: "3.60", years: "4.9 – 6.5", pctMined: "~13.4%" },
  { era: 4, reward: "2.23", years: "6.5 – 8.1", pctMined: "~14.3%" },
  { era: 5, reward: "1.38", years: "8.1 – 9.7", pctMined: "~14.8%" },
  { era: 10, reward: "0.14", years: "16.2 – 17.8", pctMined: "~15.5%" },
  { era: "11+", reward: "0.10 (tail)", years: "17.8+", pctMined: "→ 100%" },
];

const feeStructure = [
  { action: "L1 Transaction", fee: "SIZE × FEE_RATE (QBC/byte)", notes: "Miners select by fee density" },
  { action: "Chat Message", fee: "~$0.005 in QBC", notes: "Pegged via QUSD oracle" },
  { action: "Deep Reasoning", fee: "~$0.01 in QBC", notes: "2× chat fee multiplier" },
  { action: "Contract Deploy", fee: "1.0 + 0.1/KB QBC", notes: "Base + per-KB of bytecode" },
  { action: "Bridge Transfer", fee: "0.1% of amount", notes: "Configurable per chain" },
  { action: "First 5 Messages", fee: "Free", notes: "Onboarding free tier per session" },
];

export default function EconomicsPage() {
  return (
    <main
      className="min-h-screen p-6 md:p-12"
      style={{ background: C.bg, color: C.text, fontFamily: "Inter, system-ui, sans-serif" }}
    >
      <div className="mx-auto max-w-3xl">
        <Link
          href="/docs"
          className="mb-8 inline-flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          style={{ color: C.textMuted }}
        >
          <ArrowLeft size={14} />
          Back to Docs
        </Link>

        <h1 className="mb-2 text-3xl font-bold" style={{ fontFamily: "Space Grotesk, sans-serif" }}>
          Economics
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          Golden ratio emission, phi-halving, tail emission, and fee structure
        </p>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Core Constants
          </h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {[
              { label: "Max Supply", value: "3.3B QBC" },
              { label: "Golden Ratio (φ)", value: "1.618034" },
              { label: "Block Time", value: "3.3 seconds" },
              { label: "Initial Reward", value: "15.27 QBC" },
              { label: "Halving Interval", value: "15.47M blocks" },
              { label: "Genesis Premine", value: "33M QBC (1%)" },
              { label: "Tail Emission", value: "0.1 QBC/block" },
              { label: "Emission Period", value: "~2,770 years" },
              { label: "Chain ID", value: "3303" },
            ].map((c) => (
              <div key={c.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.primary }}>{c.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{c.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Phi-Halving Schedule
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Block rewards decrease by dividing by φ (1.618...) every 15,474,020 blocks (~1.618 years).
            Once the phi-halving reward drops below 0.1 QBC (at era 11), tail emission of 0.1 QBC/block
            ensures the full 3.3B supply is eventually mined over ~2,770 years.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Era</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Reward (QBC)</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Years</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Supply Mined</th>
                </tr>
              </thead>
              <tbody>
                {eras.map((e) => (
                  <tr key={String(e.era)} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono" style={{ color: C.secondary }}>{e.era}</td>
                    <td className="px-3 py-2 font-mono" style={{ color: C.primary }}>{e.reward}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{e.years}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.accent }}>{e.pctMined}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Fee Structure
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Action</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Fee</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Notes</th>
                </tr>
              </thead>
              <tbody>
                {feeStructure.map((f) => (
                  <tr key={f.action} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2" style={{ color: C.text }}>{f.action}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{f.fee}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{f.notes}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            QUSD Stablecoin
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            QUSD is a QBC-20 token on QVM with fractional reserve backing. Initial supply is 3.3B QUSD.
            Every mint creates a debt obligation, and every reserve deposit counts as partial payback.
            The system targets 100% backing over a 10-year period.
          </p>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {[
              { label: "Initial Supply", value: "3.3B QUSD" },
              { label: "Target Backing", value: "100% (10yr)" },
              { label: "Transfer Fee", value: "0.05% (mutable)" },
              { label: "Contracts", value: "7 Solidity" },
            ].map((s) => (
              <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.accent }}>{s.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Fee Pricing Modes
          </h2>
          <div className="space-y-2">
            {[
              { mode: "qusd_peg", desc: "Fees auto-adjust to USD target via QUSD oracle. Default mode.", active: true },
              { mode: "fixed_qbc", desc: "Fixed QBC amount. Fallback if QUSD oracle unavailable.", active: false },
              { mode: "direct_usd", desc: "USD target via external price feed. Emergency fallback.", active: false },
            ].map((m) => (
              <div key={m.mode} className="flex items-center gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <span
                  className="rounded-full px-2 py-0.5 text-xs font-mono"
                  style={{ background: m.active ? `${C.primary}20` : `${C.textMuted}20`, color: m.active ? C.primary : C.textMuted }}
                >
                  {m.mode}
                </span>
                <span className="text-xs" style={{ color: C.textMuted }}>{m.desc}</span>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
