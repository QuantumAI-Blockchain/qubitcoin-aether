import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Aether Mind — On-Chain AI Chat",
  description:
    "Interact with Aether Mind, Qubitcoin's on-chain neural cognitive engine. Ask questions, explore the knowledge fabric, and watch consciousness metrics grow.",
  openGraph: {
    title: "Aether Mind — On-Chain AI Chat",
    description: "Talk to a blockchain-native AI. Every response generates a Proof-of-Thought.",
  },
};

export default function AetherLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
