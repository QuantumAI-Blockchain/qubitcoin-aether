"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";

const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";

interface InheritanceStatus {
  has_plan: boolean;
  plan?: {
    beneficiary_address: string;
    inactivity_blocks: number;
    last_heartbeat_block: number;
    active: boolean;
  };
  is_claimable: boolean;
  blocks_until_claimable: number;
}

async function fetchStatus(address: string): Promise<InheritanceStatus> {
  const res = await fetch(`${RPC_URL}/inheritance/status/${address}`);
  if (!res.ok) throw new Error("Failed to fetch inheritance status");
  return res.json();
}

/**
 * Inheritance Protocol management panel for the wallet page.
 */
export function InheritancePanel() {
  const { address } = useWalletStore();
  const queryClient = useQueryClient();
  const [beneficiary, setBeneficiary] = useState("");

  const { data: status } = useQuery({
    queryKey: ["inheritanceStatus", address],
    queryFn: () => fetchStatus(address!),
    enabled: !!address,
    refetchInterval: 30_000,
    retry: false,
  });

  const setBeneficiaryMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${RPC_URL}/inheritance/set-beneficiary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          owner: address,
          beneficiary,
        }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inheritanceStatus"] });
      setBeneficiary("");
    },
  });

  const heartbeatMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${RPC_URL}/inheritance/heartbeat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner: address }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inheritanceStatus"] });
    },
  });

  if (!address) return null;

  return (
    <Card>
      <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
        Inheritance Protocol
      </h3>
      <p className="mt-1 text-xs text-text-secondary">
        Dead-man&apos;s switch — designate a beneficiary for your assets
      </p>

      {status?.has_plan && status.plan ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg bg-bg-deep p-4">
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Beneficiary</span>
              <span className="font-[family-name:var(--font-code)] text-xs text-quantum-green">
                {status.plan.beneficiary_address.slice(0, 16)}...
              </span>
            </div>
            <div className="mt-2 flex justify-between">
              <span className="text-xs text-text-secondary">Status</span>
              <span
                className={`text-xs font-semibold ${
                  status.is_claimable ? "text-red-400" : "text-quantum-green"
                }`}
              >
                {status.is_claimable ? "Claimable" : "Active"}
              </span>
            </div>
            {!status.is_claimable && status.blocks_until_claimable > 0 && (
              <div className="mt-2 flex justify-between">
                <span className="text-xs text-text-secondary">
                  Blocks Until Claimable
                </span>
                <span className="font-[family-name:var(--font-code)] text-xs">
                  {status.blocks_until_claimable.toLocaleString()}
                </span>
              </div>
            )}
          </div>
          <button
            onClick={() => heartbeatMutation.mutate()}
            disabled={heartbeatMutation.isPending}
            className="w-full rounded-lg bg-quantum-green px-4 py-2 text-sm font-semibold text-void transition hover:bg-quantum-green/80 disabled:opacity-50"
          >
            {heartbeatMutation.isPending ? "Sending..." : "Send Heartbeat"}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <input
            value={beneficiary}
            onChange={(e) => setBeneficiary(e.target.value)}
            placeholder="Beneficiary address"
            className="w-full rounded-lg bg-bg-deep px-4 py-2.5 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
          />
          <button
            onClick={() => setBeneficiaryMutation.mutate()}
            disabled={!beneficiary || setBeneficiaryMutation.isPending}
            className="w-full rounded-lg bg-quantum-violet px-4 py-2 text-sm font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-50"
          >
            {setBeneficiaryMutation.isPending
              ? "Setting..."
              : "Set Beneficiary"}
          </button>
        </div>
      )}
    </Card>
  );
}
