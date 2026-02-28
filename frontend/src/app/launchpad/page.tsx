import type { Metadata } from "next";
import { LaunchpadClient } from "./client";
import { ErrorBoundary } from "@/components/ui/error-boundary";

export const metadata: Metadata = {
  title: "Launchpad | Qubitcoin",
  description:
    "QBC Launchpad — deploy tokens, participate in presales, community due diligence, reputation staking, quality scoring, and ecosystem discovery. One-click quantum-secured token launches.",
};

export default function LaunchpadPage() {
  return (
    <ErrorBoundary>
      <LaunchpadClient />
    </ErrorBoundary>
  );
}
