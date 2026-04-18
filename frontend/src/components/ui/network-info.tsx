"use client";

import { motion } from "framer-motion";

const NETWORK_DETAILS = [
  { label: "Network Name", value: "Quantum Blockchain" },
  { label: "RPC URL", value: "https://qbc.network/rpc", mono: true, copy: true },
  { label: "Chain ID", value: "3303", copy: true },
  { label: "Currency Symbol", value: "QBC" },
  { label: "Decimals", value: "8" },
  { label: "Block Explorer", value: "https://qbc.network/explorer", mono: true, copy: true },
];

const CHAIN_PARAMS = {
  chainId: "0xce7",
  chainName: "Quantum Blockchain",
  nativeCurrency: { name: "Qubitcoin", symbol: "QBC", decimals: 8 },
  rpcUrls: ["https://qbc.network/rpc"],
  blockExplorerUrls: ["https://qbc.network/explorer"],
};

function CopyButton({ text }: { text: string }) {
  return (
    <button
      onClick={() => navigator.clipboard.writeText(text)}
      className="ml-2 rounded px-1.5 py-0.5 text-[10px] text-text-secondary hover:bg-white/10 hover:text-text-primary transition-colors"
      title="Copy"
    >
      Copy
    </button>
  );
}

export function NetworkInfo() {
  async function handleAdd() {
    try {
      const eth = (window as any).ethereum;
      if (!eth) {
        alert("MetaMask not detected. Add the network manually using the details below.");
        return;
      }
      await eth.request({ method: "wallet_addEthereumChain", params: [CHAIN_PARAMS] });
    } catch {
      // user rejected or error
    }
  }

  return (
    <section className="mx-auto max-w-6xl px-4 py-16">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.5 }}
        className="rounded-2xl border border-glow-cyan/20 bg-gradient-to-b from-glow-cyan/5 to-transparent p-8"
      >
        <div className="flex flex-col items-center gap-6 md:flex-row md:items-start md:gap-12">
          {/* Left: Text + Button */}
          <div className="flex-1 text-center md:text-left">
            <h2 className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-text-primary">
              Connect to the Network
            </h2>
            <p className="mt-2 text-sm text-text-secondary leading-relaxed">
              Add Quantum Blockchain to MetaMask or any EVM-compatible wallet.
              One click or enter the details manually.
            </p>
            <button
              onClick={handleAdd}
              className="mt-5 inline-flex items-center gap-2 rounded-lg bg-glow-cyan/20 px-6 py-3 text-sm font-bold text-glow-cyan hover:bg-glow-cyan/30 transition-colors"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 5v14M5 12h14" />
              </svg>
              Add to MetaMask
            </button>
          </div>

          {/* Right: Network Details */}
          <div className="w-full max-w-sm space-y-1.5">
            {NETWORK_DETAILS.map((row) => (
              <div
                key={row.label}
                className="flex items-center justify-between rounded-lg bg-white/5 px-3 py-2"
              >
                <span className="text-xs text-text-secondary">{row.label}</span>
                <span className="flex items-center">
                  <span
                    className={`text-xs text-text-primary ${row.mono ? "font-mono" : ""}`}
                  >
                    {row.value}
                  </span>
                  {row.copy && <CopyButton text={row.value} />}
                </span>
              </div>
            ))}
          </div>
        </div>
      </motion.div>
    </section>
  );
}
