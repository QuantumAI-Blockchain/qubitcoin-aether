import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Aether Tree — On-Chain AI Chat",
  description:
    "Interact with the Aether Tree, Qubitcoin's on-chain AI reasoning engine. Ask questions, explore the knowledge graph, and watch integration metrics grow.",
  openGraph: {
    title: "Aether Tree — On-Chain AI Chat",
    description: "Talk to a blockchain-native AI. Every response generates a Proof-of-Thought.",
  },
};

export default function AetherLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
