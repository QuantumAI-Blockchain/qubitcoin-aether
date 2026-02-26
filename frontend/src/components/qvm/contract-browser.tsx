"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
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
      <h3 className="mb-4 font-[family-name:var(--font-display)] text-lg font-semibold">
        Contract Lookup
      </h3>

      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-3">
        <input
          value={searchAddr}
          onChange={(e) => setSearchAddr(e.target.value)}
          placeholder="Contract address (0x...)"
          className="flex-1 rounded-lg bg-bg-deep px-4 py-2.5 font-[family-name:var(--font-code)] text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
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

function ContractDetail({ contract }: { contract: { address: string; code_hash: string; nonce: number; bytecode_size: number } }) {
  return (
    <div className="mt-6 space-y-4">
      <div className="rounded-lg border border-border-subtle bg-bg-deep p-4">
        <h4 className="mb-3 text-sm font-semibold text-text-primary">Contract Details</h4>

        <dl className="space-y-3 text-sm">
          <div>
            <dt className="text-xs text-text-secondary">Address</dt>
            <dd className="mt-0.5 break-all font-[family-name:var(--font-code)] text-quantum-green">
              {contract.address}
            </dd>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <dt className="text-xs text-text-secondary">Code Hash</dt>
              <dd className="mt-0.5 truncate font-[family-name:var(--font-code)] text-xs text-text-secondary">
                {contract.code_hash}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text-secondary">Nonce</dt>
              <dd className="mt-0.5 font-[family-name:var(--font-code)] text-text-primary">
                {contract.nonce}
              </dd>
            </div>
          </div>
          <div>
            <dt className="text-xs text-text-secondary">Bytecode Size</dt>
            <dd className="mt-0.5 font-[family-name:var(--font-code)] text-text-primary">
              {contract.bytecode_size.toLocaleString()} bytes
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
