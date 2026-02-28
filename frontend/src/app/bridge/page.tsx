import type { Metadata } from "next";
import { BridgeClient } from "./client";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export const metadata: Metadata = {
  title: "QBC Bridge",
  description:
    "Qubitcoin wrapped token bridge — wrap QBC and QUSD to Ethereum, BNB Smart Chain, and Solana. 100% vault-backed. Post-quantum secured.",
};

export default function BridgePage() {
  return (
    <ErrorBoundary>
      <BridgeClient />
    </ErrorBoundary>
  );
}
