"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";

export function StorageInspector() {
  const [contractAddr, setContractAddr] = useState("");
  const [slotKey, setSlotKey] = useState("");
  const [lookupKey, setLookupKey] = useState<{ addr: string; key: string } | null>(null);

  const {
    data: slotValue,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["storage", lookupKey?.addr, lookupKey?.key],
    queryFn: () => api.getContractStorage(lookupKey!.addr, lookupKey!.key),
    enabled: !!lookupKey,
    retry: false,
  });

  function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    const addr = contractAddr.trim();
    const key = slotKey.trim();
    if (addr && key) setLookupKey({ addr, key });
  }

  // Common storage slot presets
  const presets = [
    { label: "Slot 0", key: "0x0" },
    { label: "Slot 1", key: "0x1" },
    { label: "Slot 2", key: "0x2" },
    { label: "Owner", key: "0x0" },
    { label: "Total Supply", key: "0x2" },
  ];

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        Storage Inspector
      </h3>

      <form onSubmit={handleLookup} className="space-y-3">
        <div>
          <label className="mb-1 block text-xs text-text-secondary">Contract Address</label>
          <input
            value={contractAddr}
            onChange={(e) => setContractAddr(e.target.value)}
            placeholder="0x..."
            className="w-full rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-text-secondary">Storage Key</label>
          <div className="flex gap-3">
            <input
              value={slotKey}
              onChange={(e) => setSlotKey(e.target.value)}
              placeholder="0x0 (slot number or hash)"
              className="flex-1 rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
            <button
              type="submit"
              disabled={!contractAddr.trim() || !slotKey.trim()}
              className="rounded-lg bg-quantum-green/20 px-5 py-2.5 text-sm font-medium text-quantum-green transition hover:bg-quantum-green/30 disabled:opacity-40"
            >
              Read
            </button>
          </div>
        </div>

        {/* Quick presets */}
        <div className="flex flex-wrap gap-1.5">
          {presets.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => setSlotKey(p.key)}
              className="rounded-md bg-border-subtle px-2.5 py-1 text-xs text-text-secondary transition hover:bg-quantum-violet/20 hover:text-quantum-violet"
            >
              {p.label}
            </button>
          ))}
        </div>
      </form>

      {/* Result */}
      {isLoading && (
        <div className="mt-4 flex justify-center">
          <PhiSpinner className="h-5 w-5" />
        </div>
      )}

      {isError && lookupKey && (
        <div className="mt-4 rounded-lg border border-quantum-red/30 bg-quantum-red/5 px-4 py-3 text-sm text-quantum-red">
          Failed to read storage: {(error as Error)?.message || "Unknown error"}
        </div>
      )}

      {slotValue && !isLoading && (
        <div className="mt-4 rounded-lg border border-border-subtle bg-bg-deep p-4">
          <div className="space-y-2 text-sm">
            <div>
              <span className="text-xs text-text-secondary">Contract:</span>
              <p className="truncate font-[family-name:var(--font-code)] text-xs text-text-primary">
                {lookupKey?.addr}
              </p>
            </div>
            <div>
              <span className="text-xs text-text-secondary">Key:</span>
              <p className="font-[family-name:var(--font-code)] text-xs text-quantum-violet">
                {lookupKey?.key}
              </p>
            </div>
            <div>
              <span className="text-xs text-text-secondary">Value:</span>
              <p className="break-all rounded-md bg-bg-panel px-3 py-2 font-[family-name:var(--font-code)] text-sm text-quantum-green">
                {slotValue.value || "0x0 (empty)"}
              </p>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
