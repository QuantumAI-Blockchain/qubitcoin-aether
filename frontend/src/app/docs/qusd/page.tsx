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

const contracts = [
  { name: "QUSD.sol", purpose: "Core QBC-20 stablecoin token with 0.05% transfer fee, mint/burn, pause", grade: "B" },
  { name: "QUSDReserve.sol", purpose: "Multi-asset reserve vault with deposit, withdrawal, and per-asset oracle integration", grade: "B" },
  { name: "QUSDDebtLedger.sol", purpose: "Immutable on-chain debt tracking with milestone events at 5/15/30/50/100% backing", grade: "A" },
  { name: "QUSDOracle.sol", purpose: "Multi-source price feed using median aggregation with staleness detection", grade: "B" },
  { name: "QUSDStabilizer.sol", purpose: "Peg stability mechanism with configurable bands, buy/sell operations, and keeper pattern", grade: "B" },
  { name: "QUSDAllocation.sol", purpose: "Four-tier vesting and distribution for initial 3.3B QUSD allocation", grade: "A" },
  { name: "QUSDGovernance.sol", purpose: "Proposal/vote/execute governance with 48-hour timelock and emergency multi-sig", grade: "B" },
];

const keeperModes = [
  { mode: "off", desc: "Daemon disabled. No monitoring, no actions.", active: false },
  { mode: "scan", desc: "Monitor prices and emit signals only. No execution. Default mode.", active: true },
  { mode: "periodic", desc: "Check every N blocks. Execute stabilization if depeg detected.", active: false },
  { mode: "continuous", desc: "Real-time monitoring. Execute immediately on depeg signal.", active: false },
  { mode: "aggressive", desc: "All arb opportunities pursued. Max trade size. Emergency depeg defense.", active: false },
];

const crossChainDexes = [
  { chain: "Ethereum", dex: "Uniswap V3", protocol: "TWAP oracle" },
  { chain: "BNB Chain", dex: "PancakeSwap V3", protocol: "TWAP oracle" },
  { chain: "Solana", dex: "Raydium", protocol: "AMM pools" },
  { chain: "Avalanche", dex: "Trader Joe V2", protocol: "LB pools" },
  { chain: "Polygon", dex: "QuickSwap V3", protocol: "TWAP oracle" },
  { chain: "Arbitrum", dex: "Camelot V3", protocol: "TWAP oracle" },
  { chain: "Optimism", dex: "Velodrome", protocol: "AMM pools" },
  { chain: "Base", dex: "Aerodrome", protocol: "AMM pools" },
];

export default function QUSDPage() {
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
          QUSD Stablecoin
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          QBC-20 stablecoin pegged to $1 USD with fractional reserve backing and cross-chain availability
        </p>

        {/* Overview */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Overview
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            QUSD is a QBC-20 stablecoin deployed on the QVM, pegged to $1 USD. It uses a fractional reserve
            model that targets 100% backing over a 10-year period. Every QUSD mint creates a debt obligation
            tracked immutably on-chain via the DebtLedger contract. Reserve deposits count as partial payback,
            creating a transparent path from fractional to full backing. The system includes multi-collateral
            support, flash loans, multi-source oracle price feeds with median aggregation, and automated peg
            defense via the Keeper daemon.
          </p>
        </section>

        {/* Key Stats Grid */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Key Stats
          </h2>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {[
              { label: "Initial Supply", value: "3.3B QUSD" },
              { label: "Target Peg", value: "$1 USD" },
              { label: "Reserve Model", value: "Fractional \u2192 Full" },
              { label: "Backing Timeline", value: "10 years" },
              { label: "Contracts", value: "7 Solidity" },
              { label: "Transfer Fee", value: "0.05% (mutable)" },
            ].map((c) => (
              <div key={c.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.accent }}>{c.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{c.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* How It Works */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            How It Works
          </h2>
          <div className="space-y-2">
            {[
              "Every QUSD mint creates a debt obligation recorded immutably in the DebtLedger contract.",
              "Reserve deposits (multi-asset) count as partial payback, reducing outstanding debt over time.",
              "Debt milestones are tracked on-chain at 5%, 15%, 30%, 50%, and 100% backing levels.",
              "The Stabilizer contract maintains the peg via automated buy/sell operations within configurable bands.",
              "Multi-source oracle uses median aggregation to resist price manipulation.",
            ].map((item, i) => (
              <div key={i} className="flex items-start gap-3 rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <span className="mt-0.5 text-xs font-mono font-bold" style={{ color: C.secondary }}>{i + 1}</span>
                <span className="text-sm" style={{ color: C.textMuted }}>{item}</span>
              </div>
            ))}
          </div>
        </section>

        {/* QUSD Contracts Table */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            QUSD Contracts
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            7 audited Solidity contracts (overall grade B+). All use Solidity 0.8.24 with proxy-compatible initialization.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Contract</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Purpose</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Grade</th>
                </tr>
              </thead>
              <tbody>
                {contracts.map((c) => (
                  <tr key={c.name} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{c.name}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{c.purpose}</td>
                    <td className="px-3 py-2 font-mono font-bold" style={{ color: c.grade === "A" ? C.primary : C.accent }}>{c.grade}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* Peg Keeper Daemon */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Peg Keeper Daemon
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Automated daemon that monitors wQUSD prices across 8 chains and executes stabilization
            actions when the peg deviates beyond configured thresholds (default: $0.99 floor, $1.01 ceiling).
          </p>
          <div className="space-y-2">
            {keeperModes.map((m) => (
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

        {/* Cross-Chain (wQUSD) */}
        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Cross-Chain (wQUSD)
          </h2>
          <p className="mb-4 text-sm" style={{ color: C.textMuted }}>
            Wrapped QUSD (wQUSD) is available across 8 chains via lock-and-mint bridging. Each wQUSD is 1:1
            backed by locked QUSD on the QBC chain. Bridge fee is 0.1% (10 bps), configurable up to a 10% hard cap
            via BridgeVault governance. The Keeper daemon monitors cross-chain prices for arbitrage opportunities.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Chain</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>DEX</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Protocol</th>
                </tr>
              </thead>
              <tbody>
                {crossChainDexes.map((d) => (
                  <tr key={d.chain} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2" style={{ color: C.text }}>{d.chain}</td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.primary }}>{d.dex}</td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>{d.protocol}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {[
              { label: "Bridge Fee", value: "0.1% (configurable)" },
              { label: "Backing", value: "1:1 locked QUSD" },
              { label: "Decimals", value: "8" },
              { label: "Chains Supported", value: "8 networks" },
            ].map((s) => (
              <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.secondary }}>{s.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* Revenue to Investors */}
        <section>
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Revenue to Investors
          </h2>
          <p className="mb-4 text-sm leading-relaxed" style={{ color: C.textMuted }}>
            10% of all QUSD-related fees flow to the investor revenue pool as a recurring, lifetime revenue share.
            This includes transfer fees (0.05% on every QUSD transfer), bridge fees (0.1% on every wQUSD
            wrap/unwrap), stabilization fees from Keeper operations, and flash loan fees. Revenue is distributed
            proportionally to investor pool participants and accrues automatically on-chain.
          </p>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Investor Share", value: "10% of all fees" },
              { label: "Duration", value: "Lifetime (recurring)" },
              { label: "Distribution", value: "On-chain, automatic" },
              { label: "Fee Sources", value: "Transfers, bridges, stabilization, flash loans" },
            ].map((s) => (
              <div key={s.label} className="rounded border p-3" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-sm font-bold" style={{ color: C.accent }}>{s.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{s.label}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
