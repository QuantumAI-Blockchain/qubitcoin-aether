"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useWalletStore } from "@/stores/wallet-store";
import { WalletButton } from "@/components/wallet/wallet-button";
import { Card } from "@/components/ui/card";

export default function WalletPage() {
  const { address, connected } = useWalletStore();

  const { data: balance } = useQuery({
    queryKey: ["balance", address],
    queryFn: () => api.getBalance(address!),
    enabled: !!address,
    refetchInterval: 10_000,
  });

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
            {balance?.balance?.toLocaleString() ?? "---"} QBC
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
          <p className="text-xs text-text-secondary">Your address:</p>
          <p className="mt-1 break-all rounded-lg bg-void px-4 py-3 font-[family-name:var(--font-mono)] text-sm text-quantum-green">
            {address}
          </p>
        </Card>
      </div>
    </div>
  );
}
