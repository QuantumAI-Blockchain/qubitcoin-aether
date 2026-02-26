"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type TransactionInfo } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";

interface TransactionHistoryProps {
  address: string;
}

const STATUS_STYLE: Record<string, string> = {
  confirmed: "bg-quantum-green/10 text-quantum-green",
  pending: "bg-golden/10 text-golden",
  failed: "bg-quantum-red/10 text-quantum-red",
};

function truncateAddr(addr: string): string {
  if (addr.length <= 14) return addr;
  return `${addr.slice(0, 8)}...${addr.slice(-6)}`;
}

function timeAgo(timestamp: number): string {
  const seconds = Math.floor(Date.now() / 1000 - timestamp);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function TransactionHistory({ address }: TransactionHistoryProps) {
  const { data: utxoData, isLoading: utxoLoading } = useQuery({
    queryKey: ["utxos", address],
    queryFn: () => api.getUTXOs(address),
    enabled: !!address,
    refetchInterval: 15_000,
  });

  const { data: mempoolData, isLoading: mempoolLoading } = useQuery({
    queryKey: ["mempool"],
    queryFn: api.getMempool,
    refetchInterval: 10_000,
  });

  const isLoading = utxoLoading || mempoolLoading;

  // Build transaction list from UTXOs (confirmed) + mempool (pending)
  const pendingTxs: TransactionInfo[] =
    mempoolData?.transactions?.filter(
      (tx) => tx.sender === address || tx.recipient === address,
    ) ?? [];

  const confirmedUtxos = utxoData?.utxos ?? [];

  return (
    <Card>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
          Transaction History
        </h3>
        {isLoading && <PhiSpinner className="h-4 w-4" />}
      </div>

      {/* Pending transactions */}
      {pendingTxs.length > 0 && (
        <div className="mb-4">
          <p className="mb-2 text-xs font-medium text-golden">Pending</p>
          <div className="space-y-2">
            {pendingTxs.map((tx) => {
              const isSend = tx.sender === address;
              return (
                <div
                  key={tx.txid}
                  className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-deep px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-medium ${isSend ? "text-quantum-red" : "text-quantum-green"}`}>
                        {isSend ? "SEND" : "RECV"}
                      </span>
                      <span className="truncate font-[family-name:var(--font-code)] text-xs text-text-secondary">
                        {isSend ? truncateAddr(tx.recipient) : truncateAddr(tx.sender)}
                      </span>
                    </div>
                    <p className="mt-0.5 text-xs text-text-secondary">
                      {timeAgo(tx.timestamp)}
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="font-[family-name:var(--font-code)] text-sm font-medium">
                      {isSend ? "-" : "+"}{tx.amount.toLocaleString()} QBC
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE.pending}`}>
                      pending
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* UTXOs (confirmed outputs) */}
      {confirmedUtxos.length > 0 ? (
        <div>
          <p className="mb-2 text-xs font-medium text-text-secondary">
            Unspent Outputs ({confirmedUtxos.length})
          </p>
          <div className="space-y-2">
            {confirmedUtxos.map((utxo, i) => (
              <div
                key={`${utxo.txid}-${utxo.vout}`}
                className="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-deep px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate font-[family-name:var(--font-code)] text-xs text-text-secondary">
                    {truncateAddr(utxo.txid)}:{utxo.vout}
                  </p>
                  <p className="mt-0.5 text-xs text-text-secondary">
                    {utxo.confirmations} confirmation{utxo.confirmations !== 1 ? "s" : ""}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-[family-name:var(--font-code)] text-sm font-medium text-quantum-green">
                    {utxo.amount.toLocaleString()} QBC
                  </span>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE.confirmed}`}>
                    confirmed
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        !isLoading &&
        pendingTxs.length === 0 && (
          <p className="py-8 text-center text-sm text-text-secondary">
            No transactions found for this address.
          </p>
        )
      )}
    </Card>
  );
}
