"use client";

import { useQuery } from "@tanstack/react-query";
import { investorApi } from "@/lib/investor-api";
import type { TreasuryInfo } from "@/lib/investor-api";

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function shortenAddr(addr: string): string {
  if (!addr) return "";
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

const TOKEN_COLORS: Record<string, string> = {
  ETH: "text-violet-400",
  USDC: "text-blue-400",
  USDT: "text-green-400",
  DAI: "text-yellow-400",
};

export function TreasuryLive() {
  const { data: treasury, isLoading } = useQuery<TreasuryInfo>({
    queryKey: ["investor-treasury"],
    queryFn: () => investorApi.getTreasury(),
    refetchInterval: 30000,
  });

  if (isLoading || !treasury) {
    return (
      <div className="rounded-xl border border-border-subtle bg-bg-panel p-6 text-center text-text-secondary">
        Loading treasury data...
      </div>
    );
  }

  const totalUsd = parseFloat(treasury.total_raised_usd || "0");
  const balances = treasury.balances || {};

  return (
    <div className="rounded-xl border border-border-subtle bg-bg-panel p-6">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-sm font-bold uppercase tracking-widest text-text-secondary">
          Treasury — Live On-Chain
        </h3>
        <a
          href={treasury.etherscan_url}
          target="_blank"
          rel="noopener noreferrer"
          className="rounded bg-blue-500/20 px-2 py-1 text-[10px] font-medium text-blue-400 hover:bg-blue-500/30 transition-colors"
        >
          Etherscan &rarr;
        </a>
      </div>

      {/* Total raised */}
      <div className="mb-4 rounded-lg bg-glow-gold/10 border border-glow-gold/20 px-4 py-3 text-center">
        <div className="text-xs text-text-secondary">Total Raised</div>
        <div className="font-mono text-2xl font-bold text-glow-gold">
          ${totalUsd.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </div>
      </div>

      {/* Token balances */}
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {Object.entries(balances).map(([symbol, bal]) => {
          const amount = parseFloat(bal.amount);
          const usd = parseFloat(bal.usd_value);
          if (amount === 0 && symbol !== "ETH") return null;
          return (
            <div key={symbol} className="rounded-lg bg-white/5 px-3 py-2">
              <div className="text-xs text-text-secondary">{symbol}</div>
              <div className={`font-mono text-sm font-bold ${TOKEN_COLORS[symbol] || "text-text-primary"}`}>
                {symbol === "ETH" ? parseFloat(bal.amount).toFixed(4) : parseFloat(bal.amount).toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
              <div className="text-[10px] text-text-secondary">
                ${usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}
              </div>
            </div>
          );
        })}
        {treasury.eth_price_usd && (
          <div className="rounded-lg bg-white/5 px-3 py-2">
            <div className="text-xs text-text-secondary">ETH Price</div>
            <div className="font-mono text-sm font-bold text-text-primary">
              ${parseFloat(treasury.eth_price_usd).toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
            <div className="text-[10px] text-text-secondary">Chainlink</div>
          </div>
        )}
      </div>

      {/* Address */}
      <div className="mb-4 rounded-lg bg-white/5 px-3 py-2">
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-secondary">Treasury Address</span>
          <a
            href={treasury.etherscan_url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-xs text-glow-cyan hover:underline"
          >
            {treasury.address}
          </a>
        </div>
      </div>

      {/* Transaction feed */}
      {treasury.transactions.length > 0 && (
        <div>
          <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-text-secondary">
            Incoming Investments
          </h4>
          <div className="max-h-72 overflow-y-auto space-y-1">
            {treasury.transactions.map((tx) => (
              <a
                key={tx.hash}
                href={tx.etherscan_url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between rounded-lg px-3 py-2 text-xs hover:bg-white/5 transition-colors"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-text-primary">
                    {shortenAddr(tx.from)}
                  </span>
                  <span className="text-text-secondary">&rarr;</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`font-mono font-bold ${TOKEN_COLORS[tx.token] || "text-text-primary"}`}>
                    {tx.token === "ETH" ? parseFloat(tx.amount).toFixed(4) : parseFloat(tx.amount).toLocaleString(undefined, { maximumFractionDigits: 2 })} {tx.token}
                  </span>
                  {parseFloat(tx.usd_value) > 0 && (
                    <span className="text-text-secondary">
                      (${parseFloat(tx.usd_value).toLocaleString(undefined, { maximumFractionDigits: 2 })})
                    </span>
                  )}
                  <span className="text-text-secondary w-12 text-right">
                    {tx.timestamp > 0 ? timeAgo(tx.timestamp) : ""}
                  </span>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {treasury.transactions.length === 0 && (
        <p className="text-center text-xs text-text-secondary py-2">
          No incoming transactions yet. Be the first investor.
        </p>
      )}

      <p className="mt-3 text-[10px] text-text-secondary text-center italic">
        All data pulled live from Ethereum mainnet. ETH + USDC + USDT + DAI accepted. Fully verifiable on Etherscan.
      </p>
    </div>
  );
}
