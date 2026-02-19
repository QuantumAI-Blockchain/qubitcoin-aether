"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { get, post } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";

/* --- Types --- */

interface TokenInfo {
  address: string;
  name: string;
  symbol: string;
  decimals: number;
  total_supply: string;
}

interface TokenBalance {
  token_address: string;
  symbol: string;
  balance: string;
  decimals: number;
}

/* --- Helpers --- */

function formatTokenAmount(raw: string, decimals: number): string {
  const num = Number(raw);
  if (Number.isNaN(num)) return raw;
  const val = num / 10 ** decimals;
  if (val >= 1_000_000) return `${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `${(val / 1_000).toFixed(2)}K`;
  return val.toLocaleString(undefined, { maximumFractionDigits: decimals > 4 ? 4 : decimals });
}

function truncateAddr(addr: string, len = 6): string {
  if (addr.length <= len * 2 + 2) return addr;
  return `${addr.slice(0, len + 2)}...${addr.slice(-len)}`;
}

/* --- Component --- */

export function TokenManager() {
  const { address } = useWalletStore();
  const [sendToken, setSendToken] = useState<string | null>(null);
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState("");
  const [sending, setSending] = useState(false);
  const [sendResult, setSendResult] = useState<string | null>(null);
  const [lookupAddr, setLookupAddr] = useState("");
  const [lookupSearch, setLookupSearch] = useState("");

  // Fetch token balances for connected wallet
  const { data: balances, isLoading } = useQuery({
    queryKey: ["tokenBalances", address],
    queryFn: () =>
      get<{ tokens: TokenBalance[] }>(`/qvm/tokens/${address}`),
    enabled: !!address,
    refetchInterval: 15_000,
    retry: false,
  });

  // Fetch token info for lookup
  const { data: tokenInfo, isError: lookupError } = useQuery({
    queryKey: ["tokenInfo", lookupSearch],
    queryFn: () => get<TokenInfo>(`/qvm/token/${lookupSearch}`),
    enabled: !!lookupSearch,
    retry: false,
  });

  async function handleSend() {
    if (!sendToken || !recipient.trim() || !amount.trim()) return;
    setSending(true);
    setSendResult(null);
    try {
      const res = await post<{ txid: string }>("/qvm/token/transfer", {
        token: sendToken,
        from: address,
        to: recipient.trim(),
        amount: amount.trim(),
      });
      setSendResult(`Transfer sent: ${res.txid.slice(0, 20)}...`);
      setRecipient("");
      setAmount("");
    } catch (err) {
      setSendResult(
        err instanceof Error ? err.message : "Transfer failed",
      );
    } finally {
      setSending(false);
    }
  }

  const tokens = balances?.tokens ?? [];

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
        QBC-20 Tokens
      </h3>

      {/* Token balances */}
      {!address && (
        <p className="text-sm text-text-secondary">
          Connect your wallet to view token balances.
        </p>
      )}

      {address && isLoading && (
        <p className="text-sm text-text-secondary">Loading tokens...</p>
      )}

      {address && !isLoading && tokens.length === 0 && (
        <p className="text-sm text-text-secondary">No QBC-20 tokens found.</p>
      )}

      {tokens.length > 0 && (
        <div className="space-y-3">
          {tokens.map((t) => (
            <div
              key={t.token_address}
              className="flex items-center justify-between rounded-lg bg-void px-4 py-3"
            >
              <div>
                <p className="text-sm font-semibold text-text-primary">
                  {t.symbol}
                </p>
                <p className="font-[family-name:var(--font-mono)] text-xs text-text-secondary">
                  {truncateAddr(t.token_address)}
                </p>
              </div>
              <div className="text-right">
                <p className="font-[family-name:var(--font-mono)] text-sm font-semibold text-quantum-green">
                  {formatTokenAmount(t.balance, t.decimals)}
                </p>
                <button
                  onClick={() =>
                    setSendToken(
                      sendToken === t.token_address ? null : t.token_address,
                    )
                  }
                  className="mt-1 text-xs text-quantum-violet hover:text-quantum-violet/80"
                >
                  {sendToken === t.token_address ? "Cancel" : "Send"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Send panel */}
      {sendToken && (
        <div className="mt-4 space-y-3 rounded-lg border border-surface-light bg-void/50 p-4">
          <p className="text-xs font-medium text-quantum-violet">
            Sending: {truncateAddr(sendToken)}
          </p>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Recipient
            </label>
            <input
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="0x..."
              className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Amount
            </label>
            <input
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="0"
              type="number"
              className="w-full rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <button
            onClick={handleSend}
            disabled={sending || !recipient.trim() || !amount.trim()}
            className="rounded-lg bg-quantum-violet px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-40"
          >
            {sending ? "Sending..." : "Send Tokens"}
          </button>
          {sendResult && (
            <p className="text-xs text-text-secondary">{sendResult}</p>
          )}
        </div>
      )}

      {/* Token lookup */}
      <div className="mt-6 border-t border-surface-light pt-4">
        <h4 className="mb-3 text-sm font-semibold text-text-secondary">
          Token Lookup
        </h4>
        <div className="flex gap-3">
          <input
            value={lookupAddr}
            onChange={(e) => setLookupAddr(e.target.value)}
            placeholder="Token contract address (0x...)"
            className="flex-1 rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-xs text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
          <button
            onClick={() => setLookupSearch(lookupAddr.trim())}
            disabled={!lookupAddr.trim()}
            className="rounded-lg bg-quantum-green/20 px-5 py-2.5 text-sm font-medium text-quantum-green transition hover:bg-quantum-green/30 disabled:opacity-40"
          >
            Lookup
          </button>
        </div>

        {lookupError && lookupSearch && (
          <p className="mt-3 text-sm text-red-400">Token not found.</p>
        )}

        {tokenInfo && (
          <div className="mt-3 rounded-lg bg-void px-4 py-3 space-y-1">
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Name</span>
              <span className="text-sm font-medium">{tokenInfo.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Symbol</span>
              <span className="font-[family-name:var(--font-mono)] text-sm text-quantum-green">
                {tokenInfo.symbol}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Decimals</span>
              <span className="font-[family-name:var(--font-mono)] text-sm">
                {tokenInfo.decimals}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Total Supply</span>
              <span className="font-[family-name:var(--font-mono)] text-sm">
                {formatTokenAmount(tokenInfo.total_supply, tokenInfo.decimals)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Address</span>
              <span className="font-[family-name:var(--font-mono)] text-xs text-quantum-violet">
                {truncateAddr(tokenInfo.address)}
              </span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
