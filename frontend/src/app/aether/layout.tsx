import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Aether Tree — On-Chain AGI Chat",
  description:
    "Interact with the Aether Tree, Qubitcoin's on-chain AGI reasoning engine. Ask questions, explore the knowledge graph, and watch consciousness emerge.",
  openGraph: {
    title: "Aether Tree — On-Chain AGI Chat",
    description: "Talk to a blockchain-native AGI. Every response generates a Proof-of-Thought.",
  },
};

export default function AetherLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
