"use client";

import { useState, useEffect } from "react";
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
import { OfflineTxQueue } from "@/components/wallet/offline-tx-queue";
import { PushNotificationSetup } from "@/components/wallet/push-notification-setup";
import { OfflineIndicator } from "@/components/wallet/offline-indicator";
import { InstallPromptBanner } from "@/components/wallet/install-prompt-banner";
import Link from "next/link";
import { AddNetwork } from "@/components/wallet/add-network";
import {
  isMobile,
  hasInjectedProvider,
  openInMetaMask,
  getMetaMaskInstallUrl,
  isTelegramWebApp,
} from "@/lib/wallet";

const TABS = [
  { key: "metamask" as const, label: "MetaMask" },
  { key: "native" as const, label: "Native Wallet" },
  { key: "sephirot" as const, label: "Sephirot Nodes" },
];

export default function WalletPage() {
  const { walletTab, setWalletTab } = useWalletStore();

  return (
    <div className="mx-auto max-w-5xl px-4 pt-20 pb-12 sm:px-6">
      <OfflineIndicator />
      <InstallPromptBanner />
      <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold sm:text-3xl">
        Wallet
      </h1>

      {/* Tab bar — scrollable on mobile */}
      <div className="mt-6 flex gap-1 rounded-xl border border-border-subtle bg-bg-panel p-1 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setWalletTab(tab.key)}
            className={`flex-1 min-w-[100px] rounded-lg px-3 py-3 text-sm font-semibold transition whitespace-nowrap ${
              walletTab === tab.key
                ? "bg-quantum-green/20 text-quantum-green"
                : "text-text-secondary hover:text-text-primary active:bg-white/5"
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

      {/* Cross-Chain Bridge Banner */}
      <Link
        href="/bridge"
        className="pulse-glow mt-8 flex items-center justify-between rounded-xl border border-quantum-violet/30 bg-quantum-violet/5 px-4 py-4 transition-colors hover:border-quantum-violet/50 hover:bg-quantum-violet/10 sm:px-6 sm:py-5"
      >
        <div className="flex-1 min-w-0">
          <h3 className="font-[family-name:var(--font-display)] text-base font-bold text-quantum-violet sm:text-lg">
            Cross-Chain Bridge
          </h3>
          <p className="mt-1 text-xs text-text-secondary sm:text-sm">
            Wrap QBC and QUSD to Ethereum, BNB Smart Chain, and Solana
          </p>
        </div>
        <span className="ml-3 text-2xl text-quantum-violet flex-shrink-0">&#8594;</span>
      </Link>

      {/* PWA Features */}
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        <ErrorBoundary>
          <OfflineTxQueue />
        </ErrorBoundary>
        <ErrorBoundary>
          <PushNotificationSetup />
        </ErrorBoundary>
      </div>
    </div>
  );
}

/* ---- MetaMask Tab (existing wallet functionality) ---- */

function MetaMaskTab() {
  const { address, connected } = useWalletStore();
  const [mobile, setMobile] = useState(false);
  const [hasProvider, setHasProvider] = useState(true);

  useEffect(() => {
    setMobile(isMobile());
    setHasProvider(hasInjectedProvider());
  }, []);

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
      <div className="flex flex-col items-center gap-6 py-8 sm:gap-8 sm:py-12">
        {/* Mobile: no injected provider — show deep-link + install options */}
        {mobile && !hasProvider && !isTelegramWebApp() ? (
          <div className="w-full max-w-md space-y-4">
            <div className="text-center">
              <p className="text-base font-semibold text-text-primary sm:text-lg">
                Connect with MetaMask
              </p>
              <p className="mt-2 text-sm text-text-secondary">
                Open this page in MetaMask&apos;s built-in browser to connect your wallet.
              </p>
            </div>

            {/* Primary: Open in MetaMask */}
            <button
              onClick={() => openInMetaMask()}
              className="w-full flex items-center justify-center gap-3 rounded-xl bg-quantum-green px-6 py-4 text-base font-bold text-void transition active:scale-[0.98] hover:bg-quantum-green/90"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="flex-shrink-0">
                <path d="M21.3 2L13 8.2l1.6-3.7L21.3 2z" fill="#E2761B" stroke="#E2761B" strokeWidth="0.3"/>
                <path d="M2.7 2l8.2 6.3-1.5-3.8L2.7 2z" fill="#E4761B" stroke="#E4761B" strokeWidth="0.3"/>
                <path d="M18.3 16.8l-2.2 3.4 4.7 1.3 1.3-4.6-3.8-.1z" fill="#E4761B" stroke="#E4761B" strokeWidth="0.3"/>
                <path d="M1.9 16.9l1.3 4.6 4.7-1.3-2.2-3.4-3.8.1z" fill="#E4761B" stroke="#E4761B" strokeWidth="0.3"/>
              </svg>
              Open in MetaMask
            </button>

            {/* Secondary: Install MetaMask */}
            <a
              href={getMetaMaskInstallUrl()}
              target="_blank"
              rel="noopener noreferrer"
              className="block w-full rounded-xl border border-border-subtle bg-bg-panel px-6 py-4 text-center text-sm font-semibold text-text-secondary transition hover:text-text-primary hover:border-glow-cyan/30 active:scale-[0.98]"
            >
              Don&apos;t have MetaMask? Install it
            </a>

            {/* Manual config fallback */}
            <div className="pt-2">
              <AddNetwork />
            </div>
          </div>
        ) : (
          <>
            <div className="text-center px-4">
              <p className="text-sm text-text-secondary sm:text-base">
                Connect your MetaMask wallet to manage QBC via the EVM-compatible
                interface.
              </p>
            </div>
            <WalletButton />
            <div className="w-full max-w-md">
              <AddNetwork />
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Balance */}
      <Card glow="green">
        <p className="text-sm text-text-secondary">QBC Balance</p>
        <p className="mt-2 font-[family-name:var(--font-code)] text-2xl font-bold text-quantum-green sm:text-4xl">
          {balance != null ? balance.toLocaleString() : "---"} QBC
        </p>
        <p className="mt-2 font-[family-name:var(--font-code)] text-[10px] text-text-secondary break-all sm:text-xs">
          {address}
        </p>
      </Card>

      {/* Send */}
      <MetaMaskSend />

      {/* Receive */}
      <Card>
        <h3 className="mb-3 font-[family-name:var(--font-display)] text-lg font-semibold">
          Receive QBC
        </h3>
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
          <QRCode value={address ?? ""} size={120} />
          <div className="flex-1 w-full min-w-0">
            <p className="text-xs text-text-secondary">Your address:</p>
            <p className="mt-1 break-all rounded-lg bg-bg-deep px-3 py-3 font-[family-name:var(--font-code)] text-xs text-quantum-green sm:px-4 sm:text-sm select-all">
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

      // QBC uses 8 decimals (not 18 like Ethereum)
      const weiHex =
        "0x" +
        BigInt(Math.floor(parseFloat(amount) * 1e8)).toString(16);

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
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        Send QBC
      </h3>
      <form onSubmit={handleSend} className="space-y-4">
        <div>
          <label className="mb-1.5 block text-xs text-text-secondary">
            Recipient Address
          </label>
          <input
            value={to}
            onChange={(e) => setTo(e.target.value)}
            placeholder="0x..."
            autoComplete="off"
            autoCorrect="off"
            autoCapitalize="off"
            spellCheck={false}
            className="w-full rounded-lg bg-bg-deep px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <div>
          <label className="mb-1.5 block text-xs text-text-secondary">
            Amount (QBC)
          </label>
          <input
            type="number"
            inputMode="decimal"
            step="0.0001"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.0000"
            className="w-full rounded-lg bg-bg-deep px-4 py-3 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <button
          type="submit"
          disabled={sending || !to || !amount}
          className="w-full rounded-lg bg-quantum-green px-6 py-3 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50 active:scale-[0.98] sm:w-auto"
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
