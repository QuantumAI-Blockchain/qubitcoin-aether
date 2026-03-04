"use client";

import { useEffect, useState } from "react";
import {
  getPendingTransactions,
  removeTransaction,
  broadcastPendingTransactions,
  type OfflineTransaction,
} from "@/lib/offline-tx";
import { Card } from "@/components/ui/card";

/**
 * Offline Transaction Queue panel — shows pending offline transactions
 * and allows manual broadcast or removal.
 */
export function OfflineTxQueue() {
  const [transactions, setTransactions] = useState<OfflineTransaction[]>([]);
  const [broadcasting, setBroadcasting] = useState(false);

  const loadTxs = async () => {
    try {
      const txs = await getPendingTransactions();
      setTransactions(txs);
    } catch {
      // IndexedDB not available
    }
  };

  useEffect(() => {
    loadTxs();
    // Refresh when coming back online
    const handler = () => loadTxs();
    window.addEventListener("online", handler);
    return () => window.removeEventListener("online", handler);
  }, []);

  const handleBroadcast = async () => {
    const rpcUrl =
      process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";
    setBroadcasting(true);
    try {
      await broadcastPendingTransactions(rpcUrl);
      await loadTxs();
    } finally {
      setBroadcasting(false);
    }
  };

  const handleRemove = async (id: string) => {
    await removeTransaction(id);
    await loadTxs();
  };

  if (transactions.length === 0) return null;

  const pending = transactions.filter((t) => t.status === "pending");

  return (
    <Card>
      <div className="flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Offline Queue
        </h3>
        <span className="rounded-full bg-amber-600/20 px-2.5 py-0.5 text-xs font-medium text-amber-400">
          {pending.length} pending
        </span>
      </div>

      <div className="mt-4 space-y-3">
        {transactions.map((tx) => (
          <div
            key={tx.id}
            className="flex items-center justify-between rounded-lg bg-bg-deep px-4 py-3"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-[family-name:var(--font-code)] text-xs text-text-primary">
                To: {tx.to}
              </p>
              <p className="text-xs text-text-secondary">
                {tx.amount} QBC &middot;{" "}
                <span
                  className={
                    tx.status === "confirmed"
                      ? "text-quantum-green"
                      : tx.status === "failed"
                        ? "text-red-400"
                        : "text-amber-400"
                  }
                >
                  {tx.status}
                </span>
              </p>
            </div>
            {tx.status !== "confirmed" && (
              <button
                onClick={() => handleRemove(tx.id)}
                className="ml-3 text-xs text-text-secondary hover:text-red-400"
              >
                Remove
              </button>
            )}
          </div>
        ))}
      </div>

      {pending.length > 0 && (
        <button
          onClick={handleBroadcast}
          disabled={broadcasting || !navigator.onLine}
          className="mt-4 w-full rounded-lg bg-quantum-green px-4 py-2 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50"
        >
          {broadcasting ? "Broadcasting..." : "Broadcast All"}
        </button>
      )}
    </Card>
  );
}
