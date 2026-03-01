"use client";

import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { PhiSpinner } from "@/components/ui/loading";
import { useWalletStore } from "@/stores/wallet-store";
import { useAIKGSStore } from "@/stores/aikgs-store";
import { RewardDashboard } from "@/components/aikgs/reward-dashboard";
import { UploadPanel } from "@/components/aikgs/upload-panel";
import { ContributionIndicator } from "@/components/aikgs/contribution-indicator";
import { APIKeyManager } from "@/components/aikgs/api-key-manager";
import { api, type AIKGSBounty } from "@/lib/api";
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

function BountyBoard() {
  const [bounties, setBounties] = useState<AIKGSBounty[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.aikgsGetBounties("open")
      .then((res) => setBounties(res.bounties))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <Card className="mb-4">
        <div className="flex h-24 items-center justify-center">
          <PhiSpinner className="h-5 w-5" />
        </div>
      </Card>
    );
  }

  return (
    <Card className="mb-4">
      <h3 className="mb-3 text-sm font-semibold glow-emerald">Knowledge Bounties</h3>
      {bounties.length === 0 ? (
        <p className="text-center text-xs text-text-secondary">No open bounties right now.</p>
      ) : (
        <div className="space-y-2">
          {bounties.map((b) => (
            <div key={b.bounty_id} className="rounded-lg bg-bg-deep p-3">
              <div className="mb-1 flex items-center justify-between">
                <span className="rounded-full bg-quantum-green/10 px-2 py-0.5 text-[10px] font-semibold text-quantum-green">
                  {b.domain}
                </span>
                <span className="text-xs font-bold glow-gold">{b.reward_amount.toFixed(2)} QBC</span>
              </div>
              <p className="text-xs text-text-primary">{b.description}</p>
              {b.boost_multiplier > 1 && (
                <p className="mt-1 text-[10px] text-golden">
                  {b.boost_multiplier}x seasonal boost active
                </p>
              )}
              <p className="mt-1 text-[10px] text-text-secondary">
                Expires: {new Date(b.expires_at * 1000).toLocaleDateString()}
              </p>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function RewardsContent() {
  const { connected } = useWalletStore();
  const { activeTab, setActiveTab } = useAIKGSStore();

  const tabs = [
    { id: "contribute" as const, label: "Contribute" },
    { id: "rewards" as const, label: "Rewards" },
    { id: "bounties" as const, label: "Bounties" },
    { id: "keys" as const, label: "API Keys" },
  ];

  return (
    <div className="min-h-screen pt-20 pb-12">
      <div className="mx-auto max-w-6xl px-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 text-center"
        >
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
            <span className="glow-gold">AIKGS</span>
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            Aether Incentivized Knowledge Growth System — Earn QBC by contributing knowledge
          </p>
        </motion.div>

        {/* Profile indicator */}
        {connected && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="mb-6"
          >
            <ContributionIndicator />
          </motion.div>
        )}

        {/* Tab navigation */}
        <div className="mb-6 flex justify-center gap-2">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`rounded-lg px-4 py-2 text-xs font-semibold transition ${
                activeTab === t.id
                  ? "bg-quantum-violet/20 text-quantum-violet"
                  : "text-text-secondary hover:bg-bg-elevated hover:text-text-primary"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mx-auto max-w-2xl"
        >
          {activeTab === "contribute" && <UploadPanel />}
          {activeTab === "rewards" && <RewardDashboard />}
          {activeTab === "bounties" && <BountyBoard />}
          {activeTab === "keys" && <APIKeyManager />}
        </motion.div>

        {/* How it works */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="mx-auto mt-12 max-w-4xl"
        >
          <h2 className="mb-6 text-center font-[family-name:var(--font-display)] text-lg font-bold">
            How It Works
          </h2>
          <div className="grid gap-4 md:grid-cols-4">
            {[
              { step: "1", title: "Contribute", desc: "Share knowledge via chat or direct upload" },
              { step: "2", title: "Score", desc: "AI scores quality and novelty (0-1.0)" },
              { step: "3", title: "Tier", desc: "Bronze → Silver → Gold → Diamond" },
              { step: "4", title: "Earn", desc: "Receive QBC rewards from the pool" },
            ].map((s) => (
              <Card key={s.step} className="text-center">
                <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-quantum-violet/20 font-[family-name:var(--font-display)] text-sm font-bold text-quantum-violet">
                  {s.step}
                </div>
                <h3 className="text-sm font-semibold text-text-primary">{s.title}</h3>
                <p className="mt-1 text-xs text-text-secondary">{s.desc}</p>
              </Card>
            ))}
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export default function RewardsPage() {
  return (
    <ErrorBoundary>
      <RewardsContent />
    </ErrorBoundary>
  );
}
