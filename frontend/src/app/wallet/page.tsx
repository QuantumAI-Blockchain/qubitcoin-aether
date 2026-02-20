"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWalletStore } from "@/stores/wallet-store";
import { WalletButton } from "@/components/wallet/wallet-button";
import { Card } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { QRCode } from "@/components/ui/qr-code";
import { TransactionHistory } from "@/components/wallet/transaction-history";
import { TokenManager } from "@/components/wallet/token-manager";
import { NFTGallery } from "@/components/wallet/nft-gallery";
import { NativeWalletPanel } from "@/components/wallet/native-wallet";
import { SephirotLauncher } from "@/components/wallet/sephirot-launcher";

const TABS = [
  { key: "metamask" as const, label: "MetaMask" },
  { key: "native" as const, label: "Native Wallet" },
  { key: "sephirot" as const, label: "Sephirot Nodes" },
];

export default function WalletPage() {
  const { address, connected, walletTab, setWalletTab } = useWalletStore();

  return (
    <div className="mx-auto max-w-5xl px-4 pt-20 pb-12">
      <h1 className="font-[family-name:var(--font-heading)] text-3xl font-bold">
        Wallet
      </h1>

      {/* Tab bar */}
      <div className="mt-6 flex gap-1 rounded-xl border border-surface-light bg-surface p-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setWalletTab(tab.key)}
            className={`flex-1 rounded-lg px-4 py-2.5 text-sm font-semibold transition ${
              walletTab === tab.key
                ? "bg-quantum-green/20 text-quantum-green"
                : "text-text-secondary hover:text-text-primary"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="mt-6">
        {walletTab === "metamask" && <MetaMaskTab />}
        {walletTab === "native" && (
          <ErrorBoundary>
            <NativeWalletPanel />
          </ErrorBoundary>
        )}
        {walletTab === "sephirot" && (
          <ErrorBoundary>
            <SephirotLauncher />
          </ErrorBoundary>
        )}
      </div>
    </div>
  );
}

/* ---- MetaMask Tab (existing wallet functionality) ---- */

function MetaMaskTab() {
  const { address, connected } = useWalletStore();

  const { data: balanceData } = useQuery({
    queryKey: ["balance", address],
    queryFn: () => api.getBalance(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  });

  const balance = balanceData?.balance
    ? parseFloat(balanceData.balance)
    : undefined;

  if (!connected) {
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-16">
        <div className="text-center">
          <p className="text-text-secondary">
            Connect your MetaMask wallet to manage QBC via the EVM-compatible
            interface.
          </p>
        </div>
        <WalletButton />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Balance */}
      <Card glow="green">
        <p className="text-sm text-text-secondary">QBC Balance</p>
        <p className="mt-2 font-[family-name:var(--font-mono)] text-4xl font-bold text-quantum-green">
          {balance != null ? balance.toLocaleString() : "---"} QBC
        </p>
        <p className="mt-2 font-[family-name:var(--font-mono)] text-xs text-text-secondary">
          {address}
        </p>
      </Card>

      {/* Send */}
      <MetaMaskSend />

      {/* Receive */}
      <Card>
        <h3 className="mb-3 font-[family-name:var(--font-heading)] text-lg font-semibold">
          Receive QBC
        </h3>
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          <QRCode value={address ?? ""} size={120} />
          <div className="flex-1">
            <p className="text-xs text-text-secondary">Your address:</p>
            <p className="mt-1 break-all rounded-lg bg-void px-4 py-3 font-[family-name:var(--font-mono)] text-sm text-quantum-green">
              {address}
            </p>
          </div>
        </div>
      </Card>

      {/* Transaction History */}
      <ErrorBoundary>
        <TransactionHistory address={address!} />
      </ErrorBoundary>

      {/* QBC-20 Token Management */}
      <ErrorBoundary>
        <TokenManager />
      </ErrorBoundary>

      {/* QBC-721 NFT Gallery */}
      <ErrorBoundary>
        <NFTGallery />
      </ErrorBoundary>
    </div>
  );
}

/* ---- MetaMask Send (with ethers.js) ---- */

function MetaMaskSend() {
  const { address } = useWalletStore();
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!to || !amount || !address) return;
    setSending(true);
    setResult(null);
    try {
      // Use MetaMask via window.ethereum
      const ethereum = (window as unknown as { ethereum?: { request: (args: { method: string; params: unknown[] }) => Promise<string> } }).ethereum;
      if (!ethereum) throw new Error("MetaMask not found");

      const weiHex =
        "0x" +
        BigInt(Math.floor(parseFloat(amount) * 1e18)).toString(16);

      const txHash = await ethereum.request({
        method: "eth_sendTransaction",
        params: [
          {
            from: address,
            to: to.startsWith("0x") ? to : "0x" + to,
            value: weiHex,
            gas: "0x5208", // 21000
          },
        ],
      });
      setResult(`Sent! TX: ${txHash.slice(0, 18)}...`);
      setTo("");
      setAmount("");
    } catch (err) {
      setResult(`Error: ${err}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
        Send QBC
      </h3>
      <form onSubmit={handleSend} className="space-y-4">
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Recipient Address
          </label>
          <input
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="0x..."
            className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-secondary">
            Amount (QBC)
          </label>
          <input
            type="number"
            step="0.0001"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.0000"
            className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <button
          type="submit"
          disabled={sending || !to || !amount}
          className="rounded-lg bg-quantum-green px-6 py-2.5 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50"
        >
          {sending ? "Sending..." : "Send Transaction"}
        </button>
        {result && (
          <p
            className={`text-xs ${result.startsWith("Error") ? "text-red-400" : "text-quantum-green"}`}
          >
            {result}
          </p>
        )}
      </form>
    </Card>
  );
}

