import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "QVM Explorer",
  description:
    "Browse, deploy, and interact with smart contracts on the Quantum Virtual Machine. 155 EVM + 10 quantum + 2 AI opcodes.",
  openGraph: {
    title: "QVM Explorer — Quantum Virtual Machine",
    description: "EVM-compatible smart contract explorer with quantum opcode extensions.",
  },
};

export default function QVMLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
