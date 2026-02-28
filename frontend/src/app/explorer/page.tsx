import type { Metadata } from "next";
import { ExplorerClient } from "./client";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export const metadata: Metadata = {
  title: "Block Explorer",
  description:
    "Qubitcoin quantum blockchain explorer — blocks, transactions, QVM contracts, AetherTree topology, SUSY leaderboard, and cross-block pathfinder.",
};

export default function ExplorerPage() {
  return (
    <ErrorBoundary>
      <ExplorerClient />
    </ErrorBoundary>
  );
}
