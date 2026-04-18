"use client";

import { useState, useEffect } from "react";
import { isMobile, hasInjectedProvider } from "@/lib/wallet";

const NETWORK_CONFIG = {
  chainId: "0xce7", // 3303
  chainName: "Quantum Blockchain",
  nativeCurrency: { name: "Qubitcoin", symbol: "QBC", decimals: 8 },
  rpcUrls: ["https://qbc.network/rpc"],
  blockExplorerUrls: ["https://qbc.network/explorer"],
};

const DISPLAY_ROWS = [
  { label: "Network Name", value: "Quantum Blockchain" },
  { label: "RPC URL", value: "https://qbc.network/rpc", mono: true },
  { label: "Chain ID", value: "3303" },
  { label: "Currency Symbol", value: "QBC" },
  { label: "Decimals", value: "8" },
  { label: "Block Explorer", value: "https://qbc.network/explorer", mono: true },
];

export function AddNetwork({ compact = false }: { compact?: boolean }) {
  const [status, setStatus] = useState<"idle" | "adding" | "added" | "error">("idle");
  const [mobile, setMobile] = useState(false);
  const [hasProvider, setHasProvider] = useState(true);

  useEffect(() => {
    setMobile(isMobile());
    setHasProvider(hasInjectedProvider());
  }, []);

  async function handleAddNetwork() {
    try {
      setStatus("adding");
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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

  // On mobile without provider, show manual config info (no button to call ethereum)
  const showManualOnly = mobile && !hasProvider;

  if (compact) {
    if (showManualOnly) {
      return (
        <p className="text-xs text-text-secondary text-center">
          Add QBC network manually in MetaMask: Chain ID 3303, RPC: qbc.network/rpc
        </p>
      );
    }
    return (
      <button
        onClick={handleAddNetwork}
        className="rounded-lg bg-glow-cyan/20 px-4 py-3 text-sm font-semibold text-glow-cyan hover:bg-glow-cyan/30 transition-colors active:scale-[0.98] min-h-[44px]"
      >
        {status === "added" ? "Added!" : status === "adding" ? "Adding..." : "Add QBC to MetaMask"}
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-4 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-2">
        <h3 className="font-[family-name:var(--font-display)] text-xs font-bold uppercase tracking-widest text-text-secondary sm:text-sm">
          {showManualOnly ? "Manual Network Config" : "Connect to Quantum Blockchain"}
        </h3>
        <span className="rounded bg-glow-cyan/20 px-2 py-0.5 text-[10px] font-medium text-glow-cyan flex-shrink-0">
          Chain ID: 3303
        </span>
      </div>

      <div className="mb-4 space-y-1.5 sm:space-y-2">
        {DISPLAY_ROWS.map((row) => (
          <div key={row.label} className="flex items-center justify-between gap-2 rounded-lg bg-white/5 px-3 py-2">
            <span className="text-[11px] text-text-secondary flex-shrink-0 sm:text-xs">{row.label}</span>
            <span className={`text-[11px] text-text-primary text-right truncate sm:text-xs ${row.mono ? "font-mono" : ""}`}>
              {row.value}
            </span>
          </div>
        ))}
      </div>

      {!showManualOnly && (
        <button
          onClick={handleAddNetwork}
          disabled={status === "adding"}
          className="w-full rounded-lg bg-glow-cyan/20 px-4 py-3.5 text-sm font-bold text-glow-cyan hover:bg-glow-cyan/30 disabled:opacity-50 transition-colors active:scale-[0.98] min-h-[48px]"
        >
          {status === "added"
            ? "Network Added!"
            : status === "adding"
              ? "Adding..."
              : status === "error"
                ? "Retry — Add to MetaMask"
                : "Add to MetaMask"}
        </button>
      )}

      <p className="mt-2 text-center text-[10px] text-text-secondary sm:text-[11px]">
        {showManualOnly
          ? "Copy these values into MetaMask: Settings → Networks → Add Network"
          : "Or add manually in MetaMask → Settings → Networks → Add Network"}
      </p>
    </div>
  );
}
