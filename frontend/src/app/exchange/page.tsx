import type { Metadata } from "next";
import { ExchangeClient } from "./client";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export const metadata: Metadata = {
  title: "Exchange | Qubitcoin DEX",
  description:
    "Qubitcoin Decentralised Exchange — on-chain order book, spot + perpetuals, cross-chain deposits, quantum-secured settlement via CRYSTALS-Dilithium-3.",
};

export default function ExchangePage() {
  return (
    <ErrorBoundary>
      <ExchangeClient />
    </ErrorBoundary>
  );
}
