"use client";

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

export default function WalletPage() {
  const { address, connected } = useWalletStore();

  const { data: balanceData } = useQuery({
    queryKey: ["balance", address],
    queryFn: () => api.getBalance(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  });

  const balance = balanceData?.balance ? parseFloat(balanceData.balance) : undefined;

  if (!connected) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-6 pt-16">
        <div className="text-center">
          <h1 className="font-[family-name:var(--font-heading)] text-3xl font-bold">
            Wallet
          </h1>
          <p className="mt-2 text-text-secondary">
            Connect your MetaMask wallet to manage QBC
          </p>
        </div>
        <WalletButton />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-4 pt-20 pb-12">
      <h1 className="font-[family-name:var(--font-heading)] text-3xl font-bold">
        Wallet
      </h1>

      <div className="mt-8 space-y-6">
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
        <Card>
          <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
            Send QBC
          </h3>
          <form
            onSubmit={(e) => e.preventDefault()}
            className="space-y-4"
          >
            <div>
              <label className="mb-1 block text-xs text-text-secondary">
                Recipient Address
              </label>
              <input
                placeholder="qbc1..."
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
                placeholder="0.0000"
                className="w-full rounded-lg bg-void px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
              />
            </div>
            <button
              type="submit"
              className="rounded-lg bg-quantum-green px-6 py-2.5 text-sm font-semibold text-void transition hover:bg-quantum-green/80"
            >
              Send Transaction
            </button>
          </form>
        </Card>

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
    </div>
  );
}
