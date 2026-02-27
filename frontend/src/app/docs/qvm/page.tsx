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

const quantumOpcodes = [
  { opcode: "QCREATE", hex: "0xF0", gas: "5,000+", desc: "Create quantum state (density matrix)" },
  { opcode: "QMEASURE", hex: "0xF1", gas: "3,000", desc: "Measure quantum state (collapse)" },
  { opcode: "QENTANGLE", hex: "0xF2", gas: "10,000", desc: "Create entangled pair between contracts" },
  { opcode: "QGATE", hex: "0xF3", gas: "2,000", desc: "Apply quantum gate to state" },
  { opcode: "QVERIFY", hex: "0xF4", gas: "8,000", desc: "Verify quantum proof" },
  { opcode: "QCOMPLIANCE", hex: "0xF5", gas: "15,000", desc: "Check KYC/AML/sanctions compliance" },
  { opcode: "QRISK", hex: "0xF6", gas: "5,000", desc: "Query SUSY risk score for address" },
  { opcode: "QRISK_SYSTEMIC", hex: "0xF7", gas: "10,000", desc: "Query systemic risk (contagion)" },
  { opcode: "QBRIDGE_ENTANGLE", hex: "0xF8", gas: "20,000", desc: "Cross-chain quantum entanglement" },
  { opcode: "QBRIDGE_VERIFY", hex: "0xF9", gas: "15,000", desc: "Verify cross-chain bridge proof" },
  { opcode: "QREASON", hex: "0xFA", gas: "25,000", desc: "On-chain AGI reasoning query" },
  { opcode: "QPHI", hex: "0xFB", gas: "5,000", desc: "Query current consciousness Phi value" },
];

const features = [
  { name: "Quantum State Persistence (QSP)", desc: "Store quantum states as density matrices on-chain" },
  { name: "Entanglement-Based Communication (ESCC)", desc: "Zero-gas cross-contract state sync" },
  { name: "Programmable Compliance Policies (PCP)", desc: "VM-level KYC/AML/sanctions enforcement" },
  { name: "Real-Time Risk Assessment (RRAO)", desc: "SUSY field theory for financial contagion prediction" },
  { name: "Quantum-Verified Cross-Chain Proofs (QVCSP)", desc: "Instant trustless bridge verification" },
];

export default function QVMPage() {
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
          QVM Specification
        </h1>
        <p className="mb-8 text-sm" style={{ color: C.textMuted }}>
          Quantum Virtual Machine — 167 opcodes, compliance engine, plugin architecture
        </p>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Overview
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: C.textMuted }}>
            The QVM is a full EVM-compatible bytecode interpreter with quantum extensions and
            institutional-grade compliance features. It executes 155 standard EVM opcodes, 10 quantum
            opcodes for quantum state persistence, and 2 AGI opcodes for on-chain reasoning. The QVM
            supports Solidity smart contracts, QBC-20/QBC-721 token standards, and a plugin architecture
            for domain-specific functionality.
          </p>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Quantum Opcodes
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" style={{ borderColor: C.border }}>
              <thead>
                <tr style={{ borderBottom: `1px solid ${C.border}` }}>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Opcode</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Hex</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Gas</th>
                  <th className="px-3 py-2 text-left" style={{ color: C.text }}>Description</th>
                </tr>
              </thead>
              <tbody>
                {quantumOpcodes.map((op) => (
                  <tr key={op.hex} style={{ borderBottom: `1px solid ${C.border}22` }}>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.secondary }}>
                      {op.opcode}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs" style={{ color: C.textMuted }}>
                      {op.hex}
                    </td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.accent }}>
                      {op.gas}
                    </td>
                    <td className="px-3 py-2 text-xs" style={{ color: C.textMuted }}>
                      {op.desc}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Novel Features
          </h2>
          <div className="space-y-3">
            {features.map((f) => (
              <div key={f.name} className="rounded-lg border p-4" style={{ borderColor: C.border, background: C.surface }}>
                <h3 className="mb-1 text-sm font-semibold" style={{ color: C.text }}>{f.name}</h3>
                <p className="text-xs" style={{ color: C.textMuted }}>{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mb-8">
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Performance
          </h2>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {[
              { label: "Simple Transfer", value: "45,000 TPS" },
              { label: "ERC-20 Transfer", value: "12,000 TPS" },
              { label: "DeFi Swap", value: "3,500 TPS" },
              { label: "Finality", value: "< 1 second" },
            ].map((stat) => (
              <div key={stat.label} className="rounded-lg border p-3 text-center" style={{ borderColor: C.border, background: C.surface }}>
                <p className="text-lg font-bold" style={{ color: C.primary }}>{stat.value}</p>
                <p className="text-xs" style={{ color: C.textMuted }}>{stat.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h2 className="mb-3 text-xl font-semibold" style={{ color: C.primary, fontFamily: "Space Grotesk, sans-serif" }}>
            Contract Standards
          </h2>
          <ul className="space-y-2 text-sm" style={{ color: C.textMuted }}>
            <li><strong style={{ color: C.text }}>QBC-20:</strong> Fungible token standard (ERC-20 compatible)</li>
            <li><strong style={{ color: C.text }}>QBC-721:</strong> Non-fungible token standard (ERC-721 compatible)</li>
            <li><strong style={{ color: C.text }}>ERC-20-QC:</strong> Compliance-aware token standard (QVM-specific)</li>
          </ul>
        </section>
      </div>
    </main>
  );
}
