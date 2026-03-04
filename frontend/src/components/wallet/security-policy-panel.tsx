"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";

const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL ?? "http://localhost:5000";

interface SecurityPolicy {
  address: string;
  daily_limit_qbc: number;
  require_whitelist: boolean;
  whitelist: string[];
  time_lock_blocks: number;
  time_lock_threshold_qbc: number;
}

async function fetchPolicy(address: string): Promise<SecurityPolicy | null> {
  const res = await fetch(`${RPC_URL}/security/policy/${address}`);
  if (!res.ok) return null;
  const data = await res.json();
  return data.policy ?? null;
}

/**
 * High-Security Account policy management panel.
 */
export function SecurityPolicyPanel() {
  const { address } = useWalletStore();
  const queryClient = useQueryClient();
  const [dailyLimit, setDailyLimit] = useState("1000");
  const [timeLockThreshold, setTimeLockThreshold] = useState("100");
  const [timeLockBlocks, setTimeLockBlocks] = useState("26182");

  const { data: policy } = useQuery({
    queryKey: ["securityPolicy", address],
    queryFn: () => fetchPolicy(address!),
    enabled: !!address,
    refetchInterval: 30_000,
    retry: false,
  });

  const setPolicyMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${RPC_URL}/security/policy/set`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          address,
          daily_limit_qbc: parseFloat(dailyLimit),
          time_lock_threshold_qbc: parseFloat(timeLockThreshold),
          time_lock_blocks: parseInt(timeLockBlocks),
        }),
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["securityPolicy"] });
    },
  });

  const removePolicyMutation = useMutation({
    mutationFn: async () => {
      const res = await fetch(`${RPC_URL}/security/policy/${address}`, {
        method: "DELETE",
      });
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["securityPolicy"] });
    },
  });

  if (!address) return null;

  return (
    <Card>
      <h3 className="font-[family-name:var(--font-display)] text-lg font-semibold">
        Security Policy
      </h3>
      <p className="mt-1 text-xs text-text-secondary">
        Set spending limits, time-locks, and whitelists for your account
      </p>

      {policy ? (
        <div className="mt-4 space-y-3">
          <div className="rounded-lg bg-bg-deep p-4 space-y-2">
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Daily Limit</span>
              <span className="font-[family-name:var(--font-code)] text-xs">
                {policy.daily_limit_qbc.toLocaleString()} QBC
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Time-Lock</span>
              <span className="font-[family-name:var(--font-code)] text-xs">
                {policy.time_lock_blocks.toLocaleString()} blocks (above{" "}
                {policy.time_lock_threshold_qbc} QBC)
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-xs text-text-secondary">Whitelist</span>
              <span className="text-xs">
                {policy.require_whitelist
                  ? `${policy.whitelist.length} addresses`
                  : "Disabled"}
              </span>
            </div>
          </div>
          <button
            onClick={() => removePolicyMutation.mutate()}
            disabled={removePolicyMutation.isPending}
            className="w-full rounded-lg border border-red-400/30 px-4 py-2 text-sm font-semibold text-red-400 transition hover:bg-red-400/10 disabled:opacity-50"
          >
            {removePolicyMutation.isPending ? "Removing..." : "Remove Policy"}
          </button>
        </div>
      ) : (
        <div className="mt-4 space-y-3">
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Daily Limit (QBC)
            </label>
            <input
              type="number"
              value={dailyLimit}
              onChange={(e) => setDailyLimit(e.target.value)}
              className="w-full rounded-lg bg-bg-deep px-4 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Time-Lock Threshold (QBC)
            </label>
            <input
              type="number"
              value={timeLockThreshold}
              onChange={(e) => setTimeLockThreshold(e.target.value)}
              className="w-full rounded-lg bg-bg-deep px-4 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-secondary">
              Time-Lock Duration (blocks)
            </label>
            <input
              type="number"
              value={timeLockBlocks}
              onChange={(e) => setTimeLockBlocks(e.target.value)}
              className="w-full rounded-lg bg-bg-deep px-4 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-quantum-violet/50"
            />
          </div>
          <button
            onClick={() => setPolicyMutation.mutate()}
            disabled={setPolicyMutation.isPending}
            className="w-full rounded-lg bg-quantum-violet px-4 py-2 text-sm font-semibold text-white transition hover:bg-quantum-violet/80 disabled:opacity-50"
          >
            {setPolicyMutation.isPending ? "Setting..." : "Set Security Policy"}
          </button>
        </div>
      )}
    </Card>
  );
}
