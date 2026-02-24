import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Wallet",
  description:
    "Manage your QBC holdings with quantum-resistant security. Send, receive, stake on Sephirot nodes, and view transaction history.",
  openGraph: {
    title: "Qubitcoin Wallet",
    description: "Quantum-secure wallet with Dilithium2 signatures and Sephirot staking.",
  },
};

export default function WalletLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
