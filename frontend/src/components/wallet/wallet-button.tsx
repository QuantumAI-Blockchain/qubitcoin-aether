"use client";

import { useState } from "react";
import { useWalletStore } from "@/stores/wallet-store";
import { connectWallet } from "@/lib/wallet";

export function WalletButton() {
  const { address, connected, connect, disconnect } = useWalletStore();
  const [error, setError] = useState<string | null>(null);

  async function handleConnect() {
    setError(null);
    try {
      const { address } = await connectWallet();
      connect(address);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Connection failed";
      setError(msg);
      console.error("Wallet connect failed:", err);
    }
  }

  if (connected && address) {
    return (
      <button
        onClick={disconnect}
        className="rounded-lg border border-glow-cyan/30 bg-bg-panel px-3 py-1.5 text-xs text-glow-cyan transition hover:bg-glow-cyan/10"
      >
        {address.slice(0, 6)}...{address.slice(-4)}
      </button>
    );
  }

  return (
    <div>
      <button
        onClick={handleConnect}
        className="rounded-lg bg-glow-cyan/10 px-3 py-1.5 text-xs font-medium text-glow-cyan transition hover:bg-glow-cyan/20"
      >
        Connect Wallet
      </button>
      {error && (
        <p className="mt-2 max-w-xs text-[10px] leading-relaxed text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
