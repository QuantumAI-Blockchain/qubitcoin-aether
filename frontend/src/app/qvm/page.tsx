"use client";

import { useQuery } from "@tanstack/react-query";
import { get } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { ContractBrowser } from "@/components/qvm/contract-browser";

interface QVMInfo {
  total_contracts: number;
  active_contracts: number;
  total_opcodes: number;
  quantum_opcodes: number;
  block_gas_limit: number;
}

export default function QVMPage() {
  const { data: qvm } = useQuery({
    queryKey: ["qvmInfo"],
    queryFn: () => get<QVMInfo>("/qvm/info"),
    refetchInterval: 30_000,
  });

  return (
    <div className="mx-auto max-w-6xl px-4 pt-20 pb-12">
      <h1 className="font-[family-name:var(--font-heading)] text-3xl font-bold">
        QVM Explorer
      </h1>
      <p className="mt-2 text-text-secondary">
        Quantum Virtual Machine — 155 EVM opcodes + 10 quantum extensions
      </p>

      {/* Stats */}
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <p className="text-xs text-text-secondary">Total Contracts</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-bold">
            {qvm?.total_contracts ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Active Contracts</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-bold text-quantum-green">
            {qvm?.active_contracts ?? "---"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Opcodes</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-bold">
            {qvm ? `${qvm.total_opcodes}+${qvm.quantum_opcodes}` : "165"}
          </p>
        </Card>
        <Card>
          <p className="text-xs text-text-secondary">Block Gas Limit</p>
          <p className="mt-1 font-[family-name:var(--font-mono)] text-2xl font-bold">
            {qvm?.block_gas_limit?.toLocaleString() ?? "30,000,000"}
          </p>
        </Card>
      </div>

      {/* Contract browser */}
      <div className="mt-8">
        <ErrorBoundary>
          <ContractBrowser />
        </ErrorBoundary>
      </div>

      {/* Deploy section */}
      <div className="mt-8">
        <Card>
          <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
            Deploy Contract
          </h3>
          <div className="space-y-4">
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                Contract Type
              </label>
              <select className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50">
                <option value="custom">Custom Bytecode</option>
                <option value="token">QBC-20 Token</option>
                <option value="nft">QBC-721 NFT</option>
                <option value="governance">Governance</option>
                <option value="escrow">Escrow</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                Bytecode (hex)
              </label>
              <textarea
                rows={4}
                placeholder="0x6080604052..."
                className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
              />
            </div>
            <button className="rounded-lg bg-quantum-violet px-6 py-2.5 text-sm font-semibold text-white transition hover:bg-quantum-violet/80">
              Deploy to QVM
            </button>
          </div>
        </Card>
      </div>

      {/* Quantum opcodes reference */}
      <div className="mt-8">
        <Card>
          <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
            Quantum Opcodes
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-surface-light text-left text-xs text-text-secondary">
                  <th className="pb-2 pr-4">Opcode</th>
                  <th className="pb-2 pr-4">Hex</th>
                  <th className="pb-2 pr-4">Gas</th>
                  <th className="pb-2">Description</th>
                </tr>
              </thead>
              <tbody className="font-[family-name:var(--font-mono)]">
                {[
                  { name: "QCREATE", hex: "0xF0", gas: "5,000+", desc: "Create quantum state (density matrix)" },
                  { name: "QMEASURE", hex: "0xF1", gas: "3,000", desc: "Measure / collapse quantum state" },
                  { name: "QENTANGLE", hex: "0xF2", gas: "10,000", desc: "Create entangled pair between contracts" },
                  { name: "QGATE", hex: "0xF3", gas: "2,000", desc: "Apply quantum gate to state" },
                  { name: "QVERIFY", hex: "0xF4", gas: "8,000", desc: "Verify quantum proof" },
                  { name: "QCOMPLIANCE", hex: "0xF5", gas: "15,000", desc: "KYC/AML/sanctions compliance check" },
                  { name: "QRISK", hex: "0xF6", gas: "5,000", desc: "Query SUSY risk score" },
                  { name: "QRISK_SYS", hex: "0xF7", gas: "10,000", desc: "Systemic risk / contagion model" },
                  { name: "QBRIDGE_ENT", hex: "0xF8", gas: "20,000", desc: "Cross-chain quantum entanglement" },
                  { name: "QBRIDGE_VER", hex: "0xF9", gas: "15,000", desc: "Cross-chain bridge proof verification" },
                ].map((op) => (
                  <tr key={op.name} className="border-b border-surface-light/50">
                    <td className="py-2 pr-4 text-quantum-green">{op.name}</td>
                    <td className="py-2 pr-4 text-quantum-violet">{op.hex}</td>
                    <td className="py-2 pr-4">{op.gas}</td>
                    <td className="py-2 font-[family-name:var(--font-body)] text-text-secondary">
                      {op.desc}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
    </div>
  );
}
