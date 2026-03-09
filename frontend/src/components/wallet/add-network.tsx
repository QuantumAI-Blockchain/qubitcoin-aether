"use client";

import { useState } from "react";

const NETWORK_CONFIG = {
  chainId: "0xce7", // 3303
  chainName: "Quantum Blockchain",
  nativeCurrency: { name: "Qubitcoin", symbol: "QBC", decimals: 18 },
  rpcUrls: ["https://qbc.network/rpc"],
  blockExplorerUrls: ["https://qbc.network/explorer"],
};

const DISPLAY_ROWS = [
  { label: "Network Name", value: "Quantum Blockchain" },
  { label: "RPC URL", value: "https://qbc.network/rpc", mono: true },
  { label: "Chain ID", value: "3303" },
  { label: "Currency Symbol", value: "QBC" },
  { label: "Decimals", value: "18" },
  { label: "Block Explorer", value: "https://qbc.network/explorer", mono: true },
];

export function AddNetwork({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<"idle" | "adding" | "added" | "error">("idle");

  async function handleAddNetwork() {
    try {
      setStatus("adding");
      const eth = (window as any).ethereum;
      if (!eth) {
        setStatus("error");
        return;
      }
      await eth.request({
        method: "wallet_addEthereumChain",
        params: [NETWORK_CONFIG],
      });
      setStatus("added");
    } catch {
      setStatus("error");
    }
  }

  if (compact) {
    return (
      <button
        onClick={handleAddNetwork}
        className="rounded-lg bg-glow-cyan/20 px-4 py-2 text-sm font-semibold text-glow-cyan hover:bg-glow-cyan/30 transition-colors"
      >
        {status === "added" ? "Added!" : status === "adding" ? "Adding..." : "Add QBC to MetaMask"}
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
          Connect to Quantum Blockchain
        </h3>
        <span className="rounded bg-glow-cyan/20 px-2 py-0.5 text-[10px] font-medium text-glow-cyan">
          Chain ID: 3303
        </span>
      </div>

      <div className="mb-4 space-y-2">
        {DISPLAY_ROWS.map((row) => (
          <div key={row.label} className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2">
            <span className="text-xs text-text-secondary">{row.label}</span>
            <span className={`text-xs text-text-primary ${row.mono ? "font-mono" : ""}`}>
              {row.value}
            </span>
          </div>
        ))}
      </div>

      <button
        onClick={handleAddNetwork}
        disabled={status === "adding"}
        className="w-full rounded-lg bg-glow-cyan/20 px-4 py-3 text-sm font-bold text-glow-cyan hover:bg-glow-cyan/30 disabled:opacity-50 transition-colors"
      >
        {status === "added"
          ? "Network Added!"
          : status === "adding"
            ? "Adding..."
            : status === "error"
              ? "Add Manually (MetaMask not detected)"
              : "Add to MetaMask"}
      </button>

      <p className="mt-2 text-center text-[10px] text-text-secondary">
        Or add manually in MetaMask → Settings → Networks → Add Network
      </p>
    </div>
  );
}
