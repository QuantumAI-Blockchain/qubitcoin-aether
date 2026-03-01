"use client";

import { useState, useEffect } from "react";
import { Card } from "@/components/ui/card";
import { useWalletStore } from "@/stores/wallet-store";
import { useAIKGSStore } from "@/stores/aikgs-store";
import { api, type AIKGSLeaderboardEntry, type AIKGSContribution } from "@/lib/api";
import { AIKGS_TIERS } from "@/lib/constants";

function tierClass(tier: string): string {
  switch (tier) {
    case "bronze": return "tier-bronze";
    case "silver": return "tier-silver";
    case "gold": return "tier-gold";
    case "diamond": return "tier-diamond";
    default: return "text-text-secondary";
  }
}

export function RewardDashboard() {
  const { address, connected } = useWalletStore();
  const { profile, setProfile, recentContributions, setRecentContributions, setPoolStats } = useAIKGSStore();
  const { poolBalance, totalDistributed } = useAIKGSStore();
  const [leaderboard, setLeaderboard] = useState<AIKGSLeaderboardEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"overview" | "history" | "leaderboard">("overview");

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const [poolRes, lbRes] = await Promise.all([
          api.aikgsGetPoolStats(),
          api.aikgsGetLeaderboard(10),
        ]);
        setPoolStats(poolRes.pool_balance, poolRes.total_distributed);
        setLeaderboard(lbRes.leaderboard);

        if (address) {
          const [profileRes, contribRes] = await Promise.all([
            api.aikgsGetProfile(address),
            api.aikgsGetContributions(address, 10),
          ]);
          setProfile(profileRes);
          setRecentContributions(contribRes.contributions);
        }
      } catch {
        // Data unavailable
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [address, setProfile, setRecentContributions, setPoolStats]);

  return (
    <Card className="mb-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold glow-gold">AIKGS Rewards</h3>
        <div className="flex gap-1">
          {(["overview", "history", "leaderboard"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`rounded-lg px-2 py-1 text-[10px] font-semibold transition ${
                tab === t
                  ? "bg-golden/20 text-golden"
                  : "text-text-secondary hover:text-text-primary"
              }`}
            >
              {t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex h-32 items-center justify-center">
          <div className="phi-spin h-6 w-6 rounded-full border-2 border-golden/30 border-t-golden" />
        </div>
      ) : tab === "overview" ? (
        <div>
          {/* Pool stats */}
          <div className="mb-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-bg-deep p-3 text-center">
              <p className="text-lg font-bold glow-gold">{poolBalance.toLocaleString()}</p>
              <p className="text-[10px] text-text-secondary">Pool Balance (QBC)</p>
            </div>
            <div className="rounded-lg bg-bg-deep p-3 text-center">
              <p className="text-lg font-bold text-quantum-green">{totalDistributed.toLocaleString()}</p>
              <p className="text-[10px] text-text-secondary">Total Distributed</p>
            </div>
          </div>

          {/* Tier breakdown */}
          <h4 className="mb-2 text-xs font-semibold text-text-secondary">Reward Tiers</h4>
          <div className="grid grid-cols-4 gap-2">
            {(["bronze", "silver", "gold", "diamond"] as const).map((t) => {
              const tier = AIKGS_TIERS[t];
              return (
                <div key={t} className="rounded-lg bg-bg-deep p-2 text-center">
                  <p className={`text-sm font-bold ${tierClass(t)}`}>{tier.multiplier}x</p>
                  <p className="text-[10px] text-text-secondary">{tier.label}</p>
                  <p className="text-[10px] text-text-secondary">
                    {(tier.min * 100).toFixed(0)}-{(tier.max * 100).toFixed(0)}%
                  </p>
                </div>
              );
            })}
          </div>

          {/* User stats */}
          {profile && (
            <div className="mt-4 rounded-lg border border-golden/20 bg-golden/5 p-3">
              <h4 className="mb-2 text-xs font-semibold text-golden">Your Stats</h4>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div>
                  <p className="text-sm font-bold text-text-primary">{profile.total_contributions}</p>
                  <p className="text-[10px] text-text-secondary">Contributions</p>
                </div>
                <div>
                  <p className="text-sm font-bold text-text-primary">{profile.reputation_points.toLocaleString()}</p>
                  <p className="text-[10px] text-text-secondary">RP</p>
                </div>
                <div>
                  <p className="text-sm font-bold text-text-primary">Lv{profile.level}</p>
                  <p className="text-[10px] text-text-secondary">{profile.level_name}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : tab === "history" ? (
        <div>
          {!connected ? (
            <p className="text-center text-xs text-text-secondary">Connect wallet to view history.</p>
          ) : recentContributions.length === 0 ? (
            <p className="text-center text-xs text-text-secondary">No contributions yet. Start contributing!</p>
          ) : (
            <div className="space-y-2">
              {recentContributions.map((c) => (
                <div
                  key={c.contribution_id}
                  className="flex items-center justify-between rounded-lg bg-bg-deep p-2"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`text-xs font-semibold ${tierClass(c.tier)}`}>
                        {c.tier.toUpperCase()}
                      </span>
                      <span className="text-[10px] text-text-secondary">{c.domain}</span>
                    </div>
                    <p className="text-[10px] text-text-secondary">
                      Q: {c.quality_score.toFixed(2)} | N: {c.novelty_score.toFixed(2)} | Combined: {c.combined_score.toFixed(2)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs font-semibold text-golden">+{c.reward_amount.toFixed(4)}</p>
                    <p className="text-[10px] text-text-secondary">QBC</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div>
          {leaderboard.length === 0 ? (
            <p className="text-center text-xs text-text-secondary">No leaderboard data yet.</p>
          ) : (
            <div className="space-y-1">
              {leaderboard.map((entry, i) => (
                <div
                  key={entry.address}
                  className={`flex items-center gap-3 rounded-lg p-2 ${
                    entry.address === address ? "bg-golden/10 border border-golden/20" : "bg-bg-deep"
                  }`}
                >
                  <span className={`w-6 text-center text-xs font-bold ${
                    i === 0 ? "text-golden" : i === 1 ? "tier-silver" : i === 2 ? "tier-bronze" : "text-text-secondary"
                  }`}>
                    #{entry.rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-text-primary font-[family-name:var(--font-code)]">
                      {entry.address.slice(0, 10)}...{entry.address.slice(-6)}
                    </p>
                    <p className="text-[10px] text-text-secondary">
                      Lv{entry.level} {entry.level_name} | {entry.total_contributions} contributions
                    </p>
                  </div>
                  <span className="text-xs font-semibold glow-gold">
                    {entry.reputation_points.toLocaleString()} RP
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
