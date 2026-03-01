"use client";

import { useAIKGSStore } from "@/stores/aikgs-store";
import { AIKGS_TIERS, AIKGS_STREAK_MILESTONES } from "@/lib/constants";

interface ContributionIndicatorProps {
  className?: string;
  compact?: boolean;
}

function tierClass(tier: string): string {
  switch (tier) {
    case "bronze": return "tier-bronze";
    case "silver": return "tier-silver";
    case "gold": return "tier-gold";
    case "diamond": return "tier-diamond";
    default: return "text-text-secondary";
  }
}

function nextStreakMilestone(currentStreak: number): { days: number; multiplier: number } | null {
  for (const m of AIKGS_STREAK_MILESTONES) {
    if (currentStreak < m.days) return m;
  }
  return null;
}

export function ContributionIndicator({ className = "", compact = false }: ContributionIndicatorProps) {
  const { profile, recentContributions } = useAIKGSStore();

  if (!profile) return null;

  const latestContribution = recentContributions[0] ?? null;
  const nextMilestone = nextStreakMilestone(profile.current_streak);

  if (compact) {
    return (
      <div className={`flex items-center gap-2 text-xs ${className}`}>
        <span className="text-text-secondary">Lv{profile.level}</span>
        <span className={tierClass(latestContribution?.tier ?? "bronze")}>
          {profile.total_contributions} contributions
        </span>
        {profile.current_streak > 0 && (
          <span className={profile.current_streak >= 7 ? "streak-fire" : "text-golden"}>
            {profile.current_streak}d streak
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={`rounded-xl border border-border-subtle bg-bg-panel p-4 ${className}`}>
      {/* Level + RP */}
      <div className="mb-3 flex items-center justify-between">
        <div>
          <span className="text-xs text-text-secondary">Level {profile.level}</span>
          <h4 className="text-sm font-semibold text-text-primary">{profile.level_name}</h4>
        </div>
        <div className="text-right">
          <span className="text-xs text-text-secondary">RP</span>
          <p className="text-sm font-semibold glow-gold">{profile.reputation_points.toLocaleString()}</p>
        </div>
      </div>

      {/* Stats row */}
      <div className="mb-3 grid grid-cols-3 gap-2">
        <div className="rounded-lg bg-bg-deep p-2 text-center">
          <p className="text-lg font-bold text-text-primary">{profile.total_contributions}</p>
          <p className="text-[10px] text-text-secondary">Contributions</p>
        </div>
        <div className="rounded-lg bg-bg-deep p-2 text-center">
          <p className={`text-lg font-bold ${profile.current_streak >= 7 ? "streak-fire" : "text-golden"}`}>
            {profile.current_streak}
          </p>
          <p className="text-[10px] text-text-secondary">Day Streak</p>
        </div>
        <div className="rounded-lg bg-bg-deep p-2 text-center">
          <p className="text-lg font-bold text-quantum-violet">{profile.badges.length}</p>
          <p className="text-[10px] text-text-secondary">Badges</p>
        </div>
      </div>

      {/* Tier breakdown */}
      <div className="mb-3 flex items-center gap-1">
        {(["diamond", "gold", "silver", "bronze"] as const).map((t) => {
          const count = t === "diamond" ? profile.diamond_count : t === "gold" ? profile.gold_count : 0;
          const tier = AIKGS_TIERS[t];
          if (count === 0 && (t === "diamond" || t === "gold")) return null;
          return (
            <span
              key={t}
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${tierClass(t)}`}
              style={{ backgroundColor: `${tier.color}15` }}
            >
              {count > 0 ? `${count} ${tier.label}` : tier.label}
            </span>
          );
        })}
      </div>

      {/* Streak progress */}
      {nextMilestone && (
        <div className="rounded-lg bg-bg-deep p-2">
          <div className="mb-1 flex items-center justify-between text-[10px] text-text-secondary">
            <span>Next milestone: {nextMilestone.days}d ({nextMilestone.multiplier}x)</span>
            <span>{profile.current_streak}/{nextMilestone.days}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-border-subtle">
            <div
              className="h-full rounded-full bg-golden transition-all"
              style={{ width: `${Math.min(100, (profile.current_streak / nextMilestone.days) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Latest contribution */}
      {latestContribution && (
        <div className="mt-3 rounded-lg bg-bg-deep p-2">
          <p className="text-[10px] text-text-secondary">Latest Contribution</p>
          <div className="mt-1 flex items-center justify-between">
            <span className={`text-xs font-semibold ${tierClass(latestContribution.tier)}`}>
              {latestContribution.tier.toUpperCase()}
            </span>
            <span className="text-xs text-golden">
              +{latestContribution.reward_amount.toFixed(4)} QBC
            </span>
          </div>
          <p className="mt-0.5 text-[10px] text-text-secondary">
            Q: {latestContribution.quality_score.toFixed(2)} | N: {latestContribution.novelty_score.toFixed(2)} | {latestContribution.domain}
          </p>
        </div>
      )}
    </div>
  );
}
