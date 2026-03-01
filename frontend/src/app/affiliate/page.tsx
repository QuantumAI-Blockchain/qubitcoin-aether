"use client";

import { motion } from "framer-motion";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { Card } from "@/components/ui/card";
import { AffiliateTree } from "@/components/aikgs/affiliate-tree";

function AffiliateContent() {
  return (
    <div className="min-h-screen pt-20 pb-12">
      <div className="mx-auto max-w-2xl px-4">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 text-center"
        >
          <h1 className="font-[family-name:var(--font-display)] text-3xl font-bold">
            <span className="glow-cyan">Affiliate Program</span>
          </h1>
          <p className="mt-2 text-sm text-text-secondary">
            Earn commissions by inviting friends to contribute knowledge
          </p>
        </motion.div>

        {/* Affiliate component */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
        >
          <AffiliateTree />
        </motion.div>

        {/* Commission tiers */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
        >
          <Card className="mb-4">
            <h3 className="mb-3 text-sm font-semibold text-text-secondary">Commission Structure</h3>
            <div className="space-y-3">
              <div className="rounded-lg bg-bg-deep p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-quantum-green">Level 1 — Direct</p>
                    <p className="text-xs text-text-secondary">Your direct referrals</p>
                  </div>
                  <span className="text-lg font-bold text-quantum-green">10%</span>
                </div>
              </div>
              <div className="rounded-lg bg-bg-deep p-3">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-quantum-violet">Level 2 — Indirect</p>
                    <p className="text-xs text-text-secondary">Your referrals&apos; referrals</p>
                  </div>
                  <span className="text-lg font-bold text-quantum-violet">5%</span>
                </div>
              </div>
            </div>
            <p className="mt-3 text-[10px] text-text-secondary/60">
              Commissions are paid from the AIKGS reward pool, not from contributors&apos; earnings.
            </p>
          </Card>
        </motion.div>

        {/* How to share */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Card>
            <h3 className="mb-3 text-sm font-semibold text-text-secondary">How to Share</h3>
            <div className="space-y-2 text-xs text-text-secondary">
              <div className="flex items-start gap-2">
                <span className="shrink-0 text-quantum-green">1.</span>
                <p>Register to get your unique referral code (QBC-XXXXXXXX)</p>
              </div>
              <div className="flex items-start gap-2">
                <span className="shrink-0 text-quantum-green">2.</span>
                <p>Share your link via Telegram, social media, or direct message</p>
              </div>
              <div className="flex items-start gap-2">
                <span className="shrink-0 text-quantum-green">3.</span>
                <p>When referrals contribute knowledge, you earn commissions automatically</p>
              </div>
              <div className="flex items-start gap-2">
                <span className="shrink-0 text-quantum-green">4.</span>
                <p>Commissions are added directly to your QBC balance</p>
              </div>
            </div>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}

export default function AffiliatePage() {
  return (
    <ErrorBoundary>
      <AffiliateContent />
    </ErrorBoundary>
  );
}
