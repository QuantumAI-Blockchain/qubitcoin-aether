"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { showBackButton, hideBackButton } from "@/lib/telegram";
import { useAIKGSStore } from "@/stores/aikgs-store";
import { UploadPanel } from "@/components/aikgs/upload-panel";
import { RewardDashboard } from "@/components/aikgs/reward-dashboard";
import { ContributionIndicator } from "@/components/aikgs/contribution-indicator";

export default function TWAEarnPage() {
  const { activeTab, setActiveTab } = useAIKGSStore();

  useEffect(() => {
    showBackButton(() => window.history.back());
    return () => hideBackButton();
  }, []);

  return (
    <div className="px-4 pt-4">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-4"
      >
        <h1 className="font-[family-name:var(--font-display)] text-lg font-bold glow-gold">
          Earn QBC
        </h1>
        <p className="text-[10px] text-text-secondary">
          Contribute knowledge to earn rewards
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-4"
      >
        <ContributionIndicator />
      </motion.div>

      {/* Tab toggle */}
      <div className="mb-4 flex gap-2">
        <button
          onClick={() => setActiveTab("contribute")}
          className={`flex-1 rounded-lg py-2 text-xs font-semibold transition ${
            activeTab === "contribute"
              ? "bg-quantum-green/20 text-quantum-green"
              : "bg-bg-panel text-text-secondary"
          }`}
        >
          Contribute
        </button>
        <button
          onClick={() => setActiveTab("rewards")}
          className={`flex-1 rounded-lg py-2 text-xs font-semibold transition ${
            activeTab === "rewards"
              ? "bg-golden/20 text-golden"
              : "bg-bg-panel text-text-secondary"
          }`}
        >
          Rewards
        </button>
      </div>

      <motion.div
        key={activeTab}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        {activeTab === "contribute" ? <UploadPanel /> : <RewardDashboard />}
      </motion.div>
    </div>
  );
}
