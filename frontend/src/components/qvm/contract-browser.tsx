"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type ContractInfo } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { PhiSpinner } from "@/components/ui/loading";

export function ContractBrowser() {
  const [searchAddr, setSearchAddr] = useState("");
  const [lookupAddr, setLookupAddr] = useState<string | null>(null);

  const {
    data: contract,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["contract", lookupAddr],
    queryFn: () => api.getContract(lookupAddr!),
    enabled: !!lookupAddr,
    retry: false,
  });

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const addr = searchAddr.trim();
    if (addr) setLookupAddr(addr);
  }

  return (
    <Card>
      <h3 className="mb-4 font-[family-name:var(--font-heading)] text-lg font-semibold">
        Contract Lookup
      </h3>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          value={searchAddr}
          onChange={(e) => setSearchAddr(e.target.value)}
          placeholder="Contract address (0x...)"
          className="flex-1 rounded-lg bg-void px-4 py-2.5 font-[family-name:var(--font-mono)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
        />
        <button
          type="submit"
          disabled={!searchAddr.trim()}
          className="rounded-lg bg-quantum-violet/20 px-5 py-2.5 text-sm font-medium text-quantum-violet transition hover:bg-quantum-violet/30 disabled:opacity-40"
        >
          Search
        </button>
      </form>

      {/* Result */}
      {isLoading && (
        <div className="mt-6 flex justify-center">
          <PhiSpinner className="h-6 w-6" />
        </div>
      )}

      {isError && lookupAddr && (
        <div className="mt-6 rounded-lg border border-quantum-red/30 bg-quantum-red/5 px-4 py-3 text-sm text-quantum-red">
          Contract not found: {(error as Error)?.message || "Unknown error"}
        </div>
      )}

      {contract && <ContractDetail contract={contract} />}
    </Card>
  );
}

function ContractDetail({ contract }: { contract: ContractInfo }) {
  const deployedDate = new Date(contract.deployed_at * 1000);

  return (
    <div className="mt-6 space-y-4">
      <div className="rounded-lg border border-surface-light bg-void p-4">
        <div className="mb-3 flex items-center justify-between">
          <h4 className="text-sm font-semibold text-text-primary">Contract Details</h4>
          <span
            className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
              contract.is_active
                ? "bg-quantum-green/10 text-quantum-green"
                : "bg-text-secondary/10 text-text-secondary"
            }`}
          >
            {contract.is_active ? "Active" : "Inactive"}
          </span>
        </div>

        <dl className="space-y-3 text-sm">
          <div>
            <dt className="text-xs text-text-secondary">Address</dt>
            <dd className="mt-0.5 break-all font-[family-name:var(--font-mono)] text-quantum-green">
              {contract.address}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Creator</dt>
            <dd className="mt-0.5 break-all font-[family-name:var(--font-mono)] text-text-primary">
              {contract.creator}
            </dd>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-xs text-text-secondary">Type</dt>
              <dd className="mt-0.5 font-medium text-text-primary">{contract.contract_type}</dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Storage Slots</dt>
              <dd className="mt-0.5 font-[family-name:var(--font-mono)] text-text-primary">
                {contract.storage_slots.toLocaleString()}
              </dd>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-xs text-text-secondary">Deployed</dt>
              <dd className="mt-0.5 text-text-primary">
                {deployedDate.toLocaleDateString()}{" "}
                <span className="text-text-secondary">{deployedDate.toLocaleTimeString()}</span>
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Bytecode Hash</dt>
              <dd className="mt-0.5 truncate font-[family-name:var(--font-mono)] text-xs text-text-secondary">
                {contract.bytecode_hash}
              </dd>
            </div>
          </div>
        </dl>
      </div>
    </div>
  );
}
