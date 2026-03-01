"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { showBackButton, hideBackButton } from "@/lib/telegram";
import { AffiliateTree } from "@/components/aikgs/affiliate-tree";

export default function TWAReferPage() {
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
        <h1 className="font-[family-name:var(--font-display)] text-lg font-bold glow-cyan">
          Refer Friends
        </h1>
        <p className="text-[10px] text-text-secondary">
          Earn 10% L1 + 5% L2 commissions
        </p>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
      >
        <AffiliateTree />
      </motion.div>
    </div>
  );
}
